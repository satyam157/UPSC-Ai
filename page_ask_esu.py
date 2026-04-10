import streamlit as st
from datetime import datetime
from ui_components import safe_rerun
from ask_esu import (
    generate_personalized_study_plan, analyze_quiz_performance, 
    generate_performance_summary, format_study_plan_output
)
from db import get_results, save_ai_report, get_ai_reports, delete_ai_report

def show_ask_esu_page():
    st.markdown("## 🧠 Ask Esu — Your AI Mentor")
    
    # --- New Query Type Selection ---
    st.markdown("### 🎯 Choose Your Strategy Focus")
    query_type = st.selectbox("What do you need?", ["General Query / Strategy", "Subject-Wise Deep Dive"], index=0)
    
    selected_subject_keys = None
    if query_type == "Subject-Wise Deep Dive":
        from upsc_strategy_data import ALL_SUBJECTS
        subject_options = {subj['name']: key for key, subj in ALL_SUBJECTS.items()}
        selected_names = st.pills("Select one or more subjects (Recommended: 1-5):", 
                                  options=list(subject_options.keys()), 
                                  selection_mode="multi")
        if selected_names:
            selected_subject_keys = [subject_options[name] for name in selected_names]
        else:
            st.info("Please select at least one subject to get a deep-dive strategy.")

    user_prompt = st.text_area("What is your study goal or question?", 
                               placeholder="e.g., How should I prepare for Polity? Or: Give me a 3-month plan for Geography and Economy.",
                               height=100)
    
    col1, col2 = st.columns(2)
    exam_type = col1.radio("Exam Type:", ["Prelims", "Mains"])
    exam_date = col2.date_input("Target Exam Date:", value=None)

    if st.button("🚀 Ask Esu", type="primary"):
        if user_prompt.strip() or (query_type == "Subject-Wise Deep Dive" and selected_subject_keys):
            # If prompt is empty but subjects are selected, create a default prompt
            if not user_prompt.strip() and selected_subject_keys:
                from upsc_strategy_data import ALL_SUBJECTS
                subject_names = [ALL_SUBJECTS[k]['name'] for k in selected_subject_keys]
                user_prompt = f"Provide a detailed strategy and study plan for: {', '.join(subject_names)}"

            with st.spinner("Esu is thinking..."):
                results = get_results()
                quiz_analysis = analyze_quiz_performance(results)
                exam_dt = datetime.combine(exam_date, datetime.min.time()) if exam_date else None
                
                # Detect and store subjects for cross-page context
                from upsc_strategy_data import detect_subjects
                detected = selected_subject_keys if selected_subject_keys else detect_subjects(user_prompt)
                st.session_state["esu_detected_subjects"] = detected
                
                study_plan = generate_personalized_study_plan(
                    user_prompt, quiz_analysis, exam_dt, exam_type.lower(), 
                    selected_subjects=selected_subject_keys
                )
                perf_summary = generate_performance_summary(quiz_analysis, exam_type.lower())
                
                st.session_state["study_plan_output"] = format_study_plan_output(study_plan, perf_summary, quiz_analysis)
                st.session_state["study_plan_generated"] = True
                safe_rerun()
        else:
            st.warning("Please provide a question or select subjects first.")

    if st.session_state.get("study_plan_generated"):
        output = st.session_state["study_plan_output"]
        st.markdown(output.get("study_plan", ""))
        
        col_s1, col_s2 = st.columns([1, 4])
        if col_s1.button("💾 Save Strategy"):
            save_ai_report("Esu Study Plan", f"Goal: {user_prompt[:30]}", output.get("study_plan", ""))
            st.success("Strategy saved!")
        
        if col_s2.button("🗑️ Clear Answer"):
            st.session_state["study_plan_generated"] = False
            if "study_plan_output" in st.session_state:
                del st.session_state["study_plan_output"]
            safe_rerun()
