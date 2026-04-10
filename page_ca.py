import streamlit as st
from datetime import datetime, date, timedelta
from ui_components import render_news_feed, safe_rerun
from db import (
    get_news, get_news_by_date, get_available_news_dates,
    insert_news, trim_news_to_max, get_ca_filters, 
    add_ca_filter, delete_ca_filter, get_retention, set_retention, clean_old,
    set_config, get_config, has_news_access, request_news_access
)
from scraper import fetch_news, get_editorial_rank, get_source_rank

# ── Cached DB wrappers (60-second TTL to avoid redundant queries on every rerun) ────
@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_news():
    return get_news()

@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_news_by_date(date_str):
    return get_news_by_date(date_str)

@st.cache_data(ttl=120, show_spinner=False)
def _cached_get_available_news_dates():
    return get_available_news_dates()

@st.cache_data(ttl=120, show_spinner=False)
def _cached_get_ca_filters():
    return get_ca_filters()


def show_ca_page():
    from datetime import timezone, timedelta
    ist = timezone(timedelta(hours=5, minutes=30))
    
    username = st.session_state.get("username", "")
    
    # ── Control row: Integrated Fetching Suite ───────────────────────────────
    if has_news_access(username):
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        col_refresh, col_target = st.columns([1, 1])
        
        with col_refresh:
            st.markdown("#### 🔄 Daily Refresh")
            st.caption("Sync the latest news for the most recent period.")
            fetch_days = st.number_input("No. of days to sync:", min_value=1, max_value=365, value=1, help="Fetch news published in the last N days", key="ca_fetch_days")
            st.caption("ℹ️ Recommended: 1-2 days")
            
            if st.button("Refresh Latest Content", use_container_width=True, key="btn_refresh_recent"):
                with st.spinner(f"📡 Syncing latest news from The Hindu, IE, PIB, and others for last {fetch_days} day(s)..."):
                    try:
                        fetched_news = fetch_news(days=fetch_days)
                        if not fetched_news:
                            st.warning("⚠️ No new items found. Your database might already be up to date.")
                        else:
                            insert_news(fetched_news)
                            trimmed = trim_news_to_max()
                            last_fetch_time = datetime.now(ist).strftime("%Y-%m-%d %I:%M:%S %p")
                            set_config("last_fetch_time", last_fetch_time)
                            
                            st.success(f"✅ **{len(fetched_news)} items added!**")
                            if trimmed > 0:
                                st.info(f"🧹 Cleanup: Kept top-tier content, removed {trimmed} low-relevance items.")
                    except Exception as e:
                        st.error(f"❌ **Fetch Error:** {str(e)}")
                safe_rerun()

        with col_target:
            st.markdown("#### 🎯 Specific Date Fetch")
            st.caption("Retrieve news for a particular historical date.")
            selected_date = st.date_input(
                "Select target date:",
                value=date.today() - timedelta(days=1),
                max_value=date.today(),
                min_value=date.today() - timedelta(days=365),
                key="ca_target_date_picker",
            )
            date_label = selected_date.strftime("%d %b %Y")
            st.caption(f"ℹ️ Fetching for: {date_label}")
            
            if st.button(f"📥 Fetch for {date_label}", use_container_width=True, key="btn_fetch_date"):
                with st.spinner(f"🔎 Deep searching all sources for {date_label}..."):
                    try:
                        fetched_news = fetch_news(target_date=selected_date)
                        if not fetched_news:
                            st.warning(f"⚠️ No news found for {date_label}. It may be too old for RSS feeds.")
                        else:
                            insert_news(fetched_news)
                            trim_news_to_max()
                            last_fetch_time = datetime.now(ist).strftime("%Y-%m-%d %I:%M:%S %p")
                            set_config("last_fetch_time", last_fetch_time)
                            st.success(f"✅ **{len(fetched_news)} items added for {date_label}!**")
                    except Exception as e:
                        st.error(f"❌ **Fetch Error:** {str(e)}")
                safe_rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="section-card" style="text-align: center; padding: 40px;">', unsafe_allow_html=True)
        st.markdown("### 🔒 Fetch Access Restricted")
        st.info("You do not have permission to fetch new Current Affairs news. You can only view already fetched news.")
        
        if st.button("Grant Access To current affairs Fetch", type="primary", use_container_width=True, key="btn_req_access"):
            if request_news_access(username):
                st.success("Your request has been submitted to the admin.")
            else:
                st.error("Failed to submit request.")
        st.markdown('</div>', unsafe_allow_html=True)

    # ── News Feed ─────────────────────────────────────────────────────────────
    st.markdown("---")

    # ── Date filter for viewing existing news ─────────────────────────────────
    available_dates = get_available_news_dates()
    
    col_filter_label, col_filter_mode, col_filter_val = st.columns([0.8, 0.8, 2.4])
    with col_filter_label:
        st.markdown(
            '<p style="margin-top:8px; font-weight:600; color:#c4b5fd; font-size:13px;">📆 View news for:</p>',
            unsafe_allow_html=True
        )
    with col_filter_mode:
        view_mode = st.radio("View Mode", ["Dropdown", "Calendar"], label_visibility="collapsed", horizontal=True, key="ca_view_mode")
    
    with col_filter_val:
        if view_mode == "Dropdown":
            view_date = st.selectbox(
                "Filter by date",
                ["All Dates"] + available_dates,
                index=0,
                label_visibility="collapsed",
                key="ca_view_date_dropdown",
            )
        else:
            # Use date_input for a real calendar picker
            view_date_dt = st.date_input(
                "Pick a date",
                value=date.today(),
                max_value=date.today(),
                min_value=date.today() - timedelta(days=365),
                label_visibility="collapsed",
                key="ca_view_date_calendar",
            )
            view_date = view_date_dt.strftime("%Y-%m-%d")

    # Fetch news based on selected filter
    if view_date == "All Dates":
        news_data = get_news()
    else:
        news_data = get_news_by_date(view_date)

    filter_words = [w.lower() for _, w in get_ca_filters()]

    def is_filtered(title):
        tl = title.lower()
        return any(fw in tl for fw in filter_words)

    if news_data:
        # Deduplicate by title (keep the most recent entry per title)
        seen_titles = set()
        unique_news = []
        for n in news_data:
            if n[0] not in seen_titles:
                seen_titles.add(n[0])
                unique_news.append(n)

        # Define source groups for categorization
        news_sources = ["the hindu", "indian express", "down to earth", "livemint", "the wire", "the print", "business standard"]
        
        def get_item_category(n):
            title, _, _, _, source, cat = n[0], n[1], n[2], n[3], str(n[4] or "").lower(), str(n[5] or "").lower()
            
            # Manual Entry Tab
            if "manual entry" in source:
                return "manual"
            
            # PIB Tab: strictly PIB
            if "pib" in source or "pib" in cat:
                return "pib"
            
            # Explained Tab: Strictly high-quality "Explained" or IE Analysis
            if "explained" in source or "explained" in cat:
                if any(s in source for s in ["indian express", "the hindu"]):
                    return "explained"
            if "ie explained" in source:
                return "explained"
            
            # Editorial Tab: Restricted to High-Quality Analysis sources
            hq_editorial_sources = ["the hindu editorial", "the hindu opinion", "the hindu lead", "the hindu op-ed", 
                                   "indian express opinion", "bs editorial", "livemint editorial", "business standard"]
            is_hq = any(hq in source for hq in hq_editorial_sources)
            is_editorial_cat = cat in ["editorial", "opinion", "lead", "op-ed"] or "editorial" in source
            
            if is_hq and is_editorial_cat:
                return "editorial"
            
            # Regular News Tab: Everything else that is relevant
            return "news"

        # Apply categorization and user filters
        pib_items = [n for n in unique_news if get_item_category(n) == "pib" and not is_filtered(n[0])]
        ex_items = [n for n in unique_news if get_item_category(n) == "explained" and not is_filtered(n[0])]
        all_items = [n for n in unique_news if get_item_category(n) == "news" and not is_filtered(n[0])]
        ed_items = [n for n in unique_news if get_item_category(n) == "editorial" and not is_filtered(n[0])]
        manual_items = [n for n in unique_news if get_item_category(n) == "manual" and not is_filtered(n[0])]

        # Sort Editorials by Priority Rank, then Date DESC
        ed_items.sort(key=lambda x: (get_editorial_rank(x[4]), x[2]), reverse=False)
        
        # Secondary sort to ensure newest dates within same rank
        from itertools import groupby
        sorted_ed = []
        for _, group in groupby(sorted(ed_items, key=lambda x: get_editorial_rank(x[4])), key=lambda x: get_editorial_rank(x[4])):
            group_list = list(group)
            group_list.sort(key=lambda x: x[2], reverse=True)
            sorted_ed.extend(group_list)
        ed_items = sorted_ed

        # Sort Explained by Date DESC
        ex_items.sort(key=lambda x: x[2], reverse=True)
        
        # Sort All News by Source Rank, then Date DESC
        all_items.sort(key=lambda x: (get_source_rank(x[4]), x[2]), reverse=False)
        sorted_all = []
        for _, group in groupby(sorted(all_items, key=lambda x: get_source_rank(x[4])), key=lambda x: get_source_rank(x[4])):
            group_list = list(group)
            group_list.sort(key=lambda x: x[2], reverse=True)
            sorted_all.extend(group_list)
        all_items = sorted_all

        # Date context badge
        if view_date != "All Dates":
            st.markdown(
                f'<div style="background: linear-gradient(135deg, #312e81, #4c1d95); border-radius: 8px; '
                f'padding: 8px 16px; margin-bottom: 12px; display: inline-block; '
                f'color: #e0e7ff; font-size: 0.85rem; font-weight: 600;">'
                f'📅 Showing news for: <span style="color: #a5b4fc;">{view_date}</span> '
                f'({len(unique_news)} items)</div>',
                unsafe_allow_html=True
            )

        # Specialized Tabs for UPSC Focus
        tab_all, tab_editorial, tab_explained, tab_pib, tab_manual = st.tabs([
            f"🗞️ All News ({len(all_items)})", 
            f"📝 Editorials ({len(ed_items)})", 
            f"💡 Explained ({len(ex_items)})", 
            f"📣 PIB ({len(pib_items)})",
            f"👤 Manual ({len(manual_items)})"
        ])

        with tab_all:
            render_news_feed(all_items, "all", limit=50)
        with tab_editorial:
            render_news_feed(ed_items, "editorial", limit=20)
        with tab_explained:
            render_news_feed(ex_items, "explained", limit=20)
        with tab_pib:
            render_news_feed(pib_items, "pib", limit=15)
        with tab_manual:
            render_news_feed(manual_items, "manual", limit=50)
    else:
        if view_date != "All Dates":
            st.info(f"""
            📭 **No news available for {view_date}**
            
            **Next steps:**
            1. Go to the **🎯 Target Fetch** section at the top
            2. Select this date and click **📥 Fetch for ...** to download it
            3. Or try a different date from the filter dropdown/calendar
            """)
        else:
            st.info("""
            📭 **No Current Affairs data available**
            
            **Next steps:**
            1. Click **🔄 Refresh Content** button above to fetch the latest news
            2. Wait for the process to complete (may take 30-60 seconds)
            3. If still empty, check you haven't filtered all items in "Manage Filters"
            """)


    # ── Manual News Entry Section ─────────────────────────────────────────────
    st.markdown("---")
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown("### ➕ Manual Content Entry")
    st.markdown('<p style="font-size:13px; color:#94a3b8; margin-top:-10px; margin-bottom:15px;">Add a specific article found elsewhere to your study feed.</p>', unsafe_allow_html=True)
    
    with st.expander("Open Manual Entry Form", expanded=False):
        manual_input = st.text_input("News Link or Title:", key="manual_news_input", placeholder="https://www.thehindu.com/news/...")
        custom_name = st.text_input("Custom Name (Optional):", key="manual_custom_name", placeholder="Enter a custom title for this news...")
            
        if st.button("➕ Add & Analyze News", use_container_width=True, key="btn_add_manual"):
            if manual_input.strip():
                with st.spinner("Processing news..."):
                    from scraper import fetch_full_news_content
                    
                    is_url = manual_input.strip().startswith("http")
                    title_to_save = manual_input.strip()
                    content_to_save = ""
                    url_to_save = manual_input.strip() if is_url else ""
                    
                    if is_url:
                        success, full_text = fetch_full_news_content(manual_input.strip())
                        if success:
                            # Try to extract a title from the URL if possible, or just use the link
                            content_to_save = full_text
                            # Simple title extraction from URL slug
                            if "/" in manual_input.strip():
                                slug = manual_input.strip().rstrip("/").split("/")[-1]
                                title_to_save = slug.replace("-", " ").capitalize()
                        else:
                            st.error(f"Failed to fetch content from link: {full_text}")
                            st.stop()
                    else:
                        content_to_save = manual_input.strip()
                        
                    if custom_name.strip():
                        title_to_save = custom_name.strip()
                    
                    # Prepare for DB
                    new_item = {
                        "title": title_to_save,
                        "content": content_to_save,
                        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "url": url_to_save,
                        "source": "Manual Entry",
                        "category": "Manual",
                        "uid": f"manual_{int(datetime.now().timestamp())}"
                    }
                    
                    try:
                        insert_news([new_item])
                        st.success(f"✅ News added: **{title_to_save[:60]}...**")
                        st.balloons()
                        st.caption("Refresh the page to see it in the feed.")
                    except Exception as e:
                        st.error(f"Failed to save to database: {e}")
            else:
                st.warning("Please enter a link or title first.")
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Source Analytics Section ──────────────────────────────────────────────
    st.markdown("---")
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown("### 📊 Today's News Analytics")
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_items = [n for n in news_data if str(n[2]).startswith(today_str)]
    
    if today_items:
        with st.expander("View Source & Category Breakdown", expanded=False):
            from collections import Counter
            source_counts = Counter([str(n[4] or "Other") for n in today_items])
            cat_counts = Counter([str(n[5] or "General") if len(n) > 5 else "General" for n in today_items])
            
            src_items = list(source_counts.items())
            rows = (len(src_items) + 3) // 4
            for r in range(rows):
                cols = st.columns(min(4, len(src_items) - r*4))
                for i, (src, count) in enumerate(src_items[r*4 : (r+1)*4]):
                    with cols[i]:
                        st.metric(str(src).upper(), f"{count} items")
            
            st.divider()
            st.markdown("**Categorization:** " + " | ".join([f"{k}: {v}" for k, v in cat_counts.items()]))
    else:
        st.caption("No news items fetched today yet.")
    st.markdown('</div>', unsafe_allow_html=True)

    # ── AI Filter Auditor Section ─────────────────────────────────────────────
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown("### 🛠️ AI Filter Quality Auditor")
    
    with st.expander("Audit News Relevance & Keywords", expanded=False):
        st.markdown("""
        This tool uses AI to audit the news items fetched today and yesterday. 
        It evaluates if the system is correctly identifying UPSC-relevant content 
        and suggests improvements for the keyword list and blacklist.
        """)
        
        if st.button("🔍 Run Weekly/Daily Filter Audit", use_container_width=True, key="btn_audit_bottom"):
            from filter_reviewer import perform_filter_review
            with st.spinner("🤖 AI is auditing recent news items..."):
                report = perform_filter_review()
                st.session_state["filter_audit_report"] = report
        
        if "filter_audit_report" in st.session_state:
            st.markdown("---")
            st.markdown("### 📋 AI Audit Report")
            st.markdown(st.session_state["filter_audit_report"])
            
            if st.button("🗑️ Clear Audit", key="btn_clear_audit_bottom"):
                del st.session_state["filter_audit_report"]
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Last Fetch Time Display (Redesigned & Moved to Bottom) ────────────────
    last_fetch = get_config("last_fetch_time", "Never")
    st.markdown(f"""
        <div style="background: linear-gradient(90deg, #7c3aed 0%, #6d28d9 100%); 
                    border-radius: 12px; padding: 12px 20px; margin-top: 20px; margin-bottom: 10px; 
                    display: flex; align-items: center; justify-content: space-between; color: white;
                    box-shadow: 0 4px 15px rgba(124, 58, 237, 0.3);">
            <div style="display: flex; align-items: center; gap: 15px;">
                <div style="background: rgba(255, 255, 255, 0.2); border-radius: 50%; width: 40px; height: 40px; 
                            display: flex; align-items: center; justify-content: center; font-size: 1.5rem;">
                    🕒
                </div>
                <div>
                    <div style="font-size: 0.75rem; opacity: 0.85; font-weight: 500; text-transform: uppercase; letter-spacing: 1px;">
                        Last Content Sync
                    </div>
                    <div style="font-size: 1.1rem; font-weight: 700; letter-spacing: -0.2px;">
                        {last_fetch} <span style="font-size: 0.8rem; font-weight: 400; opacity: 0.8;">(IST)</span>
                    </div>
                </div>
            </div>
            <div style="text-align: right; border-left: 1px solid rgba(255, 255, 255, 0.2); padding-left: 20px;">
                <div style="font-size: 0.7rem; opacity: 0.8; font-style: italic; margin-bottom: 2px;">Status</div>
                <div style="display: flex; align-items: center; gap: 6px; font-size: 0.85rem; font-weight: 600;">
                    <span style="width: 8px; height: 8px; background: #34d399; border-radius: 50%; box-shadow: 0 0 8px #34d399;"></span>
                    Active & Synced
                </div>
            </div>
        </div>
        <p style="text-align: center; color: #94a3b8; font-size: 0.75rem; font-style: italic;">Always manual or auto-synced</p>
    """, unsafe_allow_html=True)


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
        
        from ui_components import clear_state
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

