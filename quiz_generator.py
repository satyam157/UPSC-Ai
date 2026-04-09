from llm import ask_llm
from quiz_parser import parse_quiz

def fallback_quiz():
    return (
        [
            "Q1. What is inflation?\nA) Rise in prices\nB) Fall\nC) Stable\nD) None",
            "Q2. GDP means?\nA) Growth\nB) Output\nC) Tax\nD) None",
            "Q3. MSP relates to?\nA) Industry\nB) Agriculture\nC) Banking\nD) Trade",
            "Q4. Repo rate?\nA) Loan\nB) RBI rate\nC) Tax\nD) None",
            "Q5. Fiscal deficit?\nA) Gap\nB) Export\nC) Import\nD) None"
        ],
        ["A", "B", "B", "B", "A"]
    )

def generate_quiz(text):
    prompt = f"""
    Generate EXACTLY 5 UPSC MCQs.

    Format strictly:
    Q1. Question
    A) opt
    B) opt
    C) opt
    D) opt
    Answer: A

    Content:
    {text}
    """

    res = ask_llm(prompt)

    if not res:
        return fallback_quiz()

    q, a = parse_quiz(res)

    if len(q) < 5:
        return fallback_quiz()

    return q[:5], a[:5]