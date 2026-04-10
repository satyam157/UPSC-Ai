import streamlit as st
import pandas as pd
from db import (
    get_all_users, add_user, update_user_password, toggle_user_active, 
    delete_user, is_admin, get_config, set_config, clear_all_news, 
    set_news_access, get_pending_access_requests, resolve_access_request
)
from ui_components import safe_rerun

def show_admin_page():
    st.title("🛡️ Admin Panel - User Management")
    
    username = st.session_state.get("username", "")
    if not is_admin(username):
        st.error("Access Denied: You do not have admin privileges.")
        st.stop()
    
    st.markdown("Manage user access, roles, news settings, and view last login times.")
    st.divider()
    
    tab_users, tab_news = st.tabs(["👥 User Management", "📰 News & Access Settings"])
    
    with tab_users:
        # ─── USER LIST ──────────────────────────────────────────────────────────
        st.subheader("👥 Current Users")
        users = get_all_users()
        
        if not users:
            st.warning("No users found.")
        else:
            # Convert to DataFrame for nice display
            df = pd.DataFrame(users, columns=["Username", "Role", "Active", "Has News Access", "Last Login", "Created At"])
            st.dataframe(df, use_container_width=True, hide_index=True)
        
        st.divider()
    
    # ─── ADD NEW USER ────────────────────────────────────────────────────────
    st.subheader("➕ Add New User")
    with st.form("add_user_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            new_username = st.text_input("Username")
        with col2:
            new_password = st.text_input("Password", type="password")
        with col3:
            new_role = st.selectbox("Role", ["user", "admin"])
            
        submit_add = st.form_submit_button("Add User")
        
        if submit_add:
            if not new_username or not new_password:
                st.error("Username and password are required.")
            else:
                success = add_user(new_username, new_password, new_role)
                if success:
                    st.success(f"User '{new_username}' added successfully!")
                    safe_rerun()
                else:
                    st.error(f"Failed to add user. Username '{new_username}' might already exist.")
                    
    st.divider()
    
    # ─── MANAGE EXISTING USERS ───────────────────────────────────────────────
    st.subheader("⚙️ Manage Users")
    
    manage_col1, manage_col2 = st.columns(2)
    
    with manage_col1:
        st.markdown("**Change Password / Toggle Active**")
        with st.form("edit_user_form"):
            edit_username = st.selectbox("Select User", [u[0] for u in users], key="edit_user_sel")
            new_pass = st.text_input("New Password (leave blank to keep current)", type="password")
            
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                submit_pass = st.form_submit_button("Update Password")
            with col_b2:
                submit_toggle = st.form_submit_button("Toggle Active Status")
                
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
                    
        st.markdown("**Toggle News Access (Manual)**")
        with st.form("news_access_form"):
            access_username = st.selectbox("Select User", [u[0] for u in users], key="access_user_sel")
            
            # Find current access status
            current_access = False
            for u in users:
                if u[0] == access_username:
                    current_access = u[3]
                    break
                    
            st.write(f"Current Access: **{'Granted' if current_access else 'Denied'}**")
            
            col_a1, col_a2 = st.columns(2)
            with col_a1:
                submit_grant = st.form_submit_button("Grant Access", type="primary")
            with col_a2:
                submit_revoke = st.form_submit_button("Revoke Access")
                
            if submit_grant:
                if set_news_access(access_username, True):
                    st.success(f"Granted news access for '{access_username}'")
                    safe_rerun()
            if submit_revoke:
                if set_news_access(access_username, False):
                    st.success(f"Revoked news access for '{access_username}'")
                    safe_rerun()
                    
    with manage_col2:
        st.markdown("**Delete User**")
        with st.form("delete_user_form"):
            del_username = st.selectbox("Select User to Delete", [u[0] for u in users], key="del_user_sel")
            
            st.warning("⚠️ This action cannot be undone.")
            submit_delete = st.form_submit_button("Delete User", type="primary")
            
            if submit_delete:
                if del_username == username:
                    st.error("You cannot delete your own admin account!")
                else:
                    if delete_user(del_username):
                        st.success(f"User '{del_username}' deleted.")
                        safe_rerun()
                    else:
                        st.error("Failed to delete user.")

    with tab_news:
        st.subheader("⚙️ News Fetch Settings")
        col_ns1, col_ns2 = st.columns(2)
        with col_ns1:
            current_limit = int(get_config("news_display_limit", "600"))
            new_limit = st.number_input("News Display Limit", min_value=50, max_value=2000, value=current_limit, step=50, help="Max number of news articles shown in the feed")
        with col_ns2:
            current_max = int(get_config("news_max_per_day", "40"))
            new_max = st.number_input("Max News Per Day", min_value=10, max_value=100, value=current_max, step=5, help="Number of regular news items kept per day after trimming")
            
        if st.button("💾 Save News Settings"):
            set_config("news_display_limit", str(new_limit))
            set_config("news_max_per_day", str(new_max))
            st.success("News settings updated successfully!")
            
        st.divider()
        
        st.subheader("🔐 Pending Access Requests")
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
        st.warning("⚠️ This will permanently delete all fetched news articles from the database. It cannot be undone.")
        if st.button("🚨 CLEAR ALL NEWS NOW", type="primary"):
            if clear_all_news():
                st.success("All news has been cleared from the database.")
            else:
                st.error("Failed to clear news.")
