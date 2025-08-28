"""
Tests for the main patch_file function.
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import tempfile
import os

# Import the function we want to test
from patch_file_mcp.server import (
    patch_file,
    normalize_path,
    validate_directory_access,
    is_file_in_allowed_directories,
)


class TestPatchFile:
    """Test cases for the patch_file function."""

    def test_patch_file_successful_python_file(self, tmp_path, mock_subprocess_run):
        """Test successful patching of a Python file."""
        # Setup
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    print('Hello')\n")

        # Mock the allowed directories
        with patch('patch_file_mcp.server.allowed_directories', [str(tmp_path)]):
            # Create patch content
            patch_content = """<<<<<<< SEARCH
def hello():
    print('Hello')
=======
def hello():
    print('Hello, World!')
>>>>>>> REPLACE"""

            # Mock successful QA pipeline
            with patch('patch_file_mcp.server.run_python_qa_pipeline') as mock_qa:
                mock_qa.return_value = {
                    "qa_performed": True,
                    "iterations_used": 1,
                    "ruff_status": "passed",
                    "black_status": "passed",
                    "mypy_status": "passed",
                    "errors": [],
                    "warnings": []
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
        with patch('patch_file_mcp.server.allowed_directories', [str(tmp_path)]):
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
        with patch('patch_file_mcp.server.allowed_directories', [str(tmp_path)]):
            # Mock find_venv_directory to return None
            with patch('patch_file_mcp.server.find_venv_directory', return_value=None):
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
                assert "You need to perform code linting and QA by manually running" in result

    def test_patch_file_qa_errors(self, tmp_path):
        """Test patching Python file when QA has errors."""
        # Setup
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    print('Hello')\n")

        # Mock the allowed directories
        with patch('patch_file_mcp.server.allowed_directories', [str(tmp_path)]):
            # Create patch content
            patch_content = """<<<<<<< SEARCH
def hello():
    print('Hello')
=======
def hello():
    print('Hello, World!')
>>>>>>> REPLACE"""

            # Mock QA pipeline with errors
            with patch('patch_file_mcp.server.run_python_qa_pipeline') as mock_qa:
                mock_qa.return_value = {
                    "qa_performed": True,
                    "iterations_used": 1,
                    "ruff_status": "failed",
                    "black_status": None,
                    "mypy_status": None,
                    "errors": ["Ruff found unfixable errors: syntax error"],
                    "warnings": []
                }

                # Execute
                result = patch_file(str(test_file), patch_content)

                # Verify
                assert "Successfully applied 1 patch blocks" in result
                assert "QA Results:" in result
                assert "Ruff: failed" in result
                assert "QA Errors:" in result
                assert "unfixable errors" in result
                assert "You need to perform code linting and QA by manually running" in result

    def test_patch_file_file_not_found(self, tmp_path):
        """Test patching non-existent file."""
        # Setup
        non_existent_file = tmp_path / "nonexistent.py"

        # Mock the allowed directories
        with patch('patch_file_mcp.server.allowed_directories', [str(tmp_path)]):
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
        with patch('patch_file_mcp.server.allowed_directories', ['/some/other/path']):
            patch_content = """<<<<<<< SEARCH
test content
=======
modified content
>>>>>>> REPLACE"""

            # Execute and expect exception
            with pytest.raises(PermissionError, match="File .* is not in allowed directories"):
                patch_file(str(test_file), patch_content)

    def test_patch_file_invalid_patch_format(self, tmp_path):
        """Test patching with invalid patch format."""
        # Setup
        test_file = tmp_path / "test.py"
        test_file.write_text("test content")

        # Mock the allowed directories
        with patch('patch_file_mcp.server.allowed_directories', [str(tmp_path)]):
            # Invalid patch content (missing markers)
            patch_content = "invalid patch content"

            # Execute and expect exception
            with pytest.raises(RuntimeError, match="Failed to apply patch"):
                patch_file(str(test_file), patch_content)

    def test_patch_file_multiple_blocks(self, tmp_path):
        """Test patching with multiple search-replace blocks."""
        # Setup
        test_file = tmp_path / "test.py"
        test_file.write_text("def func1():\n    return 1\n\ndef func2():\n    return 2\n")

        # Mock the allowed directories
        with patch('patch_file_mcp.server.allowed_directories', [str(tmp_path)]):
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
        with patch('patch_file_mcp.server.allowed_directories', [str(tmp_path)]):
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
        with patch('patch_file_mcp.server.allowed_directories', [str(tmp_path)]):
            # Create patch content with ambiguous search text
            patch_content = """<<<<<<< SEARCH
print('hello')
=======
print('hi')
>>>>>>> REPLACE"""

            # Execute and expect exception
            with pytest.raises(RuntimeError, match="Failed to apply patch"):
                patch_file(str(test_file), patch_content)
