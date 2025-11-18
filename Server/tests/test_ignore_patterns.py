"""
Tests for ignore pattern functionality in AlderSync Server

Tests pattern matching, filtering, and database operations for ignore patterns.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ignore_patterns import PatternMatcher, LoadPatternsFromDatabase


def test_pattern_matcher_wildcards():
    """Test wildcard pattern matching"""
    patterns = [
        "*.tmp",
        "*.log",
        ".DS_Store"
    ]
    matcher = PatternMatcher(patterns)

    # Should ignore
    assert matcher.ShouldIgnore("file.tmp")
    assert matcher.ShouldIgnore("folder/file.tmp")
    assert matcher.ShouldIgnore("test.log")
    assert matcher.ShouldIgnore(".DS_Store")

    # Should not ignore
    assert not matcher.ShouldIgnore("file.txt")
    assert not matcher.ShouldIgnore("file.tmp.bak")
    assert not matcher.ShouldIgnore("important.doc")

    print("Wildcard pattern tests passed")


def test_pattern_matcher_directories():
    """Test directory pattern matching"""
    patterns = [
        "cache/",
        "logs/*.txt"
    ]
    matcher = PatternMatcher(patterns)

    # Should ignore
    assert matcher.ShouldIgnore("cache/file.txt")
    assert matcher.ShouldIgnore("cache/subfolder/file.txt")
    assert matcher.ShouldIgnore("logs/error.txt")
    # Note: "cache/" pattern also matches "cache" itself
    assert matcher.ShouldIgnore("cache")

    # Should not ignore
    assert not matcher.ShouldIgnore("logs/error.log")
    assert not matcher.ShouldIgnore("other/file.txt")

    print("Directory pattern tests passed")


def test_pattern_matcher_negation():
    """Test negation pattern matching"""
    patterns = [
        "*.log",
        "!important.log"
    ]
    matcher = PatternMatcher(patterns)

    # Should ignore
    assert matcher.ShouldIgnore("error.log")
    assert matcher.ShouldIgnore("debug.log")

    # Should not ignore (negated)
    assert not matcher.ShouldIgnore("important.log")

    print("Negation pattern tests passed")


def test_pattern_matcher_comments():
    """Test comment and blank line handling"""
    patterns = [
        "# This is a comment",
        "",
        "*.tmp",
        "   ",
        "# Another comment",
        "*.log"
    ]
    matcher = PatternMatcher(patterns)

    # Should ignore
    assert matcher.ShouldIgnore("file.tmp")
    assert matcher.ShouldIgnore("file.log")

    # Should not ignore
    assert not matcher.ShouldIgnore("# This is a comment")
    assert not matcher.ShouldIgnore("file.txt")

    print("Comment pattern tests passed")


def test_filter_paths():
    """Test filtering a list of paths"""
    patterns = [
        "*.tmp",
        "cache/"
    ]
    matcher = PatternMatcher(patterns)

    paths = [
        "file1.txt",
        "file2.tmp",
        "cache/data.txt",
        "important.doc",
        "temp.tmp"
    ]

    filtered = matcher.FilterPaths(paths)

    assert "file1.txt" in filtered
    assert "important.doc" in filtered
    assert "file2.tmp" not in filtered
    assert "cache/data.txt" not in filtered
    assert "temp.tmp" not in filtered

    print("Filter paths tests passed")


def test_pattern_matching_edge_cases():
    """Test edge cases in pattern matching"""
    patterns = [
        "test",
        "folder/specific.txt"
    ]
    matcher = PatternMatcher(patterns)

    # Test matching component name in path
    assert matcher.ShouldIgnore("test")
    assert matcher.ShouldIgnore("folder/test")
    assert matcher.ShouldIgnore("test/file.txt")

    # Test specific path
    assert matcher.ShouldIgnore("folder/specific.txt")

    # Should not ignore
    assert not matcher.ShouldIgnore("testing.txt")
    assert not matcher.ShouldIgnore("other/specific.txt")

    print("Edge case tests passed")


if __name__ == "__main__":
    print("Running ignore pattern tests...")
    print()

    test_pattern_matcher_wildcards()
    test_pattern_matcher_directories()
    test_pattern_matcher_negation()
    test_pattern_matcher_comments()
    test_filter_paths()
    test_pattern_matching_edge_cases()

    print()
    print("All tests passed!")
