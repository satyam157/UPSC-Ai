import streamlit as st
import PyPDF2
import time
from datetime import datetime
from ui_components import safe_rerun, extract_subject_from_title
from db import (
    save_item, get_saved_items, delete_saved_item, save_result,
    save_url_summary, get_url_summaries, delete_url_summary
)
from quiz_generator import generate_quiz, generate_syllabus_quiz
from quiz_engine import evaluate, evaluate_quiz_response
from pdf_utils import generate_pdf
from llm import ask_llm, ask_llm_high_quality
from url_summarizer import URLSummarizer

def show_pdf_quiz_page():
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
            from quiz_engine import evaluate
            res = evaluate(user, st.session_state["pa"])
            content = ""
            for i, (u, c) in enumerate(zip(user, st.session_state["pa"])):
                content += f"Q{i+1}: Your={u}, Correct={c}\n"
            pdf = generate_pdf(content)
            st.download_button("Download PDF", open(pdf, "rb"), file_name="PDF_Quiz.pdf")
            save_result(("PDF_1", *res))

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
            st.text_area("Content", pdf_items[idx][2], height=280, key=f"ta_pdf_{item_id}")
            if st.button("🗑️ Remove", key=f"del_pdf_{item_id}"):
                delete_saved_item(item_id)
                safe_rerun()


def show_summarizer_page():
    st.subheader("📄 Advanced UPSC Summarizer")
    st.caption("Multi-source summarization with cross-referencing, Prelims MCQs, and elaborative analysis")

    tab_urls, tab_text, tab_pdf, tab_compare, tab_saved, tab_quiz = st.tabs([
        "🔗 URL Articles", "✍️ Text Summary", "📄 PDF Summary",
        "⚖️ Comparative Analysis", "📚 Saved Summaries", "📋 Quiz from Summaries"
    ])

    summarizer = URLSummarizer()

    # ── TAB 1: URL Article Summarization ──────────────────────────────────────
    with tab_urls:
        st.markdown("""
        <div style="background:linear-gradient(135deg,#1e1b4b,#312e81);border-radius:10px;
                    padding:12px 18px;margin-bottom:14px;">
          <div style="color:#e2e8f0;font-weight:600;font-size:14px;">
            🔗 Paste URLs from The Hindu, Indian Express, Drishti IAS, Insights, or any UPSC source
          </div>
          <div style="color:#94a3b8;font-size:12px;margin-top:4px;">
            Each article gets: Structured summary • Prelims MCQs • NCERT Links • Mains Integration
          </div>
        </div>
        """, unsafe_allow_html=True)

        urls_input = st.text_area(
            "Paste article URLs (one per line)", 
            height=120,
            placeholder="https://www.thehindu.com/opinion/editorial/...\nhttps://indianexpress.com/article/explained/...",
            key="sum_urls_input"
        )

        # Optional PDF context
        with st.expander("📎 Attach PDF context (optional)", expanded=False):
            pdf_context_file = st.file_uploader(
                "Upload a related PDF (NCERT chapter, Yojana issue, etc.) to enrich summaries",
                type=["pdf"],
                key="sum_pdf_context"
            )
            pdf_context_text = ""
            if pdf_context_file:
                try:
                    reader = PyPDF2.PdfReader(pdf_context_file)
                    for page in reader.pages[:5]:  # Max 5 pages
                        pdf_context_text += page.extract_text() or ""
                    st.success(f"✅ PDF loaded: {len(pdf_context_text)} characters extracted")
                except Exception as e:
                    st.error(f"Error reading PDF: {e}")

        if st.button("🚀 Generate Summaries", type="primary", use_container_width=True, key="btn_sum_urls"):
            if urls_input.strip():
                urls = [u.strip() for u in urls_input.split('\n') if u.strip()]
                progress = st.progress(0, text="Starting...")
                
                for idx, url in enumerate(urls):
                    progress.progress(
                        (idx) / len(urls), 
                        text=f"Processing {idx+1}/{len(urls)}: {url[:60]}..."
                    )
                    
                    with st.spinner(f"📡 Fetching & analyzing: {url[:60]}..."):
                        if pdf_context_text:
                            title, summary, source, error = summarizer.summarize_with_pdf_context(
                                url, pdf_context_text
                            )
                        else:
                            title, summary, source, error = summarizer.summarize_url(url)
                        
                        if not error:
                            subj = extract_subject_from_title(title)
                            save_url_summary(url, title, summary, subj)
                            st.success(f"✅ {title}")
                            with st.expander(f"📖 View Summary — {title}", expanded=True):
                                st.markdown(summary)
                        else:
                            st.error(f"❌ {url}: {error}")
                    
                    if idx < len(urls) - 1:
                        time.sleep(1)
                
                progress.progress(1.0, text="✅ All articles processed!")
                time.sleep(1)
                safe_rerun()
            else:
                st.warning("Please paste at least one URL.")

    # ── TAB 2: Text Summary ──────────────────────────────────────────────────
    with tab_text:
        st.markdown("""
        <div style="background:linear-gradient(135deg,#1e1b4b,#312e81);border-radius:10px;
                    padding:12px 18px;margin-bottom:14px;">
          <div style="color:#e2e8f0;font-weight:600;font-size:14px;">
            ✍️ Paste any text — editorial, news excerpt, book passage, or class notes
          </div>
          <div style="color:#94a3b8;font-size:12px;margin-top:4px;">
            AI generates a UPSC-structured summary with Prelims MCQs, entity deep-dives, and NCERT links
          </div>
        </div>
        """, unsafe_allow_html=True)

        text_title = st.text_input(
            "Title (optional)", 
            placeholder="e.g. 'The Hindu Editorial on Fiscal Deficit'",
            key="sum_text_title"
        )
        text_input = st.text_area(
            "Paste your text here", 
            height=250,
            placeholder="Paste the editorial text, news content, or any UPSC-relevant passage here...",
            key="sum_text_input"
        )
        
        if st.button("🧠 Generate Text Summary", type="primary", use_container_width=True, key="btn_sum_text"):
            if text_input.strip() and len(text_input.strip()) >= 100:
                with st.spinner("🤖 AI is analyzing and structuring your text..."):
                    title = text_title.strip() or "User Text Input"
                    summary, error = summarizer.generate_text_summary(text_input, title=title)
                    
                    if not error and summary:
                        subj = extract_subject_from_title(title)
                        save_url_summary(f"text://{title[:50]}", title, summary, subj)
                        
                        st.success(f"✅ Summary generated for: **{title}**")
                        st.markdown("---")
                        st.markdown(summary)
                    else:
                        st.error(error or "❌ Failed to generate summary")
            else:
                st.warning("⚠️ Please provide at least 100 characters of text.")

    # ── TAB 3: PDF Summary ───────────────────────────────────────────────────
    with tab_pdf:
        st.markdown("""
        <div style="background:linear-gradient(135deg,#1e1b4b,#312e81);border-radius:10px;
                    padding:12px 18px;margin-bottom:14px;">
          <div style="color:#e2e8f0;font-weight:600;font-size:14px;">
            📄 Upload a PDF — NCERT chapter, Yojana/Kurukshetra issue, or coaching material
          </div>
          <div style="color:#94a3b8;font-size:12px;margin-top:4px;">
            Extracts text and generates a structured UPSC summary with cross-references
          </div>
        </div>
        """, unsafe_allow_html=True)

        pdf_file = st.file_uploader("Upload PDF for summary", type=["pdf"], key="sum_pdf_upload")
        
        if pdf_file:
            col_start, col_end = st.columns(2)
            with col_start:
                pdf_start = st.number_input("From page", min_value=1, value=1, key="sum_pdf_start")
            with col_end:
                pdf_end = st.number_input("To page", min_value=1, value=5, key="sum_pdf_end")
            
            pdf_title = st.text_input(
                "Document Title (optional)", 
                placeholder="e.g. 'NCERT Class XII Polity Ch. 3'",
                key="sum_pdf_title"
            )
            
            if st.button("📚 Summarize PDF", type="primary", use_container_width=True, key="btn_sum_pdf"):
                try:
                    reader = PyPDF2.PdfReader(pdf_file)
                    total_pages = len(reader.pages)
                    actual_end = min(int(pdf_end), total_pages)
                    
                    pdf_text = ""
                    for i in range(int(pdf_start) - 1, actual_end):
                        page_text = reader.pages[i].extract_text()
                        if page_text:
                            pdf_text += page_text + "\n\n"
                    
                    if len(pdf_text.strip()) < 200:
                        st.error("⚠️ Too little text extracted from PDF. Try different page range or a text-based PDF.")
                    else:
                        with st.spinner(f"🤖 Analyzing {actual_end - int(pdf_start) + 1} pages..."):
                            title = pdf_title.strip() or pdf_file.name
                            summary, error = summarizer.generate_text_summary(pdf_text, title=title)
                            
                            if not error and summary:
                                subj = extract_subject_from_title(title)
                                save_url_summary(f"pdf://{title[:50]}", title, summary, subj)
                                
                                st.success(f"✅ Summary generated for: **{title}** ({actual_end - int(pdf_start) + 1} pages)")
                                st.markdown("---")
                                st.markdown(summary)
                            else:
                                st.error(error or "❌ Failed to generate summary")
                except Exception as e:
                    st.error(f"❌ Error processing PDF: {str(e)[:150]}")

    # ── TAB 4: Comparative Analysis ──────────────────────────────────────────
    with tab_compare:
        st.markdown("""
        <div style="background:linear-gradient(135deg,#1e1b4b,#4c1d95);border-radius:10px;
                    padding:12px 18px;margin-bottom:14px;">
          <div style="color:#e2e8f0;font-weight:600;font-size:14px;">
            ⚖️ Compare multiple articles on the same topic
          </div>
          <div style="color:#94a3b8;font-size:12px;margin-top:4px;">
            e.g. Compare The Hindu Editorial vs Indian Express Opinion on the same policy issue
          </div>
        </div>
        """, unsafe_allow_html=True)

        compare_urls = st.text_area(
            "Paste 2-4 article URLs to compare (one per line)",
            height=120,
            placeholder="https://www.thehindu.com/opinion/editorial/...\nhttps://indianexpress.com/article/opinion/...",
            key="sum_compare_urls"
        )
        
        if st.button("⚖️ Generate Comparative Analysis", type="primary", use_container_width=True, key="btn_compare"):
            if compare_urls.strip():
                urls = [u.strip() for u in compare_urls.split('\n') if u.strip()]
                
                if len(urls) < 2:
                    st.warning("⚠️ Please provide at least 2 URLs for comparison.")
                elif len(urls) > 4:
                    st.warning("⚠️ Maximum 4 URLs for comparison. Using first 4.")
                    urls = urls[:4]
                else:
                    articles = []
                    progress = st.progress(0, text="Fetching articles...")
                    
                    for idx, url in enumerate(urls):
                        progress.progress(idx / len(urls), text=f"Fetching {idx+1}/{len(urls)}...")
                        title, content, source, error = summarizer.fetch_article(url)
                        if not error and content:
                            articles.append((title, content, source))
                            st.success(f"✅ Fetched: {title}")
                        else:
                            st.error(f"❌ Failed: {url[:50]} — {error}")
                    
                    if len(articles) >= 2:
                        progress.progress(0.8, text="🤖 Generating comparative analysis...")
                        comp_summary, comp_error = summarizer.generate_comparative_summary(articles)
                        
                        if not comp_error and comp_summary:
                            progress.progress(1.0, text="✅ Done!")
                            
                            # Save comparative analysis
                            comp_title = f"Comparative: {articles[0][0][:40]} vs {articles[1][0][:40]}"
                            subj = extract_subject_from_title(articles[0][0])
                            save_url_summary(
                                f"compare://{datetime.now().isoformat()[:16]}", 
                                comp_title, comp_summary, subj
                            )
                            
                            st.markdown("---")
                            st.markdown("### ⚖️ Comparative Analysis")
                            st.markdown(comp_summary)
                        else:
                            st.error(comp_error or "❌ Failed to generate comparative analysis")
                    else:
                        st.error("❌ Need at least 2 successfully fetched articles for comparison.")

    # ── TAB 5: Saved Summaries ───────────────────────────────────────────────
    with tab_saved:
        saved = get_url_summaries(limit=50)
        if saved:
            # Filter options
            subjects = list(set(s[3] for s in saved if s[3]))
            filter_subj = st.selectbox(
                "Filter by subject", ["All"] + sorted(subjects), 
                key="sum_filter_subj"
            )
            
            filtered = saved if filter_subj == "All" else [s for s in saved if s[3] == filter_subj]
            
            st.caption(f"Showing {len(filtered)} summaries")
            
            for sid, url, title, subj, text, created in filtered:
                # Determine source icon
                if "compare://" in str(url):
                    icon = "⚖️"
                elif "pdf://" in str(url):
                    icon = "📄"
                elif "text://" in str(url):
                    icon = "✍️"
                else:
                    icon = "🔗"
                
                created_str = str(created)[:16] if created else ""
                
                with st.expander(f"{icon} {title} • {subj} • {created_str}"):
                    st.markdown(text)
                    
                    col_link, col_del = st.columns([4, 1])
                    with col_link:
                        if url and not url.startswith(("text://", "pdf://", "compare://")):
                            st.markdown(f"[🔗 Original Article]({url})")
                    with col_del:
                        if st.button("🗑️ Delete", key=f"ds_{sid}"):
                            delete_url_summary(sid)
                            safe_rerun()
        else:
            st.info("📭 No saved summaries yet. Use the tabs above to generate summaries.")

    # ── TAB 6: Quiz from Summaries ───────────────────────────────────────────
    with tab_quiz:
        st.markdown("""
        <div style="background:linear-gradient(135deg,#1e1b4b,#312e81);border-radius:10px;
                    padding:12px 18px;margin-bottom:14px;">
          <div style="color:#e2e8f0;font-weight:600;font-size:14px;">
            📋 Generate UPSC MCQs from any saved summary
          </div>
          <div style="color:#94a3b8;font-size:12px;margin-top:4px;">
            Select a summary → AI creates Prelims-style questions with elaborative explanations
          </div>
        </div>
        """, unsafe_allow_html=True)

        saved = get_url_summaries(limit=50)
        if saved:
            options = [f"{s[2]} ({s[3]})" for s in saved]
            selected_idx = st.selectbox(
                "Select a summary to generate quiz from",
                range(len(options)),
                format_func=lambda i: options[i],
                key="sum_quiz_select"
            )
            
            num_questions = st.slider("Number of questions", 3, 10, 5, key="sum_quiz_count")
            
            if st.button("🎯 Generate Quiz", type="primary", use_container_width=True, key="btn_sum_quiz"):
                selected_summary = saved[selected_idx]
                summary_text = selected_summary[4]  # summary content
                subj = selected_summary[3]
                
                with st.spinner(f"🤖 Generating {num_questions} UPSC questions from summary..."):
                    try:
                        questions, error = generate_syllabus_quiz(
                            resource_type=subj or "Article Summary",
                            summary_content=summary_text,
                            num_questions=num_questions
                        )
                        
                        if questions and not error:
                            st.session_state["sum_quiz_questions"] = questions
                            st.session_state["sum_quiz_submitted"] = False
                            st.session_state["sum_quiz_source"] = selected_summary[2]
                            safe_rerun()
                        else:
                            st.error(error or "❌ Failed to generate quiz")
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)[:150]}")
            
            # Quiz display
            if "sum_quiz_questions" in st.session_state and not st.session_state.get("sum_quiz_submitted"):
                questions = st.session_state["sum_quiz_questions"]
                source = st.session_state.get("sum_quiz_source", "")
                
                st.markdown(f"### 📝 Quiz — {source[:60]}")
                st.divider()
                
                for i, q in enumerate(questions):
                    st.markdown(f"""
                    <div style="background:#1a1a2e;border-left:3px solid #6366f1;
                                padding:12px 16px;margin:14px 0 6px 0;border-radius:6px;">
                      <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
                        <span style="color:#a5b4fc;font-size:12px;font-weight:600;">Q{i+1}</span>
                        <span style="color:#94a3b8;font-size:11px;">
                          {q.get('difficulty', 'Medium')} • {q.get('question_type', 'MCQ')}
                        </span>
                      </div>
                      <p style="color:#e2e8f0;margin:0;font-size:14px;white-space:pre-wrap;">
                        {q['question']}
                      </p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    opts = q.get("options", [])
                    st.radio("", opts, key=f"sum_q_{i}", index=None, label_visibility="collapsed")
                    st.divider()
                
                if st.button("✅ Submit Quiz", type="primary", use_container_width=True, key="btn_sum_quiz_submit"):
                    user_answers = []
                    for i in range(len(questions)):
                        sel = st.session_state.get(f"sum_q_{i}")
                        if sel is not None:
                            # Extract index from options list
                            try:
                                user_answers.append(questions[i]["options"].index(sel))
                            except ValueError:
                                user_answers.append(0)
                        else:
                            user_answers.append(0)
                    
                    result, err = evaluate_quiz_response(questions, user_answers)
                    if result:
                        st.session_state["sum_quiz_result"] = result
                        st.session_state["sum_quiz_submitted"] = True
                        safe_rerun()
            
            # Quiz results
            if st.session_state.get("sum_quiz_submitted") and "sum_quiz_result" in st.session_state:
                result = st.session_state["sum_quiz_result"]
                score = result["score"]
                total = result["total"]
                pct = result["percentage"]
                upsc_marks = result.get("upsc_marks", 0)
                
                color = "#34d399" if pct >= 70 else "#fbbf24" if pct >= 50 else "#f87171"
                
                st.markdown(f"""
                <div style="background:#16162a;border:2px solid {color};border-radius:14px;
                            padding:22px;text-align:center;margin:14px 0;">
                  <div style="font-size:36px;font-weight:800;color:{color};">{pct}%</div>
                  <div style="color:#e2e8f0;margin-top:6px;font-size:16px;">{score} / {total} correct</div>
                  <div style="color:#94a3b8;margin-top:4px;font-size:13px;">
                    UPSC Marks: <b style="color:{color};">{upsc_marks}</b>
                  </div>
                </div>
                """, unsafe_allow_html=True)
                
                st.subheader("📖 Elaborative Answer Review")
                for r in result.get("results", []):
                    icon = "✅" if r["is_correct"] else "❌"
                    q_preview = r["question"][:80] + ("…" if len(r["question"]) > 80 else "")
                    
                    with st.expander(f"{icon} {q_preview}", expanded=not r["is_correct"]):
                        st.markdown(f"**Question:** {r['question']}")
                        st.markdown(f"**Your answer:** {r['user_answer']}")
                        st.markdown(f"**Correct answer:** {r['correct_answer']}")
                        
                        if r.get("explanation"):
                            st.markdown("---")
                            st.markdown(f"**📋 Explanation:** {r['explanation']}")
                        
                        # Per-option analysis
                        opt_expl = r.get("option_explanations", {})
                        if any(opt_expl.values()):
                            st.markdown("**🔍 Option-by-Option Analysis:**")
                            for letter in ["A", "B", "C", "D"]:
                                if opt_expl.get(letter):
                                    st.markdown(f"&nbsp;&nbsp; **{letter}:** {opt_expl[letter]}")
                
                if st.button("🔄 New Quiz", use_container_width=True, key="btn_sum_new_quiz"):
                    for k in ["sum_quiz_questions", "sum_quiz_submitted", "sum_quiz_result", "sum_quiz_source"]:
                        st.session_state.pop(k, None)
                    for k in list(st.session_state.keys()):
                        if k.startswith("sum_q_"):
                            del st.session_state[k]
                    safe_rerun()
        else:
            st.info("📭 No summaries saved yet. Generate summaries in the other tabs first, then come back here to quiz yourself.")
