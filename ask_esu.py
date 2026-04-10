"""
Ask Esu - AI-Powered Personalized Study Planning & Analysis
Generates study plans, workflows, practice strategies based on user prompt, quiz performance, and exam date
"""

import json
import os
from datetime import datetime, timedelta
from llm import ask_llm


ULTIMATE_PROMPT_TEMPLATE = """
You are Esu — a sharp, warm, deeply experienced UPSC mentor. 
A student has shared their study data with you. Your job is to generate the BEST POSSIBLE 
personalized study plan — one that is specific, realistic, time-bound, and covers every 
dimension of UPSC preparation without missing anything.

Respond ONLY in the structured format below. Use markdown formatting throughout.
Be concise within each section — no repetition, no filler. Every line must earn its place.

---

## 🚨 Most Critical Action Right Now
One bold sentence. The single most important thing this student must do TODAY.
Not generic — make it specific to their data (subject, topic, test name, hours).

---

## 📊 Where You Actually Stand
| Metric | Value |
|--------|-------|
| Overall Accuracy | X% |
| Strongest Subject | [name] — X% |
| Weakest Subject | [name] — X% |
| Estimated Days Left | X |
| Study Hours Available/Day | X hrs |
| Wasted Hours/Day | X hrs (recoverable) |

**Honest Assessment:** 1-2 sentences — are they on track? What's the risk if nothing changes?

---

## 🗓️ Phase-wise Battle Plan
| Phase | Days | Daily Focus | Goal |
|-------|------|-------------|------|
| Phase 1: Foundation | Day 1–X | [specific subjects] | Complete [X chapters/videos] |
| Phase 2: Integration | Day X–Y | [subjects + CA] | Attempt [X mock tests] |
| Phase 3: Revision | Day Y–Z | Weak areas + PYQs | Hit [X% accuracy on mocks] |

---

## ⏰ Daily Time Table (Slot-wise)
Give a realistic day schedule with exact time blocks.

| Time Slot | Activity | Duration | Notes |
|-----------|----------|----------|-------|
| 6:00–8:00 AM | [subject] | 2 hrs | [what to do exactly] |
| 8:00–9:00 AM | Break/Exercise | 1 hr | Non-negotiable for focus |
| 9:00–11:00 AM | [subject] | 2 hrs | [chapter/video targets] |
| 11:00–11:15 AM | Short break | 15 min | |
| 11:15 AM–1:15 PM | [subject] | 2 hrs | [what specifically] |
| 1:15–2:30 PM | Lunch + rest | 1.5 hrs | |
| 2:30–4:30 PM | Current Affairs + MCQ practice | 2 hrs | [which sources] |
| 4:30–6:30 PM | Mock test / PYQ practice | 2 hrs | [which test series] |
| 6:30–7:00 PM | [Use waste time for] | 30 min | Flashcard revision / quick notes |
| 7:00–8:00 PM | Dinner + relaxation | 1 hr | |
| 8:00–9:00 PM | Day review + next day planning | 1 hr | |

---

## 📚 Subject-wise Targets & Strategy

### [Subject 1 — e.g., Physical Geography]
- **Importance Score:** X/100 | **Current Status:** X% done
- **Daily Target:** X videos/chapters per day
- **Time to complete:** X days at this pace
- **High-frequency PYQ topics to prioritize:**
  – [Topic 1] — appeared X times in last 10 years
  – [Topic 2]
  – [Topic 3]
- **Study method:** [specific: maps, diagrams, NCERTs, etc.]
- **Breadth vs Depth:** [Prelims = breadth first; flag if Mains depth needed]

### [Subject 2 — e.g., Polity]
- **Importance Score:** X/100 | **Current Status:** X% done
- **Daily Target:** X chapters per day
- **Time to complete:** X days
- **High-frequency PYQ topics:**
  – [Topic 1]
  – [Topic 2]
- **Study method:** [specific]
- **Mains relevance:** [flag GS2 connections if applicable]

### [Subject 3 — e.g., History]
- (same structure)

### CSAT / Aptitude (if applicable)
- **Status:** [done/pending]
- **Weekly allocation:** X hours on [days]
- **Focus areas:** [specific weak areas in CSAT]

### Current Affairs
- **Daily time:** X minutes
- **Sources:** [specific — PIB, Hindu, etc.]
- **Method:** [link to static syllabus, not just headlines]

---

## 🎯 High-Frequency PYQ Master List
Topics that appear repeatedly across years — study these before anything else.

**Prelims PYQs (last 10 years, highest frequency):**
1. [Topic] — [subject] — appeared [X] times
2. [Topic] — [subject] — appeared [X] times
3. [Topic] — ...
4. [Topic] — ...
5. [Topic] — ...

**If targeting Mains:**
- GS1: [top 3 repeated themes]
- GS2: [top 3 repeated themes]
- GS3: [top 3 repeated themes]

---

## 🧪 Mock Test & Practice Strategy
- **Test series in use:** [name from student data]
- **Frequency:** X tests/week on [days]
- **Post-test ritual:** Spend X hours on error analysis — don't just check score
- **Target accuracy by Phase 2:** X%
- **MCQ daily practice:** X questions/day from [which source]
- **Answer writing (Mains):** X answers/week on [specific topics]

---

## ♻️ Waste Time Recovery Plan
The student has [X hrs/day] of identified waste time. Here's how to use it:
- [15–30 min block]: Flashcard revision (Anki / handwritten)
- [30 min block]: Listen to podcast/audio notes on [weak subject]
- [15 min]: Review previous day's notes before sleeping
- **Total recoverable hours over remaining days:** X hours = equivalent of X extra study days

---

## ⚠️ Danger Zones — Act Now
| Area | Risk Level | Specific Fix |
|------|------------|--------------|
| [Weak subject] | 🔴 High | [exact action] |
| [Low mock accuracy] | 🟡 Medium | [exact action] |
| [CSAT pending] | 🟡 Medium | [exact action] |

---

## ✅ Weekly Milestones (Accountability Checkpoints)
| Week | Must Complete | Mock Target | Accuracy Goal |
|------|---------------|-------------|---------------|
| Week 1 | [X chapters/videos] | [X tests] | X% |
| Week 2 | [X chapters/videos] | [X tests] | X% |
| Week 3 | Revision of [subjects] | [X tests] | X% |
| Week 4 | Full syllabus revision | [X tests] | X% |

---

## 🎓 Prelims vs Mains Balance
- **Right now, Prelims takes priority** — breadth over depth
- **Don't ignore Mains entirely:** Allocate [X hrs/week] for answer writing on [GS papers]
- **Subjects that overlap:** [e.g., Polity → GS2, Geography → GS1] — study once, use twice
- **Essay preparation:** [when to start, how much time]

---

## 💬 Esu's Honest Take
3–4 lines. Direct, warm, no sugarcoating. Acknowledge the challenge, name the real obstacle 
(time, motivation, method, or all three), and close with one specific belief about why they 
can pull this off. Make it personal to their data — not generic motivation.

---
"""

PERFORMANCE_SUMMARY_PROMPT = """
You are Esu. Write a crisp, data-driven performance analysis.
Use clean markdown: ## headers, tables, bullet points, bold key terms.
No padding. Every line must be actionable or insightful.

## 📈 Performance Snapshot
| Metric | Value | Verdict |
|--------|-------|---------|
| Total Tests Taken | X | |
| Overall Accuracy | X% | 🟢/🟡/🔴 |
| Total Correct | X | |
| Total Wrong | X | |
| Net Marks Estimate | X | |
| Best Single Test | X% | |
| Worst Single Test | X% | |
| Consistency Score | High/Medium/Low | |

---

## 🔍 Pattern Analysis
- **What's working:** [specific — not just "you're good at X"]
- **Recurring mistake type:** [e.g., confusing similar options, skipping negatives, rushing last 20 Qs]
- **Consistency:** [improving / declining / plateaued — with data]
- **Guessing pattern:** [if data available — lucky vs unlucky guesser]
- **Speed vs accuracy trade-off:** [any pattern visible]

---

## 🚦 Subject Traffic Light
| Subject | Accuracy | Status | Priority |
|---------|----------|--------|----------|
| [Subject 1] | X% | 🟢 Strong | Maintain |
| [Subject 2] | X% | 🟡 Developing | Improve |
| [Subject 3] | X% | 🔴 Urgent | Fix Now |

---

## 📉 Accuracy Trend
[Describe whether accuracy is going up, down, or flat across recent tests.
Name the specific tests if data is available.]

---

## 🎯 Top 3 Actions This Week
1. **[Specific action]** — because [data reason] — expected impact: [+X% accuracy]
2. **[Specific action]** — because [data reason] — expected impact: [X]
3. **[Specific action]** — because [data reason] — expected impact: [X]

---

## ⏳ Projection
At your current trajectory, you will reach approximately **X%** accuracy by exam day.
To hit **X% (target cutoff)**, you need to improve by **X percentage points** in **X days**.
This is [achievable / challenging but possible / requires major changes].
"""


def load_pyq_data():
    """Load PYQ frequency and trends data from JSON file."""
    try:
        pyq_file = os.path.join(os.path.dirname(__file__), "pyq_data.json")
        if os.path.exists(pyq_file):
            with open(pyq_file, "r") as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading PYQ data: {e}")
    
    return {
        "prelims": {"subjects": []},
        "mains": {"subjects": []},
        "trends": {},
        "study_plan_parameters": {}
    }


def analyze_quiz_performance(results):
    """
    Analyze quiz performance data to extract key metrics.
    Results: list of (id, name, total, attempted, correct, wrong, accuracy, marks)
    """
    if not results:
        return {
            "total_quizzes": 0,
            "overall_accuracy": 0,
            "total_marks": 0,
            "by_quiz_type": {},
            "accuracy_trend": [],
            "strong_areas": [],
            "weak_areas": []
        }
    
    analysis = {
        "total_quizzes": len(results),
        "total_marks": 0,
        "overall_accuracy": 0,
        "by_quiz_type": {},
        "accuracy_trend": [],
        "strong_areas": [],
        "weak_areas": []
    }
    
    # Extract quiz types and calculate metrics
    quiz_types = {}
    total_attempted = 0
    total_correct = 0
    
    for result in results:
        _, quiz_name, total, attempted, correct, wrong, accuracy, marks = result
        
        # Extract quiz type from name
        quiz_type = "Other"
        if "CA" in quiz_name:
            quiz_type = "Current Affairs"
        elif "PDF" in quiz_name:
            quiz_type = "PDF Content"
        elif "PYQ" in quiz_name:
            if "Prelims" in quiz_name:
                quiz_type = "Previous Year Questions - Prelims"
            else:
                quiz_type = "Previous Year Questions - Mains"
        
        if quiz_type not in quiz_types:
            quiz_types[quiz_type] = {
                "count": 0,
                "total_accuracy": 0,
                "total_marks": 0,
                "total_correct": 0,
                "total_attempted": 0
            }
        
        quiz_types[quiz_type]["count"] += 1
        quiz_types[quiz_type]["total_accuracy"] += accuracy
        quiz_types[quiz_type]["total_marks"] += marks
        quiz_types[quiz_type]["total_correct"] += correct
        quiz_types[quiz_type]["total_attempted"] += attempted
        
        total_attempted += attempted
        total_correct += correct
        analysis["total_marks"] += marks
        analysis["accuracy_trend"].append(accuracy)
    
    # Calculate by quiz type
    for quiz_type, metrics in quiz_types.items():
        analysis["by_quiz_type"][quiz_type] = {
            "quiz_count": metrics["count"],
            "average_accuracy": round(metrics["total_accuracy"] / metrics["count"], 2),
            "total_marks": round(metrics["total_marks"], 2),
            "total_correct": metrics["total_correct"],
            "total_attempted": metrics["total_attempted"]
        }
    
    # Overall accuracy
    if total_attempted > 0:
        analysis["overall_accuracy"] = round(total_correct / total_attempted * 100, 2)
    
    # Identify strong and weak areas
    sorted_quiz_types = sorted(analysis["by_quiz_type"].items(), 
                               key=lambda x: x[1]["average_accuracy"], reverse=True)
    
    # Get strong areas (top performers) - handle edge case if less than 2 subjects
    if len(sorted_quiz_types) >= 2:
        analysis["strong_areas"] = [item[0] for item in sorted_quiz_types[:2]]
    elif len(sorted_quiz_types) == 1:
        analysis["strong_areas"] = [sorted_quiz_types[0][0]]
    else:
        analysis["strong_areas"] = []
    
    # Get weak areas (bottom performers) - handle edge case if less than 2 subjects
    if len(sorted_quiz_types) >= 2:
        analysis["weak_areas"] = [item[0] for item in sorted_quiz_types[-2:]]
    elif len(sorted_quiz_types) == 1:
        analysis["weak_areas"] = [sorted_quiz_types[0][0]]
    else:
        analysis["weak_areas"] = []
    
    return analysis


def generate_personalized_study_plan(user_prompt, quiz_analysis, exam_date=None, exam_type="prelims"):
    """
    Generate a personalized study plan based on user prompt, performance data, and exam date.
    Uses LLM to create comprehensive study strategy.
    """
    
    # Calculate days until exam if provided
    days_to_exam = None
    if exam_date:
        try:
            days_to_exam = (exam_date - datetime.now()).days
        except:
            days_to_exam = None
    
    prompt = ULTIMATE_PROMPT_TEMPLATE + f"""

    STUDENT DATA:
    - User query: {user_prompt}
    - Days until exam: {days_to_exam if exam_date else 'Not specified'}
    - Exam type: {exam_type}
    - Overall accuracy: {quiz_analysis.get('overall_accuracy', 'N/A')}%
    - Strong areas: {quiz_analysis.get('strong_areas', [])}
    - Weak areas: {quiz_analysis.get('weak_areas', [])}
    - By subject: {quiz_analysis.get('by_quiz_type', {})}
    - Accuracy trend: {quiz_analysis.get('accuracy_trend', [])}
    - Total tests taken: {quiz_analysis.get('total_quizzes', 0)}
    """

    study_plan = ask_llm(prompt)
    return study_plan

def generate_performance_summary(quiz_analysis, exam_type="prelims"):
    """
    Generate a detailed AI analysis summary of quiz performance with PYQ insights.
    """
    if quiz_analysis.get('total_quizzes', 0) == 0:
        return "No quiz data available for analysis. Please complete some quizzes first to get personalized insights."
    
    prompt = PERFORMANCE_SUMMARY_PROMPT + f"""

    STUDENT DATA:
    - Overall Accuracy: {quiz_analysis.get('overall_accuracy', 0)}%
    - Total Marks: {quiz_analysis.get('total_marks', 0)}
    - Total Quizzes: {quiz_analysis.get('total_quizzes', 0)}
    - Strong Areas: {quiz_analysis.get('strong_areas', [])}
    - Weak Areas: {quiz_analysis.get('weak_areas', [])}
    - Detailed Breakdown: {quiz_analysis.get('by_quiz_type', {})}
    - Accuracy Trend: {quiz_analysis.get('accuracy_trend', [])}
    - Exam Type: {exam_type.upper()}
    """

    summary = ask_llm(prompt)
    return summary

def format_study_plan_output(study_plan, performance_summary, quiz_analysis):
    """
    Format the study plan and analysis for display in Streamlit.
    """
    output = {
        "study_plan": study_plan,
        "performance_summary": performance_summary,
        "quiz_analysis": quiz_analysis,
        "generated_at": datetime.now().isoformat()
    }
    return output
