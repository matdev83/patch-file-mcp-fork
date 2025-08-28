"""
Comprehensive tests for path normalization functionality.
"""
import pytest
import os
from pathlib import Path

# Import the function we want to test
from patch_file_mcp.server import normalize_path


class TestPathNormalization:
    """Comprehensive tests for path normalization functionality."""

    def test_normalize_path_forward_slashes(self, tmp_path):
        """Test path with forward slashes."""
        test_file = tmp_path / "subdir" / "test.txt"
        test_file.parent.mkdir(exist_ok=True)
        test_file.write_text("content")

        unix_path = str(test_file).replace('\\', '/')
        normalized = normalize_path(unix_path)
        assert normalized == test_file.resolve()

    def test_normalize_path_windows_backslashes(self, tmp_path):
        """Test path with Windows backslashes."""
        test_file = tmp_path / "subdir" / "test.txt"
        test_file.parent.mkdir(exist_ok=True)
        test_file.write_text("content")

        windows_path = str(test_file).replace('/', '\\')
        normalized = normalize_path(windows_path)
        assert normalized == test_file.resolve()

    def test_normalize_path_escaped_backslashes(self, tmp_path):
        """Test path with escaped backslashes (command line style)."""
        test_file = tmp_path / "subdir" / "test.txt"
        test_file.parent.mkdir(exist_ok=True)
        test_file.write_text("content")

        # Simulate command line escaped path
        escaped_path = str(test_file).replace('/', '\\\\')
        normalized = normalize_path(escaped_path)
        assert normalized == test_file.resolve()

    def test_normalize_path_mixed_separators(self, tmp_path):
        """Test path with mixed separators."""
        test_file = tmp_path / "level1" / "level2" / "test.txt"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("content")

        # Create mixed separator path
        mixed_path = str(test_file).replace('level1', 'level1\\').replace('level2', 'level2/')
        normalized = normalize_path(mixed_path)
        assert normalized == test_file.resolve()

    def test_normalize_path_double_backslashes(self, tmp_path):
        """Test path with double backslashes."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        double_slash_path = str(test_file).replace('/', '\\\\')
        normalized = normalize_path(double_slash_path)
        assert normalized == test_file.resolve()

    def test_normalize_path_empty_string(self):
        """Test that empty path raises error."""
        with pytest.raises(ValueError, match="Empty path provided"):
            normalize_path("")

    def test_normalize_path_relative_path(self, tmp_path, monkeypatch):
        """Test path normalization with relative paths."""
        # Change to tmp_path directory
        monkeypatch.chdir(tmp_path)

        # Create a relative path
        rel_file = Path("subdir") / "test.txt"
        rel_file.parent.mkdir(exist_ok=True)
        rel_file.write_text("content")

        # Normalize relative path
        normalized = normalize_path("subdir/test.txt")

        # Should resolve to absolute path
        expected = (tmp_path / "subdir" / "test.txt").resolve()
        assert normalized == expected

    def test_normalize_path_cross_platform_consistency(self, tmp_path):
        """Test that path normalization is consistent across different input formats."""
        test_file = tmp_path / "consistent" / "test.txt"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("content")

        # Test different input formats that should all resolve to the same path
        formats_to_test = [
            str(test_file),  # Native format
            str(test_file).replace('/', '\\'),  # Windows style
            str(test_file).replace('/', '\\\\'),  # Escaped Windows
            str(test_file).replace('\\', '/'),  # Unix style
        ]

        # All should resolve to the same absolute path
        expected_path = test_file.resolve()
        for path_format in formats_to_test:
            normalized = normalize_path(path_format)
            assert normalized == expected_path, f"Failed for format: {path_format}"

    def test_normalize_path_special_characters(self, tmp_path):
        """Test path normalization with special characters and spaces."""
        # Create a directory with spaces and special characters
        special_dir = tmp_path / "special dir" / "test-file_123"
        special_dir.mkdir(parents=True, exist_ok=True)
        test_file = special_dir / "file with spaces.txt"
        test_file.write_text("content")

        # Test with different separator formats
        path_with_spaces = str(test_file)
        windows_format = path_with_spaces.replace('/', '\\')
        escaped_format = path_with_spaces.replace('/', '\\\\')

        # All should work
        normalized1 = normalize_path(path_with_spaces)
        normalized2 = normalize_path(windows_format)
        normalized3 = normalize_path(escaped_format)

        expected = test_file.resolve()
        assert normalized1 == expected
        assert normalized2 == expected
        assert normalized3 == expected
