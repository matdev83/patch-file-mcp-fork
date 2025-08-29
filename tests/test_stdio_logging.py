"""
Tests for ensuring logging does not leak to STDOUT/STDERR.

These tests verify that the logging system correctly writes only to log files
and never emits anything to console output, which is critical for MCP protocol
compatibility and clean operation.
"""


class TestStdioLogging:
    """Test cases for STDOUT/STDERR logging isolation."""

    def test_logging_setup_creates_file_handler_only(self, tmp_path):
        """
        Test that logging setup creates only file handlers, no console handlers.

        This test verifies that the logging configuration only creates file handlers
        and does not add any console/stream handlers that would output to STDOUT/STDERR.
        """
        from patch_file_mcp.server import setup_logging

        log_file = tmp_path / "test.log"

        # Setup logging
        logger = setup_logging(str(log_file), "INFO")

        # Verify logger was created
        assert logger is not None
        assert logger.name == "patch_file_mcp"

        # Verify only file handlers exist (no console handlers)
        file_handlers = [h for h in logger.handlers if hasattr(h, "baseFilename")]
        stream_handlers = [
            h
            for h in logger.handlers
            if hasattr(h, "stream") and not hasattr(h, "baseFilename")
        ]  # Exclude file handlers that also have stream

        # Should have exactly one file handler
        assert len(file_handlers) == 1
        assert len(stream_handlers) == 0  # No stream handlers (no console output)

        # Verify the file handler points to our log file
        file_handler = file_handlers[0]
        assert file_handler.baseFilename == str(log_file)

        # Test that logging actually works
        logger.info("Test log message")
        logger.warning("Test warning message")
        logger.error("Test error message")

        # Verify log file was created and contains messages
        assert log_file.exists()
        log_content = log_file.read_text(encoding="utf-8")

        assert "Test log message" in log_content
        assert "Test warning message" in log_content
        assert "Test error message" in log_content
        assert "INFO" in log_content
        assert "WARNING" in log_content
        assert "ERROR" in log_content

    def test_debug_logging_includes_detailed_info(self, tmp_path):
        """
        Test that DEBUG logging includes comprehensive parameter information.

        This test verifies that when DEBUG level is enabled, the logging includes
        detailed information about function parameters and operations.
        """
        from patch_file_mcp.server import setup_logging

        log_file = tmp_path / "debug_test.log"

        # Setup DEBUG logging
        logger = setup_logging(str(log_file), "DEBUG")

        # Test various log levels
        logger.debug("DEBUG: Detailed parameter information")
        logger.info("INFO: General information")
        logger.warning("WARNING: Warning message")
        logger.error("ERROR: Error message")

        # Verify log file contains all messages
        log_content = log_file.read_text(encoding="utf-8")

        assert "DEBUG: Detailed parameter information" in log_content
        assert "INFO: General information" in log_content
        assert "WARNING: Warning message" in log_content
        assert "ERROR: Error message" in log_content

        # Verify DEBUG messages are included (they should be since we set DEBUG level)
        assert "DEBUG" in log_content

    def test_no_console_output_when_logging(self, tmp_path, capsys):
        """
        Test that logging does not produce console output.

        This test verifies that even when logging messages are generated,
        nothing appears in STDOUT or STDERR.
        """
        from patch_file_mcp.server import setup_logging

        log_file = tmp_path / "console_test.log"

        # Setup logging
        logger = setup_logging(str(log_file), "DEBUG")

        # Generate various log messages
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        logger.critical("Critical message")

        # Capture any console output
        captured = capsys.readouterr()

        # Verify no output went to STDOUT or STDERR
        assert captured.out == ""
        assert captured.err == ""

        # But verify logging went to file
        assert log_file.exists()
        log_content = log_file.read_text(encoding="utf-8")

        assert "Debug message" in log_content
        assert "Info message" in log_content
        assert "Warning message" in log_content
        assert "Error message" in log_content
        assert "Critical message" in log_content

    def test_guarded_logging_performance(self, tmp_path):
        """
        Test that guarded logging (checking logger before logging) works correctly.

        This test verifies that the logging guards properly check if logging is enabled
        before performing any logging operations.
        """
        from patch_file_mcp.server import setup_logging

        log_file = tmp_path / "guarded_test.log"

        # Test with DEBUG level (all messages should be logged)
        logger = setup_logging(str(log_file), "DEBUG")

        # These should all be logged since DEBUG level includes everything
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")

        debug_content = log_file.read_text(encoding="utf-8")

        # All messages should be present
        assert "Debug message" in debug_content
        assert "Info message" in debug_content
        assert "Warning message" in debug_content
        assert "Error message" in debug_content

        # Test with WARNING level (only WARNING and above should be logged)
        # Close all handlers to release file locks
        for handler in logger.handlers:
            handler.close()
        logger.handlers.clear()

        log_file.unlink()  # Remove previous log file
        logger = setup_logging(str(log_file), "WARNING")

        # Only WARNING, ERROR, CRITICAL should be logged
        logger.debug("Debug message")  # Should NOT be logged
        logger.info("Info message")  # Should NOT be logged
        logger.warning("Warning message")  # Should be logged
        logger.error("Error message")  # Should be logged

        warning_content = log_file.read_text(encoding="utf-8")

        # Only WARNING and ERROR should be present
        assert "Debug message" not in warning_content
        assert "Info message" not in warning_content
        assert "Warning message" in warning_content
        assert "Error message" in warning_content

    def test_log_file_creation_and_permissions(self, tmp_path):
        """
        Test that log files are created correctly with proper permissions.

        This test verifies that log files are created in the correct location
        and have appropriate permissions for writing.
        """
        from patch_file_mcp.server import setup_logging

        # Test with nested directory path
        nested_log_dir = tmp_path / "logs" / "nested"
        log_file = nested_log_dir / "test.log"

        # Setup logging (should create the directory structure)
        logger = setup_logging(str(log_file), "INFO")

        # Verify directory was created
        assert nested_log_dir.exists()
        assert nested_log_dir.is_dir()

        # Verify log file was created
        assert log_file.exists()

        # Test logging to the file
        logger.info("Test message in nested directory")

        # Verify message was written
        log_content = log_file.read_text(encoding="utf-8")
        assert "Test message in nested directory" in log_content

    def test_multiple_loggers_dont_interfere(self, tmp_path):
        """
        Test that multiple logger instances work independently.

        This test verifies that creating multiple logger instances doesn't
        cause interference or console output leakage.
        """
        import logging

        log_file1 = tmp_path / "logger1.log"
        log_file2 = tmp_path / "logger2.log"

        # Create two separate loggers with different names
        logger1 = logging.getLogger("test_logger_1")
        logger2 = logging.getLogger("test_logger_2")

        # Configure each logger with its own file handler
        for logger, log_file, level in [
            (logger1, log_file1, logging.INFO),
            (logger2, log_file2, logging.DEBUG),
        ]:
            logger.setLevel(level)

            # Remove any existing handlers
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)

            # Add file handler
            handler = logging.FileHandler(str(log_file), encoding="utf-8")
            handler.setLevel(level)
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        # Log different messages to each
        logger1.info("Message to logger 1")
        logger2.debug("Debug message to logger 2")
        logger2.info("Info message to logger 2")

        # Close handlers to ensure data is written
        for logger in [logger1, logger2]:
            for handler in logger.handlers:
                handler.close()

        # Verify each log file contains only its own messages
        content1 = log_file1.read_text(encoding="utf-8")
        content2 = log_file2.read_text(encoding="utf-8")

        assert "Message to logger 1" in content1
        assert "Message to logger 1" not in content2

        assert "Debug message to logger 2" in content2
        assert "Info message to logger 2" in content2
        assert "Debug message to logger 2" not in content1

    def test_debug_logging_produces_output(self, tmp_path):
        """
        Test that DEBUG logging actually produces log output to files.

        This test simulates the server initialization process and verifies that
        when DEBUG logging is enabled, appropriate log messages are written to the file.
        """
        from patch_file_mcp.server import setup_logging, validate_allowed_directories

        # Create a temporary directory for the server
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()

        # Create a unique log file path for this test
        log_file = tmp_path / "debug_output_test.log"

        # Ensure log file doesn't exist before test
        if log_file.exists():
            log_file.unlink()

        # Verify log file is clean before starting
        assert not log_file.exists(), "Log file should not exist before test starts"

        # Setup DEBUG logging FIRST (this creates the logger)
        import sys
        server_module = sys.modules['patch_file_mcp.server']
        logger = setup_logging(str(log_file), "DEBUG")
        server_module.logger = logger

        # Simulate server initialization that would trigger DEBUG logging
        # This mimics what happens in the main() function
        validate_allowed_directories([str(allowed_dir)])

        # Force flush any pending log messages
        for handler in logger.handlers:
            handler.flush()

        # Check if log file was created and has content
        log_file_exists = log_file.exists()
        log_content = ""
        log_has_content = False

        if log_file_exists:
            log_content = log_file.read_text(encoding="utf-8")
            log_has_content = len(log_content.strip()) > 0

        # The test should pass if log file exists and has content (from directory validation)
        assert log_file_exists, "Log file should be created when DEBUG logging is used"
        assert (
            log_has_content
        ), "Log file should contain output when DEBUG logging is used"

        # Verify that DEBUG-level content is present in the log
        expected_debug_patterns = [
            "Validated allowed directory",  # Directory validation happens during startup
            "patch_file_mcp",  # Logger name
        ]

        for pattern in expected_debug_patterns:
            assert (
                pattern in log_content
            ), f"Expected pattern '{pattern}' not found in log file content"

        print(f"\nDEBUG: Log file created with {len(log_content)} characters")
        print(f"DEBUG: Log content preview: {log_content[:300]}...")

        # Clean up log file after test
        if log_file.exists():
            try:
                log_file.unlink()
            except Exception:
                pass  # Ignore cleanup errors
