import re

def parse_quiz(text):
    questions = []
    answers = []

    pattern = r"(Q\d+\..*?)(?:Answer:\s*([A-D]))"

    matches = re.findall(pattern, text, re.DOTALL)

    for q, a in matches:
        questions.append(q.strip())
        answers.append(a.strip())

    return questions, answers