"""
Tests for the main patch_file function.
"""

import pytest
from unittest.mock import patch
from datetime import datetime, timedelta

# Import the function we want to test
from patch_file_mcp.server import (
    patch_file,
    is_binary_file_extension,
    track_failed_edit,
    clear_failed_edit_history,
    get_failed_edit_info,
    FAILED_EDITS_HISTORY,
    create_patch_params_hash,
    garbage_collect_failed_edit_history,
    TOOL_CALL_COUNTER,
    should_suppress_mypy_info,
    update_mypy_failure_count,
    MYPY_FAILURE_COUNTS,
)


class TestPatchFile:
    """Test cases for the patch_file function."""

    def test_patch_file_successful_python_file(self, tmp_path, mock_subprocess_run):
        """Test successful patching of a Python file."""
        # Setup
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    print('Hello')\n")

        # Mock the allowed directories and virtual environment
        with (
            patch("patch_file_mcp.server.allowed_directories", [str(tmp_path)]),
            patch(
                "patch_file_mcp.server.find_venv_directory",
                return_value="/fake/venv/bin/python",
            ),
        ):
            # Create patch content
            patch_content = """<<<<<<< SEARCH
def hello():
    print('Hello')
=======
def hello():
    print('Hello, World!')
>>>>>>> REPLACE"""

            # Mock successful QA pipeline
            with patch("patch_file_mcp.server.run_python_qa_pipeline") as mock_qa:
                mock_qa.return_value = {
                    "qa_performed": True,
                    "iterations_used": 1,
                    "ruff_status": "passed",
                    "black_status": "passed",
                    "mypy_status": "passed",
                    "errors": [],
                    "warnings": [],
                }

                # Execute
                result = patch_file(str(test_file), patch_content)

                # Verify
                assert "Successfully applied 1 patch blocks" in result
                assert "QA Results:" in result
                assert "Ruff: ✅" in result
                assert "Black: ✅" in result
                assert "MyPy: ✅" in result

                # Verify file was actually modified
                content = test_file.read_text()
                assert "Hello, World!" in content

    def test_patch_file_successful_non_python_file(self, tmp_path):
        """Test successful patching of a non-Python file (no QA)."""
        # Setup
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello World")

        # Mock the allowed directories
        with patch("patch_file_mcp.server.allowed_directories", [str(tmp_path)]):
            # Create patch content
            patch_content = """<<<<<<< SEARCH
Hello World
=======
Hello, Universe!
>>>>>>> REPLACE"""

            # Execute
            result = patch_file(str(test_file), patch_content)

            # Verify
            assert "Successfully applied 1 patch blocks" in result
            assert "QA" not in result  # Should not contain QA information

            # Verify file was actually modified
            content = test_file.read_text()
            assert "Hello, Universe!" in content

    def test_patch_file_no_venv_found(self, tmp_path):
        """Test patching Python file when no venv is found."""
        # Setup
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    print('Hello')\n")

        # Mock the allowed directories
        with patch("patch_file_mcp.server.allowed_directories", [str(tmp_path)]):
            # Mock find_venv_directory to return None
            with patch("patch_file_mcp.server.find_venv_directory", return_value=None):
                # Create patch content
                patch_content = """<<<<<<< SEARCH
def hello():
    print('Hello')
=======
def hello():
    print('Hello, World!')
>>>>>>> REPLACE"""

                # Execute
                result = patch_file(str(test_file), patch_content)

                # Verify
                assert "Successfully applied 1 patch blocks" in result
                assert "QA Results:" in result
                assert "No virtual environment" in result
                assert "Please run QA checks manually" in result

    def test_patch_file_qa_errors(self, tmp_path):
        """Test patching Python file when QA has errors."""
        # Setup
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    print('Hello')\n")

        # Mock the allowed directories and virtual environment
        with (
            patch("patch_file_mcp.server.allowed_directories", [str(tmp_path)]),
            patch(
                "patch_file_mcp.server.find_venv_directory",
                return_value="/fake/venv/bin/python",
            ),
        ):
            # Create patch content
            patch_content = """<<<<<<< SEARCH
def hello():
    print('Hello')
=======
def hello():
    print('Hello, World!')
>>>>>>> REPLACE"""

            # Mock QA pipeline with errors
            with patch("patch_file_mcp.server.run_python_qa_pipeline") as mock_qa:
                mock_qa.return_value = {
                    "qa_performed": True,
                    "iterations_used": 1,
                    "ruff_status": "failed",
                    "black_status": None,
                    "mypy_status": None,
                    "ruff_stdout": "",
                    "ruff_stderr": "Ruff found unfixable errors: syntax error",
                    "black_stdout": "",
                    "black_stderr": "",
                    "mypy_stdout": "",
                    "mypy_stderr": "",
                    "errors": [],
                    "warnings": [],
                }

                # Execute
                result = patch_file(str(test_file), patch_content)

                # Verify
                assert "Successfully applied 1 patch blocks" in result
                assert "QA Results:" in result
                assert "Ruff: ❌" in result
                assert "Error Details:" in result
                assert "Ruff (failed):" in result
                assert "Ruff found unfixable errors: syntax error" in result
                assert (
                    "Please fix the issues and run the following commands manually"
                    in result
                )

    def test_patch_file_file_not_found(self, tmp_path):
        """Test patching non-existent file."""
        # Setup
        non_existent_file = tmp_path / "nonexistent.py"

        # Mock the allowed directories
        with patch("patch_file_mcp.server.allowed_directories", [str(tmp_path)]):
            patch_content = """<<<<<<< SEARCH
test
=======
modified
>>>>>>> REPLACE"""

            # Execute and expect exception
            with pytest.raises(FileNotFoundError, match="File .* does not exist"):
                patch_file(str(non_existent_file), patch_content)

    def test_patch_file_not_in_allowed_directory(self, tmp_path):
        """Test patching file not in allowed directories."""
        # Setup
        test_file = tmp_path / "test.py"
        test_file.write_text("test content")

        # Mock the allowed directories to not include tmp_path
        with patch("patch_file_mcp.server.allowed_directories", ["/some/other/path"]):
            patch_content = """<<<<<<< SEARCH
test content
=======
modified content
>>>>>>> REPLACE"""

            # Execute and expect exception
            with pytest.raises(
                PermissionError, match="File .* is not in.*allowed directories"
            ):
                patch_file(str(test_file), patch_content)

    def test_patch_file_invalid_patch_format(self, tmp_path):
        """Test patching with invalid patch format."""
        # Setup
        test_file = tmp_path / "test.py"
        test_file.write_text("test content")

        # Mock the allowed directories
        with patch("patch_file_mcp.server.allowed_directories", [str(tmp_path)]):
            # Invalid patch content (missing markers)
            patch_content = "invalid patch content"

            # Execute and expect exception
            with pytest.raises(RuntimeError, match="Failed to apply patch"):
                patch_file(str(test_file), patch_content)

    def test_patch_file_multiple_blocks(self, tmp_path):
        """Test patching with multiple search-replace blocks."""
        # Setup
        test_file = tmp_path / "test.py"
        test_file.write_text(
            "def func1():\n    return 1\n\ndef func2():\n    return 2\n"
        )

        # Mock the allowed directories
        with patch("patch_file_mcp.server.allowed_directories", [str(tmp_path)]):
            # Create patch content with multiple blocks
            patch_content = """<<<<<<< SEARCH
def func1():
    return 1
=======
def func1():
    return "one"
>>>>>>> REPLACE
<<<<<<< SEARCH
def func2():
    return 2
=======
def func2():
    return "two"
>>>>>>> REPLACE"""

            # Execute
            result = patch_file(str(test_file), patch_content)

            # Verify
            assert "Successfully applied 2 patch blocks" in result

            # Verify file was actually modified
            content = test_file.read_text()
            assert 'return "one"' in content
            assert 'return "two"' in content

    def test_patch_file_no_matching_content(self, tmp_path):
        """Test patching when search text is not found."""
        # Setup
        test_file = tmp_path / "test.py"
        test_file.write_text("def existing():\n    return True\n")

        # Mock the allowed directories
        with patch("patch_file_mcp.server.allowed_directories", [str(tmp_path)]):
            # Create patch content with non-matching search text
            patch_content = """<<<<<<< SEARCH
def nonexistent():
    return False
=======
def nonexistent():
    return True
>>>>>>> REPLACE"""

            # Execute and expect exception
            with pytest.raises(RuntimeError, match="Failed to apply patch"):
                patch_file(str(test_file), patch_content)

    def test_patch_file_fuzzy_matching_hint(self, tmp_path):
        """Test patch_file generates fuzzy matching hints for whitespace differences."""
        # Setup
        test_file = tmp_path / "test.py"
        test_file.write_text(
            "def hello():\n    print('Hello, World!')\n    return True\n"
        )

        with patch("patch_file_mcp.server.allowed_directories", [str(tmp_path)]):
            # Create patch content with different indentation (2 spaces instead of 4)
            patch_content = """<<<<<<< SEARCH
def hello():
  print('Hello, World!')
  return True
=======
def hello():
    print('Hello, Universe!')
    return True
>>>>>>> REPLACE"""

            # Test that it raises RuntimeError with fuzzy hint
            with pytest.raises(RuntimeError) as exc_info:
                patch_file(str(test_file), patch_content)

            error_message = str(exc_info.value)

            # Verify the error contains the fuzzy matching hint
            assert "Could not find the search text" in error_message
            assert (
                "Hint: Found similar content with whitespace/formatting differences"
                in error_message
            )
            assert "1:" in error_message  # Should include line numbers
            assert (
                "print('Hello, World!')" in error_message
            )  # Should show the actual content
            assert "<-- likely match" in error_message  # Should mark the matching lines

    def test_patch_file_fuzzy_matching_no_hint_for_nonexistent(self, tmp_path):
        """Test patch_file does not generate fuzzy hints for completely non-existent code."""
        # Setup
        test_file = tmp_path / "test.py"
        test_file.write_text(
            "def hello():\n    print('Hello, World!')\n    return True\n"
        )

        with patch("patch_file_mcp.server.allowed_directories", [str(tmp_path)]):
            # Create patch content for completely non-existent function
            patch_content = """<<<<<<< SEARCH
def nonexistent_function():
    pass
=======
def nonexistent_function():
    return None
>>>>>>> REPLACE"""

            # Test that it raises RuntimeError without fuzzy hint
            with pytest.raises(RuntimeError) as exc_info:
                patch_file(str(test_file), patch_content)

            error_message = str(exc_info.value)

            # Verify the error does NOT contain a fuzzy matching hint
            assert "Could not find the search text" in error_message
            assert (
                "Hint: Found similar content with whitespace/formatting differences"
                not in error_message
            )

    def test_patch_file_fuzzy_matching_safeguards(self, tmp_path):
        """Test that fuzzy matching safeguards prevent hints for inappropriate search strings."""
        # Setup
        test_file = tmp_path / "test.py"
        test_file.write_text(
            "def hello():\n    print('Hello, World!')\n    return True\n"
        )

        with patch("patch_file_mcp.server.allowed_directories", [str(tmp_path)]):
            # Test 1: Too short search text (< 20 chars) - should not generate hint
            patch_content_short = """<<<<<<< SEARCH
def hi():
  x = 1
=======
def hi():
    x = 1
>>>>>>> REPLACE"""

            with pytest.raises(RuntimeError) as exc_info:
                patch_file(str(test_file), patch_content_short)

            error_message = str(exc_info.value)
            assert "Could not find the search text" in error_message
            assert (
                "Hint: Found similar content with whitespace/formatting differences"
                not in error_message
            )

            # Test 2: Single line search text (< 2 lines) - should not generate hint
            patch_content_single_line = """<<<<<<< SEARCH
def hello_world():
=======
def hello_universe():
>>>>>>> REPLACE"""

            with pytest.raises(RuntimeError) as exc_info:
                patch_file(str(test_file), patch_content_single_line)

            error_message = str(exc_info.value)
            assert "Could not find the search text" in error_message
            assert (
                "Hint: Found similar content with whitespace/formatting differences"
                not in error_message
            )

            # Test 3: Valid multi-line search text (should generate hint if similar match found)
            patch_content_valid = """<<<<<<< SEARCH
def hello():
  print('Hello, World!')
  return True
=======
def hello():
    print('Hello, Universe!')
    return True
>>>>>>> REPLACE"""

            with pytest.raises(RuntimeError) as exc_info:
                patch_file(str(test_file), patch_content_valid)

            error_message = str(exc_info.value)
            assert "Could not find the search text" in error_message
            assert (
                "Hint: Found similar content with whitespace/formatting differences"
                in error_message
            )

    def test_patch_file_ambiguous_match(self, tmp_path):
        """Test patching when search text appears multiple times."""
        # Setup
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')\nprint('hello')\nprint('world')\n")

        # Mock the allowed directories
        with patch("patch_file_mcp.server.allowed_directories", [str(tmp_path)]):
            # Create patch content with ambiguous search text
            patch_content = """<<<<<<< SEARCH
print('hello')
=======
print('hi')
>>>>>>> REPLACE"""

            # Execute and expect exception
            with pytest.raises(RuntimeError, match="Failed to apply patch"):
                patch_file(str(test_file), patch_content)


class TestBinaryFileSecurity:
    """Test cases for binary file extension security checks."""

    def test_is_binary_file_extension_blocks_exe(self):
        """Test that .exe files are correctly identified as binary."""
        assert is_binary_file_extension("/path/to/file.exe") == (True, ".exe")
        assert is_binary_file_extension("C:\\path\\to\\file.EXE") == (
            True,
            ".exe",
        )  # Case insensitive

    def test_is_binary_file_extension_blocks_dll(self):
        """Test that .dll files are correctly identified as binary."""
        assert is_binary_file_extension("/path/to/file.dll") == (True, ".dll")

    def test_is_binary_file_extension_blocks_so(self):
        """Test that .so files are correctly identified as binary."""
        assert is_binary_file_extension("/path/to/file.so") == (True, ".so")

    def test_is_binary_file_extension_blocks_documents(self):
        """Test that document files are correctly identified as binary."""
        binary_docs = [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"]

        for ext in binary_docs:
            file_path = f"/path/to/file{ext}"
            assert is_binary_file_extension(file_path) == (True, ext)

    def test_is_binary_file_extension_blocks_media(self):
        """Test that media files are correctly identified as binary."""
        binary_media = [".mp3", ".mp4", ".avi", ".jpg", ".png", ".gif"]

        for ext in binary_media:
            file_path = f"/path/to/file{ext}"
            assert is_binary_file_extension(file_path) == (True, ext)

    def test_is_binary_file_extension_blocks_archives(self):
        """Test that archive files are correctly identified as binary."""
        binary_archives = [".zip", ".rar", ".7z", ".tar", ".gz"]

        for ext in binary_archives:
            file_path = f"/path/to/file{ext}"
            assert is_binary_file_extension(file_path) == (True, ext)

    def test_is_binary_file_extension_allows_text_files(self):
        """Test that text files are correctly identified as non-binary."""
        text_files = [
            "/path/to/file.txt",
            "/path/to/file.py",
            "/path/to/file.js",
            "/path/to/file.html",
            "/path/to/file.css",
            "/path/to/file.json",
            "/path/to/file.xml",
            "/path/to/file.md",
            "/path/to/file.yml",
            "/path/to/file.yaml",
            "/path/to/file.toml",
            "/path/to/file.ini",
            "/path/to/file.cfg",
            "/path/to/file.log",
            "/path/to/file.sh",
            "/path/to/file.bat",
            "/path/to/file.ps1",
        ]

        for file_path in text_files:
            assert is_binary_file_extension(file_path) == (False, None)

    def test_is_binary_file_extension_allows_files_without_extension(self):
        """Test that files without extensions are allowed (treated as text)."""
        assert is_binary_file_extension("/path/to/file") == (False, None)
        assert is_binary_file_extension("/path/to/file.") == (False, None)

    def test_is_binary_file_extension_handles_malformed_paths(self):
        """Test that malformed paths are handled safely."""
        # Should return True (binary) for safety when path parsing fails
        assert is_binary_file_extension("") == (True, None)
        assert is_binary_file_extension(None) == (True, None)

    def test_patch_file_rejects_binary_files(self, tmp_path):
        """Test that patch_file rejects attempts to edit binary files."""
        # Create a mock binary file
        binary_file = tmp_path / "test.exe"
        binary_file.write_bytes(b"fake binary content")

        # Mock the allowed directories
        with patch("patch_file_mcp.server.allowed_directories", [str(tmp_path)]):
            patch_content = """<<<<<<< SEARCH
fake binary content
=======
modified content
>>>>>>> REPLACE"""

            # Execute and expect ValueError for binary file rejection
            with pytest.raises(
                ValueError,
                match="Rejected: patch_file tool should only be used to edit text files",
            ):
                patch_file(str(binary_file), patch_content)

    def test_patch_file_rejects_various_binary_extensions(self, tmp_path):
        """Test that patch_file rejects various binary file types."""
        binary_extensions = [".exe", ".dll", ".pdf", ".docx", ".mp4", ".zip"]

        for ext in binary_extensions:
            # Create a mock binary file
            binary_file = tmp_path / f"test{ext}"
            binary_file.write_bytes(b"fake binary content")

            # Mock the allowed directories
            with patch("patch_file_mcp.server.allowed_directories", [str(tmp_path)]):
                patch_content = """<<<<<<< SEARCH
fake binary content
=======
modified content
>>>>>>> REPLACE"""

                # Execute and expect ValueError for binary file rejection
                with pytest.raises(
                    ValueError,
                    match="Rejected: patch_file tool should only be used to edit text files",
                ):
                    patch_file(str(binary_file), patch_content)

    def test_patch_file_allows_text_files_after_binary_check(self, tmp_path):
        """Test that text files still work after adding binary file security check."""
        # Create a text file
        text_file = tmp_path / "test.txt"
        text_file.write_text("Hello World")

        # Mock the allowed directories
        with patch("patch_file_mcp.server.allowed_directories", [str(tmp_path)]):
            patch_content = """<<<<<<< SEARCH
Hello World
=======
Hello Universe
>>>>>>> REPLACE"""

            # Execute - should work fine
            result = patch_file(str(text_file), patch_content)

            # Verify
            assert "Successfully applied 1 patch blocks" in result
            assert "Hello Universe" in text_file.read_text()

    def test_is_binary_file_extension_exception_handling(self):
        """Test exception handling in is_binary_file_extension."""
        # Mock Path to raise an exception
        with patch("pathlib.Path") as mock_path:
            mock_path.side_effect = Exception("Unexpected error")

            result = is_binary_file_extension("/some/path/file.txt")

            # Should return (True, None) for safety when exception occurs
            assert result == (True, None)

    def test_is_binary_file_extension_with_none_input(self):
        """Test is_binary_file_extension with None input."""
        result = is_binary_file_extension(None)

        # Should return (True, None) for safety with None input
        assert result == (True, None)


class TestPatchFileErrorConditions:
    """Test cases for various error conditions in patch_file function."""

    def test_patch_file_path_validation_error(self, tmp_path):
        """Test patch_file with path validation error."""
        # Test with a file that's not in allowed directories
        with patch("patch_file_mcp.server.allowed_directories", [str(tmp_path)]):
            patch_content = """<<<<<<< SEARCH
test
=======
modified
>>>>>>> REPLACE"""

            # On Windows, /invalid/path is not considered absolute, so it raises ValueError
            # On Unix-like systems, it would be considered absolute and raise PermissionError
            with pytest.raises((PermissionError, ValueError)):
                patch_file("/invalid/path", patch_content)

    def test_patch_file_file_reading_error(self, tmp_path):
        """Test patch_file with file reading error."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        # Mock open to raise IOError during reading
        with patch("builtins.open", side_effect=IOError("Read permission denied")):
            with patch("patch_file_mcp.server.allowed_directories", [str(tmp_path)]):
                patch_content = """<<<<<<< SEARCH
content
=======
modified
>>>>>>> REPLACE"""

                with pytest.raises(IOError, match="Read permission denied"):
                    patch_file(str(test_file), patch_content)

    def test_patch_file_file_writing_error(self, tmp_path):
        """Test patch_file with file writing error."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        # Mock open for writing to raise OSError
        original_open = open

        def mock_open_write(filename, mode, **kwargs):
            if "w" in mode:
                raise OSError("Write permission denied")
            return original_open(filename, mode, **kwargs)

        with patch("builtins.open", side_effect=mock_open_write):
            with patch("patch_file_mcp.server.allowed_directories", [str(tmp_path)]):
                patch_content = """<<<<<<< SEARCH
content
=======
modified
>>>>>>> REPLACE"""

                with pytest.raises(
                    RuntimeError, match="Failed to apply patch.*Write permission denied"
                ):
                    patch_file(str(test_file), patch_content)

    def test_patch_file_with_empty_patch_content(self, tmp_path):
        """Test patch_file with empty patch content."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        with patch("patch_file_mcp.server.allowed_directories", [str(tmp_path)]):
            with pytest.raises(RuntimeError, match="Failed to apply patch"):
                patch_file(str(test_file), "")

    def test_patch_file_with_whitespace_only_patch(self, tmp_path):
        """Test patch_file with whitespace-only patch content."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        with patch("patch_file_mcp.server.allowed_directories", [str(tmp_path)]):
            with pytest.raises(RuntimeError, match="Failed to apply patch"):
                patch_file(str(test_file), "   \n\t  ")

    def test_patch_file_with_none_patch_content(self, tmp_path):
        """Test patch_file with None patch content."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        with patch("patch_file_mcp.server.allowed_directories", [str(tmp_path)]):
            with pytest.raises(RuntimeError, match="Failed to apply patch"):
                patch_file(str(test_file), None)

    def test_patch_file_with_nonexistent_allowed_directory(self, tmp_path):
        """Test patch_file when allowed directory doesn't exist during validation."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        # Mock allowed_directories to contain a non-existent path
        nonexistent_dir = tmp_path / "nonexistent"
        with patch("patch_file_mcp.server.allowed_directories", [str(nonexistent_dir)]):
            patch_content = """<<<<<<< SEARCH
content
=======
modified
>>>>>>> REPLACE"""

            # This should fail during the is_file_in_allowed_directories check
            with pytest.raises(PermissionError):
                patch_file(str(test_file), patch_content)


class TestFailedEditTracking:
    """Test cases for failed edit tracking functionality."""

    def setup_method(self):
        """Clear failed edit history before each test."""
        FAILED_EDITS_HISTORY.clear()

    def test_create_patch_params_hash(self):
        """Test parameter hash creation."""
        file_path = "/path/to/file.py"
        patch_content = "test patch content"

        hash1 = create_patch_params_hash(file_path, patch_content)
        hash2 = create_patch_params_hash(file_path, patch_content)

        # Same parameters should produce same hash
        assert hash1 == hash2
        assert isinstance(hash1, str)
        assert len(hash1) > 0

        # Different parameters should produce different hash
        hash3 = create_patch_params_hash(file_path, "different content")
        assert hash1 != hash3

        hash4 = create_patch_params_hash("/different/path.py", patch_content)
        assert hash1 != hash4

    def test_track_failed_edit(self):
        """Test tracking failed edit attempts."""
        file_path = "/path/to/test.py"
        patch_content = """<<<<<<< SEARCH
old content
=======
new content
>>>>>>> REPLACE"""

        # Track a failed edit
        track_failed_edit(
            file_path, patch_content, "test_failure", "Test error message"
        )

        # Verify tracking
        assert file_path in FAILED_EDITS_HISTORY
        assert len(FAILED_EDITS_HISTORY[file_path]) == 1

        attempt = FAILED_EDITS_HISTORY[file_path][0]
        assert attempt["filename"] == file_path
        assert attempt["block_count"] == 1  # Should parse 1 block
        assert attempt["failure_stage"] == "test_failure"
        assert attempt["error_message"] == "Test error message"
        assert "params_hash" in attempt
        assert "datetime" in attempt

    def test_track_failed_edit_multiple_attempts(self):
        """Test tracking multiple failed attempts."""
        file_path = "/path/to/test.py"
        patch_content = """<<<<<<< SEARCH
old content
=======
new content
>>>>>>> REPLACE"""

        # Track multiple failed attempts
        track_failed_edit(file_path, patch_content, "failure1", "Error 1")
        track_failed_edit(file_path, patch_content, "failure2", "Error 2")

        assert len(FAILED_EDITS_HISTORY[file_path]) == 2

        # Verify both attempts are tracked
        assert FAILED_EDITS_HISTORY[file_path][0]["failure_stage"] == "failure1"
        assert FAILED_EDITS_HISTORY[file_path][1]["failure_stage"] == "failure2"

    def test_track_failed_edit_memory_limit(self):
        """Test that failed edit history is limited to prevent memory bloat."""
        file_path = "/path/to/test.py"
        patch_content = """<<<<<<< SEARCH
old content
=======
new content
>>>>>>> REPLACE"""

        # Track more than 10 attempts
        for i in range(12):
            track_failed_edit(file_path, patch_content, f"failure{i}", f"Error {i}")

        # Should only keep last 10 attempts
        assert len(FAILED_EDITS_HISTORY[file_path]) == 10

        # Should keep the most recent ones
        assert FAILED_EDITS_HISTORY[file_path][0]["failure_stage"] == "failure2"
        assert FAILED_EDITS_HISTORY[file_path][-1]["failure_stage"] == "failure11"

    def test_clear_failed_edit_history(self):
        """Test clearing failed edit history."""
        file_path = "/path/to/test.py"
        patch_content = """<<<<<<< SEARCH
old content
=======
new content
>>>>>>> REPLACE"""

        # Track a failed attempt
        track_failed_edit(file_path, patch_content, "test_failure", "Test error")

        # Verify it's tracked
        assert file_path in FAILED_EDITS_HISTORY

        # Clear history
        clear_failed_edit_history(file_path)

        # Verify it's cleared
        assert file_path not in FAILED_EDITS_HISTORY

    def test_get_failed_edit_info_no_history(self):
        """Test getting awareness info when no failed attempts exist."""
        file_path = "/path/to/test.py"
        patch_content = "test content"

        result = get_failed_edit_info(file_path, patch_content)
        assert result is None

    def test_get_failed_edit_info_second_attempt(self):
        """Test getting awareness info for 2nd consecutive failed attempt."""
        file_path = "/path/to/test.py"
        patch_content = """<<<<<<< SEARCH
old content
=======
new content
>>>>>>> REPLACE"""

        # Track first attempt - should not show message yet
        track_failed_edit(file_path, patch_content, "failure1", "Error1")
        result = get_failed_edit_info(file_path, patch_content)
        assert result is None  # No message for 1st attempt

        # Track second attempt - should show 2nd attempt message
        track_failed_edit(file_path, patch_content, "failure2", "Error2")
        result = get_failed_edit_info(file_path, patch_content)
        assert result is not None
        assert "2nd consecutive failed edit attempt" in result
        assert "consider splitting this edit" not in result  # Not 3+ yet

    def test_get_failed_edit_info_third_attempt_multiple_blocks(self):
        """Test getting awareness info for 3+ attempts with multiple blocks."""
        file_path = "/path/to/test.py"
        patch_content = """<<<<<<< SEARCH
old content
=======
new content
>>>>>>> REPLACE
<<<<<<< SEARCH
more old content
=======
more new content
>>>>>>> REPLACE"""

        # Track two attempts first - should not show splitting message yet
        for i in range(2):
            track_failed_edit(file_path, patch_content, f"failure{i}", f"Error {i}")

        result = get_failed_edit_info(file_path, patch_content)
        assert result is not None
        assert "2nd consecutive failed edit attempt" in result
        assert "consider splitting this edit" not in result  # Not 3+ yet

        # Track third attempt - should now show splitting message
        track_failed_edit(file_path, patch_content, "failure2", "Error 2")

        result = get_failed_edit_info(file_path, patch_content)
        assert result is not None
        assert "3rd consecutive failed edit attempt" in result
        assert "consider splitting this edit" in result

    def test_get_failed_edit_info_third_attempt_single_block(self):
        """Test getting awareness info for 3+ attempts with single block."""
        file_path = "/path/to/test.py"
        patch_content = """<<<<<<< SEARCH
old content
=======
new content
>>>>>>> REPLACE"""

        # Track two attempts first
        for i in range(2):
            track_failed_edit(file_path, patch_content, f"failure{i}", f"Error {i}")

        result = get_failed_edit_info(file_path, patch_content)
        assert result is not None
        assert "2nd consecutive failed edit attempt" in result

        # Track third attempt - should show message but not mention splitting (only single block)
        track_failed_edit(file_path, patch_content, "failure2", "Error 2")

        result = get_failed_edit_info(file_path, patch_content)
        assert result is not None
        assert "3rd consecutive failed edit attempt" in result
        assert "consider splitting this edit" not in result  # Single block

    def test_get_failed_edit_info_different_parameters(self):
        """Test that awareness messages show regardless of parameter differences."""
        file_path = "/path/to/test.py"

        # Track attempt with one set of parameters
        patch_content1 = """<<<<<<< SEARCH
content1
=======
new1
>>>>>>> REPLACE"""
        track_failed_edit(file_path, patch_content1, "failure", "Error")

        # Check with different parameters - should still show message after 1+ attempts
        patch_content2 = """<<<<<<< SEARCH
content2
=======
new2
>>>>>>> REPLACE"""
        result = get_failed_edit_info(file_path, patch_content2)
        assert result is None  # Still None for 1st attempt, need 2+ attempts

        # Track second attempt with different parameters
        track_failed_edit(file_path, patch_content2, "failure2", "Error2")

        # Now should show message for 2nd attempt
        result = get_failed_edit_info(file_path, patch_content2)
        assert result is not None
        assert "2nd consecutive failed edit attempt" in result

    def test_patch_file_integration_failed_tracking(self, tmp_path):
        """Test end-to-end integration of failed edit tracking in patch_file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        # Mock allowed directories
        with patch("patch_file_mcp.server.allowed_directories", [str(tmp_path)]):
            # Try to patch with non-matching content (should fail)
            patch_content = """<<<<<<< SEARCH
nonexistent content
=======
modified content
>>>>>>> REPLACE"""

            # This should fail and track the attempt
            with pytest.raises(RuntimeError):
                patch_file(str(test_file), patch_content)

            # Verify the failed attempt was tracked
            assert str(test_file) in FAILED_EDITS_HISTORY
            assert len(FAILED_EDITS_HISTORY[str(test_file)]) == 1
            attempt = FAILED_EDITS_HISTORY[str(test_file)][0]
            assert attempt["failure_stage"] == "block_application"
            assert "Could not find the search text" in attempt["error_message"]

    def test_patch_file_integration_success_clears_history(self, tmp_path):
        """Test that successful patch clears failed edit history."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("old content")

        # Mock allowed directories
        with patch("patch_file_mcp.server.allowed_directories", [str(tmp_path)]):
            # First fail an attempt
            patch_content = """<<<<<<< SEARCH
nonexistent content
=======
modified content
>>>>>>> REPLACE"""

            with pytest.raises(RuntimeError):
                patch_file(str(test_file), patch_content)

            # Verify failed attempt is tracked
            assert str(test_file) in FAILED_EDITS_HISTORY

            # Now succeed with correct content
            success_patch = """<<<<<<< SEARCH
old content
=======
new content
>>>>>>> REPLACE"""

            result = patch_file(str(test_file), success_patch)

            # Verify success
            assert "Successfully applied 1 patch blocks" in result

            # Verify history was cleared
            assert str(test_file) not in FAILED_EDITS_HISTORY

    def test_garbage_collection_removes_old_entries(self):
        """Test that garbage collection removes entries older than 1 hour."""
        file_path = "/path/to/test.py"
        # No need for patch content in this test

        # Create attempts with different timestamps
        old_datetime = datetime.now() - timedelta(hours=2)  # 2 hours ago
        recent_datetime = datetime.now() - timedelta(minutes=30)  # 30 minutes ago

        # Add old attempt
        FAILED_EDITS_HISTORY[file_path] = [
            {
                "datetime": old_datetime,
                "filename": file_path,
                "block_count": 1,
                "failure_stage": "test_failure",
                "error_message": "Old error",
                "params_hash": "hash1",
            }
        ]

        # Add another file with recent attempts
        recent_file = "/path/to/recent.py"
        FAILED_EDITS_HISTORY[recent_file] = [
            {
                "datetime": recent_datetime,
                "filename": recent_file,
                "block_count": 1,
                "failure_stage": "test_failure",
                "error_message": "Recent error",
                "params_hash": "hash2",
            }
        ]

        # Verify we have entries
        assert len(FAILED_EDITS_HISTORY) == 2
        assert len(FAILED_EDITS_HISTORY[file_path]) == 1
        assert len(FAILED_EDITS_HISTORY[recent_file]) == 1

        # Run garbage collection
        garbage_collect_failed_edit_history()

        # Verify old entries were removed but recent ones remain
        assert file_path not in FAILED_EDITS_HISTORY  # Old file completely removed
        assert recent_file in FAILED_EDITS_HISTORY  # Recent file remains
        assert len(FAILED_EDITS_HISTORY[recent_file]) == 1

    def test_garbage_collection_keeps_mixed_entries(self):
        """Test that garbage collection keeps recent entries but removes old ones from same file."""
        file_path = "/path/to/test.py"

        # Create mixed old and recent attempts for same file
        old_datetime = datetime.now() - timedelta(hours=2)
        recent_datetime = datetime.now() - timedelta(minutes=30)

        FAILED_EDITS_HISTORY[file_path] = [
            {
                "datetime": old_datetime,
                "filename": file_path,
                "block_count": 1,
                "failure_stage": "old_failure",
                "error_message": "Old error",
                "params_hash": "hash1",
            },
            {
                "datetime": recent_datetime,
                "filename": file_path,
                "block_count": 1,
                "failure_stage": "recent_failure",
                "error_message": "Recent error",
                "params_hash": "hash2",
            },
        ]

        # Run garbage collection
        garbage_collect_failed_edit_history()

        # Verify only recent entry remains
        assert file_path in FAILED_EDITS_HISTORY
        assert len(FAILED_EDITS_HISTORY[file_path]) == 1
        assert FAILED_EDITS_HISTORY[file_path][0]["failure_stage"] == "recent_failure"

    def test_successful_edit_always_clears_history(self):
        """Test that ANY successful edit clears ALL failed edit history for that file."""
        file_path = "/path/to/test.py"

        # Track multiple different failed attempts
        patch_content1 = """<<<<<<< SEARCH
content1
=======
new1
>>>>>>> REPLACE"""
        track_failed_edit(file_path, patch_content1, "failure1", "Error 1")

        patch_content2 = """<<<<<<< SEARCH
content2
=======
new2
>>>>>>> REPLACE"""
        track_failed_edit(file_path, patch_content2, "failure2", "Error 2")

        # Verify we have history
        assert file_path in FAILED_EDITS_HISTORY
        assert len(FAILED_EDITS_HISTORY[file_path]) == 2

        # Clear history (simulating successful edit)
        clear_failed_edit_history(file_path)

        # Verify history is completely cleared
        assert file_path not in FAILED_EDITS_HISTORY
        assert len(FAILED_EDITS_HISTORY.get(file_path, [])) == 0

    def test_tool_call_counter_and_garbage_collection_integration(self, tmp_path):
        """Test that tool call counter triggers garbage collection every 100 calls."""
        global TOOL_CALL_COUNTER

        # Reset counter for test
        original_counter = TOOL_CALL_COUNTER
        TOOL_CALL_COUNTER = 99  # One before garbage collection trigger

        file_path = tmp_path / "test.txt"
        file_path.write_text("content")

        # Mock old entries
        old_datetime = datetime.now() - timedelta(hours=2)
        FAILED_EDITS_HISTORY[str(file_path)] = [
            {
                "datetime": old_datetime,
                "filename": str(file_path),
                "block_count": 1,
                "failure_stage": "old_failure",
                "error_message": "Old error",
                "params_hash": "hash1",
            }
        ]

        # Mock allowed directories and call patch_file (should trigger GC on 100th call)
        with patch("patch_file_mcp.server.allowed_directories", [str(tmp_path)]):
            patch_content = """<<<<<<< SEARCH
content
=======
modified
>>>>>>> REPLACE"""

            # This should be the 100th call and trigger garbage collection
            result = patch_file(str(file_path), patch_content)

            # Verify the patch succeeded
            assert "Successfully applied 1 patch blocks" in result

            # Verify garbage collection removed old entries
            assert str(file_path) not in FAILED_EDITS_HISTORY

        # Restore original counter
        TOOL_CALL_COUNTER = original_counter


class TestMypyFailureSuppression:
    """Test cases for mypy failure count tracking and suppression."""

    def setup_method(self):
        """Clear mypy failure counts before each test."""
        MYPY_FAILURE_COUNTS.clear()

    def test_should_suppress_mypy_info_no_failures(self):
        """Test that mypy info is not suppressed when there are no failures."""
        file_path = "/path/to/test.py"

        assert should_suppress_mypy_info(file_path) is False

    def test_should_suppress_mypy_info_few_failures(self):
        """Test that mypy info is not suppressed with less than 3 failures."""
        file_path = "/path/to/test.py"

        # 1 failure
        update_mypy_failure_count(file_path, False)
        assert should_suppress_mypy_info(file_path) is False

        # 2 failures
        update_mypy_failure_count(file_path, False)
        assert should_suppress_mypy_info(file_path) is False

    def test_should_suppress_mypy_info_three_failures(self):
        """Test that mypy info is suppressed after 3 consecutive failures."""
        file_path = "/path/to/test.py"

        # First 2 failures - should not suppress
        update_mypy_failure_count(file_path, False)
        update_mypy_failure_count(file_path, False)
        assert should_suppress_mypy_info(file_path) is False

        # 3rd failure - should suppress
        update_mypy_failure_count(file_path, False)
        assert should_suppress_mypy_info(file_path) is True

        # 4th failure - should still suppress
        update_mypy_failure_count(file_path, False)
        assert should_suppress_mypy_info(file_path) is True

    def test_update_mypy_failure_count_reset_on_success(self):
        """Test that mypy failure count resets to 0 on successful mypy."""
        file_path = "/path/to/test.py"

        # Build up 2 failures
        update_mypy_failure_count(file_path, False)
        update_mypy_failure_count(file_path, False)
        assert MYPY_FAILURE_COUNTS[file_path] == 2

        # Success should reset to 0
        update_mypy_failure_count(file_path, True)
        assert MYPY_FAILURE_COUNTS[file_path] == 0

        # Should not suppress after reset
        assert should_suppress_mypy_info(file_path) is False

    def test_update_mypy_failure_count_increment_on_failure(self):
        """Test that mypy failure count increments on each failure."""
        file_path = "/path/to/test.py"

        assert MYPY_FAILURE_COUNTS.get(file_path, 0) == 0

        update_mypy_failure_count(file_path, False)
        assert MYPY_FAILURE_COUNTS[file_path] == 1

        update_mypy_failure_count(file_path, False)
        assert MYPY_FAILURE_COUNTS[file_path] == 2

        update_mypy_failure_count(file_path, False)
        assert MYPY_FAILURE_COUNTS[file_path] == 3

    def test_different_files_have_separate_counts(self):
        """Test that different files maintain separate mypy failure counts."""
        file1 = "/path/to/file1.py"
        file2 = "/path/to/file2.py"

        # File 1 gets 2 failures
        update_mypy_failure_count(file1, False)
        update_mypy_failure_count(file1, False)

        # File 2 gets 3 failures
        update_mypy_failure_count(file2, False)
        update_mypy_failure_count(file2, False)
        update_mypy_failure_count(file2, False)

        # File 1 should not suppress (only 2 failures)
        assert should_suppress_mypy_info(file1) is False

        # File 2 should suppress (3 failures)
        assert should_suppress_mypy_info(file2) is True

        # Counts should be separate
        assert MYPY_FAILURE_COUNTS[file1] == 2
        assert MYPY_FAILURE_COUNTS[file2] == 3

    def test_mypy_suppression_integration_with_qa_output(self, tmp_path):
        """Test that mypy suppression works in the full patch_file QA output."""
        file_path = tmp_path / "test.py"
        file_path.write_text("def hello():\n    return 'world'")

        # Mock allowed directories
        with patch("patch_file_mcp.server.allowed_directories", [str(tmp_path)]):
            # Build up 3 mypy failures first
            for i in range(3):
                update_mypy_failure_count(str(file_path), False)

            # Verify suppression is active
            assert should_suppress_mypy_info(str(file_path)) is True

            # Mock QA pipeline with mypy failure - should not include mypy in output
            with patch("patch_file_mcp.server.run_python_qa_pipeline") as mock_qa:
                mock_qa.return_value = {
                    "qa_performed": True,
                    "iterations_used": 1,
                    "ruff_status": "passed",
                    "black_status": "passed",
                    "mypy_status": "failed",  # This should be suppressed
                    "mypy_stdout": "mypy error output",
                    "mypy_stderr": "",
                    "errors": [],
                    "warnings": [],
                }

                patch_content = """<<<<<<< SEARCH
def hello():
    return 'world'
=======
def hello():
    return "world"
>>>>>>> REPLACE"""

                result = patch_file(str(file_path), patch_content)

                # Verify success
                assert "Successfully applied 1 patch blocks" in result
                assert "QA Results:" in result

                # Verify mypy info is suppressed (not mentioned at all)
                assert "MyPy" not in result
                assert "mypy error output" not in result

    def test_mypy_suppression_logic(self):
        """Test the core mypy suppression logic without full patch_file integration."""
        file_path = "/path/to/test.py"

        # Test suppression threshold
        assert should_suppress_mypy_info(file_path) is False  # 0 failures

        update_mypy_failure_count(file_path, False)
        assert should_suppress_mypy_info(file_path) is False  # 1 failure

        update_mypy_failure_count(file_path, False)
        assert should_suppress_mypy_info(file_path) is False  # 2 failures

        update_mypy_failure_count(file_path, False)
        assert should_suppress_mypy_info(file_path) is True  # 3 failures

        # Test reset on success
        update_mypy_failure_count(file_path, True)
        assert should_suppress_mypy_info(file_path) is False  # Reset to 0

    def test_mypy_success_resets_suppression(self, tmp_path):
        """Test that mypy success resets the suppression counter."""
        file_path = tmp_path / "test.py"
        file_path.write_text("def hello():\n    return 'world'")

        # Mock allowed directories and virtual environment
        with (
            patch("patch_file_mcp.server.allowed_directories", [str(tmp_path)]),
            patch(
                "patch_file_mcp.server.find_venv_directory",
                return_value="/fake/venv/bin/python",
            ),
        ):
            # Build up 3 failures to trigger suppression
            for i in range(3):
                update_mypy_failure_count(str(file_path), False)

            assert should_suppress_mypy_info(str(file_path)) is True

            # Mock QA pipeline with mypy success - should reset counter and include info
            with patch("patch_file_mcp.server.run_python_qa_pipeline") as mock_qa:
                mock_qa.return_value = {
                    "qa_performed": True,
                    "iterations_used": 1,
                    "ruff_status": "passed",
                    "black_status": "passed",
                    "mypy_status": "passed",  # Success should reset counter
                    "mypy_stdout": "",
                    "mypy_stderr": "",
                    "errors": [],
                    "warnings": [],
                }

                patch_content = """<<<<<<< SEARCH
def hello():
    return 'world'
=======
def hello():
    return "world"
>>>>>>> REPLACE"""

                result = patch_file(str(file_path), patch_content)

                # Verify success
                assert "Successfully applied 1 patch blocks" in result
                assert "QA Results:" in result

                # Verify mypy info is included (suppression was reset)
                assert "MyPy: ✅" in result

                # Verify counter was reset
                assert MYPY_FAILURE_COUNTS.get(str(file_path), 0) == 0
                assert should_suppress_mypy_info(str(file_path)) is False
