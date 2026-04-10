"""
Quick test: Verify that the updated filter allows important PIB/DTE news through.
Tests the specific headlines the user mentioned were being dropped.
"""
from filter import is_relevant

# ─── PIB articles that SHOULD pass ────────────────────────────────────────────
pib_tests = [
    ("15th Round Commercial Coal Auction launched by Ministry of Coal", "pib"),
    ("Nari Shakti Vandan Adhiniyam: 33% reservation for women in Lok Sabha", "pib"),
    ("Kankaria Coaching Depot becomes India's first water-neutral coaching depot", "pib"),
    ("Cabinet approves significant rail infrastructure projects", "pib"),
    ("India's first commercial coal mine in Arunachal Pradesh announced", "pib"),
    ("Government updates SHAKTI Policy to optimize domestic coal use", "pib"),
    ("Delhi-Dehradun Economic Corridor wildlife section inaugurated", "pib"),
    ("India's merchandise and services exports for FY 2025-26 reached $800 billion", "pib"),
    ("AI Governance and Economic Group (AIGEG) formed for national AI strategy", "pib"),
    ("Kankaria Depot advanced wastewater treatment saves 1.60 lakh litres daily", "pib"),
    ("President Droupadi Murmu graces AIIMS Nagpur convocation ceremony", "pib"),
    ("Ministry of MSME workshop in Varanasi for toy and doll artisans under PM Vishwakarma", "pib"),
]

# ─── Down to Earth articles ───────────────────────────────────────────────────
dte_tests = [
    ("Rising air pollution threatens children's health in Indian cities", "down to earth"),
    ("Groundwater depletion in Punjab: A crisis in the making", "down to earth"),
    ("Forest fires and climate change: What the data tells us", "down to earth"),
    ("India's wetlands face growing threat from urbanisation", "down to earth"),
]

# ─── Articles that SHOULD be rejected (entertainment/sports) ─────────────────
reject_tests = [
    ("IPL auction: Mumbai Indians buy new player for 12 crore", "cricket news"),
    ("Bollywood star's wedding ceremony photos go viral", "entertainment"),
    ("Netflix show review: Best web series to watch this weekend", "ott news"),
    ("Celebrity gossip: Who is dating whom in Tollywood", "gossip"),
]

# ─── Neutral articles from non-trusted sources (need keywords) ────────────────
neutral_tests = [
    ("Local theft reported in Kanpur market area", "local news"),       # Should fail (blacklisted)
    ("New government policy on electric vehicles announced", "news"),   # Should pass (has keywords)
    ("Random blog post about weekend plans", "blog"),                   # Should fail (no keywords)
]

print("=" * 70)
print("FILTER v4.0 VALIDATION TEST")
print("=" * 70)

print("\n📢 PIB Articles (ALL should PASS):")
pib_pass = 0
for title, src in pib_tests:
    result = is_relevant(title, source_label=src, title=title)
    status = "✅ PASS" if result else "❌ FAIL"
    if result: pib_pass += 1
    print(f"  {status}: {title[:65]}")
print(f"  → {pib_pass}/{len(pib_tests)} passed")

print("\n🌍 Down to Earth Articles (ALL should PASS):")
dte_pass = 0
for title, src in dte_tests:
    result = is_relevant(title, source_label=src, title=title)
    status = "✅ PASS" if result else "❌ FAIL"
    if result: dte_pass += 1
    print(f"  {status}: {title[:65]}")
print(f"  → {dte_pass}/{len(dte_tests)} passed")

print("\n🚫 Reject Articles (ALL should FAIL):")
reject_pass = 0
for title, src in reject_tests:
    result = is_relevant(title, source_label=src, title=title)
    status = "✅ REJECTED" if not result else "❌ LEAKED THROUGH"
    if not result: reject_pass += 1
    print(f"  {status}: {title[:65]}")
print(f"  → {reject_pass}/{len(reject_tests)} correctly rejected")

print("\n🔍 Neutral Articles (mixed expectations):")
for title, src in neutral_tests:
    result = is_relevant(title, source_label=src, title=title)
    status = "PASS" if result else "FAIL"
    print(f"  {'✅' if result else '⬚'} {status}: {title[:65]} [source: {src}]")

total_tests = len(pib_tests) + len(dte_tests) + len(reject_tests)
total_correct = pib_pass + dte_pass + reject_pass
print(f"\n{'=' * 70}")
print(f"OVERALL: {total_correct}/{total_tests} core tests correct")
if total_correct == total_tests:
    print("🎉 ALL TESTS PASSED — Filter v4.0 is working correctly!")
else:
    print("⚠️  Some tests failed — review the filter logic.")
print("=" * 70)
