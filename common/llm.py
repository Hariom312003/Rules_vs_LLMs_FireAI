"""Thin Gemini wrapper shared by both projects.

Every call is recorded (latency, tokens, notional cost) so the measurement
tasks in both projects can read real numbers from `LLMClient.stats`.
The free tier costs nothing, so cost is *notional*: tokens x list price.
Verify the prices below against the current Gemini pricing page before
quoting them in RESULTS_*.md.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

CACHE_DIR = Path(__file__).resolve().parents[1] / ".llm_cache"

# USD per 1M tokens (input, output). Keyed by model-name prefix. EDIT / VERIFY.
PRICES_PER_M = {
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-3.5-flash": (0.10, 0.40),
    "gemini-3.8-flash": (0.10, 0.40),
}


def _price(model: str) -> tuple[float, float]:
    for prefix, p in PRICES_PER_M.items():
        if model.startswith(prefix):
            return p
    return (0.0, 0.0)


@dataclass
class CallRecord:
    latency_s: float
    in_tokens: int
    out_tokens: int
    cost_usd: float
    cached: bool
    notional_usd: float = 0.0  # tokens x Gemini list price, also filled for local models


@dataclass
class LLMStats:
    calls: list[CallRecord] = field(default_factory=list)

    def summary(self) -> dict:
        live = [c for c in self.calls if not c.cached]
        n = len(live)
        return {
            "live_calls": n,
            "cached_calls": len(self.calls) - n,
            "total_cost_usd": sum(c.cost_usd for c in live),
            "notional_gemini_usd": sum(c.notional_usd for c in live),
            "mean_latency_s": (sum(c.latency_s for c in live) / n) if n else 0.0,
            "in_tokens": sum(c.in_tokens for c in live),
            "out_tokens": sum(c.out_tokens for c in live),
        }


class LLMClient:
    def __init__(self, model: str | None = None, use_cache: bool | None = None):
        # LLM_BACKEND=gemini (default, free tier) | local (OpenAI-compatible llama-server)
        self.backend = os.getenv("LLM_BACKEND", "gemini").lower()
        self.local_url = os.getenv("LOCAL_LLM_URL", "http://127.0.0.1:8090/v1")
        default = (os.getenv("LOCAL_LLM_MODEL", "LFM2.5-1.2B-Instruct") if self.backend == "local"
                   else os.getenv("GEMINI_MODEL", "gemini-3.5-flash"))
        self.model = model or default
        self.use_cache = (
            use_cache if use_cache is not None else os.getenv("LLM_CACHE", "1") == "1"
        )
        self.stats = LLMStats()
        self._client = None

    def _get_client(self):
        if self._client is None:
            from google import genai

            key = os.getenv("GEMINI_API_KEY")
            if not key:
                raise RuntimeError("GEMINI_API_KEY is not set (see .env.example)")
            self._client = genai.Client(api_key=key)
        return self._client

    def _cache_path(self, key: str) -> Path:
        return CACHE_DIR / f"{key}.json"

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        json_mode: bool = False,
        use_cache: bool | None = None,
        max_tokens: int = 1024,
    ) -> str:
        """Return model text. Pass use_cache=False for the determinism runs."""
        cache_on = self.use_cache if use_cache is None else use_cache
        key = hashlib.sha256(
            json.dumps([self.model, system, prompt, temperature, json_mode]).encode()
        ).hexdigest()
        path = self._cache_path(key)
        if cache_on and path.exists():
            d = json.loads(path.read_text(encoding="utf-8"))
            self.stats.calls.append(CallRecord(0.0, 0, 0, 0.0, True))
            return d["text"]

        if self.backend == "local":
            return self._generate_local(prompt, system, temperature, json_mode, cache_on, path, max_tokens)

        from google.genai import types
        from tenacity import retry, stop_after_attempt, wait_exponential

        cfg = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            response_mime_type="application/json" if json_mode else None,
            max_output_tokens=max_tokens,
        )

        @retry(stop=stop_after_attempt(5), wait=wait_exponential(min=2, max=60))
        def _call():
            return self._get_client().models.generate_content(
                model=self.model, contents=prompt, config=cfg
            )

        t0 = time.perf_counter()
        resp = _call()
        latency = time.perf_counter() - t0
        um = resp.usage_metadata
        tin = getattr(um, "prompt_token_count", 0) or 0
        tout = getattr(um, "candidates_token_count", 0) or 0
        pin, pout = _price(self.model)
        cost = (tin * pin + tout * pout) / 1_000_000
        self.stats.calls.append(CallRecord(latency, tin, tout, cost, False, cost))

        text = resp.text or ""
        if cache_on:
            CACHE_DIR.mkdir(exist_ok=True)
            path.write_text(json.dumps({"text": text}), encoding="utf-8")
        return text

    def _generate_local(self, prompt, system, temperature, json_mode, cache_on, path, max_tokens=1024) -> str:
        """Local llama-server (OpenAI-compatible). Cost is $0 API; latency/tokens still recorded."""
        import requests

        msgs = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}]
        body = {"model": self.model, "messages": msgs, "temperature": temperature, "max_tokens": max_tokens}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        t0 = time.perf_counter()
        r = requests.post(f"{self.local_url}/chat/completions", json=body, timeout=600)
        r.raise_for_status()
        latency = time.perf_counter() - t0
        d = r.json()
        u = d.get("usage", {})
        tin, tout = u.get("prompt_tokens", 0), u.get("completion_tokens", 0)
        pin, pout = _price("gemini-2.0-flash")  # notional: what the same tokens would cost on Gemini
        self.stats.calls.append(CallRecord(latency, tin, tout, 0.0, False, (tin * pin + tout * pout) / 1_000_000))
        text = d["choices"][0]["message"]["content"] or ""
        if cache_on:
            CACHE_DIR.mkdir(exist_ok=True)
            path.write_text(json.dumps({"text": text}), encoding="utf-8")
        return text
