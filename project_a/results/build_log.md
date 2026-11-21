# Build log (facts recorded while building, used for RESULTS_A and AI_USAGE)

- Oracle bug caught: first version rounded fractional rupees to the nearest rupee before the Rs 10 rounding of Sec 288A. The official CBDT example (2,52,844.99 -> ignore paise -> 2,52,844 -> 2,52,840) shows paise are ignored first. Fixed in tests/oracle.py. The hand-coded rules were already equivalent (exact fractions).
- 2026-11-20 19:44:20 compile FY2024-25 started (Qwen3.5-9B Q4_K_M, local); 104.9 s, 2,527 in / 4,280 out tokens, 425 lines.
- 19:46:10 raw output measured: all 258 cases raised (loud). Read top to bottom; 17 defects logged in generated/REVIEW.md.
- 19:47:24 reviewed module written and green on the suite (case-exact 1.0). Raw + crash-fix-only: 194/256 silently wrong.
- Suite bug caught: two FY2025-26 anchor cases were placed in the FY2024-25 file; the (correctly) refusing compiled FY24-25 rules exposed it. Moved.
- 19:48:10 compile FY2025-26 started.
- 19:50:38 compile FY2025-26 finished (142.1 s, 2,467 in / 5,699 out, 450 lines): 225/238 loud UnboundLocalError, 12 silent wrong, 1 right. Draft rejected, not patched.
- 19:51:04 reviewed FY2025-26 module (derived from reviewed FY2024-25, 11 changed lines) green: 238/238 exact.
- 19:52 hand-coded rules FY2025-26: new YAML file fy2025_26.yaml (26 changed lines vs fy2024_25.yaml incl. comments) plus 0 code lines; 238/238 exact (created at the start of the build, before the compiled path was run).
