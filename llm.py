"""
llm.py — LLM Interface with Standard and High-Quality Modes
=============================================================
Standard mode:  fast, lower token budget (used for most queries)
High-quality:   prioritises larger models + higher token budget
                (used for UPSC quiz generation where quality > speed)
"""

import os
from dotenv import load_dotenv

load_dotenv()


def _get_api_key() -> str | None:
    try:
        import streamlit as st
        return os.getenv("GROQ_API_KEY") or st.secrets.get("GROQ_API_KEY")
    except Exception:
        return os.getenv("GROQ_API_KEY")


def ask_llm(prompt: str) -> str:
    """
    Standard LLM call with fallback chain.
    Optimised for speed; suitable for summarisation, classification, etc.

    Model order: fast → capable → fallback
    Token budget: ~1800-2200 tokens per response
    """
    from groq import Groq

    api_key = _get_api_key()
    if not api_key:
        return "❌ API Key missing. Check .env file or Streamlit secrets."

    try:
        client = Groq(api_key=api_key)
    except Exception as e:
        return f"❌ Groq API initialization failed: {str(e)}"

    # Models ordered by reliability + speed
    # Token limits increased for structured table-rich outputs
    models = [
        ("llama-3.1-8b-instant",       2500, 0.4, "fast & reliable"),
        ("llama-3.3-70b-versatile",     3500, 0.4, "detailed & comprehensive"),
        ("llama-3.2-90b-vision-preview",3000, 0.4, "advanced"),
        ("mixtral-8x7b-32768",          3000, 0.4, "balanced"),
        ("llama3-70b-8192",             3000, 0.4, "fallback"),
    ]

    last_error = None
    for model, max_tokens, temperature, desc in models:
        try:
            res = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=60,
            )
            return res.choices[0].message.content
        except Exception as e:
            last_error = str(e)
            print(f"[llm] Model {model} ({desc}) failed: {e}")
            continue

    return f"❌ All models failed. Last error: {last_error}"


def _compress_prompt(prompt: str) -> str:
    """
    Compress prompt to save input tokens for Groq free tier (12K TPM).
    Strips excessive whitespace, blank lines, and redundant formatting
    while preserving all meaningful content.
    """
    import re
    # Collapse multiple blank lines into one
    prompt = re.sub(r'\n{3,}', '\n\n', prompt)
    # Strip trailing whitespace per line
    lines = [line.rstrip() for line in prompt.split('\n')]
    # Remove lines that are only dashes/equals (decorative separators)
    lines = [l for l in lines if not re.match(r'^[─═━\-=]{5,}$', l)]
    return '\n'.join(lines)


def ask_llm_high_quality(prompt: str) -> str:
    """
    High-quality LLM call — optimized for Groq FREE TIER.

    Groq Free Tier Constraints:
      - 12,000 tokens/minute (input + output combined)
      - 30 requests/minute
      - 1,000 requests/day

    Strategy: Maximize OUTPUT quality by:
      1. Compressing input prompt (strip decorative whitespace)
      2. Setting output tokens to 6000 (enough for 800+ word detailed response)
      3. Leaving ~6000 tokens for input context
      4. Using system/user message split so the model understands priorities

    Priority order for answer quality:
      Direct Answer > Smart Work > Danger Zones > Esu's Take >
      Priority Topics > Practice Strategy > Milestones > CA Intel
    """
    from groq import Groq

    api_key = _get_api_key()
    if not api_key:
        return "❌ API Key missing. Check .env file or Streamlit secrets."

    try:
        client = Groq(api_key=api_key)
    except Exception as e:
        return f"❌ Groq API initialization failed: {str(e)}"

    # Compress input to save tokens
    compressed = _compress_prompt(prompt)

    # Groq Free Tier optimized model chain:
    # - max_tokens = OUTPUT budget (leaves rest for input)
    # - Primary: 70B model with 6000 output tokens (~800-1200 words)
    # - Fallbacks: progressively lower output but still rich
    models = [
        ("llama-3.3-70b-versatile",     6000, 0.3, "high-quality primary"),
        ("llama3-70b-8192",             5500, 0.3, "capable fallback"),
        ("mixtral-8x7b-32768",          5500, 0.3, "mixture-of-experts"),
        ("llama-3.1-8b-instant",        5000, 0.3, "fast fallback"),
    ]

    last_error = None
    for model, max_tokens, temperature, desc in models:
        try:
            res = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": compressed}],
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=90,
            )
            return res.choices[0].message.content
        except Exception as e:
            last_error = str(e)
            print(f"[llm] High-quality model {model} ({desc}) failed: {e}")
            continue

    # Fall back to standard ask_llm
    print("[llm] High-quality chain exhausted — falling back to standard ask_llm")
    return ask_llm(prompt)


def ask_llm_vision(prompt: str, image_base64: str, mime_type: str = "image/png") -> str:
    """Send an image + prompt to a vision-capable LLM for analysis."""
    from groq import Groq

    api_key = _get_api_key()
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
                    "image_url": {"url": f"data:{mime_type};base64,{image_base64}"},
                },
                {"type": "text", "text": prompt},
            ],
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
        except Exception:
            continue

    return "❌ Vision models failed. Try uploading a clearer image."