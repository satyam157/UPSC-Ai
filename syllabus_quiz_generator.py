#!/usr/bin/env python3
"""
Quiz Generator for Syllabus Resources
Creates UPSC-style questions from syllabus summaries
"""

from llm import ask_llm
import json

def generate_syllabus_quiz(resource_type, summary_content, num_questions=5):
    """
    Generate multiple-choice quiz questions from a syllabus resource summary
    
    Args:
        resource_type: Type of resource (Yojana, Kurukshetra, etc.)
        summary_content: The summary text to generate questions from
        num_questions: Number of questions to generate (default 5)
    
    Returns:
        list of questions in format: [
            {
                "question": "Question text?",
                "options": ["A) Option 1", "B) Option 2", "C) Option 3", "D) Option 4"],
                "correct_answer": 0,  // Index of correct option (0-3)
                "explanation": "Why this is correct...",
                "difficulty": "Easy|Medium|Hard"
            },
            ...
        ]
    """
    
    prompt = f"""You are an expert UPSC exam creator. Create {num_questions} RIGOROUS, EXAM-QUALITY multiple-choice questions from this {resource_type} summary.

**SUMMARY CONTENT:**
{summary_content[:11000]}

**STRICT REQUIREMENTS:**
1. Each question must test understanding, NOT memorization
2. Include factual details (dates, numbers, policies, impacts)
3. Create plausible but incorrect distractors
4. Vary difficulty: Easy→Medium→Hard progression
5. Cover different aspects of the topic
6. Each question should have ONE clearly correct answer

**OUTPUT FORMAT:**
Respond ONLY with JSON array (no markdown, no extra text, just raw JSON):

[
  {{
    "question": "Which ministry implements the scheme?",
    "options": ["A) Ministry of Agriculture", "B) Ministry of Finance", "C) Ministry of Health", "D) Ministry of Commerce"],
    "correct_answer": 1,
    "explanation": "According to the content, the scheme is implemented by Ministry of Finance.",
    "difficulty": "Easy"
  }},
  {{
    "question": "What is the key objective?",
    "options": ["A) Land reform", "B) Financial inclusion", "C) Agricultural subsidy", "D) Healthcare"],
    "correct_answer": 1,
    "explanation": "The primary objective is financial inclusion.",
    "difficulty": "Medium"
  }}
]"""

    try:
        response = ask_llm(prompt)
        
        # Clean response - remove markdown code blocks if present
        response = response.strip()
        if response.startswith("```"):
            response = response.split("```")[1]
            if response.startswith("json"):
                response = response[4:]
        
        # Parse JSON response
        json_start = response.find('[')
        json_end = response.rfind(']') + 1
        
        if json_start == -1 or json_end == 0:
            return None, "❌ Could not generate valid questions. Please try again."
        
        json_str = response[json_start:json_end]
        questions = json.loads(json_str)
        
        # Validate and fix questions
        valid_questions = []
        for q in questions:
            try:
                # Ensure all required keys exist
                if not all(key in q for key in ["question", "options", "correct_answer", "explanation", "difficulty"]):
                    continue
                
                # Fix incorrect answer index
                if not (0 <= q["correct_answer"] < len(q["options"])):
                    q["correct_answer"] = 0
                
                # Ensure options are strings
                q["options"] = [str(opt) for opt in q["options"]]
                
                valid_questions.append(q)
            except:
                continue
        
        if not valid_questions:
            return None, "❌ Generated quiz format invalid. Please try again."
        
        return valid_questions, None
    
    except json.JSONDecodeError as e:
        return None, f"❌ Error parsing quiz questions: {str(e)}"
    except Exception as e:
        return None, f"❌ Error generating quiz: {str(e)}"


def evaluate_quiz_response(questions, user_answers):
    """
    Evaluate user's quiz responses
    
    Args:
        questions: List of question dicts
        user_answers: List of user's selected answer indices (0-3)
    
    Returns:
        {
            "score": 8,
            "total": 10,
            "percentage": 80,
            "results": [
                {
                    "question": "...",
                    "user_answer": "B) Option",
                    "correct_answer": "A) Option",
                    "is_correct": false,
                    "explanation": "..."
                }
            ]
        }
    """
    
    if len(user_answers) != len(questions):
        return None, "Number of answers doesn't match number of questions"
    
    score = 0
    results = []
    
    for i, (question, user_answer) in enumerate(zip(questions, user_answers)):
        is_correct = user_answer == question["correct_answer"]
        if is_correct:
            score += 1
        
        results.append({
            "question": question["question"],
            "user_answer": question["options"][user_answer],
            "correct_answer": question["options"][question["correct_answer"]],
            "is_correct": is_correct,
            "explanation": question["explanation"],
            "difficulty": question["difficulty"]
        })
    
    return {
        "score": score,
        "total": len(questions),
        "percentage": int((score / len(questions)) * 100),
        "results": results
    }, None
