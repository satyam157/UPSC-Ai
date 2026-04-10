import streamlit as st
from datetime import date
import pandas as pd
import json

# Internal module imports
from ui_components import (
    CUSTOM_CSS, login_page, logout, safe_rerun
)
from db import init_db, user_exists, is_admin

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

# ─── AUTHENTICATION ──────────────────────────────────────────────────────────
if "logged_in" not in st.session_state:
    # Check query params for persistence
    q_user = st.query_params.get("user")
    if q_user and user_exists(q_user):
        st.session_state["logged_in"] = True
        st.session_state["username"] = q_user
    else:
        st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
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
with st.sidebar:
    st.markdown(f"### 👤 Welcome, **{username.capitalize()}**")
    
    nav_options = [
        "Current Affairs", "CA Quiz", "RANDOM DATE CA QUIZ", "AI CA PYQ Predicator", 
        "PDF Quiz", "AI Summarizer", "Ask Esu", "Test Paper Analysis", 
        "Results", "AI Analysis"
    ]
    
    if is_admin(username):
        nav_options.append("Admin Panel")
        
    page = st.radio("📍 Navigation", nav_options)
    
    st.markdown("---")
    if st.button("🚪 Logout", use_container_width=True):
        logout()

# ─── ROUTER ──────────────────────────────────────────────────────────────────
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
