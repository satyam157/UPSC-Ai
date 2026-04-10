# Ask Esu - Quick Start Guide

## 🎯 Navigation

```
UPSC AI System
│
├── Sidebar Menu
│   ├── Current Affairs
│   ├── CA Quiz
│   ├── Practice
│   ├── PDF Quiz
│   ├── Results
│   ├── 🎯 Ask Esu          ← NEW FEATURE
│   ├── AI Analysis
│   └── Test Paper Analysis
│
└── 👤 Username | Logout
```

## 📱 Ask Esu Interface Layout

```
┌─────────────────────────────────────────────────────┐
│ 🤖 Ask Esu - Your Personal Study Plan & AI Guide   │
│ Provide a prompt and your exam date...              │
├─────────────────────────────────────────────────────┤
│                                                      │
│ 📝 Your Query/Prompt           📅 Exam Date        │
│ ┌──────────────────────────┐   ┌─────────────────┐ │
│ │ Describe your study      │   │ Pick Date       │ │
│ │ goals or challenges...   │   │ [✅ X days]     │ │
│ │                          │   │                 │ │
│ │                          │   └─────────────────┘ │
│ └──────────────────────────┘                        │
│                                                      │
│  [🚀 Generate Personalized Study Plan]             │
│                                                      │
├─────────────────────────────────────────────────────┤
│  Generated Output (4 Tabs):                        │
│  📚 | 📊 | 📈 | 📄                                 │
│                                                      │
│  Content + [Download JSON] [Download Text]         │
│  [🔄 Generate New Study Plan]                      │
└─────────────────────────────────────────────────────┘
```

## 📊 Performance Analysis Flow

```
Quiz Database
    ↓
Fetch Results (CA, PDF, PYQ)
    ↓
Analyze Performance
├── Total quizzes
├── Overall accuracy
├── By subject:
│   ├── CA Performance
│   ├── PDF Performance
│   ├── PYQ Prelims
│   └── PYQ Mains
├── Strong areas (top 2)
└── Weak areas (bottom 2)
    ↓
User Prompt + Analysis Data
    ↓
AI (LLM) Processing
├── Study Plan Generation
├── Performance Summary
└── Metrics Analysis
    ↓
Display Results
├── Study Plan Tab
├── Performance Summary Tab
├── Metrics Tab
└── Full Report Tab
```

## 🎓 Content Generation Process

### User Input
```json
{
  "prompt": "I'm weak in CA and want to improve before exam",
  "exam_date": "2026-07-15",
  "quiz_data": {
    "total_quizzes": 25,
    "overall_accuracy": 62.5,
    "by_subject": {
      "Current Affairs": {
        "accuracy": 52,
        "marks": 180
      },
      "PYQ Prelims": {
        "accuracy": 68,
        "marks": 290
      }
    }
  }
}
```

### AI Context Building
```
Prompt to LLM includes:
- User's specific goal
- Quiz performance data
- Subject-wise metrics
- Days until exam
- Strong/weak areas
```

### AI Output Generated
```
1. Executive Summary (2-3 lines)
2. Personalized Study Plan (3-4 weeks breakdown)
3. Daily Workflow recommendations
4. Practice strategy (quiz frequency)
5. Tackling techniques
6. Subject analysis
7. Revision plan
8. Metrics to track
```

## 📈 Metrics Dashboard - What You'll See

```
Overall Metrics Row:
┌──────────────┬──────────────┬──────────────┬──────────────┐
│  Total Tests │   Accuracy   │ Total Marks  │ Avg Accuracy │
│      25      │     62.5%    │   2,450     │     62.5%    │
└──────────────┴──────────────┴──────────────┴──────────────┘

Subject-wise Table:
┌─────────────────┬────────┬─────────────┬──────────────┬─────────┐
│ Subject         │ Tests  │ Avg Accuracy│ Total Marks  │ C/A    │
├─────────────────┼────────┼─────────────┼──────────────┼─────────┤
│ PYQ Prelims     │   10   │    68%      │    640      │ 68/100 │
│ Current Affairs │   12   │    52%      │    560      │ 62/120 │
│ PDF Content     │    3   │    71%      │    250      │ 21/30  │
│ PYQ Mains       │   none │    N/A      │    N/A      │ N/A    │
└─────────────────┴────────┴─────────────┴──────────────┴─────────┘

Strengths & Weaknesses:
💪 Strengths              🎯 Areas to Improve
✅ PDF Content (71%)      ⚠️ Current Affairs (52%)
✅ PYQ Prelims (68%)      ⚠️ Generic (Low attempts)
```

## 📝 Study Plan Output Examples

### Study Plan Section
```
📚 STUDY PLAN & WORKFLOW
═══════════════════════

Executive Summary
─────────────────
Your CA performance (52% avg) indicates you need focused
improvement. With 90 days remaining, here's your roadmap.

Personalized Study Plan
───────────────────────
Week 1-2: Foundation Building
- Daily: 2 hours CA news reading
- Focus: Politics, International Relations
- Daily CA quiz (5-10 questions)
- Target accuracy: 60%

Week 3-4: Deepening Understanding
- Daily: 2.5 hours (news + previous topics)
- Focus: Economics, Environment
- Daily quiz (10-15 questions)
- Target accuracy: 65%

[... continues for 12 weeks ...]

Daily Workflow
──────────────
6:00 AM - Wake up & Morning Routine (30 min)
6:30 AM - Review previous day notes (15 min)
6:45 AM - Read current affairs (45 min)
7:30 AM - Solve CA quiz (30 min)
...

Practice Strategy
─────────────────
- Daily: 1 CA Quiz (mandatory)
- Weekly: 1 test paper
- Monthly: 1 revision session
...
```

### Performance Summary Section
```
📊 PERFORMANCE ANALYSIS
════════════════════════

Overall Assessment
──────────────────
Current Level: Above Average Foundation
Your 62.5% overall accuracy indicates solid understanding
but weak retention in Current Affairs specifics.

Subject-wise Analysis
─────────────────────
Current Affairs (52% - WEAK):
- Causes: Insufficient reading of sources
- Gap: Updates vs long-term concepts
- Recommendation: Daily 1-hour reading + weekly recap

PYQ Prelims (68% - GOOD):
- Strength: Conceptual clarity
- Opportunity: Combine with CA knowledge
- Recommendation: Focus on questions linking to current events

Key Recommendations
───────────────────
1. Increase CA news reading time
2. Combine PYQ Prelims with current affairs
3. Weekly performance review
4. Mock tests every 2 weeks
```

## 🔄 Export Options

### Download as JSON
```json
{
  "study_plan": "Full text of study plan...",
  "performance_summary": "Full AI analysis...",
  "quiz_analysis": {
    "total_quizzes": 25,
    "overall_accuracy": 62.5,
    "by_quiz_type": {
      "Current Affairs": {
        "quiz_count": 12,
        "average_accuracy": 52
        // ... more data
      }
    },
    "strong_areas": ["PYQ Prelims"],
    "weak_areas": ["Current Affairs"]
  },
  "generated_at": "2026-04-11T10:30:00"
}
```

### Download as Text
```
PERSONALIZED STUDY PLAN
Generated on 2026-04-11 10:30

USER PROMPT: I'm weak in CA and want to improve

STUDY PLAN & WORKFLOW
═══════════════════════
[Full study plan text...]

PERFORMANCE ANALYSIS
════════════════════
[Full performance summary...]

METRICS
═══════
Total Quizzes: 25
...
```

## 💾 Use Cases for Exports

| Format | Use Case |
|--------|----------|
| **JSON** | Data analysis, integration with tools, archival |
| **Text** | Printing, sharing via email, offline reading |
| **Both** | Long-term tracking, progress comparison |

## 🔄 Workflow: Using Ask Esu

```
START
  │
  ├─ 1. Open Ask Esu from sidebar
  │     │
  ├─ 2. Enter your study challenge
  │     │
  ├─ 3. (Optional) Select exam date
  │     │
  ├─ 4. Click "Generate Study Plan"
  │     │
  ├─ 5. AI analyzes your quiz data
  │     │
  ├─ 6. Review results in 4 tabs:
  │     ├─ 📚 Study Plan
  │     ├─ 📊 Performance Summary
  │     ├─ 📈 Metrics
  │     └─ 📄 Full Report
  │
  ├─ 7. Download or take action
  │     │
  ├─ 8. (Optional) Generate another plan
  │     │
  └─ END
```

## 🎯 Example Prompts

### For Weak Areas
```
"I'm consistently getting 40-45% in Current Affairs.
I have 3 months for prelims. Create a plan to reach 75%."
```

### For Focused Improvement
```
"My conceptual knowledge is good but I can't structure
Mains answers properly. Help me with answer writing
skills and time management."
```

### For Comprehensive Planning
```
"I'm taking UPSC in 6 months. I want a complete study
roadmap covering Prelims, Mains, and revision strategy.
Which subject should I focus on first?"
```

### For Time Management
```
"I can only study 2 hours daily with office work.
Create an efficient plan that maximizes my preparation
for exam in 4 months."
```

## ⏱️ Time Estimates

- **First Plan Generation**: 1-2 minutes (AI processing)
- **Reviewing Plan**: 10-15 minutes
- **Implementing Plan**: Varies by your schedule
- **Next Plan Update**: Every 2-4 weeks

## 📞 Tips for Best Results

1. **Specific Prompts**
   - ❌ "Help me study"
   - ✅ "I score 55% in CA, need 75% in 2 months"

2. **Set Realistic Dates**
   - ❌ "Exam tomorrow"
   - ✅ "Exam on July 15, 2026"

3. **Have Quiz Data**
   - ❌ Zero quizzes taken
   - ✅ 5+ quizzes from different categories

4. **Check Metrics Tab**
   - See your actual performance data
   - Understand your starting point
   - Track which areas need work

5. **Regular Updates**
   - Generate new plans every 3-4 weeks
   - Update based on progress
   - Adjust strategies as needed

## ✅ You're All Set!

Everything is ready to use. Simply navigate to the "Ask Esu" option in your UPSC AI System sidebar and start generating your personalized study plans!

---

**Quick Access:**
1. Open UPSC AI System
2. Click "Ask Esu" in sidebar
3. Describe your study challenge
4. Get AI-powered personalized plan!

Happy Studying! 📚
