#!/usr/bin/env python3
"""
syllabus_quiz_generator.py — UPSC-Authentic Syllabus Resource Quiz Generator
=============================================================================
Creates MCQs from Yojana, Kurukshetra, PIB summaries and other syllabus resources
at authentic UPSC Prelims difficulty — NOT basic recall questions.

Key upgrades:
  • UPSC question type taxonomy (statement-based, AR, match, NOT-correct)
  • Bloom's Taxonomy Level 3-5 framing (Application / Analysis / Evaluation)
  • Calibrated difficulty distribution (no trivially wrong options)
  • Per-option explanations
  • Difficulty tagging per question
"""

from llm import ask_llm_high_quality, ask_llm
import json
import re


# ── UPSC QUALITY PROMPT TEMPLATE ─────────────────────────────────────────────
_UPSC_SYSTEM = """You are a SENIOR UPSC CSE QUESTION SETTER creating questions from a government publication.
Questions must match authentic UPSC Prelims difficulty — Medium to Hard.
NEVER write questions that can be answered by common sense or basic GK alone.
ALWAYS test conceptual understanding, specific provisions, data, and policy nuances."""

_QUESTION_TYPES = """
MANDATORY QUESTION TYPE DISTRIBUTION:
  ✦ 40% Statement-Based: "Consider the following statements about [specific scheme/concept]...
     Which is/are correct?" — include at least one subtle trap (wrong year/provision/figure)
  ✦ 20% NOT-Correct: "Which of the following statements about [topic] is NOT correct?"
     → 3 options are genuinely correct; 1 has a specific factual error
  ✦ 20% Analytical/Application: "Which of the following best explains/identifies...?"
     → Test understanding of WHY, not just WHAT
  ✦ 10% Assertion-Reason: "Assertion (A): [specific claim] / Reason (R): [causal claim]"
  ✦ 10% Match the Following: List-I matched to List-II with code options

QUALITY RULES (non-negotiable):
  → All 4 options must be plausible — a student who has read about the topic should need
    to think carefully to eliminate wrong options
  → Cite Article / Section / Act / Year / Data in explanations (not vague references)
  → Difficulty: 60% Medium-Hard, 40% Hard — NO easy questions
  → Do NOT repeat the same question concept twice in one set
  → Explanations must cite WHY each wrong option is wrong (not just state the correct answer)
"""


def generate_syllabus_quiz(
    resource_type: str,
    summary_content: str,
    num_questions: int = 5
) -> tuple[list | None, str | None]:
    """
    Generate UPSC-quality MCQs from a syllabus resource summary.

    Args:
        resource_type: Source type (Yojana, Kurukshetra, PIB, etc.)
        summary_content: The content to generate questions from
        num_questions: Number of questions (3-15)

    Returns:
        (questions_list, error_message) — one will be None
        questions_list format: [
            {
                "question": str,
                "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
                "correct_answer": int (0-3),
                "explanation": str,
                "difficulty": "Medium" | "Hard",
                "question_type": str,
                "option_explanations": {"A": str, "B": str, "C": str, "D": str}
            }
        ]
    """
    prompt = f"""{_UPSC_SYSTEM}

SOURCE: {resource_type}
{_QUESTION_TYPES}

CONTENT TO GENERATE QUESTIONS FROM:
{summary_content[:10000]}

YOUR TASK:
Generate EXACTLY {num_questions} MCQs from the above content.
Each question must be directly grounded in specific details from the content above.

OUTPUT FORMAT — respond ONLY with a raw JSON array (no markdown, no code fences):
[
  {{
    "question": "Consider the following statements about [specific scheme from content]:\\n1. [Specific statement — may be subtly wrong]\\n2. [Specific statement — factually accurate]\\n3. [Specific statement — may contain wrong figure/year]\\nWhich of the statements given above is/are correct?",
    "options": [
      "A) 1 only",
      "B) 1 and 2 only",
      "C) 2 and 3 only",
      "D) 1, 2 and 3"
    ],
    "correct_answer": 1,
    "explanation": "Statement 1 is incorrect because [specific reason from content]. Statement 2 is correct: [cite specific provision/data from content]. Statement 3 is incorrect because [specific reason].",
    "difficulty": "Hard",
    "question_type": "Statement-Based",
    "option_explanations": {{
      "A": "Wrong — misses statement 2 which is correct.",
      "B": "Correct — only statements 2 is factually accurate based on the content.",
      "C": "Wrong — statement 3 contains [specific factual error].",
      "D": "Wrong — statements 1 and 3 are incorrect."
    }}
  }},
  {{
    "question": "Which of the following statements about [topic from content] is NOT correct?",
    "options": [
      "A) [Correct fact from content]",
      "B) [Correct fact from content]",
      "C) [INCORRECT statement — specific factual error]",
      "D) [Correct fact from content]"
    ],
    "correct_answer": 2,
    "explanation": "Option C is incorrect because [specific reason with correct data]. Options A, B, and D are all accurate as per the content.",
    "difficulty": "Medium",
    "question_type": "NOT-Correct",
    "option_explanations": {{
      "A": "Correct statement — [brief explanation].",
      "B": "Correct statement — [brief explanation].",
      "C": "INCORRECT — this is the answer because [specific factual error].",
      "D": "Correct statement — [brief explanation]."
    }}
  }}
]"""

    try:
        # Use high-quality model for better question generation
        response = ask_llm_high_quality(prompt)

        if not response or "All models failed" in response:
            # Fallback to standard
            response = ask_llm(prompt)

        if not response:
            return None, "❌ LLM did not return a response. Please try again."

        questions = _parse_and_validate(response, num_questions)

        if not questions:
            return None, "❌ Could not parse valid questions from the response. Please try again."

        return questions, None

    except json.JSONDecodeError as e:
        return None, f"❌ Error parsing quiz questions: {str(e)}"
    except Exception as e:
        return None, f"❌ Error generating quiz: {str(e)}"


def _parse_and_validate(response: str, num_questions: int) -> list | None:
    """Parse JSON response and validate each question."""
    # Clean response
    cleaned = response.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)

    # Fix bad escape sequences
    cleaned = re.sub(r'\\(?![nrtu"\\])', r'\\\\', cleaned)

    # Find JSON array
    start = cleaned.find('[')
    end = cleaned.rfind(']') + 1
    if start == -1 or end == 0:
        return None

    json_str = cleaned[start:end]

    try:
        questions = json.loads(json_str)
    except json.JSONDecodeError:
        # Try bracket balancing
        b = json_str.count('{') - json_str.count('}')
        l = json_str.count('[') - json_str.count(']')
        patched = json_str + ('}' * max(0, b)) + (']' * max(0, l))
        try:
            questions = json.loads(patched)
        except Exception:
            return None

    if not isinstance(questions, list):
        return None

    valid_questions = []
    for q in questions:
        try:
            if not all(key in q for key in ["question", "options", "correct_answer", "explanation"]):
                continue

            # Ensure options is a list of 4
            if not isinstance(q["options"], list) or len(q["options"]) < 4:
                continue

            # Validate correct_answer index
            ca = q["correct_answer"]
            if not isinstance(ca, int) or not (0 <= ca < len(q["options"])):
                # Try to recover if it's a letter
                if isinstance(ca, str) and ca.upper() in "ABCD":
                    ca = ord(ca.upper()) - ord('A')
                    q["correct_answer"] = ca
                else:
                    q["correct_answer"] = 0

            # Ensure options are strings
            q["options"] = [str(opt) for opt in q["options"]]

            # Set defaults
            q.setdefault("difficulty", "Medium")
            q.setdefault("question_type", "MCQ")
            q.setdefault("option_explanations", {"A": "", "B": "", "C": "", "D": ""})

            valid_questions.append(q)
        except Exception:
            continue

    return valid_questions if valid_questions else None


def evaluate_quiz_response(
    questions: list,
    user_answers: list
) -> tuple[dict | None, str | None]:
    """
    Evaluate user responses against correct answers.

    Args:
        questions: List of question dicts
        user_answers: List of selected answer indices (0-3)

    Returns:
        (result_dict, error_message)
    """
    if len(user_answers) != len(questions):
        return None, "Number of answers doesn't match number of questions."

    score = 0
    results = []

    for question, user_answer in zip(questions, user_answers):
        is_correct = user_answer == question["correct_answer"]
        if is_correct:
            score += 1

        results.append({
            "question": question["question"],
            "user_answer": question["options"][user_answer],
            "correct_answer": question["options"][question["correct_answer"]],
            "is_correct": is_correct,
            "explanation": question.get("explanation", ""),
            "difficulty": question.get("difficulty", "Medium"),
            "question_type": question.get("question_type", "MCQ"),
            "option_explanations": question.get("option_explanations", {}),
        })

    total = len(questions)
    percentage = int((score / total) * 100) if total > 0 else 0

    # UPSC-style scoring (Prelims: +2 for correct, -0.66 for wrong)
    wrong = total - score  # simplification: unattempted treated as wrong
    upsc_marks = round(score * 2 - wrong * 0.66, 2)

    return {
        "score": score,
        "total": total,
        "wrong": total - score,
        "percentage": percentage,
        "upsc_marks": upsc_marks,
        "results": results,
    }, None
