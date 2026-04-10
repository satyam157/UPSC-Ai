import streamlit as st
import pandas as pd
import PyPDF2
from datetime import date, datetime, timedelta
import json
import time

from scraper import fetch_news, is_upsc_relevant_topic, fetch_full_news_content
from syllabus_scraper import RESOURCE_TYPES, get_all_resource_types, RESOURCE_URLS, fetch_resource_content, combine_articles_for_summary
from url_summarizer import URLSummarizer, fetch_and_summarize_urls
from syllabus_quiz_generator import generate_syllabus_quiz, evaluate_quiz_response
from db import (
    insert_news, get_news, clean_old, get_retention, set_retention,
    save_result, get_results, delete_result,
    save_item, get_saved_items, delete_saved_item,
    add_ca_filter, get_ca_filters, delete_ca_filter,
    save_ai_report, get_ai_reports, delete_ai_report,
    save_test_paper, get_test_papers, delete_test_paper,
    save_syllabus_summary, get_syllabus_summaries, delete_syllabus_summary,
    save_syllabus_quiz, get_syllabus_quiz, save_quiz_attempt, get_quiz_attempts, delete_syllabus_quiz,
    save_url_summary, get_url_summaries, delete_url_summary
)
from quiz_generator import generate_quiz
from llm import ask_llm, ask_llm_vision
import base64
from quiz_parser import parse_quiz
from quiz_engine import evaluate
from pdf_utils import generate_pdf
from pyq_engine import predict, generate_prelims_pyqs, generate_mains_pyqs, generate_full_pyq_session
from ask_esu import analyze_quiz_performance, generate_personalized_study_plan, generate_performance_summary, format_study_plan_output, load_pyq_data

# ─── HELPER FUNCTIONS ─────────────────────────────────────────────────────────
def extract_subject_from_title(title):
    """
    Intelligently extract subject from article title
    Returns a simplified subject category
    """
    title_lower = title.lower()
    
    # Subject mapping with keywords
    subject_keywords = {
        "Policing & Law": ["police", "policing", "law enforcement", "fir", "criminal", "crime", "jail", "prison", "court"],
        "Education": ["education", "nep", "school", "university", "student", "literacy", "exam", "curriculum"],
        "Health": ["health", "disease", "vaccine", "hospital", "medical", "pandemic", "covid", "nutrition"],
        "Economy": ["economy", "gdp", "inflation", "finance", "budget", "tax", "monetary", "rbi", "commerce"],
        "Government": ["government", "ministry", "policy", "scheme", "parliament", "act", "bill", "governance"],
        "Environment": ["environment", "climate", "pollution", "forest", "wildlife", "conservation", "green"],
        "Foreign Affairs": ["foreign", "international", "diplomat", "trade", "agreement", "border", "geopolitics"],
        "Technology": ["technology", "digital", "ai", "startup", "innovation", "tech", "cyber", "it"],
        "Agriculture": ["agriculture", "farming", "crop", "irrigation", "soil", "farmer", "agri"],
        "Infrastructure": ["railway", "highway", "metro", "infrastructure", "transport", "roads", "power"],
        "Social Issues": ["social", "rights", "discrimination", "equality", "welfare", "poverty", "gender"]
    }
    
    for subject, keywords in subject_keywords.items():
        if any(keyword in title_lower for keyword in keywords):
            return subject
    
    # Default: extract from first meaningful word
    words = title_lower.split()
    for word in words:
        if len(word) > 3 and word not in ["from", "with", "what", "your", "the", "and", "for", "are"]:
            return word.capitalize()
    
    return "General"

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
[data-testid="collapsedControl"] { display: none; }
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

# ─── INITIALIZE ASKEU SESSION STATE ───────────────────────────────────────────
if "study_plan_generated" not in st.session_state:
    st.session_state["study_plan_generated"] = False
if "study_plan_output" not in st.session_state:
    st.session_state["study_plan_output"] = {}
if "show_esu_welcome" not in st.session_state:
    st.session_state["show_esu_welcome"] = True

# ─── SIDEBAR ──────────────────────────────────────────────────────────────────
st.sidebar.title(f"👤 {st.session_state['username']}")

# ── Sidebar Logout ────────────────────────────────────────────────────────────
if st.sidebar.button("Logout", use_container_width=True, key="btn_logout_sidebar"):
    logout()

page = st.sidebar.radio("Navigate", [
    "Current Affairs",
    "CA Quiz",
    "Practice",
    "PDF Quiz",
    "Results",
    "Ask Esu",
    "Summarizer",
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
    col_btn, col_days = st.columns([4, 1])
    with col_days:
        fetch_days = st.number_input("Days to fetch", min_value=1, max_value=30, value=1)
    with col_btn:
        st.markdown('<div style="margin-top: 28px;"></div>', unsafe_allow_html=True)
        if st.button("🔄 Refresh Content", use_container_width=True):
            with st.spinner(f"Fetching latest news from PIB, The Hindu, Indian Express for last {fetch_days} day(s)..."):
                try:
                    fetched_news = fetch_news(days=fetch_days)
                    if not fetched_news:
                        st.warning("""
                        ⚠️ **No news items found**
                        
                        This could mean:
                        - RSS feeds are temporarily unavailable
                        - Try again in a few moments
                        - Already have the news for the selected days in the database
                        """)
                    else:
                        insert_news(fetched_news)
                        st.success(f"✅ **{len(fetched_news)} news items added!**")
                        st.info("📰 Including: Politics, Policy, Economy, International Relations, Governance")
                except Exception as e:
                    st.error(f"❌ **Error fetching news:** {str(e)}")
            safe_rerun()

    # ── Source Analytics ──────────────────────────────────────────────────────
    news_data = get_news()
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_items = [n for n in news_data if n[2] == today_str]
    
    if today_items:
        with st.expander("📊 **Today's News Sources Analytics**", expanded=False):
            from collections import Counter
            # Count sources and categories, ensuring no None values
            source_counts = Counter([str(n[4] or "Other") for n in today_items])
            cat_counts = Counter([str(n[5] or "General") if len(n) > 5 else "General" for n in today_items])
            
            # Display metrics in a responsive grid (max 4 per row)
            src_items = list(source_counts.items())
            rows = (len(src_items) + 3) // 4
            for r in range(rows):
                cols = st.columns(min(4, len(src_items) - r*4))
                for i, (src, count) in enumerate(src_items[r*4 : (r+1)*4]):
                    with cols[i]:
                        st.metric(str(src).upper(), f"{count} items")
            
            st.divider()
            st.markdown("**Categorization:** " + " | ".join([f"{k}: {v}" for k, v in cat_counts.items()]))

        # ── Filter Reviewer ───────────────────────────────────────────────────
        with st.expander("🛠️ **AI Filter Quality Auditor**", expanded=False):
            st.markdown("""
            This tool uses AI to audit the news items fetched today and yesterday. 
            It evaluates if the system is correctly identifying UPSC-relevant content 
            and suggests improvements for the keyword list and blacklist.
            """)
            
            if st.button("🔍 Run Weekly/Daily Filter Audit", use_container_width=True):
                from filter_reviewer import perform_filter_review
                with st.spinner("🤖 AI is auditing recent news items..."):
                    report = perform_filter_review()
                    st.session_state["filter_audit_report"] = report
            
            if "filter_audit_report" in st.session_state:
                st.markdown("---")
                st.markdown("### 📋 AI Audit Report")
                st.markdown(st.session_state["filter_audit_report"])
                
                if st.button("🗑️ Clear Audit"):
                    del st.session_state["filter_audit_report"]
                    st.rerun()

    # ── News Feed ─────────────────────────────────────────────────────────────
    st.markdown("---")
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

        # Specialized Tabs for UPSC Focus
        tab_all, tab_editorial, tab_explained, tab_pib = st.tabs([
            "🗞️ All News", "📝 Editorials", "💡 Explained", "📣 PIB"
        ])

        # Source context colors
        SOURCE_COLORS = {
            "the hindu editorial": "#d32f2f", "the hindu opinion": "#c62828", "the hindu": "#e53935",
            "ie explained": "#1565c0", "indian express opinion": "#0d47a1", "indian express": "#1976d2",
            "pib": "#2e7d32", "bs editorial": "#6a1b9a", "business standard": "#7b1fa2",
            "down to earth": "#00695c", "the print": "#f57f17", "livemint editorial": "#3e2723"
        }
        DEFAULT_COLOR = "#546e7a"

        def render_news_feed(items, key_prefix):
            if not items:
                st.info("No items found in this section.")
                return
            
            feed_dates = sorted(list(set(n[2] for n in items)), reverse=True)
            for d in feed_dates:
                day_items = [n for n in items if n[2] == d and not is_filtered(n[0])]
                if day_items:
                    with st.expander(f"📅 {d} ({len(day_items)} items)", expanded=False):
                        for idx, n in enumerate(day_items):
                            title_val    = n[0]
                            content_val  = n[1]
                            url_val      = n[3]
                            source_val   = str(n[4] or "Other")
                            category_val = str(n[5] or "General") if len(n) > 5 else "General"
                            
                            news_key = f"{key_prefix}_{d}_{idx}"
                            exp_key = f"news_exp_{news_key}"
                            
                            col_t, col_b = st.columns([9, 1])
                            with col_t:
                                s_color = SOURCE_COLORS.get(source_val.lower(), DEFAULT_COLOR)
                                badge = f'<span style="background:{s_color};color:white;font-size:10px;padding:2px 8px;border-radius:10px;margin-right:8px;font-weight:700;">{source_val.upper()}</span>'
                                cat_badge = f'<span style="color:#94a3b8;font-size:10px;border:1px solid #334155;padding:1px 6px;border-radius:4px;margin-right:8px;">{category_val}</span>'
                                st.markdown(f"**• {badge}{cat_badge}{title_val}**", unsafe_allow_html=True)
                            with col_b:
                                if st.button("🔍" if not st.session_state.get(exp_key) else "✕", key=f"btn_{news_key}"):
                                    st.session_state[exp_key] = not st.session_state.get(exp_key, False)
                                    safe_rerun()
                            
                            if st.session_state.get(exp_key):
                                with st.container():
                                    st.markdown('<div style="background:#1e1e2e;border:1px solid #334155;border-radius:8px;padding:15px;margin-bottom:15px;">', unsafe_allow_html=True)
                                    
                                    if title_val not in st.session_state["news_summaries"]:
                                        with st.spinner("🤖 Analyzing..."):
                                            is_deep = "editorial" in category_val.lower() or "explained" in category_val.lower() or "editorial" in title_val.lower() or \
                                                      any(kw in source_val.lower() for kw in ["hindu", "express", "mint", "standard"])
                                            
                                            raw_text = ""
                                            if is_deep and url_val:
                                                st.caption("🔗 Fetching full article content...")
                                                suc, ft = fetch_full_news_content(url_val)
                                                raw_text = ft if suc else (content_val or title_val)
                                            else:
                                                raw_text = content_val or title_val
                                                
                                            prompt_text = f"Analyze for UPSC:\nTITLE: {title_val}\nCONTENT: {raw_text}\n\nFormat with: One-Liner, Relevant Articles/Acts, Background, Important Points, Challenges, Way Forward, Conclusion."
                                            st.session_state["news_summaries"][title_val] = ask_llm(prompt_text)
                                    
                                    st.markdown(st.session_state["news_summaries"][title_val])
                                    if url_val: st.markdown(f"[🔗 Read Full Article]({url_val})")
                                    st.markdown('</div>', unsafe_allow_html=True)
                            st.markdown("---")

        with tab_all:
            render_news_feed(unique_news, "all")
        with tab_editorial:
            ed_items = [n for n in unique_news if n[5] and str(n[5]).lower() in ["editorial", "opinion"]]
            render_news_feed(ed_items, "editorial")
        with tab_explained:
            ex_items = [n for n in unique_news if n[5] and str(n[5]).lower() == "explained"]
            render_news_feed(ex_items, "explained")
        with tab_pib:
            pib_items = [n for n in unique_news if n[4] and "pib" in str(n[4]).lower()]
            render_news_feed(pib_items, "pib")
    else:
        st.info("""
        📭 **No Current Affairs data available**
        
        **Next steps:**
        1. Click **🔄 Refresh Content** button above to fetch the latest news
        2. Wait for the process to complete (may take 30-60 seconds)
        3. If still empty, check you haven't filtered all items in "Manage Filters"
        """)

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
            st.warning("""
            ⚠️ **No current affairs data available**
            
            Go to **Current Affairs** tab → Click **🔄 Refresh Content** to fetch the latest news first!
            """)
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
#   ASK ESU - PERSONALIZED STUDY PLANNING
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Ask Esu":
    st.subheader("🤖 Ask Esu - Your Personal Study Plan & AI Guide")
    st.caption("Provide a prompt and your exam date, and Esu will generate a personalized study plan, workflow, practice strategy, and comprehensive AI analysis based on your quiz data and UPSC PYQ trends.")
    
    st.markdown("---")
    
    # ── Exam Type Selection ───────────────────────────────────────────────────
    st.markdown("### 📌 Select Your Target Exam")
    col1, col2 = st.columns([1, 1])
    
    with col1:
        exam_type = st.radio(
            "Target Exam Type:",
            ("UPSC Prelims", "UPSC Mains"),
            horizontal=True,
            label_visibility="collapsed"
        )
        exam_type = "prelims" if exam_type == "UPSC Prelims" else "mains"
    
    st.markdown("---")
    
    # ── Study Plan Input Section ──────────────────────────────────────────────
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### 📝 Your Query/Prompt")
        user_prompt = st.text_area(
            "Describe your study goals, challenges, or specific areas you want help with:",
            placeholder="E.g., 'I'm weak in Current Affairs and want a plan to improve before UPSC Prelims'",
            height=100,
            key="esu_prompt",
            label_visibility="collapsed"
        )
    
    with col2:
        st.markdown("### 📅 Exam Date (Optional)")
        exam_date = st.date_input(
            "Select your target exam date:",
            value=None,
            key="esu_exam_date",
            label_visibility="collapsed"
        )
        
        if exam_date:
            days_left = (exam_date - datetime.now().date()).days
            if days_left < 0:
                st.error(f"❌ Exam date is in the past!")
            else:
                st.success(f"✅ {days_left} days left")
    
    st.markdown("---")
    
    # ── Generate Study Plan Button ────────────────────────────────────────────
    if st.button("🚀 Generate Personalized Study Plan", type="primary", use_container_width=True, key="btn_generate_study_plan"):
        if not user_prompt.strip():
            st.error("❌ Please provide a prompt to proceed.")
        else:
            with st.spinner("🤖 Esu is analyzing your performance and generating your study plan..."):
                # Get quiz results
                results = get_results()
                
                # Analyze performance
                quiz_analysis = analyze_quiz_performance(results)
                
                # Convert exam date to datetime if provided
                exam_datetime = None
                if exam_date:
                    exam_datetime = datetime.combine(exam_date, datetime.min.time())
                
                # Generate study plan with exam type
                study_plan = generate_personalized_study_plan(user_prompt, quiz_analysis, exam_datetime, exam_type)
                
                # Generate performance summary with exam type
                performance_summary = generate_performance_summary(quiz_analysis, exam_type)
                
                # Save to session state
                st.session_state["study_plan_output"] = format_study_plan_output(
                    study_plan, performance_summary, quiz_analysis
                )
                st.session_state["study_plan_generated"] = True
                st.success("✅ Study plan generated successfully!")
                safe_rerun()
    
    st.markdown("---")
    
    # ── Display Generated Study Plan ──────────────────────────────────────────
    if st.session_state.get("study_plan_generated"):
        output = st.session_state.get("study_plan_output", {})
        
        # ── Create Tabs for different sections ─────────────────────────────────
        tab_plan, tab_summary, tab_metrics, tab_pyq, tab_full = st.tabs([
            "📚 Study Plan",
            "📊 Performance Summary",
            "📈 Your Current Data",
            "📌 UPSC PYQ Trends",
            "📄 Full Report"
        ])
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        #   STUDY PLAN TAB
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        with tab_plan:
            st.markdown(output.get("study_plan", "No study plan generated"))
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        #   PERFORMANCE SUMMARY TAB
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        with tab_summary:
            st.markdown(output.get("performance_summary", "No performance summary generated"))
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        #   CURRENT DATA TAB (with dropdowns for each section)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        with tab_metrics:
            analysis = output.get("quiz_analysis", {})
            
            if analysis.get("total_quizzes", 0) > 0:
                # Overall Metrics - Collapsible
                with st.expander("📊 Overall Metrics", expanded=True):
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("Total Quizzes", analysis.get("total_quizzes", 0))
                    with col2:
                        st.metric("Overall Accuracy", f"{analysis.get('overall_accuracy', 0)}%")
                    with col3:
                        st.metric("Total Marks", round(analysis.get("total_marks", 0), 2))
                    with col4:
                        st.metric("Accuracy Trend", f"avg: {round(sum(analysis.get('accuracy_trend', [0]))/max(len(analysis.get('accuracy_trend', [1])),1), 2)}%")
                
                # Subject-wise breakdown - Collapsible
                with st.expander("🎯 Subject-Wise Breakdown", expanded=False):
                    metrics_data = []
                    for quiz_type, metrics in analysis.get("by_quiz_type", {}).items():
                        metrics_data.append({
                            "Subject/Quiz Type": quiz_type,
                            "Quizzes": metrics.get("quiz_count", 0),
                            "Avg Accuracy": f"{metrics.get('average_accuracy', 0)}%",
                            "Total Marks": round(metrics.get("total_marks", 0), 2),
                            "Correct": metrics.get("total_correct", 0),
                            "Attempted": metrics.get("total_attempted", 0)
                        })
                    
                    if metrics_data:
                        df_metrics = pd.DataFrame(metrics_data)
                        st.dataframe(df_metrics, use_container_width=True)
                
                # Strengths and Weaknesses - Collapsible
                with st.expander("💪 Strengths & Areas for Improvement", expanded=False):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("### 💪 Strengths")
                        strong = analysis.get("strong_areas", [])
                        if strong:
                            for area in strong:
                                st.success(f"✅ {area}")
                                metrics = analysis.get("by_quiz_type", {}).get(area, {})
                                st.caption(f"Accuracy: {metrics.get('average_accuracy', 0)}%")
                        else:
                            st.info("No strong areas identified yet. Keep practicing!")
                    
                    with col2:
                        st.markdown("### 🎯 Areas for Improvement")
                        weak = analysis.get("weak_areas", [])
                        if weak:
                            for area in weak:
                                st.warning(f"⚠️ {area}")
                                metrics = analysis.get("by_quiz_type", {}).get(area, {})
                                st.caption(f"Accuracy: {metrics.get('average_accuracy', 0)}%")
                        else:
                            st.info("No weak areas identified. Great job!")
            else:
                st.info("📊 No quiz data available for analysis. Start by taking some quizzes!")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        #   UPSC PYQ TRENDS TAB
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        with tab_pyq:
            pyq_data = load_pyq_data()
            if pyq_data:
                # Select Exam Type
                pyq_exam_type = st.radio(
                    "Select Exam Type:",
                    ("UPSC Prelims", "UPSC Mains"),
                    horizontal=True,
                    key="pyq_exam_selector"
                )
                pyq_exam_type = "prelims" if pyq_exam_type == "UPSC Prelims" else "mains"
                if pyq_exam_type == "prelims" and "prelims" in pyq_data:
                    prelims_data = pyq_data["prelims"]
                    with st.expander("🏆 Most Important Subjects (By PYQ Frequency)", expanded=True):
                        for subject in prelims_data.get("subjects", []):
                            col1, col2 = st.columns([2, 1])
                            with col1:
                                st.markdown(f"**{subject.get('rank')}. {subject.get('name')}**")
                            with col2:
                                st.metric("Difficulty", subject.get('difficulty', 'N/A'))
                            chapters = subject.get('important_chapters', [])
                            if chapters:
                                st.markdown(f"**Key Topics:** {', '.join(chapters[:8])}")
                            st.markdown("---")
                elif pyq_exam_type == "mains" and "mains" in pyq_data:
                    mains_data = pyq_data["mains"]
                    with st.expander("🏆 Most Important Papers (By PYQ Frequency)", expanded=True):
                        for paper in mains_data.get("subjects", []):
                            col1, col2 = st.columns([2, 1])
                            with col1:
                                st.markdown(f"**{paper.get('rank')}. {paper.get('name')}**")
                            with col2:
                                st.metric("Questions", paper.get('total_questions', 'N/A'))
                            chapters = paper.get('important_chapters', [])
                            if chapters:
                                st.markdown(f"**Key Topics:** {', '.join(chapters[:8])}")
                            st.markdown("---")
                with st.expander("📊 Recent Trends & Patterns", expanded=False):
                    if "trends" in pyq_data:
                        trends = pyq_data["trends"].get(pyq_exam_type, {})
                        if trends:
                            if "question_pattern_changes" in trends:
                                st.markdown("**Recent Question Pattern Changes:**")
                                for trend in trends.get("question_pattern_changes", []):
                                    st.markdown(f"• {trend}")
                            if "high_frequency_topics" in trends:
                                st.markdown("**High Frequency Topics:**")
                                for topic in trends.get("high_frequency_topics", [])[:10]:
                                    st.markdown(f"• {topic}")
                        else:
                            st.info("Trend data not available yet.")
                    else:
                        st.info("PYQ trend data will be updated weekly.")
            else:
                st.error("❌ Could not load PYQ data. Please ensure pyq_data.json exists.")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        #   FULL REPORT TAB
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        with tab_full:
            st.markdown("## 📋 Complete Study Plan & Analysis Report")
            st.markdown("---")
            
            st.markdown("### Executive Summary")
            st.markdown(output.get("study_plan", "").split("\n\n")[0] if output.get("study_plan") else "")
            
            st.markdown("---")
            st.markdown(output.get("study_plan", "No study plan generated"))
            
            st.markdown("---")
            st.markdown("## Performance Analysis")
            st.markdown(output.get("performance_summary", "No performance summary generated"))
        
        st.markdown("---")
        
        st.markdown("---")

        # ── Save Report to DB ────────────────────────────────────────────────
        st.markdown("### 💾 Save This Report")
        col_save, col_reset = st.columns([1, 1])

        with col_save:
            if st.button("💾 Save Report to Database", type="primary", use_container_width=True):
                period_label = f"Prompt: {user_prompt[:60]}{'...' if len(user_prompt) > 60 else ''}"
                full_report = (
                    f"**USER PROMPT:** {user_prompt}\n"
                    f"**EXAM DATE:** {exam_date if exam_date else 'Not specified'}\n\n"
                    f"---\n## Study Plan\n\n"
                    f"{output.get('study_plan', '')}\n\n"
                    f"---\n## Performance Summary\n\n"
                    f"{output.get('performance_summary', '')}"
                )
                report_id = save_ai_report("Esu Study Plan", period_label, full_report)
                if report_id:
                    st.success(f"✅ Report saved to database! (ID: {report_id})")
                else:
                    st.error("❌ Failed to save. Check DB connection.")

        with col_reset:
            if st.button("🔄 Generate New Study Plan", use_container_width=True):
                st.session_state["study_plan_generated"] = False
                st.session_state["study_plan_output"] = {}
                safe_rerun()
    # ── Saved Esu Reports ─────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📁 Saved Esu Study Plans")
    esu_reports = [r for r in get_ai_reports() if r[1] == "Esu Study Plan"]

    if esu_reports:
        esu_options = [
            f"[{r[2][:50]}] – {r[4].strftime('%d %b %Y %H:%M') if hasattr(r[4], 'strftime') else str(r[4])}"
            for r in esu_reports
        ]
        sel_esu_report = st.selectbox("Select a saved plan", [""] + esu_options, key="sel_esu_report")

        if sel_esu_report:
            ridx = esu_options.index(sel_esu_report)
            report = esu_reports[ridx]
            report_id = report[0]
            report_content = report[3]

            col_h, col_x = st.columns([20, 1])
            with col_x:
                st.button("✕", key=f"x_esu_{report_id}", help="Close",
                          on_click=clear_state, args=("sel_esu_report",))
            with col_h:
                st.markdown(f"**Context:** {report[2]}")

            st.markdown(report_content)

            if st.button("🗑️ Delete This Report", key=f"del_esu_{report_id}"):
                st.session_state[f"confirm_del_esu_{report_id}"] = True
                safe_rerun()
            if st.session_state.get(f"confirm_del_esu_{report_id}"):
                st.warning("Permanently delete this study plan report?")
                c1, c2 = st.columns(2)
                if c1.button("Yes, Delete", key=f"yes_esu_{report_id}"):
                    delete_ai_report(report_id)
                    st.session_state[f"confirm_del_esu_{report_id}"] = False
                    safe_rerun()
                if c2.button("Cancel", key=f"no_esu_{report_id}"):
                    st.session_state[f"confirm_del_esu_{report_id}"] = False
                    safe_rerun()
    else:
        st.info("No saved Esu study plans yet. Generate and save one above.")

    if not st.session_state.get("study_plan_generated"):
        if st.session_state.get("show_esu_welcome", True):
            st.info("""
            👋 **Welcome to Ask Esu!**
            
            Esu is your personal AI study guide. Here's what Esu does:
            
            1. **📚 Analyzes Your Performance** - Reviews all your quiz results across different subjects
            2. **🎯 Creates Personalized Plans** - Based on your strengths, weaknesses, and goals
            3. **📅 Time-Bound Strategy** - If you provide an exam date, Esu creates a deadline-aware study schedule
            4. **💡 Workflow & Tactics** - Gives you daily routines, practice strategies, and exam-cracking techniques
            5. **📊 Detailed Analytics** - Provides comprehensive performance analysis and metrics
            
            **To get started:**
            - Share what you're struggling with or your study goals
            - (Optional) Enter your target exam date
            - Click "Generate Personalized Study Plan"
            
            Esu will then create a complete study roadmap just for you!
            """)


# ══════════════════════════════════════════════════════════════════════════════
#   CRISP SUMMARIZER - Summarize Any URLs
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Summarizer":
    st.subheader("📄 Summarizer - UPSC Resources from Coaching Institutes")
    
    st.markdown("---")
    
    # Create tabs
    tab_urls, tab_text, tab_pdf, tab_saved, tab_quiz = st.tabs(["📝 Summarize Articles", "✍️ Text Summary", "📄 PDF Summary", "📚 Saved Summaries", "📋 Quiz from Summaries"])
    
    # ── TAB 1: SUMMARIZE ARTICLES ──────────────────────────────────────────
    with tab_urls:
        st.info("📌 Paste coaching institute article URLs (one per line). System will auto-generate crisp summaries with NCERT connections.")
        
        urls_input = st.text_area(
            "Paste article URLs from coaching institutes",
            height=150,
            placeholder="https://nextias.com/article-name\nhttps://visionias.in/topic-name\nhttps://vajiramandravi.com/current-affairs\nhttps://forumias.com/blog\nhttps://www.pmfias.com/article-6-of-paris-agreement/topic-name"
        )
        
        # Optional subject input
        custom_subject = st.text_input(
            "📚 Subject/Topic (optional - leave empty for auto-detection)",
            placeholder="e.g., National Education, Economy, Policing",
            help="If you provide a subject, it will be associated with these summaries"
        )
        
        if st.button("🚀 Generate Summaries", use_container_width=True, key="btn_gen_summaries"):
            if urls_input.strip():
                urls = [url.strip() for url in urls_input.split('\n') if url.strip()]
                
                if urls:
                    progress_bar = st.progress(0)
                    summarizer = URLSummarizer()
                    
                    for idx, url in enumerate(urls):
                        with st.spinner(f"📥 Processing ({idx+1}/{len(urls)})..."):
                            title, summary, source, error = summarizer.summarize_url(url)
                            
                            if error:
                                st.error(f"**❌ {source}** - {error}")
                            else:
                                # Auto-extract subject if not provided
                                subject = custom_subject if custom_subject else extract_subject_from_title(title)
                                
                                # Save to database with subject
                                save_id = save_url_summary(url, title, summary, subject)
                                
                                # Display success
                                st.success(f"✅ **{source}** - {title}\n📚 Subject: {subject}")
                                
                                # Display summary
                                with st.expander(f"📖 View Summary", expanded=True):
                                    st.markdown(summary)
                                    
                                    # Save button (if not already saved)
                                    col_save_gen, col_copy_gen = st.columns(2)
                                    with col_save_gen:
                                        st.caption("✅ Auto-saved to Saved Summaries")
                                    with col_copy_gen:
                                        if st.button("📋 Copy", key=f"copy_article_{save_id}"):
                                            st.caption("✓ Copied!")
                        
                        progress_bar.progress((idx + 1) / len(urls))
                    
                    st.info("✅ All summaries generated and saved!")
            else:
                st.warning("⚠️ Please paste at least one URL")
    
    
    
    
    # ── TAB 3: TEXT SUMMARY ────────────────────────────────────────────────
    with tab_text:
        st.subheader("✍️ Paste Text & Get Crisp Summary")
        st.info("📌 Paste any article, news, or research text and get a concise UPSC-focused summary.")
        
        # Text input
        text_input = st.text_area(
            "Paste your text here:",
            height=200,
            placeholder="Paste article content, research material, or any text you want to summarize...",
            key="text_summary_area"
        )
        
        # Summary style selection
        col_style, col_btn = st.columns([0.5, 0.5])
        with col_style:
            summary_style = st.radio(
                "Summary Style:",
                ["Syllabus Format", "Detailed"],
                horizontal=True,
                help="Choose how you want the summary to be formatted",
                key="text_style_radio_v3"
            )
        
        with col_btn:
            st.write("")
            if st.button("🚀 Generate Summary", use_container_width=True, key="btn_text_summary"):
                if text_input.strip():
                    st.session_state['generating_text_summary'] = True
                    st.session_state['text_summary_saved_id'] = None 
                else:
                    st.warning("⚠️ Please paste some text first")
        
        # Generate text summary
        if st.session_state.get('generating_text_summary'):
            with st.spinner("🤖 Generating crisp summary..."):
                style_prompts = {
                    "Detailed": """Analyze the following text and provide a comprehensive UPSC-focused summary with:
- Key facts and figures
- Relevant constitutional or policy background
- Implications and impact
- Questions this might generate for UPSC Prelims/Mains
- **📚 NCERT Links**: Mention relevant Class, Subject, and Chapter connections.

Keep it detailed but structured.""",
                    "Syllabus Format": """Analyze the following text using this EXACT format:
## 📌 One-Liner
(One crisp sentence summary)

## ✍️ Crisp & Concise Summary
(3-4 high-impact bullet points summarizing the essence)

## 🏛️ Relevant Articles/Acts
(List constitutional provisions, acts, or policies)

## ⭐ Key Points
(3-5 bullet points with key facts)

## 📚 NCERT Links
Class [X] [Subject] → Chapter: [Name]
Connection: [1-2 lines how it connects]

## 🎓 GS Paper Relevance
(Which GS paper: GS1/GS2/GS3/GS4, and Essay topic if applicable)

## ⚠️ Key Issues
(Main challenges or concerns)"""
                }
                
                full_prompt = f"""{style_prompts.get(summary_style, style_prompts['Detailed'])}

---
**TEXT TO SUMMARIZE:**

{text_input[:11000]}

---

Provide the summary now. 
ALSO, on the very last line, strictly provide a suggested title and a suggested subject category (from: Economy, Polity, Environment, S&T, IR, History, Social, Health, Education, Agriculture) in this format: 
METADATA: Title: [Your Title] | Subject: [Your Subject]"""
                
                resp = ask_llm(full_prompt)
                
                if "METADATA:" in resp:
                    st.session_state['text_summary'] = resp.split("METADATA:")[0].strip()
                    meta = resp.split("METADATA:")[1].strip()
                    try:
                        st.session_state['text_summary_auto_title'] = meta.split("|")[0].replace("Title:", "").strip()
                        st.session_state['text_summary_auto_subj'] = meta.split("|")[1].replace("Subject:", "").strip()
                    except:
                        st.session_state['text_summary_auto_title'] = f"Text Summary - {datetime.now().strftime('%Y-%m-%d')}"
                        st.session_state['text_summary_auto_subj'] = "General"
                else:
                    st.session_state['text_summary'] = resp
                    st.session_state['text_summary_auto_title'] = f"Text Summary - {datetime.now().strftime('%Y-%m-%d')}"
                    st.session_state['text_summary_auto_subj'] = "General"
                st.session_state['generating_text_summary'] = False
        
        # Display and save text summary
        if st.session_state.get('text_summary'):
            st.markdown("---")
            st.markdown("**📊 Summary:**")
            st.markdown(st.session_state['text_summary'])
            
            st.markdown("### 🏷️ Summary Info")
            col_t, col_s = st.columns(2)
            with col_t:
                final_title = st.text_input("Summary Title:", value=st.session_state.get('text_summary_auto_title', ""), key="text_final_title")
            with col_s:
                final_subject = st.text_input("Subject Category:", value=st.session_state.get('text_summary_auto_subj', ""), key="text_final_subj")
            
            col_save, col_del, col_clear = st.columns(3)
            with col_save:
                if not st.session_state.get('text_summary_saved_id'):
                    if st.button("💾 Save to Resources", use_container_width=True, key="save_text_summary"):
                        u_url = f"text_input_{int(time.time())}"
                        s_id = save_url_summary(u_url, final_title, st.session_state['text_summary'], final_subject)
                        if s_id:
                            st.session_state['text_summary_saved_id'] = s_id
                            st.success("✅ Saved!")
                            time.sleep(0.5)
                            safe_rerun()
                else: st.success("✅ Already Saved")
            
            with col_del:
                saved_id = st.session_state.get('text_summary_saved_id')
                if saved_id:
                    if st.button("🗑️ Delete Save", use_container_width=True, key="del_text_summary_btn"):
                        delete_url_summary(saved_id)
                        st.session_state['text_summary_saved_id'] = None
                        st.warning("Deleted.")
                        time.sleep(0.5)
                        safe_rerun()
                else: st.button("🗑️ Delete", use_container_width=True, disabled=True, key="del_text_dis")
            
            with col_clear:
                if st.button("🔄 Clear All", use_container_width=True, key="clear_text_summary"):
                    st.session_state['text_summary'] = None
                    st.session_state['text_summary_saved_id'] = None
                    safe_rerun()
    
    # ── TAB 4: PDF SUMMARY ─────────────────────────────────────────────────
    with tab_pdf:
        st.subheader("📄 Upload PDF & Get Summary by Page Range")
        st.info("📌 Upload a PDF file, select page range, and get a crisp UPSC-focused summary.")
        
        pdf_file = st.file_uploader("Choose a PDF file:", type="pdf", key="pdf_summary_uploader_final")
        if pdf_file:
            try:
                reader = PyPDF2.PdfReader(pdf_file)
                total_pages = len(reader.pages)
                st.info(f"📄 PDF loaded: **{pdf_file.name}**. Total pages: {total_pages}")
                
                col_from, col_to = st.columns(2)
                with col_from: from_page = st.number_input("From Page:", min_value=1, max_value=total_pages, value=1, key="pdf_from_page_final")
                with col_to: to_page = st.number_input("To Page:", min_value=1, max_value=total_pages, value=min(5, total_pages), key="pdf_to_page_final")
                
                if from_page > to_page: st.warning("⚠️ 'From Page' should be less than or equal to 'To Page'")
                else: st.success(f"✅ Will summarize pages {from_page} to {to_page} ({to_page - from_page + 1} pages)")
                
                col_style, col_btn = st.columns([0.5, 0.5])
                with col_style: pdf_style = st.radio("Summary Style:", ["Syllabus Format", "Detailed"], horizontal=True, key="pdf_summary_style_v3")
                
                with col_btn:
                    st.write("")
                    if st.button("🚀 Generate Summary", use_container_width=True, key="btn_pdf_summary_final"):
                        if from_page <= to_page:
                            st.session_state['generating_pdf_summary'] = True
                            st.session_state['pdf_summary_saved_id'] = None
                        else: st.error("❌ Invalid page range")
                
                if st.session_state.get('generating_pdf_summary'):
                    with st.spinner(f"📥 Extracting text..."):
                        pdf_extracted_text = ""
                        for page_num in range(int(from_page) - 1, int(to_page)):
                            pdf_extracted_text += reader.pages[page_num].extract_text() + "\n"
                        
                        if not pdf_extracted_text.strip():
                            st.error("❌ Could not extract text.")
                            st.session_state['generating_pdf_summary'] = False
                        else:
                            with st.spinner("🤖 Generating summary..."):
                                pdf_style_prompts = {
                                    "Detailed": """Analyze the following text and provide a comprehensive UPSC-focused summary with:
- Key facts and figures
- Relevant constitutional or policy background
- Implications and impact
- Questions this might generate for UPSC Prelims/Mains
- **📚 NCERT Links**: Mention relevant Class, Subject, and Chapter connections.

Keep it detailed but structured.""",
                                    "Syllabus Format": """Analyze the following text using this EXACT format:
## 📌 One-Liner
(One crisp sentence summary)

## ✍️ Crisp & Concise Summary
(3-4 high-impact bullet points summarizing the essence)

## 🏛️ Relevant Articles/Acts
(List constitutional provisions, acts, or policies)

## ⭐ Key Points
(3-5 bullet points with key facts)

## 📚 NCERT Links
Class [X] [Subject] → Chapter: [Name]
Connection: [1-2 lines how it connects]

## 🎓 GS Paper Relevance
(Which GS paper: GS1/GS2/GS3/GS4, and Essay topic if applicable)

## ⚠️ Key Issues
(Main challenges or concerns)"""
                                }
                                pdf_meta_prompt = f"""{pdf_style_prompts.get(pdf_style)}
---
**PDF CONTENT:** {pdf_extracted_text[:11000]}
---
Provide the summary now. ALSO, on the very last line, strictly provide METADATA: Title: [Your Title] | Subject: [Your Subject]"""
                                pdf_resp = ask_llm(pdf_meta_prompt)
                                if "METADATA:" in pdf_resp:
                                    st.session_state['pdf_summary'] = pdf_resp.split("METADATA:")[0].strip()
                                    meta = pdf_resp.split("METADATA:")[1].strip()
                                    st.session_state['pdf_auto_title'] = meta.split("|")[0].replace("Title:", "").strip()
                                    st.session_state['pdf_auto_subj'] = meta.split("|")[1].replace("Subject:", "").strip()
                                else:
                                    st.session_state['pdf_summary'] = pdf_resp
                                    st.session_state['pdf_auto_title'] = f"{pdf_file.name} (p.{from_page}-{to_page})"
                                    st.session_state['pdf_auto_subj'] = "General"
                                st.session_state['pdf_pages_attr'] = f"{from_page}-{to_page}"
                                st.session_state['generating_pdf_summary'] = False
                
                if st.session_state.get('pdf_summary'):
                    st.markdown("---")
                    st.markdown(f"**📊 Summary ({pdf_file.name}, Pages {st.session_state.get('pdf_pages_attr', '?')}):**")
                    st.markdown(st.session_state['pdf_summary'])
                    
                    st.markdown("### 🏷️ Summary Info")
                    col_pt, col_ps = st.columns(2)
                    with col_pt: pdf_title = st.text_input("Summary Title:", value=st.session_state.get('pdf_auto_title', ""), key="pdf_final_title")
                    with col_ps: pdf_subj = st.text_input("Subject Category:", value=st.session_state.get('pdf_auto_subj', ""), key="pdf_final_subj")

                    col_psave, col_pdel, col_pclear = st.columns(3)
                    with col_psave:
                        if not st.session_state.get('pdf_summary_saved_id'):
                            if st.button("💾 Save to Resources", use_container_width=True, key="save_pdf_summary_btn"):
                                u_url = f"pdf_upload_{pdf_file.name}_{int(time.time())}"
                                p_id = save_url_summary(u_url, pdf_title, st.session_state['pdf_summary'], pdf_subj)
                                if p_id:
                                    st.session_state['pdf_summary_saved_id'] = p_id; st.success("✅ Saved!"); time.sleep(0.5); safe_rerun()
                        else: st.success("✅ Already Saved")
                    with col_pdel:
                        if st.session_state.get('pdf_summary_saved_id'):
                            saved_id_to_del = st.session_state.get('pdf_summary_saved_id')
                            if st.button("🗑️ Delete Save", use_container_width=True, key="del_pdf_summary_btn"):
                                delete_url_summary(saved_id_to_del)
                                st.session_state['pdf_summary_saved_id'] = None
                                st.warning("Deleted."); time.sleep(0.5); safe_rerun()
                        else: st.button("🗑️ Delete", use_container_width=True, disabled=True, key="del_pdf_dis")
                    with col_pclear:
                        if st.button("🔄 Clear All", use_container_width=True, key="clear_pdf_summary_btn"):
                            st.session_state['pdf_summary'] = None; st.session_state['pdf_summary_saved_id'] = None; safe_rerun()
            except Exception as e: st.error(f"❌ PDF Error: {e}")


    # ── TAB 4: SAVED SUMMARIES ─────────────────────────────────────────────
    with tab_saved:
        st.subheader("📚 Your Saved Summaries")
        saved_summaries = get_url_summaries(limit=100)
        if saved_summaries:
            col_filter1, col_filter2 = st.columns([0.7, 0.3])
            with col_filter2:
                if st.button("🔄 Refresh", use_container_width=True, key="refresh_saved"):
                    safe_rerun()
            for summary_id, url, title, subject, summary_text, created_at in saved_summaries:
                col_exp, col_btns = st.columns([0.85, 0.15])
                with col_exp:
                    with st.expander(f"📄 {title} • {subject} ({created_at.strftime('%Y-%m-%d') if created_at else 'Unknown'})"):
                        st.markdown(summary_text)
                        st.caption(f"🔗 Source: {url}"); st.caption(f"📚 Subject: {subject}")
                with col_btns:
                    if st.button("🗑️", key=f"del_btn_{summary_id}", help="Delete this summary"):
                        col_yes, col_no = st.columns(2)
                        with col_yes:
                            if st.button("YES", key=f"yes_{summary_id}"):
                                delete_url_summary(summary_id); st.success("Deleted!"); time.sleep(0.5); safe_rerun()
                        with col_no:
                            if st.button("NO", key=f"no_{summary_id}"): st.info("Cancelled")
        else:
            st.info("📭 No saved summaries yet. Start by summarizing article URLs or text!")

    # ── TAB 5: QUIZ FROM SUMMARIES ─────────────────────────────────────────
    with tab_quiz:
        st.subheader("📋 Generate Quiz from Summaries")
        saved_summaries_all = get_url_summaries(limit=100)
        if not saved_summaries_all: st.warning("⚠️ No saved summaries available.")
        else:
            st.markdown("### 🔍 Filter Summaries")
            source_filter = st.selectbox("Show summaries from:", ["All Sources", "Web Articles", "Text Inputs", "PDF Uploads"], key="quiz_source_filter")
            filtered_summaries = []
            for s in saved_summaries_all:
                url = s[1]
                if source_filter == "All Sources": filtered_summaries.append(s)
                elif source_filter == "Web Articles" and url.startswith("http"): filtered_summaries.append(s)
                elif source_filter == "Text Inputs" and url.startswith("text_input"): filtered_summaries.append(s)
                elif source_filter == "PDF Uploads" and url.startswith("pdf_upload"): filtered_summaries.append(s)
            
            if not filtered_summaries: st.info(f"No summaries found.")
            else:
                summary_options = {}
                for summary_id, url, title, subject, summary_text, created_at in filtered_summaries:
                    stype = "Article"
                    if url.startswith("text_input"): stype = "Text"
                    elif url.startswith("pdf_upload"): stype = "PDF"
                    display_text = f"[{stype}] {title} ({created_at.strftime('%Y-%m-%d') if created_at else 'Unknown'})"
                    summary_options[display_text] = (summary_id, title, subject, summary_text)
                
                selected_summary = st.selectbox("Select summary to create quiz from:", list(summary_options.keys()), key="article_quiz_select_multi")
                if selected_summary:
                    summary_id, title, auto_subject, summary_text = summary_options[selected_summary]
                    col_subj1, col_subj2 = st.columns([0.6, 0.4])
                    with col_subj1:
                        custom_subject_quiz = st.text_input("📚 Subject for Quiz Results", value=auto_subject or "", key="quiz_override_subj")
                    with col_subj2:
                        st.write("")
                        if st.button("ℹ️ Auto-detect", use_container_width=True, key="quiz_auto_subj"):
                            custom_subject_quiz = extract_subject_from_title(title)
                    final_subject_quiz = custom_subject_quiz if custom_subject_quiz else (auto_subject or "General")
                    col1, col2 = st.columns([0.6, 0.4])
                    with col1: num_questions = st.slider("Number of questions:", 3, 10, 5, key="article_quiz_num_multi")
                    with col2:
                        if st.button("🎯 Generate Quiz", use_container_width=True, key="btn_gen_article_quiz_multi"):
                            st.session_state['generating_article_quiz'] = True
                    
                    if st.session_state.get('generating_article_quiz'):
                        with st.spinner("🧠 Generating questions..."):
                            questions, error = generate_syllabus_quiz(final_subject_quiz, summary_text, num_questions)
                            if error: st.error(error)
                            else:
                                st.session_state['current_article_quiz'] = questions
                                st.session_state['article_quiz_subject'] = final_subject_quiz
                                st.session_state['article_quiz_started'] = True
                                st.session_state['generating_article_quiz'] = False
                    
                    if st.session_state.get('article_quiz_started') and st.session_state.get('current_article_quiz'):
                        st.markdown("---"); st.subheader(f"📋 Quiz - {final_subject_quiz}")
                        questions = st.session_state['current_article_quiz']
                        user_answers = []
                        for idx, question in enumerate(questions):
                            st.markdown(f"**Q{idx+1}. {question['question']}**")
                            ans = st.radio(f"Opt for Q{idx+1}:", question['options'], key=f"multi_q_{idx}", label_visibility="collapsed")
                            user_answers.append(question['options'].index(ans))
                            st.caption(f"Difficulty: {question.get('difficulty', 'Medium')}"); st.markdown("---")
                        if st.button("✅ Submit Quiz", use_container_width=True, key="submit_article_quiz_multi"):
                                eval_result, eval_error = evaluate_quiz_response(questions, user_answers)
                                if eval_error: st.error(eval_error)
                                else:
                                    st.session_state['article_quiz_results'] = eval_result
                                    st.session_state['article_quiz_started'] = False
                                    save_result((final_subject_quiz, len(questions), len(questions), eval_result['correct'], eval_result['wrong'], eval_result['percentage'], eval_result['score']))
                                    safe_rerun()
                    
                    if st.session_state.get('article_quiz_results'):
                        st.markdown("---"); st.subheader(f"📊 Quiz Results - {final_subject_quiz}")
                        results = st.session_state['article_quiz_results']
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Score", f"{results['score']}/{results['total']}")
                        c2.metric("Percentage", f"{results['percentage']}%")
                        c3.metric("Rating", "🏆" if results['percentage'] >= 70 else "📚")
                        for idx, result in enumerate(results['results'], 1):
                            status = "✅" if result['is_correct'] else "❌"
                            with st.expander(f"{status} Q{idx}. {result['question']}", expanded=not result['is_correct']):
                                st.write(f"**Your Answer:** {result['user_answer']}")
                                st.write(f"**Correct Answer:** {result['correct_answer']}")
                                st.markdown(f"**Explanation:** {result['explanation']}")
                        if st.button("🔄 New Quiz", use_container_width=True, key="retry_multi_quiz"):
                            st.session_state['article_quiz_results'] = None; st.session_state['article_quiz_started'] = False; safe_rerun()



# ══════════════════════════════════════════════════════════════════════════════
#   AI ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "AI Analysis":
    st.subheader("🤖 AI-Powered Quiz Analysis")
    st.markdown("""
**Summary Report:**

This section displays AI-generated analysis reports for your quizzes and test papers. Each report includes detailed insights, error patterns, and actionable recommendations to help you optimize your preparation and avoid repeating mistakes.
    """)
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
    
    st.markdown("""
    Get crisp, UPSC-focused summaries of:
    - **Yojana** - Government schemes & policies
    - **Kurukshetra** - Rural development & governance  
    - **Economic Survey** - Economic analysis & data
    - **Union Budget** - Financial allocations & priorities
    - **India Yearbook** - Facts, figures & institutions
    
    Sourced from: Next IAS, Vision IAS, Forum IAS, Vajiram & Ravi
    """)
    
    st.markdown("---")
    
    # ── Resource Type Selection ────────────────────────────────────────────────
    col1, col2 = st.columns([2, 1])
    with col1:
        resource_type = st.selectbox(
            "Select Resource Type",
            options=get_all_resource_types(),
            key="select_resource_type"
        )
    with col2:
        st.write("")
        st.write("")
        if st.button("📖 View Sources", use_container_width=True):
            st.session_state['show_sources'] = not st.session_state.get('show_sources', False)
            safe_rerun()
    
    # ── Show coaching institute sources ─────────────────────────────────────────
    if st.session_state.get('show_sources', False):
        resource_urls = RESOURCE_URLS[resource_type]
        st.info(f"""
        **{resource_type}**  
        {resource_urls['description']}
        
        **Primary Sources (Fetched First):**
        {chr(10).join([f"• {url}" for url in resource_urls['primary_urls']])}
        
        **Backup Sources:**
        {chr(10).join([f"• {url}" for url in resource_urls['backup_urls']])}
        """)
    
    st.markdown("---")
    
    # ── Fetch from Internet ────────────────────────────────────────────────────
    st.subheader(f"🌐 {resource_type} - Auto-Fetch & Summarize")
    
    st.caption("📡 AI automatically fetches latest content from multiple sources and generates crisp UPSC-relevant summaries")
    
    # Option 1: Fetch from Internet
    col_fetch, col_space = st.columns([2, 1])
    with col_fetch:
        if st.button("🔍 Fetch Latest from Internet", use_container_width=True, key="btn_fetch_latest"):
            with st.spinner(f"📡 Fetching {resource_type} content from multiple sources..."):
                articles, errors = fetch_resource_content(resource_type)
                
                if articles:
                    st.session_state['fetched_articles'] = articles
                    st.session_state['fetched_errors'] = errors
                    st.success(f"✅ Fetched {len(articles)} source(s)")
                    
                    # Show what was fetched
                    with st.expander("📜 View Fetched Sources"):
                        for idx, article in enumerate(articles, 1):
                            st.markdown(f"**Source {idx}: {article['url']}**")
                            st.caption(f"Fetched: {article['fetched_at']}")
                            st.text(article['content'][:500] + "..." if len(article['content']) > 500 else article['content'])
                    
                    # Show any errors
                    if errors:
                        with st.expander("⚠️ Fetch Errors"):
                            for error in errors:
                                st.warning(error)
                else:
                    st.error("❌ Could not fetch from any sources. Try manual entry below.")
                    if errors:
                        with st.expander("See errors"):
                            for error in errors:
                                st.write(error)
    
    # Option 2: Generate summary from fetched content
    if st.session_state.get('fetched_articles'):
        st.markdown("---")
        st.subheader("📝 Generate Summary from Fetched Content")
        
        if st.button("🤖 Generate AI Summary", use_container_width=True, key="btn_gen_from_fetched"):
            fetched_articles = st.session_state.get('fetched_articles', [])
            combined_content = combine_articles_for_summary(fetched_articles)
            
            with st.spinner("✍️ Generating crisp UPSC-focused summary..."):
                prompt = f"""You are an expert UPSC coach. Analyze the following content fetched from {resource_type} sources and create a COMPREHENSIVE, CONCISE summary that combines insights from ALL sources.

**FETCHED CONTENT:**
{combined_content}

**YOUR TASK:**
1. Analyze ALL sources above
2. Extract ONLY UPSC-RELEVANT information
3. Combine insights and avoid duplication
4. Create ONE crisp summary (max 300 words of content)

**FORMAT (STRICT):**

## 📌 Overview
1-2 sentence summary combining all sources

## 🎯 Key Topics Covered
• Topic 1 from sources
• Topic 2 from combined analysis
• Topic 3 synthesis
(3-5 major points)

## 💡 UPSC Relevance
- Relevant GSs: [Papers]
- Why matters: [How it affects exams]
- Key takeaways: [Exam-focus]

## 📊 Key Figures/Data (if applicable)
• Data point 1
• Data point 2

## 🔗 Related Areas
- Adjacent topic 1
- Adjacent topic 2

---

NO FLUFF. Pure exam-focused content synthesized from all sources."""
                
                ai_summary = ask_llm(prompt)
                st.session_state['generated_summary'] = ai_summary
                st.session_state['generated_title'] = f"{resource_type} Summary - {datetime.now().strftime('%B %Y')}"
                st.success("✅ Summary generated from internet sources!")
    
    # Display and save generated summary
    if st.session_state.get('generated_summary'):
        st.markdown("---")
        st.markdown("### 📄 Generated Summary")
        st.markdown(st.session_state['generated_summary'])
        
        col_save, col_discard = st.columns(2)
        with col_save:
            if st.button("💾 Save This Summary", use_container_width=True, key="btn_save_internet_summary"):
                saved_id = save_syllabus_summary(
                    resource_type,
                    st.session_state['generated_title'],
                    st.session_state['generated_summary'],
                    f"Fetched from internet sources: {', '.join([a['url'] for a in st.session_state.get('fetched_articles', [])])}"
                )
                if saved_id:
                    st.success("✅ Summary saved!")
                    del st.session_state['generated_summary']
                    del st.session_state['generated_title']
                    safe_rerun()
                else:
                    st.error("Error saving summary")
        
        with col_discard:
            if st.button("❌ Discard", use_container_width=True, key="btn_discard_internet"):
                del st.session_state['generated_summary']
                del st.session_state['generated_title']
                safe_rerun()
    
    # Option 3: Manual Entry (Fallback)
    st.markdown("---")
    st.subheader("✏️ Manual Entry (Fallback)")
    st.caption("If automatic fetch doesn't work, paste content manually here")
    
    with st.expander("Paste custom content"):
        summary_title = st.text_input("Title", key="manual_title")
        summary_content = st.text_area("Content", height=250, key="manual_content")
        source_url = st.text_input("Source URL", key="manual_url")
        
        if st.button("💾 Save Manual Summary", use_container_width=True, key="btn_save_manual"):
            if summary_title and summary_content:
                if not is_upsc_relevant_topic(summary_title):
                    st.error("Title must be UPSC-relevant (education, policy, government, etc.)")
                else:
                    saved_id = save_syllabus_summary(resource_type, summary_title, summary_content, source_url)
                    if saved_id:
                        st.success("✅ Summary saved!")
                        safe_rerun()
            else:
                st.warning("Title and content required")
    
    st.markdown("---")
    
    # ── View Saved Summaries ───────────────────────────────────────────────────
    st.subheader(f"📚 Saved {resource_type} Summaries")
    
    saved_summaries = get_syllabus_summaries(resource_type)
    
    if saved_summaries:
        for idx, (summary_id, res_type, title, content, source_url, saved_at) in enumerate(saved_summaries):
            with st.expander(f"📄 {title} ({saved_at.strftime('%Y-%m-%d') if saved_at else 'Unknown'})"):
                st.markdown(content)
                
                if source_url:
                    st.markdown(f"🔗 [Source]({source_url})")
                
                # Delete button with confirmation
                col_delete, col_empty = st.columns([1, 3])
                with col_delete:
                    if st.button(f"🗑️ Delete", key=f"del_btn_{summary_id}_{idx}"):
                        # Show confirmation dialog
                        confirm_col1, confirm_col2 = st.columns(2)
                        with confirm_col1:
                            if st.button(f"✅ Yes, Delete", key=f"confirm_del_{summary_id}_{idx}"):
                                if delete_syllabus_summary(summary_id):
                                    st.success("✅ Deleted!")
                                    safe_rerun()
                                else:
                                    st.error("Error deleting")
                        with confirm_col2:
                            if st.button(f"❌ Cancel", key=f"cancel_del_{summary_id}_{idx}"):
                                st.info("Deletion cancelled")
    else:
        st.info(f"No {resource_type} summaries saved yet. Fetch and generate one above!")


# ══════════════════════════════════════════════════════════════════════════════
#   TEST PAPER ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Test Paper Analysis":
    st.subheader("📝 Test Paper Analysis")
    st.markdown("""
**Summary Report:**

This section provides a comprehensive summary of your test paper performance, including scores, accuracy, strengths, weaknesses, and trends over time. Use this report to identify areas for improvement and track your progress across all attempted test papers.
    """)

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
            # Actually: correct = attempted correct + guessed correct
            # We don't store attempted correct separately, so:
            # wrong = attempted - guessed_correct (only guessed_incorrect + truly wrong among non-guessed)
            # Simplify: total correct = total_att - total_wrong; we know guessed_incorrect → wrong
            # Better formula given inputs:
            # wrong = (guessed_incorrect) + (attempted - total_guessed - correct_in_non_guessed)
            # Since we don't have "correct in non-guessed" separately, use overall:
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
