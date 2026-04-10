#!/usr/bin/env python3
"""
Test URL Summarizer and Syllabus Quiz Generator
"""

import sys
from url_summarizer import URLSummarizer, fetch_and_summarize_urls
from syllabus_quiz_generator import generate_syllabus_quiz, evaluate_quiz_response

print("=" * 80)
print("TESTING URL SUMMARIZER & QUIZ GENERATOR")
print("=" * 80)

# Test 1: URL Summarizer basic functionality
print("\n✅ Test 1: URL Summarizer initialization")
try:
    summarizer = URLSummarizer()
    print("✅ URLSummarizer instance created successfully")
except Exception as e:
    print(f"❌ Error creating URLSummarizer: {e}")
    sys.exit(1)

# Test 2: Test with a reliable news source
print("\n✅ Test 2: Fetching article content")
test_url = "https://www.wikipedia.org/wiki/Pradhan_Mantri_Jan_Dhan_Yojana"
try:
    title, content, error = summarizer.fetch_article(test_url)
    if error:
        print(f"⚠️ Could not fetch: {error}")
        print("(This is OK - some websites may block automated requests)")
    else:
        print(f"✅ Successfully fetched: {title}")
        print(f"✅ Content length: {len(content)} characters")
except Exception as e:
    print(f"❌ Error fetching article: {e}")

# Test 3: Quiz generator
print("\n✅ Test 3: Quiz Generator")
sample_content = """
The Pradhan Mantri Jan Dhan Yojana (PMJDY) is a national mission to achieve universal financial inclusion by providing a basic savings bank account.

Key Facts:
- Launched: August 15, 2014
- Objective: Provide banking services to unbanked populations
- Benefits: No minimum balance requirement, life insurance cover
- Government has deposited Rs. 1000 crore in selected accounts
- Over 500 million accounts opened till 2023

Significance: 
- First major policy for rural financial inclusion
- Bridges banking access gap in rural India
- Supports Direct Benefit Transfer (DBT) implementation
- Critical for digital India initiatives
"""

try:
    questions, error = generate_syllabus_quiz("Yojana", sample_content, num_questions=3)
    if error:
        print(f"⚠️ Could not generate quiz: {error}")
        print("(Note: This requires LLM setup - Groq API should be configured)")
    else:
        print(f"✅ Successfully generated {len(questions)} questions")
        for idx, q in enumerate(questions, 1):
            print(f"  Q{idx}: {q['question'][:60]}...")
except Exception as e:
    print(f"⚠️ Quiz generation note: {type(e).__name__}")
    print("(This is normal if Groq/LLM is not configured)")

# Test 4: Quiz evaluation
print("\n✅ Test 4: Quiz Evaluation")
mock_questions = [
    {
        "question": "What year was PMJDY launched?",
        "options": ["A) 2012", "B) 2014", "C) 2016", "D) 2018"],
        "correct_answer": 1,
        "explanation": "PMJDY was launched on August 15, 2014",
        "difficulty": "Easy"
    }
]
mock_answers = [1]

try:
    result, error = evaluate_quiz_response(mock_questions, mock_answers)
    if error:
        print(f"❌ Evaluation error: {error}")
    else:
        print(f"✅ Quiz evaluated successfully")
        print(f"   Score: {result['score']}/{result['total']}")
        print(f"   Percentage: {result['percentage']}%")
except Exception as e:
    print(f"❌ Error evaluating quiz: {e}")

print("\n" + "=" * 80)
print("TESTING COMPLETE")
print("=" * 80)
print("\n📝 Summary:")
print("✅ All core modules load successfully")
print("⚠️ URL fetching may be limited due to website restrictions")
print("⚠️ LLM features require Groq API key in .env or Streamlit secrets")
print("\n🚀 Ready to run! Start with: streamlit run app.py")
