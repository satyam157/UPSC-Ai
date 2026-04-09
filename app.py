import streamlit as st
import pandas as pd
import PyPDF2
from datetime import date, datetime, timedelta
import json

from scraper import fetch_news
from db import (
    insert_news, get_news, clean_old, get_retention, set_retention,
    save_result, get_results, delete_result,
    save_item, get_saved_items, delete_saved_item,
    add_ca_filter, get_ca_filters, delete_ca_filter,
    save_ai_report, get_ai_reports, delete_ai_report,
    save_test_paper, get_test_papers, delete_test_paper
)
from quiz_generator import generate_quiz
from llm import ask_llm
from quiz_parser import parse_quiz
from quiz_engine import evaluate
from pdf_utils import generate_pdf
from pyq_engine import predict

# ─── PAGE CONFIG ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="UPSC AI System", layout="wide")

# ─── CUSTOM CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
.popup-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.65); z-index: 9998; display: flex; align-items: center; justify-content: center;}
.popup-box { background: #1e1e2e; border: 1px solid #7c3aed; border-radius: 14px; padding: 28px 32px; max-width: 780px; width: 95%; max-height: 84vh; overflow-y: auto; position: relative; color: #e2e8f0;}
.popup-close { position: absolute; top: 12px; right: 16px; font-size: 22px; cursor: pointer; color: #a78bfa; background: none; border: none;}
.popup-close:hover { color: #ef4444;}
.test-table { width: 100%; border-collapse: collapse; font-size: 13px;}
.test-table th, .test-table td { border: 1px solid #374151; padding: 8px 10px; text-align: center; color: #e2e8f0;}
.test-table th { background: #2d1b6b; color: #c4b5fd;}
.test-table tr:nth-child(even) { background: #1a1a2e;}
.test-table tr:hover { background: #2d2d44;}
.read-more-btn { background: #7c3aed; color: white; border: none; padding: 4px 10px; border-radius: 6px; cursor: pointer;}
.section-card { background: #16162a; border: 1px solid #312e81; border-radius: 12px; padding: 18px 22px; margin-bottom: 18px;}
.accuracy-good { color: #34d399; font-weight: 600; }
.accuracy-mid  { color: #fbbf24; font-weight: 600; }
.accuracy-low  { color: #f87171; font-weight: 600; }
.filter-tag { display: inline-flex; align-items: center; background: #2d1b6b; color: #c4b5fd; border-radius: 20px; padding: 4px 12px; margin: 4px; font-size: 13px; }
.filter-tag .tag-x { margin-left: 8px; cursor: pointer; color: #f87171; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ─── AUTH (UPDATED) ───────────────────────────────────────────────────────────
CREDENTIALS = {
    "admin": "admin123",
    "esu": "satyam",
    "rishika": "love",
    "love": "esu"
}

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["username"] = ""

# Optional: auto login using query params
params = st.query_params
saved_user = params.get("user")

if saved_user and saved_user in CREDENTIALS:
    st.session_state["logged_in"] = True
    st.session_state["username"] = saved_user

def login_page():
    st.markdown("## 🔐 Login to UPSC AI SYSTEM")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")

        if submit:
            if username in CREDENTIALS and CREDENTIALS[username] == password:
                st.session_state["logged_in"] = True
                st.session_state["username"] = username

                # Save login in URL (optional persistence)
                st.query_params["user"] = username

                st.success("✅ Login successful!")
                st.rerun()
            else:
                st.error("❌ Invalid Username or Password")

def logout():
    st.session_state.clear()
    st.query_params.clear()
    st.success("Logged out successfully")
    st.rerun()

if not st.session_state["logged_in"]:
    login_page()
    st.stop()

# ─── SIDEBAR ──────────────────────────────────────────────────────────────────
st.sidebar.title(f"👤 {st.session_state['username']}")
if st.sidebar.button("Logout"):
    logout()

page = st.sidebar.radio("Navigate", [
    "Current Affairs",
    "CA Quiz",
    "PDF Quiz",
    "Results",
    "AI Analysis",
    "Test Paper Analysis",
    "PYQ Predictor"
])

st.title("📚 UPSC AI SYSTEM")

# ─── helper: safe rerun ───────────────────────────────────────────────────────
def safe_rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()

# ─── helper: accuracy colour ─────────────────────────────────────────────────
def acc_class(val):
    if val >= 70: return "accuracy-good"
    if val >= 50: return "accuracy-mid"
    return "accuracy-low"

def clear_state(key):
    st.session_state[key] = ""


# ══════════════════════════════════════════════════════════════════════════════
#   CURRENT AFFAIRS
# ══════════════════════════════════════════════════════════════════════════════
if page == "Current Affairs":
    # ── Control row ──────────────────────────────────────────────────────────
    if st.button("🔄 Refresh Content", use_container_width=True):
        with st.spinner("Fetching news..."):
            insert_news(fetch_news())
        st.toast("✅ Feed updated successfully!")
        safe_rerun()

    # ── CA Filter Section ─────────────────────────────────────────────────────
    st.markdown("---")
    with st.expander("🔧 Manage CA Topic Filters", expanded=False):
        st.markdown("Add words/phrases below. Any news headline containing these words will be **hidden** from the feed.")
        
        # Show existing tags
        existing_filters = get_ca_filters()
        if existing_filters:
            tags_html = ""
            for fid, word in existing_filters:
                tags_html += f'<span class="filter-tag">{word}<span class="tag-x" title="Remove">✕</span></span>'
            st.markdown(f'<div>{tags_html}</div>', unsafe_allow_html=True)
            
            # Remove filter UI
            filter_options = [f"{word} (id:{fid})" for fid, word in existing_filters]
            to_remove = st.selectbox("Select filter to remove", [""] + filter_options, key="rm_filter")
            if to_remove and st.button("Remove Filter Word", key="btn_rm_filter"):
                fid = int(to_remove.split("id:")[1].rstrip(")"))
                delete_ca_filter(fid)
                st.success("Filter removed!")
                safe_rerun()
        else:
            st.info("No filter words added yet.")

        # Add new filter
        with st.form("add_filter_form"):
            new_word = st.text_input("New filter word / phrase (e.g. 'cricket', 'bollywood')")
            if st.form_submit_button("➕ Add Filter"):
                if new_word.strip():
                    add_ca_filter(new_word.strip())
                    st.success(f"Added filter: '{new_word.strip()}'")
                    safe_rerun()
                else:
                    st.warning("Please enter a word first.")

    # ── News Feed ─────────────────────────────────────────────────────────────
    st.markdown("---")
    news_data = get_news()
    filter_words = [w.lower() for _, w in get_ca_filters()]

    def is_filtered(title):
        tl = title.lower()
        return any(fw in tl for fw in filter_words)

    if news_data:
        dates = sorted(list(set(n[2] for n in news_data)), reverse=True)
        for d in dates:
            day_items = [n for n in news_data if n[2] == d and not is_filtered(n[0])]
            if day_items:
                with st.expander(f"📅 Current Affairs for {d} ({len(day_items)} items)"):
                    for n in day_items:
                        st.markdown(f"**• {n[0]}**")
    else:
        st.info("No Current Affairs data available. Please refresh to fetch current affairs.")

    # ── Retention Rules (Moved to Bottom) ─────────────────────────────────────
    st.markdown("---")
    username = st.session_state["username"]
    current_retention = get_retention(username)
    
    col_ret_label, col_ret_input, col_ret_apply = st.columns([1.5, 1, 1.5])
    with col_ret_label:
        st.markdown('<p style="text-align:right; margin-top:10px; font-weight:600; color:#c4b5fd;">Data Retention Settings:</p>', unsafe_allow_html=True)
    with col_ret_input:
        retention_days = st.number_input("Retention Days", min_value=1, max_value=365, value=current_retention, label_visibility="collapsed")
        if retention_days != current_retention:
            set_retention(username, retention_days)
            st.toast(f"⚙️ Retention set to {retention_days} days")
    with col_ret_apply:
        if st.button("🧹 Apply Rules", use_container_width=True, help="Delete data older than retention period"):
            clean_old(days=retention_days)
            st.success(f"🗑️ Cleaned data older than {retention_days} days!")


# ══════════════════════════════════════════════════════════════════════════════
#   CA QUIZ
# ══════════════════════════════════════════════════════════════════════════════
elif page == "CA Quiz":
    if st.button("Generate Quiz"):
        data = get_news()
        if not data:
            st.warning("No current affairs data available. Please refresh first.")
        else:
            data = sorted(data, key=lambda x: x[2], reverse=True)
            text = "\n".join([x[0] for x in data[:20]])
            q, a = generate_quiz(text)
            st.session_state["q"] = q
            st.session_state["a"] = a
            content = "CA Quiz\n\n"
            for idx, (quest, ans) in enumerate(zip(q, a)):
                content += f"Q{idx+1}: {quest}\nA: {ans}\n\n"
            save_item("CA Quiz", content)

    if "q" in st.session_state:
        user = []
        for i, q in enumerate(st.session_state["q"]):
            user.append(st.radio(q, ["A", "B", "C", "D"], key=i))

        if st.button("Submit CA Quiz"):
            res = evaluate(user, st.session_state["a"])
            content = ""
            st.subheader("Answer Review")
            for i, (u, c) in enumerate(zip(user, st.session_state["a"])):
                if u == c:
                    st.success(f"Q{i+1}: {u} ✅")
                else:
                    st.error(f"Q{i+1}: {u} ❌ | Correct: {c}")
                content += f"Q{i+1}: Your={u}, Correct={c}\n"
            pdf = generate_pdf(content)
            st.download_button("Download PDF", open(pdf, "rb"), file_name="CA_Quiz.pdf")
            save_result(("CA_1", *res))

    # ── Previous CA Quiz with ✕ close ────────────────────────────────────────
    st.markdown("---")
    st.subheader("📂 Previous CA Quizzes")
    saved_items = get_saved_items()
    ca_items = [item for item in saved_items if item[1] == "CA Quiz"]

    if ca_items:
        options = [f"CA Quiz – {item[3]}" for item in ca_items]
        selected = st.selectbox("Select a previous quiz", [""] + options, key="sel_ca")

        if selected:
            idx = options.index(selected)
            item_id = ca_items[idx][0]
            content = ca_items[idx][2]

            # Render with ✕ close button
            close_key = f"close_ca_{item_id}"
            if st.session_state.get(close_key):
                st.session_state[close_key] = False
                safe_rerun()

            col_content, col_close = st.columns([20, 1])
            with col_close:
                st.button("✕", key=f"x_ca_{item_id}", help="Close", on_click=clear_state, args=("sel_ca",))
            with col_content:
                st.text_area("Content", content, height=280, key=f"ta_ca_{item_id}")

            # Delete option
            if st.button("🗑️ Remove from Database", key=f"del_ca_{item_id}"):
                st.session_state[f"confirm_del_ca_{item_id}"] = True
                safe_rerun()
            if st.session_state.get(f"confirm_del_ca_{item_id}"):
                st.warning("Are you sure you want to delete this quiz?")
                c1, c2 = st.columns(2)
                if c1.button("Yes", key=f"yes_ca_{item_id}"):
                    delete_saved_item(item_id)
                    st.session_state[f"confirm_del_ca_{item_id}"] = False
                    safe_rerun()
                if c2.button("No", key=f"no_ca_{item_id}"):
                    st.session_state[f"confirm_del_ca_{item_id}"] = False
                    safe_rerun()
    else:
        st.info("No previous CA Quiz items found.")


# ══════════════════════════════════════════════════════════════════════════════
#   PDF QUIZ
# ══════════════════════════════════════════════════════════════════════════════
elif page == "PDF Quiz":
    pdf_file = st.file_uploader("Upload PDF")
    col1, col2 = st.columns(2)
    start = col1.number_input("From Page", 1)
    end = col2.number_input("To Page", 1)

    if pdf_file and st.button("Generate PDF Quiz"):
        reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for i in range(int(start) - 1, int(end)):
            text += reader.pages[i].extract_text()
        q, a = generate_quiz(text)
        st.session_state["pq"] = q
        st.session_state["pa"] = a
        content = "PDF Quiz\n\n"
        for idx, (quest, ans) in enumerate(zip(q, a)):
            content += f"Q{idx+1}: {quest}\nA: {ans}\n\n"
        save_item("PDF Quiz", content)

    if "pq" in st.session_state:
        user = []
        for i, q in enumerate(st.session_state["pq"]):
            user.append(st.radio(q, ["A", "B", "C", "D"], key=f"p{i}"))

        if st.button("Submit PDF Quiz"):
            res = evaluate(user, st.session_state["pa"])
            content = ""
            st.subheader("Answer Review")
            for i, (u, c) in enumerate(zip(user, st.session_state["pa"])):
                if u == c:
                    st.success(f"Q{i+1}: {u} ✅")
                else:
                    st.error(f"Q{i+1}: {u} ❌ | Correct: {c}")
                content += f"Q{i+1}: Your={u}, Correct={c}\n"
            pdf = generate_pdf(content)
            st.download_button("Download PDF", open(pdf, "rb"), file_name="PDF_Quiz.pdf")
            save_result(("PDF_1", *res))

    # ── Previous PDF Quiz with ✕ close ────────────────────────────────────────
    st.markdown("---")
    st.subheader("📂 Previous PDF Quizzes")
    saved_items = get_saved_items()
    pdf_items = [item for item in saved_items if item[1] == "PDF Quiz"]

    if pdf_items:
        options = [f"PDF Quiz – {item[3]}" for item in pdf_items]
        selected = st.selectbox("Select a previous quiz", [""] + options, key="sel_pdf")

        if selected:
            idx = options.index(selected)
            item_id = pdf_items[idx][0]
            content = pdf_items[idx][2]

            col_content, col_close = st.columns([20, 1])
            with col_close:
                st.button("✕", key=f"x_pdf_{item_id}", help="Close", on_click=clear_state, args=("sel_pdf",))
            with col_content:
                st.text_area("Content", content, height=280, key=f"ta_pdf_{item_id}")

            if st.button("🗑️ Remove from Database", key=f"del_pdf_{item_id}"):
                st.session_state[f"confirm_del_pdf_{item_id}"] = True
                safe_rerun()
            if st.session_state.get(f"confirm_del_pdf_{item_id}"):
                st.warning("Are you sure?")
                c1, c2 = st.columns(2)
                if c1.button("Yes", key=f"yes_pdf_{item_id}"):
                    delete_saved_item(item_id)
                    st.session_state[f"confirm_del_pdf_{item_id}"] = False
                    safe_rerun()
                if c2.button("No", key=f"no_pdf_{item_id}"):
                    st.session_state[f"confirm_del_pdf_{item_id}"] = False
                    safe_rerun()
    else:
        st.info("No previous PDF Quiz items found.")


# ══════════════════════════════════════════════════════════════════════════════
#   PYQ PREDICTOR
# ══════════════════════════════════════════════════════════════════════════════
elif page == "PYQ Predictor":
    if st.button("Predict PYQ Topics"):
        data_news = [x[0] for x in get_news()]
        out = predict(data_news)
        st.write(out)
        save_item("PYQ Predictor", out)
        pdf = generate_pdf(out)
        st.download_button("Download PDF", open(pdf, "rb"), file_name="pyq.pdf")

    # ── Previous PYQ with ✕ close ─────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📂 Previous PYQ Predictions")
    saved_items = get_saved_items()
    pyq_items = [item for item in saved_items if item[1] == "PYQ Predictor"]

    if pyq_items:
        options = [f"PYQ – {item[3]}" for item in pyq_items]
        selected = st.selectbox("Select a previous prediction", [""] + options, key="sel_pyq")

        if selected:
            idx = options.index(selected)
            item_id = pyq_items[idx][0]
            content = pyq_items[idx][2]

            col_content, col_close = st.columns([20, 1])
            with col_close:
                st.button("✕", key=f"x_pyq_{item_id}", help="Close", on_click=clear_state, args=("sel_pyq",))
            with col_content:
                st.text_area("Content", content, height=280, key=f"ta_pyq_{item_id}")

            if st.button("🗑️ Remove from Database", key=f"del_pyq_{item_id}"):
                st.session_state[f"confirm_del_pyq_{item_id}"] = True
                safe_rerun()
            if st.session_state.get(f"confirm_del_pyq_{item_id}"):
                st.warning("Are you sure?")
                c1, c2 = st.columns(2)
                if c1.button("Yes", key=f"yes_pyq_{item_id}"):
                    delete_saved_item(item_id)
                    st.session_state[f"confirm_del_pyq_{item_id}"] = False
                    safe_rerun()
                if c2.button("No", key=f"no_pyq_{item_id}"):
                    st.session_state[f"confirm_del_pyq_{item_id}"] = False
                    safe_rerun()
    else:
        st.info("No previous PYQ Predictor items found.")


# ══════════════════════════════════════════════════════════════════════════════
#   RESULTS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Results":
    data = get_results()
    if data:
        df = pd.DataFrame([x[1:] for x in data], columns=[
            "Test Name", "Total", "Attempted", "Correct", "Wrong", "Accuracy", "Marks"
        ])
        st.table(df)

        st.markdown("### Remove Result")
        del_options = [f"ID: {x[0]} | {x[1]} | Marks: {x[7]}" for x in data]
        selected_del = st.selectbox("Select result to remove", [""] + del_options)

        if selected_del:
            idx = del_options.index(selected_del) - 1
            rowid = data[idx][0]
            if st.button("Remove Result", key=f"del_res_{rowid}"):
                st.session_state[f"confirm_delete_res_{rowid}"] = True
                safe_rerun()
            if st.session_state.get(f"confirm_delete_res_{rowid}"):
                st.warning("Are you sure you want to delete this result?")
                c1, c2 = st.columns(2)
                if c1.button("Yes", key=f"yes_res_{rowid}"):
                    delete_result(rowid)
                    st.session_state[f"confirm_delete_res_{rowid}"] = False
                    safe_rerun()
                if c2.button("No", key=f"no_res_{rowid}"):
                    st.session_state[f"confirm_delete_res_{rowid}"] = False
                    safe_rerun()
    else:
        st.info("No results found yet.")


# ══════════════════════════════════════════════════════════════════════════════
#   AI ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "AI Analysis":
    st.subheader("🤖 AI-Powered Quiz Analysis")
    st.markdown("Generate deep AI insights from your quiz performance over a selected period.")

    results = get_results()

    if not results:
        st.warning("No quiz results found. Take some quizzes first!")
    else:
        # ── Period selector ──────────────────────────────────────────────────
        analysis_mode = st.radio("Analysis Period", ["Single Month", "Date Range"], horizontal=True)

        today = date.today()
        if analysis_mode == "Single Month":
            col1, col2 = st.columns(2)
            sel_year  = col1.number_input("Year",  min_value=2023, max_value=today.year, value=today.year)
            sel_month = col2.number_input("Month", min_value=1,    max_value=12,         value=today.month)
            from_dt = date(int(sel_year), int(sel_month), 1)
            if sel_month == 12:
                to_dt = date(int(sel_year) + 1, 1, 1) - timedelta(days=1)
            else:
                to_dt = date(int(sel_year), int(sel_month) + 1, 1) - timedelta(days=1)
            period_label = f"{from_dt.strftime('%B %Y')}"
        else:
            col1, col2 = st.columns(2)
            from_dt = col1.date_input("From Date", value=today - timedelta(days=30))
            to_dt   = col2.date_input("To Date",   value=today)
            period_label = f"{from_dt} to {to_dt}"

        st.markdown(f"**Period:** `{period_label}`")

        # ── Generate analysis ────────────────────────────────────────────────
        if st.button("🔍 Generate AI Analysis", type="primary"):
            # Summarise results (we don't have dates on results table, so use all)
            total_tests    = len(results)
            total_correct  = sum(r[4] for r in results)
            total_wrong    = sum(r[5] for r in results)
            total_attempted = sum(r[3] for r in results)
            avg_accuracy   = (total_correct / total_attempted * 100) if total_attempted else 0

            # Also pull test papers for the period
            test_papers = get_test_papers()
            period_papers = [
                tp for tp in test_papers
                if tp[2] and from_dt <= tp[2] <= to_dt
            ]

            paper_summary = ""
            if period_papers:
                for tp in period_papers:
                    tp_id, tp_name, tp_date, tp_total, tp_att, tp_natt, tp_gc, tp_gi, tp_care, tp_created = tp
                    paper_summary += (
                        f"\n- Test: {tp_name} ({tp_date}): "
                        f"Total={tp_total}, Attempted={tp_att}, "
                        f"Guessed Correct={tp_gc}, Guessed Incorrect={tp_gi}, "
                        f"Carelessness Notes: {tp_care}"
                    )

            prompt = f"""You are an expert UPSC preparation coach. Analyze the following quiz performance data for the period {period_label}.

QUIZ RESULTS SUMMARY:
- Total tests taken: {total_tests}
- Total questions attempted: {total_attempted}
- Total correct answers: {total_correct}
- Total wrong answers: {total_wrong}
- Average accuracy: {avg_accuracy:.1f}%

INDIVIDUAL RESULTS:
{chr(10).join([f"Test {r[1]}: Total={r[2]}, Attempted={r[3]}, Correct={r[4]}, Wrong={r[5]}, Accuracy={r[6]:.1f}%, Marks={r[7]}" for r in results])}

TEST PAPER ANALYSIS FOR THIS PERIOD:
{paper_summary if paper_summary else "No test papers recorded for this period."}

Please provide:
1. **Performance Overview** – Key metrics and what they mean
2. **Mistake Pattern Analysis** – What type of mistakes are being made
3. **Subject-wise Insights** – Based on test names and patterns
4. **Carelessness & Silly Mistakes** – Analysis of recurring errors from test papers
5. **Improvement Strategy** – Specific, actionable steps for the next 30 days
6. **Danger Zones** – Topics/areas that need urgent attention
7. **Motivational Assessment** – Honest, encouraging feedback

Be specific, thorough, and UPSC-focused."""

            with st.spinner("🤖 Generating deep analysis..."):
                analysis = ask_llm(prompt)

            st.markdown("---")
            st.markdown("### 📊 AI Analysis Report")
            st.markdown(analysis)

            # Save report
            report_id = save_ai_report("Quiz Analysis", period_label, analysis)
            if report_id:
                st.success(f"✅ Analysis saved to database (ID: {report_id})")
            else:
                st.warning("Could not save report to database.")

    # ── Saved AI Reports ──────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📁 Saved AI Analysis Reports")
    reports = get_ai_reports()

    if reports:
        report_options = [f"[{r[2]}] {r[1]} – {r[4].strftime('%d %b %Y %H:%M') if hasattr(r[4], 'strftime') else r[4]}" for r in reports]
        sel_report = st.selectbox("Select saved report", [""] + report_options, key="sel_report")

        if sel_report:
            ridx = report_options.index(sel_report)
            report = reports[ridx]
            report_id = report[0]
            report_content = report[3]

            # Close (X) button
            col_h, col_x = st.columns([20, 1])
            with col_x:
                st.button("✕", key=f"x_report_{report_id}", help="Close", on_click=clear_state, args=("sel_report",))
            with col_h:
                st.markdown(f"**Period:** {report[2]}")

            st.markdown(report_content)

            # Delete report
            if st.button("🗑️ Delete This Report", key=f"del_report_{report_id}"):
                st.session_state[f"confirm_del_report_{report_id}"] = True
                safe_rerun()
            if st.session_state.get(f"confirm_del_report_{report_id}"):
                st.warning("Permanently delete this AI report?")
                c1, c2 = st.columns(2)
                if c1.button("Yes, Delete", key=f"yes_report_{report_id}"):
                    delete_ai_report(report_id)
                    st.session_state[f"confirm_del_report_{report_id}"] = False
                    safe_rerun()
                if c2.button("Cancel", key=f"no_report_{report_id}"):
                    st.session_state[f"confirm_del_report_{report_id}"] = False
                    safe_rerun()
    else:
        st.info("No saved AI reports yet. Generate an analysis above.")


# ══════════════════════════════════════════════════════════════════════════════
#   TEST PAPER ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Test Paper Analysis":
    st.subheader("📝 Test Paper Analysis")

    # ── INPUT FORM ────────────────────────────────────────────────────────────
    with st.expander("➕ Add New Test Entry", expanded=True):
        with st.form("test_paper_form", clear_on_submit=True):
            st.markdown("#### 📋 Test Details")
            col1, col2 = st.columns(2)
            test_name = col1.text_input("Test Name *", placeholder="e.g. UPSC Prelims Mock 5")
            test_date_inp = col2.date_input("Test Date", value=date.today())

            st.markdown("#### 📊 Question Statistics")
            c1, c2, c3 = st.columns(3)
            total_q   = c1.number_input("Total Questions",   min_value=0, value=100)
            attempted = c2.number_input("Attempted",         min_value=0, value=80)
            not_att   = c3.number_input("Not Attempted",     min_value=0, value=20)

            st.markdown("#### 🎲 Guessed Questions")
            cg1, cg2 = st.columns(2)
            guessed_c = cg1.number_input("Guessed – Correct",   min_value=0, value=0)
            guessed_i = cg2.number_input("Guessed – Incorrect", min_value=0, value=0)

            st.markdown("#### ⚠️ Carelessness / Silly Mistakes")
            st.caption("Enter each mistake on a new line, numbered (e.g. 1. Confused Article 72 with 73)")
            careless_notes = st.text_area(
                "Carelessness Notes",
                height=150,
                placeholder="1. Confused President's rule articles\n2. Wrong answer in SDG targets\n3. Missed reading 'NOT' in option"
            )

            submitted = st.form_submit_button("✅ Save Test Entry", type="primary")
            if submitted:
                if not test_name.strip():
                    st.error("Test Name is required!")
                else:
                    new_id = save_test_paper(
                        test_name.strip(), test_date_inp,
                        int(total_q), int(attempted), int(not_att),
                        int(guessed_c), int(guessed_i),
                        careless_notes.strip()
                    )
                    if new_id:
                        st.success(f"✅ Test '{test_name}' saved successfully! (ID: {new_id})")
                        safe_rerun()
                    else:
                        st.error("Failed to save test entry. Check DB connection.")

    # ── TEST PAPER TABLE ──────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📊 Test Analysis History")

    papers = get_test_papers()

    # ── Carelessness popup state ───────────────────────────────────────────────
    if "care_popup_id" not in st.session_state:
        st.session_state["care_popup_id"] = None
    if "care_ai_expanded" not in st.session_state:
        st.session_state["care_ai_expanded"] = {}

    # Close popup if ✕ triggered
    if st.session_state.get("close_care_popup"):
        st.session_state["care_popup_id"] = None
        st.session_state["close_care_popup"] = False

    if papers:
        # ── Build HTML table ──────────────────────────────────────────────────
        table_rows = ""
        for tp in papers:
            tp_id, tp_name, tp_date, tp_total, tp_att, tp_natt, tp_gc, tp_gi, tp_care, tp_created = tp

            total_guessed    = (tp_gc or 0) + (tp_gi or 0)
            total_correct    = (tp_att - (tp_gi or 0)) + (tp_gc or 0)  # attempted correct + guessed correct
            # Actually: correct = attempted_correct + guessed_correct
            # We don't store attempted_correct separately, so:
            # wrong = attempted - guessed_correct (only guessed_incorrect + truly wrong among non-guessed)
            # Simplify: total correct = total_att - total_wrong; we know guessed_incorrect → wrong
            # Better formula given inputs:
            # wrong = (guessed_incorrect) + (attempted - total_guessed - correct_in_non_guessed)
            # Since we don't have "correct in non-guessed" separately, use overall:
            # total_correct_all = guessed_correct + (attempted - total_guessed - wrong_non_guessed)
            # We'll derive from: total attempted base = attempted (includes guessed)
            # wrong = attempted - correct; but correct = guessed_correct + attempted_correct_non_guessed
            # Since we don't store attempted_correct_non_guessed, treat the displayed metric as:
            # total_correct = (attempted - tp_gi) where attempted includes guessed attempts
            # This simplifies to: correct = attempted - wrong_guessed = attempted - tp_gi
            # But that ignores non-guessed wrong... We'll use the standard formula:
            # correct = attempted - (tp_gi + non_guessed_wrong) — not enough info
            # So display: Known Correct = tp_gc (guessed correct), Wrong = tp_gi (guessed wrong)
            # For summary show what we have:
            total_guessed    = (tp_gc or 0) + (tp_gi or 0)
            # accuracy_total: correct / (attempted + guessed) — but attempted already may include guessed
            # We'll treat: total_correct as guessed_correct (what we can compute), accuracy_guessed
            guessed_acc = round(tp_gc / total_guessed * 100, 1) if total_guessed > 0 else 0
            # total accuracy = (all correct) / attempted -- but we only know guessed correct
            # Show what we can: guessed acc, and overall if we treat attempted as base
            overall_acc = round(tp_gc / tp_att * 100, 1) if tp_att > 0 else 0
            attempted_non_g = (tp_att or 0) - total_guessed
            attempted_acc = round(((tp_att or 0) - total_guessed - (tp_gi or 0) + (tp_gc or 0)) / attempted_non_g * 100, 1) if attempted_non_g > 0 else 0

            def acc_color(v):
                if v >= 70: return "#34d399"
                if v >= 50: return "#fbbf24"
                return "#f87171"

            care_btn = f'<button class="read-more-btn" onclick="window.location.href=\'?care_popup={tp_id}\'">Read More</button>' if tp_care else "—"

            table_rows += f"""
            <tr>
                <td>{tp_name}</td>
                <td>{tp_date}</td>
                <td>{tp_total}</td>
                <td>{tp_att}</td>
                <td>{tp_natt}</td>
                <td>{total_guessed}</td>
                <td>{tp_gc}</td>
                <td>{tp_gi}</td>
                <td style="color:{acc_color(overall_acc)}">{overall_acc}%</td>
                <td style="color:{acc_color(attempted_acc)}">{attempted_acc}%</td>
                <td style="color:{acc_color(guessed_acc)}">{guessed_acc}%</td>
                <td>{care_btn}</td>
            </tr>"""

        st.markdown(f"""
        <div style="overflow-x:auto;">
        <table class="test-table">
            <thead>
                <tr>
                    <th rowspan="2">Test Name</th>
                    <th rowspan="2">Date</th>
                    <th rowspan="2">Total Q</th>
                    <th rowspan="2">Attempted</th>
                    <th rowspan="2">Not Attempted</th>
                    <th colspan="3">Guessed</th>
                    <th colspan="3">Accuracy</th>
                    <th rowspan="2">Carelessness</th>
                </tr>
                <tr>
                    <th>Total</th><th>✅ Correct</th><th>❌ Incorrect</th>
                    <th>Overall %</th><th>Attempted %</th><th>Guessed %</th>
                </tr>
            </thead>
            <tbody>
                {table_rows}
            </tbody>
        </table>
        </div>
        """, unsafe_allow_html=True)

        # ── Carelessness Popup (Streamlit-side) ───────────────────────────────
        st.markdown("---")
        st.markdown("#### ⚠️ Carelessness Notes Viewer")
        st.caption("Select a test to view its carelessness notes and get AI analysis per mistake.")

        paper_opts = [f"{tp[1]} ({tp[2]})" for tp in papers if tp[8]]
        sel_care = st.selectbox("Select Test for Carelessness Review", [""] + paper_opts, key="sel_care_test")

        if sel_care:
            cidx = paper_opts.index(sel_care)
            # find the matching paper (only those with care notes)
            care_papers = [tp for tp in papers if tp[8]]
            chosen_tp = care_papers[cidx]
            tp_id   = chosen_tp[0]
            tp_name = chosen_tp[1]
            notes_raw = chosen_tp[8]

            # Close button
            col_t, col_x = st.columns([20, 1])
            with col_x:
                st.button("✕", key=f"x_care_{tp_id}", help="Close", on_click=clear_state, args=("sel_care_test",))
            with col_t:
                st.markdown(f"**📋 Carelessness Notes for: {tp_name}**")

            # Parse numbered points
            lines = notes_raw.strip().split("\n")
            points = []
            current = ""
            for line in lines:
                stripped = line.strip()
                if stripped and stripped[0].isdigit() and "." in stripped[:3]:
                    if current:
                        points.append(current.strip())
                    current = stripped
                else:
                    current += " " + stripped
            if current:
                points.append(current.strip())

            if not points:
                points = [notes_raw.strip()]

            for pi, point in enumerate(points):
                with st.container():
                    col_point, col_ai = st.columns([5, 1])
                    with col_point:
                        with st.expander(f"🔸 {point}", expanded=False):
                            st.markdown(f"**Your Note:**\n> {point}")

                            ai_key = f"ai_analysis_{tp_id}_{pi}"
                            if ai_key in st.session_state:
                                st.markdown("---")
                                st.markdown("#### 🤖 AI Topic Analysis")
                                st.markdown(st.session_state[ai_key])
                            else:
                                if st.button(f"🤖 Get AI Analysis", key=f"btn_ai_{tp_id}_{pi}"):
                                    prompt = f"""You are an expert UPSC coach. A student made the following mistake in an exam:

"{point}"

Please provide:
1. **What Went Wrong** – Explain the likely knowledge gap or confusion
2. **The Correct Concept** – Explain the right answer/concept clearly
3. **UPSC Relevance** – How important is this topic for UPSC Prelims/Mains
4. **Memory Trick** – A mnemonic or trick to remember the correct answer
5. **Related Topics** – Other connected topics to study to avoid similar mistakes

Keep the analysis concise, specific, and UPSC-exam-focused."""
                                    with st.spinner("Analysing mistake..."):
                                        ai_response = ask_llm(prompt)
                                    st.session_state[ai_key] = ai_response
                                    safe_rerun()

        # ── Delete test paper ────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("### 🗑️ Remove Test Entry")
        del_opts = [f"{tp[1]} ({tp[2]}) – ID:{tp[0]}" for tp in papers]
        sel_del = st.selectbox("Select test to remove", [""] + del_opts, key="sel_del_test")

        if sel_del:
            didx = del_opts.index(sel_del) - 1
            del_id = papers[didx][0]

            if st.button("Remove Test Entry", key=f"rm_test_{del_id}"):
                st.session_state[f"confirm_del_test_{del_id}"] = True
                safe_rerun()
            if st.session_state.get(f"confirm_del_test_{del_id}"):
                st.warning("Permanently delete this test paper entry?")
                c1, c2 = st.columns(2)
                if c1.button("Yes, Delete", key=f"yes_test_{del_id}"):
                    delete_test_paper(del_id)
                    st.session_state[f"confirm_del_test_{del_id}"] = False
                    safe_rerun()
                if c2.button("Cancel", key=f"no_test_{del_id}"):
                    st.session_state[f"confirm_del_test_{del_id}"] = False
                    safe_rerun()
    else:
        st.info("No test papers recorded yet. Add your first test entry above!")