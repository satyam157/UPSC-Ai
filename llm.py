import os
from dotenv import load_dotenv

load_dotenv()

def ask_llm(prompt):
    """
    Standard LLM call with fallback models and retry logic.
    Primary: llama-3.3-70b (best for complex JSON)
    Falls back to 70b-8192, then Mixtral, then 8b-instant.
    """
    from groq import Groq
    import os

    import streamlit as st
    api_key = os.getenv("GROQ_API_KEY") or st.secrets.get("GROQ_API_KEY")
    if not api_key:
        return "❌ API Key missing. Check .env file or Streamlit secrets."

    client = Groq(api_key=api_key)

    models = [
        "llama-3.3-70b-versatile",
        "llama3-70b-8192",
        "mixtral-8x7b-32768",
        "llama-3.1-8b-instant"
    ]

    for model in models:
        try:
            res = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=8000 if "70b" in model else 4000,
                temperature=0.5, # Lower temperature = more stable JSON
            )
            return res.choices[0].message.content
        except Exception as e:
            print(f"Model {model} failed: {e}")
            continue

    return "❌ All models failed"


def ask_llm_vision(prompt, image_base64, mime_type="image/png"):
    """Send an image + prompt to a vision-capable LLM for analysis."""
    from groq import Groq
    import os

    import streamlit as st
    api_key = os.getenv("GROQ_API_KEY") or st.secrets.get("GROQ_API_KEY")
    client = Groq(api_key=api_key)

    vision_models = [
        "llama-3.2-90b-vision-preview",
        "llama-3.2-11b-vision-preview",
    ]

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{image_base64}"
                    }
                },
                {
                    "type": "text",
                    "text": prompt
                }
            ]
        }
    ]

    for model in vision_models:
        try:
            res = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=4096,
            )
            return res.choices[0].message.content
        except:
            continue

    return "❌ Vision models failed. Try uploading a clearer image."