import streamlit as st
from datetime import date
import pandas as pd
import json

# Internal module imports
from ui_components import (
    CUSTOM_CSS, login_page, logout, safe_rerun
)
from db import init_db, user_exists, is_admin, validate_session_token, get_user_allowed_pages, get_unified_test_records
from codeforces_visualizer import get_tier_info

# Page imports
from page_ca import show_ca_page
from page_ca_quiz import show_ca_quiz_page
from page_ai_ca_test import show_ai_ca_test_page
from page_practice import show_practice_page
from page_study_materials import show_pdf_quiz_page, show_summarizer_page
from page_analysis import show_results_page, show_ai_analysis_page, show_test_paper_analysis_page
from page_ask_esu import show_ask_esu_page
from page_admin import show_admin_page

# ─── CONFIG ──────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="UPSC AI SYSTEM",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
init_db()

# ─── SECURE AUTHENTICATION & URL TAMPERING GUARD ──────────────────────────────
# We protect against unauthorized access by verifying cryptographically secure session tokens.
# Changing ?user= in the URL will NEVER grant access to another user's data.
q_token = st.query_params.get("session_token")
q_user = st.query_params.get("user")

if st.session_state.get("logged_in") and st.session_state.get("username"):
    curr_user = st.session_state["username"]
    
    # URL Tamper Guard: If someone changes ?user= to another name in their URL:
    if q_user and q_user.lower().strip() != curr_user.lower().strip():
        st.session_state["logged_in"] = False
        st.session_state["username"] = ""
        st.session_state["session_token"] = ""
        st.query_params.clear()
        st.error("⛔ Security Alert: URL parameter tampering detected. You have been logged out.")
        login_page()
        st.stop()
        
    # Keep URL clean of plain username parameters
    if "user" in st.query_params:
        del st.query_params["user"]

else:
    st.session_state["logged_in"] = False
    st.session_state["username"] = ""
    
    # If someone directly tries to tamper with ?user= without a token:
    if q_user and not q_token:
        st.query_params.clear()
        st.error("⛔ Direct URL parameter access is prohibited. Please sign in.")
        login_page()
        st.stop()

    # If session token is present in URL, validate it against the database
    if q_token:
        token_user = validate_session_token(q_token)
        if token_user:
            # If URL also had ?user= and it doesn't match the token:
            if q_user and q_user.lower().strip() != token_user.lower().strip():
                st.query_params.clear()
                st.error("⛔ Invalid session credentials for the requested user.")
                login_page()
                st.stop()

            st.session_state["logged_in"] = True
            st.session_state["username"] = token_user
            st.session_state["session_token"] = q_token
            if "user" in st.query_params:
                del st.query_params["user"]
        else:
            # Token invalid or expired
            st.query_params.clear()

if not st.session_state.get("logged_in"):
    login_page()
    st.stop()

# ─── AUTO-FETCH TRIGGER (ONCE A DAY) ─────────────────────────────────────────
def _background_fetch_task():
    from datetime import datetime, timezone, timedelta
    from scraper import fetch_news
    from db import insert_news, trim_news_to_max, set_config, get_config, get_news_by_date_range
    import time
    
    ist = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(ist)
    today_str = now.strftime("%Y-%m-%d")
    
    # 1. Global check: has ANY user/session triggered it today?
    last_auto_date = get_config("last_auto_fetch_date")
    
    if last_auto_date != today_str:
        try:
            # Fetch only 1 day by default for auto-sync
            fetched = fetch_news(days=1)
            if fetched:
                insert_news(fetched)
                trim_news_to_max()
                
                # Update the display timestamp
                last_fetch_time = now.strftime("%Y-%m-%d %I:%M:%S %p")
                set_config("last_fetch_time", last_fetch_time)
            
            # Persist the success globally for today
            set_config("last_auto_fetch_date", today_str)
        except Exception as e:
            print(f"Background auto-fetch failed: {e}")

    # 2. Weekly Sync on Sunday
    if now.weekday() == 6: # Sunday
        last_weekly_sync = get_config("last_weekly_sync_date")
        if last_weekly_sync != today_str:
            try:
                start_date = (now - timedelta(days=6)).date() # Monday
                end_date = now.date() # Sunday
                
                recent_news = get_news_by_date_range(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d 23:59:59"))
                
                from collections import defaultdict
                counts_by_date = defaultdict(int)
                for n in recent_news:
                    d = n[2].split(" ")[0] if len(n) > 2 else ""
                    if d:
                        counts_by_date[d] += 1
                        
                fetched_any = False
                for i in range(7):
                    target_d = start_date + timedelta(days=i)
                    target_str = target_d.strftime("%Y-%m-%d")
                    if counts_by_date[target_str] < 35:
                        print(f"Background: Fetching backlog for {target_str}")
                        f_news = fetch_news(target_date=target_d)
                        if f_news:
                            insert_news(f_news)
                            fetched_any = True
                            
                if fetched_any:
                    trim_news_to_max()
                    
                set_config("last_weekly_sync_date", today_str)
            except Exception as e:
                print(f"Background weekly sync failed: {e}")

def trigger_auto_fetch():
    # Only spawn the thread if it hasn't been spawned in this session to prevent thread spam
    if st.session_state.get("auto_fetch_started"):
        return
    st.session_state["auto_fetch_started"] = True
    
    import threading
    _fetch_thread = threading.Thread(target=_background_fetch_task, daemon=True)
    
    # Try to attach Streamlit script run context so thread works cleanly
    try:
        from streamlit.runtime.scriptrunner import add_script_run_ctx
        add_script_run_ctx(_fetch_thread)
    except Exception:
        pass
        
    _fetch_thread.start()

trigger_auto_fetch()

# ─── SIDEBAR NAVIGATION ──────────────────────────────────────────────────────
username = st.session_state["username"]
allowed_pages = get_user_allowed_pages(username)

with st.sidebar:
    st.markdown(f"### 👤 Welcome, **{username.capitalize()}**")
    if is_admin(username):
        st.markdown('<span style="color:#a78bfa;font-size:12px;font-weight:600;">👑 Administrator</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span style="color:#34d399;font-size:12px;font-weight:600;">🎓 Aspirant</span>', unsafe_allow_html=True)

    # ── Sidebar Rating Cards ──────────────────────────────────────────────────
    def _sidebar_rating_html(exam_type):
        recs = get_unified_test_records(username=username, exam_type=exam_type)
        if not recs:
            return ""
        from datetime import date as _date, datetime as _datetime, timezone as _tz, timedelta as _td
        today = _datetime.now(_tz(_td(hours=5, minutes=30))).date()  # IST
        sorted_recs = sorted(recs, key=lambda r: r["date"])
        all_marks = [float(r["marks"]) for r in sorted_recs]
        highest_m = max(all_marks)
        high_tier = get_tier_info(highest_m, exam_type)
        denom = 200 if exam_type == "Prelims" else 250
        label = "🎯 Prelims" if exam_type == "Prelims" else "✍️ Mains"

        def rec_date(r):
            d = r["date"]
            return d.date() if isinstance(d, _datetime) else d

        today_recs = [r for r in sorted_recs if rec_date(r) == today]
        has_today  = len(today_recs) > 0

        if has_today:
            current_m = float(today_recs[-1]["marks"])
            cur_tier  = get_tier_info(current_m, exam_type)
            prior = [float(r["marks"]) for r in sorted_recs if rec_date(r) < today]
            delta_html = ""
            if prior:
                diff = current_m - prior[-1]
                if diff > 0:
                    delta_html = f'<span style="color:#4ade80;font-size:10px;">&#9650;+{diff:.1f}</span>'
                elif diff < 0:
                    delta_html = f'<span style="color:#f87171;font-size:10px;">&#9660;{diff:.1f}</span>'
            current_inner = f"""
              <div style="font-size:9px;color:#64748b;text-transform:uppercase;letter-spacing:.5px;">Today</div>
              <div style="font-size:18px;font-weight:800;color:{cur_tier['color']};line-height:1.1;">
                {current_m:.1f}<span style="font-size:11px;color:#475569;font-weight:400;">/{denom}</span>
                &nbsp;{delta_html}
              </div>
              <div style="font-size:9px;color:{cur_tier['color']};background:{cur_tier['color']}18;
                          border:1px solid {cur_tier['color']}30;border-radius:10px;
                          padding:1px 6px;display:inline-block;margin-top:2px;font-weight:600;">
                {cur_tier['name']}
              </div>"""
            left_border = cur_tier['color']
        else:
            current_inner = f"""
              <div style="font-size:9px;color:#64748b;text-transform:uppercase;letter-spacing:.5px;">Today</div>
              <div style="font-size:16px;font-weight:700;color:#475569;line-height:1.2;">
                &#8212;/{denom}
              </div>
              <div style="font-size:9px;color:#64748b;margin-top:2px;">No test today</div>"""
            left_border = "#475569"

        return f"""
        <div style="margin:6px 0;padding:10px 12px;background:linear-gradient(135deg,#161b22,#1e2430);
                    border-radius:10px;border-left:3px solid {left_border};font-family:Inter,sans-serif;">
          <div style="font-size:10px;color:#94a3b8;font-weight:600;letter-spacing:.8px;margin-bottom:4px;">
            {label}
          </div>
          <div style="display:flex;justify-content:space-between;align-items:center;gap:6px;">
            <div style="flex:1;">
              {current_inner}
            </div>
            <div style="width:1px;height:40px;background:rgba(255,255,255,0.08);"></div>
            <div style="flex:1;text-align:right;">
              <div style="font-size:9px;color:#64748b;text-transform:uppercase;letter-spacing:.5px;">&#127942; Highest</div>
              <div style="font-size:18px;font-weight:800;color:{high_tier['color']};line-height:1.1;">
                {highest_m:.1f}<span style="font-size:11px;color:#475569;font-weight:400;">/{denom}</span>
              </div>
              <div style="font-size:9px;color:{high_tier['color']};background:{high_tier['color']}18;
                          border:1px solid {high_tier['color']}30;border-radius:10px;
                          padding:1px 6px;display:inline-block;margin-top:2px;font-weight:600;">
                {high_tier['name']}
              </div>
            </div>
          </div>
        </div>
        """

    sidebar_prelims_html = _sidebar_rating_html("Prelims")
    sidebar_mains_html   = _sidebar_rating_html("Mains")
    if sidebar_prelims_html or sidebar_mains_html:
        st.markdown(sidebar_prelims_html + sidebar_mains_html, unsafe_allow_html=True)

    st.markdown("---")

    ALL_STANDARD_PAGES = [
        "Current Affairs", "CA Quiz", "RANDOM DATE CA QUIZ", "AI CA PYQ Predicator", 
        "PDF Quiz", "AI Summarizer", "Ask Esu", "Test Paper Analysis", 
        "Results", "AI Analysis"
    ]
    
    # Filter navigation options based on administrator-assigned permissions
    if is_admin(username):
        nav_options = list(ALL_STANDARD_PAGES)
        nav_options.append("Admin Panel")
    else:
        nav_options = [p for p in ALL_STANDARD_PAGES if p in allowed_pages]
        
    if not nav_options:
        st.warning("⚠️ No pages have been assigned to your account. Please contact the administrator.")
        page = None
    else:
        page = st.radio("📍 Navigation", nav_options)
    
    st.markdown("---")
    if st.button("🚪 Logout", use_container_width=True):
        logout()

# ─── ROUTER & PAGE ACCESS GUARD ──────────────────────────────────────────────
if page is None:
    st.info("You do not have active page permissions. Please contact your administrator.")
    st.stop()

# Route guard: prevent unauthorized page access
if not is_admin(username) and page not in allowed_pages:
    st.error(f"⛔ Access Restricted: You do not have permission to access '{page}'. Please contact the administrator.")
    st.stop()

if page == "Current Affairs":
    st.title("🗞️ Current Affairs")
    show_ca_page()

elif page == "CA Quiz":
    st.title("🎯 Current Affairs Quiz")
    show_ca_quiz_page()

elif page == "RANDOM DATE CA QUIZ":
    show_ai_ca_test_page()

elif page == "AI CA PYQ Predicator":
    show_practice_page()

elif page == "PDF Quiz":
    st.title("📄 PDF Quiz Generator")
    show_pdf_quiz_page()

elif page == "AI Summarizer":
    show_summarizer_page()

elif page == "Results":
    show_results_page()

elif page == "Ask Esu":
    show_ask_esu_page()

elif page == "AI Analysis":
    show_ai_analysis_page()

elif page == "Test Paper Analysis":
    show_test_paper_analysis_page()

elif page == "Admin Panel" and is_admin(username):
    show_admin_page()
