import os
from dotenv import load_dotenv

load_dotenv()

def ask_llm(prompt):
    """
    Standard LLM call with fallback models and retry logic.
    Primary: llama-3.1-8b-instant (best compatibility with Groq)
    Falls back to larger models for complex tasks.
    """
    from groq import Groq
    import os
    try:
        import streamlit as st
        api_key = os.getenv("GROQ_API_KEY") or st.secrets.get("GROQ_API_KEY")
    except:
        api_key = os.getenv("GROQ_API_KEY")
    
    if not api_key:
        return "❌ API Key missing. Check .env file or Streamlit secrets."

    try:
        client = Groq(api_key=api_key)
    except Exception as e:
        return f"❌ Groq API initialization failed: {str(e)}"

    # Models ordered by compatibility and speed
    # Recalibrated to target ~5500 tokens total (Prompt + Completion)
    models = [
        ("llama-3.1-8b-instant", 1800, "fast & reliable"),
        ("llama-3.3-70b-versatile", 2000, "detailed & comprehensive"),
        ("llama-3.2-90b-vision-preview", 2000, "advanced"),
        ("mixtral-8x7b-32768", 2000, "balanced"),
        ("llama3-70b-8192", 2000, "fallback")
    ]

    last_error = None
    for model, max_tokens, description in models:
        try:
            res = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.5,  # Lower temperature = more stable output
                timeout=60
            )
            return res.choices[0].message.content
        except Exception as e:
            last_error = str(e)
            print(f"Model {model} ({description}) failed: {e}")
            continue

    return f"❌ All models failed. Last error: {last_error}"


def ask_llm_vision(prompt, image_base64, mime_type="image/png"):
    """Send an image + prompt to a vision-capable LLM for analysis."""
    from groq import Groq
    import os

    try:
        import streamlit as st
        api_key = os.getenv("GROQ_API_KEY") or st.secrets.get("GROQ_API_KEY")
    except:
        api_key = os.getenv("GROQ_API_KEY")
    
    if not api_key:
        return "❌ API Key missing. Check .env file."
    
    try:
        client = Groq(api_key=api_key)
    except Exception as e:
        return f"❌ Groq API initialization failed: {str(e)}"

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