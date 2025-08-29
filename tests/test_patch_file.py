"""
Tests for the main patch_file function.
"""

import pytest
from unittest.mock import patch

# Import the function we want to test
from patch_file_mcp.server import (
    patch_file,
    is_binary_file_extension,
)


class TestPatchFile:
    """Test cases for the patch_file function."""

    def test_patch_file_successful_python_file(self, tmp_path, mock_subprocess_run):
        """Test successful patching of a Python file."""
        # Setup
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    print('Hello')\n")

        # Mock the allowed directories
        with patch("patch_file_mcp.server.allowed_directories", [str(tmp_path)]):
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
                assert "Ruff: passed" in result
                assert "Black: passed" in result
                assert "MyPy: passed" in result

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
                assert "QA Warning: No virtual environment" in result
                assert (
                    "You need to perform code linting and QA by manually running"
                    in result
                )

    def test_patch_file_qa_errors(self, tmp_path):
        """Test patching Python file when QA has errors."""
        # Setup
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    print('Hello')\n")

        # Mock the allowed directories
        with patch("patch_file_mcp.server.allowed_directories", [str(tmp_path)]):
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
                assert "Ruff output:" in result
                assert "Ruff found unfixable errors: syntax error" in result
                assert "QA Errors:" in result
                assert "unfixable errors" in result
                assert (
                    "You need to perform code linting and QA by manually running"
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
        # Mock normalize_path to raise ValueError
        with patch("patch_file_mcp.server.normalize_path") as mock_normalize:
            mock_normalize.side_effect = ValueError("Path validation failed")

            with patch("patch_file_mcp.server.allowed_directories", [str(tmp_path)]):
                patch_content = """<<<<<<< SEARCH
test
=======
modified
>>>>>>> REPLACE"""

                with pytest.raises(ValueError, match="Invalid or relative path"):
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
            if 'w' in mode:
                raise OSError("Write permission denied")
            return original_open(filename, mode, **kwargs)

        with patch("builtins.open", side_effect=mock_open_write):
            with patch("patch_file_mcp.server.allowed_directories", [str(tmp_path)]):
                patch_content = """<<<<<<< SEARCH
content
=======
modified
>>>>>>> REPLACE"""

                with pytest.raises(RuntimeError, match="Failed to apply patch.*Write permission denied"):
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
