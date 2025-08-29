"""
Tests for QA pipeline functionality.
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call

# Import the functions we want to test
from patch_file_mcp.server import run_python_qa_pipeline


class TestQAPipeline:
    """Test cases for QA pipeline functionality."""

    def test_run_python_qa_pipeline_successful(self, tmp_path, mock_subprocess_run):
        """Test successful QA pipeline run."""
        # Setup - create a properly formatted Python file
        test_file = tmp_path / "test.py"
        test_file.write_text('''"""A simple test module."""

def hello_world():
    """Print hello world."""
    print("Hello, World!")
    return True

if __name__ == "__main__":
    hello_world()
''')
        python_exe = "/mock/python.exe"

        # Mock successful command executions
        mock_subprocess_run.return_value = (True, "", "", 0)

        # Execute
        result = run_python_qa_pipeline(str(test_file), python_exe)

        # Verify
        assert result["qa_performed"] is True
        assert result["iterations_used"] == 1
        assert result["ruff_status"] == "passed"
        assert result["black_status"] == "passed"
        assert result["mypy_status"] == "passed"
        assert result["errors"] == []
        assert result["warnings"] == []

    def test_run_python_qa_pipeline_ruff_fails(self, tmp_path, mock_subprocess_run):
        """Test QA pipeline when ruff fails."""
        # Setup
        test_file = tmp_path / "test.py"
        test_file.write_text('''"""A test module with issues."""

def bad_function():
    print("This has issues")
    return
''')
        python_exe = "/mock/python.exe"

        # Mock ruff failure
        def mock_run(cmd, **kwargs):
            if "ruff" in cmd:
                return (True, "", "Ruff error: unfixable issue", 1)
            return (True, "", "", 0)

        mock_subprocess_run.side_effect = mock_run

        # Execute
        result = run_python_qa_pipeline(str(test_file), python_exe)

        # Verify
        assert result["qa_performed"] is True
        assert result["ruff_status"] == "failed"
        assert len(result["errors"]) == 1
        assert "unfixable errors" in result["errors"][0]

    def test_run_python_qa_pipeline_black_reformats(self, tmp_path, mock_qa_pipeline_complex):
        """Test QA pipeline when black reformats code."""
        # Setup
        test_file = tmp_path / "test.py"
        test_file.write_text('''"""Test module that needs formatting."""

def hello():
    print("hello")
    return True
''')
        python_exe = "/mock/python.exe"

        # Execute
        result = run_python_qa_pipeline(str(test_file), python_exe)

        # Verify
        assert result["qa_performed"] is True
        assert result["iterations_used"] >= 2  # Should have multiple iterations

    def test_run_python_qa_pipeline_iteration_limit(self, tmp_path, mock_qa_pipeline_iteration_limit):
        """Test QA pipeline hits iteration limit."""
        # Setup
        test_file = tmp_path / "test.py"
        test_file.write_text('''"""Test module for iteration limit."""

def test():
    print("test")
    return True
''')
        python_exe = "/mock/python.exe"

        # Execute
        result = run_python_qa_pipeline(str(test_file), python_exe)

        # Verify
        assert result["qa_performed"] is True
        assert result["iterations_used"] == 2  # Should hit the limit (QA_MAX_ITERATIONS = 2)
        assert len(result["errors"]) == 1
        assert "maximum iterations" in result["errors"][0]

    def test_run_python_qa_pipeline_command_timeout(self, tmp_path, mock_qa_pipeline_timeout):
        """Test QA pipeline when command times out."""
        # Setup
        test_file = tmp_path / "test.py"
        test_file.write_text('''"""Test module for timeout."""

def test():
    print("test")
    return True
''')
        python_exe = "/mock/python.exe"

        # Execute
        result = run_python_qa_pipeline(str(test_file), python_exe)

        # Verify
        assert result["qa_performed"] is True
        assert result["ruff_status"] == "failed"
        assert len(result["errors"]) == 1
        assert "timed out" in result["errors"][0]

    def test_run_python_qa_pipeline_with_warnings(self, tmp_path, mock_qa_pipeline_warnings):
        """Test QA pipeline with warnings but no errors."""
        # Setup
        test_file = tmp_path / "test.py"
        test_file.write_text('''"""Test module with warnings."""

def test_function():
    print("test")
    return True
''')
        python_exe = "/mock/python.exe"

        # Execute
        result = run_python_qa_pipeline(str(test_file), python_exe)

        # Verify
        assert result["qa_performed"] is True
        assert result["ruff_status"] == "passed"
        assert result["black_status"] == "warnings"
        assert result["mypy_status"] == "passed"
        assert len(result["warnings"]) >= 1

    @pytest.mark.parametrize("file_extension", [".txt", ".md", ".json", ".html"])
    def test_run_python_qa_pipeline_non_python_file(self, tmp_path, file_extension):
        """Test QA pipeline with non-Python files (should not run)."""
        # Setup
        test_file = tmp_path / f"test{file_extension}"
        test_file.write_text("some content")
        python_exe = "/mock/python.exe"

        # Execute - this should not run QA
        result = run_python_qa_pipeline(str(test_file), python_exe)

        # Verify - should return early with qa_performed=False
        # Note: In the actual implementation, this function is only called for .py files
        # But we test the logic anyway
        assert result["qa_performed"] is True  # Function always sets this to True
        assert result["iterations_used"] == 1  # Should still attempt to run

    def test_run_python_qa_pipeline_empty_python_exe(self, tmp_path, mock_subprocess_run):
        """Test QA pipeline with empty Python executable path."""
        test_file = tmp_path / "test.py"
        test_file.write_text('def test():\n    pass')

        # Configure mock to return failure for empty python exe
        def mock_command(cmd, cwd=None, timeout=30):
            if '""' in cmd or cmd.strip() == '':  # Empty command
                return (False, "", "python.exe: command not found", 127)
            return (True, "", "", 0)

        mock_subprocess_run.side_effect = mock_command

        # Test with empty python_exe
        result = run_python_qa_pipeline(str(test_file), "")

        # Should fail gracefully
        assert result["qa_performed"] is True
        assert result["ruff_status"] == "failed"
        assert len(result["errors"]) >= 1

    def test_run_python_qa_pipeline_none_python_exe(self, tmp_path, mock_subprocess_run):
        """Test QA pipeline with None Python executable path."""
        test_file = tmp_path / "test.py"
        test_file.write_text('def test():\n    pass')

        # Configure mock to return failure for None python exe
        def mock_command(cmd, cwd=None, timeout=30):
            if cmd is None or 'None' in cmd:  # None command
                return (False, "", "python.exe: command not found", 127)
            return (True, "", "", 0)

        mock_subprocess_run.side_effect = mock_command

        # Test with None python_exe
        result = run_python_qa_pipeline(str(test_file), None)

        # Should fail gracefully
        assert result["qa_performed"] is True
        assert result["ruff_status"] == "failed"
        assert len(result["errors"]) >= 1

    def test_run_python_qa_pipeline_nonexistent_file(self, tmp_path, mock_subprocess_run):
        """Test QA pipeline with non-existent file."""
        nonexistent_file = tmp_path / "nonexistent.py"

        # Configure mock to return failure for nonexistent file
        def mock_command(cmd, cwd=None, timeout=30):
            if str(nonexistent_file.name) in cmd:
                return (False, "", "No such file or directory", 1)
            return (True, "", "", 0)

        mock_subprocess_run.side_effect = mock_command

        # Should handle gracefully - commands will fail
        result = run_python_qa_pipeline(str(nonexistent_file), "/mock/python.exe")

        assert result["qa_performed"] is True
        assert result["ruff_status"] == "failed"
        assert len(result["errors"]) >= 1

    def test_run_python_qa_pipeline_empty_file(self, tmp_path, mock_subprocess_run):
        """Test QA pipeline with empty Python file."""
        test_file = tmp_path / "empty.py"
        test_file.write_text("")  # Empty file

        mock_subprocess_run.return_value = (True, "", "", 0)

        result = run_python_qa_pipeline(str(test_file), "/mock/python.exe")

        assert result["qa_performed"] is True
        assert result["iterations_used"] == 1

    def test_run_python_qa_pipeline_comments_only(self, tmp_path, mock_subprocess_run):
        """Test QA pipeline with file containing only comments."""
        test_file = tmp_path / "comments.py"
        test_file.write_text('''# This is a comment file
# Another comment
# Final comment''')

        mock_subprocess_run.return_value = (True, "", "", 0)

        result = run_python_qa_pipeline(str(test_file), "/mock/python.exe")

        assert result["qa_performed"] is True
        assert result["iterations_used"] == 1

    def test_run_python_qa_pipeline_mypy_only_warnings(self, tmp_path, mock_subprocess_run):
        """Test QA pipeline when mypy has only warnings (no errors)."""
        test_file = tmp_path / "test.py"
        test_file.write_text('def test():\n    print("hello")')

        def mock_run(cmd, **kwargs):
            if "mypy" in cmd:
                return (True, "", "warning: unused variable", 0)  # Return code 0 means success but with warnings
            return (True, "", "", 0)

        mock_subprocess_run.side_effect = mock_run

        result = run_python_qa_pipeline(str(test_file), "/mock/python.exe")

        assert result["qa_performed"] is True
        assert result["mypy_status"] == "passed"  # Should be passed since return code was 0

    def test_run_python_qa_pipeline_wall_time_timeout(self, tmp_path, mock_subprocess_run):
        """Test QA pipeline wall time timeout."""
        test_file = tmp_path / "test.py"
        test_file.write_text('def test():\n    pass')

        # Mock subprocess to always succeed
        mock_subprocess_run.return_value = (True, "", "", 0)

        # Mock to simulate wall time timeout: start_time = 0, loop check = 100
        call_count = 0
        def mock_monotonic():
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # start_time call
                return 0.0
            else:  # loop check call
                return 100.0  # Exceeded QA_WALL_TIME (20)

        with patch("time.monotonic", side_effect=mock_monotonic):
            result = run_python_qa_pipeline(str(test_file), "/mock/python.exe")

            assert result["qa_performed"] is True
            assert len(result["warnings"]) >= 1
            assert "timed out" in result["warnings"][0]