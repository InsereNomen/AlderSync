"""
AlderSync Client - Ignore Pattern Matching

This module provides gitignore-style pattern matching functionality for the Client.
Reads .aldersyncignore files and applies patterns to filter files during sync operations.
"""

import logging
from pathlib import Path
from typing import List, Tuple, Set, Dict
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


class IgnorePatternManager:
    """
    Manages loading and merging ignore patterns from multiple sources:
    1. .aldersyncignore next to the executable (applies to all operations)
    2. .aldersyncignore files in directories (applies to that directory and subdirectories)
    """

    def __init__(self, executable_dir: Path, propresenter_root: Path):
        """
        Initialize ignore pattern manager

        Args:
            executable_dir: Directory containing the AlderSync executable
            propresenter_root: Root ProPresenter directory to scan for .aldersyncignore files
        """
        self.executable_dir = executable_dir
        self.propresenter_root = propresenter_root
        self.global_patterns: List[str] = []
        self.directory_patterns: Dict[Path, List[str]] = {}

    def LoadPatterns(self):
        """
        Load all ignore patterns from files
        """
        # Load global patterns from executable directory
        self.global_patterns = self.LoadPatternsFromFile(
            self.executable_dir / ".aldersyncignore"
        )

        # Scan for .aldersyncignore files in ProPresenter directory tree
        self.directory_patterns = {}
        if self.propresenter_root.exists():
            for ignore_file in self.propresenter_root.rglob(".aldersyncignore"):
                patterns = self.LoadPatternsFromFile(ignore_file)
                if patterns:
                    self.directory_patterns[ignore_file.parent] = patterns

    def LoadPatternsFromFile(self, file_path: Path) -> List[str]:
        """
        Load ignore patterns from a file

        Args:
            file_path: Path to .aldersyncignore file

        Returns:
            List of pattern lines from file
        """
        if not file_path.exists():
            logger.debug(f"Ignore file not found: {file_path}")
            return []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                patterns = f.readlines()
                logger.info(f"Loaded {len(patterns)} patterns from {file_path}")
                return patterns
        except Exception as e:
            logger.warning(f"Error reading ignore file {file_path}: {e}")
            return []

    def ShouldIgnore(self, file_path: Path) -> bool:
        """
        Check if a file should be ignored based on all applicable patterns

        Args:
            file_path: Absolute path to file

        Returns:
            bool: True if file should be ignored
        """
        # Convert to relative path from ProPresenter root
        try:
            relative_path = file_path.relative_to(self.propresenter_root)
        except ValueError:
            # File is not under ProPresenter root
            logger.debug(f"File not under ProPresenter root: {file_path}")
            return False

        # Check global patterns first
        if self.global_patterns:
            matcher = PatternMatcher(self.global_patterns)
            if matcher.ShouldIgnore(str(relative_path)):
                logger.debug(f"File ignored by global pattern: {relative_path}")
                return True

        # Check directory-specific patterns
        # Walk up the directory tree from the file's location
        current_dir = file_path.parent
        while current_dir >= self.propresenter_root:
            if current_dir in self.directory_patterns:
                # Calculate relative path from this directory
                try:
                    rel_from_dir = file_path.relative_to(current_dir)
                    matcher = PatternMatcher(self.directory_patterns[current_dir])
                    if matcher.ShouldIgnore(str(rel_from_dir)):
                        logger.debug(f"File ignored by pattern in {current_dir}: {relative_path}")
                        return True
                except ValueError:
                    pass

            # Move up to parent directory
            if current_dir == self.propresenter_root:
                break
            current_dir = current_dir.parent

        return False

    def FilterFiles(self, file_paths: List[Path]) -> List[Path]:
        """
        Filter a list of file paths, removing ignored ones

        Args:
            file_paths: List of file paths to filter

        Returns:
            List of paths that should NOT be ignored
        """
        return [p for p in file_paths if not self.ShouldIgnore(p)]
