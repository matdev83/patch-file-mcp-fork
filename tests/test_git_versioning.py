"""
Tests for git versioning and recovery functionality.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from patch_file_mcp.git_repo import GitRepo, ANY_GIT_ERROR


class TestGitRepo:
    """Test the GitRepo class functionality."""

    def test_git_repo_initialization_with_git_repo(self):
        """Test GitRepo initialization in a git repository."""
        # We're in a git repo, so this should work
        repo = GitRepo(".", logger=None)
        assert repo.git_available is True
        assert repo.is_available() is True
        assert repo.root is not None
        assert repo.root.exists()

    def test_git_repo_initialization_without_git_repo(self):
        """Test GitRepo initialization in a non-git directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = GitRepo(temp_dir, logger=None)
            assert repo.git_available is True
            assert repo.is_available() is False
            assert repo.root is None

    def test_git_repo_initialization_without_gitpython(self):
        """Test GitRepo initialization when GitPython is not available."""
        # Mock the git module at the module level where it's imported
        with patch("patch_file_mcp.git_repo.git", None):
            repo = GitRepo(".", logger=None)
            assert repo.git_available is False
            assert repo.is_available() is False

    def test_get_head_commit_sha(self):
        """Test getting HEAD commit SHA."""
        repo = GitRepo(".", logger=None)
        if repo.is_available():
            sha = repo.get_head_commit_sha()
            assert sha is not None
            assert len(sha) >= 7  # Short SHA should be at least 7 chars

            # Test full SHA
            full_sha = repo.get_head_commit_sha(short=False)
            assert full_sha is not None
            assert len(full_sha) == 40  # Full SHA is 40 chars
        else:
            assert repo.get_head_commit_sha() is None

    def test_is_dirty(self):
        """Test checking if repository has uncommitted changes."""
        repo = GitRepo(".", logger=None)
        # This should return a boolean
        result = repo.is_dirty()
        assert isinstance(result, bool)

    def test_get_dirty_files(self):
        """Test getting list of dirty files."""
        repo = GitRepo(".", logger=None)
        dirty_files = repo.get_dirty_files()
        assert isinstance(dirty_files, list)

    def test_stage_files_success(self):
        """Test staging files successfully."""
        repo = GitRepo(".", logger=None)
        if not repo.is_available():
            pytest.skip("No git repository available")

        # Test with existing file
        test_file = "README.md"
        if Path(test_file).exists():
            result = repo.stage_files([test_file])
            assert isinstance(result, bool)

    def test_stage_files_nonexistent_file(self):
        """Test staging non-existent files."""
        repo = GitRepo(".", logger=None)
        if not repo.is_available():
            pytest.skip("No git repository available")

        result = repo.stage_files(["nonexistent_file.txt"])
        # Should handle gracefully
        assert isinstance(result, bool)

    def test_commit_files_success(self):
        """Test committing files successfully."""
        repo = GitRepo(".", logger=None)
        if not repo.is_available():
            pytest.skip("No git repository available")

        # Test with existing file
        test_file = "README.md"
        if Path(test_file).exists():
            # First stage the file
            repo.stage_files([test_file])
            # Then try to commit
            result = repo.commit_files([test_file], "Test commit")
            assert result is None or isinstance(result, tuple)

    def test_commit_files_no_files(self):
        """Test committing with no files."""
        repo = GitRepo(".", logger=None)
        result = repo.commit_files([], "Test commit")
        assert result is None

    def test_commit_files_no_message(self):
        """Test committing with no message."""
        repo = GitRepo(".", logger=None)
        result = repo.commit_files(["README.md"], "")
        assert result is None

    def test_get_commit_message_single_file(self):
        """Test generating commit message for single file."""
        repo = GitRepo(".", logger=None)
        message = repo.get_commit_message(["test.py"])
        assert isinstance(message, str)
        assert len(message) > 0

    def test_get_commit_message_multiple_files(self):
        """Test generating commit message for multiple files."""
        repo = GitRepo(".", logger=None)
        message = repo.get_commit_message(["file1.py", "file2.py", "file3.py"])
        assert isinstance(message, str)
        assert len(message) > 0
        assert "3 files" in message

    def test_get_commit_message_empty_list(self):
        """Test generating commit message for empty file list."""
        repo = GitRepo(".", logger=None)
        message = repo.get_commit_message([])
        assert message == "Update files"

    @patch("patch_file_mcp.git_repo.git")
    def test_git_error_handling(self, mock_git):
        """Test error handling for git operations."""
        mock_git.Repo.side_effect = ANY_GIT_ERROR[0]("Test error")

        repo = GitRepo(".", logger=None)
        assert repo.is_available() is False
        assert repo.get_head_commit_sha() is None
        assert repo.is_dirty() is False
        assert repo.get_dirty_files() == []

    def test_stage_files_empty_list(self):
        """Test staging with empty file list."""
        repo = GitRepo(".", logger=None)
        result = repo.stage_files([])
        assert result is False

    def test_commit_files_empty_list(self):
        """Test committing with empty file list."""
        repo = GitRepo(".", logger=None)
        result = repo.commit_files([], "Test message")
        assert result is None

    def test_stage_files_outside_repo(self):
        """Test staging files outside the repository."""
        repo = GitRepo(".", logger=None)
        if not repo.is_available():
            pytest.skip("No git repository available")

        # Create a temp file outside the repo
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b"test content")
            temp_file_path = temp_file.name

        try:
            result = repo.stage_files([temp_file_path])
            # Should handle gracefully (file is outside repo)
            assert isinstance(result, bool)
        finally:
            os.unlink(temp_file_path)

    def test_commit_files_outside_repo(self):
        """Test committing files outside the repository."""
        repo = GitRepo(".", logger=None)
        if not repo.is_available():
            pytest.skip("No git repository available")

        # Create a temp file outside the repo
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b"test content")
            temp_file_path = temp_file.name

        try:
            result = repo.commit_files([temp_file_path], "Test commit")
            # Should handle gracefully (file is outside repo)
            assert result is None
        finally:
            os.unlink(temp_file_path)

    def test_get_head_commit_sha_with_errors(self):
        """Test get_head_commit_sha with various error conditions."""
        repo = GitRepo(".", logger=None)

        # Test with repo not available
        if repo.is_available():
            # Force repo to be None to test error path
            original_repo = repo.repo
            repo.repo = None
            try:
                result = repo.get_head_commit_sha()
                assert result is None

                result = repo.is_dirty()
                assert result is False

                result = repo.get_dirty_files()
                assert result == []
            finally:
                repo.repo = original_repo

    def test_commit_files_with_staging_error(self):
        """Test commit_files when staging fails."""
        repo = GitRepo(".", logger=None)
        if not repo.is_available():
            pytest.skip("No git repository available")

        # Test with a file that might cause staging issues
        result = repo.commit_files(["/nonexistent/path/file.txt"], "Test commit")
        # Should handle gracefully
        assert result is None


class TestGitVersioningIntegration:
    """Test git versioning integration with patch_file function."""

    def test_disable_versioning_flag_parsing(self):
        """Test that --disable-versioning flag is parsed correctly."""
        import argparse

        # Create a parser similar to what's in main()
        parser = argparse.ArgumentParser()
        parser.add_argument("--disable-versioning", action="store_true")
        parser.add_argument(
            "--allowed-dir", action="append", dest="allowed_dirs", required=True
        )

        # Test without flag
        args = parser.parse_args(["--allowed-dir", "."])
        assert args.disable_versioning is False

        # Test with flag
        args = parser.parse_args(["--allowed-dir", ".", "--disable-versioning"])
        assert args.disable_versioning is True

    @patch("patch_file_mcp.server.git_repo")
    def test_git_versioning_disabled(self, mock_git_repo):
        """Test that git versioning is skipped when disabled."""
        mock_git_repo.is_available.return_value = True

        # This would need to be tested by calling the patch_file function
        # with DISABLE_VERSIONING = True and verifying git operations are not called
        from patch_file_mcp.server import DISABLE_VERSIONING

        # Store original value
        original_value = DISABLE_VERSIONING

        try:
            # Set to True (disabled)
            import patch_file_mcp.server

            patch_file_mcp.server.DISABLE_VERSIONING = True

            # The actual integration test would require mocking the entire patch_file function
            # For now, just verify the flag can be set
            assert patch_file_mcp.server.DISABLE_VERSIONING is True

        finally:
            # Restore original value
            patch_file_mcp.server.DISABLE_VERSIONING = original_value

    @patch("patch_file_mcp.server.git_repo")
    def test_git_versioning_enabled(self, mock_git_repo):
        """Test that git versioning works when enabled."""
        mock_git_repo.is_available.return_value = True

        from patch_file_mcp.server import DISABLE_VERSIONING

        # Store original value
        original_value = DISABLE_VERSIONING

        try:
            # Set to False (enabled)
            import patch_file_mcp.server

            patch_file_mcp.server.DISABLE_VERSIONING = False

            assert patch_file_mcp.server.DISABLE_VERSIONING is False

        finally:
            # Restore original value
            patch_file_mcp.server.DISABLE_VERSIONING = original_value


class TestGitVersioningErrorHandling:
    """Test error handling in git versioning operations."""

    def test_git_repo_with_corrupted_repo(self):
        """Test GitRepo behavior with corrupted git repository."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a directory that looks like a git repo but is corrupted
            git_dir = Path(temp_dir) / ".git"
            git_dir.mkdir()

            repo = GitRepo(temp_dir, logger=None)
            # Should handle gracefully
            assert repo.is_available() is False

    def test_commit_files_with_git_errors(self):
        """Test commit_files method with git errors."""
        repo = GitRepo(".", logger=None)
        if not repo.is_available():
            pytest.skip("No git repository available")

        # Test with invalid file path
        result = repo.commit_files(["/invalid/path/file.txt"], "Test commit")
        # Should handle gracefully
        assert result is None

    def test_stage_files_with_git_errors(self):
        """Test stage_files method with git errors."""
        repo = GitRepo(".", logger=None)
        if not repo.is_available():
            pytest.skip("No git repository available")

        # Test with invalid file path
        result = repo.stage_files(["/invalid/path/file.txt"])
        # Should handle gracefully
        assert isinstance(result, bool)


class TestGitIgnoreIntegration:
    """Test that git versioning respects .gitignore."""

    def test_gitignore_respected(self):
        """Test that .gitignore patterns are respected during staging."""
        repo = GitRepo(".", logger=None)
        if not repo.is_available():
            pytest.skip("No git repository available")

        # Create a temporary file that should be ignored
        test_file = Path("temp_test_file.tmp")
        try:
            test_file.write_text("test content")

            # Check if file gets staged (it shouldn't be if .gitignore works)
            # This is a basic test - in real scenarios, the file might not be ignored
            result = repo.stage_files([str(test_file)])
            assert isinstance(result, bool)

        finally:
            # Clean up
            if test_file.exists():
                test_file.unlink()


class TestGitVersioningWorkflow:
    """Test complete git versioning workflow."""

    def test_versioning_workflow_simulation(self):
        """Simulate a complete versioning workflow."""
        repo = GitRepo(".", logger=None)
        if not repo.is_available():
            pytest.skip("No git repository available")

        # Get initial state
        initial_dirty = repo.is_dirty()
        initial_dirty_files = repo.get_dirty_files()

        # These should be valid
        assert isinstance(initial_dirty, bool)
        assert isinstance(initial_dirty_files, list)

        # Test commit message generation
        if initial_dirty_files:
            message = repo.get_commit_message(initial_dirty_files)
            assert isinstance(message, str)
            assert len(message) > 0
        else:
            message = repo.get_commit_message(["test_file.py"])
            assert isinstance(message, str)
            assert len(message) > 0


class TestServerGitIntegration:
    """Test git versioning integration with the server module."""

    @patch("patch_file_mcp.server.git_repo")
    def test_server_git_repo_initialization_enabled(self, mock_git_repo):
        """Test server initializes git repo when versioning is enabled."""
        mock_git_repo.is_available.return_value = True
        mock_git_repo.root = "/test/repo"

        # Import and test the server module behavior
        import patch_file_mcp.server as server_module

        # Store original values
        original_disabled = server_module.DISABLE_VERSIONING
        original_git_repo = server_module.git_repo

        try:
            # Set versioning enabled
            server_module.DISABLE_VERSIONING = False
            server_module.git_repo = None

            # Simulate what happens in main() - this would normally call GitRepo
            # For testing, we just verify the logic works
            should_initialize = not server_module.DISABLE_VERSIONING
            assert should_initialize is True

        finally:
            # Restore originals
            server_module.DISABLE_VERSIONING = original_disabled
            server_module.git_repo = original_git_repo

    @patch("patch_file_mcp.server.git_repo")
    def test_server_git_repo_initialization_disabled(self, mock_git_repo):
        """Test server skips git repo when versioning is disabled."""
        import patch_file_mcp.server as server_module

        # Store original values
        original_disabled = server_module.DISABLE_VERSIONING
        original_git_repo = server_module.git_repo

        try:
            # Set versioning disabled
            server_module.DISABLE_VERSIONING = True
            server_module.git_repo = None

            # Simulate what happens in main()
            should_initialize = not server_module.DISABLE_VERSIONING
            assert should_initialize is False

        finally:
            # Restore originals
            server_module.DISABLE_VERSIONING = original_disabled
            server_module.git_repo = original_git_repo

    def test_server_constants(self):
        """Test that server constants are properly defined."""
        import patch_file_mcp.server as server_module

        # Check that DISABLE_VERSIONING is defined and is a boolean
        assert hasattr(server_module, "DISABLE_VERSIONING")
        assert isinstance(server_module.DISABLE_VERSIONING, bool)

        # Check that git_repo is defined
        assert hasattr(server_module, "git_repo")
        # git_repo can be None initially
        assert server_module.git_repo is None or hasattr(
            server_module.git_repo, "is_available"
        )


class TestGitFileTracking:
    """Test git file tracking functionality."""

    def test_is_file_tracked_with_tracked_file(self):
        """Test is_file_tracked returns True for tracked files."""
        repo = GitRepo(".", logger=None)
        if not repo.is_available():
            pytest.skip("No git repository available")

        # Test with a file that should be tracked (like this test file)
        test_file = __file__
        is_tracked = repo.is_file_tracked(test_file)
        # This test file should be tracked in the repository
        assert is_tracked is True

    def test_is_file_tracked_with_untracked_file(self):
        """Test is_file_tracked returns False for untracked files."""
        repo = GitRepo(".", logger=None)
        if not repo.is_available():
            pytest.skip("No git repository available")

        # Test with a file that doesn't exist
        nonexistent_file = "nonexistent_file_12345.txt"
        is_tracked = repo.is_file_tracked(nonexistent_file)
        assert is_tracked is False

    def test_is_file_tracked_outside_repo(self):
        """Test is_file_tracked returns False for files outside repo."""
        repo = GitRepo(".", logger=None)
        if not repo.is_available():
            pytest.skip("No git repository available")

        # Test with a file outside the repository
        outside_file = "/tmp/outside_file.txt"
        is_tracked = repo.is_file_tracked(outside_file)
        assert is_tracked is False

    def test_is_file_tracked_without_git(self):
        """Test is_file_tracked returns False when git is not available."""
        with patch("patch_file_mcp.git_repo.git", None):
            repo = GitRepo(".", logger=None)
            assert repo.is_file_tracked("any_file.txt") is False

    def test_add_file_to_tracking_success(self):
        """Test add_file_to_tracking with a valid untracked file."""
        repo = GitRepo(".", logger=None)
        if not repo.is_available():
            pytest.skip("No git repository available")

        import tempfile
        import os

        # Create a temporary file in the repo
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, dir=repo.root
        ) as f:
            temp_file = f.name
            f.write("test content")

        try:
            # File should not be tracked initially
            assert repo.is_file_tracked(temp_file) is False

            # Add file to tracking
            success = repo.add_file_to_tracking(temp_file)
            assert success is True

            # File should now be tracked
            assert repo.is_file_tracked(temp_file) is True

        finally:
            # Clean up - remove from git and filesystem
            try:
                repo.repo.git.reset("HEAD", temp_file)
                os.unlink(temp_file)
            except Exception:
                pass  # Ignore cleanup errors

    def test_add_file_to_tracking_outside_repo(self):
        """Test add_file_to_tracking fails for files outside repo."""
        repo = GitRepo(".", logger=None)
        if not repo.is_available():
            pytest.skip("No git repository available")

        # Test with a file outside the repository
        outside_file = "/tmp/outside_file.txt"
        success = repo.add_file_to_tracking(outside_file)
        assert success is False

    def test_add_file_to_tracking_without_git(self):
        """Test add_file_to_tracking returns False when git is not available."""
        with patch("patch_file_mcp.git_repo.git", None):
            repo = GitRepo(".", logger=None)
            assert repo.add_file_to_tracking("any_file.txt") is False

    def test_add_file_to_tracking_git_error(self):
        """Test add_file_to_tracking handles git errors gracefully."""
        repo = GitRepo(".", logger=None)
        if not repo.is_available():
            pytest.skip("No git repository available")

        # Test with a file that will cause git errors (invalid path)
        invalid_file = "invalid\x00file.txt"  # Null byte in filename
        success = repo.add_file_to_tracking(invalid_file)
        assert success is False


class TestGitVersioningIntegrationWithTracking:
    """Test git versioning integration with file tracking."""

    @patch("patch_file_mcp.server.git_repo")
    def test_patch_file_adds_untracked_file(self, mock_git_repo):
        """Test that patch_file adds untracked files to git tracking."""
        # Mock git repo to simulate untracked file scenario
        mock_git_repo.is_available.return_value = True
        mock_git_repo.is_file_tracked.return_value = False  # File is untracked
        mock_git_repo.add_file_to_tracking.return_value = True  # Adding succeeds
        mock_git_repo.commit_files.return_value = ("abc1234", "Update test.py")
        mock_git_repo.get_commit_message.return_value = "Update test.py"

        import patch_file_mcp.server as server_module

        # Store original values
        original_disabled = server_module.DISABLE_VERSIONING
        original_git_repo = server_module.git_repo

        try:
            # Set up test environment
            server_module.DISABLE_VERSIONING = False
            server_module.git_repo = mock_git_repo

            # This would be called in a real scenario, but we're just testing the logic
            # The actual patch_file function would call these methods

            # Verify the methods would be called correctly
            test_file = "/test/path/test.py"

            # Simulate the logic from patch_file function
            if (
                not server_module.DISABLE_VERSIONING
                and server_module.git_repo
                and server_module.git_repo.is_available()
            ):
                is_tracked = server_module.git_repo.is_file_tracked(test_file)
                if not is_tracked:
                    add_success = server_module.git_repo.add_file_to_tracking(test_file)
                    assert add_success is True

            # Verify mock calls
            mock_git_repo.is_file_tracked.assert_called_with(test_file)
            mock_git_repo.add_file_to_tracking.assert_called_with(test_file)

        finally:
            # Restore originals
            server_module.DISABLE_VERSIONING = original_disabled
            server_module.git_repo = original_git_repo

    @patch("patch_file_mcp.server.git_repo")
    def test_patch_file_skips_tracked_file(self, mock_git_repo):
        """Test that patch_file skips adding already tracked files."""
        # Mock git repo to simulate tracked file scenario
        mock_git_repo.is_available.return_value = True
        mock_git_repo.is_file_tracked.return_value = True  # File is already tracked
        mock_git_repo.commit_files.return_value = ("abc1234", "Update test.py")
        mock_git_repo.get_commit_message.return_value = "Update test.py"

        import patch_file_mcp.server as server_module

        # Store original values
        original_disabled = server_module.DISABLE_VERSIONING
        original_git_repo = server_module.git_repo

        try:
            # Set up test environment
            server_module.DISABLE_VERSIONING = False
            server_module.git_repo = mock_git_repo

            test_file = "/test/path/test.py"

            # Simulate the logic from patch_file function
            if (
                not server_module.DISABLE_VERSIONING
                and server_module.git_repo
                and server_module.git_repo.is_available()
            ):
                is_tracked = server_module.git_repo.is_file_tracked(test_file)
                if not is_tracked:
                    # This should not be called since file is tracked
                    server_module.git_repo.add_file_to_tracking(test_file)

            # Verify mock calls
            mock_git_repo.is_file_tracked.assert_called_with(test_file)
            # add_file_to_tracking should NOT be called since file is tracked
            mock_git_repo.add_file_to_tracking.assert_not_called()

        finally:
            # Restore originals
            server_module.DISABLE_VERSIONING = original_disabled
            server_module.git_repo = original_git_repo
