"""
UPSC News Relevance Filter v4.2
=================================
Core logic for determining if an article or topic is relevant for UPSC exam preparation.

v4.0 Changes:
  - "Neutral" articles (neither whitelisted nor blacklisted) from trusted sources
    now PASS by default — this prevents silently dropping important PIB/DTE articles
    on novel topics the keyword bank hasn't anticipated.
  - Blacklist split into HARD (instant reject: entertainment, sports, gossip)
    and SOFT (score penalty: administrative/ceremonial content that *might* still
    be relevant when combined with policy keywords).
  - Expanded keyword bank with recent UPSC-relevant terms.
  - Down to Earth, Yojana, Kurukshetra treated as premium sources.
  - Source-based trust tiers: Trusted sources need a much lower threshold.

v4.1 Changes (Audit-driven):
  - HARD_BLACKLIST: added hate-crime, royal-visit, live-ticker, satellite-name-generator
    and other noise patterns identified from the 2026-04 Filter Audit (72% → target 85%+).
  - HIGH_VALUE_KEYWORDS: added economic-sanctions, cybersecurity-threat, SDG, pharma,
    supply-chain, strait-of-hormuz, nuclear-deal, helium, FTA specifics.
  - New `score_article()` helper returns (passes: bool, score: float, reasons: list)
    for debugging and the DB audit runner.
  - Daily Relevance Score target: 85%+

v4.2 Changes (2026 Hot Topics + Feed Expansion):
  - HIGH_VALUE_KEYWORDS: added Operation Sindoor, NISAR satellite, India-Pakistan LOC
    tensions, Waqf Amendment Act, One Nation One Election, TRAI, NCERT overhaul,
    PM-KISAN 19th installment, SCO, Manipur crisis, climate finance GAP, CAATSA.
  - HARD_BLACKLIST: added celebrity rankings, award show red-carpets, sports trophies,
    viral social media trends, clickbait quiz formats.
  - SOFT_BLACKLIST: added corporate earnings noise, app update reviews, IPO grey market.
  - `score_article()`: now returns `hv_hits_count` + `generic_hits_count` for quick
    numeric comparison in audit dashboards.

v4.3 Changes (False-Positive Audit — HARD → SOFT demotions):
  Problem: broad single-word phrases in HARD_BLACKLIST were blocking legitimate
  UPSC articles because the check is a bare substring match (no word boundary).

  Moved HARD → SOFT (scoring penalty instead of instant reject):
    'theft'      → dual-use: 'data theft', 'AI theft', 'IP theft by China' are UPSC-relevant.
                   Added specific variants 'petty theft', 'vehicle theft' to HARD.
    'cricket'    → dual-use: 'cricket diplomacy', 'BCCI governance reform' are UPSC-relevant.
                   Replaced with 'cricket match', 'cricket score', 'cricket result' in HARD.
    'football'   → dual-use: 'football diplomacy', 'FIFA India policy' occasionally UPSC.
                   Replaced with 'football match', 'football score', 'football result' in HARD.
    'tennis'     → dual-use: 'lawn tennis federation', 'sports ministry' occasionally UPSC.
                   Replaced with 'tennis match', 'tennis result' in HARD.
    'hate crime' → dual-use: 'hate crime legislation', 'SC judgment on hate speech'.
                   Kept 'hate attack' in HARD (pure incident reporting).
    'murder case'→ dual-use: 'SC verdict on murder case' (capital punishment jurisprudence).
    'tiktok ban' → UPSC-relevant: digital sovereignty, data privacy, app-ban policy.
"""

import re

# ─── SOURCE MARKERS ────────────────────────────────────────────────────────────
EDITORIAL_MARKERS = [
    "the hindu editorial", "hindu editorial", "th editorial",
    "the hindu opinion", "the hindu op-ed", "the hindu lead",
    "the hindu analysis", "editorial - the hindu",
    "opinion - the hindu", "today's editorial",
    "indian express explained", "ie explained", "express explained",
    "indian express opinion", "ie opinion", "express editorial",
    "the indian express editorial",
    "explained:", "explained |", "what is ", "what are ", "why is ", 
    "why are ", "how does ", "how do ", "how india", "who is ",
    "bs editorial", "business standard editorial",
    "et editorial", "economic times editorial",
    "livemint editorial", "mint view",
]

# ─── TRUSTED UPSC SOURCES ─────────────────────────────────────────────────────
# Articles from these sources that aren't blacklisted will pass with lower threshold.
# This prevents dropping important government/environment news on novel topics.
TRUSTED_SOURCE_MARKERS = [
    "pib", "press information bureau",
    "down to earth", "downtoearth",
    "yojana", "kurukshetra",
    "the hindu editorial", "hindu editorial",
    "the hindu opinion", "the hindu op-ed", "the hindu lead",
    "ie explained", "indian express explained", "express explained",
    "indian express opinion",
    "bs editorial", "business standard editorial",
    "livemint editorial",
]

# ─── UPSC-RELEVANT FEED CATEGORIES ────────────────────────────────────────────
# Articles from these curated feed sections (Hindu S&T, IE World, etc.) already
# have an editorial filter applied by the publisher — the section curation itself
# is a signal of relevance. We apply a LENIENT threshold (block only true waste)
# instead of requiring heavy keyword matches.
UPSC_RELEVANT_CATEGORIES = {
    "science & technology", "science and technology",
    "international", "world",
    "economy", "business",
    "polity", "national",
    "lead", "op-ed", "opinion",
    "environment", "ecology",
    "governance",
    "analysis", "explained", "editorial",
}

# ─── KEYWORD BANK ──────────────────────────────────────────────────────────────
# Keywords are matched case-insensitively. Word boundaries \b are used for length > 3.
HIGH_VALUE_KEYWORDS = [
    "constitution", "fundamental rights", "directive principles", "fundamental duties",
    "supreme court", "high court", "judiciary", "judicial", "seventh schedule", "parliament",
    "lok sabha", "rajya sabha", "ordinance", "anti-defection", "federalism",
    "eci", "election commission", "delimitation", "civil services", "nias", "cbi", "ed",
    "cag", "lokpal", "rti", "e-governance", "tripartite", "inter-state council",
    "fiscal deficit", "monetary policy", "mpc", "rbi", "gst", "inflation",
    "cpi", "wpi", "gdp", "gva", "balance of payments", "trade deficit", "fdi", "fpi",
    "disinvestment", "banking reform", "npa", "ibc", "msme", "sebi", "nabard",
    "special economic zone", "blue economy", "digital rupee", "crypto regulation",
    "unsc", "g20", "quad", "brics", "sco", "asean", "bimstec", "saarc", "unclos",
    "lac", "loc", "border management", "maritime security", "indo-pacific", 
    "global south", "strategic autonomy", "nuclear doctrine", "treaty", "accord",
    "bilateral agreement", "mou", "embassy", "consulate", "geopolitics",
    "climate change", "cop28", "cop27", "cop29", "cop30", "net zero", "carbon neutral", "net-zero",
    "green hydrogen", "renewable energy", "biodiversity", "wildlife protection",
    "national park", "tiger reserve", "wetland", "ramsar", "aqi",
    "environmental impact", "eia", "deforestation", "afforestation", "circular economy",
    "carbon pricing", "carbon tax", "carbon credit", "emission", "sustainability", "ecology",
    "subsidy", "msp", "minimum support price", "food security", "nfsa", "pds",
    "land reforms", "labor laws", "labour laws", "industrial policy", "startup india", "make in india",
    "poverty", "unemployment", "migration", "urbanization", "solid waste", "e-waste",
    "isro", "chandrayaan", "gaganyaan", "aditya-l1", "satellite", "semiconductor",
    "quantum computing", "artificial intelligence", "generative ai", "5g", "6g",
    "biotechnology", "nanotechnology", "nuclear reactor", "thorium", "defence acquisition",
    "indigenous", "atmanirbhar", "drdo", "missile", "stealth", "submarine", "vaccine",
    "malnutrition", "stunting", "wasting", "gender equality", "human rights",
    "reservation", "caste census", "obc", "sc/st", "tribal rights", "maternity benefit",
    "national education policy", "nep", "skill development", "primary health",
    "jal jeevan", "ayushman bharat", "hunger index", "human development index",
    "yojana", "kurukshetra", "india yearbook", "economic survey", "budget", "gazette",
    # v4.0 additions — recent UPSC-relevant terms
    "coal auction", "coal mine", "coal block", "commercial coal", "energy security",
    "nari shakti", "women reservation", "women's reservation", "vandan adhiniyam",
    "water neutral", "water-neutral", "phytoremediation", "wastewater treatment",
    "ai governance", "ai strategy", "ai policy", "national ai",
    "shakti policy", "domestic coal",
    "economic corridor", "delhi-dehradun", "wildlife corridor",
    "merchandise export", "services export", "export target",
    "pm vishwakarma", "vishwakarma scheme",
    "convocation", "aiims",
    "green credit", "green bond", "sovereign green bond",
    "critical minerals", "rare earth", "lithium",
    "national hydrogen mission", "solar energy", "wind energy",
    "smart city", "amrit bharat", "vande bharat",
    "digital india", "digital public infrastructure", "dpi",
    "upi", "aadhaar", "digilocker", "cowin",
    "niti aayog", "finance commission", "gst council",
    "national security", "internal security", "naxalism", "maoist",
    "northeast", "north east", "act east", "look east",
    "panchayati raj", "local governance", "73rd amendment", "74th amendment",
    "right to education", "right to health", "right to privacy",
    "uniform civil code", "ucc", "one nation one election",
    "cooperative federalism", "competitive federalism",
    "pradhan mantri", "pm kisan", "pm awas", "pm ujjwala",
    "ayushman bharat", "swachh bharat", "poshan abhiyaan",
    "national green tribunal", "ngt", "pollution control",
    "forest conservation", "compensatory afforestation",
    "disaster management", "ndma", "sdma", "flood", "cyclone", "earthquake",
    "space economy", "space debris", "space policy",
    "data protection", "data privacy", "digital personal data",
    "telecom", "broadcasting", "spectrum auction",
    "anti-corruption", "vigilance", "lokpal", "lokayukta",
    "women empowerment", "beti bachao", "she-box",
    "tribal welfare", "van dhan", "scheduled tribe",
    "minority welfare", "linguistic minority",
    "demographic dividend", "population policy",
    "electric vehicle", "ev policy", "battery storage",
    "blue flag", "heritage site", "unesco", "intangible heritage",
    "free trade agreement", "fta", "rcep", "cepa", "ceca",
    "wto", "world trade organization", "trade dispute",
    "un general assembly", "unga", "security council",
    "climate finance", "loss and damage", "adaptation fund",
    "paris agreement", "kyoto protocol", "montreal protocol",
    "ozone layer", "ozone depleting",
    "water crisis", "water scarcity", "groundwater", "river linking",
    "interlinking of rivers", "ken-betwa", "namami gange",
    "soil health", "desertification", "land degradation",
    "ocean economy", "deep sea mining", "antarctic treaty",
    "arctic council", "indo-arctic",
    # v4.1 additions — from 2026-04 Filter Audit
    # Geopolitics & IR
    "economic sanctions", "sanctions regime", "strait of hormuz", "nuclear agreement",
    "nuclear deal", "nuclear deterrence", "uranium enrichment",
    "geopolitical risk", "strategic competition", "power projection",
    "south china sea", "taiwan strait", "korean peninsula",
    "nato", "aukus", "i2u2", "miga", "pgii",
    # Cybersecurity (Audit finding: CERT-In/DeepSeek/AI theft news = high value)
    "cybersecurity", "cyber threat", "cyber attack", "data breach",
    "cert-in", "critical infrastructure", "ransomware", "zero-day",
    "information warfare", "deepfake", "ai theft", "data exfiltration",
    # Economy & Finance
    "supply chain", "supply chain disruption", "reshoring", "friend-shoring",
    "de-dollarisation", "de-dollarization", "currency swap", "dedollarization",
    "carbon border", "carbon border adjustment", "cbam",
    "pharmaceutical", "drug regulation", "drug approval", "drug pricing",
    "generic drug", "biosimilar", "medical device", "fda approval",
    "acquisition", "merger", "antitrust",
    # Sustainable Development
    "sustainable development goal", "sdg", "agenda 2030",
    "just transition", "green transition", "energy transition",
    "carbon capture", "carbon sequestration", "blue carbon",
    "ecosystem services", "nature-based solution",
    # Strategic resources (Audit: helium shortage linked to US-Israel-Iran conflict)
    "helium", "neon gas", "krypton", "xenon",   # rare industrial gases
    "tungsten", "cobalt", "manganese", "graphite",  # critical minerals
    # Gender & Social
    "women in science", "gender pay gap", "gender disparity",
    "maternal mortality", "child marriage", "girl education",
    # Health & Research
    "cancer research", "drug resistance", "antimicrobial resistance", "amr",
    "genome", "clinical trial", "precision medicine",
    "pneumonia", "tuberculosis", "malaria", "dengue", "pandemic preparedness",
    # v4.2 additions — 2026 Hot Topics & Exam-Specific Terms
    # India-Pakistan / Defence
    "operation sindoor", "surgical strike", "cross-border", "loc tension",
    "pulwama", "balakot", "article 370", "ceasefire violation",
    "india pakistan", "line of control", "indo-pak",
    "pahlgam attack", "pahalgam",
    # Space & S&T
    "nisar satellite", "nisar", "nasa isro", "gaganyaan mission",
    "space docking", "spadex", "reusable launch vehicle", "rlv",
    "one web", "starlink india", "spectrum sharing",
    # Constitutional & Governance
    "waqf amendment", "waqf act", "waqf board",
    "one nation one election", "simultaneous elections",
    "lateral entry", "upsc lateral", "ias reform",
    "delimitation commission", "eci eci",
    "trai", "telecom regulatory authority",
    "broadcast regulation", "ott regulation",
    # Economy & Trade
    "caatsa", "sanctions waiver", "s-400",
    "pm kisan", "pm-kisan installment", "kisan credit card",
    "msme credit", "priority sector lending",
    "repo rate", "reverse repo", "crr slr",
    "rupee depreciation", "current account deficit",
    "india stack", "ocen", "account aggregator",
    # Environment & Disaster
    "cyclone", "flood warning", "heat wave", "cold wave",
    "glacial lake outburst", "glof", "landslide",
    "ozone hole", "aerosol", "pm 2.5", "pm10",
    "species red list", "iucn", "wildlife trafficking",
    # Social & Education
    "ncert overhaul", "new ncert", "ncert textbook",
    "neet controversy", "cuet exam", "common university",
    "manipur crisis", "ethnic conflict", "inter-community",
    "scheduled area", "fifth schedule", "sixth schedule",
    "pesa act", "forest rights act", "fra",
    # International & Multilateral
    "sco summit", "brics expansion", "quad summit",
    "india africa", "india asean", "india gcc",
    "g7 summit", "g20 sherpa",
    "oecd pillar two", "global minimum tax",
    "un peacekeeping", "un reform",
    "imf world bank", "imf forecast",
    "belt and road", "bri", "debt trap",
    "global gateway",
    # Climate & Energy
    "cop30", "loss and damage fund", "climate finance gap",
    "solar rooftop", "pm surya ghar", "rooftop solar",
    "small modular reactor", "smr", "thorium reactor",
    "green ammonia", "green methanol",
    # v4.3 additions — keywords that pair with the demoted SOFT phrases
    # (ensures 'tiktok ban policy' and 'SC murder verdict' still pass)
    "tiktok", "app ban", "digital protectionism", "data sovereignty",
    "rarest of rare", "rarest-of-rare", "capital punishment", "death penalty", "sc judgment", "sc verdict",
    "hate speech law", "communal violence act", "nsa detention",
    "preventive detention", "sedition law", "uapa", "pota",
    "ip theft", "trade secret", "economic espionage",
    "bcci", "sports governance", "sports authority", "sports ministry",
]

GENERIC_KEYWORDS = [
    "government", "policy", "scheme", "ministry", "minister", "cabinet", "authority",
    "regulator", "digital", "technology", "science", "health", "education", "economy",
    "trade", "export", "import", "diplomacy", "foreign", "national", "international",
    "report", "survey", "index", "ranking", "agreement", "law", "act", "legislation",
    "regulation", "welfare", "programme", "mission", "initiative", "agriculture", 
    "farmer", "rural", "infrastructure", "highway", "railway", "power", "energy",
    "pollution", "environment", "security", "defence", "military", "police", 
    "justice", "election", "poll", "voting", "reform", "economic", "development",
    "global", "regional", "crisis", "growth", "investment", "tax", "banking",
    # v4.0 additions
    "auction", "corridor", "depot", "water", "carbon", "hydrogen",
    "green", "solar", "nuclear", "atomic", "space", "cyber",
    "tribal", "scheduled", "minority", "women", "gender",
    "innovation", "research", "patent", "intellectual property",
    "manufacturing", "industrial", "production", "procurement",
    "bilateral", "multilateral", "summit", "dialogue", "cooperation",
    "amendment", "bill", "notification", "gazette", "ordinance",
    "commission", "committee", "tribunal", "ombudsman",
    "transport", "logistics", "port", "shipping", "aviation",
    "housing", "urban", "migration", "displacement",
    "nutrition", "sanitation", "drinking water", "hygiene",
    "census", "demographic", "population",
    "connectivity", "broadband", "fiber", "telecom",
    "launched", "inaugurated", "approved", "sanctioned", "notified",
]

# ─── BLACKLIST (HARD — instant reject, truly irrelevant) ──────────────────────
# Only genuinely non-UPSC content goes here. Be conservative.
HARD_BLACKLIST = [
    # Entertainment / celebrity
    "bollywood", "hollywood", "tollywood", "celebrity gossip", "star kid",
    "movie review", "film review", "movie trailer", "film trailer", "trailer launch",
    "box office collection", "ott release", "netflix show", "amazon prime show",
    "web series", "bigg boss", "reality show", "celebrity wedding", "celebrity breakup",
    "dating advice", "fashion trends", "astrology", "viral video", "horoscope",
    "beauty tips", "skincare routine", "lifestyle hack",
    "celebrity ranking", "award show", "red carpet", "oscars fashion",
    "golden globes", "grammy winner", "bafta",
    # ── Sports (pure scores/match reports — NOT policy/governance) ──────────
    # KEPT specific: 'cricket match', 'cricket score', 'cricket result' block
    # score updates; bare 'cricket' moved to SOFT so 'cricket diplomacy' /
    # 'BCCI governance reform' still passes.
    "ipl auction", "ipl match", "ipl score", "ipl points table", "t20 match",
    "cricket match", "cricket score", "cricket result", "cricket highlights",
    "football match", "football score", "football result", "football highlights",
    "tennis match", "tennis result", "tennis score",
    "match result", "scorecard", "score update",
    "sports news", "sports update",
    "fifa world cup score", "champions league match", "premier league match",
    "la liga match", "wimbledon match", "us open tennis match", "french open match",
    # ── Crime / local incidents ───────────────────────────────────────────────
    # SPECIFIC variants in HARD; bare 'theft' / 'hate crime' / 'murder case'
    # moved to SOFT because they appear in policy/SC-judgment contexts.
    "accident news", "local crime",
    "petty theft", "vehicle theft", "house theft", "jewellery theft",  # specific petty crime
    "hate attack", "assaulted in",   # incident-only; 'hate crime' → SOFT
    "robbery", "gang violence", "serial killer",
    # ── Royal gossip / ceremonial visits ──────────────────────────────────────
    "king charles", "royal visit", "buckingham palace", "queen consort",
    "prince harry", "meghan markle", "royal family drama",
    # ── Live tickers / real-time noise ───────────────────────────────────────
    "live updates:", "live blog:", "as it happened:",
    # ── Clearly frivolous / gimmick content ───────────────────────────────────
    "name generator", "satellite name generator",
    "quiz: can you", "test yourself:",
    # ── Budget airline / airline bailouts (US domestic) ───────────────────────
    "budget airline", "american budget airline",
    # ── Viral / clickbait ─────────────────────────────────────────────────────
    "goes viral", "twitter trend", "instagram reel", "youtube shorts",
    # NOTE: 'tiktok ban' moved to SOFT — app-ban policy is UPSC-relevant
    #       (data sovereignty, digital protectionism, cybersecurity)
    # ── Pure consumer tech / gaming ───────────────────────────────────────────
    "iphone 17", "iphone 16", "samsung galaxy s",
    "playstation 6", "xbox series", "nintendo switch",
    "gaming headset", "best graphics card",
]

# ─── BLACKLIST (SOFT — score penalty, administrative/ceremonial fluff) ────────
# These are often low-value but SOMETIMES contain policy substance.
# Instead of instant reject, they get a score penalty (-1.5 each).
# If total penalty >= source bonus, the article gets blocked.
SOFT_BLACKLIST = [
    # Ceremonial / greetings
    "greetings", "condolences", "tribute to", "pays tribute",
    "birth anniversary", "death anniversary",
    "photo release", "media advisory", "curtain raiser", "video link",
    # PIB administrative fluff (not policy-substantive)
    "change of guard", "guard ceremony",
    "pension adalat", "life certificate camp", "life certificate",
    "blood donation", "swachhata pledge", "cleanliness drive",
    "yoga day celebration", "observes vigilance",
    "farewell function", "flag hoisting", "oath ceremony",
    "flower show", "cultural programme", "cultural event",
    "darpg", "cpgrams",
    # Hindi PIB empty/generic titles and condolences
    "\u092a\u094d\u0930\u0947\u0938 \u0935\u093f\u091c\u094d\u091e\u092a\u094d\u0924\u093f",  # "प्रेस विज्ञप्ति" (just "Press Release" — no info)
    "\u0936\u094b\u0915 \u0935\u094d\u092f\u0915\u094d\u0924 \u0915\u093f\u092f\u093e",  # "शोक व्यक्त किया" (expressed grief/condolences)
    "\u0936\u094d\u0930\u0926\u094d\u0927\u093e\u0902\u091c\u0932\u093f",  # "श्रद्धांजलि" (tribute)
    "\u0928\u093f\u0927\u0928",  # "निधन" (demise)
    # Routine military/naval movements (not strategic)
    "arrives at", "departs from", "port call at",
    "ins sudarshini", "ins tarangini",
    "no change of guard",
    # Corporate / consumer tech waste
    "layoff", "job cut", "hiring freeze", "mass firing", "slash jobs",
    "property fraud", "online scam", "how to stay safe", "digital trap",
    "gaming", "game launch", "esports", "cohort launch",
    "startup funding", "valuation round", "series a", "series b",
    "stock price", "share price", "market rally", "sensex",
    "iphone", "samsung galaxy", "pixel", "smartphone launch", "gadget review",
    "sale on amazon", "flipkart sale", "discount offer",
    "recipe", "lifestyle hack", "beauty tips", "skincare",
    # v4.2 additions — corporate earnings / IPO / app-update noise
    "quarterly earnings", "q3 results", "q4 results", "net profit rises",
    "ipo allotment", "ipo grey market", "gmp today", "listing gain",
    "app update", "new feature rollout", "version update", "patch notes",
    "unboxing", "hands-on review", "first look review",
    "best deals", "coupon code", "promo code",
    # ── v4.3 demotions from HARD_BLACKLIST ───────────────────────────────────
    # These phrases CAN appear in legitimate UPSC articles; penalty not rejection.
    "theft",        # 'data theft', 'AI theft', 'IP theft by China' = high UPSC value
    "cricket",      # 'cricket diplomacy', 'BCCI governance' = occasional UPSC value
    "football",     # 'football diplomacy', 'FIFA India policy' = occasional UPSC value
    "tennis",       # 'lawn tennis federation', 'sports ministry' = low but possible
    "hate crime",   # 'hate crime legislation', 'SC judgment on hate speech'
    "murder case",  # 'SC verdict in murder case' (capital punishment jurisprudence)
    "tiktok ban",   # app-ban policy: data sovereignty / digital protectionism / cybersecurity
]

# Keep the combined BLACKLIST for backward compatibility with any external code
BLACKLIST = HARD_BLACKLIST + SOFT_BLACKLIST

# ─── REGEX PATTERNS ────────────────────────────────────────────────────────────
def _compile_patterns(keywords):
    patterns = []
    for kw in keywords:
        kw_l = kw.lower()
        # Use word boundaries for all keywords to avoid false positives (e.g., 'ed' in 'closed')
        patterns.append(re.compile(r'\b' + re.escape(kw_l), re.I))
    return patterns

_HIGH_VAL_PATTERNS = _compile_patterns(HIGH_VALUE_KEYWORDS)
_GENERIC_PATTERNS  = _compile_patterns(GENERIC_KEYWORDS)

# ─── SOURCE DETECTION ──────────────────────────────────────────────────────────
def _is_trusted_source(source_label: str) -> bool:
    """Check if the source is a trusted UPSC-relevant source."""
    src = source_label.lower()
    return any(marker in src for marker in TRUSTED_SOURCE_MARKERS)

def _is_pib(source_label: str) -> bool:
    return "pib" in source_label.lower()

def _is_dte(source_label: str) -> bool:
    src = source_label.lower()
    return "down to earth" in src or "downtoearth" in src

# ─── MAIN RELEVANCE LOGIC ──────────────────────────────────────────────────────
def is_relevant(text: str, source_label: str = "", title: str = "",
                strict: bool = False, category: str = "") -> bool:
    """
    Weighted scoring system for UPSC relevance.
    
    v4.1 Key changes:
      - Category-aware thresholds: articles from UPSC-relevant feed sections
        (S&T, Economy, International, Environment, Polity, Lead/Op-Ed) get a
        lenient threshold because the section curation itself is a signal.
      - Trusted sources (PIB, DTE, Editorials) still get the lowest threshold.
      - True waste (Bollywood, cricket, gossip) is ALWAYS hard-blocked.
    
    Thresholds:
      - Trusted sources (PIB, DTE, Editorials):  score >= 1.0 (very lenient)
      - UPSC-relevant sections (S&T, Economy):   score >= 1.2 (lenient)
      - Normal sources (non-strict):              score >= 2.0
      - Normal sources (strict):                  score >= 3.0
    """
    # Use title if text is missing
    t_input = text if text and text.strip() else title
    if not t_input: return False
    
    t_full = (t_input + " " + source_label).lower()
    t_title = title.lower() if title else t_full
    
    # 1. Minimum length guard
    if len(t_full) < 10: return False

    # 2. HARD Blacklist check (Immediate Exit — truly irrelevant content)
    for phrase in HARD_BLACKLIST:
        if phrase in t_full: return False

    # 3. Score calculation
    score = 0.0
    soft_penalty = 0.0

    # Source trust detection
    src = source_label.lower()
    is_pib = _is_pib(source_label)
    is_dte = _is_dte(source_label)
    is_editorial = any(marker in src for marker in EDITORIAL_MARKERS)
    is_trusted = _is_trusted_source(source_label)
    
    # Category-based relevance detection
    cat_lower = category.lower().strip() if category else ""
    is_upsc_section = cat_lower in UPSC_RELEVANT_CATEGORIES
    
    # Source Bonus
    if is_editorial:
        score += 1.5
    elif is_pib:
        score += 1.5
    elif is_dte:
        score += 1.5
    elif is_trusted:
        score += 1.2
    
    # Hindi/Devanagari text detection
    has_devanagari = bool(re.search(r'[\u0900-\u097F]', t_full))
    
    # Category Bonus — articles from curated UPSC-relevant sections
    # get a smaller but meaningful boost because the section itself
    # implies relevance (Hindu S&T, IE Economy, Hindu International, etc.)
    if is_upsc_section:
        score += 1.0
        
    # 4. SOFT Blacklist check (score penalty, not instant reject)
    for phrase in SOFT_BLACKLIST:
        if phrase in t_full:
            soft_penalty += 1.5
    
    # PIB-specific: penalize (but don't kill) purely administrative items
    # Only very clearly non-substantive patterns get penalized
    if is_pib:
        pib_admin_patterns = ["media advisory", "curtain raiser", "video link"]
        for w in pib_admin_patterns:
            if w in t_title:
                soft_penalty += 2.0
        
        # Boost actual policy keywords for PIB (English)
        pib_policy_words = [
            "cabinet", "mou", "agreement", "sanctioned", "launched", "scheme", 
            "policy", "approved", "notified", "inaugurated", "auction",
            "corridor", "amendment", "act", "bill", "mission", "initiative",
            "export", "import", "production", "manufacturing", "billion",
            "crore", "lakh", "water", "energy", "coal", "rail", "highway",
            "governance", "strategy", "reform", "welfare", "reservation",
        ]
        if any(w in t_full for w in pib_policy_words):
            score += 1.0

        # Boost actual policy keywords for PIB (Hindi / Devanagari)
        if has_devanagari:
            hindi_policy_words = [
                "योजना", "नीति", "मंजूरी", "समझौता", "हस्ताक्षर", "समझौता ज्ञापन",
                "उद्घाटन", "शिलान्यास", "लागू", "अधिसूचित", "पारित", "संशोधन",
                "विधेयक", "अधिनियम", "मिशन", "पहल", "कैबिनेट", "मंत्रिमंडल",
                "आयोग", "समिति", "निर्यात", "आयात", "उत्पादन", "विनिर्माण",
                "करोड़", "अरब", "अर्थव्यवस्था", "विकास", "पर्यावरण", "रक्षा",
                "विज्ञान", "प्रौद्योगिकी", "कृषि", "स्वास्थ्य", "बुनियादी ढांचा",
                "रेलवे", "राजमार्ग", "समझौते", "समझौतों", "परियोजना", "परियोजनाओं",
                "बैठक", "समीक्षा", "महासभा", "शिखर सम्मेलन", "सम्मेलन"
            ]
            if any(w in t_full for w in hindi_policy_words):
                score += 1.0

    # Keyword matching
    high_val_hits = 0
    for pat in _HIGH_VAL_PATTERNS:
        if pat.search(t_title): 
            score += 2.0
            high_val_hits += 1
        elif pat.search(t_full): 
            score += 1.0
            high_val_hits += 1
    
    generic_hits = 0
    for pat in _GENERIC_PATTERNS:
        if pat.search(t_title): 
            score += 1.0
            generic_hits += 1
        elif pat.search(t_full): 
            score += 0.5
            generic_hits += 1

    # Apply soft penalty
    score -= soft_penalty

    # 5. Threshold determination
    #
    #  Tier 1 — Trusted sources (PIB, DTE, Editorials):
    #           Source bonus (1.5) + at least 1 generic keyword (0.5) = 2.0
    #           This ensures even trusted sources need SOME policy substance.
    #           Filters out empty titles, guard ceremonies, pension camps, etc.
    #
    #  Tier 2 — UPSC-relevant sections (S&T, Economy, International,
    #           Environment, Polity, Lead/Op-Ed):
    #           Category bonus (1.0) + any generic keyword (0.5) = 1.5
    #           Section curation helps, but need minimal keyword evidence.
    #
    #  Tier 3 — Normal sources:
    #           Need solid keyword evidence. threshold = 2.5
    #
    if is_trusted:
        threshold = 2.0    # Trusted: needs source bonus + ≥1 keyword
    elif is_upsc_section:
        threshold = 1.5    # UPSC section: category bonus + ≥1 keyword
    elif strict:
        threshold = 3.0    # Strict: need solid keyword evidence
    else:
        threshold = 2.5    # Normal: moderate keyword evidence needed
    
    return score >= threshold

def detect_source_label(url: str = "", feed_title: str = "") -> str:
    """Infers a source label from URL or feed title."""
    s = (url + " " + feed_title).lower()
    if "editorial" in s: return "Editorial"
    if "pib.gov.in" in s: return "PIB"
    if "downtoearth" in s: return "Down to Earth"
    return "News"


# ─── TITLE NORMALIZER (used for deduplication in fetcher) ─────────────────────
_LIVE_PREFIX = re.compile(
    r'^(LIVE\s*:?\s*|BREAKING\s*:?\s*|JUST\s*IN\s*:?\s*|UPDATE\s*:?\s*)',
    re.IGNORECASE
)

def normalize_title(title: str) -> str:
    """
    Strip 'LIVE:', 'BREAKING:', 'JUST IN:' prefixes and lowercase for dedup.
    Example: 'LIVE: India-Iran talks' → 'india-iran talks'
    """
    cleaned = _LIVE_PREFIX.sub("", title.strip())
    return cleaned.lower().strip()


# ─── SCORE ARTICLE (debug / audit helper) ─────────────────────────────────────
def score_article(
    title: str,
    text: str = "",
    source_label: str = "",
    category: str = "",
    strict: bool = False,
) -> dict:
    """
    Return a full scoring breakdown for an article — useful for:
      • DB audit (filter_reviewer.py)
      • Streamlit debug panel
      • Unit tests

    Returns
    -------
    dict with keys:
        passes      : bool   — True if article would pass the filter
        score       : float  — raw relevance score
        threshold   : float  — threshold used for this source/category
        hard_blocked: bool   — True if caught by HARD_BLACKLIST
        soft_hits   : list   — SOFT_BLACKLIST phrases matched
        hv_hits     : list   — HIGH_VALUE_KEYWORDS matched
        generic_hits: list   — GENERIC_KEYWORDS matched
        source_bonus: float  — bonus awarded for source tier
        category_bonus: float— bonus awarded for UPSC-relevant category
    """
    t_input = text if text and text.strip() else title
    if not t_input:
        return {
            "passes": False, "score": 0.0, "threshold": 0.0,
            "hard_blocked": False, "soft_hits": [], "hv_hits": [],
            "generic_hits": [], "source_bonus": 0.0, "category_bonus": 0.0,
            "reason": "empty input",
        }

    t_full  = (t_input + " " + source_label).lower()
    t_title = title.lower() if title else t_full

    # 1. Minimum length
    if len(t_full) < 10:
        return {
            "passes": False, "score": 0.0, "threshold": 0.0,
            "hard_blocked": False, "soft_hits": [], "hv_hits": [],
            "generic_hits": [], "source_bonus": 0.0, "category_bonus": 0.0,
            "reason": "text too short",
        }

    # 2. Hard blacklist
    hard_blocked = False
    for phrase in HARD_BLACKLIST:
        if phrase in t_full:
            hard_blocked = True
            return {
                "passes": False, "score": 0.0, "threshold": 0.0,
                "hard_blocked": True, "soft_hits": [], "hv_hits": [],
                "generic_hits": [], "source_bonus": 0.0, "category_bonus": 0.0,
                "reason": f"HARD_BLACKLIST: '{phrase}'",
            }

    # 3. Source tier
    src = source_label.lower()
    is_pib       = _is_pib(source_label)
    is_dte       = _is_dte(source_label)
    is_editorial = any(m in src for m in EDITORIAL_MARKERS)
    is_trusted   = _is_trusted_source(source_label)

    cat_lower     = category.lower().strip() if category else ""
    is_upsc_sec   = cat_lower in UPSC_RELEVANT_CATEGORIES

    source_bonus = 0.0
    if is_editorial:   source_bonus = 1.5
    elif is_pib:       source_bonus = 1.5
    elif is_dte:       source_bonus = 1.5
    elif is_trusted:   source_bonus = 1.2

    category_bonus = 1.0 if is_upsc_sec else 0.0

    score = source_bonus + category_bonus

    # 4. Soft blacklist
    soft_hits = []
    soft_penalty = 0.0
    for phrase in SOFT_BLACKLIST:
        if phrase in t_full:
            soft_hits.append(phrase)
            soft_penalty += 1.5

    if is_pib:
        pib_admin_patterns = ["media advisory", "curtain raiser", "video link"]
        for w in pib_admin_patterns:
            if w in t_title:
                soft_hits.append(f"pib-admin:{w}")
                soft_penalty += 2.0

        pib_policy_words = [
            "cabinet", "mou", "agreement", "sanctioned", "launched", "scheme",
            "policy", "approved", "notified", "inaugurated", "auction",
            "corridor", "amendment", "act", "bill", "mission", "initiative",
            "export", "import", "production", "manufacturing", "billion",
            "crore", "lakh", "water", "energy", "coal", "rail", "highway",
            "governance", "strategy", "reform", "welfare", "reservation",
        ]
        if any(w in t_full for w in pib_policy_words):
            score += 1.0

    score -= soft_penalty

    # 5. Keyword matching
    hv_hits = []
    for i, pat in enumerate(_HIGH_VAL_PATTERNS):
        if pat.search(t_title):
            score += 2.0
            hv_hits.append(HIGH_VALUE_KEYWORDS[i])
        elif pat.search(t_full):
            score += 1.0
            hv_hits.append(HIGH_VALUE_KEYWORDS[i])

    gen_hits = []
    for i, pat in enumerate(_GENERIC_PATTERNS):
        if pat.search(t_title):
            score += 1.0
            gen_hits.append(GENERIC_KEYWORDS[i])
        elif pat.search(t_full):
            score += 0.5
            gen_hits.append(GENERIC_KEYWORDS[i])

    # 6. Threshold
    if is_trusted:     threshold = 2.0
    elif is_upsc_sec:  threshold = 1.5
    elif strict:       threshold = 3.0
    else:              threshold = 2.5

    passes = score >= threshold
    reason = "PASS" if passes else f"score {score:.1f} < threshold {threshold:.1f}"

    return {
        "passes":         passes,
        "score":          round(score, 2),
        "threshold":      threshold,
        "hard_blocked":   False,
        "soft_hits":      soft_hits,
        "hv_hits":        hv_hits[:10],   # cap for readability
        "generic_hits":   gen_hits[:10],
        "source_bonus":   source_bonus,
        "category_bonus": category_bonus,
        "reason":         reason,
    }