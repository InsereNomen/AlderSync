"""
AlderSync Server - Ignore Pattern Matching

This module provides gitignore-style pattern matching functionality.
Supports wildcards, directory patterns, negation, and comments.
"""

import logging
from pathlib import Path
from typing import List, Tuple
import fnmatch

logger = logging.getLogger(__name__)


class PatternMatcher:
    """
    Matches file paths against gitignore-style patterns

    Supports:
    - Wildcards: *, ?, [abc]
    - Directory patterns: trailing /
    - Negation: ! prefix
    - Comments: # prefix (ignored)
    - Blank lines (ignored)
    """

    def __init__(self, patterns: List[str], base_path: str = ""):
        """
        Initialize pattern matcher

        Args:
            patterns: List of pattern strings (can include comments and blank lines)
            base_path: Base directory path for relative pattern matching
        """
        self.base_path = Path(base_path) if base_path else Path()
        self.patterns = self.ParsePatterns(patterns)

    def ParsePatterns(self, pattern_lines: List[str]) -> List[Tuple[str, bool]]:
        """
        Parse pattern lines into (pattern, is_negation) tuples

        Args:
            pattern_lines: Raw pattern strings

        Returns:
            List of (pattern, is_negation) tuples
        """
        parsed = []

        for line in pattern_lines:
            # Strip whitespace
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue

            # Check for negation
            is_negation = line.startswith('!')
            if is_negation:
                line = line[1:].strip()

            # Store pattern and negation flag
            if line:  # Only add non-empty patterns
                parsed.append((line, is_negation))

        return parsed

    def ShouldIgnore(self, file_path: str) -> bool:
        """
        Check if a file path should be ignored

        Args:
            file_path: Relative file path to check

        Returns:
            bool: True if file should be ignored, False otherwise
        """
        # Normalize path separators to forward slashes for consistent matching
        normalized_path = str(Path(file_path)).replace('\\', '/')

        # Track ignore state (last matching pattern wins)
        should_ignore = False

        for pattern, is_negation in self.patterns:
            if self.MatchesPattern(normalized_path, pattern):
                # If negation pattern matches, don't ignore
                # If normal pattern matches, do ignore
                should_ignore = not is_negation

        return should_ignore

    def MatchesPattern(self, file_path: str, pattern: str) -> bool:
        """
        Check if a file path matches a specific pattern

        Args:
            file_path: Normalized file path (with forward slashes)
            pattern: Pattern to match against

        Returns:
            bool: True if path matches pattern
        """
        # Normalize pattern separators
        pattern = pattern.replace('\\', '/')

        # Handle directory-only patterns (ending with /)
        is_dir_pattern = pattern.endswith('/')
        if is_dir_pattern:
            pattern = pattern.rstrip('/')

        # If pattern contains /, it must match from root or contain the path structure
        if '/' in pattern:
            # Pattern with path separator - match full path
            if fnmatch.fnmatch(file_path, pattern):
                return True
            # Also try matching if file_path starts with the pattern
            if fnmatch.fnmatch(file_path, f"{pattern}/*"):
                return True
        else:
            # Pattern without path separator - match filename in any directory
            # Split path and check if any component matches
            path_parts = file_path.split('/')
            for part in path_parts:
                if fnmatch.fnmatch(part, pattern):
                    return True

            # Also check full path match
            if fnmatch.fnmatch(file_path, pattern):
                return True

        return False

    def FilterPaths(self, paths: List[str]) -> List[str]:
        """
        Filter a list of paths, removing ignored ones

        Args:
            paths: List of file paths to filter

        Returns:
            List of paths that should NOT be ignored
        """
        return [p for p in paths if not self.ShouldIgnore(p)]


def LoadPatternsFromFile(file_path: str) -> List[str]:
    """
    Load ignore patterns from a file

    Args:
        file_path: Path to .aldersyncignore file

    Returns:
        List of pattern lines from file
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.readlines()
    except FileNotFoundError:
        logger.debug(f"Ignore file not found: {file_path}")
        return []
    except Exception as e:
        logger.warning(f"Error reading ignore file {file_path}: {e}")
        return []


def LoadPatternsFromDatabase(db_manager) -> List[str]:
    """
    Load ignore patterns from database

    Args:
        db_manager: DatabaseManager instance

    Returns:
        List of pattern strings from database
    """
    session = db_manager.GetSession()
    try:
        from models.database import IgnorePattern
        patterns = session.query(IgnorePattern).all()
        return [p.pattern for p in patterns]
    except Exception as e:
        logger.warning(f"Error loading ignore patterns from database: {e}")
        return []
    finally:
        session.close()
