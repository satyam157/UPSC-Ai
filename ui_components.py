import streamlit as st
import re
from datetime import datetime

# ─── CONSTANTS ───────────────────────────────────────────────────────────────
# Credentials are now stored in the database (users table).
# Import auth functions from db module.
from db import validate_user, user_exists, get_credentials

SOURCE_COLORS = {
    "the hindu editorial": "#d32f2f", "the hindu opinion": "#c62828", "the hindu": "#e53935",
    "ie explained": "#1565c0", "indian express opinion": "#0d47a1", "indian express": "#1976d2",
    "pib": "#2e7d32", "bs editorial": "#6a1b9a", "business standard": "#7b1fa2",
    "down to earth": "#00695c", "the print": "#f57f17", "livemint editorial": "#3e2723"
}
DEFAULT_COLOR = "#546e7a"

# ─── CSS ─────────────────────────────────────────────────────────────────────
CUSTOM_CSS = """
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
"""

# ─── HELPERS ──────────────────────────────────────────────────────────────────
def safe_rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()

def acc_class(val):
    if val >= 70: return "accuracy-good"
    if val >= 50: return "accuracy-mid"
    return "accuracy-low"

def clear_state(key):
    st.session_state[key] = ""

def extract_subject_from_title(title):
    title_lower = title.lower()
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
    words = title_lower.split()
    for word in words:
        if len(word) > 3 and word not in ["from", "with", "what", "your", "the", "and", "for", "are"]:
            return word.capitalize()
    return "General"

def login_page():
    st.markdown("## 🔐 Login to UPSC AI SYSTEM")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        if submit:
            if validate_user(username, password):
                st.session_state["logged_in"] = True
                st.session_state["username"] = username
                st.query_params["user"] = username
                st.success("✅ Login successful!")
                st.rerun()
            else:
                st.error("❌ Invalid Username or Password")

def logout():
    st.session_state["logged_in"] = False
    st.session_state["username"] = ""
    if hasattr(st, "query_params"):
        st.query_params.clear()
    st.rerun()

def render_news_feed(items, key_prefix, limit=40):
    from scraper import fetch_full_news_content
    from llm import ask_llm

    if not items:
        st.info("No items found in this section.")
        return
    
    # ── Initialize news summary state ─────────────────────────────────────────
    if "news_summaries" not in st.session_state:
        st.session_state["news_summaries"] = {}
    if "news_keywords" not in st.session_state:
        st.session_state["news_keywords"] = {}
    if "news_raw_text" not in st.session_state:
        st.session_state["news_raw_text"] = {}
    if "keyword_facts" not in st.session_state:
        st.session_state["keyword_facts"] = {}

    # ── Hierarchical Grouping (Year -> Month -> Date) ─────────────────────────
    news_hierarchy = {}
    for n in items:
        try:
            # Assuming n[2] is 'YYYY-MM-DD HH:MM:S' or similar
            date_str = str(n[2]).split(" ")[0]
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            year = str(dt.year)
            month = dt.strftime("%B")
            day = date_str
            
            if year not in news_hierarchy: news_hierarchy[year] = {}
            if month not in news_hierarchy[year]: news_hierarchy[year][month] = {}
            if day not in news_hierarchy[year][month]: news_hierarchy[year][month][day] = []
            news_hierarchy[year][month][day].append(n)
        except Exception:
            continue

    sorted_years = sorted(news_hierarchy.keys(), reverse=True)
    if not sorted_years:
        st.info("No formatted news items found.")
        return

    # Year & Month Dropdowns in a single row
    col_y, col_m = st.columns(2)
    with col_y:
        selected_year = st.selectbox("📅 Select Year", sorted_years, key=f"sel_year_{key_prefix}")
    
    with col_m:
        available_months = sorted(
            news_hierarchy[selected_year].keys(),
            key=lambda m: datetime.strptime(m, "%B").month,
            reverse=True
        )
        selected_month = st.selectbox("📁 Select Month", available_months, key=f"sel_month_{key_prefix}")

    # Render days for the selected year/month
    sorted_days = sorted(news_hierarchy[selected_year][selected_month].keys(), reverse=True)
    
    for d in sorted_days:
        day_items_raw = news_hierarchy[selected_year][selected_month][d]
        
        # Apply UI-level limit only if specified
        if limit:
            day_items = day_items_raw[:limit]
        else:
            day_items = day_items_raw
            
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
                                    is_editorial_priority = "editorial" in category_val.lower() or "opinion" in category_val.lower() or "explained" in category_val.lower() or \
                                              "editorial" in source_val.lower() or "opinion" in source_val.lower() or "explained" in source_val.lower()
                                    
                                    raw_text = ""
                                    if is_deep and url_val:
                                        st.caption("🔗 Fetching full article content...")
                                        suc, ft = fetch_full_news_content(url_val)
                                        raw_text = ft if suc else (content_val or title_val)
                                    else:
                                        raw_text = content_val or title_val
                                    
                                    if is_editorial_priority:
                                        prompt_text = f"""You are an elite UPSC exam coach specializing in editorial analysis for Mains answer writing.
This is an EDITORIAL/OPINION piece — the most important content for UPSC exam preparation.
Your job is to EXTRACT and preserve the article's core arguments, data, and analysis (not just summarize generically).

**ARTICLE TITLE:** {title_val}
**SOURCE:** {source_val}
**CONTENT:** {raw_text[:8000]}

## OUTPUT FORMAT (follow EXACTLY — this is an EDITORIAL, go deeper than regular news):

### 📌 Central Thesis
(What is the main argument of this editorial? State it in 2-3 sentences, preserving the author's position.)

### 🔑 Key Arguments (Extract from Article)
| # | Argument WITH (in the article) | Argument AGAINST (in the article) | Significance & Critical Impact |
|---|--------------------------------|-----------------------------------|--------------------------------|
| 1 | [Pro-argument/Fact] | [Critical counter-view/Concern] | [Analytical Takeaway / Impact] |
| 2 | [Fact] | [Concern/Limitation] | [Impact/Implication] |
| 3 | [Fact] | [Concern/Limitation] | [Impact/Implication] |
| 4 | [Fact] | [Concern/Limitation] | [Impact/Implication] |
| 5 | [Fact] | [Concern/Limitation] | [Impact/Implication] |
(Ensure "Argument AGAINST" captures any dissent, challenges, or risks mentioned in the article for full insight.)
**CRITICAL RULE for Table:** DO NOT repeat the same argument or core phrase across different rows. Each row MUST add unique value. If the article has fewer than 5 unique points, provide only those (e.g. only 2 or 3 rows) rather than using filler or repeating text.

### 🏛️ Constitutional/Legal/Policy Framework
- **Article/Provision:** [Exact Article Number, Law Section, or Policy Clause mentioned]
- **Details:** Relevant Acts, Amendments, and Institutional recommendations. (Proactively link to relevant static laws even if not explicitly in text).

### 📊 Data, Reports & Evidence (Answer Fodder)
- [List any specific numbers, %, committee names, reports (e.g. IMF, NITI Aayog), or surveys mentioned in the article]

### ⚡ Challenges Identified (Author's Perspective)
- [Strictly extract the author's specific concerns, dissent, or limitations mentioned]

### 🛤️ Way Forward (Author's Recommendations)
- [Focus on the author's specific solutions and suggestions for the future]

### 🌍 Global Context / Case Studies
- [Any international comparisons, global best practices, or foreign examples mentioned]

### 🧭 Editorial Perspective & Tone
- **Tone:** [e.g., Critical, Supportive, Suggestive, Reformist]
- **Core Viewpoint:** [1-sentence summary of the author's specific stance]

### 🎯 UPSC Relevance & Mains Integration
- **GS Paper:** GS-[1/2/3/4] | **Topic:** [Specific syllabus topic]
- **Essay Connection:** [How this can be used in an Essay - specific hook]
- **Probable Mains Question:** [One analytical question this editorial could generate]

### 🌍 UPSC Entity Deep-Dive (Proactive)
(Identify 1-2 most critical entities (Rivers, Species, Parks, Organizations). Provide a data-rich "About [Entity]:" block. 
**Follow these sub-rules based on entity type (ONLY output the relevant block, NO "Not applicable" fields):**
- **If Geography/Place (Rivers, Lakes, Mountains, Regions):**
  - **About:** (Location (districts/states), context)
  - **Geographical & Physical Features:** (Topography, surrounding hills/ranges, climate, drainage/tributaries, soil type)
  - **Biodiversity:** (Key Flora and Fauna in the region)
  - **Designations & Status:** (Ramsar, UNESCO, Protected Area status with years)
  - **Significance:** (Economic, Strategic, or Cultural importance)
- **If Organization / Body / Portal / Scheme:**
  - **About/Genesis:** (Launch year, HQ, Parent Ministry/Organization)
  - **Type & Governance:** (Statutory/Constitutional/Extra-constitutional, Secretariat, Board structure)
  - **Mandate & Functions:** (Core objectives and powers)
  - **Key Initiatives & Achievements:** (Specific programs or milestones)
  - **Issues & Challenges:** (Financial health, implementation hurdles, etc.)
- **If Species / Environment:**
  - **Scientific Name & Family**
  - **Physical Traits & Adaptations**
  - **Habitat & Distribution:** (Regions, forest types, state-wise presence)
  - **Conservation Status:** (IUCN Red List, CITES, WPA 1972 Schedule)
  - **Threats & Conservation Efforts**)

### 📚 NCERT Link
- **Source:** Class [X] [Subject] → Chapter: [Name]
- **Connection:** [1-2 lines on how it connects]
- **Contextual Excerpt:** [Provide a 2-3 sentence verbatim-style line or paragraph from this chapter that captures the core concept relevant to the news.]

### 💾 Remember
→ [One key takeaway]
→ [One date/number/name to memorize]

### 🏷️ UPSC High-Value Keywords
(Extract 5-8 keywords. For each, provide a 1-sentence UPSC-relevant fact. **For Geo/Env keywords:** Include Flora, Fauna, or Status. Format: **Keyword**: [Fact]. Bulleted.)

**RULES: Extract arguments DIRECTLY from the article — do NOT make up generic points. Max 500 words total.**"""
                                    else:
                                        prompt_text = f"""You are an expert UPSC exam coach. Analyze this news article and create a **structured, exam-focused summary**. 
NO repetition — every sentence must add new information. Be crisp and precise.

**ARTICLE TITLE:** {title_val}
**CONTENT:** {raw_text[:6000]}

## OUTPUT FORMAT (follow EXACTLY):

### 📌 One-Liner
(Single sentence capturing the core news — what happened, who, when)

### 🔑 Key Points (Exam-Critical)
| # | Argument WITH (in the article) | Argument AGAINST (in the article) | Significance & Critical Impact |
|---|--------------------------------|-----------------------------------|--------------------------------|
| 1 | [Pro-argument/Fact] | [Critical counter-view/Concern] | [Analytical Takeaway / Impact] |
| 2 | [Fact] | [Concern/Limitation] | [Impact/Implication] |
| 3 | [Fact] | [Concern/Limitation] | [Impact/Implication] |
(Maximum 5 rows — only exam-worthy facts)
**CRITICAL RULE for Table:** DO NOT repeat the same argument or core phrase across different rows. Each row MUST add unique value. If the article has fewer than 5 unique points, provide only those (e.g. only 2 or 3 rows) rather than using filler or repeating text.

### 🏛️ Constitutional/Legal/Institutional Framework
- **Proactive Context:** (Even if not in text, identify relevant Constitutional Articles (e.g. 243, 324), Acts (e.g. EPA 1986), or Institutions (e.g. NITI Aayog) related to this topic)
- **Article/Provision:** [Exact Article Number or Law Section if applicable]

### 📊 Key Data & Evidence
- [High-value stats, percentages, or report names mentioned in the news]

### ⚡ Challenges & Risks
- [Specific challenges, implementation hurdles, or risks mentioned in the text]

### 🛤️ Way Forward
- [Specific solutions or future steps suggested by the news/author]

### 🌍 Global Context / Comparison
- [How this compares to global trends or other countries, if mentioned]

### 🎯 UPSC Relevance & Mains Integration
- **GS Paper:** GS-[1/2/3/4] | **Topic:** [Specific syllabus topic]
- **Essay Connection:** [How this can be used in an Essay - specific hook]
- **Probable Mains Question:** [One analytical question this could generate]

### 🌍 UPSC Entity Deep-Dive (Proactive)
(Identify 1-2 most critical entities (Rivers, Species, Parks, Organizations). Provide a data-rich "About [Entity]:" block. 
**Follow these sub-rules based on entity type (ONLY output the relevant block, NO "Not applicable" fields):**
- **If Geography/Place (Rivers, Lakes, Mountains, Regions):**
  - **About:** (Location (districts/states), context)
  - **Geographical & Physical Features:** (Topography, surrounding hills/ranges, climate, drainage/tributaries, soil type)
  - **Biodiversity:** (Key Flora and Fauna in the region)
  - **Designations & Status:** (Ramsar, UNESCO, Protected Area status with years)
  - **Significance:** (Economic, Strategic, or Cultural importance)
- **If Organization / Body / Portal / Scheme:**
  - **About/Genesis:** (Launch year, HQ, Parent Ministry/Organization)
  - **Type & Governance:** (Statutory/Constitutional/Extra-constitutional, Secretariat, Board structure)
  - **Mandate & Functions:** (Core objectives and powers)
  - **Key Initiatives & Achievements:** (Specific programs or milestones)
  - **Issues & Challenges:** (Financial health, implementation hurdles, etc.)
- **If Species / Environment:**
  - **Scientific Name & Family**
  - **Physical Traits & Adaptations**
  - **Habitat & Distribution:** (Regions, forest types, state-wise presence)
  - **Conservation Status:** (IUCN Red List, CITES, WPA 1972 Schedule)
  - **Threats & Conservation Efforts**)

### 📚 NCERT Link
- **Source:** Class [X] [Subject] → Chapter: [Name]
- **Connection:** [1-2 lines on how it connects]
- **Contextual Excerpt:** [Provide a 2-3 sentence verbatim-style line or paragraph from this chapter that captures the core concept relevant to the news.]

### 💾 Remember
→ [One key takeaway]
→ [One date/number/name to memorize]

### 🏷️ UPSC High-Value Keywords
(Extract 5-8 keywords. For each, provide a 1-sentence UPSC-relevant fact. **For Geo/Env keywords:** Include Flora, Fauna, or Status. Format: **Keyword**: [Fact]. Bulleted.)

**RULES: Max 400 words total. No filler. Proactively include relevant static/legal links.**"""
                                    llm_output = ask_llm(prompt_text)
                                    
                                    # ── Advanced Section-Aware Parser v2.0 ─────────────────────
                                    # Uses regex-based section detection to handle LLM output
                                    # variations robustly. Parses in correct order:
                                    #   1. Extract Keywords section (always near end)
                                    #   2. Extract Deep-Dive section (middle)
                                    #   3. Everything else = summary_part
                                    # ───────────────────────────────────────────────────────────
                                    
                                    summary_part = llm_output
                                    proactive_deep_dive = ""
                                    extracted_keywords = []
                                    
                                    # ── 1. KEYWORD EXTRACTION (multi-pattern, tolerant) ────────
                                    kw_section_patterns = [
                                        r'#{1,4}\s*🏷️?\s*UPSC\s+High[- ]Value\s+Keywords?',
                                        r'#{1,4}\s*🏷️\s*Keywords?',
                                        r'#{1,4}\s*Important\s+Words?\s*(?:&|and)\s*UPSC',
                                        r'🏷️\s*(?:UPSC\s+)?(?:High[- ]Value\s+)?Keywords?\s*:?',
                                        r'#{1,4}\s*Keywords?\s+(?:&|and)\s+Facts?',
                                    ]
                                    
                                    for pat in kw_section_patterns:
                                        match = re.search(pat, llm_output, re.IGNORECASE)
                                        if match:
                                            kw_start = match.start()
                                            kw_header_end = match.end()
                                            
                                            # Everything before keyword section
                                            before_kw = llm_output[:kw_start].strip()
                                            # Everything after keyword header
                                            after_kw = llm_output[kw_header_end:].strip()
                                            
                                            # Find where the keyword section ends (next ### header or end)
                                            next_header = re.search(r'\n#{1,4}\s+[^\n]', after_kw)
                                            if next_header:
                                                kw_block = after_kw[:next_header.start()].strip()
                                                remaining_after = after_kw[next_header.start():].strip()
                                                # Append anything after keywords back to summary
                                                summary_part = before_kw + "\n\n" + remaining_after
                                            else:
                                                kw_block = after_kw
                                                summary_part = before_kw
                                            
                                            # Strip trailing rules/filler from keyword block
                                            kw_block = re.split(r'\*{2}RULES?\s*:', kw_block, flags=re.IGNORECASE)[0]
                                            kw_block = re.split(r'(?:^|\n)\s*RULES?\s*:', kw_block, flags=re.IGNORECASE)[0]
                                            kw_block = kw_block.strip()
                                            
                                            # Parse individual keyword lines (flexible)
                                            kw_lines = []
                                            for line in kw_block.split("\n"):
                                                line = line.strip()
                                                if not line:
                                                    continue
                                                # Accept lines that: start with bullet/dash/number/bold, or contain a colon
                                                if (line.startswith(("-", "•", "–", "—", "*", "·")) or
                                                    re.match(r'^\d+[\.\)]\s', line) or
                                                    re.match(r'^\*\*', line) or
                                                    ":" in line):
                                                    # Clean leading bullet/dash
                                                    cleaned = re.sub(r'^[-•–—*·]\s*', '', line).strip()
                                                    cleaned = re.sub(r'^\d+[\.\)]\s*', '', cleaned).strip()
                                                    if cleaned and len(cleaned) > 5:
                                                        kw_lines.append(cleaned)
                                            
                                            extracted_keywords = kw_lines[:12]
                                            break
                                    
                                    # ── 2. DEEP-DIVE EXTRACTION (section-aware) ────────────────
                                    dd_section_patterns = [
                                        r'#{1,4}\s*🌍?\s*UPSC\s+Entity\s+Deep[- ]Dive\s*\(?Proactive\)?',
                                        r'#{1,4}\s*🌍\s*Deep[- ]Dive\s*:?',
                                        r'#{1,4}\s*🏆?\s*Entity\s+Spotlight',
                                        r'🌍\s*(?:UPSC\s+)?(?:Entity\s+)?Deep[- ]Dive\s*:?',
                                    ]
                                    
                                    for pat in dd_section_patterns:
                                        match = re.search(pat, summary_part, re.IGNORECASE)
                                        if match:
                                            dd_start = match.start()
                                            dd_header_end = match.end()
                                            
                                            before_dd = summary_part[:dd_start].strip()
                                            after_dd_header = summary_part[dd_header_end:].strip()
                                            
                                            # Find where deep-dive ends (next ### header or end)
                                            next_hdr = re.search(r'\n#{1,4}\s+[^\n]', after_dd_header)
                                            if next_hdr:
                                                proactive_deep_dive = after_dd_header[:next_hdr.start()].strip()
                                                remaining = after_dd_header[next_hdr.start():].strip()
                                                summary_part = before_dd + "\n\n" + remaining
                                            else:
                                                proactive_deep_dive = after_dd_header.strip()
                                                summary_part = before_dd
                                            break
                                    
                                    # ── 3. Final cleanup on summary_part ────────────────────────
                                    # Remove duplicate blank lines
                                    summary_part = re.sub(r'\n{3,}', '\n\n', summary_part).strip()
                                    
                                    st.session_state["news_summaries"][title_val] = summary_part
                                    st.session_state["news_keywords"][title_val] = extracted_keywords
                                    st.session_state["keyword_facts"][f"proactive_{title_val}"] = proactive_deep_dive
                                    # Store raw text for re-analysis if needed
                                    st.session_state["news_raw_text"][title_val] = raw_text

                            # Display Summary
                            if title_val in st.session_state["news_summaries"]:
                                st.markdown(st.session_state["news_summaries"][title_val])
                                
                                # Display Proactive Deep-Dive if exists
                                proactive = st.session_state["keyword_facts"].get(f"proactive_{title_val}")
                                if proactive and proactive.strip():
                                    with st.container():
                                        st.markdown(
                                            f'<div style="background: linear-gradient(135deg, #1a3a2a, #0d2818); '
                                            f'border: 1px solid #34d399; border-radius: 10px; padding: 16px; margin: 10px 0;">'
                                            f'<h4 style="color: #34d399; margin: 0 0 8px;">🏆 UPSC Entity Spotlight</h4>'
                                            f'</div>', unsafe_allow_html=True
                                        )
                                        st.markdown(proactive)
                                
                                # ── KEYWORD DISPLAY (Advanced Pill-Style UI) ───────────────
                                keywords = st.session_state["news_keywords"].get(title_val, [])
                                if keywords:
                                    st.divider()
                                    st.markdown(
                                        '<h4 style="color: #a5b4fc; margin-bottom: 4px;">🏷️ UPSC High-Value Keywords & Facts</h4>',
                                        unsafe_allow_html=True
                                    )
                                    
                                    # Render keyword pills with facts inline
                                    for kw_item in keywords:
                                        # Split keyword : fact if present
                                        if ":" in kw_item and "**" in kw_item:
                                            # Pattern: **Keyword**: Fact sentence
                                            kw_match = re.match(r'\*{0,2}([^*:]+?)\*{0,2}\s*:\s*(.*)', kw_item)
                                            if kw_match:
                                                kw_name = kw_match.group(1).strip()
                                                kw_fact = kw_match.group(2).strip()
                                                st.markdown(
                                                    f'<div style="display:flex; align-items:flex-start; gap:8px; margin:6px 0;">'
                                                    f'<span style="background:#4c1d95; color:#e0e7ff; font-size:12px; font-weight:700; '
                                                    f'padding:3px 10px; border-radius:20px; white-space:nowrap; min-width:fit-content;">{kw_name}</span>'
                                                    f'<span style="color:#cbd5e1; font-size:13px; line-height:1.5;">{kw_fact}</span>'
                                                    f'</div>', unsafe_allow_html=True
                                                )
                                            else:
                                                st.markdown(f"• {kw_item}")
                                        else:
                                            st.markdown(f"• {kw_item}")
                                    
                                    st.markdown("---")
                                    st.markdown(
                                        '<h5 style="color:#c4b5fd; margin-bottom:2px;">🔍 Deep-Dive Interactive</h5>'
                                        '<p style="color:#64748b; font-size:12px; margin-top:0;">Select keywords or type any entity for an exhaustive UPSC deep-dive.</p>',
                                        unsafe_allow_html=True
                                    )
                                    
                                    # Clean keywords for selection (strip markdown artifacts)
                                    clean_keywords = []
                                    for k in keywords:
                                        # Extract just the keyword name
                                        ck = re.sub(r'\*{1,2}', '', k)           # Remove bold markers
                                        ck = ck.split(":")[0].strip()             # Take part before colon
                                        ck = re.sub(r'^[-•–—·]\s*', '', ck)       # Remove leading bullets
                                        ck = re.sub(r'^\d+[\.\)]\s*', '', ck)     # Remove numbering
                                        ck = ck.strip()
                                        if ck and len(ck) > 1 and ck not in clean_keywords:
                                            clean_keywords.append(ck)
                                    
                                    col_sel, col_custom = st.columns([2, 1])
                                    with col_sel:
                                        selected_kws = st.multiselect(
                                            "Select from extracted keywords:", 
                                            options=clean_keywords,
                                            key=f"kw_sel_{news_key}",
                                            label_visibility="collapsed"
                                        )
                                    with col_custom:
                                        custom_kw = st.text_input(
                                            "Or type any entity:", 
                                            key=f"kw_custom_{news_key}", 
                                            placeholder="e.g., NAM, Arctic Council",
                                            label_visibility="collapsed"
                                        )
                                    
                                    fetch_targets = list(selected_kws)
                                    if custom_kw and custom_kw.strip():
                                        fetch_targets.append(custom_kw.strip())
                                    
                                    fetch_btn = st.button(
                                        f"✨ Fetch Deep-Dive for {len(fetch_targets)} keyword(s)" if fetch_targets else "✨ Select keywords first",
                                        key=f"btn_kw_{news_key}",
                                        disabled=not fetch_targets,
                                        use_container_width=True
                                    )
                                    
                                    if fetch_btn and fetch_targets:
                                        for kw in fetch_targets:
                                            fact_key = f"{title_val}_{kw}"
                                            if fact_key not in st.session_state["keyword_facts"]:
                                                with st.spinner(f"🔎 Building exhaustive deep-dive for **{kw}**..."):
                                                    # Use high-quality LLM for keyword deep-dives
                                                    from llm import ask_llm_high_quality
                                                    kw_prompt = f"""You are an elite UPSC encyclopedia. Provide a FACTUAL, VERIFIABLE, exam-focused deep-dive for: **{kw}**

Context: This keyword appeared in the article "{title_val}".

## ⚠️ CRITICAL ANTI-HALLUCINATION RULES (MUST FOLLOW):
1. **ONLY state facts you are confident about.** If unsure, write "Data not confirmed — verify from [source]" instead of guessing.
2. **NEVER use vague language:** Ban these words entirely: "likely", "perhaps", "possibly", "may have", "could be", "it is believed", "reportedly", "presumably", "might", "seems to".
3. **Every claim MUST have a verifiable anchor:** Include specific Act names, Article numbers, years, official report names, NCERT chapter references, or organization names.
4. **Numbers over narratives:** Prefer "Established in 1992 under Article 280" over "It was established long ago under the Constitution".
5. **If the entity is obscure or you lack data**, say so explicitly and provide what you DO know with high confidence.

---

## OUTPUT FORMAT — Pick the MOST relevant format for "{kw}":

### FORMAT A — Geography/Place (Rivers, Lakes, Mountains, Passes, Plateaus, Islands):
- **About {kw}:** (Precise location — state(s), district(s), coordinates if notable; what it is; origin/formation)
- **Key Geographic Data:** (Length/Area/Elevation with numbers; tributaries with L/R bank; drainage basin area; geological formation type)
- **Climate & Soil:** (Rainfall range, temperature, soil type — laterite/alluvial/black etc.)
- **Biodiversity:** (Flora: name 3-5 species; Fauna: name 3-5 species with IUCN Red List status in parentheses)
- **Designations:** (Ramsar Site — year; UNESCO — year; National Park/Sanctuary — year; Biosphere Reserve — year. State "None" if not designated)
- **Economic & Strategic Significance:** (Resources, trade routes, projects, dams, irrigation schemes)
- **Recent News & Threats:** (Why in news; environmental threats; government projects)

### FORMAT B — Species / Biodiversity:
- **Identity:** (Common Name, **Scientific Name: _Genus species_**, Family, Order)
- **Physical Profile:** (Size: X cm/m; Weight: X kg; Distinguishing features; Coloration; Adaptations)
- **Habitat:** (Ecosystem type; Altitude range; Geographic distribution — states/countries; Forest type)
- **Ecology:** (Diet; Breeding season; Lifespan; Role in ecosystem — pollinator/predator/seed disperser)
- **Conservation Status:** (IUCN: [category]; CITES: Appendix [I/II/III]; WPA 1972: Schedule [I-VI]; State animal/bird of: [state])
- **Threats:** (Specific threats with data if available — habitat loss %, poaching statistics)
- **Conservation Programs:** (Project Tiger/Elephant/Dolphin; Breeding centers with location; Recovery plans)

### FORMAT C — Organization / Body / Scheme / Fund:
- **Genesis:** (Established: [exact date/year]; HQ: [city]; Parent: [Ministry/Department]; Enabling Act/Notification)
- **Type:** (Statutory body under [Act] / Constitutional body under Article [X] / Executive body / Autonomous)
- **Composition:** (Chairman appointment by [whom]; Members: [number and who appoints]; Current Chairman: [name if known])
- **Core Mandate:** (List 3-5 specific functions/powers with Section references)
- **Key Reports/Decisions:** (Name 2-3 landmark reports/recommendations with year)
- **Budget/Funding:** (Corpus size, funding mechanism, recent allocation if known)
- **Challenges:** (Specific implementation gaps, criticism, audit findings)
- **Current News Context:** (Why this entity is in news now)

### FORMAT D — Legal / Constitutional / Policy Framework:
- **Identity:** (Full title; Enacted: [date]; Article/Section number; Amendment number if applicable)
- **Historical Context:** (Why enacted; Which committee recommended it — name + year)
- **Key Provisions:** (List 4-6 specific sections/clauses with section numbers and what they provide)
- **Important Amendments:** (Amendment [number] in [year]: [what changed] — list top 3)
- **Landmark Judgments:** (Case name (Year): [1-line holding] — list 2-3 cases)
- **Current Relevance:** (Recent controversies, proposed amendments, news context)

### FORMAT E — International Relations / Treaties / Agreements:
- **Identity:** (Full name; Signed: [year]; Parties: [countries/organizations]; Secretariat: [city])
- **Objectives:** (List 3-4 core objectives)
- **Key Provisions:** (Specific articles/protocols with numbers)
- **India's Role:** (When India joined; India's commitments; Contributions)
- **Recent Developments:** (Latest COP/Summit; Key decisions; Controversies)

---

## MANDATORY FOR ALL TYPES:
- **📝 Prelims Flash Card:** (3-4 one-line facts formatted as "Q: ... → A: ..." that UPSC could directly test)
- **🎯 UPSC Relevance:** (GS Paper [1/2/3/4]; Specific syllabus topic; Why it's exam-worthy this year)
- **📚 NCERT Connection:** (Class [X], [Subject], Chapter: "[Name]" — provide a 2-3 sentence excerpt from that chapter that connects to this entity)
- **🔗 Related UPSC Topics:** (3 connected keywords/topics that UPSC clubs together with this)
- **✍️ Mains Answer Opening Line:** (A strong, quotable first sentence for a 250-word answer on this topic)

## QUALITY RULES:
- Every bullet point must contain a SPECIFIC fact (name, number, date, or Act/Article reference).
- Zero tolerance for generic statements like "It plays an important role in governance" — instead write "It advises the President under Article 280 on tax devolution between Centre and States".
- If a section doesn't apply to this entity type, SKIP it entirely — do NOT write "Not applicable".
- Target: 500-700 words of HIGH-DENSITY factual content."""
                                                    st.session_state["keyword_facts"][fact_key] = ask_llm_high_quality(kw_prompt)

                                    # Display all fetched deep-dives for this session
                                    all_fetched = [kw for kw in fetch_targets if f"{title_val}_{kw}" in st.session_state["keyword_facts"]]
                                    if all_fetched:
                                        for kw in all_fetched:
                                            with st.expander(f"📌 Deep-Dive: {kw}", expanded=True):
                                                st.markdown(
                                                    f'<div style="background:#1a1a2e; border-left:3px solid #7c3aed; padding:12px 16px; border-radius:6px;">'
                                                    f'</div>', unsafe_allow_html=True
                                                )
                                                st.markdown(st.session_state["keyword_facts"][f"{title_val}_{kw}"])
                                
                            if url_val: st.markdown(f"[🔗 Read Full Article]({url_val})")
                            st.markdown('</div>', unsafe_allow_html=True)
                    st.markdown("---")
