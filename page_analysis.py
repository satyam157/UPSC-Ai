import streamlit as st
import pandas as pd
from datetime import date, timedelta
from ui_components import safe_rerun, acc_class
from db import (
    get_results, delete_result, get_ai_reports, 
    save_ai_report, delete_ai_report, get_test_papers,
    save_test_paper, delete_test_paper
)
from llm import ask_llm

def show_results_page():
    st.subheader("📊 Quiz Results & Performance")
    data = get_results()
    if data:
        df = pd.DataFrame([x[1:] for x in data], columns=[
            "Test Name", "Total", "Attempted", "Correct", "Wrong", "Accuracy", "Marks"
        ])
        st.table(df)
        
        total_tests = len(data)
        avg_accuracy = sum(x[6] for x in data) / total_tests if total_tests > 0 else 0
        st.metric("Avg Accuracy", f"{avg_accuracy:.1f}%")
        
        if st.button("🗑️ Clear Results"):
            # confirmation logic...
            pass
    else:
        st.info("No results yet.")

def show_ai_analysis_page():
    st.subheader("🤖 AI-Powered Quiz Analysis")
    results = get_results()
    if not results:
        st.warning("No quiz results found.")
        return

    if st.button("🔍 Generate AI Analysis", type="primary"):
        prompt = f"Analyze my UPSC prep performance based on these results: {results}"
        with st.spinner("Analyzing..."):
            analysis = ask_llm(prompt)
        st.markdown(analysis)
        save_ai_report("Quiz Analysis", str(date.today()), analysis)

def show_test_paper_analysis_page():
    st.subheader("📝 Test Paper Analysis")
    
    with st.expander("➕ Add New Test Paper Entry", expanded=False):
        with st.form("new_test_paper_form"):
            test_name = st.text_input("Test Name/Subject", placeholder="e.g., Vision IAS Mock 1")
            test_date = st.date_input("Test Date", date.today())
            
            col1, col2, col3 = st.columns(3)
            with col1:
                total_q = st.number_input("Total Questions", min_value=1, value=100)
                attempted = st.number_input("Attempted", min_value=0, value=0)
            with col2:
                # not_attempted will be calculated before saving
                st.markdown("**(Not Attempted will be calculated)**")
                guessed_correct = st.number_input("Guessed Correctly", min_value=0, value=0)
            with col3:
                guessed_incorrect = st.number_input("Guessed Incorrectly (Silly Mistakes)", min_value=0, value=0)
                
            notes = st.text_area("Carelessness Notes / Remarks", placeholder="e.g., misread 'NOT' in question 45...")
            
            submitted = st.form_submit_button("Save Test Paper")
            if submitted:
                if not test_name.strip():
                    st.error("Please enter a Test Name.")
                else:
                    not_attempted = total_q - attempted
                    save_test_paper(
                        test_name, test_date, total_q, attempted, not_attempted,
                        guessed_correct, guessed_incorrect, notes
                    )
                    st.success("Test paper saved successfully!")
                    safe_rerun()

    st.markdown("---")
    st.subheader("📚 Past Test Papers")
    papers = get_test_papers()
    if papers:
        for p in papers:
            pid = p[0]
            with st.expander(f"📄 {p[1]} (Date: {p[2]})"):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Total Questions", p[3])
                c2.metric("Attempted", p[4])
                c3.metric("Guessed Correct", p[6])
                c4.metric("Guessed Incorrect", p[7])
                
                if p[8]:
                    st.write("**Notes:**")
                    st.info(p[8])
                
                if st.button("🗑️ Delete", key=f"del_tp_{pid}"):
                    delete_test_paper(pid)
                    safe_rerun()
    else:
        st.info("No test paper records found.")
