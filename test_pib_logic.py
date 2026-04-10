
from filter import is_relevant

articles = [
    {"title": "PM greetings on festive occasion", "source": "pib", "expected": False},
    {"title": "Cabinet approves MoU between India and Bhutan on energy", "source": "pib", "expected": True},
    {"title": "Media Advisory: Visit of President to Mumbai", "source": "pib", "expected": False},
    {"title": "Ministry of Finance releases GDP data for Q3", "source": "pib", "expected": True},
    {"title": "Photo Release: PM interaction with farmers", "source": "pib", "expected": False},
    {"title": "Government launches new scheme for MSMEs", "source": "pib", "expected": True},
]

print(f"{'TITLE':<60} {'ACTUAL':<8} {'EXPECTED':<8}")
print("-" * 80)
for a in articles:
    res = is_relevant(a['title'], source_label=a['source'], title=a['title'], strict=False)
    print(f"{a['title']:<60} {str(res):<8} {str(a['expected']):<8}")
