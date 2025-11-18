"""
Tests for ignore pattern functionality in AlderSync Client

Tests pattern matching and .aldersyncignore file handling.
"""

import sys
import os
import tempfile
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ignore_patterns import PatternMatcher, IgnorePatternManager


def test_pattern_matcher_wildcards():
    """Test wildcard pattern matching"""
    patterns = [
        "*.tmp",
        "*.log",
        ".DS_Store",
        "Thumbs.db"
    ]
    matcher = PatternMatcher(patterns)

    # Should ignore
    assert matcher.ShouldIgnore("file.tmp")
    assert matcher.ShouldIgnore("folder/file.tmp")
    assert matcher.ShouldIgnore("test.log")
    assert matcher.ShouldIgnore(".DS_Store")
    assert matcher.ShouldIgnore("Thumbs.db")

    # Should not ignore
    assert not matcher.ShouldIgnore("file.txt")
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


def test_ignore_pattern_manager():
    """Test IgnorePatternManager with temporary files"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create directory structure
        propresenter_root = temp_path / "ProPresenter"
        propresenter_root.mkdir()

        subfolder = propresenter_root / "Playlists"
        subfolder.mkdir()

        # Create .aldersyncignore in executable directory
        global_ignore = temp_path / ".aldersyncignore"
        global_ignore.write_text("*.tmp\n*.log\n")

        # Create .aldersyncignore in subfolder
        local_ignore = subfolder / ".aldersyncignore"
        local_ignore.write_text("*.bak\n")

        # Initialize manager
        manager = IgnorePatternManager(
            executable_dir=temp_path,
            propresenter_root=propresenter_root
        )
        manager.LoadPatterns()

        # Create test files
        file1 = propresenter_root / "test.tmp"
        file2 = propresenter_root / "test.txt"
        file3 = subfolder / "playlist.bak"
        file4 = subfolder / "playlist.txt"

        # Test global patterns
        assert manager.ShouldIgnore(file1)  # Ignored by global *.tmp
        assert not manager.ShouldIgnore(file2)  # Not ignored

        # Test directory-specific patterns
        assert manager.ShouldIgnore(file3)  # Ignored by local *.bak
        assert not manager.ShouldIgnore(file4)  # Not ignored

        print("IgnorePatternManager tests passed")


def test_filter_files():
    """Test filtering file lists"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        propresenter_root = temp_path / "ProPresenter"
        propresenter_root.mkdir()

        # Create .aldersyncignore
        ignore_file = temp_path / ".aldersyncignore"
        ignore_file.write_text("*.tmp\ncache/\n")

        # Initialize manager
        manager = IgnorePatternManager(
            executable_dir=temp_path,
            propresenter_root=propresenter_root
        )
        manager.LoadPatterns()

        # Create file list
        files = [
            propresenter_root / "file1.txt",
            propresenter_root / "file2.tmp",
            propresenter_root / "cache" / "data.txt",
            propresenter_root / "important.doc",
        ]

        # Filter files
        filtered = manager.FilterFiles(files)

        assert propresenter_root / "file1.txt" in filtered
        assert propresenter_root / "important.doc" in filtered
        assert propresenter_root / "file2.tmp" not in filtered
        assert propresenter_root / "cache" / "data.txt" not in filtered

        print("Filter files tests passed")


if __name__ == "__main__":
    print("Running Client ignore pattern tests...")
    print()

    test_pattern_matcher_wildcards()
    test_pattern_matcher_directories()
    test_pattern_matcher_negation()
    test_ignore_pattern_manager()
    test_filter_files()

    print()
    print("All tests passed!")
