"""
quiz_generator.py — UPSC CSE-Grade Quiz Generation Engine v6.0
===============================================================
Generates questions that match the actual cognitive difficulty and
format of UPSC Prelims (2015-2025) and Mains GS papers.

v6.0 Upgrades:
  • Fixed missing functions: fallback_quiz(), MAINS_SUPPLEMENT, _build_theme_instruction()
  • Per-option elaborative explanations (why each option is correct/incorrect)
  • Source-enriched explanations pulling from DB news + URL summaries
  • Enhanced retry logic with different prompt strategies
  • Difficulty calibration based on UPSC 2023-2024 trend data
"""

import re
import json
from llm import ask_llm, ask_llm_high_quality


# ── UPSC THEME DISTRIBUTION (mirrors real paper stats) ───────────────────────
THEME_WEIGHTS = {
    "Polity & Governance":  20,   # Article-based, constitutional provisions
    "Economy & Finance":    18,   # RBI, budget, indices, fiscal policy
    "Environment & Ecology":16,   # NGT, conventions, species, disasters
    "International Relations": 14,# Treaties, groupings, summits
    "Science & Technology": 12,   # Space, biotech, defence tech
    "History & Culture":    10,   # Ancient/Medieval/Modern, art forms
    "Social Issues":         6,   # Poverty, gender, tribal
    "Geography":             4,   # Physical, rivers, coasts
}


# ── MAINS SUPPLEMENT (used when generating 6+ questions) ─────────────────────
MAINS_SUPPLEMENT = """
MAINS-STYLE INTEGRATION (for larger question sets):
  • Include at least 1 case-study question (GS Paper IV style)
  • Include at least 1 "map-based" or geography question
  • Ensure no two questions test the same underlying concept
  • At least 2 questions should require knowledge of post-2020 developments
"""


# ── THEME DISTRIBUTION BUILDER ────────────────────────────────────────────────
def _build_theme_instruction(n: int) -> str:
    """
    Build a theme distribution instruction based on question count.
    Ensures diversity across UPSC GS themes proportional to real paper stats.
    """
    if n <= 3:
        return "Cover at least 2 different GS themes from: Polity, Economy, Environment, IR, S&T."
    
    # Calculate target per theme based on weights
    total_weight = sum(THEME_WEIGHTS.values())
    distribution = []
    assigned = 0
    
    for theme, weight in THEME_WEIGHTS.items():
        count = max(1, round(n * weight / total_weight))
        if assigned + count > n:
            count = n - assigned
        if count > 0:
            distribution.append(f"  • {theme}: {count} question(s)")
            assigned += count
        if assigned >= n:
            break
    
    # If we haven't assigned enough, add to the top themes
    while assigned < n:
        distribution.append(f"  • General Studies: 1 question")
        assigned += 1
    
    return (
        f"THEME DISTRIBUTION (target {n} questions — spread across themes):\n"
        + "\n".join(distribution)
        + "\n  ⚠️ No two questions should test the exact same concept."
    )


# ── FALLBACK QUIZ (when all LLM attempts fail) ───────────────────────────────
def fallback_quiz() -> tuple[list, list]:
    """
    Return a curated set of 5 UPSC-quality questions as a fallback
    when LLM generation fails completely.
    """
    questions = [
        (
            "Consider the following statements about the National Green Tribunal (NGT):\n"
            "1. NGT was established under the National Green Tribunal Act, 2010.\n"
            "2. NGT has the power to hear all civil cases relating to environmental issues.\n"
            "3. The Chairperson of NGT is appointed by the Central Government in consultation with the Chief Justice of India.\n"
            "Which of the statements given above is/are correct?\n"
            "A) 1 and 2 only\n"
            "B) 1 and 3 only\n"
            "C) 2 and 3 only\n"
            "D) 1, 2 and 3"
        ),
        (
            "With reference to the Monetary Policy Committee (MPC) of the Reserve Bank of India, consider the following statements:\n"
            "1. The MPC consists of six members — three from RBI and three external members.\n"
            "2. The Governor of RBI is the ex-officio chairperson of the MPC.\n"
            "3. Decisions of the MPC are taken by a simple majority with the Governor having a casting vote.\n"
            "Which of the statements given above is/are correct?\n"
            "A) 1 only\n"
            "B) 1 and 2 only\n"
            "C) 2 and 3 only\n"
            "D) 1, 2 and 3"
        ),
        (
            "Which of the following best describes the term 'Green GDP'?\n"
            "A) GDP calculated after deducting environmental costs and natural resource depletion\n"
            "B) GDP from the renewable energy sector only\n"
            "C) GDP growth rate adjusted for green technology investments\n"
            "D) GDP measured exclusively from environmentally sustainable industries"
        ),
        (
            "Consider the following pairs:\n"
            "1. Article 14 : Right to Equality\n"
            "2. Article 19 : Right to Freedom\n"
            "3. Article 32 : Right to Constitutional Remedies\n"
            "How many of the above pairs are correctly matched?\n"
            "A) Only one pair\n"
            "B) Only two pairs\n"
            "C) All three pairs\n"
            "D) None of the pairs"
        ),
        (
            "Assertion (A): India is a member of the Nuclear Suppliers Group (NSG).\n"
            "Reason (R): India signed the Nuclear Non-Proliferation Treaty (NPT) in 1968.\n"
            "Which is correct?\n"
            "A) Both A and R are true, R is the correct explanation of A\n"
            "B) Both A and R are true, R is NOT the correct explanation of A\n"
            "C) A is true, R is false\n"
            "D) A is false, R is false"
        ),
    ]
    answers = ["B", "D", "A", "C", "D"]
    return questions, answers


# ── AUTHENTIC UPSC QUESTION TYPE TEMPLATES ────────────────────────────────────
UPSC_QUESTION_FRAMEWORK = """
You are a SENIOR UPSC CSE QUESTION SETTER and IAS TOPPER MENTOR — with 20 years of experience crafting
questions for UPSC Prelims and Mains GS Papers. Your questions have appeared in
real UPSC papers. You NEVER write easy or generic questions.

═══════════════ TYPE 1 ── STATEMENT-BASED (The Gold Standard)
# ─────────────────────────────────────────────────────────────────────────────
"Consider the following statements:
 1. [Factually nuanced statement — partially true or subtly false]
 2. [Concept-based statement linking to NCERT/Standard Book]
 3. [Figure/Data based statement with a precise trap]
 Which of the statements given above is/are correct?
 A) 1 only  B) 2 and 3 only  C) 1 and 3 only  D) 1, 2 and 3"

TYPE 1b ── "HOW MANY" PAIRS (Latest 2023-2024 UPSC Pattern)
# ─────────────────────────────────────────────────────────────────────────────
"Consider the following pairs:
 1. [Term/Place] : [Context/Reason]
 2. [Term/Place] : [Context/Reason]
 3. [Term/Place] : [Context/Reason]
 How many of the above pairs are correctly matched?
 A) Only one  B) Only two  C) All three  D) None"

TYPE 2 ── ASSERTION-REASON (Conceptual Depth)
# ─────────────────────────────────────────────────────────────────────────────
"Assertion (A): [Statement of principle]
 Reason (R): [Scientific/Legal/Economic justification]
 Which is correct?
 A) Both A and R are true, R is the correct explanation of A
 B) Both A and R are true, R is NOT the correct explanation of A
 C) A is true, R is false
 D) A is false, R is true"

═══════════════════════════════════════════════════════════════
MANDATORY QUALITY STANDARDS
═══════════════════════════════════════════════════════════════
1. **The "Static Link" Rule:** Every question must have a `Static Link` to a specific Book/NCERT chapter.
2. **Subtle Traps:** Change "Ministry of Finance" to "Ministry of Commerce", or "100%" to "90%", or "Mandatory" to "Voluntary".
3. **Statement-by-Statement Debunking:** Explanations MUST explain why EACH statement is correct or incorrect individually.
4. **Per-Option Analysis:** For each option A/B/C/D, provide a separate reason why it is correct or incorrect.
5. **No Generalizations:** Avoid "various", "multiple", "all sections". Be precise.
6. **Difficulty:** 80% Hard (matching UPSC 2024 trend).
"""

# ── MAIN GENERATION FUNCTION ──────────────────────────────────────────────────
def generate_quiz(text: str, n: int = 5, subject: str = None, book: str = None) -> tuple[list, list]:
    """
    Generate n UPSC-CSE-grade MCQs from current affairs or book content.
    
    Algorithm:
      1. Build a rich, structured prompt with UPSC framework + theme instruction
      2. Fetch related context from DB for enriched explanations
      3. Call LLM with high token budget (use high-quality model when available)
      4. Parse with multi-line-aware regex
      5. Validate: check 4 options, answer letter, minimum length
      6. On failure: re-attempt with simplified prompt
      7. Final fallback: return curated UPSC questions

    Returns:
        (questions_list, answers_list) — both same length
    """
    theme_instruction = _build_theme_instruction(n)
    context_prefix = f"SUBJECT: {subject} | BOOK: {book}\n" if subject or book else ""
    mains_note = MAINS_SUPPLEMENT if n >= 6 else ""
    
    # Fetch related context from DB for richer explanations
    enrichment = ""
    try:
        from pyq_engine import _fetch_related_context
        related = _fetch_related_context(text.split("\n")[:10], max_items=5)
        if related:
            enrichment = f"\n\nENRICHMENT CONTEXT (coaching materials & news for richer explanations):\n{related}"
    except Exception:
        pass

    prompt = f"""{UPSC_QUESTION_FRAMEWORK}

{theme_instruction}

{mains_note}

══════════════════════════════════════════════════════════════
SOURCE MATERIAL / CONTEXT
{context_prefix}
══════════════════════════════════════════════════════════════
{text[:4000]}
{enrichment}

══════════════════════════════════════════════════════════════
YOUR TASK
Generate EXACTLY {n} MCQs based on the provided material. 
If a BOOK/SUBJECT is mentioned, ensure questions test deep conceptual concepts from that source, linking them to the contemporary context provided.
Map each item to the appropriate UPSC GS theme.
Mix question types (Type 1 or 1b is mandatory for ≥2 questions).

STRICT OUTPUT FORMAT — repeat EXACTLY for every question:
Q[N]. [Full question text — may span multiple lines]
A) [Option A — plausible, not trivially wrong]
B) [Option B]
C) [Option C]
D) [Option D]
Answer: [A/B/C/D]
Explanation: [DEBUNKING LOGIC: Explain Statement 1 (Correct/Incorrect because...), Statement 2 (...), Statement 3 (...). Cite Article/Act/Year/Data.]
Option A: [Why A is correct/incorrect]
Option B: [Why B is correct/incorrect]
Option C: [Why C is correct/incorrect]
Option D: [Why D is correct/incorrect]
Static Link: [Specific Book/NCERT Chapter]
Difficulty: [Hard / Medium]
Theme: [Subject Area]

Begin with Q1. Do NOT add any preamble, conclusion, or markdown headers."""

    # Use high-quality model for better UPSC question output
    raw = ask_llm_high_quality(prompt)

    if not raw or "All models failed" in raw:
        return fallback_quiz()

    questions, answers = _parse_quiz_robust(raw)

    # If we got enough questions, return them
    if len(questions) >= n:
        return questions[:n], answers[:n]

    # ── RETRY with simplified prompt ──────────────────────────────────────────
    simple_prompt = f"""Generate {n} UPSC Prelims MCQs from this content.
Use a mix of statement-based, assertion-reason, and direct MCQ formats.
Include tricky options — no trivially wrong choices.

For each question, explain why each option is correct or incorrect.

STRICT FORMAT for EVERY question:
Q[N]. [Question text]
A) [option]
B) [option]
C) [option]
D) [option]
Answer: [A/B/C/D]
Explanation: [Detailed explanation with per-option analysis citing facts/articles/acts]

Content:
{text[:2500]}

Start with Q1."""

    raw2 = ask_llm(simple_prompt)
    if raw2:
        q2, a2 = _parse_quiz_robust(raw2)
        if len(q2) >= n:
            return q2[:n], a2[:n]
        # Merge what we got from both attempts
        combined_q = questions + [q for q in q2 if q not in questions]
        combined_a = answers + [a2[i] for i, q in enumerate(q2) if q not in questions]
        if len(combined_q) >= n:
            return combined_q[:n], combined_a[:n]

    # ── FINAL FALLBACK ─────────────────────────────────────────────────────────
    return fallback_quiz()

# Proxy for syllabus_quiz_generator function
def generate_syllabus_quiz(*args, **kwargs):
    from syllabus_quiz_generator import generate_syllabus_quiz as gen
    return gen(*args, **kwargs)


# ── ROBUST MULTI-LINE PARSER ──────────────────────────────────────────────────
def _parse_quiz_robust(text: str) -> tuple[list, list]:
    """
    Parse LLM output into (questions, answers) lists.

    Handles:
      • Multi-line question bodies (statement-based questions)
      • Options on the same line or separate lines
      • Answer on its own line
      • Optional Explanation / Difficulty / Theme lines (ignored for output)
    """
    questions = []
    answers = []

    # Split into question blocks at "Q<N>." markers
    # Allow for Q1. Q2. ... Q20. at start of line
    blocks = re.split(r'\n(?=Q\d{1,2}\.)', '\n' + text.strip())

    for block in blocks:
        block = block.strip()
        if not block or not re.match(r'Q\d{1,2}\.', block):
            continue

        # Extract answer first
        ans_match = re.search(r'(?i)^Answer:\s*([A-D])', block, re.MULTILINE)
        if not ans_match:
            # Try inline Answer: X pattern
            ans_match = re.search(r'(?i)Answer:\s*([A-D])', block)
        if not ans_match:
            continue
        answer_letter = ans_match.group(1).upper()

        # Find where the options block starts
        opt_a_match = re.search(r'(?m)^A\)', block)
        if not opt_a_match:
            # Try "A) " anywhere in the line
            opt_a_match = re.search(r'A\)', block)
        if not opt_a_match:
            continue

        # Question text = everything from start of block up to first option
        q_raw = block[:opt_a_match.start()].strip()
        # Remove leading "Q<N>. " prefix
        q_raw = re.sub(r'^Q\d{1,2}\.\s*', '', q_raw).strip()

        # Validate question has meaningful content
        if len(q_raw) < 15:
            continue

        # Extract options
        opts = _extract_options(block[opt_a_match.start():ans_match.start()])
        if len(opts) < 4:
            continue

        # Reconstruct full question with options for display
        full_q = _format_question(q_raw, opts)
        questions.append(full_q)
        answers.append(answer_letter)

    return questions, answers


def _extract_options(text: str) -> dict:
    """Extract A/B/C/D options from the options+answer block."""
    opts = {}
    # Match patterns like "A) text" or "A. text"
    pattern = re.finditer(r'(?m)^([A-D])[)\.]\s*(.+?)(?=\n[A-D][)\.]\s|\Z)', text, re.DOTALL)
    for m in pattern:
        letter = m.group(1).upper()
        content = m.group(2).strip()
        # Remove any trailing "Answer:" or "Explanation:" bleeds
        content = re.split(r'(?i)\n?Answer:', content)[0].strip()
        opts[letter] = content
    return opts


def _format_question(q_text: str, opts: dict) -> str:
    """Format question + options into a display-ready string."""
    out = q_text
    for letter in ['A', 'B', 'C', 'D']:
        if letter in opts:
            out += f"\n{letter}) {opts[letter]}"
    return out


# ── ANSWER EXTRACTION UTILITY ─────────────────────────────────────────────────
def extract_answers_from_formatted(questions: list) -> list:
    """
    If questions already contain embedded answers (legacy format),
    extract just the answer letters. Returns empty list if not applicable.
    """
    # This utility is not used in main flow but kept for compatibility
    return []
