import os
from dotenv import load_dotenv

load_dotenv()

# def ask_llm(prompt):
#     try:
#         from groq import Groq
#
#         api_key = os.getenv("GROQ_API_KEY")
#
#         if not api_key:
#             return "❌ API Key missing. Check .env file."
#
#         client = Groq(api_key=api_key)
#
#         response = client.chat.completions.create(
#             model="llama-3.1-8b-instant",  # ✅ UPDATED MODEL
#             messages=[{"role": "user", "content": prompt}],
#             temperature=0.7
#         )
#
#         return response.choices[0].message.content
#
#     except Exception as e:
#         return f"❌ LLM Error: {str(e)}"


def ask_llm(prompt):
    from groq import Groq
    import os

    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    models = [
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768"
    ]

    for model in models:
        try:
            res = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )
            return res.choices[0].message.content
        except:
            continue

    return "❌ All models failed"