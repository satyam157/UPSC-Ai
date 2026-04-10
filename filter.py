def is_relevant(text):
    text = text.lower()

    blacklist = [
        # ── Elections & Voting ──
        "election", "vote", "voting", "ballot", "poll", "bypoll",
        "by-poll", "exit poll", "polling booth", "evm", "vvpat",
        "nomination", "candidature", "re-election",

        # ── Political Parties ──
        "bjp", "congress", "aap", "tmc", "shiv sena", "ncp",
        "jdu", "rjd", "bsp", "samajwadi", "dmk", "aiadmk",
        "cpi", "cpim", "jmm", "akali dal", "ysrcp", "trs", "brs",
        "jds", "ljp", "rlsp", "mns", "aimim", "iuml",
        "political party", "coalition", "alliance", "seat sharing",

        # ── Political Leaders ──
        "modi", "rahul", "sonia gandhi", "priyanka gandhi",
        "amit shah", "kejriwal", "mamata", "yogi", "nitish",
        "lalu", "mayawati", "akhilesh", "uddhav", "fadnavis",
        "stalin", "jagan", "kcr", "siddaramaiah", "shinde",
        "tejashwi", "owaisi", "gadkari",

        # ── Political Jargon ──
        "campaign", "seat", "manifesto", "rally", "roadshow",
        "mla", "mp ", "lok sabha seat", "rajya sabha seat",
        "horse trading", "floor test", "no confidence",
        "political crisis", "defection", "anti-defection",

        # ── Bollywood & Entertainment ──
        "bollywood", "hollywood", "tollywood", "kollywood",
        "actress", "actor", "film star", "movie star",
        "box office", "blockbuster", "trailer launch",
        "ott release", "web series", "celebrity",
        "red carpet", "award show", "filmfare",
        "iifa", "kapoor", "khan", "deepika", "ranveer",
        "alia bhatt", "ranbir", "salman", "shahrukh", "srk",
        "akshay kumar", "anushka", "katrina", "kareena",
        "priyanka chopra", "bigg boss", "koffee with karan",
        "gossip", "paparazzi", "stardom",

        # ── Sports Gossip & Non-UPSC Sports ──
        "ipl", "cricket score", "match result", "toss",
        "man of the match", "fantasy league", "dream11",
        "premier league", "la liga", "champions league",
        "transfer window", "football club", "wwe",

        # ── Local News / Crime / Accidents ──
        "road accident", "car crash", "bike accident",
        "murder case", "stabbing", "robbery", "theft",
        "kidnapping", "chain snatching", "eve teasing",
        "domestic violence case", "dowry death",
        "pothole", "waterlogging", "traffic jam",
        "local body", "municipal", "panchayat election",
        "ward", "corporator", "gram sabha",

        # ── Social Media / Viral / Clickbait ──
        "viral video", "trending", "meme", "troll",
        "twitter war", "instagram", "influencer",
        "youtuber", "reels", "hashtag",
        "controversy", "row erupts", "slams",
        "lashes out", "hits back", "war of words",

        # ── Astrology / Horoscope ──
        "horoscope", "zodiac", "rashifal", "astrology",
        "kundli", "numerology",

        # ── Lifestyle / Misc Irrelevant ──
        "weight loss", "diet plan", "skincare",
        "relationship advice", "dating tips",
        "shopping sale", "discount offer", "amazon sale",
        "flipkart sale",
    ]

    if len(text) < 40:
        return False

    for word in blacklist:
        if word in text:
            return False

    return True