import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from ui_components import safe_rerun, acc_class
from db import (
    get_results, save_result, delete_result, clear_results,
    get_test_papers, save_test_paper, delete_test_paper,
    get_unified_test_records, seed_demo_results,
    get_ai_reports, save_ai_report, delete_ai_report
)
from llm import ask_llm
from codeforces_visualizer import (
    render_codeforces_dashboard, get_tier_info,
    PRELIMS_TIERS, MAINS_TIERS
)


def _render_exam_tab(exam_type="Prelims"):
    """Renders the complete Codeforces-style analytics & test logger for an exam type."""
    is_prelims = (exam_type.lower() == "prelims")
    username = st.session_state.get("username")
    
    # 1. Fetch Unified Test Records
    records = get_unified_test_records(username=username, exam_type=exam_type)
    
    # 2. Key Metrics Row
    total_tests = len(records)
    if total_tests > 0:
        avg_marks = sum(r["marks"] for r in records) / total_tests
        max_marks = max(r["marks"] for r in records)
        avg_acc = sum(r["accuracy"] for r in records) / total_tests
        latest_record = records[-1]
        latest_marks = latest_record["marks"]
        tier_inf = get_tier_info(latest_marks, exam_type)
        
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Total Tests", total_tests)
        m2.metric("Average Marks", f"{avg_marks:.1f}")
        m3.metric("Highest Marks", f"{max_marks:.1f}")
        if is_prelims:
            m4.metric("Average Accuracy", f"{avg_acc:.1f}%")
        else:
            m4.metric("Latest Score", f"{latest_marks:.1f}")
            
        with m5:
            st.markdown(
                f'<div style="background:#1e2430;border:1px solid {tier_inf["color"]};border-radius:10px;padding:8px 12px;text-align:center;">'
                f'<span style="font-size:11px;color:#94a3b8;display:block;">Current Rank Tier</span>'
                f'<b style="color:{tier_inf["color"]};font-size:13px;">{tier_inf["name"]}</b>'
                f'</div>',
                unsafe_allow_html=True
            )
    else:
        st.info(f"No {exam_type} test results recorded yet. Log a test below or click 'Load Demo Codeforces Data' to see the visualization!")

    # 3. Codeforces Marks Graph & Activity Heatmap Dashboard
    render_codeforces_dashboard(records, exam_type=exam_type, username=username)

    st.markdown("---")

    # 4. Action Bars & Test Logger
    col_log, col_demo = st.columns([2, 1])
    
    with col_log:
        with st.expander(f"➕ Log New {exam_type} Test Result / Mock Score", expanded=False):
            with st.form(f"log_test_form_{exam_type}"):
                t_name = st.text_input("Test / Mock Name", placeholder=f"e.g., {'Vision IAS Abhyas Mock 1' if is_prelims else 'ForumIAS MGP GS 2 Full Mock'}")
                t_date = st.date_input("Test Date", date.today(), key=f"form_date_{exam_type}")
                
                if is_prelims:
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        total_q = st.number_input("Total Questions", min_value=1, value=100, step=5)
                        attempted = st.number_input("Attempted", min_value=0, value=85, step=1)
                    with c2:
                        correct = st.number_input("Correct", min_value=0, value=65, step=1)
                        wrong = st.number_input("Wrong", min_value=0, value=20, step=1)
                    with c3:
                        calc_marks = round(correct * 2.0 - wrong * 0.66, 2)
                        custom_marks = st.number_input("Marks Scored (Auto-calculated: +2 / -0.66)", value=float(calc_marks), step=0.5)
                        st.caption(f"Calculated: **{calc_marks:.2f}** / {total_q * 2}")
                    notes = st.text_area("Remarks / Carelessness Notes", placeholder="e.g. Silly mistake in Modern History; need revision on Art & Culture...")
                else:
                    c1, c2 = st.columns(2)
                    with c1:
                        mains_paper = st.selectbox("Paper", ["GS Paper 1", "GS Paper 2", "GS Paper 3", "GS Paper 4 (Ethics)", "Essay", "Optional Paper 1", "Optional Paper 2"])
                        total_m = st.number_input("Total Marks", min_value=10, value=250, step=25)
                    with c2:
                        custom_marks = st.number_input("Marks Scored", min_value=0.0, max_value=float(total_m), value=95.0, step=0.5)
                        total_q = st.number_input("Total Questions Written", min_value=1, value=20, step=1)
                    notes = st.text_area("Evaluator Feedback / Key Weaknesses", placeholder="e.g. Introduction lacked constitutional articles; needed more case laws in GS2...")
                    correct, wrong, attempted = total_q, 0, total_q

                submitted = st.form_submit_button(f"💾 Save {exam_type} Test", type="primary", use_container_width=True)
                if submitted:
                    if not t_name.strip():
                        st.error("Please enter a Test Name.")
                    else:
                        acc = round((correct / attempted * 100), 1) if attempted > 0 else 0.0
                        full_name = f"[{mains_paper}] {t_name}" if not is_prelims else t_name
                        save_result(
                            (full_name, total_q, attempted, correct, wrong, acc, custom_marks),
                            username=username,
                            exam_type=exam_type,
                            test_date=t_date,
                            notes=notes
                        )
                        st.success(f"{exam_type} test recorded successfully!")
                        safe_rerun()

    with col_demo:
        with st.expander("⚙️ Data Options & Demo Seed", expanded=False):
            st.caption("Instantly test the Codeforces Graph & Heatmap with realistic UPSC mock series data.")
            if st.button(f"✨ Load Demo {exam_type} Data", key=f"btn_demo_{exam_type}", use_container_width=True):
                seed_demo_results(username=username, exam_type=exam_type)
                st.success(f"Generated realistic {exam_type} test series!")
                safe_rerun()
                
            st.markdown("---")
            confirm_clear = st.checkbox(f"Confirm clear all {exam_type} records", key=f"chk_clr_{exam_type}")
            if st.button(f"🗑️ Clear {exam_type} Data", disabled=not confirm_clear, key=f"btn_clr_{exam_type}", use_container_width=True):
                clear_results(username=username, exam_type=exam_type)
                st.info(f"Cleared all {exam_type} results.")
                safe_rerun()

    # 5. Detailed Test History Table
    st.markdown(f"#### 📜 Past {exam_type} Test History")
    if records:
        rows = []
        for r in reversed(records):  # Most recent first
            d_str = r["date"].strftime("%d %b %Y") if hasattr(r["date"], "strftime") else str(r["date"])
            t_inf = get_tier_info(r["marks"], exam_type)
            rows.append({
                "Date": d_str,
                "Test Name": r["name"],
                "Source": r["source"],
                "Marks": f"{r['marks']:.2f} / {int(r['total_marks'])}",
                "Accuracy": f"{r['accuracy']:.1f}%",
                "Correct": r["correct"],
                "Wrong": r["wrong"],
                "Tier": t_inf["name"],
                "_id": r["id"],
                "_raw_id": r["raw_id"]
            })
        
        df_display = pd.DataFrame(rows)
        # Display clean table
        st.dataframe(
            df_display.drop(columns=["_id", "_raw_id"]),
            use_container_width=True,
            hide_index=True
        )
        
        # Single-item delete tool
        with st.expander("🗑️ Delete an Entry", expanded=False):
            del_opts = {f"{r['Date']} — {r['Test Name']} (Marks: {r['Marks']})": (r["_id"], r["_raw_id"]) for r in rows}
            selected_del = st.selectbox("Select test to delete", list(del_opts.keys()), key=f"sel_del_{exam_type}")
            if st.button("Delete Selected Test", type="secondary", key=f"btn_del_single_{exam_type}"):
                item_id, raw_id = del_opts[selected_del]
                if item_id.startswith("res_"):
                    delete_result(raw_id, username=username)
                else:
                    delete_test_paper(raw_id, username=username)
                st.success("Test deleted.")
                safe_rerun()
    else:
        st.info(f"No {exam_type} tests found.")


def show_results_page():
    st.subheader("📊 UPSC Performance Analytics & Test Results")
    st.markdown(
        "Track your preparation trajectory using Codeforces-style **Marks Graphs** and "
        "**Calendar Activity Heatmaps**. Prelims and Mains are tracked as distinct exams with custom rating tiers."
    )
    
    tab_prelims, tab_mains = st.tabs(["🎯 Prelims Performance", "✍️ Mains Performance"])
    
    with tab_prelims:
        _render_exam_tab("Prelims")
        
    with tab_mains:
        _render_exam_tab("Mains")


def show_ai_analysis_page():
    st.subheader("🤖 AI-Powered Quiz & Test Analysis")
    username = st.session_state.get("username")
    prelims_records = get_unified_test_records(username=username, exam_type="Prelims")
    mains_records = get_unified_test_records(username=username, exam_type="Mains")
    
    if not prelims_records and not mains_records:
        st.warning("No test or quiz results found. Attempt tests to unlock AI analysis.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.info(f"🎯 Prelims records available: **{len(prelims_records)}**")
    with col2:
        st.info(f"✍️ Mains records available: **{len(mains_records)}**")

    analysis_scope = st.radio("Select Scope for AI Evaluation", ["Prelims Focus", "Mains Focus", "Comprehensive (Both Prelims & Mains)"], horizontal=True)

    if st.button("🔍 Generate AI Strategic Analysis", type="primary", use_container_width=True):
        if analysis_scope == "Prelims Focus":
            data_context = prelims_records[-15:]
        elif analysis_scope == "Mains Focus":
            data_context = mains_records[-15:]
        else:
            data_context = {"Prelims": prelims_records[-10:], "Mains": mains_records[-10:]}

        prompt = f"""
        You are a senior UPSC mentor and Civil Services Examination topper. Analyze the aspirant's test performance trajectory:
        Performance Data: {data_context}
        
        Provide a structured, rigorous assessment:
        1. **Marks Trajectory & Consistency**: Analyze the progression of marks and identify growth or stagnation.
        2. **Accuracy & Negative Marking Audit**: Pinpoint issues with risk management and silly mistakes.
        3. **Subject-wise & Paper-wise Weak Spots**: Highlight critical areas needing immediate revision.
        4. **Actionable 30-Day Strategy**: 3 specific, high-yield interventions to raise score into the safe cutoff / selection zone.
        """
        with st.spinner("Analyzing performance with AI mentor..."):
            analysis = ask_llm(prompt)
        st.markdown(analysis)
        save_ai_report(f"AI Performance Analysis ({analysis_scope})", str(date.today()), analysis)


def show_test_paper_analysis_page():
    st.subheader("📝 Test Paper Analysis & Mock Tracking")
    st.caption("Deep-dive into full-length mock papers, careless mistakes, guessing accuracy, and score trajectories.")
    username = st.session_state.get("username")
    
    with st.expander("➕ Add New Mock Test Paper Entry", expanded=False):
        with st.form("new_test_paper_form"):
            t_exam_type = st.radio("Exam Type", ["Prelims", "Mains"], horizontal=True)
            test_name = st.text_input("Test Name / Coaching Institute", placeholder="e.g., Vision IAS Abhyas Mock 1 / ForumIAS SFG")
            test_date = st.date_input("Test Date", date.today())
            
            if t_exam_type == "Prelims":
                col1, col2, col3 = st.columns(3)
                with col1:
                    total_q = st.number_input("Total Questions", min_value=1, value=100)
                    attempted = st.number_input("Attempted", min_value=0, value=85)
                with col2:
                    guessed_correct = st.number_input("Guessed Correctly (Intuition/50-50)", min_value=0, value=10)
                    guessed_incorrect = st.number_input("Guessed Incorrectly (Silly Mistakes)", min_value=0, value=8)
                with col3:
                    correct = st.number_input("Total Correct", min_value=0, value=60)
                    wrong = attempted - correct if attempted >= correct else 0
                    st.caption(f"Wrong answers: **{wrong}**")
                    calc_marks = round(correct * 2.0 - wrong * 0.66, 2)
                    marks_val = st.number_input("Total Marks Scored", value=float(calc_marks), step=0.5)
                    total_marks_val = float(total_q * 2)
            else:
                col1, col2, col3 = st.columns(3)
                with col1:
                    mains_paper = st.selectbox("Paper", ["GS 1", "GS 2", "GS 3", "GS 4", "Essay", "Optional 1", "Optional 2"])
                    total_q = st.number_input("Questions Written", min_value=1, value=20)
                with col2:
                    total_marks_val = st.number_input("Paper Total Marks", min_value=10.0, value=250.0, step=25.0)
                    marks_val = st.number_input("Marks Awarded", min_value=0.0, max_value=float(total_marks_val), value=92.0, step=0.5)
                with col3:
                    guessed_correct = 0
                    guessed_incorrect = 0
                    correct = total_q
                    wrong = 0
                    attempted = total_q
                    st.caption(f"Percentage: **{(marks_val / total_marks_val * 100):.1f}%**")
                
            notes = st.text_area("Carelessness Notes / Remarks & Key Learnings", placeholder="e.g., Misread 'NOT correct' in Q45; didn't manage time well on questions 80-100...")
            
            submitted = st.form_submit_button("💾 Save Test Paper", type="primary", use_container_width=True)
            if submitted:
                if not test_name.strip():
                    st.error("Please enter a Test Name.")
                else:
                    not_attempted = total_q - attempted if total_q >= attempted else 0
                    acc = round(correct / attempted * 100, 1) if attempted > 0 else 0.0
                    save_test_paper(
                        test_name, test_date, total_q, attempted, not_attempted,
                        guessed_correct, guessed_incorrect, notes, username=username,
                        exam_type=t_exam_type, marks=marks_val, total_marks=total_marks_val,
                        correct=correct, wrong=wrong, accuracy=acc
                    )
                    st.success("Test paper saved successfully!")
                    safe_rerun()

    st.markdown("---")
    
    # Filter between Prelims & Mains
    filter_exam = st.radio("Display Mock Papers for:", ["🎯 Prelims Papers", "✍️ Mains Papers"], horizontal=True)
    selected_type = "Prelims" if "Prelims" in filter_exam else "Mains"
    
    papers = get_test_papers(username=username, exam_type=selected_type)
    
    if papers:
        # Mini Codeforces graph for test papers
        paper_records = get_unified_test_records(username=username, exam_type=selected_type)
        paper_records_only = [r for r in paper_records if r["source"] == "Mock Paper"]
        
        if paper_records_only:
            st.markdown(f"#### 📈 {selected_type} Mock Trajectory")
            render_codeforces_dashboard(paper_records_only, exam_type=selected_type, username=username)
            st.markdown("---")
            
        st.markdown(f"#### 📚 Past {selected_type} Mock Test Records ({len(papers)})")
        for p in papers:
            # id, test_name, test_date, total_questions, attempted, not_attempted,
            # guessed_correct, guessed_incorrect, carelessness_notes,
            # exam_type, marks, total_marks, correct, wrong, accuracy, created_at
            pid = p[0]
            tname = p[1]
            tdate = p[2]
            tot_q = p[3]
            att = p[4]
            g_corr = p[6]
            g_inc = p[7]
            notes = p[8]
            marks_scored = p[10] if len(p) > 10 else 0.0
            tot_m = p[11] if len(p) > 11 else (200.0 if selected_type == "Prelims" else 250.0)
            
            with st.expander(f"📄 {tname} — Date: {tdate} | Score: {marks_scored:.1f} / {tot_m:.0f}"):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Marks Scored", f"{marks_scored:.1f} / {tot_m:.0f}")
                c2.metric("Attempted", f"{att} / {tot_q}")
                if selected_type == "Prelims":
                    c3.metric("Guessed Correct", g_corr)
                    c4.metric("Guessed Incorrect", g_inc)
                else:
                    c3.metric("Score %", f"{(marks_scored / tot_m * 100):.1f}%")
                    c4.metric("Questions Written", tot_q)
                
                if notes:
                    st.write("**Carelessness Notes / Remarks:**")
                    st.info(notes)
                
                if st.button("🗑️ Delete Record", key=f"del_tp_{pid}"):
                    delete_test_paper(pid, username=username)
                    st.success("Test paper deleted.")
                    safe_rerun()
    else:
        st.info(f"No {selected_type} mock paper records found yet. Click 'Add New Mock Test Paper Entry' above to add one!")
