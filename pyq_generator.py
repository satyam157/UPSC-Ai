import re
import json
from llm import ask_llm


def generate_pyq_quiz(news_headlines):
    """
    Generate UPSC Previous Year Question style MCQs.
    Returns a list of dicts, each with:
      - question, options (A-D), correct_answer, year,
        explanation (overall), option_explanations (per-option)
    """
    headlines_text = "\n".join(f"- {h}" for h in news_headlines[:15])

    prompt = f"""You are a UPSC exam expert. Based on the following current affairs headlines, generate EXACTLY 10 Previous Year Questions (PYQs).

RULES:
- 6 questions should be ACTUAL past UPSC Prelims PYQs (from 2013–2025) that relate to the topics in these headlines. Mention the real year they appeared.
- 4 questions should be PYQ-STYLE predicted questions that could appear in upcoming UPSC exams based on these topics. For these, use year "Predicted".
- Each question must have exactly 4 options (A, B, C, D).
- Provide the correct answer letter.
- Provide a DETAILED explanation for EACH option — why it is correct or incorrect.

CURRENT AFFAIRS HEADLINES:
{headlines_text}

FORMAT YOUR RESPONSE AS VALID JSON — an array of objects. Use this EXACT structure:
[
  {{
    "question": "Which of the following statements is/are correct?\\n1. Statement one\\n2. Statement two",
    "options": {{
      "A": "1 only",
      "B": "2 only",
      "C": "Both 1 and 2",
      "D": "Neither 1 nor 2"
    }},
    "correct_answer": "C",
    "year": "2023",
    "explanation": "Overall explanation of the answer.",
    "option_explanations": {{
      "A": "Why A is correct/incorrect...",
      "B": "Why B is correct/incorrect...",
      "C": "Why C is correct/incorrect...",
      "D": "Why D is correct/incorrect..."
    }}
  }}
]

Return ONLY the JSON array. No markdown, no code fences, no extra text.
"""

    response = ask_llm(prompt)

    if not response:
        return []

    return parse_pyq_response(response)


def parse_pyq_response(response_text):
    """Parse the LLM JSON response into a structured list of PYQ dicts."""
    # Strip markdown code fences if present
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        # Remove opening fence (```json or ```)
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        # Remove closing fence
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)

    try:
        questions = json.loads(cleaned)
        if isinstance(questions, list):
            validated = []
            for q in questions:
                if all(k in q for k in ("question", "options", "correct_answer", "year", "explanation")):
                    # Ensure option_explanations exists
                    if "option_explanations" not in q:
                        q["option_explanations"] = {
                            "A": "", "B": "", "C": "", "D": ""
                        }
                    validated.append(q)
            return validated
        return []
    except json.JSONDecodeError:
        # Fallback: try to find JSON array in the text
        match = re.search(r'\[.*\]', cleaned, re.DOTALL)
        if match:
            try:
                questions = json.loads(match.group())
                if isinstance(questions, list):
                    validated = []
                    for q in questions:
                        if all(k in q for k in ("question", "options", "correct_answer")):
                            q.setdefault("year", "Unknown")
                            q.setdefault("explanation", "")
                            q.setdefault("option_explanations", {
                                "A": "", "B": "", "C": "", "D": ""
                            })
                            validated.append(q)
                    return validated
            except json.JSONDecodeError:
                pass
        return []
