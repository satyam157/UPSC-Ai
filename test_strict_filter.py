#!/usr/bin/env python3
"""Test strict UPSC relevance filtering for Syllabus Resources"""

from scraper import is_upsc_relevant_topic

test_cases = {
    # Valid UPSC topics
    "National Education Policy 2020": True,
    "Pradhan Mantri Ujjwala Yojana": True,
    "Supreme Court ruling on RTI": True,
    "Economic Survey: Inflation Control": True,
    "Budget 2026: Infrastructure Investment": True,
    "India Yearbook: Constitutional Bodies": True,
    "Carbon Pricing Mechanism in India": True,
    "Agricultural Subsidy Reform": True,
    "Foreign Direct Investment Policy": True,
    "Environmental Protection Act": True,
    
    # Invalid topics
    "Bollywood actress wins award": False,
    "Cricket match results": False,
    "IPL tournament updates": False,
    "Celebrity gossip": False,
    "Weight loss diet": False,
    "Fashion trends 2026": False,
    "Astrology predictions": False,
    "Dating advice": False,
    "Viral video trending": False,
    "Local accident news": False,
    
    # Edge cases
    "AI": False,  # Too short
    "Food inflation": True,  # Has relevant keywords
    "Government policy": True,  # Basic policy term
}

print("=" * 80)
print("TESTING STRICT UPSC RELEVANCE FOR SYLLABUS RESOURCES")
print("=" * 80)

passed = 0
failed = 0

for topic, expected in test_cases.items():
    result = is_upsc_relevant_topic(topic)
    status = "✓" if result == expected else "✗"
    
    if result == expected:
        passed += 1
    else:
        failed += 1
    
    print(f"{status} [{result:5}] {topic}")

print("=" * 80)
print(f"✅ Passed: {passed}/{len(test_cases)}")
print(f"❌ Failed: {failed}/{len(test_cases)}")
print("=" * 80)

if failed == 0:
    print("\n✅ All tests passed! Strict filtering is working correctly.")
else:
    print(f"\n⚠️ Some tests failed. Review the filter logic.")
