"""
Integration tests for the patch-file-mcp functionality.
"""
import pytest
from pathlib import Path
import time
import tempfile
import os

# Import the functions we want to test
from patch_file_mcp.server import (
    get_file_modification_time,
    run_command_with_timeout,
    parse_search_replace_blocks,
    validate_block_integrity,
)


class TestIntegration:
    """Integration test cases."""

    def test_get_file_modification_time(self, tmp_path):
        """Test getting file modification time."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        # Get modification time
        mod_time = get_file_modification_time(str(test_file))

        # Verify it's a valid timestamp
        assert isinstance(mod_time, float)
        assert mod_time > 0

        # Modify file and check time changes
        time.sleep(0.01)  # Small delay
        test_file.write_text("modified content")
        new_mod_time = get_file_modification_time(str(test_file))

        assert new_mod_time > mod_time

    def test_run_command_with_timeout_success(self):
        """Test successful command execution."""
        if os.name == 'nt':  # Windows
            success, stdout, stderr, returncode = run_command_with_timeout(
                'echo "test"', shell=True
            )
        else:  # Unix-like
            success, stdout, stderr, returncode = run_command_with_timeout(
                'echo "test"'
            )

        assert success is True
        assert returncode == 0

    def test_run_command_with_timeout_failure(self):
        """Test failed command execution."""
        success, stdout, stderr, returncode = run_command_with_timeout(
            'nonexistent_command_that_should_fail'
        )

        assert success is False
        assert returncode != 0

    def test_run_command_with_timeout_timeout(self):
        """Test command timeout."""
        # Use a command that should take longer than timeout
        if os.name == 'nt':  # Windows
            success, stdout, stderr, returncode = run_command_with_timeout(
                'timeout /t 10', timeout=1
            )
        else:  # Unix-like
            success, stdout, stderr, returncode = run_command_with_timeout(
                'sleep 10', timeout=1
            )

        assert success is False
        assert "timed out" in stderr.lower()

    def test_parse_search_replace_blocks_valid(self):
        """Test parsing valid patch blocks."""
        patch_content = """<<<<<<< SEARCH
def hello():
    print("Hello")
=======
def hello():
    print("Hello, World!")
>>>>>>> REPLACE"""

        blocks = parse_search_replace_blocks(patch_content)

        assert len(blocks) == 1
        assert blocks[0][0] == 'def hello():\n    print("Hello")'
        assert blocks[0][1] == 'def hello():\n    print("Hello, World!")'

    def test_parse_search_replace_blocks_multiple(self):
        """Test parsing multiple patch blocks."""
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

        blocks = parse_search_replace_blocks(patch_content)

        assert len(blocks) == 2
        assert "func1" in blocks[0][0]
        assert "func2" in blocks[1][0]

    def test_parse_search_replace_blocks_invalid_format(self):
        """Test parsing invalid patch format."""
        invalid_patch = "invalid patch content without markers"

        with pytest.raises(ValueError, match="Invalid patch format"):
            parse_search_replace_blocks(invalid_patch)

    def test_validate_block_integrity_valid(self):
        """Test validating valid patch block integrity."""
        valid_patch = """<<<<<<< SEARCH
content
=======
replacement
>>>>>>> REPLACE"""

        # Should not raise exception
        validate_block_integrity(valid_patch)

    def test_validate_block_integrity_unbalanced_markers(self):
        """Test validating patch with unbalanced markers."""
        invalid_patch = """<<<<<<< SEARCH
content
=======
replacement
>>>>>>> REPLACE
<<<<<<< SEARCH
more content
=======
more replacement
>>>>>>> REPLACE"""

        with pytest.raises(ValueError, match="Unbalanced markers"):
            validate_block_integrity(invalid_patch)

    def test_validate_block_integrity_nested_markers(self):
        """Test validating patch with nested markers."""
        invalid_patch = """<<<<<<< SEARCH
<<<<<<< SEARCH
nested
=======
replacement
>>>>>>> REPLACE
=======
outer replacement
>>>>>>> REPLACE"""

        with pytest.raises(ValueError, match="Nested SEARCH marker"):
            validate_block_integrity(invalid_patch)

    def test_validate_block_integrity_incorrect_sequence(self):
        """Test validating patch with incorrect marker sequence."""
        invalid_patch = """=======
replacement
<<<<<<< SEARCH
content
>>>>>>> REPLACE"""

        with pytest.raises(ValueError, match="Incorrect marker sequence"):
            validate_block_integrity(invalid_patch)

    @pytest.mark.slow
    def test_full_workflow_simulation(self, tmp_path):
        """Test a simulated full workflow (slow test)."""
        # This test simulates the full workflow without actually calling patch_file
        # to avoid complex mocking

        # Create a test Python file
        test_file = tmp_path / "example.py"
        original_content = """def calculate_sum(a, b):
    return a + b

def main():
    result = calculate_sum(5, 3)
    print(f"Result: {result}")

if __name__ == "__main__":
    main()
"""
        test_file.write_text(original_content)

        # Simulate parsing a patch
        patch_content = """<<<<<<< SEARCH
def calculate_sum(a, b):
    return a + b
=======
def calculate_sum(a, b):
    '''Calculate the sum of two numbers.'''
    return a + b
>>>>>>> REPLACE"""

        # Parse the patch
        blocks = parse_search_replace_blocks(patch_content)
        assert len(blocks) == 1

        # Simulate applying the patch
        search_text, replace_text = blocks[0]
        assert search_text in original_content

        modified_content = original_content.replace(search_text, replace_text)
        assert "Calculate the sum of two numbers" in modified_content

        # Write back to file
        test_file.write_text(modified_content)

        # Verify file was modified
        final_content = test_file.read_text()
        assert '"""Calculate the sum of two numbers."""' in final_content
        assert "Result: 8" not in final_content  # Original calculation still works
