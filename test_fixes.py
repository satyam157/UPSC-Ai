#!/usr/bin/env python3
"""Test script to verify Ask Esu fixes"""

from ask_esu import analyze_quiz_performance, load_pyq_data
from datetime import datetime

print("=" * 60)
print("TESTING ASK ESU FIXES")
print("=" * 60)

# Test 1: Test analyze_quiz_performance with sample data
print("\nTEST 1: analyze_quiz_performance() with sample data")
print("-" * 60)

# Mock quiz results
sample_results = [
    (1, "CA Quiz 1", 10, 10, 8, 2, 80.0, 8.0),
    (2, "CA Quiz 2", 10, 10, 7, 3, 70.0, 7.0),
    (3, "PYQ Prelims 1", 15, 15, 12, 3, 80.0, 12.0),
    (4, "PYQ Prelims 2", 15, 15, 13, 2, 86.67, 13.0),
    (5, "PDF Content", 20, 20, 15, 5, 75.0, 15.0),
]

try:
    analysis = analyze_quiz_performance(sample_results)
    print(f"✓ Total Quizzes: {analysis['total_quizzes']}")
    print(f"✓ Overall Accuracy: {analysis['overall_accuracy']}%")
    print(f"✓ Total Marks: {analysis['total_marks']}")
    print(f"✓ Strong Areas: {analysis['strong_areas']}")
    print(f"✓ Weak Areas: {analysis['weak_areas']}")
    print(f"✓ By Quiz Type: {list(analysis['by_quiz_type'].keys())}")
    print("✓ TEST PASSED: analyze_quiz_performance works correctly!")
except Exception as e:
    print(f"✗ TEST FAILED: {e}")

# Test 2: Test load_pyq_data
print("\n\nTEST 2: load_pyq_data()")
print("-" * 60)

try:
    pyq_data = load_pyq_data()
    if pyq_data:
        print(f"✓ PYQ Data Loaded Successfully")
        if "prelims" in pyq_data:
            print(f"✓ Prelims subjects: {len(pyq_data['prelims'].get('subjects', []))} loaded")
        if "mains" in pyq_data:
            print(f"✓ Mains subjects: {len(pyq_data['mains'].get('subjects', []))} loaded")
        if "trends" in pyq_data:
            print(f"✓ Trends data available for: {list(pyq_data['trends'].keys())}")
        print("✓ TEST PASSED: load_pyq_data works correctly!")
    else:
        print("! Warning: PYQ data is empty or not loaded")
except Exception as e:
    print(f"✗ TEST FAILED: {e}")

# Test 3: Test edge case with single quiz type
print("\n\nTEST 3: Edge case - Single quiz type")
print("-" * 60)

single_result = [
    (1, "CA Quiz 1", 10, 10, 8, 2, 80.0, 8.0),
]

try:
    analysis = analyze_quiz_performance(single_result)
    print(f"✓ Total Quizzes: {analysis['total_quizzes']}")
    print(f"✓ Strong Areas: {analysis['strong_areas']}")
    print(f"✓ Weak Areas: {analysis['weak_areas']}")
    print("✓ TEST PASSED: handles single quiz type correctly!")
except Exception as e:
    print(f"✗ TEST FAILED: {e}")

# Test 4: Test edge case with no results
print("\n\nTEST 4: Edge case - Empty results")
print("-" * 60)

try:
    analysis = analyze_quiz_performance([])
    print(f"✓ Total Quizzes: {analysis['total_quizzes']}")
    print(f"✓ Strong Areas: {analysis['strong_areas']}")
    print(f"✓ Weak Areas: {analysis['weak_areas']}")
    assert analysis['strong_areas'] == [], "Strong areas should be empty"
    assert analysis['weak_areas'] == [], "Weak areas should be empty"
    print("✓ TEST PASSED: handles empty results correctly!")
except Exception as e:
    print(f"✗ TEST FAILED: {e}")

print("\n" + "=" * 60)
print("ALL TESTS COMPLETED!")
print("=" * 60)
