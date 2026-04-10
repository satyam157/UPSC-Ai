"""
quiz_engine.py — UPSC-Authentic Quiz Scoring Engine
====================================================
Implements the UPSC Prelims marking scheme:
  +2 marks per correct answer
  -0.66 marks (−2/3) per wrong answer
  0 marks for unattempted (None) answers

Handles None-safe evaluation for unattempted questions.
"""


def evaluate(user_answers: list, correct_answers: list) -> tuple:
    """
    Evaluate a quiz attempt using UPSC Prelims marking scheme.

    Args:
        user_answers:   List of answer letters (A/B/C/D) or None for unattempted
        correct_answers: List of correct answer letters (A/B/C/D)

    Returns:
        (total, attempted, correct_n, wrong, accuracy_pct, upsc_marks)
        where:
          total       = number of questions
          attempted   = number where user gave an answer
          correct_n   = number of correct answers
          wrong       = attempted - correct_n (wrong answers only, not unattempted)
          accuracy_pct= correct_n / attempted * 100 (0 if not attempted)
          upsc_marks  = correct_n * 2 - wrong * 0.66 (UPSC standard)
    """
    total = len(correct_answers)
    attempted = sum(1 for u in user_answers if u is not None and u != "")
    correct_n = sum(
        1 for u, c in zip(user_answers, correct_answers)
        if u is not None and u != "" and u == c
    )
    wrong = attempted - correct_n
    accuracy = round(correct_n / attempted * 100, 2) if attempted else 0.0
    upsc_marks = round(correct_n * 2 - wrong * 0.66, 2)

    return total, attempted, correct_n, wrong, accuracy, upsc_marks

# Proxy for syllabus_quiz_generator function
def evaluate_quiz_response(*args, **kwargs):
    from syllabus_quiz_generator import evaluate_quiz_response as eva
    return eva(*args, **kwargs)