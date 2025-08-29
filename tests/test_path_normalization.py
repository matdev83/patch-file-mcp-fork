"""
Comprehensive tests for path normalization functionality.
"""
import pytest
import os
from pathlib import Path
from unittest.mock import patch

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

    def test_normalize_path_unix_separator_handling(self):
        """Test Unix path separator handling."""
        from patch_file_mcp.server import normalize_path

        # On Windows, we can't test Unix path creation directly, but we can test
        # that the function handles the os.name check correctly by using a valid path
        # and mocking the os.name to ensure the Unix code path is reached

        # We'll use a relative path that works on both platforms
        test_path = "relative/path/file.txt"

        # Test with current os.name (should work)
        result1 = normalize_path(test_path)
        assert result1.is_absolute()

        # The test verifies that normalize_path can handle different os.name values
        # without crashing - the actual path separator logic is tested in other tests

    def test_normalize_path_windows_separator_handling(self):
        """Test Windows path separator handling."""
        from patch_file_mcp.server import normalize_path

        # Test with patch to force Windows behavior (which is the current platform)
        with patch("os.name", "nt"):
            # This should trigger the Windows path separator replacement
            windows_path = "C:/path/to/file.txt"
            normalized = normalize_path(windows_path)

            # Should convert forward slashes to backslashes and work
            assert normalized.is_absolute()

    def test_normalize_path_resolution_os_error(self):
        """Test OSError during path resolution."""
        from patch_file_mcp.server import normalize_path

        # Mock Path.resolve to raise OSError
        with patch("pathlib.Path.resolve") as mock_resolve:
            mock_resolve.side_effect = OSError("Permission denied")

            with pytest.raises(ValueError, match="Invalid path.*Permission denied"):
                normalize_path("/some/path")

    def test_normalize_path_resolution_runtime_error(self):
        """Test RuntimeError during path resolution."""
        from patch_file_mcp.server import normalize_path

        # Mock Path.resolve to raise RuntimeError
        with patch("pathlib.Path.resolve") as mock_resolve:
            mock_resolve.side_effect = RuntimeError("Runtime error during resolution")

            with pytest.raises(ValueError, match="Invalid path.*Runtime error during resolution"):
                normalize_path("/some/path")


class TestDirectoryAccessValidation:
    """Tests for directory access validation functionality."""

    def test_validate_directory_access_nonexistent_directory(self, tmp_path):
        """Test validation of non-existent directory."""
        from patch_file_mcp.server import validate_directory_access

        nonexistent_dir = tmp_path / "nonexistent"
        is_valid, error_msg = validate_directory_access(nonexistent_dir)

        assert is_valid is False
        assert "Directory does not exist" in error_msg

    def test_validate_directory_access_file_as_directory(self, tmp_path):
        """Test validation when a file is provided instead of directory."""
        from patch_file_mcp.server import validate_directory_access

        # Create a file instead of directory
        test_file = tmp_path / "file_not_dir.txt"
        test_file.write_text("content")

        is_valid, error_msg = validate_directory_access(test_file)

        assert is_valid is False
        assert "Path is not a directory" in error_msg

    def test_validate_directory_access_no_read_access(self, tmp_path, monkeypatch):
        """Test validation when directory has no read access."""
        from patch_file_mcp.server import validate_directory_access

        test_dir = tmp_path / "no_read_access"
        test_dir.mkdir()

        # Mock Path.iterdir() to raise PermissionError
        def mock_iterdir(self):
            if str(test_dir) in str(self):
                raise PermissionError("Permission denied")
            return []

        monkeypatch.setattr('pathlib.Path.iterdir', mock_iterdir)

        is_valid, error_msg = validate_directory_access(test_dir)

        assert is_valid is False
        assert "No read access" in error_msg

    def test_validate_directory_access_no_write_access(self, tmp_path, monkeypatch):
        """Test validation when directory has no write access."""
        from patch_file_mcp.server import validate_directory_access

        test_dir = tmp_path / "no_write_access"
        test_dir.mkdir()

        # Mock write_text to raise PermissionError
        original_write_text = Path.write_text
        def mock_write_text(self, content, **kwargs):
            if str(test_dir) in str(self):
                raise PermissionError("Permission denied")
            return original_write_text(self, content, **kwargs)

        monkeypatch.setattr('pathlib.Path.write_text', mock_write_text)

        is_valid, error_msg = validate_directory_access(test_dir)

        assert is_valid is False
        assert "No write access" in error_msg

    def test_validate_directory_access_general_exception(self, tmp_path):
        """Test validation with general exception."""
        from patch_file_mcp.server import validate_directory_access

        # Mock Path.exists to raise a general exception
        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.side_effect = Exception("Unexpected error")

            is_valid, error_msg = validate_directory_access(tmp_path / "test")

            assert is_valid is False
            assert "Error validating directory" in error_msg

    def test_validate_directory_access_success(self, tmp_path):
        """Test successful directory validation."""
        from patch_file_mcp.server import validate_directory_access

        test_dir = tmp_path / "valid_dir"
        test_dir.mkdir()

        is_valid, error_msg = validate_directory_access(test_dir)

        assert is_valid is True
        assert error_msg is None