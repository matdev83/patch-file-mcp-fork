"""
Tests for QA pipeline functionality.
"""

import pytest
from unittest.mock import patch

# Import the functions we want to test
from patch_file_mcp import server as pf_server
from patch_file_mcp.server import run_python_qa_pipeline


class TestQAPipeline:
    """Test cases for QA pipeline functionality."""

    def test_run_python_qa_pipeline_successful(self, tmp_path, mock_subprocess_run):
        """Test successful QA pipeline run."""
        # Setup - create a properly formatted Python file
        test_file = tmp_path / "test.py"
        test_file.write_text(
            '''"""A simple test module."""

def hello_world():
    """Print hello world."""
    print("Hello, World!")
    return True

if __name__ == "__main__":
    hello_world()
'''
        )
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
        test_file.write_text(
            '''"""A test module with issues."""

def bad_function():
    print("This has issues")
    return
'''
        )
        python_exe = "/mock/python.exe"

        # Mock ruff failure
        def mock_run(cmd, cwd=None, timeout=30, shell=False, env=None):
            # Handle both string and list command formats
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            if "ruff" in cmd_str:
                return (True, "", "Ruff error: unfixable issue", 1)
            return (True, "", "", 0)

        mock_subprocess_run.side_effect = mock_run

        # Execute
        result = run_python_qa_pipeline(str(test_file), python_exe)

        # Verify
        assert result["qa_performed"] is True
        assert result["ruff_status"] == "failed"
        assert result["ruff_stderr"] == "Ruff error: unfixable issue"

    def test_run_python_qa_pipeline_black_reformats(
        self, tmp_path, mock_qa_pipeline_complex
    ):
        """Test QA pipeline when black reformats code."""
        # Setup
        test_file = tmp_path / "test.py"
        test_file.write_text(
            '''"""Test module that needs formatting."""

def hello():
    print("hello")
    return True
'''
        )
        python_exe = "/mock/python.exe"

        # Execute
        result = run_python_qa_pipeline(str(test_file), python_exe)

        # Verify
        assert result["qa_performed"] is True
        assert result["iterations_used"] >= 2  # Should have multiple iterations

    def test_run_python_qa_pipeline_iteration_limit(
        self, tmp_path, mock_qa_pipeline_iteration_limit
    ):
        """Test QA pipeline hits iteration limit."""
        # Setup
        test_file = tmp_path / "test.py"
        test_file.write_text(
            '''"""Test module for iteration limit."""

def test():
    print("test")
    return True
'''
        )
        python_exe = "/mock/python.exe"

        # Execute
        result = run_python_qa_pipeline(str(test_file), python_exe)

        # Verify
        assert result["qa_performed"] is True
        assert (
            result["iterations_used"] == 4
        )  # Should hit the limit (QA_MAX_ITERATIONS = 4)
        assert len(result["warnings"]) == 1
        assert "iteration limit" in result["warnings"][0]

    def test_run_python_qa_pipeline_command_timeout(
        self, tmp_path, mock_qa_pipeline_timeout
    ):
        """Test QA pipeline when command times out."""
        # Setup
        test_file = tmp_path / "test.py"
        test_file.write_text(
            '''"""Test module for timeout."""

def test():
    print("test")
    return True
'''
        )
        python_exe = "/mock/python.exe"

        # Execute
        result = run_python_qa_pipeline(str(test_file), python_exe)

        # Verify
        assert result["qa_performed"] is True
        assert result["ruff_status"] == "failed"
        assert result["ruff_stderr"] == "Command timed out after 15 seconds"

    def test_run_python_qa_pipeline_with_warnings(
        self, tmp_path, mock_qa_pipeline_warnings
    ):
        """Test QA pipeline with warnings but no errors."""
        # Setup
        test_file = tmp_path / "test.py"
        test_file.write_text(
            '''"""Test module with warnings."""

def test_function():
    print("test")
    return True
'''
        )
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

        # Verify - QA pipeline should not run for non-Python files
        # The function returns the default result without running QA
        assert result["qa_performed"] is True  # Function always sets this to True
        # For non-Python files, iterations_used should be 0 since QA doesn't run
        assert result["iterations_used"] == 0

    def test_run_python_qa_pipeline_empty_python_exe(
        self, tmp_path, mock_subprocess_run
    ):
        """Test QA pipeline with empty Python executable path."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def test():\n    pass")

        # Configure mock to return failure for empty python exe
        def mock_command(cmd, cwd=None, timeout=30, shell=False, env=None):
            # Handle both string and list command formats
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
            if (
                '""' in cmd_str or cmd_str.strip() == "" or cmd_str == '""'
            ):  # Empty command
                return (False, "", "python.exe: command not found", 127)
            return (True, "", "", 0)

        mock_subprocess_run.side_effect = mock_command

        # Test with empty python_exe
        result = run_python_qa_pipeline(str(test_file), "")

        # Should fail gracefully
        assert result["qa_performed"] is True
        assert result["ruff_status"] == "failed"
        assert len(result["errors"]) >= 1

    def test_run_python_qa_pipeline_none_python_exe(
        self, tmp_path, mock_subprocess_run
    ):
        """Test QA pipeline with None Python executable path."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def test():\n    pass")

        # Configure mock to return failure for None python exe
        def mock_command(cmd, cwd=None, timeout=30, shell=False, env=None):
            # Handle both string and list command formats
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            if cmd is None or "None" in cmd_str:  # None command
                return (False, "", "python.exe: command not found", 127)
            return (True, "", "", 0)

        mock_subprocess_run.side_effect = mock_command

        # Test with None python_exe
        result = run_python_qa_pipeline(str(test_file), None)

        # Should fail gracefully
        assert result["qa_performed"] is True
        assert result["ruff_status"] == "failed"
        assert len(result["errors"]) >= 1

    def test_run_python_qa_pipeline_nonexistent_file(
        self, tmp_path, mock_subprocess_run
    ):
        """Test QA pipeline with non-existent file."""
        nonexistent_file = tmp_path / "nonexistent.py"

        # Configure mock to return failure for nonexistent file
        def mock_command(cmd, cwd=None, timeout=30, shell=False, env=None):
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
        test_file.write_text(
            """# This is a comment file
# Another comment
# Final comment"""
        )

        mock_subprocess_run.return_value = (True, "", "", 0)

        result = run_python_qa_pipeline(str(test_file), "/mock/python.exe")

        assert result["qa_performed"] is True
        assert result["iterations_used"] == 1

    def test_run_python_qa_pipeline_mypy_only_warnings(
        self, tmp_path, mock_subprocess_run
    ):
        """Test QA pipeline when mypy has only warnings (no errors)."""
        test_file = tmp_path / "test.py"
        test_file.write_text('def test():\n    print("hello")')

        def mock_run(cmd, cwd=None, timeout=30, shell=False, env=None):
            # Handle both string and list command formats
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            if "mypy" in cmd_str:
                return (
                    True,
                    "",
                    "warning: unused variable",
                    0,
                )  # Return code 0 means success but with warnings
            return (True, "", "", 0)

        mock_subprocess_run.side_effect = mock_run

        result = run_python_qa_pipeline(str(test_file), "/mock/python.exe")

        assert result["qa_performed"] is True
        assert (
            result["mypy_status"] == "passed"
        )  # Should be passed since return code was 0

    def test_run_python_qa_pipeline_wall_time_timeout(
        self, tmp_path, mock_subprocess_run
    ):
        """Test QA pipeline wall time timeout."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def test():\n    pass")

        # Mock subprocess to always succeed
        def mock_command(cmd, cwd=None, timeout=30, shell=False, env=None):
            return (True, "", "", 0)

        mock_subprocess_run.side_effect = mock_command

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

    def test_mypy_skipped_on_tests_by_default(self, tmp_path, mock_subprocess_run):
        """Test that mypy is skipped by default on files with 'tests' in path."""
        # Setup - create a test file with 'tests' in path
        test_file = tmp_path / "tests" / "test_example.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("def test_function():\n    pass")
        python_exe = "/mock/python.exe"

        # Mock to track mypy calls
        mypy_called = False

        def mock_command(cmd, cwd=None, timeout=30, shell=False, env=None):
            nonlocal mypy_called
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            if "mypy" in cmd_str and "--no-color-output" in cmd_str:
                mypy_called = True
            return (True, "", "", 0)

        mock_subprocess_run.side_effect = mock_command

        # Test the actual behavior by temporarily modifying the global variables
        original_skip_mypy = pf_server.SKIP_MYPY
        original_skip_mypy_on_tests = pf_server.SKIP_MYPY_ON_TESTS

        try:
            # Set the desired state for this test
            pf_server.SKIP_MYPY = False
            pf_server.SKIP_MYPY_ON_TESTS = True

            result = run_python_qa_pipeline(str(test_file), python_exe)

            # Verify mypy was not called
            assert not mypy_called
            assert result["mypy_status"] is None

        finally:
            # Restore original values
            pf_server.SKIP_MYPY = original_skip_mypy
            pf_server.SKIP_MYPY_ON_TESTS = original_skip_mypy_on_tests

    def test_mypy_runs_on_tests_with_flag(self, tmp_path, mock_subprocess_run):
        """Test that mypy runs on test files when --run-mypy-on-tests is used."""
        # Setup - create a test file with 'tests' in path
        test_file = tmp_path / "tests" / "test_example.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("def test_function():\n    pass")
        python_exe = "/mock/python.exe"

        # Mock to track mypy calls
        mypy_called = False

        def mock_command(cmd, cwd=None, timeout=30, shell=False, env=None):
            nonlocal mypy_called
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            if "mypy" in cmd_str:
                mypy_called = True
            return (True, "", "", 0)

        mock_subprocess_run.side_effect = mock_command

        # Test the actual behavior by temporarily modifying the global variables
        original_skip_mypy = pf_server.SKIP_MYPY
        original_skip_mypy_on_tests = pf_server.SKIP_MYPY_ON_TESTS

        try:
            # Set the desired state for this test (when --run-mypy-on-tests is used)
            pf_server.SKIP_MYPY = False
            pf_server.SKIP_MYPY_ON_TESTS = False

            result = run_python_qa_pipeline(str(test_file), python_exe)

            # Verify mypy was called
            assert mypy_called
            assert result["mypy_status"] == "passed"

        finally:
            # Restore original values
            pf_server.SKIP_MYPY = original_skip_mypy
            pf_server.SKIP_MYPY_ON_TESTS = original_skip_mypy_on_tests

    def test_mypy_runs_on_non_test_files_by_default(
        self, tmp_path, mock_subprocess_run
    ):
        """Test that mypy runs on non-test files by default."""
        # Setup - create a regular file (no 'tests' in path)
        test_file = tmp_path / "regular_file.py"
        test_file.write_text("def regular_function():\n    pass")
        python_exe = "/mock/python.exe"

        # Mock to track mypy calls
        mypy_called = False

        def mock_command(cmd, cwd=None, timeout=30, shell=False, env=None):
            nonlocal mypy_called
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            if "mypy" in cmd_str:
                mypy_called = True
            return (True, "", "", 0)

        mock_subprocess_run.side_effect = mock_command

        # Test the actual behavior by temporarily modifying the global variables
        original_skip_mypy = pf_server.SKIP_MYPY
        original_skip_mypy_on_tests = pf_server.SKIP_MYPY_ON_TESTS

        try:
            # Set the desired state for this test (default behavior)
            pf_server.SKIP_MYPY = False
            pf_server.SKIP_MYPY_ON_TESTS = True

            result = run_python_qa_pipeline(str(test_file), python_exe)

            # Verify mypy was called (since file doesn't contain 'tests')
            assert mypy_called
            assert result["mypy_status"] == "passed"

        finally:
            # Restore original values
            pf_server.SKIP_MYPY = original_skip_mypy
            pf_server.SKIP_MYPY_ON_TESTS = original_skip_mypy_on_tests

    def test_no_mypy_overrides_run_mypy_on_tests(self, tmp_path, mock_subprocess_run):
        """Test that --no-mypy overrides --run-mypy-on-tests."""
        # Setup - create a test file with 'tests' in path
        test_file = tmp_path / "tests" / "test_example.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("def test_function():\n    pass")
        python_exe = "/mock/python.exe"

        # Mock to track mypy calls
        mypy_called = False

        def mock_command(cmd, cwd=None, timeout=30, shell=False, env=None):
            nonlocal mypy_called
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            if "mypy" in cmd_str and "--no-color-output" in cmd_str:
                mypy_called = True
            return (True, "", "", 0)

        mock_subprocess_run.side_effect = mock_command

        # Test the actual behavior by temporarily modifying the global variables
        original_skip_mypy = pf_server.SKIP_MYPY
        original_skip_mypy_on_tests = pf_server.SKIP_MYPY_ON_TESTS

        try:
            # Set the desired state for this test (--no-mypy overrides)
            pf_server.SKIP_MYPY = True
            pf_server.SKIP_MYPY_ON_TESTS = False

            result = run_python_qa_pipeline(str(test_file), python_exe)

            # Verify mypy was not called (overridden by --no-mypy)
            assert not mypy_called
            assert result["mypy_status"] is None

        finally:
            # Restore original values
            pf_server.SKIP_MYPY = original_skip_mypy
            pf_server.SKIP_MYPY_ON_TESTS = original_skip_mypy_on_tests
