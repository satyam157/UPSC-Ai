import streamlit as st
import json
from datetime import datetime
from ui_components import safe_rerun
from db import get_news, save_item, get_saved_items, delete_saved_item
from pyq_engine import generate_full_pyq_session, generate_batch_elaborative_solutions

def show_practice_page():
    st.subheader("📜 PYQ Practice — Prelims & Mains")
    st.caption("Generate Previous Year Questions linked to today's current affairs with **elaborative solutions**.")

    if "pyq_prelims" not in st.session_state:
        st.session_state["pyq_prelims"] = None
    if "pyq_mains" not in st.session_state:
        st.session_state["pyq_mains"] = None
    if "pyq_submitted" not in st.session_state:
        st.session_state["pyq_submitted"] = False
    if "pyq_user_answers" not in st.session_state:
        st.session_state["pyq_user_answers"] = {}
    if "pyq_elaborative" not in st.session_state:
        st.session_state["pyq_elaborative"] = None
    
    col_range, col_info = st.columns([2, 3])
    with col_range:
        time_range = st.selectbox("🎯 Select Practice Scope", ["Day", "Week", "Month", "Year"])
    
    range_map = {"Day": (15, 7), "Week": (30, 14), "Month": (50, 25), "Year": (90, 60)}
    p_count, m_count = range_map[time_range]
    
    with col_info:
        st.info(f"✨ Generating **{p_count} Prelims** & **{m_count} Mains** questions with elaborative solutions.")

    if st.button("🚀 Generate PYQ Practice Set", type="primary", use_container_width=True):
        news_data = get_news()
        data_news = [x[0] for x in news_data]
        if not data_news:
            st.warning("No current affairs data. Please refresh the feed first.")
        else:
            # Integrate Ask Esu subjects if available
            focus_subjs = st.session_state.get("esu_detected_subjects", [])
            subj_context = f" (Focus: {', '.join(focus_subjs)})" if focus_subjs else ""
            
            with st.spinner(f"🤖 AI is analyzing {time_range} context{subj_context}..."):
                # We update the headlines to include the focus subjects as a preference
                context_news = data_news
                if focus_subjs:
                    context_news = [f"[Focus Subject: {s}]" for s in focus_subjs] + data_news
                
                result = generate_full_pyq_session(context_news, prelims_count=p_count, mains_count=m_count)
                st.session_state["pyq_prelims"] = result.get("prelims", [])
                st.session_state["pyq_mains"] = result.get("mains", [])
                st.session_state["pyq_submitted"] = False
                st.session_state["pyq_user_answers"] = {}
                st.session_state["pyq_elaborative"] = None
                
                # Save structured JSON for history with Show Answer support
                quiz_data = {
                    "label": f"Practice Set — {time_range}{subj_context} — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    "prelims": result.get("prelims", []),
                    "mains": result.get("mains", []),
                }
                save_item("Practice", json.dumps(quiz_data, default=str))
                safe_rerun()

    tab_prelims, tab_mains, tab_history = st.tabs(["📝 Prelims PYQ Quiz", "✍️ Mains PYQ Practice", "📂 History"])
    
    with tab_prelims:
        prelims_data = st.session_state["pyq_prelims"]
        if prelims_data:
            if not st.session_state["pyq_submitted"]:
                # ── QUIZ MODE: Answer questions ──────────────────────────────
                for i, pq in enumerate(prelims_data):
                    # Question card with metadata
                    theme = pq.get("theme", "General Studies")
                    difficulty = pq.get("difficulty", "Medium")
                    q_type = pq.get("question_type", "MCQ")
                    year = pq.get("year", "Predicted")
                    
                    diff_color = "#f87171" if difficulty == "Hard" else "#fbbf24"
                    year_color = "#34d399" if year != "Predicted" else "#94a3b8"
                    
                    st.markdown(f"""
                    <div style="background:#1a1a2e;border-left:3px solid #6366f1;
                                padding:14px 18px;margin:16px 0 8px 0;border-radius:8px;">
                      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                        <span style="color:#a5b4fc;font-size:12px;font-weight:700;">Q{i+1} • {theme}</span>
                        <span>
                          <span style="background:{diff_color}22;color:{diff_color};padding:2px 8px;
                                       border-radius:4px;font-size:11px;font-weight:600;margin-right:6px;">{difficulty}</span>
                          <span style="background:{year_color}22;color:{year_color};padding:2px 8px;
                                       border-radius:4px;font-size:11px;font-weight:600;">{year}</span>
                          <span style="background:#6366f122;color:#a5b4fc;padding:2px 8px;
                                       border-radius:4px;font-size:11px;font-weight:600;margin-left:6px;">{q_type}</span>
                        </span>
                      </div>
                      <p style="color:#e2e8f0;margin:0;font-size:15px;white-space:pre-wrap;">{pq['question']}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    opts = pq["options"]
                    sel = st.radio(
                        "Select:", 
                        [f"{k}) {v}" for k, v in opts.items()], 
                        key=f"pyq_ans_{i}", 
                        index=None,
                        label_visibility="collapsed"
                    )
                    st.divider()
                
                if st.button("✅ Submit Prelims Answers", type="primary", use_container_width=True):
                    user_answers = {}
                    for i in range(len(prelims_data)):
                        sel = st.session_state.get(f"pyq_ans_{i}")
                        if sel:
                            user_answers[i] = sel[0]  # Extract letter (A/B/C/D)
                        else:
                            user_answers[i] = None
                    
                    st.session_state["pyq_user_answers"] = user_answers
                    st.session_state["pyq_submitted"] = True
                    
                    # Generate elaborative solutions for review
                    with st.spinner("🔍 Generating elaborative solutions for each question..."):
                        try:
                            solutions = generate_batch_elaborative_solutions(prelims_data)
                            st.session_state["pyq_elaborative"] = solutions
                        except Exception as e:
                            print(f"Elaborative solutions error: {e}")
                            st.session_state["pyq_elaborative"] = None
                    
                    safe_rerun()
            else:
                # ── REVIEW MODE: Show results with elaborative solutions ─────
                user_answers = st.session_state["pyq_user_answers"]
                elaborative = st.session_state.get("pyq_elaborative") or []
                
                # Score calculation
                correct_count = 0
                attempted = 0
                for i, pq in enumerate(prelims_data):
                    ua = user_answers.get(i)
                    if ua is not None:
                        attempted += 1
                        if ua == pq["correct_answer"]:
                            correct_count += 1
                
                wrong = attempted - correct_count
                score_pct = round(correct_count / len(prelims_data) * 100, 1) if prelims_data else 0
                upsc_marks = round(correct_count * 2 - wrong * 0.66, 2)
                color = "#34d399" if score_pct >= 70 else "#fbbf24" if score_pct >= 50 else "#f87171"
                
                # Score card
                st.markdown(f"""
                <div style="background:#16162a;border:2px solid {color};border-radius:14px;
                            padding:22px;text-align:center;margin:14px 0;">
                  <div style="font-size:36px;font-weight:800;color:{color};">{score_pct:.1f}%</div>
                  <div style="color:#e2e8f0;margin-top:6px;font-size:16px;">{correct_count} / {len(prelims_data)} correct</div>
                  <div style="color:#94a3b8;margin-top:4px;font-size:13px;">
                    UPSC Marks: <b style="color:{color};">{upsc_marks}</b>
                    &nbsp;(+2 correct, −0.66 wrong, {len(prelims_data) - attempted} unattempted)
                  </div>
                </div>
                """, unsafe_allow_html=True)
                
                st.subheader("📖 Elaborative Answer Review")
                
                for i, pq in enumerate(prelims_data):
                    ua = user_answers.get(i)
                    ca = pq["correct_answer"]
                    is_correct = (ua == ca)
                    icon = "✅" if is_correct else ("⏭️" if ua is None else "❌")
                    
                    q_preview = pq["question"][:80] + ("…" if len(pq["question"]) > 80 else "")
                    
                    with st.expander(f"{icon} Q{i+1}. {q_preview}", expanded=not is_correct):
                        # Question
                        st.markdown(f"**Question:** {pq['question']}")
                        
                        # Options with color coding
                        for letter, opt_text in pq["options"].items():
                            if letter == ca:
                                st.markdown(f"✅ **{letter}) {opt_text}**")
                            elif letter == ua and ua != ca:
                                st.markdown(f"❌ ~~{letter}) {opt_text}~~")
                            else:
                                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;{letter}) {opt_text}")
                        
                        st.markdown(f"**Your answer:** `{ua or 'Skipped'}` &nbsp;|&nbsp; **Correct:** `{ca}`")
                        
                        # Basic explanation (from question generation)
                        if pq.get("explanation"):
                            st.markdown("---")
                            st.markdown(f"**📋 Explanation:** {pq['explanation']}")
                        
                        # Per-option analysis (from question generation)
                        opt_expl = pq.get("option_explanations", {})
                        if any(opt_expl.values()):
                            st.markdown("**🔍 Option-by-Option Analysis:**")
                            for letter in ["A", "B", "C", "D"]:
                                if opt_expl.get(letter):
                                    prefix = "✅" if letter == ca else "❌"
                                    st.markdown(f"&nbsp;&nbsp;{prefix} **{letter}:** {opt_expl[letter]}")
                        
                        # Elaborative solution (from batch generation)
                        if i < len(elaborative) and elaborative[i]:
                            elab = elaborative[i]
                            
                            if elab.get("detailed_explanation"):
                                st.markdown("---")
                                st.markdown("**📚 Detailed Elaboration:**")
                                st.markdown(elab["detailed_explanation"])
                            
                            if elab.get("source_references"):
                                refs = elab["source_references"]
                                if isinstance(refs, list) and refs:
                                    st.markdown("**📖 Sources:** " + " • ".join(refs))
                            
                            if elab.get("ncert_link"):
                                st.markdown(f"**📘 NCERT Link:** {elab['ncert_link']}")
                            
                            if elab.get("current_affairs_link"):
                                st.markdown(f"**📰 CA Link:** {elab['current_affairs_link']}")
                            
                            if elab.get("revision_note"):
                                st.markdown(f"**💡 Remember:** {elab['revision_note']}")
                        
                        # Source references from question generation
                        if pq.get("source_references"):
                            refs = pq["source_references"]
                            if isinstance(refs, list) and refs:
                                st.markdown(f"**📖 References:** {' • '.join(refs)}")
                        
                        if pq.get("static_link"):
                            st.markdown(f"**📘 Static Link:** {pq['static_link']}")
                        
                        if pq.get("current_affairs_link"):
                            st.markdown(f"**📰 Current Affairs:** {pq['current_affairs_link']}")
                        
                        if pq.get("revision_note"):
                            st.markdown(f"**💡 Revision Note:** {pq['revision_note']}")
                
                if st.button("🔄 New Practice Set", use_container_width=True):
                    for k in ["pyq_prelims", "pyq_mains", "pyq_submitted", 
                              "pyq_user_answers", "pyq_elaborative"]:
                        st.session_state.pop(k, None)
                    # Clear radio button states
                    for k in list(st.session_state.keys()):
                        if k.startswith("pyq_ans_"):
                            del st.session_state[k]
                    safe_rerun()
        else:
            st.info("Click **🚀 Generate PYQ Practice Set** above to get started.")

    with tab_mains:
        mains_data = st.session_state["pyq_mains"]
        if mains_data:
            for i, mq in enumerate(mains_data):
                # Mains question card with metadata
                paper = mq.get("paper", "General Studies")
                marks = mq.get("marks", 15)
                word_limit = mq.get("word_limit", 250)
                theme = mq.get("theme", "")
                year = mq.get("year", "Predicted")
                
                year_badge = f'<span style="color:#34d399;font-weight:600;">{year}</span>' if year != "Predicted" else '<span style="color:#94a3b8;">Predicted</span>'
                
                st.markdown(f"""
                <div style="background:#1a1a2e;border-left:3px solid #8b5cf6;
                            padding:14px 18px;margin:16px 0 8px 0;border-radius:8px;">
                  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                    <span style="color:#c4b5fd;font-size:12px;font-weight:700;">Q{i+1} • {paper} • {theme}</span>
                    <span style="color:#94a3b8;font-size:11px;">
                      {marks} marks • {word_limit} words • {year_badge}
                    </span>
                  </div>
                  <p style="color:#e2e8f0;margin:0;font-size:15px;line-height:1.6;">{mq['question']}</p>
                </div>
                """, unsafe_allow_html=True)
                
                with st.expander("📝 Show Elaborative Model Answer", expanded=False):
                    model_answer = mq.get("model_answer", "No answer provided.")
                    st.markdown(model_answer)
                    
                    # Key terms
                    if mq.get("key_terms"):
                        terms = mq["key_terms"]
                        if isinstance(terms, list) and terms:
                            st.markdown("**🏷️ Key Terms:** " + " • ".join(f"`{t}`" for t in terms))
                    
                    # Related articles/provisions
                    if mq.get("related_articles"):
                        arts = mq["related_articles"]
                        if isinstance(arts, list) and arts:
                            st.markdown("**📜 Related:** " + " • ".join(arts))
                    
                    # Source references
                    if mq.get("source_references"):
                        refs = mq["source_references"]
                        if isinstance(refs, list) and refs:
                            st.markdown("**📖 Sources:** " + " • ".join(refs))
                    
                    # Answer strategy
                    if mq.get("answer_strategy"):
                        st.markdown(f"**🎯 Strategy:** {mq['answer_strategy']}")
                    
                    # Common mistakes
                    if mq.get("common_mistakes"):
                        st.markdown(f"**⚠️ Common Mistakes:** {mq['common_mistakes']}")
                
                st.divider()
        else:
            st.info("Click **🚀 Generate PYQ Practice Set** above to get started.")

    with tab_history:
        st.caption("Previous practice sessions are saved with full questions & answers.")
        saved_items = get_saved_items()
        practice_items = [item for item in saved_items if item[1] == "Practice"]
        if practice_items:
            options = [f"Practice — {item[3]}" for item in practice_items[:15]]
            selected_hist = st.selectbox(
                "Select a previous practice set", [""] + options,
                key="sel_practice_hist"
            )
            if selected_hist:
                hist_idx = options.index(selected_hist)
                hist_item = practice_items[hist_idx]
                item_id = hist_item[0]
                content = hist_item[2]

                # Try to parse structured JSON
                parsed = None
                try:
                    parsed = json.loads(content)
                except (json.JSONDecodeError, TypeError):
                    pass

                if parsed and isinstance(parsed, dict) and ("prelims" in parsed or "mains" in parsed):
                    label = parsed.get("label", "Practice Set")
                    st.markdown(f"### 📜 {label}")

                    hist_prelims = parsed.get("prelims", [])
                    hist_mains = parsed.get("mains", [])

                    htab_p, htab_m = st.tabs([
                        f"📝 Prelims ({len(hist_prelims)})",
                        f"✍️ Mains ({len(hist_mains)})"
                    ])

                    with htab_p:
                        if hist_prelims:
                            for qi, pq in enumerate(hist_prelims):
                                q_text = pq.get("question", "")
                                correct = pq.get("correct_answer", "")
                                theme = pq.get("theme", "")
                                difficulty = pq.get("difficulty", "Medium")
                                year = pq.get("year", "Predicted")
                                q_type = pq.get("question_type", "MCQ")

                                diff_color = "#f87171" if difficulty == "Hard" else "#fbbf24"

                                st.markdown(
                                    f'<div style="background:#1a1a2e;border-left:3px solid #6366f1;'
                                    f'padding:10px 14px;margin:10px 0 4px 0;border-radius:6px;">'
                                    f'<div style="display:flex;justify-content:space-between;margin-bottom:4px;">'
                                    f'<span style="color:#a5b4fc;font-size:12px;font-weight:600;">Q{qi+1} • {theme}</span>'
                                    f'<span style="color:{diff_color};font-size:11px;font-weight:600;">{difficulty} • {year} • {q_type}</span>'
                                    f'</div>'
                                    f'<p style="color:#e2e8f0;margin:0;font-size:14px;'
                                    f'white-space:pre-wrap;">{q_text}</p></div>',
                                    unsafe_allow_html=True
                                )

                                # Display options
                                opts = pq.get("options", {})
                                if opts:
                                    for letter, opt_text in opts.items():
                                        st.markdown(f"&nbsp;&nbsp;&nbsp;{letter}) {opt_text}")

                                with st.expander(f"📖 Show Answer — Q{qi+1}", expanded=False):
                                    st.markdown(f"**✅ Correct Answer: `{correct}`**")
                                    # Highlight correct option
                                    if opts and correct in opts:
                                        st.success(f"{correct}) {opts[correct]}")

                                    if pq.get("explanation"):
                                        st.markdown(f"**📋 Explanation:** {pq['explanation']}")

                                    opt_expl = pq.get("option_explanations", {})
                                    if any(v for v in opt_expl.values() if v):
                                        st.markdown("**🔍 Option Analysis:**")
                                        for letter in ["A", "B", "C", "D"]:
                                            if opt_expl.get(letter):
                                                prefix = "✅" if letter == correct else "❌"
                                                st.markdown(f"&nbsp;&nbsp;{prefix} **{letter}:** {opt_expl[letter]}")

                                    if pq.get("source_references"):
                                        refs = pq["source_references"]
                                        if isinstance(refs, list) and refs:
                                            st.markdown("**📖 Sources:** " + " • ".join(refs))

                                    if pq.get("static_link"):
                                        st.markdown(f"**📘 Static Link:** {pq['static_link']}")

                                    if pq.get("current_affairs_link"):
                                        st.markdown(f"**📰 CA Link:** {pq['current_affairs_link']}")

                                    if pq.get("revision_note"):
                                        st.markdown(f"**💡 Remember:** {pq['revision_note']}")

                        else:
                            st.info("No Prelims questions in this set.")

                    with htab_m:
                        if hist_mains:
                            for qi, mq in enumerate(hist_mains):
                                paper = mq.get("paper", "General Studies")
                                marks = mq.get("marks", 15)
                                word_limit = mq.get("word_limit", 250)
                                theme = mq.get("theme", "")
                                year = mq.get("year", "Predicted")

                                st.markdown(
                                    f'<div style="background:#1a1a2e;border-left:3px solid #8b5cf6;'
                                    f'padding:10px 14px;margin:10px 0 4px 0;border-radius:6px;">'
                                    f'<div style="display:flex;justify-content:space-between;margin-bottom:4px;">'
                                    f'<span style="color:#c4b5fd;font-size:12px;font-weight:600;">Q{qi+1} • {paper} • {theme}</span>'
                                    f'<span style="color:#94a3b8;font-size:11px;">{marks}m • {word_limit}w • {year}</span>'
                                    f'</div>'
                                    f'<p style="color:#e2e8f0;margin:0;font-size:14px;line-height:1.6;">{mq["question"]}</p></div>',
                                    unsafe_allow_html=True
                                )

                                with st.expander(f"📖 Show Model Answer — Q{qi+1}", expanded=False):
                                    ma = mq.get("model_answer", "No answer provided.")
                                    st.markdown(ma)

                                    if mq.get("key_terms"):
                                        terms = mq["key_terms"]
                                        if isinstance(terms, list) and terms:
                                            st.markdown("**🏷️ Key Terms:** " + " • ".join(f"`{t}`" for t in terms))

                                    if mq.get("related_articles"):
                                        arts = mq["related_articles"]
                                        if isinstance(arts, list) and arts:
                                            st.markdown("**📜 Related:** " + " • ".join(arts))

                                    if mq.get("source_references"):
                                        refs = mq["source_references"]
                                        if isinstance(refs, list) and refs:
                                            st.markdown("**📖 Sources:** " + " • ".join(refs))

                                    if mq.get("answer_strategy"):
                                        st.markdown(f"**🎯 Strategy:** {mq['answer_strategy']}")

                                    if mq.get("common_mistakes"):
                                        st.markdown(f"**⚠️ Common Mistakes:** {mq['common_mistakes']}")
                        else:
                            st.info("No Mains questions in this set.")
                else:
                    # Legacy plain text
                    st.markdown(f"📄 {content[:200]}")

                if st.button("🗑️ Remove", key=f"del_practice_{item_id}"):
                    delete_saved_item(item_id)
                    safe_rerun()
        else:
            st.info("No previous practice sessions found.")
