import streamlit as st
import pandas as pd
from datetime import datetime
from db import (
    get_all_users, add_user, update_user_password, toggle_user_active, 
    delete_user, is_admin, get_config, set_config, clear_all_news, 
    set_news_access, get_pending_access_requests, resolve_access_request,
    get_user_allowed_pages, set_user_allowed_pages, ALL_AVAILABLE_PAGES,
    get_results, get_uploaded_files, get_uploaded_file_bytes, delete_uploaded_file,
    get_test_papers, get_saved_items, get_ai_reports
)
from ui_components import safe_rerun

def show_admin_page():
    st.markdown("""
    <div style="background: linear-gradient(135deg, #111827 0%, #311042 100%);
                border: 1px solid rgba(168, 85, 247, 0.4); border-radius: 14px;
                padding: 20px 24px; margin-bottom: 24px;">
        <h2 style="color: #f3e8ff; margin: 0 0 4px 0;">🛡️ Admin Control & Tenant Hub</h2>
        <p style="color: #cbd5e1; margin: 0; font-size: 14px;">
            Manage user accounts, configure page access permissions, and explore isolated tenant data (files, quiz results, test analyses).
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    current_admin = st.session_state.get("username", "")
    if not is_admin(current_admin):
        st.error("⛔ Access Denied: You do not have administrator privileges.")
        st.stop()
    
    users = get_all_users()
    user_list = [u[0] for u in users] if users else []
    
    tab_inspect, tab_perms, tab_users, tab_news = st.tabs([
        "🔍 User Data Inspector", 
        "🔒 Page Access Permissions", 
        "👥 User Accounts Management", 
        "📰 News & System Settings"
    ])
    
    # ════════════════════════════════════════════════════════════════════════════
    # TAB 1: USER DATA INSPECTOR (QUIZ RESULTS, UPLOADED FILES, ANALYSES, NOTES)
    # ════════════════════════════════════════════════════════════════════════════
    with tab_inspect:
        st.subheader("🔍 Tenant Data Explorer")
        st.caption("Inspect private tenant database records for each user without data overlap.")
        
        if not user_list:
            st.info("No registered users found.")
        else:
            selected_user = st.selectbox(
                "Select User to Inspect:",
                user_list,
                key="admin_inspect_user_sel"
            )
            
            st.markdown(f"#### 📂 Active Tenant Database: `<tenant_{selected_user}>`")
            
            sub_tab_results, sub_tab_files, sub_tab_tests, sub_tab_saved, sub_tab_ai = st.tabs([
                "🎯 Quiz Results", 
                "📁 Uploaded Files", 
                "📝 Test Papers Analysis", 
                "📑 Saved Bookmarks & Notes", 
                "🤖 AI Reports & Esu Plans"
            ])
            
            # Sub-Tab: Quiz & Test Results
            with sub_tab_results:
                st.markdown(f"**Performance Analytics for `{selected_user}`**")
                from codeforces_visualizer import render_codeforces_dashboard
                from db import get_unified_test_records
                
                admin_exam_type = st.radio("Select Exam Type View:", ["🎯 Prelims", "✍️ Mains"], horizontal=True, key=f"adm_exam_{selected_user}")
                sel_e_type = "Prelims" if "Prelims" in admin_exam_type else "Mains"
                u_records = get_unified_test_records(username=selected_user, exam_type=sel_e_type)
                
                if not u_records:
                    st.info(f"No {sel_e_type} test results recorded yet for user '{selected_user}'.")
                else:
                    total_quizzes = len(u_records)
                    avg_marks = sum(r["marks"] for r in u_records) / total_quizzes
                    best_marks = max(r["marks"] for r in u_records)
                    avg_acc = sum(r["accuracy"] for r in u_records) / total_quizzes
                    
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Total Tests Attempted", total_quizzes)
                    m2.metric("Average Marks", f"{avg_marks:.1f}")
                    m3.metric("Highest Marks", f"{best_marks:.1f}")
                    
                    # Render Codeforces Graph & Heatmap for admin
                    render_codeforces_dashboard(u_records, exam_type=sel_e_type, username=selected_user)
                    
                    st.markdown("---")
                    res_rows = []
                    for r in reversed(u_records):
                        res_rows.append({
                            "Date": r["date"].strftime("%d %b %Y") if hasattr(r["date"], "strftime") else str(r["date"]),
                            "Test Name": r["name"],
                            "Source": r["source"],
                            "Total Questions": r["total_questions"],
                            "Attempted": r["attempted"],
                            "Correct": r["correct"],
                            "Wrong": r["wrong"],
                            "Accuracy (%)": f"{r['accuracy']:.1f}%",
                            "Marks": f"{r['marks']:.2f} / {int(r['total_marks'])}"
                        })
                    st.dataframe(pd.DataFrame(res_rows), use_container_width=True, hide_index=True)
            
            # Sub-Tab: Uploaded Files
            with sub_tab_files:
                st.markdown(f"**Files Uploaded by `{selected_user}`**")
                u_files = get_uploaded_files(username=selected_user)
                
                if not u_files:
                    st.info(f"No uploaded files recorded for user '{selected_user}'.")
                else:
                    st.write(f"Total uploaded files: **{len(u_files)}**")
                    for file_row in u_files:
                        fid, fname, fsize, ftype, fcontext, fuploaded = file_row
                        fsize_kb = round(fsize / 1024, 1) if fsize else 0
                        
                        with st.expander(f"📄 {fname} ({fsize_kb} KB) — Context: {fcontext or 'General'}", expanded=False):
                            col_info, col_actions = st.columns([3, 1])
                            with col_info:
                                st.write(f"**Uploaded At:** {fuploaded}")
                                st.write(f"**File Type:** {ftype}")
                                st.write(f"**Size:** {fsize_kb} KB ({fsize} bytes)")
                            
                            with col_actions:
                                f_name, f_bytes = get_uploaded_file_bytes(fid, username=selected_user)
                                if f_bytes:
                                    st.download_button(
                                        "📥 Download File",
                                        data=f_bytes,
                                        file_name=fname,
                                        mime="application/pdf" if ftype == "pdf" else "application/octet-stream",
                                        key=f"dl_file_{selected_user}_{fid}",
                                        use_container_width=True
                                    )
                                if st.button("🗑️ Delete File", key=f"del_f_{selected_user}_{fid}", use_container_width=True):
                                    if delete_uploaded_file(fid, username=selected_user):
                                        st.success(f"Deleted '{fname}'")
                                        safe_rerun()
            
            # Sub-Tab: Test Papers Analysis
            with sub_tab_tests:
                st.markdown(f"**Test Paper Analysis Entries for `{selected_user}`**")
                u_papers = get_test_papers(username=selected_user)
                
                if not u_papers:
                    st.info(f"No test paper analyses recorded for user '{selected_user}'.")
                else:
                    for p in u_papers:
                        pid, tname, tdate, tot_q, att, not_att, g_corr, g_incorr, notes, cat = p
                        with st.expander(f"📝 {tname} — Date: {tdate}", expanded=False):
                            c1, c2, c3, c4 = st.columns(4)
                            c1.metric("Total", tot_q)
                            c2.metric("Attempted", att)
                            c3.metric("Guessed Correct", g_corr)
                            c4.metric("Guessed Incorrect", g_incorr)
                            if notes:
                                st.markdown("**Remarks / Silly Mistakes Notes:**")
                                st.info(notes)
            
            # Sub-Tab: Saved Bookmarks & Notes
            with sub_tab_saved:
                st.markdown(f"**Saved Notes & Bookmarks for `{selected_user}`**")
                u_saved = get_saved_items(username=selected_user)
                
                if not u_saved:
                    st.info(f"No saved notes found for user '{selected_user}'.")
                else:
                    for item in u_saved:
                        iid, itype, icontent, itime = item
                        with st.expander(f"📌 [{itype}] Saved on {itime}", expanded=False):
                            st.text_area("Content", icontent, height=180, key=f"insp_saved_{selected_user}_{iid}")
            
            # Sub-Tab: AI Reports
            with sub_tab_ai:
                st.markdown(f"**AI Reports & Study Plans for `{selected_user}`**")
                u_reports = get_ai_reports(username=selected_user)
                
                if not u_reports:
                    st.info(f"No AI reports generated for user '{selected_user}'.")
                else:
                    for rep in u_reports:
                        rid, rtype, rperiod, rcontent, rtime = rep
                        with st.expander(f"🤖 {rtype} ({rperiod}) — {rtime}", expanded=False):
                            st.markdown(rcontent)
    
    # ════════════════════════════════════════════════════════════════════════════
    # TAB 2: PAGE ACCESS PERMISSIONS MANAGEMENT
    # ════════════════════════════════════════════════════════════════════════════
    with tab_perms:
        st.subheader("🔒 Page Access Permissions")
        st.markdown("Provide or remove access to specific pages for each user. Users will only see and access authorized pages.")
        
        if not user_list:
            st.info("No registered users found.")
        else:
            perm_user = st.selectbox("Select User to Manage Permissions:", user_list, key="perm_user_sel")
            
            if is_admin(perm_user):
                st.info(f"👑 **{perm_user}** is an Administrator and inherently has unrestricted access to all pages.")
            else:
                current_allowed = get_user_allowed_pages(perm_user)
                
                col_btn_all, col_btn_clear, _ = st.columns([1, 1, 2])
                with col_btn_all:
                    if st.button("✅ Grant All Pages", use_container_width=True, key=f"btn_grant_all_{perm_user}"):
                        set_user_allowed_pages(perm_user, list(ALL_AVAILABLE_PAGES))
                        st.success(f"Granted access to all pages for '{perm_user}'")
                        safe_rerun()
                with col_btn_clear:
                    if st.button("🚫 Revoke All Pages", use_container_width=True, key=f"btn_revoke_all_{perm_user}"):
                        set_user_allowed_pages(perm_user, [])
                        st.warning(f"Revoked all page access for '{perm_user}'")
                        safe_rerun()
                
                st.markdown("---")
                st.markdown(f"##### Configure Page Access for **{perm_user.capitalize()}**:")
                
                with st.form(f"perm_form_{perm_user}"):
                    selected_pages = []
                    
                    # Group into 2 columns for neat presentation
                    p_col1, p_col2 = st.columns(2)
                    half = len(ALL_AVAILABLE_PAGES) // 2
                    
                    with p_col1:
                        for page_name in ALL_AVAILABLE_PAGES[:half]:
                            is_checked = page_name in current_allowed
                            if st.checkbox(f"📄 {page_name}", value=is_checked, key=f"chk_{perm_user}_{page_name}"):
                                selected_pages.append(page_name)
                                
                    with p_col2:
                        for page_name in ALL_AVAILABLE_PAGES[half:]:
                            is_checked = page_name in current_allowed
                            if st.checkbox(f"📄 {page_name}", value=is_checked, key=f"chk_{perm_user}_{page_name}"):
                                selected_pages.append(page_name)
                                
                    save_perms_btn = st.form_submit_button("💾 Save Page Permissions", type="primary", use_container_width=True)
                    if save_perms_btn:
                        if set_user_allowed_pages(perm_user, selected_pages):
                            st.success(f"✅ Permissions successfully updated for **{perm_user}**! ({len(selected_pages)} pages enabled)")
                            safe_rerun()
                        else:
                            st.error("Failed to update page permissions.")
                            
                st.info(f"Active Permissions: {len(selected_pages if 'selected_pages' in locals() else current_allowed)} / {len(ALL_AVAILABLE_PAGES)} pages authorized.")
    
    # ════════════════════════════════════════════════════════════════════════════
    # TAB 3: USER ACCOUNTS MANAGEMENT
    # ════════════════════════════════════════════════════════════════════════════
    with tab_users:
        st.subheader("👥 Registered User Accounts")
        if users:
            df = pd.DataFrame(users, columns=["Username", "Role", "Active", "Has News Access", "Last Login", "Created At"])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.warning("No users found.")
        
        st.divider()
        
        # Add New User
        st.subheader("➕ Create New User Account")
        with st.form("add_user_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                new_username = st.text_input("Username").strip().lower()
            with col2:
                new_password = st.text_input("Password", type="password")
            with col3:
                new_role = st.selectbox("Role", ["user", "admin"])
                
            submit_add = st.form_submit_button("Create User", type="primary")
            if submit_add:
                if not new_username or not new_password:
                    st.error("Username and password are required.")
                else:
                    if add_user(new_username, new_password, new_role):
                        st.success(f"✅ User '{new_username}' created successfully!")
                        safe_rerun()
                    else:
                        st.error(f"Failed to create user. Username '{new_username}' might already exist.")
                        
        st.divider()
        
        # Modify Existing User
        st.subheader("⚙️ Account Controls")
        col_edit, col_del = st.columns(2)
        
        with col_edit:
            st.markdown("**Change Password / Toggle Active Status**")
            with st.form("edit_user_form"):
                edit_username = st.selectbox("Select User", user_list, key="edit_usr_sel")
                new_pass = st.text_input("New Password (leave empty to keep current)", type="password")
                
                b1, b2 = st.columns(2)
                with b1:
                    submit_pass = st.form_submit_button("Update Password")
                with b2:
                    submit_toggle = st.form_submit_button("Toggle Active")
                    
                if submit_pass:
                    if new_pass:
                        if update_user_password(edit_username, new_pass):
                            st.success(f"Password updated for '{edit_username}'")
                        else:
                            st.error("Failed to update password.")
                    else:
                        st.warning("Please enter a new password.")
                        
                if submit_toggle:
                    if toggle_user_active(edit_username):
                        st.success(f"Toggled active status for '{edit_username}'")
                        safe_rerun()
                    else:
                        st.error("Failed to toggle status.")
                        
        with col_del:
            st.markdown("**Delete Account**")
            with st.form("delete_user_form"):
                del_username = st.selectbox("Select User to Remove", user_list, key="del_usr_sel")
                st.warning("⚠️ Deleting will remove user account and credentials.")
                submit_delete = st.form_submit_button("Delete User", type="primary")
                
                if submit_delete:
                    if del_username == current_admin:
                        st.error("You cannot delete your own admin account!")
                    else:
                        if delete_user(del_username):
                            st.success(f"User '{del_username}' deleted.")
                            safe_rerun()
                        else:
                            st.error("Failed to delete user.")

    # ════════════════════════════════════════════════════════════════════════════
    # TAB 4: NEWS & SYSTEM SETTINGS
    # ════════════════════════════════════════════════════════════════════════════
    with tab_news:
        st.subheader("⚙️ News Sync & Access Requests")
        col_ns1, col_ns2 = st.columns(2)
        with col_ns1:
            current_limit = int(get_config("news_display_limit", "600"))
            new_limit = st.number_input("News Display Limit", min_value=50, max_value=2000, value=current_limit, step=50)
        with col_ns2:
            current_max = int(get_config("news_max_per_day", "40"))
            new_max = st.number_input("Max News Per Day", min_value=10, max_value=100, value=current_max, step=5)
            
        if st.button("💾 Save News Settings"):
            set_config("news_display_limit", str(new_limit))
            set_config("news_max_per_day", str(new_max))
            st.success("News settings updated successfully!")
            
        st.divider()
        
        st.subheader("🔐 Pending News Access Requests")
        requests = get_pending_access_requests()
        if not requests:
            st.info("No pending access requests.")
        else:
            for req in requests:
                req_id, req_user, req_time = req
                col_u, col_a, col_d = st.columns([3, 1, 1])
                with col_u:
                    st.write(f"**{req_user}** - requested on {req_time.strftime('%Y-%m-%d %H:%M')}")
                with col_a:
                    if st.button("✅ Approve", key=f"approve_{req_user}"):
                        resolve_access_request(req_user, True)
                        st.success(f"Granted access to {req_user}")
                        safe_rerun()
                with col_d:
                    if st.button("❌ Deny", key=f"deny_{req_user}"):
                        resolve_access_request(req_user, False)
                        st.success(f"Denied access to {req_user}")
                        safe_rerun()
                        
        st.divider()
        st.subheader("🗑️ Clear All News")
        st.warning("⚠️ This will permanently delete all fetched news articles from the database.")
        if st.button("🚨 CLEAR ALL NEWS NOW", type="primary"):
            if clear_all_news():
                st.success("All news has been cleared from the database.")
            else:
                st.error("Failed to clear news.")
