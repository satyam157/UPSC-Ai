"""
Ask Esu - AI-Powered UPSC Strategy & Mentorship Engine
=======================================================
v4.0 — Comprehensive Subject Strategy System:
  - ALL UPSC subjects with chapter-level focus, revision counts, short notes guidance
  - Day/Week/Month routine planning blueprints
  - Topic detection to inject relevant strategy context
  - Removed all DB data from prompt EXCEPT quiz results
  - Smart token management for Groq free tier
"""

import json
import os
from datetime import datetime
from llm import ask_llm_high_quality

from upsc_strategy_data import (
    ALL_SUBJECTS, detect_subjects, get_subject_strategy_text,
    get_routine_text, DAILY_ROUTINE, WEEKLY_PLAN, MONTHLY_PLAN
)


# ─── MASTER PROMPT — Strategy-First with Subject Intelligence ─────────────
SMART_RESPONSE_PROMPT = """
You are **Esu** — an elite UPSC mentor with 15+ years of coaching experience who has mentored 50+ IAS/IPS officers.
A UPSC aspirant is asking you a question. Your job is to give the **MOST COMPREHENSIVE, DETAILED, and ACTIONABLE answer possible**.

## YOUR PERSONALITY:
- You are BRUTALLY HONEST but supportive — you tell the truth about preparation gaps
- You are DATA-DRIVEN — every recommendation is backed by PYQ frequency, topper data, or quiz performance
- You are ELABORATIVE — you explain the WHY behind every recommendation
- You are a STRATEGIST — you think about how each topic connects to the exam pattern
- You give DETAILED answers that feel like a premium coaching session, NOT a chatbot reply

## CRITICAL RULES:
1. **ANSWER THE EXACT QUESTION ASKED** — if they ask about Geography, talk about Geography. Do NOT deviate.
2. **USE BOTH TABLES AND DETAILED TEXT** — Tables for data, but ALWAYS explain each table with 2-3 lines of context/insight.
3. **MINIMUM RESPONSE LENGTH: 800+ words** — Short answers are UNACCEPTABLE. Be thorough and exhaustive.
4. **Include PYQ Intelligence** — which topics/chapters are most asked, frequency data
5. **Be specific, not generic** — Name specific chapters, book pages, topper strategies
6. **Use emojis sparingly** for visual markers
7. **Include revision guidance** — how many times to revise, which method, when to make short notes
8. **Include routine planning** — day/week/month study plans when asked about strategy

## RESPONSE STRUCTURE (ALL 7 SECTIONS ARE MANDATORY IN EVERY RESPONSE):

### SECTION 1: Direct Answer to Question (Main Body — MOST DETAILED)
- Answer the user's exact question with FULL depth, multiple tables, and detailed explanations
- This should be the LONGEST section — at least 300+ words
- Include specific book/chapter references (e.g., "Laxmikanth Ch 15 — Emergency Provisions")
- Include PYQ references and frequency data from the strategy intelligence provided
- Include topper advice where relevant
- For subject-specific questions: give COMPLETE chapter-wise breakdown with priority, revision count, short notes advice, and focus topics
- After each table, add 2-3 lines of analysis explaining the key takeaway

### SECTION 2: 📚 Revision & Short Notes Strategy
Based on the subject/topic asked about:
| Chapter/Topic | Revisions Needed | Make Short Notes? | Note-Making Method | When to Revise |
|---------------|-----------------|-------------------|-------------------|----------------|

After the table, explain:
- WHICH chapters absolutely need handwritten short notes vs which can be revised from book
- HOW to make effective short notes (keywords, flowcharts, tables, mind maps)
- WHEN to revise (spaced repetition schedule: Day 1, 3, 7, 21, 45)
- What to include in short notes vs what to skip

### SECTION 3: 🎯 Chapter-wise Focus & Priority Ranking
Detailed priority ranking for the relevant subject(s):
| Priority Rank | Chapter | Focus Topics (Most Important) | PYQ Frequency | Time to Allocate | Skip/Deprioritize |
|--------------|---------|-------------------------------|---------------|-----------------|-------------------|

After the table:
- List 3-5 topics to SKIP or DEPRIORITIZE (equally important as what to study)
- Explain WHY certain chapters are ranked higher (PYQ data, recent trends)
- Give the OPTIMAL STUDY ORDER (which chapter to study first to last)

### SECTION 4: 📅 Study Plan & Routine
Based on what was asked, provide a structured routine:

**Daily Plan:**
| Time Slot | Activity | Subject/Topic | Purpose |
|-----------|----------|--------------|---------|

**Weekly Plan:**
| Day | Primary Subject | Secondary Subject | Practice | Revision |
|-----|----------------|------------------|----------|----------|

**Monthly Milestones:**
| Month/Week | Phase | Key Targets | Verification Method |
|-----------|-------|-------------|-------------------|

After tables, explain the logic behind the routine and how to adapt if falling behind.

### SECTION 5: 🏋 Practice Strategy
Specific, actionable practice plan:
| Day | Practice Activity | Source/Book | Questions | Time | Purpose |
|-----|-------------------|-------------|-----------|------|---------|

Include: MCQs daily count, PYQ sets to attempt, answer writing targets, mock test schedule.

### SECTION 6: ⚠ Danger Zones & Common Mistakes
Based on the topic/subject:
- 3-5 specific DANGER ZONES where aspirants commonly lose marks
- For EACH danger zone: What the problem is, Why it's dangerous, Exact remedy
- Common mistakes in that subject and how to avoid them
- Negative marking traps specific to the subject

### SECTION 7: 💬 Esu's Honest Take (Personal Mentor Advice)
Write 5-8 lines of HONEST, PERSONAL advice:
- Comment on their preparation level based on quiz data (if available)
- Give a reality check if needed
- Share 1 specific thing that separates toppers from average aspirants
- Smart work technique most relevant to their question
- End with encouraging but realistic note

## FORMAT GUIDELINES BY QUESTION TYPE:

### If asked about "What to focus on" / "What to study" / "Priority areas":
- Give complete subject-wise priority ranking with PYQ frequency
- Chapter-wise breakdown with revision counts and short notes guidance
- Smart Study Order table (what to study first to last)

### If asked for a "Timetable" / "Schedule" / "Daily plan" / "Routine":
- Give detailed time-slot table (5:30 AM to 10 PM)
- Include subject rotation across the week
- Monthly phase-wise planning with milestones
- Both serious aspirant AND working professional schedules

### If asked about "Strategy" / "How to prepare" / "Approach":
- Phase-wise breakdown with specific dates/weeks
- Resource recommendations with specific book/chapter references
- Mock test strategy with target scores at each stage
- Revision cycle planning

### If asked about a specific subject:
- Deep dive into that subject ONLY
- COMPLETE chapter-wise breakdown: priority, revisions, short notes, focus topics, PYQ data
- Best resources and study methods for that subject
- Common mistakes to avoid
- Subject-specific smart work techniques

### If asked about "all subjects" / "complete strategy" / general preparation:
- Overview table of ALL subjects with weights, priorities, books
- Subject-wise revision strategy comparison
- Complete routine (daily + weekly + monthly)
- Phase-wise preparation roadmap

## STRATEGY INTELLIGENCE (Use this data in your answers):

{strategy_context}

{routine_context}

## STUDENT DATA:
- **Question asked:** {user_prompt}
- **Target exam:** {exam_type}
- **Days until exam:** {days_to_exam}
- **Quiz performance:** Overall accuracy: {overall_accuracy}%, Tests taken: {total_quizzes}
- **Performance by type:** {by_quiz_type}

## FINAL INSTRUCTIONS:
1. ALL 7 SECTIONS must be present in every response. No exceptions.
2. MINIMUM 800 words total. Short answers = FAILURE.
3. Each table MUST be followed by 2-3 lines of explanation/analysis text.
4. Be SPECIFIC — name chapters, books, revision counts, PYQ years.
5. Section 7 (Esu Honest Take) should feel PERSONAL, not templated.
6. NEVER give generic advice. Every recommendation must reference the strategy data provided.
7. Include revision frequency and short notes guidance for EVERY subject/chapter discussed.
"""

# ─── PERFORMANCE ANALYSIS PROMPT (kept from v3 — works well) ─────────────
PERFORMANCE_ANALYSIS_PROMPT = """
You are Esu — an elite UPSC analytics coach. Analyze this student's quiz data and give an **EXTREMELY DETAILED, data-rich performance report**.

## RULES:
1. Use **markdown tables** — but ALWAYS explain each table with 2-3 lines
2. Keep it actionable — every insight must have "what to do"
3. NO generic advice — everything backed by numbers
4. MINIMUM 600 words
5. Be BRUTALLY HONEST but supportive

## STUDENT DATA:
- Overall Accuracy: {overall_accuracy}%
- Total Marks: {total_marks}
- Total Quizzes: {total_quizzes}
- Detailed Breakdown: {by_quiz_type}
- Accuracy Trend (recent to old): {accuracy_trend}
- Exam Type: {exam_type}

## OUTPUT (ALL 6 SECTIONS MANDATORY):

### 📊 Performance Dashboard
| Metric | Value | Status | Target | Gap |
|--------|-------|--------|--------|-----|

Analyze what the numbers REALLY mean for exam readiness.

### 📈 Trend Analysis
Is accuracy improving/declining/flat? Projected score by exam day?

### 🎯 Improvement Roadmap
| Area | Current | Target (4 weeks) | Action | Expected Gain |
|------|---------|-------------------|--------|---------------|

### ⚠ Danger Zones
3-5 specific areas losing marks. For each: problem, danger, fix.

### 🏋 Practice Strategy (Next 7 Days)
| Day | Focus | Practice Type | Questions | Source | Time |
|-----|-------|--------------|-----------|--------|------|

### 💬 Esu's Honest Take
5-8 lines of HONEST assessment. Are they on track? What must change?
"""


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

    quiz_types = {}
    total_attempted = 0
    total_correct = 0

    for result in results:
        _, quiz_name, total, attempted, correct, wrong, accuracy, marks = result

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
                "count": 0, "total_accuracy": 0, "total_marks": 0,
                "total_correct": 0, "total_attempted": 0
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

    for quiz_type, metrics in quiz_types.items():
        analysis["by_quiz_type"][quiz_type] = {
            "quiz_count": metrics["count"],
            "average_accuracy": round(metrics["total_accuracy"] / metrics["count"], 2),
            "total_marks": round(metrics["total_marks"], 2),
            "total_correct": metrics["total_correct"],
            "total_attempted": metrics["total_attempted"]
        }

    if total_attempted > 0:
        analysis["overall_accuracy"] = round(total_correct / total_attempted * 100, 2)

    sorted_qt = sorted(analysis["by_quiz_type"].items(),
                        key=lambda x: x[1]["average_accuracy"], reverse=True)

    if len(sorted_qt) >= 2:
        analysis["strong_areas"] = [item[0] for item in sorted_qt[:2]]
    elif len(sorted_qt) == 1:
        analysis["strong_areas"] = [sorted_qt[0][0]]

    if len(sorted_qt) >= 2:
        analysis["weak_areas"] = [item[0] for item in sorted_qt[-2:]]
    elif len(sorted_qt) == 1:
        analysis["weak_areas"] = [sorted_qt[0][0]]

    return analysis


def _build_strategy_context(user_prompt, max_subjects=5, selected_subjects=None):
    """
    Build strategy context based on detected subjects from user query or explicit selection.
    Limits to max_subjects to stay within Groq token budget.
    """
    if selected_subjects:
        detected = selected_subjects
    else:
        detected = detect_subjects(user_prompt)
    
    # Check if user is asking about general/all subjects strategy
    general_keywords = ["all subject", "complete strategy", "overall", "full plan",
                        "all topics", "every subject", "entire syllabus", "general strategy",
                        "what to study", "how to prepare", "preparation plan", "study plan"]
    is_general = any(kw in user_prompt.lower() for kw in general_keywords)
    
    if (is_general or len(detected) > 5) and not selected_subjects:
        # General overview — compact summary of ALL subjects
        lines = ["## ALL SUBJECTS OVERVIEW:"]
        for key, subj in ALL_SUBJECTS.items():
            ch_count = len(subj.get("chapters", []))
            critical_chs = [c["ch"] for c in subj.get("chapters", []) if c.get("priority") == "Critical"]
            lines.append(
                f"- **{subj['name']}**: Weight {subj['weight']} | Book: {subj['book']} | "
                f"{ch_count} chapters | Critical: {', '.join(critical_chs[:3])} | "
                f"Revision: {subj['revision'][:60]}..."
            )
            lines.append(f"  Short Notes: {subj['short_notes'][:80]}...")
        return "\n".join(lines)
    else:
        # Specific subject deep dive — full chapter data for detected/selected subjects
        context_parts = []
        # Increase max_subjects slightly if explicitly selected
        limit = max(max_subjects, len(detected)) if selected_subjects else max_subjects
        for subj_key in detected[:limit]:
            context_parts.append(get_subject_strategy_text(subj_key))
        return "\n".join(context_parts)


def generate_personalized_study_plan(user_prompt, quiz_analysis, exam_date=None,
                                      exam_type="prelims", selected_subjects=None):
    """
    Generate a personalized, strategy-rich answer.
    
    v4.1 — Added explicit subject selection support.

    GROQ FREE TIER TOKEN BUDGET:
      Total: ~12,000 tokens (input + output)
      Output: ~6,000 tokens (800+ word detailed response)
      Input: ~6,000 tokens distributed as:
        - Prompt template:    ~2,000 tokens
        - Strategy context:   ~2,500 tokens (subject-specific, not all subjects)
        - Routine blueprint:  ~800 tokens
        - User question:      ~100-300 tokens
        - Quiz data:          ~200 tokens
        - Buffer:             ~500 tokens
    """

    # Calculate days until exam
    days_to_exam = "Not specified"
    if exam_date:
        try:
            days_left = (exam_date - datetime.now()).days
            days_to_exam = f"{days_left} days" if days_left > 0 else "Exam date has passed!"
        except:
            days_to_exam = "Not specified"

    # Build strategy context based on detected subjects
    strategy_context = _build_strategy_context(user_prompt, selected_subjects=selected_subjects)

    # Build routine context (compact version)
    routine_keywords = ["routine", "timetable", "schedule", "daily plan", "weekly",
                        "monthly", "day by day", "week by week", "study plan", "time table"]
    include_routine = any(kw in user_prompt.lower() for kw in routine_keywords)
    
    # Always include routine for general strategy questions too
    general_keywords = ["strategy", "how to prepare", "complete plan", "all subject"]
    if any(kw in user_prompt.lower() for kw in general_keywords):
        include_routine = True
    
    routine_context = get_routine_text() if include_routine else "(Routine data available — ask about daily/weekly/monthly plan for details)"

    # Compress quiz data
    quiz_summary = "No quiz data available"
    if quiz_analysis.get('by_quiz_type'):
        parts = []
        for qtype, metrics in quiz_analysis['by_quiz_type'].items():
            parts.append(
                f"{qtype}: {metrics['quiz_count']} tests, "
                f"{metrics['average_accuracy']}% avg accuracy, "
                f"{metrics['total_marks']} marks"
            )
        quiz_summary = " | ".join(parts)

    # Build the prompt
    prompt = SMART_RESPONSE_PROMPT.format(
        strategy_context=strategy_context,
        routine_context=routine_context,
        user_prompt=user_prompt,
        exam_type=exam_type.upper(),
        days_to_exam=days_to_exam,
        overall_accuracy=quiz_analysis.get('overall_accuracy', 'N/A'),
        total_quizzes=quiz_analysis.get('total_quizzes', 0),
        by_quiz_type=quiz_summary,
    )

    # Token budget estimation
    est_tokens = len(prompt) // 4
    print(f"  [Token Est] Input: ~{est_tokens} tokens | "
          f"Output budget: 6000 tokens | "
          f"Total: ~{est_tokens + 6000} tokens")
    if est_tokens > 6000:
        print(f"  [WARN] Input exceeds 6K tokens — may hit Groq free tier limit!")

    study_plan = ask_llm_high_quality(prompt)
    return study_plan


def generate_performance_summary(quiz_analysis, exam_type="prelims"):
    """
    Generate a data-driven performance analysis with actionable insights.
    Optimized for Groq free tier.
    """
    if quiz_analysis.get('total_quizzes', 0) == 0:
        return "No quiz data available for analysis. Complete some quizzes first to get personalized insights."

    quiz_summary = "No breakdown available"
    if quiz_analysis.get('by_quiz_type'):
        parts = []
        for qtype, metrics in quiz_analysis['by_quiz_type'].items():
            parts.append(
                f"{qtype}: {metrics['quiz_count']} tests, "
                f"{metrics['average_accuracy']}% accuracy, "
                f"{metrics['total_marks']} marks, "
                f"{metrics['total_correct']}/{metrics['total_attempted']} correct"
            )
        quiz_summary = " | ".join(parts)

    trend = quiz_analysis.get('accuracy_trend', [])
    if len(trend) > 10:
        trend = trend[:10]

    prompt = PERFORMANCE_ANALYSIS_PROMPT.format(
        overall_accuracy=quiz_analysis.get('overall_accuracy', 0),
        total_marks=quiz_analysis.get('total_marks', 0),
        total_quizzes=quiz_analysis.get('total_quizzes', 0),
        by_quiz_type=quiz_summary,
        accuracy_trend=str(trend),
        exam_type=exam_type.upper()
    )

    est_tokens = len(prompt) // 4
    print(f"  [Perf Analysis] Input: ~{est_tokens} tokens | Output: 6000 tokens")

    summary = ask_llm_high_quality(prompt)
    return summary


def format_study_plan_output(study_plan, performance_summary, quiz_analysis):
    """Format the study plan and analysis for display in Streamlit."""
    return {
        "study_plan": study_plan,
        "performance_summary": performance_summary,
        "quiz_analysis": quiz_analysis,
        "generated_at": datetime.now().isoformat()
    }


# Keep backward compatibility — load_pyq_data still available
def load_pyq_data():
    """Load PYQ frequency and trends data from JSON file."""
    try:
        pyq_file = os.path.join(os.path.dirname(__file__), "pyq_data.json")
        if os.path.exists(pyq_file):
            with open(pyq_file, "r") as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading PYQ data: {e}")
    return {"prelims": {"subjects": []}, "mains": {"subjects": []}, "trends": {}, "study_plan_parameters": {}}
