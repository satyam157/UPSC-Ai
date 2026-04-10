import re
import json
from llm import ask_llm

def _parse_json_response(response_text):
    """Helper function to safely parse JSON from LLM response."""
    if not response_text or "All models failed" in response_text:
        return None
    
    text = response_text.strip()
    
    # Check for markdown code blocks
    if "```" in text:
        matches = re.findall(r"```(?:json)?(.*?)```", text, re.DOTALL)
        if matches:
            text = matches[0].strip()
    
    # Find outer curly braces or brackets
    start = text.find("{")
    if start == -1:
        start = text.find("[")
    end = text.rfind("}")
    if end == -1:
        end = text.rfind("]")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    
    # CRITICAL: Clean up invalid backslashes that cause JSON Parse Error
    # Replace single backslashes (not followed by n, r, t, u, ", \) with double backslashes
    text = re.sub(r'\\(?![nrtu"\\])', r'\\\\', text)
    
    try:
        data = json.loads(text)
        return data
    except json.JSONDecodeError as e:
        print(f"JSON Parse Error: {e}")
        # Try to fix common truncation
        if "{" in text or "[" in text:
            try:
                balance = text.count('{') - text.count('}')
                if balance > 0:
                    text += '}' * balance
                balance_list = text.count('[') - text.count(']')
                if balance_list > 0:
                    text += ']' * balance_list
                data = json.loads(text)
                return data
            except:
                pass
        return None

def generate_prelims_pyqs_batch(news_headlines):
    """Generate 7 unique Prelims MCQs with focus on current affairs."""
    headlines_text = "\n".join(f"- {h}" for h in news_headlines[:20])

    prompt = f"""You are a senior UPSC Prelims Expert with deep knowledge of previous year questions. Based on these current affairs headlines, generate EXACTLY 7 Prelims MCQs.

HEADLINES:
{headlines_text}

REQUIREMENTS:
- Generate EXACTLY 7 questions
- 4 should be ACTUAL past UPSC Prelims PYQs (from 2015-2024) related to these topics - mention the REAL year ONLY if actual past question
- 3 should be PYQ-STYLE predicted questions for 2025-2026 - mark year as "Predicted" (NOT past years)
- CRITICAL: Do not use fake years like "2019" for predicted questions. Use ONLY real past years for real PYQs or "Predicted" for new questions
- Each question must have exactly 4 options (A, B, C, D)
- Focus on factual accuracy and current affairs relevance
- Include diverse GS topics (History, Geography, Polity, Science, Economics)
- Provide detailed explanations for EACH option

Return as valid JSON array (not wrapped in object):
[
  {{
    "question": "Which of the following statements is/are correct?\\n1. Statement\\n2. Statement",
    "options": {{"A": "1 only", "B": "2 only", "C": "Both 1 and 2", "D": "Neither 1 nor 2"}},
    "correct_answer": "C",
    "year": "2023",
    "explanation": "Overall explanation",
    "option_explanations": {{"A": "Why A...", "B": "Why B...", "C": "Why C...", "D": "Why D..."}}
  }}
]

IMPORTANT RULES:
- Use double quotes everywhere
- No backslashes except \\n for newlines
- Ensure balanced brackets and braces
- Return ONLY the JSON array, nothing else"""

    response = ask_llm(prompt)
    data = _parse_json_response(response)
    
    if not data:
        return []
    
    questions = data if isinstance(data, list) else [data]
    
    validated = []
    for item in questions:
        if isinstance(item, dict) and "question" in item:
            item.setdefault("options", {"A":"", "B":"", "C":"", "D":""})
            item.setdefault("correct_answer", "A")
            year = item.get("year", "Predicted")
            # Only keep year if it's "Predicted" or a real past year (2015-2024)
            if year.strip():
                try:
                    year_int = int(year.strip())
                    if year_int < 2015 or year_int > 2024:
                        year = "Predicted"  # Invalid year, mark as predicted
                except:
                    if year.lower() != "predicted":
                        year = "Predicted"  # Invalid format, mark as predicted
            item["year"] = year
            item.setdefault("explanation", "Reference explanation")
            item.setdefault("option_explanations", {"A": "", "B": "", "C": "", "D": ""})
            validated.append(item)
    
    return validated

def generate_mains_pyqs_batch(news_headlines):
    """Generate 7 unique Mains questions with model answers."""
    headlines_text = "\n".join(f"- {h}" for h in news_headlines[:20])

    prompt = f"""You are a senior UPSC Mains Expert. Based on these current affairs headlines, generate EXACTLY 7 Mains questions with detailed model answers.

HEADLINES:
{headlines_text}

REQUIREMENTS:
- Generate EXACTLY 7 questions
- 3 should be ACTUAL past UPSC Mains questions (2018-2024) - mention the REAL year and paper ONLY if actual past question
- 4 should be predicted questions for 2025-2026 - mark year as "Predicted" (NOT past years)
- CRITICAL: Do not use fake years. Use ONLY real past years (2018-2024) for real PYQs or "Predicted" for new questions
- Questions should cover different GS Papers (II, III, IV generally best for CA)
- Each model answer: 150-200 words with Introduction, Key Points, Conclusion
- Focus on structure and analysis, not just factual listing
- Include relevant schemes, policies, constitutional provisions where applicable

Return as valid JSON array:
[
  {{
    "question": "Discuss the implications of [topic] on [aspect]. What steps should government take?",
    "year": "2022",
    "paper": "GS Paper III",
    "model_answer": "**Introduction:** [1-2 sentences setup]\\n\\n**Key Points:**\\n1. [First aspect with explanation]\\n2. [Second aspect]\\n3. [Third aspect]\\n\\n**Conclusion:** [1-2 sentences]"
  }}
]

IMPORTANT:
- Use double quotes everywhere
- No backslashes except \\n for newlines  
- Balanced brackets and braces
- Return ONLY the JSON array, nothing else"""

    response = ask_llm(prompt)
    data = _parse_json_response(response)
    
    if not data:
        return []
    
    questions = data if isinstance(data, list) else [data]
    
    validated = []
    for item in questions:
        if isinstance(item, dict) and "question" in item:
            # Parse model answer to extract key points if not already formatted
            ma = item.get("model_answer", "Model answer pending...")
            if isinstance(ma, str) and ma:
                # Ensure it has proper structure
                if "**Introduction:**" not in ma:
                    ma = f"**Introduction:** {ma}\n\n**Key Points:**\n- [Points from model answer]\n\n**Conclusion:** See explanation above."
            item["model_answer"] = ma
            year = item.get("year", "Predicted")
            # Only keep year if it's "Predicted" or a real past year (2018-2024)
            if year.strip():
                try:
                    year_int = int(year.strip())
                    if year_int < 2018 or year_int > 2024:
                        year = "Predicted"  # Invalid year range, mark as predicted
                except:
                    if year.lower() != "predicted":
                        year = "Predicted"  # Invalid format, mark as predicted
            item["year"] = year
            item.setdefault("paper", "General Studies")
            validated.append(item)
    
    return validated

def generate_full_pyq_session(news_headlines):
    """
    Generates both Prelims and Mains questions in SEPARATE calls for uniqueness.
    Each set has 7 questions: 4 Real PYQs + 3 Predicted for Prelims,
                            3 Real PYQs + 4 Predicted for Mains.
    """
    if not news_headlines:
        return {"prelims": [], "mains": []}
    
    print("🔄 Generating 7 Prelims questions...")
    prelims = generate_prelims_pyqs_batch(news_headlines)
    
    print("🔄 Generating 7 Mains questions...")
    mains = generate_mains_pyqs_batch(news_headlines)
    
    return {"prelims": prelims, "mains": mains}

def generate_prelims_pyqs(news_headlines):
    return generate_full_pyq_session(news_headlines)["prelims"]

def generate_mains_pyqs(news_headlines):
    return generate_full_pyq_session(news_headlines)["mains"]

def predict(news):
    text = "\n".join(news)
    return ask_llm("Based on current affairs, predict UPSC questions:\n" + text)
