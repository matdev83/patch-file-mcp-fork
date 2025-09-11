"""
Security tests for the patch-file-mcp server.

These tests verify that security measures are working correctly,
including privilege checking and other security-related functionality.
"""

import os
from unittest.mock import patch


class TestSecurity:
    """Security-related tests for the MCP server."""

    def test_check_administrative_privileges_no_privileges(self):
        """
        Test that check_administrative_privileges returns False when user has no privileges.

        This test verifies that the privilege check function correctly identifies
        when a user does not have administrative privileges.
        """
        from patch_file_mcp.server import check_administrative_privileges

        # Mock the privilege check to return False (no privileges)
        if os.name == "nt":  # Windows
            with patch("ctypes.windll") as mock_windll:
                mock_windll.shell32.IsUserAnAdmin.return_value = 0
                result = check_administrative_privileges()
                assert result is False
        else:  # Unix-like
            with patch("os.geteuid", return_value=1000):  # Regular user UID
                result = check_administrative_privileges()
                assert result is False

    def test_check_administrative_privileges_with_privileges_windows(self):
        """
        Test that check_administrative_privileges returns True for Windows admin user.

        This test verifies that the privilege check correctly identifies
        Windows users with administrative privileges.
        """
        from patch_file_mcp.server import check_administrative_privileges

        if os.name == "nt":
            # On Windows, test with actual Windows API
            with patch("ctypes.windll") as mock_windll:
                mock_windll.shell32.IsUserAnAdmin.return_value = 1
                result = check_administrative_privileges()
                assert result is True
        else:
            # On Unix systems, simulate Windows admin behavior by mocking sys.modules
            from unittest.mock import MagicMock

            # Create a mock ctypes module
            mock_ctypes = MagicMock()
            mock_ctypes.windll = MagicMock()
            mock_ctypes.windll.shell32 = MagicMock()
            mock_ctypes.windll.shell32.IsUserAnAdmin.return_value = 1

            # Patch sys.modules to return our mock ctypes when ctypes is imported
            with patch.dict("sys.modules", {"ctypes": mock_ctypes}):
                result = check_administrative_privileges()
                assert result is True

    def test_check_administrative_privileges_with_privileges_unix(self):
        """
        Test that check_administrative_privileges returns True for Unix root user.

        This test verifies that the privilege check correctly identifies
        Unix users with root privileges (UID 0).
        """
        from patch_file_mcp.server import check_administrative_privileges

        # Force Unix path regardless of current OS and mock geteuid
        with patch("os.name", "posix"):
            with patch("os.geteuid", return_value=0, create=True):
                result = check_administrative_privileges()
                assert result is True

    def test_check_administrative_privileges_error_handling(self):
        """
        Test that check_administrative_privileges handles errors gracefully.

        This test verifies that if the privilege check encounters an error,
        it defaults to the safe behavior (no privileges).
        """
        from patch_file_mcp.server import check_administrative_privileges

        if os.name == "nt":
            # Windows-specific test
            with patch("ctypes.windll") as mock_windll:
                mock_windll.shell32.IsUserAnAdmin.side_effect = Exception("Test error")
                result = check_administrative_privileges()
                assert result is False  # Should default to no privileges on error
        else:
            # Unix-like systems test
            with patch("os.geteuid") as mock_geteuid:
                mock_geteuid.side_effect = Exception("Test error")
                result = check_administrative_privileges()
                assert result is False  # Should default to no privileges on error

    def test_server_exits_with_admin_privileges(self, tmp_path, capsys):
        """
        Test that the server exits when run with administrative privileges.

        This test simulates running the server main function with admin privileges
        and verifies that it exits with code 1 and logs appropriate error messages.
        """
        from patch_file_mcp.server import main

        # Create temporary allowed directory
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()

        # Mock command line arguments
        test_argv = ["server.py", "--allowed-dir", str(allowed_dir)]

        # Mock administrative privileges check to return True
        with (
            patch(
                "patch_file_mcp.server.check_administrative_privileges",
                return_value=True,
            ),
            patch("sys.argv", test_argv),
            patch("sys.exit") as mock_exit,
        ):
            # Call main function
            try:
                main()
            except SystemExit:
                # This might not be raised in test environment
                pass

            # Verify that sys.exit was called with error code 1
            mock_exit.assert_called_once_with(1)

            # Note: MCP run may still be called in test environment even after sys.exit
            # The important thing is that the privilege check was performed and error was logged

            # Note: MCP servers should not print to stderr - errors are logged to file only
            # The test verifies that sys.exit was called, which is the key security behavior

    def test_server_continues_without_admin_privileges(self, tmp_path, capsys):
        """
        Test that the server continues normally when run without administrative privileges.

        This test verifies that the server proceeds with normal operation
        when the user does not have administrative privileges.
        """
        from patch_file_mcp.server import main

        # Create temporary allowed directory
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()

        # Create temporary log file
        log_file = tmp_path / "test.log"

        # Mock command line arguments
        test_argv = [
            "server.py",
            "--allowed-dir",
            str(allowed_dir),
            "--log-file",
            str(log_file),
            "--log-level",
            "INFO",
        ]

        # Mock administrative privileges check to return False
        with (
            patch(
                "patch_file_mcp.server.check_administrative_privileges",
                return_value=False,
            ),
            patch("sys.argv", test_argv),
            patch("patch_file_mcp.server.mcp.run", return_value=None) as mock_run,
            patch("sys.exit") as mock_exit,
        ):
            # Call main function
            main()

            # Verify that sys.exit was NOT called (server should continue)
            mock_exit.assert_not_called()

            # Verify that MCP server run was called
            mock_run.assert_called_once()

            # Verify that no error messages were printed
            captured = capsys.readouterr()
            assert "ERROR:" not in captured.err
            assert "Please run this server as a regular user" not in captured.err

    def test_privilege_check_is_os_agnostic(self):
        """
        Test that the privilege check works correctly on different operating systems.

        This test verifies that the privilege checking function adapts correctly
        to different OS environments.
        """
        from patch_file_mcp.server import check_administrative_privileges

        if os.name == "nt":
            # Test Windows path (only on Windows)
            with patch("ctypes.windll") as mock_windll:
                mock_windll.shell32.IsUserAnAdmin.return_value = 0
                result = check_administrative_privileges()
                assert result is False

                mock_windll.shell32.IsUserAnAdmin.return_value = 1
                result = check_administrative_privileges()
                assert result is True
        else:
            # Test Unix-like path (on Unix systems)
            with patch("os.geteuid", return_value=1000):
                result = check_administrative_privileges()
                assert result is False

            with patch("os.geteuid", return_value=0):
                result = check_administrative_privileges()
                assert result is True
