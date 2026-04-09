def is_relevant(text):
    text = text.lower()

    blacklist = [
        "election", "vote", "bjp", "congress",
        "rahul", "modi", "campaign", "seat","manifesto",
        "political party"
    ]

    if len(text) < 40:
        return False

    for word in blacklist:
        if word in text:
            return False

    return True