import os
from dotenv import load_dotenv
from groq import Groq

# Load variables from .env file
load_dotenv()

# Initialize the client once.
# Groq() automatically looks for "GROQ_API_KEY" in your env by default.
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


def ask_llm(prompt):
    try:
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"An error occurred: {e}"

# Example usage:
# print(ask_llm("Explain quantum physics in one sentence."))
