import streamlit as st
import json
from datetime import date, timedelta
from ui_components import safe_rerun, clear_state
from db import (
    get_quiz_streaks, get_available_news_dates, get_news_by_date_range, 
    save_quiz_streak, save_result, save_item, get_saved_items, delete_saved_item
)
from quiz_generator import generate_quiz
from quiz_engine import evaluate
from pdf_utils import generate_pdf

def show_ca_quiz_page():
    username = st.session_state["username"]
    today = date.today()

    # ── STREAK CALENDAR ───────────────────────────────────────────────────────
    streak_rows = get_quiz_streaks(username, quiz_type="CA Quiz", days=90)
    streak_map = {str(r[0]): r[1] for r in streak_rows}   # date_str → score_pct

    # Compute current streak
    current_streak = 0
    check = today
    while str(check) in streak_map:
        current_streak += 1
        check -= timedelta(days=1)

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1e1b4b,#312e81);border:1px solid #4f46e5;
                border-radius:14px;padding:16px 22px;margin-bottom:18px;display:flex;
                align-items:center;gap:24px;">
      <div style="text-align:center;">
        <div style="font-size:36px;font-weight:800;color:#fbbf24;">🔥 {current_streak}</div>
        <div style="color:#a5b4fc;font-size:12px;font-weight:600;">Day Streak</div>
      </div>
      <div style="flex:1;">
        <div style="color:#e2e8f0;font-weight:700;font-size:15px;margin-bottom:4px;">
          Quiz Activity — Last 90 Days
        </div>
        <div style="color:#94a3b8;font-size:12px;">
          🟩 ≥70% correct &nbsp; 🟨 50–69% &nbsp; 🟥 &lt;50% &nbsp; ⬛ no quiz
        </div>
      </div>
      <div style="text-align:center;">
        <div style="font-size:22px;font-weight:800;color:#34d399;">{len(streak_map)}</div>
        <div style="color:#a5b4fc;font-size:12px;font-weight:600;">Total Days</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Build calendar grid
    cal_end = today
    cal_start = cal_end - timedelta(days=89)
    cal_start = cal_start - timedelta(days=cal_start.weekday())

    weeks = []
    cur = cal_start
    week = []
    while cur <= cal_end + timedelta(days=(6 - cal_end.weekday())):
        week.append(cur)
        if cur.weekday() == 6:
            weeks.append(week)
            week = []
        cur += timedelta(days=1)
    if week:
        weeks.append(week)

    day_names = ["Mo","Tu","We","Th","Fr","Sa","Su"]
    cal_html = '<div style="overflow-x:auto;margin-bottom:10px;">'
    cal_html += '<table style="border-collapse:separate;border-spacing:3px;">'
    cal_html += '<tr><td style="color:#64748b;font-size:10px;width:24px;"></td>'
    for dn in day_names:
        cal_html += f'<td style="color:#64748b;font-size:10px;text-align:center;width:16px;">{dn}</td>'
    cal_html += '</tr><tr><td></td>'
    for week in weeks:
        month_lbl = ""
        for d in week:
            if d.day == 1:
                month_lbl = d.strftime("%b")
                break
        cal_html += f'<td colspan="1" style="color:#94a3b8;font-size:9px;text-align:center;">{month_lbl}</td>'
    cal_html += '</tr>'

    for dow in range(7):
        cal_html += f'<tr><td style="color:#64748b;font-size:9px;padding-right:3px;">{day_names[dow]}</td>'
        for week in weeks:
            if dow < len(week):
                d = week[dow]
                ds = str(d)
                if d > today:
                    color = "#1e1e2e"
                    title = ""
                elif ds in streak_map:
                    sc = streak_map[ds]
                    if sc >= 70: color = "#16a34a"
                    elif sc >= 50: color = "#ca8a04"
                    else: color = "#dc2626"
                    title = f"{ds}: {sc:.0f}%"
                else:
                    color = "#374151"
                    title = ds
                cal_html += f'<td title="{title}" style="width:14px;height:14px;background:{color};border-radius:3px;"></td>'
            else:
                cal_html += '<td></td>'
        cal_html += '</tr>'
    cal_html += '</table></div>'
    st.markdown(cal_html, unsafe_allow_html=True)

    st.markdown("---")

    # ── DATE RANGE PICKER ─────────────────────────────────────────────────────
    st.markdown("### 📅 Select Date Range for Quiz")
    range_mode = st.radio(
        "Range Mode",
        ["Today", "Last 7 Days", "This Month", "This Year", "Custom Range"],
        horizontal=True,
        key="ca_range_mode"
    )

    if range_mode == "Today":
        q_start = q_end = today
        range_label = f"Today ({today})"
    elif range_mode == "Last 7 Days":
        q_start = today - timedelta(days=6)
        q_end = today
        range_label = f"Last 7 Days ({q_start} → {q_end})"
    elif range_mode == "This Month":
        q_start = today.replace(day=1)
        q_end = today
        range_label = f"{today.strftime('%B %Y')} ({q_start} → {q_end})"
    elif range_mode == "This Year":
        q_start = today.replace(month=1, day=1)
        q_end = today
        range_label = f"Year {today.year} ({q_start} → {q_end})"
    else:  # Custom Range
        col_cs, col_ce = st.columns(2)
        with col_cs:
            q_start = st.date_input("From Date", value=today - timedelta(days=6), key="ca_custom_start")
        with col_ce:
            q_end = st.date_input("To Date", value=today, key="ca_custom_end")
        range_label = f"Custom ({q_start} → {q_end})"

    filtered_news = get_news_by_date_range(q_start, q_end)
    count_in_range = len(filtered_news)
    if count_in_range > 0:
        st.success(f"✅ **{count_in_range} news items** found for {range_label}")
    else:
        st.warning(f"⚠️ No news in DB for {range_label}. Use **AI CA Test** page for AI-generated quiz.")

    # ── GENERATE QUIZ ─────────────────────────────────────────────────────────
    if st.button("🎯 Generate Quiz for Selected Range", type="primary", use_container_width=True):
        if not filtered_news:
            st.error("No news data available for the selected date range.")
        else:
            sorted_news = sorted(filtered_news, key=lambda x: x[2], reverse=True)
            text = "\n".join([x[0] for x in sorted_news[:30]])
            
            # Integrate Ask Esu subjects if available
            focus_subjs = st.session_state.get("esu_detected_subjects", [])
            subj_context = f" (Focus: {', '.join(focus_subjs)})" if focus_subjs else ""
            
            with st.spinner(f"🤖 Generating UPSC-quality quiz{subj_context}…"):
                q, a = generate_quiz(text, n=5, subject=", ".join(focus_subjs) if focus_subjs else None)
            
            st.session_state["ca_q"] = q
            st.session_state["ca_a"] = a
            st.session_state["ca_range_label"] = range_label + subj_context
            st.session_state["ca_submitted"] = False
            # Save structured JSON for history with Show Answer support
            quiz_data = {
                "label": f"CA Quiz [{range_label}]{subj_context}",
                "questions": [
                    {"question": quest, "answer": ans}
                    for quest, ans in zip(q, a)
                ]
            }
            save_item("CA Quiz", json.dumps(quiz_data))
            safe_rerun()

    # ── QUIZ ATTEMPT ──────────────────────────────────────────────────────────
    if "ca_q" in st.session_state and not st.session_state.get("ca_submitted"):
        st.markdown(f"#### 📝 Quiz — {st.session_state.get('ca_range_label','')}")
        st.caption("Questions are UPSC Prelims style.")
        st.markdown("---")
        user_ans_ca = []
        for i, q_full in enumerate(st.session_state["ca_q"]):
            lines = q_full.split("\n")
            opt_start_idx = next((j for j, ln in enumerate(lines) if ln.strip().startswith(("A)", "B)", "C)", "D)"))), len(lines))
            q_body = "\n".join(lines[:opt_start_idx]).strip()
            opts_display = [ln.strip() for ln in lines[opt_start_idx:] if ln.strip()]

            st.markdown(
                f'<div style="background:#1a1a2e;border-left:3px solid #6366f1;'
                f'padding:12px 16px;margin:14px 0 6px 0;border-radius:6px;">'
                f'<span style="color:#a5b4fc;font-size:12px;font-weight:600;">Q{i+1}</span>'
                f'<p style="color:#e2e8f0;margin:6px 0 0 0;font-size:15px;'
                f'white-space:pre-wrap;">{q_body}</p></div>',
                unsafe_allow_html=True
            )
            radio_opts = opts_display if opts_display else ["A", "B", "C", "D"]
            user_ans_ca.append(st.radio("", radio_opts, key=f"ca_ans_{i}", label_visibility="collapsed", index=None))
            st.divider()

        if st.button("✅ Submit CA Quiz", type="primary", use_container_width=True):
            import re as _re
            norm_ans = []
            for ua in user_ans_ca:
                if ua is None: norm_ans.append(None)
                else:
                    m = _re.match(r'^([A-D])', str(ua).strip())
                    norm_ans.append(m.group(1) if m else ua[:1].upper())

            correct = sum(u == c for u, c in zip(norm_ans, st.session_state["ca_a"]) if u)
            total_q = len(st.session_state["ca_a"])
            score_pct = round(correct / total_q * 100, 1) if total_q else 0
            st.session_state["ca_submitted"] = True
            st.session_state["ca_score"] = (correct, total_q, score_pct)
            st.session_state["ca_user_ans"] = norm_ans
            save_quiz_streak(username, "CA Quiz", today, score_pct)
            res = evaluate(norm_ans, st.session_state["ca_a"])
            save_result(("CA_1", *res))
            
            content = ""
            for i, (u, c) in enumerate(zip(norm_ans, st.session_state["ca_a"])):
                content += f"Q{i+1}: Your={u or 'Skipped'}, Correct={c}\n"
            pdf = generate_pdf(content)
            st.session_state["ca_pdf"] = pdf
            safe_rerun()

    if st.session_state.get("ca_submitted"):
        correct, total_q, score_pct = st.session_state["ca_score"]
        color = "#34d399" if score_pct >= 70 else "#fbbf24" if score_pct >= 50 else "#f87171"
        wrong = total_q - correct
        upsc_marks = round(correct * 2 - wrong * 0.66, 2)
        st.markdown(f"""
        <div style="background:#16162a;border:2px solid {color};border-radius:14px;
                    padding:22px;text-align:center;margin:14px 0;">
          <div style="font-size:36px;font-weight:800;color:{color};">{score_pct:.1f}%</div>
          <div style="color:#e2e8f0;margin-top:6px;font-size:16px;">{correct} / {total_q} correct</div>
          <div style="color:#94a3b8;margin-top:4px;font-size:13px;">
            UPSC Marks: <b style="color:{color};">{upsc_marks}</b>
            &nbsp;(+2 correct, −0.66 wrong)
          </div>
        </div>
        """, unsafe_allow_html=True)
        st.subheader("📖 Answer Review")
        user_ans_ca = st.session_state.get("ca_user_ans", [])
        for i, (u, c) in enumerate(zip(user_ans_ca, st.session_state["ca_a"])):
            is_correct = (u == c)
            icon = "✅" if is_correct else "❌"
            q_lines = st.session_state["ca_q"][i].split("\n")
            q_preview = q_lines[0][:90] + ("…" if len(q_lines[0]) > 90 else "")
            with st.expander(f"{icon} Q{i+1}. {q_preview}", expanded=not is_correct):
                st.markdown(f"**Full Question:**")
                st.markdown(st.session_state["ca_q"][i])
                st.markdown(f"**Your answer:** `{u or 'Skipped'}` &nbsp;|&nbsp; **Correct:** `{c}`", unsafe_allow_html=True)
        
        pdf_path = st.session_state.get("ca_pdf")
        if pdf_path:
            st.download_button("📥 Download PDF", open(pdf_path, "rb"), file_name="CA_Quiz.pdf")
        if st.button("🔄 New Quiz"):
            for k in ["ca_q","ca_a","ca_submitted","ca_score","ca_user_ans","ca_pdf","ca_range_label"]:
                st.session_state.pop(k, None)
            safe_rerun()

    # ── History ───────────────────────────────────────────────────────────────
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

            col_header, col_close = st.columns([20, 1])
            with col_close:
                st.button("✕", key=f"x_ca_{item_id}", on_click=clear_state, args=("sel_ca",))

            # Try to parse as structured JSON (new format)
            parsed = None
            try:
                parsed = json.loads(content)
            except (json.JSONDecodeError, TypeError):
                pass

            if parsed and isinstance(parsed, dict) and "questions" in parsed:
                # ── Structured format: render each question with Show Answer ──
                label = parsed.get("label", "CA Quiz")
                st.markdown(f"**{label}**")
                for qi, qdata in enumerate(parsed["questions"]):
                    q_text = qdata.get("question", "")
                    ans = qdata.get("answer", "")

                    # Split question body from options
                    lines = q_text.split("\n")
                    opt_start = next(
                        (j for j, ln in enumerate(lines)
                         if ln.strip().startswith(("A)", "B)", "C)", "D)"))),
                        len(lines)
                    )
                    q_body = "\n".join(lines[:opt_start]).strip()
                    opts_lines = [ln.strip() for ln in lines[opt_start:] if ln.strip()]

                    # Question card
                    st.markdown(
                        f'<div style="background:#1a1a2e;border-left:3px solid #6366f1;'
                        f'padding:10px 14px;margin:10px 0 4px 0;border-radius:6px;">'
                        f'<span style="color:#a5b4fc;font-size:12px;font-weight:600;">Q{qi+1}</span>'
                        f'<p style="color:#e2e8f0;margin:4px 0 0 0;font-size:14px;'
                        f'white-space:pre-wrap;">{q_body}</p></div>',
                        unsafe_allow_html=True
                    )
                    if opts_lines:
                        for ol in opts_lines:
                            st.markdown(f"&nbsp;&nbsp;&nbsp;{ol}")

                    with st.expander(f"📖 Show Answer — Q{qi+1}", expanded=False):
                        st.markdown(f"**✅ Correct Answer: `{ans}`**")
                        # Highlight the correct option if we can find it
                        for ol in opts_lines:
                            if ol.startswith(f"{ans})"):
                                st.success(f"{ol}")
                                break
            else:
                # ── Legacy plain-text format: show as-is ─────────────────────
                st.text_area("Content", content, height=280, key=f"ta_ca_{item_id}")

            if st.button("🗑️ Remove", key=f"del_ca_{item_id}"):
                delete_saved_item(item_id)
                safe_rerun()
    else:
        st.info("No previous CA Quiz items found.")
