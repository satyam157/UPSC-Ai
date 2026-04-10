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
from llm import ask_llm, ask_llm_vision
import base64
from quiz_parser import parse_quiz
from quiz_engine import evaluate
from pdf_utils import generate_pdf
from pyq_engine import predict, generate_prelims_pyqs, generate_mains_pyqs, generate_full_pyq_session

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

# ── Sidebar Collapse Toggle ───────────────────────────────────────────────────
col_logout, col_collapse = st.sidebar.columns([1, 0.5])
with col_logout:
    if st.button("Logout", use_container_width=True, key="btn_logout_sidebar"):
        logout()
with col_collapse:
    if st.button("⬅️", use_container_width=True, key="btn_collapse_sidebar", help="Minimize sidebar"):
        st.markdown("""
        <style>
            [data-testid="stSidebar"] {
                max-width: 80px;
            }
            [data-testid="stSidebar"] > div:first-child {
                overflow: hidden;
            }
        </style>
        """, unsafe_allow_html=True)

page = st.sidebar.radio("Navigate", [
    "Current Affairs",
    "CA Quiz",
    "Practice",
    "PDF Quiz",
    "Results",
    "AI Analysis",
    "Test Paper Analysis"
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

    # ── News Feed ─────────────────────────────────────────────────────────────
    st.markdown("---")
    news_data = get_news()
    filter_words = [w.lower() for _, w in get_ca_filters()]

    def is_filtered(title):
        tl = title.lower()
        return any(fw in tl for fw in filter_words)

    # ── Initialize news summary state ─────────────────────────────────────────
    if "news_summaries" not in st.session_state:
        st.session_state["news_summaries"] = {}  # key: title, value: summary

    if news_data:
        # Deduplicate by title (keep the most recent entry per title)
        seen_titles = set()
        unique_news = []
        for n in news_data:
            if n[0] not in seen_titles:
                seen_titles.add(n[0])
                unique_news.append(n)

        dates = sorted(list(set(n[2] for n in unique_news)), reverse=True)
        for d in dates:
            day_items = [n for n in unique_news if n[2] == d and not is_filtered(n[0])]
            if day_items:
                with st.expander(f"📅 Current Affairs for {d} ({len(day_items)} items)"):
                    for idx, n in enumerate(day_items):
                        title   = n[0]
                        content = n[1] if len(n) > 1 else ""
                        url     = n[3] if len(n) > 3 else ""
                        
                        # Unique key for this news item
                        news_key = f"{d}_{idx}_{title[:30]}"
                        expanded_key = f"news_expanded_{news_key}"
                        
                        # News item header with button
                        col_title, col_btn = st.columns([8, 1])
                        with col_title:
                            st.markdown(f"**• {title}**")
                        with col_btn:
                            if st.button(
                                "🔍" if not st.session_state.get(expanded_key, False) else "✕",
                                key=f"btn_{news_key}",
                                help="View summary" if not st.session_state.get(expanded_key, False) else "Close summary"
                            ):
                                st.session_state[expanded_key] = not st.session_state.get(expanded_key, False)
                                safe_rerun()
                        
                        # ── Display Summary if Expanded ────────────────
                        if st.session_state.get(expanded_key, False):
                            with st.container():
                                st.markdown(
                                    f'<div style="background:#1e1e2e;border:2px solid #7c3aed;border-radius:12px;'
                                    f'padding:18px 20px;margin:10px 0;color:#e2e8f0;">'
                                    f'<p style="color:#a78bfa;margin:0 0 8px 0;font-size:13px;font-weight:600;'
                                    f'text-transform:uppercase;letter-spacing:0.5px;">📊 UPSC Analysis</p>'
                                    f'</div>',
                                    unsafe_allow_html=True
                                )
                                
                                # ── Generate or retrieve summary ────────
                                if title not in st.session_state["news_summaries"]:
                                    with st.spinner("🤖 Generating UPSC-focused analysis..."):
                                        raw = content.strip() if content and content.strip() else title
                                        prompt = f"""You are an expert UPSC coach and current affairs analyst. Analyse the following news article and present a structured UPSC-focused summary using the exact format below. Be concise, factual, and exam-relevant.

---
**NEWS TITLE:** {title}

**CONTENT:** {raw}
---

Provide the analysis in this exact structured format:

## 📌 One-Liner (What happened — one crisp sentence)

## 🏛️ Relevant Articles / Constitutional Provisions / Acts
- List any relevant Articles of the Constitution, Acts of Parliament, International agreements, or Government schemes directly related to this news.

## 📖 Background
- Key historical context or background that a UPSC aspirant must know about this topic.
- Include GS Paper relevance (GS1 / GS2 / GS3 / GS4 / Mains Essay).

## ⭐ Important Points (Key Facts for Prelims & Mains)
- Bullet-point the most important factual information, dates, names, statistics, or policy details.
- Include topics this connects to (e.g., federalism, environment, economy, governance).

## ⚠️ Problems / Challenges
- What are the core issues, challenges, or concerns highlighted by this news?

## ✅ Solutions / Government Response / Way Forward
- What steps have been taken or recommended? Policy measures, government schemes, expert recommendations.

## 🔚 Conclusion
- One crisp closing statement on why this matters for India's development or UPSC perspective.

Be factual, structured, and UPSC Prelims + Mains focused. Avoid unnecessary padding."""
                                        summary = ask_llm(prompt)
                                        st.session_state["news_summaries"][title] = summary
                                        
                                        # ── Save summary to database ────────
                                        summary_content = f"**TITLE:** {title}\n\n{summary}"
                                        if url:
                                            summary_content += f"\n\n**SOURCE:** {url}"
                                        save_item("CA News Summary", summary_content)
                                
                                # ── Display the summary ────────────────
                                st.markdown(st.session_state["news_summaries"][title])
                                
                                # ── Show source URL ────────────────────
                                if url:
                                    st.markdown(
                                        f'<div style="margin-top:12px;padding:10px 14px;background:#16162a;'
                                        f'border-radius:8px;border:1px solid #312e81;">'
                                        f'🔗 <strong>Source:</strong> <a href="{url}" target="_blank" style="color:#a78bfa;word-break:break-all;">'
                                        f'{url[:80]}...</a></div>',
                                        unsafe_allow_html=True
                                    )
                            
                            st.markdown("---")
    else:
        st.info("No Current Affairs data available. Please refresh to fetch current affairs.")

    # ── Bottom Controls: Retention Rules + Manage Filters ──────────────────────
    st.markdown("---")
    username = st.session_state["username"]
    current_retention = get_retention(username)
    
    col_ret_label, col_ret_input, col_ret_apply, col_filter = st.columns([1.2, 0.8, 0.9, 1.1])
    
    with col_ret_label:
        st.markdown('<p style="text-align:right; margin-top:10px; font-weight:600; color:#c4b5fd; font-size:13px;">Retention:</p>', unsafe_allow_html=True)
    with col_ret_input:
        retention_days = st.number_input("Days", min_value=1, max_value=365, value=current_retention, label_visibility="collapsed")
        if retention_days != current_retention:
            set_retention(username, retention_days)
            st.toast(f"⚙️ Retention set to {retention_days} days")
    with col_ret_apply:
        if st.button("🧹 Apply", use_container_width=True, help="Delete data older than retention period"):
            clean_old(days=retention_days)
            st.success(f"🗑️ Cleaned data older than {retention_days} days!")
    
    with col_filter:
        if st.button("🔧 Manage Filters", use_container_width=True, key="btn_manage_filters_bottom"):
            st.session_state["show_filter_panel"] = not st.session_state.get("show_filter_panel", False)
            safe_rerun()
    
    # ── Filter Management Panel (Compact) ─────────────────────────────────────
    if st.session_state.get("show_filter_panel", False):
        st.markdown(
            f'<div style="background:#16162a;border:1px solid #312e81;border-radius:10px;'
            f'padding:14px 16px;margin-top:12px;">'
            f'<p style="color:#34d399;margin:0 0 8px 0;font-weight:600;font-size:13px;"><span style="color:#34d399;">⭐</span> Hide headlines with these words:</p>',
            unsafe_allow_html=True
        )
        
        existing_filters = get_ca_filters()
        if existing_filters:
            tags_html = ""
            for fid, word in existing_filters:
                tags_html += f'<span class="filter-tag">{word}<span class="tag-x" title="Remove" onclick="alert(\'Use remove button below\')" style="cursor:pointer;">✕</span></span>'
            st.markdown(f'<div>{tags_html}</div>', unsafe_allow_html=True)
            
            col_rm, col_add = st.columns(2)
            with col_rm:
                filter_options = [f"{word} (id:{fid})" for fid, word in existing_filters]
                to_remove = st.selectbox("Remove:", [""] + filter_options, key="rm_filter_compact", label_visibility="collapsed")
                if to_remove and st.button("Remove", key="btn_rm_filter_compact", use_container_width=True):
                    fid = int(to_remove.split("id:")[1].rstrip(")"))
                    delete_ca_filter(fid)
                    st.success("Removed!")
                    safe_rerun()
            with col_add:
                new_word = st.text_input("Add word:", label_visibility="collapsed", key="new_filter_compact", placeholder="e.g., cricket")
                if st.button("➕ Add", key="btn_add_filter_compact", use_container_width=True):
                    if new_word.strip():
                        add_ca_filter(new_word.strip())
                        st.success(f"Added!")
                        safe_rerun()
        else:
            st.write("No filter words added yet.")
            new_word = st.text_input("Add filter word:", key="new_filter_panel", placeholder="e.g., cricket")
            if st.button("➕ Add Filter", key="btn_add_first_filter", use_container_width=True):
                if new_word.strip():
                    add_ca_filter(new_word.strip())
                    st.success(f"Added filter: '{new_word.strip()}'")
                    safe_rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)


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
elif page == "Practice":
    st.subheader("📜 PYQ Practice — Prelims & Mains")
    st.caption("Generate Previous Year Questions linked to today's current affairs. Prelims as a quiz, Mains with model answers.")

    # ── Session state init ────────────────────────────────────────────────────
    if "pyq_prelims" not in st.session_state:
        st.session_state["pyq_prelims"] = None
    if "pyq_mains" not in st.session_state:
        st.session_state["pyq_mains"] = None
    if "pyq_submitted" not in st.session_state:
        st.session_state["pyq_submitted"] = False
    if "pyq_user_answers" not in st.session_state:
        st.session_state["pyq_user_answers"] = {}

    # ── Generate button ───────────────────────────────────────────────────────
    if st.button("🚀 Generate PYQ Practice Set", type="primary", use_container_width=True):
        data_news = [x[0] for x in get_news()]
        if not data_news:
            st.warning("No current affairs data. Please refresh the feed first.")
        else:
            with st.spinner("🤖 AI is analyzing current affairs and predicted PYQs..."):
                result = generate_full_pyq_session(data_news)
                prelims = result.get("prelims", [])
                mains = result.get("mains", [])

            if not prelims and not mains:
                st.error("AI failed to generate questions. This might be an API limit. Try again in a moment.")
            else:
                st.session_state["pyq_prelims"] = prelims
                st.session_state["pyq_mains"] = mains
                st.session_state["pyq_submitted"] = False
                st.session_state["pyq_user_answers"] = {}

                # Save for history
                save_content = f"Session Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                save_content += f"=== PRELIMS ({len(prelims)}) ===\n"
                for i, pq in enumerate(prelims):
                    save_content += f"Q{i+1}. [{pq.get('year','')}] {pq['question']}\nAns: {pq.get('correct_answer','')}\n\n"
                save_content += f"=== MAINS ({len(mains)}) ===\n"
                for i, mq in enumerate(mains):
                    save_content += f"Q{i+1}. [{mq.get('year','')} | {mq.get('paper','')}] {mq['question']}\n\n"
                
                save_item("Practice", save_content)
                st.success(f"Generated {len(prelims)} Prelims and {len(mains)} Mains questions!")
                safe_rerun()

    # ── TABS: Prelims | Mains ─────────────────────────────────────────────────
    tab_prelims, tab_mains, tab_history = st.tabs(["📝 Prelims PYQ Quiz", "✍️ Mains PYQ Practice", "📂 History"])

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #   PRELIMS TAB
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    with tab_prelims:
        prelims_data = st.session_state["pyq_prelims"]

        if prelims_data:
            st.markdown(f"**{len(prelims_data)} questions generated** — Answer all, then submit to see explanations.")
            st.markdown("---")

            if not st.session_state["pyq_submitted"]:
                # ── Quiz Mode (answers hidden) ────────────────────────────────
                st.markdown("### Answer the following questions:")
                with st.form("pyq_prelims_form"):
                    for i, pq in enumerate(prelims_data):
                        year_badge = pq.get("year", "")
                        badge_color = "#34d399" if year_badge != "Predicted" else "#fbbf24"
                        
                        st.markdown(
                            f'<div style="background:#16162a;border-left:3px solid {badge_color};'
                            f'padding:12px 14px;margin:12px 0 8px 0;border-radius:4px;">'
                            f'<div style="margin-bottom:6px;">'
                            f'<span style="background:{badge_color};color:#000;padding:2px 8px;'
                            f'border-radius:6px;font-size:11px;font-weight:600;">{year_badge}</span>'
                            f'</div>'
                            f'<p style="color:#e2e8f0;margin:0;font-size:15px;font-weight:600;">Q{i+1}. {pq["question"]}</p>'
                            f'</div>',
                            unsafe_allow_html=True
                        )
                        
                        opts = pq["options"]
                        option_labels = []
                        for letter in ["A", "B", "C", "D"]:
                            opt_text = opts.get(letter, "")
                            # Truncate long options for display
                            if len(opt_text) > 80:
                                opt_text = opt_text[:77] + "..."
                            option_labels.append(f"{letter}) {opt_text}")
                        
                        sel = st.radio(
                            "Select your answer:",
                            option_labels,
                            key=f"pyq_ans_{i}",
                            index=None,
                            label_visibility="collapsed"
                        )
                        st.divider()

                    submitted = st.form_submit_button("📩 Submit Quiz", type="primary", use_container_width=True)
                    if submitted:
                        answers = {}
                        for i in range(len(prelims_data)):
                            sel = st.session_state.get(f"pyq_ans_{i}")
                            if sel:
                                answers[i] = sel[0]  # Extract letter (A/B/C/D)
                            else:
                                answers[i] = None
                        st.session_state["pyq_user_answers"] = answers
                        st.session_state["pyq_submitted"] = True
                        safe_rerun()

            else:
                # ── Review Mode (answers + explanations shown) ────────────────
                user_answers = st.session_state["pyq_user_answers"]
                total = len(prelims_data)
                correct_count = 0
                attempted_count = 0

                for i, pq in enumerate(prelims_data):
                    user_ans = user_answers.get(i)
                    correct_ans = pq["correct_answer"]
                    year_badge = pq.get("year", "")

                    is_correct = user_ans == correct_ans
                    if user_ans:
                        attempted_count += 1
                    if is_correct:
                        correct_count += 1

                    # Status icon
                    if user_ans is None:
                        status_icon = "⚪"
                        status_text = "Not Attempted"
                        border_color = "#6b7280"
                    elif is_correct:
                        status_icon = "✅"
                        status_text = "Correct"
                        border_color = "#34d399"
                    else:
                        status_icon = "❌"
                        status_text = f"Wrong (You: {user_ans})"
                        border_color = "#f87171"

                    badge_color = "#34d399" if year_badge != "Predicted" else "#fbbf24"

                    st.markdown(
                        f'<div style="border-left:4px solid {border_color}; padding:12px 16px; '
                        f'margin-bottom:8px; background:#16162a; border-radius:8px;">'
                        f'<span style="background:{badge_color};color:#000;padding:2px 10px;'
                        f'border-radius:10px;font-size:12px;font-weight:600;margin-right:8px;">{year_badge}</span>'
                        f'{status_icon} {status_text}'
                        f'</div>',
                        unsafe_allow_html=True
                    )

                    with st.expander(f"Q{i+1}. {pq['question'][:100]}...", expanded=False):
                        st.markdown(f"**Full Question:** {pq['question']}")
                        st.markdown("")

                        opts = pq["options"]
                        opt_expl = pq.get("option_explanations", {})

                        for letter in ["A", "B", "C", "D"]:
                            opt_text = opts.get(letter, "")
                            expl = opt_expl.get(letter, "")

                            if letter == correct_ans:
                                icon = "✅"
                                bg = "#0f3d2c"
                                bdr = "#34d399"
                                text_color = "#86efac"
                            elif letter == user_ans and letter != correct_ans:
                                icon = "❌"
                                bg = "#3d1519"
                                bdr = "#f87171"
                                text_color = "#fca5a5"
                            else:
                                icon = "⚪"
                                bg = "#1a1a2e"
                                bdr = "#374151"
                                text_color = "#d1d5db"

                            st.markdown(
                                f'<div style="background:{bg}; border:2px solid {bdr}; border-radius:10px; '
                                f'padding:14px 16px; margin:10px 0;">'
                                f'<div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px;">'
                                f'<div style="flex:1;">'
                                f'<p style="color:{text_color}; font-weight:600; font-size:15px; margin:0 0 6px 0;">{icon} <strong>{letter})</strong> {opt_text}</p>'
                                f'<p style="color:#cbd5e1; font-size:13px; margin:0; line-height:1.5;">{expl}</p>'
                                f'</div>'
                                f'</div>'
                                f'</div>',
                                unsafe_allow_html=True
                            )

                        overall_expl = pq.get("explanation", "")
                        if overall_expl:
                            st.markdown(
                                f'<div style="background:#1a2236; border-left:4px solid #818cf8; '
                                f'padding:14px 18px; border-radius:4px 10px 10px 4px; margin-top:10px;">'
                                f'<h5 style="color:#818cf8; margin:0 0 6px 0; font-size:14px; text-transform:uppercase; letter-spacing:0.5px;">📖 Detailed Analysis</h5>'
                                f'<p style="color:#e2e8f0; font-size:14px; margin:0; line-height:1.5;">{overall_expl}</p>'
                                f'</div>',
                                unsafe_allow_html=True
                            )
                        
                        st.markdown(
                            f'<div style="margin-top:12px; font-size:13px; color:#94a3b8; '
                            f'background:#16162a; padding:12px; border-radius:6px;">'
                            f'🏷️ <strong>Year:</strong> {year_badge} | '
                            f'🎯 <strong>Correct Answer:</strong> <span style="color:#34d399; font-weight:700;">{correct_ans}</span>'
                            f'</div>',
                            unsafe_allow_html=True
                        )

                    st.markdown("---")

                # ── Score Summary ─────────────────────────────────────────────
                wrong_count = attempted_count - correct_count
                accuracy = round(correct_count / attempted_count * 100, 1) if attempted_count > 0 else 0
                marks = round(correct_count * 2 - wrong_count * 0.66, 2)
                acc_col = "#34d399" if accuracy >= 70 else ("#fbbf24" if accuracy >= 50 else "#f87171")

                st.markdown(
                    f'<div style="background: linear-gradient(135deg, #1e1e3f 0%, #111122 100%); '
                    f'border: 1px solid #7c3aed; border-radius: 16px; padding: 24px; '
                    f'margin: 20px 0; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);">'
                    f'<h3 style="color:#ffffff; margin-top:0; font-size:20px; border-bottom:1px solid #312e81; padding-bottom:12px;">📊 Result Performance Score</h3>'
                    f'<div style="display:grid; grid-template-columns: 1fr 1fr; gap:16px; margin-top:16px;">'
                    f'<div>'
                    f'<p style="color:#94a3b8; font-size:12px; margin:0; text-transform:uppercase;">Accuracy</p>'
                    f'<p style="color:{acc_col}; font-size:32px; font-weight:800; margin:0;">{accuracy}%</p>'
                    f'</div>'
                    f'<div>'
                    f'<p style="color:#94a3b8; font-size:12px; margin:0; text-transform:uppercase;">Total Marks</p>'
                    f'<p style="color:#ffffff; font-size:32px; font-weight:800; margin:0;">{marks}</p>'
                    f'</div>'
                    f'</div>'
                    f'<div style="margin-top:20px; font-size:14px; border-top:1px solid #312e81; padding-top:16px;">'
                    f'<span style="color:#cbd5e1; margin-right:20px;">Questions: <strong>{total}</strong></span>'
                    f'<span style="color:#34d399; margin-right:20px;">Correct: <strong>{correct_count}</strong></span>'
                    f'<span style="color:#f87171;">Wrong: <strong>{wrong_count}</strong></span>'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )

                # ── Retry button ──────────────────────────────────────────────
                if st.button("🔄 Retry / Generate New Set", key="pyq_retry"):
                    st.session_state["pyq_prelims"] = None
                    st.session_state["pyq_submitted"] = False
                    st.session_state["pyq_user_answers"] = {}
                    safe_rerun()

                # Save result
                save_result(("PYQ_Prelims", total, attempted_count, correct_count, wrong_count, accuracy, marks))

        else:
            st.info("Click **Generate PYQ Practice Set** above to start.")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #   MAINS TAB
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    with tab_mains:
        mains_data = st.session_state["pyq_mains"]

        if mains_data:
            st.markdown(f"**{len(mains_data)} Mains questions generated** — Click *Show Model Answer* to reveal the ideal answer, or upload your handwritten answer for AI evaluation.")
            st.markdown("---")

            for i, mq in enumerate(mains_data):
                year_badge = mq.get("year", "")
                paper_badge = mq.get("paper", "")
                badge_color = "#34d399" if year_badge != "Predicted" else "#fbbf24"
                paper_color = "#818cf8"

                st.markdown(
                    f'<div style="background:#16162a;border:1px solid #312e81;border-radius:12px;'
                    f'padding:18px 22px;margin-bottom:6px;">'
                    f'<div style="margin-bottom:8px;">'
                    f'<span style="background:{badge_color};color:#000;padding:2px 10px;'
                    f'border-radius:10px;font-size:12px;font-weight:600;margin-right:6px;">{year_badge}</span>'
                    f'<span style="background:#2d1b6b;color:{paper_color};padding:2px 10px;'
                    f'border-radius:10px;font-size:12px;font-weight:600;">{paper_badge}</span>'
                    f'</div>'
                    f'<p style="color:#e2e8f0;font-size:15px;font-weight:500;margin:0;">'
                    f'<strong>Q{i+1}.</strong> {mq["question"]}</p>'
                    f'</div>',
                    unsafe_allow_html=True
                )

                # ── Action buttons row ────────────────────────────────────────
                col_ma, col_upload = st.columns(2)

                # Show Model Answer toggle
                ma_key = f"show_ma_{i}"
                with col_ma:
                    if st.button(
                        f"📖 Show Model Answer" if not st.session_state.get(ma_key) else f"🔒 Hide Model Answer",
                        key=f"btn_ma_{i}", use_container_width=True
                    ):
                        st.session_state[ma_key] = not st.session_state.get(ma_key, False)
                        safe_rerun()

                # Submit Answer toggle
                sa_key = f"show_upload_{i}"
                with col_upload:
                    if st.button(
                        f"📤 Submit My Answer" if not st.session_state.get(sa_key) else f"🔒 Hide Upload",
                        key=f"btn_sa_{i}", use_container_width=True
                    ):
                        st.session_state[sa_key] = not st.session_state.get(sa_key, False)
                        safe_rerun()

                # ── Model Answer Panel ────────────────────────────────────────
                if st.session_state.get(ma_key):
                    model_ans = mq.get("model_answer", "")
                    
                    # Parse model answer to extract sections
                    intro = ""
                    key_points = []
                    conclusion = ""
                    
                    if model_ans:
                        # Try to extract structured sections
                        if "**Introduction:**" in model_ans:
                            parts = model_ans.split("**Introduction:**")
                            if len(parts) > 1:
                                intro_text = parts[1]
                                if "**Key Points:**" in intro_text:
                                    intro = intro_text.split("**Key Points:**")[0].strip()
                                elif "**Conclusion:**" in intro_text:
                                    intro = intro_text.split("**Conclusion:**")[0].strip()
                                else:
                                    intro = intro_text[:300].strip()
                        
                        if "**Key Points:**" in model_ans:
                            kp_section = model_ans.split("**Key Points:**")[1]
                            if "**Conclusion:**" in kp_section:
                                kp_text = kp_section.split("**Conclusion:**")[0]
                            else:
                                kp_text = kp_section
                            
                            # Extract bullet points
                            for line in kp_text.split("\n"):
                                line = line.strip()
                                if line and (line.startswith("-") or line.startswith("•") or line[0].isdigit()):
                                    clean_line = line.lstrip("-•0123456789) ").strip()
                                    if clean_line:
                                        key_points.append(clean_line)
                        
                        if "**Conclusion:**" in model_ans:
                            conc_text = model_ans.split("**Conclusion:**")[1]
                            conclusion = conc_text.strip()[:200]
                    
                    # Display with better formatting
                    st.markdown(
                        f'<div style="background:#0f1729;border:2px solid #7c3aed;border-radius:12px;'
                        f'padding:24px;margin:8px 0 20px 0;">'
                        f'<h4 style="color:#a78bfa;margin:0 0 16px 0; font-size:18px;"><span style="color:#fbbf24;">📝</span> Model Answer</h4>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
                    
                    # Introduction
                    if intro:
                        st.markdown(
                            f'<div style="background:#16162a;border-left:4px solid #818cf8;'
                            f'padding:14px 16px;margin-bottom:12px;border-radius:4px;">'
                            f'<p style="color:#cbd5e1;margin:0;font-size:14px;line-height:1.5;"><strong style="color:#818cf8;">Introduction:</strong> {intro}</p>'
                            f'</div>',
                            unsafe_allow_html=True
                        )
                    
                    # Key Points - Highlighted separately
                    if key_points:
                        st.markdown(
                            f'<div style="background:#1a1a35;border-left:4px solid #34d399;'
                            f'padding:16px;margin-bottom:12px;border-radius:4px;">'
                            f'<p style="color:#34d399;margin:0 0 12px 0;font-size:15px;font-weight:600;'
                            f'text-transform:uppercase;letter-spacing:0.5px;">⭐ Important Points to Remember:</p>',
                            unsafe_allow_html=True
                        )
                        for idx, point in enumerate(key_points[:5], 1):  # Limit to 5 points
                            st.markdown(
                                f'<div style="margin:8px 0;padding-left:12px;border-left:2px solid #34d399;">'
                                f'<p style="color:#e2e8f0;margin:0;font-size:14px;"><strong>{idx}.</strong> {point}</p>'
                                f'</div>',
                                unsafe_allow_html=True
                            )
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Conclusion
                    if conclusion:
                        st.markdown(
                            f'<div style="background:#16162a;border-left:4px solid #f59e0b;'
                            f'padding:14px 16px;margin-bottom:12px;border-radius:4px;">'
                            f'<p style="color:#cbd5e1;margin:0;font-size:14px;line-height:1.5;"><strong style="color:#f59e0b;">Conclusion:</strong> {conclusion}</p>'
                            f'</div>',
                            unsafe_allow_html=True
                        )
                    
                    # Full answer if different from parsed sections
                    if model_ans and not (intro or key_points or conclusion):
                        with st.expander("📖 Full Model Answer", expanded=False):
                            st.markdown(model_ans)


                # ── Answer Upload & Evaluation Panel ──────────────────────────
                if st.session_state.get(sa_key):
                    eval_key = f"eval_result_{i}"

                    st.markdown(
                        f'<div style="background:#1a1a2e;border:2px solid #065f46;border-radius:10px;'
                        f'padding:16px 20px;margin:8px 0 12px 0;color:#d1d5db;">'
                        f'<h4 style="color:#34d399;margin:0 0 8px 0;"><span style="color:#34d399;">📤</span> Submit Your Answer for Q{i+1}</h4>'
                        f'<p style="font-size:14px;color:#cbd5e1;margin:0;line-height:1.4;">'
                        f'Upload a photo/scan of your handwritten answer OR type your response below. '
                        f'Our AI will evaluate it against the model answer.</p>'
                        f'</div>',
                        unsafe_allow_html=True
                    )

                    col_img, col_type = st.columns([1, 1])
                    
                    # Image upload
                    with col_img:
                        st.subheader("📸 Upload Image", divider=False)
                        uploaded_img = st.file_uploader(
                            "Upload scanned/photo answer",
                            type=["png", "jpg", "jpeg", "webp"],
                            key=f"img_upload_{i}",
                            label_visibility="collapsed"
                        )

                    # Or type answer
                    with col_type:
                        st.subheader("⌨️ Type Answer", divider=False)
                        typed_answer = st.text_area(
                            "Type your answer here",
                            height=150,
                            key=f"typed_ans_{i}",
                            placeholder="Write your complete answer here...",
                            label_visibility="collapsed"
                        )

                    st.markdown("")
                    if st.button(f"🤖 Evaluate My Answer for Q{i+1}", key=f"eval_btn_{i}", type="primary", use_container_width=True):
                        question_text = mq["question"]
                        model_answer = mq.get("model_answer", "")

                        eval_prompt = f"""You are a senior UPSC Mains answer evaluator and mentor. Evaluate the student's answer for the following question using UPSC Mains evaluation criteria.

**QUESTION:** {question_text}

**MODEL ANSWER (for reference):** {model_answer}

Evaluate the student's answer and provide a detailed analysis in this EXACT format:

## 📊 Overall Score: ___ / 10

## ✅ Strengths
- What the student did well
- Good points, examples, or structure used

## ❌ Weaknesses & Mistakes
- What was missing or incorrect
- Factual errors, if any
- Important points that were skipped

## 📐 Structure & Presentation
- Did the answer have Introduction, Body, Conclusion?
- Was the answer well-organized with headings/sub-points?
- Was it within the ideal word limit (250 words for 10-markers, 150 for 5-markers)?

## 📚 Content & Knowledge
- Depth of knowledge demonstrated
- Use of facts, data, examples, case studies, committee reports
- Constitutional/legal provisions mentioned

## 🔗 Answer vs Model Answer Comparison
- Key points present in model answer but missing in student's answer
- Any extra good points the student covered

## 🎯 Improvement Tips
- Specific, actionable tips for next time
- What to study/revise for this topic
- How to improve the answer structure

## 📝 Rewritten Key Lines (if needed)
- Suggest 2-3 better-worded sentences the student could use

Be strict but encouraging. This is UPSC-level evaluation."""

                        if uploaded_img:
                            # Process image via vision model
                            img_bytes = uploaded_img.read()
                            img_b64 = base64.b64encode(img_bytes).decode("utf-8")
                            mime = uploaded_img.type or "image/png"

                            vision_prompt = f"""First, carefully read and extract ALL the handwritten/printed text from this image. This is a student's answer to a UPSC Mains exam question.

After extracting the text, evaluate it.

{eval_prompt}

**STUDENT'S ANSWER:** [extracted from the image above]"""

                            with st.spinner("🤖 Reading your answer and evaluating..."):
                                result = ask_llm_vision(vision_prompt, img_b64, mime)
                            st.session_state[eval_key] = result
                            safe_rerun()

                        elif typed_answer.strip():
                            full_prompt = eval_prompt + f"\n\n**STUDENT'S ANSWER:**\n{typed_answer.strip()}"
                            with st.spinner("🤖 Evaluating your answer..."):
                                result = ask_llm(full_prompt)
                            st.session_state[eval_key] = result
                            safe_rerun()

                        else:
                            st.warning("Please upload an image or type your answer first.")

                    # Show evaluation result
                    if eval_key in st.session_state:
                        st.markdown(
                            f'<div style="background:#0f2b1d;border:1px solid #065f46;border-radius:10px;'
                            f'padding:18px 22px;margin:10px 0;color:#d1fae5;">'
                            f'<h4 style="color:#34d399;margin-top:0;">🤖 AI Evaluation Report — Q{i+1}</h4>'
                            f'</div>',
                            unsafe_allow_html=True
                        )
                        st.markdown(st.session_state[eval_key])

                        # Clear evaluation
                        if st.button("🗑️ Clear Evaluation", key=f"clear_eval_{i}"):
                            del st.session_state[eval_key]
                            safe_rerun()

                st.markdown("---")
        else:
            st.info("Click **Generate PYQ Practice Set** above to start.")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #   HISTORY TAB
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    with tab_history:
        st.subheader("📂 Previous PYQ Sessions")
        saved_items = get_saved_items()
        pyq_items = [item for item in saved_items if item[1] == "PYQ Predictor"]

        if pyq_items:
            options = [f"PYQ Session – {item[3]}" for item in pyq_items]
            selected = st.selectbox("Select a previous session", [""] + options, key="sel_pyq")

            if selected:
                idx = options.index(selected)
                item_id = pyq_items[idx][0]
                content = pyq_items[idx][2]

                col_content, col_close = st.columns([20, 1])
                with col_close:
                    st.button("✕", key=f"x_pyq_{item_id}", help="Close", on_click=clear_state, args=("sel_pyq",))
                with col_content:
                    st.text_area("Content", content, height=400, key=f"ta_pyq_{item_id}")

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
            st.info("No previous PYQ sessions found.")


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