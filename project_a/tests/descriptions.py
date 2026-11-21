"""50 plain-language user descriptions for the parser (Task 1 / Task 3).

expected  : fields the parser must return (all other fields must stay 0/False/default,
            i.e. nothing may be invented), or None when a clarifying question is required.
clarify   : the fields (or ambiguity keys) the clarifying question should be about.

Policy being tested (see parser/parse.py): never guess age or gross salary; ask when the
salary basis/period is ambiguous (CTC, take-home, bare number), when rent/home-loan/parent-
insurance is mentioned without the amounts needed, or when the text contradicts itself.
Investments that are not mentioned are assumed to be zero and reported as assumptions.
"""

def ok(i, style, text, **exp):
    return {"id": f"d{i:02d}", "style": style, "text": text, "expected": exp, "clarify": []}


def ask(i, style, text, *keys):
    return {"id": f"d{i:02d}", "style": style, "text": text, "expected": None, "clarify": list(keys)}


DESCRIPTIONS = [
    ok(1, "plain", "I'm 32 and earn 18 lakh a year. No investments.", age=32, gross_salary=1_800_000),
    ok(2, "plain", "Salary 12,00,000 per annum, age 28, I put 1.5 lakh in PPF and ELSS.",
       age=28, gross_salary=1_200_000, sec_80c=150_000),
    ok(3, "hinglish", "Meri age 35 saal hai, salary 25 lakh per year hai. 80C mein 1.5 lakh invest kiya hai aur NPS mein 50 hazaar.",
       age=35, gross_salary=2_500_000, sec_80c=150_000, sec_80ccd_1b=50_000),
    ok(4, "hinglish", "Mera salary 80,000 rupaye mahina hai, umar 26.", age=26, gross_salary=960_000),
    ok(5, "detailed", "Age 45. Annual gross salary is Rs 30,00,000. Basic is 12 lakh, HRA received 6 lakh, I pay rent 20,000 per month in Mumbai.",
       age=45, gross_salary=3_000_000, basic_salary=1_200_000, hra_received=600_000, rent_paid=240_000, metro_city=True),
    ok(6, "casual", "turning 61 this year, salary 9.5 lakh a year. mediclaim premium 40k for me",
       age=61, gross_salary=950_000, sec_80d_self=40_000),
    ok(7, "detailed", "I am 58, salary 22L per year, my parents (both 75) have mediclaim, I pay 45,000 for it.",
       age=58, gross_salary=2_200_000, sec_80d_parents=45_000, parents_senior=True),
    ok(8, "plain", "Home loan interest Rs 1.8 lakh, I am 40, annual salary 16 lakh.",
       age=40, gross_salary=1_600_000, home_loan_interest=180_000),
    ok(9, "detailed", "Salary 50 lakh, age 38, 80C maxed at 1.5 lakh, NPS 50k extra, health insurance 25k for self and 30k for parents (not senior).",
       age=38, gross_salary=5_000_000, sec_80c=150_000, sec_80ccd_1b=50_000, sec_80d_self=25_000, sec_80d_parents=30_000),
    ok(10, "terse", "29M, 9.6L pa, nothing else", age=29, gross_salary=960_000),
    ok(11, "hinglish", "bhai mera CTC nahi, gross salary 14 lakh hai saalana, 31 saal ka hoon, Delhi mein rehta hoon, basic 5.6 lakh, HRA 2.8 lakh milta hai, kiraya 25000 mahina",
       age=31, gross_salary=1_400_000, basic_salary=560_000, hra_received=280_000, rent_paid=300_000, metro_city=True),
    ok(12, "terse", "I'm 50, make 1 crore per year.", age=50, gross_salary=10_000_000),
    ok(13, "symbols", "Annual salary is ₹6,50,000, I am 24 years old.", age=24, gross_salary=650_000),
    ok(14, "detailed", "Age: 36. Gross: 21,60,000/yr. Rent 30k/month in Bengaluru, HRA 4.2 lakh, basic 8.64 lakh.",
       age=36, gross_salary=2_160_000, basic_salary=864_000, hra_received=420_000, rent_paid=360_000, metro_city=False),
    ok(15, "formal", "I am sixty-three years old, a retired consultant; salary income 11 lakh; 80D premium 52000 for myself.",
       age=63, gross_salary=1_100_000, sec_80d_self=52_000),
    ok(16, "casual", "I'm 27 and I earn 75k per month, I invest 12,500 per month in ELSS.",
       age=27, gross_salary=900_000, sec_80c=150_000),
    ok(17, "hinglish", "Age 42, salary 33 lakh, home loan ka byaaj 2.4 lakh hai, aur 80C mein 1 lakh.",
       age=42, gross_salary=3_300_000, home_loan_interest=240_000, sec_80c=100_000),
    ok(18, "plain", "Gross annual pay of 8 lakh rupees; I'm 55; my employer gives HRA but I live in my own house so I pay no rent.",
       age=55, gross_salary=800_000),
    ok(19, "hinglish", "Meri umar 45 hai, income 17.5 lakh saalana. Parents 70 saal ke hain, unka health insurance premium 48000 main bharta hoon.",
       age=45, gross_salary=1_750_000, sec_80d_parents=48_000, parents_senior=True),
    ok(20, "terse", "34 yrs, 24 LPA fixed gross. Zero deductions.", age=34, gross_salary=2_400_000),
    ok(21, "plain", "At 66, my salary (from re-employment) is 15 lakh a year. NPS 50000.",
       age=66, gross_salary=1_500_000, sec_80ccd_1b=50_000),
    ok(22, "detailed", "Age 47, 1.2 crore a year gross. I claim 80C 1.5 lakh, NPS 50k, 80D 25k for myself, home loan interest 2 lakh.",
       age=47, gross_salary=12_000_000, sec_80c=150_000, sec_80ccd_1b=50_000, sec_80d_self=25_000, home_loan_interest=200_000),
    ok(23, "plain", "Rs 40,000 monthly salary, 23 years old fresher, no investments.", age=23, gross_salary=480_000),
    ok(24, "terse", "82 years old, salary 7 lakh per annum.", age=82, gross_salary=700_000),
    ok(25, "hindi_script", "मेरी उम्र 33 साल है और सालाना वेतन 18 लाख रुपये है।",
       age=33, gross_salary=1_800_000),
    ok(26, "detailed", "Age 30. My CTC is 20 lakh but my gross salary is 18 lakh per year.", age=30, gross_salary=1_800_000),
    ok(27, "plain", "Salary 10 lakh a year, 41 years, paid 1,50,000 life insurance premium and 50,000 into PPF.",
       age=41, gross_salary=1_000_000, sec_80c=200_000),
    ok(28, "detailed", "29 yrs, salary 13.2 lakh/annum, rent 18000 pm in Chennai, HRA component 2.64 lakh, basic 5.28 lakh.",
       age=29, gross_salary=1_320_000, basic_salary=528_000, hra_received=264_000, rent_paid=216_000, metro_city=True),

    ask(29, "incomplete", "I earn 15 lakh.", "age"),
    ask(30, "incomplete", "I am 35 years old.", "gross_salary"),
    ask(31, "hinglish", "Mera salary achha hai, 30 saal ka hoon.", "gross_salary"),
    ask(32, "ambiguous", "My CTC is 24 lakh, I'm 30.", "gross_salary_basis"),
    ask(33, "ambiguous", "My take-home is 90,000 per month; age 33.", "gross_salary_basis"),
    ask(34, "incomplete", "I'm 28 and paying rent of 25,000 a month; salary 18 lakh.", "basic_salary", "hra_received", "metro_city"),
    ask(35, "incomplete", "Age 40, salary 20 lakh, I live in a rented flat in Pune, HRA is part of my pay.", "basic_salary", "hra_received", "rent_paid"),
    ask(36, "incomplete", "I'm 31, 16 lakh salary, I have a home loan.", "home_loan_interest"),
    ask(37, "incomplete", "Age 50, salary 28 lakh, I pay health insurance for my parents.", "sec_80d_parents", "parents_senior"),
    ask(38, "contradictory", "Age 34. Actually I am 52. Salary 19 lakh.", "age"),
    ask(39, "contradictory", "Salary is 12 lakh per year, no wait, 15 lakh per year. Age 38.", "gross_salary"),
    ask(40, "contradictory", "I'm 45, I make 20 lakh annually and 1.5 lakh per month.", "gross_salary"),
    ask(41, "ambiguous", "I'm a senior citizen, salary 10 lakh.", "age"),
    ask(42, "vague", "Young, about 25ish, salary maybe 8-10 lakh.", "gross_salary"),
    ask(43, "incomplete", "Rent 30,000 per month in Delhi, age 33, salary 24 lakh, basic is 40% of salary.", "hra_received"),
    ask(44, "ambiguous", "I earn 90000, age 37.", "gross_salary_period"),
    ask(45, "hinglish", "Meri age 44 hai, salary 22 lakh hai, aur mera ghar kiraye ka hai.", "basic_salary", "hra_received", "rent_paid", "metro_city"),
    ask(46, "ambiguous", "I'm 36 and got a 12 lakh salary plus a 3 lakh bonus. Is the bonus included in the salary?", "gross_salary_basis"),
    ask(47, "incomplete", "Salary 18 lakh. I invest in NPS.", "age", "sec_80ccd_1b"),
    ask(48, "contradictory", "Age 55. Salary 14 lakh. 80C investments 2 lakh in ELSS, and I am under 40.", "age"),
    ask(49, "incomplete", "I'm 39, salary 16 lakh, 80D premium paid but I don't remember the amount.", "sec_80d_self"),
    ask(50, "hinglish", "Mujhe nahi pata mera salary kitna hai, 29 saal ka hoon.", "gross_salary"),
]
assert len(DESCRIPTIONS) == 50
