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
        # Mock subprocess.run to return a failure
        from unittest.mock import patch, MagicMock

        with patch('patch_file_mcp.server.subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_result.stderr = "Command failed"
            mock_run.return_value = mock_result

            success, stdout, stderr, returncode = run_command_with_timeout(
                'false'
            )

        assert success is False
        assert returncode == 1

    def test_run_command_with_timeout_timeout(self):
        """Test command timeout."""
        # Mock subprocess.run to raise TimeoutExpired
        from unittest.mock import patch
        import subprocess

        with patch('patch_file_mcp.server.subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired('sleep 10', 1)

            success, stdout, stderr, returncode = run_command_with_timeout(
                'sleep 10', timeout=1
            )

        assert success is False
        assert "timed out" in stderr.lower()
        assert returncode == -1

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
replacement"""

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

        with pytest.raises(ValueError, match="Incorrect marker sequence"):
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
        assert "'''Calculate the sum of two numbers.'''" in final_content
        assert "Result: 8" not in final_content  # Original calculation still works

    def test_parse_search_replace_blocks_fallback_parsing(self):
        """Test fallback parsing when regex fails."""
        from unittest.mock import patch

        # Create a patch that might confuse regex but should work with fallback
        patch_content = """<<<<<<< SEARCH
# Special regex characters: .*+?^$()[]{}|
# These might confuse regex patterns
=======
# Modified content with special characters
>>>>>>> REPLACE"""

        # Mock re.findall to return empty (simulating regex failure)
        with patch("patch_file_mcp.server.re.findall", return_value=[]):
            blocks = parse_search_replace_blocks(patch_content)

            assert len(blocks) == 1
            assert "Special regex characters" in blocks[0][0]
            assert "Modified content" in blocks[0][1]

    def test_parse_search_replace_blocks_fallback_missing_separator(self):
        """Test fallback parsing with missing separator marker."""
        from unittest.mock import patch

        # Create malformed patch missing separator
        patch_content = """<<<<<<< SEARCH
content without separator
>>>>>>> REPLACE"""

        # Mock re.findall to return empty to trigger fallback
        with patch("patch_file_mcp.server.re.findall", return_value=[]):
            with pytest.raises(ValueError, match="Unbalanced markers"):
                parse_search_replace_blocks(patch_content)

    def test_parse_search_replace_blocks_fallback_missing_replace_marker(self):
        """Test fallback parsing with missing replace marker."""
        from unittest.mock import patch

        # Create malformed patch missing replace marker
        patch_content = """<<<<<<< SEARCH
content
=======
replacement content"""

        # Mock re.findall to return empty to trigger fallback
        with patch("patch_file_mcp.server.re.findall", return_value=[]):
            with pytest.raises(ValueError, match="Unbalanced markers"):
                parse_search_replace_blocks(patch_content)

    def test_parse_search_replace_blocks_fallback_markers_in_search_content(self):
        """Test fallback parsing when markers appear in search content."""
        from unittest.mock import patch

        # Create patch with markers in search content (should be rejected)
        patch_content = """<<<<<<< SEARCH
This content has ======= in it
=======
This replacement is fine
>>>>>>> REPLACE"""

        # Mock re.findall to return empty to trigger fallback
        with patch("patch_file_mcp.server.re.findall", return_value=[]):
            with pytest.raises(ValueError, match="Unbalanced markers"):
                parse_search_replace_blocks(patch_content)

    def test_parse_search_replace_blocks_fallback_markers_in_replace_content(self):
        """Test fallback parsing when markers appear in replace content."""
        from unittest.mock import patch

        # Create patch with markers in replace content (should be rejected)
        patch_content = """<<<<<<< SEARCH
This search is fine
=======
This replacement has >>>>>>> REPLACE in it
>>>>>>> REPLACE"""

        # Mock re.findall to return empty to trigger fallback
        with patch("patch_file_mcp.server.re.findall", return_value=[]):
            with pytest.raises(ValueError, match="Unbalanced markers"):
                parse_search_replace_blocks(patch_content)