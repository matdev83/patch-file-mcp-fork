#! /usr/bin/env python3
import sys
import argparse
import subprocess
import os
import time
import logging
from pathlib import Path
import re
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import difflib

from fastmcp import FastMCP
from pydantic.fields import Field


def setup_logging(log_file_path: str, log_level: str) -> logging.Logger:
    """
    Setup logging configuration for the application.

    Args:
        log_file_path: Path to the log file
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Configured logger instance
    """
    # Create logs directory if it doesn't exist
    log_dir = Path(log_file_path).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    # Convert string level to logging level
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    numeric_level = level_map.get(log_level.upper(), logging.INFO)

    # Configure logger
    logger = logging.getLogger("patch_file_mcp")
    logger.setLevel(numeric_level)

    # Remove any existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create file handler (no console handler to avoid STDOUT/STDERR output)
    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setLevel(numeric_level)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
    )
    file_handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(file_handler)

    return logger


mcp = FastMCP(
    name="Patch File MCP",
    instructions="""
Patch existing files using a simple block format. Use absolute file paths.

Block format (multiple blocks allowed):
```
<<<<<<< SEARCH
Text to find in the file
=======
Text to replace it with
>>>>>>> REPLACE
```

Rules:
- Provide absolute paths only (e.g., C:/proj/file.py or /home/user/file.py).
- Each SEARCH text must match exactly once; otherwise the tool errors.
- If the file is a Python file, you will also receive a brief linter/formatter/type-check summary in addition to the patch result.
""",
)

allowed_directories = []
logger = None  # Global logger instance

# QA execution limits and toggles
QA_CMD_TIMEOUT = int(os.getenv("PATCH_MCP_QA_CMD_TIMEOUT", "15"))  # per-tool seconds
QA_WALL_TIME = int(os.getenv("PATCH_MCP_QA_WALL_TIME", "20"))  # total QA time
QA_MAX_ITERATIONS = int(os.getenv("PATCH_MCP_QA_MAX_ITERATIONS", "4"))

# QA feature flags (set via CLI)
SKIP_RUFF = False
SKIP_BLACK = False
SKIP_MYPY = False
SKIP_MYPY_ON_TESTS = True

# Failed edit tracking data structures
FAILED_EDITS_HISTORY: Dict[str, List[Dict]] = {}  # filename -> list of failed attempts
TOOL_CALL_COUNTER = 0  # Counter for tool calls to trigger garbage collection
MYPY_FAILURE_COUNTS: Dict[str, int] = {}  # filename -> consecutive mypy failure count


def create_patch_params_hash(file_path: str, patch_content: str) -> str:
    """
    Create a hash of patch parameters to uniquely identify similar failed attempts.

    Args:
        file_path: The file path being patched
        patch_content: The patch content

    Returns:
        SHA256 hash of the parameters
    """
    params_str = f"{file_path}|{patch_content}"
    return hashlib.sha256(params_str.encode("utf-8")).hexdigest()


def track_failed_edit(
    file_path: str, patch_content: str, failure_stage: str, error_message: str
) -> None:
    """
    Track a failed file edit attempt.

    Args:
        file_path: The file path that failed to be patched
        patch_content: The patch content that failed
        failure_stage: The stage where the failure occurred
        error_message: The error message from the failure
    """
    if file_path not in FAILED_EDITS_HISTORY:
        FAILED_EDITS_HISTORY[file_path] = []

    # Parse the patch content to count blocks
    try:
        blocks = parse_search_replace_blocks(patch_content)
        block_count = len(blocks)
    except Exception:
        # If parsing fails, we still track it but with 0 blocks
        block_count = 0

    # Create parameter hash for tracking similar attempts
    params_hash = create_patch_params_hash(file_path, patch_content)

    failed_attempt = {
        "datetime": datetime.now(),
        "filename": file_path,
        "block_count": block_count,
        "failure_stage": failure_stage,
        "error_message": error_message,
        "params_hash": params_hash,
    }

    FAILED_EDITS_HISTORY[file_path].append(failed_attempt)

    # Keep only the last 10 attempts per file to prevent memory bloat
    if len(FAILED_EDITS_HISTORY[file_path]) > 10:
        FAILED_EDITS_HISTORY[file_path] = FAILED_EDITS_HISTORY[file_path][-10:]

    if logger:
        logger.debug(
            f"Tracked failed edit attempt: {file_path} | stage: {failure_stage} | blocks: {block_count}"
        )


def clear_failed_edit_history(file_path: str) -> None:
    """
    Clear the failed edit history for a file after successful patching.

    Args:
        file_path: The file path to clear history for
    """
    if file_path in FAILED_EDITS_HISTORY:
        if logger:
            logger.debug(
                f"Clearing failed edit history for {file_path} (was {len(FAILED_EDITS_HISTORY[file_path])} attempts)"
            )
        FAILED_EDITS_HISTORY.pop(file_path, None)


def garbage_collect_failed_edit_history() -> None:
    """
    Perform garbage collection on failed edit history.
    Remove entries that are older than 1 hour.
    """
    current_time = datetime.now()
    one_hour_ago = current_time - timedelta(hours=1)

    files_to_remove = []
    total_entries_before = sum(
        len(entries) for entries in FAILED_EDITS_HISTORY.values()
    )

    for file_path, attempts in FAILED_EDITS_HISTORY.items():
        # Keep only attempts from the last hour
        recent_attempts = [
            attempt for attempt in attempts if attempt["datetime"] >= one_hour_ago
        ]

        if not recent_attempts:
            # No recent attempts, remove entire file entry
            files_to_remove.append(file_path)
        else:
            # Update with only recent attempts
            FAILED_EDITS_HISTORY[file_path] = recent_attempts

    # Remove files with no recent attempts
    for file_path in files_to_remove:
        FAILED_EDITS_HISTORY.pop(file_path, None)
        # Also clean up mypy failure counts for these files
        MYPY_FAILURE_COUNTS.pop(file_path, None)

    total_entries_after = sum(len(entries) for entries in FAILED_EDITS_HISTORY.values())

    if logger and total_entries_before != total_entries_after:
        logger.debug(
            f"Garbage collection: removed {total_entries_before - total_entries_after} old entries, {len(files_to_remove)} files completely"
        )


def should_suppress_mypy_info(file_path: str) -> bool:
    """
    Check if mypy information should be suppressed for the given file.

    Returns True if the file has had 3 or more consecutive mypy failures,
    meaning mypy info should be excluded from tool output to help agents focus
    on more important issues.

    Args:
        file_path: The file path to check

    Returns:
        bool: True if mypy info should be suppressed, False otherwise
    """
    return MYPY_FAILURE_COUNTS.get(file_path, 0) >= 3


def update_mypy_failure_count(file_path: str, mypy_passed: bool) -> None:
    """
    Update the mypy failure count for a file based on the mypy result.

    Args:
        file_path: The file path being processed
        mypy_passed: True if mypy passed, False if mypy failed
    """
    if mypy_passed:
        # Reset counter on successful mypy
        MYPY_FAILURE_COUNTS[file_path] = 0
    else:
        # Increment counter on mypy failure
        MYPY_FAILURE_COUNTS[file_path] = MYPY_FAILURE_COUNTS.get(file_path, 0) + 1


def get_failed_edit_info(file_path: str, patch_content: str) -> Optional[str]:
    """
    Get awareness message for failed edit attempts.

    Args:
        file_path: The file path being patched
        patch_content: The patch content

    Returns:
        Awareness message if applicable, None otherwise
    """
    if file_path not in FAILED_EDITS_HISTORY:
        return None

    failed_attempts = FAILED_EDITS_HISTORY[file_path]
    if not failed_attempts:
        return None

    # Count all failed attempts for this file
    total_failed_count = len(failed_attempts)

    # Parse current patch content to get block count
    try:
        blocks = parse_search_replace_blocks(patch_content)
        current_block_count = len(blocks)
    except Exception:
        current_block_count = 1  # Default to 1 if parsing fails

    # Format ordinal number correctly
    if total_failed_count == 2:
        ordinal = "2nd"
    elif total_failed_count == 3:
        ordinal = "3rd"
    else:
        ordinal = f"{total_failed_count}th"

    # Conditions as outlined:
    # After 2nd failed attempt: show basic message
    # After 3+ failed attempts AND multiple blocks: show additional splitting suggestion
    if total_failed_count >= 3 and current_block_count > 1:
        return f"This was your {ordinal} consecutive failed edit attempt of this file.\n\nIt looks you are having problems with providing multiple diffs in one tool call. Please consider splitting this edit into a few smaller ones."
    elif total_failed_count >= 2:
        return f"This was your {ordinal} consecutive failed edit attempt of this file."

    return None


def check_administrative_privileges():
    """
    Check if the current user has administrative/root privileges.

    Returns:
        bool: True if user has administrative privileges, False otherwise

    This function is OS-agnostic and works on Windows, Linux, and macOS.
    """
    try:
        if os.name == "nt":  # Windows
            import ctypes

            # Check if user is Administrator on Windows
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        else:  # Unix-like systems (Linux, macOS)
            # Check if effective user ID is 0 (root)
            return os.geteuid() == 0
    except Exception as e:
        # If privilege check fails, err on the side of caution
        if logger:
            logger.warning(f"Failed to check administrative privileges: {e}")
            logger.warning("Assuming no administrative privileges to continue safely")
        return False


def normalize_path(path_str):
    r"""
    Normalize and resolve a path string, handling cross-platform path separators and un-escaping.

    Handles various input formats:
    - Windows backslashes: C:\path\to\file
    - Escaped backslashes: C:\\path\\to\\file
    - Unix forward slashes: C:/path/to/file
    - Mixed separators: C:\path/to\file

    Args:
        path_str: Path string to normalize

    Returns:
        Resolved Path object
    """
    if not path_str:
        raise ValueError("Empty path provided")

    # Step 1: Handle escaped backslashes (\\ -> \)
    # Only decode unicode escapes if the string contains escaped sequences
    if "\\\\" in path_str:
        try:
            unescaped = path_str.encode().decode("unicode_escape")
        except UnicodeDecodeError:
            # If unicode_escape fails, use the original string
            unescaped = path_str
    else:
        unescaped = path_str

    # Step 2: Normalize path separators
    # Convert all separators to OS-native format
    if os.name == "nt":  # Windows
        # On Windows, ensure we use backslashes
        normalized = unescaped.replace("/", "\\")
    else:  # Unix-like systems
        # On Unix, ensure we use forward slashes
        normalized = unescaped.replace("\\", "/")

    # Step 3: Create Path object and resolve to absolute path
    try:
        path = Path(normalized).resolve()
    except (OSError, RuntimeError) as e:
        # Handle cases where path resolution fails
        raise ValueError(f"Invalid path '{path_str}': {e}")

    return path


def validate_directory_access(directory_path):
    """
    Validate that a directory exists and has read/write access.

    Args:
        directory_path: Path to the directory to validate

    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    try:
        # Check if path exists
        if not directory_path.exists():
            return False, f"Directory does not exist: {directory_path}"

        # Check if it's actually a directory
        if not directory_path.is_dir():
            return False, f"Path is not a directory: {directory_path}"

        # Check read access
        try:
            list(directory_path.iterdir())
        except (PermissionError, OSError) as e:
            return False, f"No read access to directory: {directory_path} ({e})"

        # Check write access by trying to create a temporary file
        test_file = directory_path / ".mcp_test_write_access"
        try:
            test_file.write_text("test")
            test_file.unlink()  # Clean up
        except (PermissionError, OSError) as e:
            return False, f"No write access to directory: {directory_path} ({e})"

        return True, None

    except Exception as e:
        return False, f"Error validating directory {directory_path}: {e}"


def validate_allowed_directories(directories):
    """
    Validate all allowed directories at server startup.

    Args:
        directories: List of directory path strings

    Exits the program with error if validation fails.
    """
    if not directories:
        if logger:
            logger.error(
                "No allowed directories specified. At least one --allowed-dir is required."
            )
        sys.exit(1)

    validated_dirs = []

    for dir_path_str in directories:
        try:
            # Normalize the path
            dir_path = normalize_path(dir_path_str)

            # Validate directory access
            is_valid, error_msg = validate_directory_access(dir_path)

            if not is_valid:
                if logger:
                    logger.error(error_msg)
                sys.exit(1)

            validated_dirs.append(str(dir_path))
            if logger:
                logger.info(f"Validated allowed directory: {dir_path}")

        except Exception as e:
            if logger:
                logger.error(f"Failed to process directory '{dir_path_str}': {e}")
            sys.exit(1)

    return validated_dirs


def is_file_in_allowed_directories(file_path, allowed_directories):
    """
    Check if a file path is within any of the allowed directories.

    Args:
        file_path: Path to the file to check
        allowed_directories: List of allowed directory paths

    Returns:
        tuple: (is_allowed: bool, matched_directory: str or None)
    """
    try:
        # Normalize the file path
        normalized_file_path = normalize_path(file_path)

        # Check against each allowed directory
        for allowed_dir in allowed_directories:
            allowed_path = Path(allowed_dir)

            # Check if the file is within this allowed directory (supports subdirectories)
            try:
                # Use relative path to check containment
                normalized_file_path.relative_to(allowed_path)
                return True, allowed_dir
            except ValueError:
                # Not within this directory, continue checking others
                continue

        return False, None

    except Exception as e:
        if logger:
            logger.error(f"Failed to validate file path '{file_path}': {e}")
        return False, None


def main():
    # Process command line arguments
    global allowed_directories
    parser = argparse.ArgumentParser(
        description="Patch File MCP server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Logging Options:
  --log-file PATH       Path to log file (default: logs/app.log)
  --log-level LEVEL     Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL (default: INFO)

Security Features:
  --allowed-dir DIR     Allowed base directory for project paths (required, can be used multiple times)

Examples:
  %(prog)s --allowed-dir /home/user/projects --allowed-dir /home/user/code
  %(prog)s --allowed-dir C:\\Projects --log-file custom.log --log-level DEBUG
        """,
    )
    parser.add_argument(
        "--allowed-dir",
        action="append",
        dest="allowed_dirs",
        required=True,
        help="Allowed base directory for project paths (can be used multiple times)",
    )
    parser.add_argument(
        "--log-file",
        default="logs/app.log",
        help="Path to log file (default: logs/app.log)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--no-ruff",
        action="store_true",
        help="Skip Ruff in the QA pipeline",
    )
    parser.add_argument(
        "--no-black",
        action="store_true",
        help="Skip Black in the QA pipeline",
    )
    parser.add_argument(
        "--no-mypy",
        action="store_true",
        help="Skip MyPy in the QA pipeline",
    )
    parser.add_argument(
        "--run-mypy-on-tests",
        action="store_true",
        help="Run MyPy even when the target file path contains 'tests' (overridden by --no-mypy)",
    )

    args = parser.parse_args()

    # Setup logging first
    global logger
    logger = setup_logging(args.log_file, args.log_level)

    # SECURITY CHECK: Ensure user does not have administrative privileges
    if check_administrative_privileges():
        logger.error("Server cannot run with administrative/root privileges")
        logger.error("This is a security measure to prevent potential system damage.")
        logger.error("Please run this server as a regular user.")
        sys.exit(1)

    logger.info("Starting Patch File MCP server")
    logger.info(f"Log file: {args.log_file}")
    logger.info(f"Log level: {args.log_level}")

    # Validate allowed directories at startup
    allowed_directories = validate_allowed_directories(args.allowed_dirs)

    # Apply QA flags
    global SKIP_RUFF, SKIP_BLACK, SKIP_MYPY, SKIP_MYPY_ON_TESTS
    SKIP_RUFF = bool(args.no_ruff)
    SKIP_BLACK = bool(args.no_black)
    SKIP_MYPY = bool(args.no_mypy)
    SKIP_MYPY_ON_TESTS = not bool(args.run_mypy_on_tests)

    logger.info(
        f"QA config: timeout={QA_CMD_TIMEOUT}s, wall={QA_WALL_TIME}s, iterations={QA_MAX_ITERATIONS}, "
        f"no_ruff={SKIP_RUFF}, no_black={SKIP_BLACK}, no_mypy={SKIP_MYPY}, skip_mypy_on_tests={SKIP_MYPY_ON_TESTS}"
    )

    logger.info(
        f"Server started successfully with {len(allowed_directories)} allowed directories"
    )
    for i, dir_path in enumerate(allowed_directories, 1):
        logger.info(f"Allowed directory {i}: {dir_path}")

    # Run the MCP server
    logger.info("Starting MCP server with stdio transport")
    mcp.run(transport="stdio")


#
# Tools
#


def validate_block_integrity(patch_content):
    """
    Validate the integrity of patch blocks before parsing.
    Checks for balanced markers and correct sequence.
    """
    # Check marker balance
    search_count = patch_content.count("<<<<<<< SEARCH")
    separator_count = patch_content.count("=======")
    replace_count = patch_content.count(">>>>>>> REPLACE")

    if not (search_count == separator_count == replace_count):
        raise ValueError(
            f"Malformed patch format: Unbalanced markers - "
            f"{search_count} SEARCH, {separator_count} separator, {replace_count} REPLACE markers"
        )

    # Check marker sequence
    markers = []
    for line in patch_content.splitlines():
        line = line.strip()
        if line in ["<<<<<<< SEARCH", "=======", ">>>>>>> REPLACE"]:
            markers.append(line)

    # Verify correct marker sequence (always SEARCH, SEPARATOR, REPLACE pattern)
    for i in range(0, len(markers), 3):
        if i + 2 < len(markers):
            if (
                markers[i] != "<<<<<<< SEARCH"
                or markers[i + 1] != "======="
                or markers[i + 2] != ">>>>>>> REPLACE"
            ):
                raise ValueError(
                    f"Malformed patch format: Incorrect marker sequence at position {i}: "
                    f"Expected [SEARCH, SEPARATOR, REPLACE], got {markers[i:i+3]}"
                )

    # Check for nested markers in each block
    sections = patch_content.split("<<<<<<< SEARCH")
    for i, section in enumerate(sections[1:], 1):  # Skip first empty section
        if "<<<<<<< SEARCH" in section and section.find(
            ">>>>>>> REPLACE"
        ) > section.find("<<<<<<< SEARCH"):
            raise ValueError(
                f"Malformed patch format: Nested SEARCH marker in block {i}"
            )


def parse_search_replace_blocks(patch_content):
    """
    Parse multiple search-replace blocks from the patch content.
    Returns a list of tuples (search_text, replace_text).
    """
    # Define the markers
    search_marker = "<<<<<<< SEARCH"
    separator = "======="
    replace_marker = ">>>>>>> REPLACE"

    # First validate patch integrity
    validate_block_integrity(patch_content)

    # Use regex to extract all blocks
    pattern = f"{search_marker}\\n(.*?)\\n{separator}\\n(.*?)\\n{replace_marker}"
    matches = re.findall(pattern, patch_content, re.DOTALL)

    if not matches:
        # Try alternative parsing if regex fails
        blocks = []
        lines = patch_content.splitlines()
        i = 0
        while i < len(lines):
            if lines[i] == search_marker:
                search_start = i + 1
                separator_idx = -1
                replace_end = -1

                # Find the separator
                for j in range(search_start, len(lines)):
                    if lines[j] == separator:
                        separator_idx = j
                        break

                if separator_idx == -1:
                    raise ValueError("Invalid format: missing separator")

                # Find the replace marker
                for j in range(separator_idx + 1, len(lines)):
                    if lines[j] == replace_marker:
                        replace_end = j
                        break

                if replace_end == -1:
                    raise ValueError("Invalid format: missing replace marker")

                search_text = "\n".join(lines[search_start:separator_idx])
                replace_text = "\n".join(lines[separator_idx + 1 : replace_end])

                # Check for markers in the search or replace text
                if any(
                    marker in search_text
                    for marker in [search_marker, separator, replace_marker]
                ):
                    raise ValueError(
                        f"Block {len(blocks)+1}: Search text contains patch markers"
                    )
                if any(
                    marker in replace_text
                    for marker in [search_marker, separator, replace_marker]
                ):
                    raise ValueError(
                        f"Block {len(blocks)+1}: Replace text contains patch markers"
                    )

                blocks.append((search_text, replace_text))

                i = replace_end + 1
            else:
                i += 1

        if blocks:
            return blocks
        else:
            raise ValueError(
                "Invalid patch format. Expected block format with SEARCH/REPLACE markers."
            )

    # Check for markers in matched content
    for i, (search_text, replace_text) in enumerate(matches):
        if any(
            marker in search_text
            for marker in [search_marker, separator, replace_marker]
        ):
            raise ValueError(f"Block {i+1}: Search text contains patch markers")
        if any(
            marker in replace_text
            for marker in [search_marker, separator, replace_marker]
        ):
            raise ValueError(f"Block {i+1}: Replace text contains patch markers")

    return matches


def get_current_python_executable():
    """Get the path to the currently running Python executable."""
    return sys.executable


def is_same_venv(python_exe_path, current_exe_path):
    """
    Check if two Python executable paths are from the same virtual environment.
    Returns True if they are the same venv, False otherwise.
    """
    if not python_exe_path or not current_exe_path:
        return False

    # Normalize paths
    python_exe = Path(python_exe_path).resolve()
    current_exe = Path(current_exe_path).resolve()

    # If they're the same file, they're the same venv
    if python_exe == current_exe:
        return True

    # Check if they're in the same Scripts directory (Windows venv structure)
    python_scripts_dir = python_exe.parent
    current_scripts_dir = current_exe.parent

    if python_scripts_dir == current_scripts_dir:
        return True

    # Check if they're in the same venv directory structure
    python_venv_root = (
        python_scripts_dir.parent if python_scripts_dir.name == "Scripts" else None
    )
    current_venv_root = (
        current_scripts_dir.parent if current_scripts_dir.name == "Scripts" else None
    )

    if python_venv_root and current_venv_root and python_venv_root == current_venv_root:
        return True

    return False


def find_venv_directory(file_path):
    """
    Find the virtual environment directory (.venv or venv) by walking up from the file path.
    Returns the path to the Python executable in the venv, or None if not found.
    Ensures we find the project's venv, not the MCP server's venv.
    """
    file_path = Path(file_path).resolve()
    current_path = file_path.parent
    current_python_exe = get_current_python_executable()

    if logger:
        logger.debug(f"Looking for venv starting from: {current_path}")
        logger.debug(f"Current Python executable (MCP server): {current_python_exe}")

    # Walk up the directory tree looking for venv
    for depth in range(10):  # Limit search depth to prevent infinite loops
        if logger:
            logger.debug(f"Checking directory {depth}: {current_path}")

        # Check for .venv first (preferred)
        venv_path = current_path / ".venv"
        if venv_path.exists() and venv_path.is_dir():
            python_exe = venv_path / "Scripts" / "python.exe"
            if python_exe.exists():
                found_exe_path = str(python_exe)
                if is_same_venv(found_exe_path, current_python_exe):
                    if logger:
                        logger.debug(
                            f"Found .venv at {venv_path}, but it's the same as MCP server's venv - skipping"
                        )
                    continue
                else:
                    if logger:
                        logger.info(
                            f"Found .venv at: {venv_path} (different from MCP server venv)"
                        )
                    return found_exe_path

        # Check for venv
        venv_path = current_path / "venv"
        if venv_path.exists() and venv_path.is_dir():
            python_exe = venv_path / "Scripts" / "python.exe"
            if python_exe.exists():
                found_exe_path = str(python_exe)
                if is_same_venv(found_exe_path, current_python_exe):
                    if logger:
                        logger.debug(
                            f"Found venv at {venv_path}, but it's the same as MCP server's venv - skipping"
                        )
                    continue
                else:
                    if logger:
                        logger.info(
                            f"Found venv at: {venv_path} (different from MCP server venv)"
                        )
                    return found_exe_path

        # Move up one directory
        parent = current_path.parent
        if parent == current_path:  # Reached root
            if logger:
                logger.debug("Reached filesystem root, no venv found")
            break
        current_path = parent

    if logger:
        logger.warning(
            "No venv found in directory tree (or all found venvs are the same as MCP server)"
        )
    return None


def get_file_modification_time(file_path):
    """Get the modification time of a file."""
    return os.path.getmtime(file_path)


def is_binary_file_extension(file_path):
    """
    Check if the file has a binary format extension that should be blocked from patching.

    This security check prevents attempts to edit binary files which could cause data corruption
    or other security issues. The patch_file tool is designed for text files only.

    Args:
        file_path: Path to the file to check

    Returns:
        tuple: (is_binary: bool, extension: str or None)
    """
    # Comprehensive list of binary file extensions to block
    # Includes user's suggested list plus additional common binary formats
    binary_extensions = {
        # Executables and libraries
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".lib",
        ".a",
        ".o",
        ".obj",
        # Documents and spreadsheets
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".odt",
        ".ods",
        ".odp",
        ".rtf",
        # Images
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".bmp",
        ".tiff",
        ".tif",
        ".webp",
        ".svg",
        ".ico",
        ".raw",
        ".psd",
        ".ai",
        ".eps",
        # Audio/Video
        ".mp3",
        ".mp4",
        ".avi",
        ".mkv",
        ".mov",
        ".wmv",
        ".flv",
        ".wav",
        ".aac",
        ".ogg",
        ".wma",
        ".flac",
        ".m4a",
        ".m4v",
        # Archives and compressed files
        ".zip",
        ".rar",
        ".7z",
        ".tar",
        ".gz",
        ".bz2",
        ".xz",
        ".cab",
        ".iso",
        ".dmg",
        ".deb",
        ".rpm",
        # System and data files
        ".bin",
        ".dat",
        ".db",
        ".sqlite",
        ".mdb",
        ".accdb",
        ".reg",
        ".sys",
        ".drv",
        ".ocx",
        ".cpl",
        ".scr",
        # Installer and package files
        ".msi",
        ".pkg",
        ".app",
        ".dmg",
        ".appx",
        ".snap",
        # Other binary formats
        ".ld",
        ".elf",
        ".coff",
        ".pe",
        ".mach-o",
        ".class",
        ".jar",
        ".war",
        ".ear",
        ".swf",
        ".fla",
        ".xap",
    }

    try:
        # Handle None or empty string inputs
        if not file_path or file_path.strip() == "":
            return True, None

        path_obj = Path(file_path)
        extension = path_obj.suffix.lower()

        if extension in binary_extensions:
            return True, extension

        return False, None

    except Exception:
        # If path parsing fails, err on the side of caution
        return True, None


def run_command_with_timeout(cmd, cwd=None, timeout=30, shell=False, env=None):
    """
    Run a command with a timeout and return the result.
    Returns a tuple: (success: bool, stdout: str, stderr: str, return_code: int)
    """
    try:
        if logger:
            logger.debug(f"spawn cmd={cmd} cwd={cwd} timeout={timeout} shell={shell}")
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=shell,
            env=env,
            stdin=subprocess.DEVNULL,
        )
        success = result.returncode == 0
        return success, result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return False, "", f"Command timed out after {timeout} seconds", -1
    except Exception as e:
        return False, "", f"Command execution failed: {str(e)}", -1


def run_python_qa_pipeline(file_path, python_exe):
    """
    Run the Python QA pipeline: ruff -> black -> mypy
    Returns a dict with QA results and status.
    """
    file_path = Path(file_path)
    file_dir = str(file_path.parent)
    file_abs = str(file_path)
    max_iterations = max(1, QA_MAX_ITERATIONS)
    iteration = 0
    start_time = time.monotonic()

    # Initialize qa_results
    qa_results = {
        "qa_performed": True,
        "iterations_used": 0,
        "ruff_status": None,
        "black_status": None,
        "mypy_status": None,
        "ruff_stdout": "",
        "ruff_stderr": "",
        "black_stdout": "",
        "black_stderr": "",
        "mypy_stdout": "",
        "mypy_stderr": "",
        "errors": [],
        "warnings": [],
    }

    # Only run QA for Python files
    if file_path.suffix != ".py":
        qa_results["warnings"].append("QA skipped: not a Python file")
        return qa_results

    # Determine which tools to run
    file_abs_lower = file_abs.lower()
    do_ruff = not SKIP_RUFF
    do_black = not SKIP_BLACK
    do_mypy = not SKIP_MYPY and (
        not SKIP_MYPY_ON_TESTS or "tests" not in file_abs_lower
    )

    # Only iterate when both ruff and black are enabled
    effective_iterations = max_iterations if (do_ruff and do_black) else 1

    # If everything is disabled, return early
    if not (do_ruff or do_black or do_mypy):
        qa_results["qa_performed"] = False
        qa_results["warnings"].append("QA disabled by server configuration")
        return qa_results

    while iteration < effective_iterations:
        # Wall-time guard to avoid client timeouts
        if time.monotonic() - start_time > QA_WALL_TIME:
            qa_results["warnings"].append(
                f"QA timed out after ~{QA_WALL_TIME}s. Run `ruff`, `black`, `mypy` manually if needed."
            )
            return qa_results
        iteration += 1
        qa_results["iterations_used"] = iteration

        # Handle None or empty python_exe
        if not python_exe or python_exe.strip() == "":
            qa_results["ruff_status"] = "failed"
            qa_results["black_status"] = "failed"
            qa_results["mypy_status"] = "failed"
            qa_results["errors"].append("Invalid Python executable path")
            return qa_results

        # Prefer venv binaries when available to avoid module resolution quirks
        py = Path(python_exe)
        scripts_dir = py.parent
        ruff_bin = scripts_dir / ("ruff.exe" if os.name == "nt" else "ruff")
        black_bin = scripts_dir / ("black.exe" if os.name == "nt" else "black")
        mypy_bin = scripts_dir / ("mypy.exe" if os.name == "nt" else "mypy")

        # Minimal, non-interactive environment
        qa_env = os.environ.copy()
        qa_env.setdefault("PYTHONIOENCODING", "utf-8")
        qa_env.setdefault("RUFF_LOG_LEVEL", "error")

        # Track modification time to detect Black changes
        try:
            original_mod_time = get_file_modification_time(file_path)
        except (OSError, FileNotFoundError):
            # File doesn't exist or can't be accessed
            qa_results["ruff_status"] = "failed"
            qa_results["black_status"] = "failed"
            qa_results["mypy_status"] = "failed"
            qa_results["errors"].append(f"File not found or inaccessible: {file_path}")
            return qa_results
        time.sleep(0.05)

        ruff_return_code = 0
        if do_ruff:
            if logger:
                logger.info(f"QA: ruff start ({file_abs})")
            if ruff_bin.exists():
                ruff_cmd = [
                    str(ruff_bin),
                    "check",
                    "--fix",
                    "--isolated",
                    "--no-cache",
                    "--",
                    file_abs,
                ]
            else:
                ruff_cmd = [
                    python_exe,
                    "-m",
                    "ruff",
                    "check",
                    "--fix",
                    "--isolated",
                    "--no-cache",
                    "--",
                    file_abs,
                ]
            success, stdout, stderr, ruff_return_code = run_command_with_timeout(
                ruff_cmd, cwd=file_dir, timeout=QA_CMD_TIMEOUT, shell=False, env=qa_env
            )
            if logger:
                logger.info(f"QA: ruff done rc={ruff_return_code}")
            if ruff_return_code == -1:
                qa_results["ruff_status"] = "failed"
                qa_results["ruff_stdout"] = stdout or ""
                qa_results["ruff_stderr"] = stderr or ""
                return qa_results
            if ruff_return_code != 0:
                if stderr and "unfixable" in stderr.lower():
                    qa_results["ruff_status"] = "failed"
                    qa_results["ruff_stdout"] = stdout or ""
                    qa_results["ruff_stderr"] = stderr or ""
                    return qa_results
                elif stderr:
                    qa_results["warnings"].append(f"Ruff warnings: {stderr}")
            qa_results["ruff_status"] = (
                "passed" if ruff_return_code == 0 else "warnings"
            )

        if do_black:
            if logger:
                logger.info(f"QA: black start ({file_abs})")
            if black_bin.exists():
                black_cmd = [str(black_bin), "--quiet", "--", file_abs]
            else:
                black_cmd = [python_exe, "-m", "black", "--quiet", "--", file_abs]
            success, stdout, stderr, black_return_code = run_command_with_timeout(
                black_cmd, cwd=file_dir, timeout=QA_CMD_TIMEOUT, shell=False, env=qa_env
            )
            if logger:
                logger.info(f"QA: black done rc={black_return_code}")
            if black_return_code == -1:
                qa_results["black_status"] = "failed"
                qa_results["black_stdout"] = stdout or ""
                qa_results["black_stderr"] = stderr or ""
                return qa_results
            if black_return_code == 0:
                qa_results["black_status"] = "passed"
            else:
                qa_results["black_status"] = "warnings"
                if stderr:
                    qa_results["warnings"].append(f"Black warnings: {stderr}")

            # If both ruff and black are enabled and black changed the file, iterate
            new_mod_time = get_file_modification_time(file_path)
            if do_ruff and new_mod_time > original_mod_time:
                if logger:
                    logger.debug("Black reformatted file, iterating QA loop")
                continue
        # No iteration needed
        break

    # Check for iteration limit exceeded
    if iteration >= effective_iterations:
        qa_results["warnings"].append(
            f"QA pipeline reached iteration limit ({effective_iterations})."
        )
        return qa_results

    # Step 3: MyPy (optional)
    if do_mypy:
        if logger:
            logger.info(f"QA: mypy start ({file_abs})")
        # Wall-time guard before mypy
        if time.monotonic() - start_time > QA_WALL_TIME:
            qa_results["warnings"].append(
                f"QA timed out after ~{QA_WALL_TIME}s (before mypy). Run `mypy` manually if needed."
            )
            return qa_results

        if mypy_bin.exists():
            mypy_cmd = [str(mypy_bin), "--no-color-output", "--", file_abs]
        else:
            mypy_cmd = [python_exe, "-m", "mypy", "--no-color-output", "--", file_abs]
        success, stdout, stderr, return_code = run_command_with_timeout(
            mypy_cmd, cwd=file_dir, timeout=QA_CMD_TIMEOUT, shell=False, env=qa_env
        )

        if logger:
            logger.info(f"QA: mypy done rc={return_code}")
        if return_code == -1:
            qa_results["mypy_status"] = "failed"
            qa_results["mypy_stdout"] = stdout or ""
            qa_results["mypy_stderr"] = stderr or ""
        else:
            if return_code == 0:
                qa_results["mypy_status"] = "passed"
            else:
                qa_results["mypy_status"] = "failed"
                qa_results["mypy_stdout"] = stdout or ""
                qa_results["mypy_stderr"] = stderr or ""

    return qa_results


def normalize_text_for_fuzzy_matching(text: str) -> str:
    """
    Normalize text for fuzzy matching by:
    - Stripping leading/trailing whitespace
    - Normalizing line endings to \n
    - Collapsing multiple consecutive whitespace characters to single spaces
    - Converting tabs to spaces
    """
    # Normalize line endings
    normalized = text.replace('\r\n', '\n').replace('\r', '\n')
    
    # Convert tabs to spaces and collapse multiple whitespace
    normalized = re.sub(r'[ \t]+', ' ', normalized)
    
    # Strip leading/trailing whitespace from each line
    lines = [line.strip() for line in normalized.split('\n')]
    
    # Remove empty lines at start and end, but preserve internal empty lines
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    
    return '\n'.join(lines)


def find_fuzzy_matches(search_text: str, content: str) -> List[tuple]:
    """
    Find fuzzy matches for search_text in content using relaxed matching criteria.
    
    Returns a list of tuples: (start_line, end_line, matched_text, similarity_ratio)
    """
    # Normalize both texts for comparison
    normalized_search = normalize_text_for_fuzzy_matching(search_text)
    
    if not normalized_search.strip():
        return []
    
    content_lines = content.split('\n')
    search_lines = normalized_search.split('\n')
    num_search_lines = len(search_lines)
    matches = []
    
    # Try to find matches with exact line count first, then with some flexibility
    for line_tolerance in [0, 1, 2]:  # Try exact match, then +/- 1 line, then +/- 2 lines
        for start_line in range(len(content_lines)):
            # Try different end positions around the expected size
            for line_offset in range(-line_tolerance, line_tolerance + 1):
                end_line = start_line + num_search_lines - 1 + line_offset
                
                if end_line >= len(content_lines) or end_line < start_line:
                    continue
                
                # Extract candidate text
                candidate_lines = content_lines[start_line:end_line + 1]
                candidate_text = '\n'.join(candidate_lines)
                normalized_candidate = normalize_text_for_fuzzy_matching(candidate_text)
                
                # Calculate similarity using difflib
                similarity = difflib.SequenceMatcher(None, normalized_search, normalized_candidate).ratio()
                
                # Consider it a fuzzy match if similarity is high enough
                # Use higher threshold for better precision
                if similarity >= 0.8:
                    matches.append((start_line, end_line, candidate_text, similarity))
    
    if not matches:
        return []
    
    # Sort by similarity (best matches first)
    matches.sort(key=lambda x: x[3], reverse=True)
    
    # Remove overlapping matches, keeping only the best one
    filtered_matches = []
    for match in matches:
        start, end, text, sim = match
        # Check if this match overlaps with any existing match
        overlaps = False
        for existing_start, existing_end, _, _ in filtered_matches:
            # Check for any overlap
            if not (end < existing_start or start > existing_end):
                overlaps = True
                break
        
        if not overlaps:
            filtered_matches.append(match)
    
    # If we have multiple non-overlapping matches, only return the best one
    # to avoid ambiguity in hints
    if len(filtered_matches) > 1:
        # Check if the best match is significantly better than others
        best_similarity = filtered_matches[0][3]
        second_best_similarity = filtered_matches[1][3] if len(filtered_matches) > 1 else 0
        
        # Only return the best match if it's clearly better (5% difference)
        if best_similarity - second_best_similarity >= 0.05:
            return [filtered_matches[0]]
        else:
            # Too ambiguous, return empty to avoid confusing hints
            return []
    
    return filtered_matches


def generate_fuzzy_match_hint(search_text: str, content: str, file_path: str) -> Optional[str]:
    """
    Generate a helpful hint when exact search fails by finding fuzzy matches.
    
    Returns a hint string if exactly one fuzzy match is found, None otherwise.
    
    Safeguards:
    - Skip if search text is too short (< 20 chars) - likely too many false matches
    - Skip if search text is too long (> 2000 chars) - unlikely to be helpful for large blocks
    - Skip if search text has too few lines (< 2) - single lines often match too broadly
    - Skip if search text has too many lines (> 50) - large blocks are usually structurally different
    """
    try:
        if logger:
            logger.debug(f"Generating fuzzy match hint for search text in {file_path}")
        
        # Safeguard: Check search text length
        search_text_stripped = search_text.strip()
        if len(search_text_stripped) < 20:
            if logger:
                logger.debug(f"Search text too short ({len(search_text_stripped)} chars), skipping fuzzy matching")
            return None
        
        if len(search_text_stripped) > 2000:
            if logger:
                logger.debug(f"Search text too long ({len(search_text_stripped)} chars), skipping fuzzy matching")
            return None
        
        # Safeguard: Check number of lines
        search_lines = search_text_stripped.split('\n')
        num_lines = len([line for line in search_lines if line.strip()])  # Count non-empty lines
        
        if num_lines < 2:
            if logger:
                logger.debug(f"Search text has too few lines ({num_lines}), skipping fuzzy matching")
            return None
        
        if num_lines > 50:
            if logger:
                logger.debug(f"Search text has too many lines ({num_lines}), skipping fuzzy matching")
            return None
        
        fuzzy_matches = find_fuzzy_matches(search_text, content)
        
        if logger:
            logger.debug(f"Found {len(fuzzy_matches)} fuzzy matches")
        
        # Only provide hint if we have exactly one match
        if len(fuzzy_matches) == 1:
            start_line, end_line, matched_text, similarity = fuzzy_matches[0]
            
            if logger:
                logger.debug(f"Single fuzzy match found at lines {start_line+1}-{end_line+1} with {similarity:.2%} similarity")
            
            # Add context lines (3 before and 3 after)
            content_lines = content.split('\n')
            context_start = max(0, start_line - 3)
            context_end = min(len(content_lines), end_line + 4)
            
            # Build the hint with line numbers
            hint_lines = []
            hint_lines.append("Hint: Found similar content with whitespace/formatting differences. Check the exact text around these lines:")
            hint_lines.append("")
            
            for line_num in range(context_start, context_end):
                line_content = content_lines[line_num] if line_num < len(content_lines) else ""
                # Mark the actual match lines with arrows
                if start_line <= line_num <= end_line:
                    hint_lines.append(f"{line_num + 1:4d}: {line_content}  <-- likely match")
                else:
                    hint_lines.append(f"{line_num + 1:4d}: {line_content}")
            
            return '\n'.join(hint_lines)
        
        elif len(fuzzy_matches) > 1:
            if logger:
                logger.debug(f"Multiple fuzzy matches found ({len(fuzzy_matches)}), not providing hint")
        else:
            if logger:
                logger.debug("No fuzzy matches found")
        
        return None
        
    except Exception as e:
        if logger:
            logger.warning(f"Error generating fuzzy match hint: {e}")
        return None


@mcp.tool()
def patch_file(
    file_path: str = Field(description="The path to the file to patch"),
    patch_content: str = Field(
        description="Content to search and replace in the file using block format with SEARCH/REPLACE markers. Multiple blocks are supported."
    ),
):
    """
    Update the file by applying a patch/edit to it using block format.

    Required format:
    ```
    <<<<<<< SEARCH
    Text to find in the file
    =======
    Text to replace it with
    >>>>>>> REPLACE
    ```

    You can include multiple search-replace blocks in a single request:
    ```
    <<<<<<< SEARCH
    First text to find
    =======
    First replacement
    >>>>>>> REPLACE
    <<<<<<< SEARCH
    Second text to find
    =======
    Second replacement
    >>>>>>> REPLACE
    ```

    Rules:
    - Provide an absolute file path (Windows: C:/path/to/file.py or C:\\path\\to\\file.py; Unix: /path/to/file.py). Relative paths are rejected.
    - Each SEARCH text must match exactly once; otherwise the tool errors.
    - If the file is Python, you will also receive a brief linter output in addition to patch status.
    """
    # Increment tool call counter and trigger garbage collection every 100 calls
    global TOOL_CALL_COUNTER
    TOOL_CALL_COUNTER += 1
    if TOOL_CALL_COUNTER % 100 == 0:
        if logger:
            logger.debug(
                f"Tool call #{TOOL_CALL_COUNTER}: triggering garbage collection"
            )
        garbage_collect_failed_edit_history()

    # DEBUG: Log input parameters for precise debugging
    if logger:
        logger.info(f"patch_file start: {file_path}")
        logger.debug("=== PATCH_FILE DEBUG INFO ===")
        logger.debug(f"Input file_path: '{file_path}'")
        logger.debug(f"Input patch_content length: {len(patch_content)} characters")
        logger.debug(
            f"Input patch_content preview (first 200 chars): {patch_content[:200]}{'...' if len(patch_content) > 200 else ''}"
        )
        logger.debug(f"Allowed directories: {allowed_directories}")
        logger.debug("=== END PATCH_FILE INPUT DEBUG ===")

    # Check for failed edit awareness message
    awareness_message = get_failed_edit_info(file_path, patch_content)
    if awareness_message:
        if logger:
            logger.info(f"Failed edit awareness: {awareness_message}")
        print(awareness_message)  # Print to stdout so it appears in the response

    # Self-correct hint: require absolute paths
    try:
        if not Path(file_path).is_absolute():
            raise ValueError(
                "Relative path provided. Use an absolute file path (e.g., C:/proj/file.py or /home/user/file.py)."
            )
    except Exception:
        # If Path() fails (very malformed), still guide the agent
        raise ValueError(
            "Invalid or relative path. Provide an absolute file path (e.g., C:/proj/file.py or /home/user/file.py)."
        )

    # SECURITY CHECK: Reject binary file extensions
    is_binary, extension = is_binary_file_extension(file_path)
    if is_binary:
        if logger:
            logger.warning(
                f"Rejected patch attempt on binary file: {file_path} (extension: {extension})"
            )
        raise ValueError(
            "Rejected: patch_file tool should only be used to edit text files. Editing of binary files is not supported"
        )

    # Validate file path and check if it's within allowed directories
    is_allowed, matched_dir = is_file_in_allowed_directories(
        file_path, allowed_directories
    )

    if not is_allowed:
        if matched_dir:
            raise PermissionError(f"File {file_path} is not in allowed directories")
        else:
            raise PermissionError(
                f"File {file_path} is not in any of the allowed directories: {allowed_directories}"
            )

    # Resolve the file path after validation
    pp = Path(file_path).resolve()
    if logger:
        logger.debug(f"Resolved file path: '{pp}'")
        logger.debug(f"File exists: {pp.exists()}, is_file: {pp.is_file()}")

    if not pp.exists() or not pp.is_file():
        if logger:
            logger.debug(
                f"File validation failed - exists: {pp.exists()}, is_file: {pp.is_file()}"
            )
        raise FileNotFoundError(f"File {file_path} does not exist")

    # Read the current file content
    if logger:
        logger.debug(f"Reading file content from: '{pp}'")

    with open(pp, "r", encoding="utf-8") as f:
        original_content = f.read()

    if logger:
        logger.debug(
            f"Original file content length: {len(original_content)} characters"
        )
        logger.debug(
            f"Original file content preview (first 300 chars): {original_content[:300]}{'...' if len(original_content) > 300 else ''}"
        )

    try:
        # Parse multiple search-replace blocks
        if logger:
            logger.debug("Parsing search-replace blocks from patch_content")

        blocks = parse_search_replace_blocks(patch_content)
        if not blocks:
            if logger:
                logger.debug("No valid search-replace blocks found in patch_content")
            raise ValueError(
                "No valid search-replace blocks found in the patch content"
            )

        if logger:
            logger.debug(f"Successfully parsed {len(blocks)} search-replace blocks")
            for i, (search, replace) in enumerate(blocks, 1):
                logger.debug(
                    f"Block {i} - Search text ({len(search)} chars): {search[:100]}{'...' if len(search) > 100 else ''}"
                )
                logger.debug(
                    f"Block {i} - Replace text ({len(replace)} chars): {replace[:100]}{'...' if len(replace) > 100 else ''}"
                )

        # Apply each block sequentially
        current_content = original_content
        applied_blocks = 0

        for i, (search_text, replace_text) in enumerate(blocks):
            if logger:
                logger.debug(f"=== Processing Block {i+1}/{len(blocks)} ===")
                logger.debug(
                    f"Block {i+1} search_text length: {len(search_text)} chars"
                )
                logger.debug(
                    f"Block {i+1} replace_text length: {len(replace_text)} chars"
                )

            # Check exact match count
            count = current_content.count(search_text)
            if logger:
                logger.debug(
                    f"Block {i+1}: Search text appears {count} times in current content"
                )

            if count == 1:
                # Exactly one match - perfect!
                if logger:
                    logger.debug(
                        f"Block {i+1}: Found exactly one exact match - proceeding with replacement"
                    )
                current_content = current_content.replace(search_text, replace_text)
                applied_blocks += 1
                if logger:
                    logger.debug(f"Block {i+1}: Successfully applied replacement")

            elif count > 1:
                # Multiple matches - too ambiguous
                if logger:
                    logger.debug(
                        f"Block {i+1}: ERROR - Multiple matches ({count}) found, too ambiguous"
                    )
                raise ValueError(
                    f"Block {i+1}: The search text appears {count} times in the file. "
                    "Please provide more context to identify the specific occurrence."
                )

            else:
                # No match found - try fuzzy matching to provide helpful hints
                if logger:
                    logger.debug(f"Block {i+1}: ERROR - No matches found in file")
                
                # Generate fuzzy match hint
                fuzzy_hint = generate_fuzzy_match_hint(search_text, current_content, file_path)
                
                error_message = (
                    f"Block {i+1}: Could not find the search text in the file. "
                    "Please ensure the search text exactly matches the content in the file."
                )
                
                if fuzzy_hint:
                    error_message += f"\n\n{fuzzy_hint}"
                
                raise ValueError(error_message)

        # Write the final content back to the file
        if logger:
            logger.debug(f"Writing modified content back to file: '{pp}'")
            logger.debug(f"Modified content length: {len(current_content)} characters")
            logger.debug(f"Content changed: {current_content != original_content}")

        with open(pp, "w", encoding="utf-8") as f:
            f.write(current_content)

        if logger:
            logger.debug(
                f"Successfully wrote {len(current_content)} characters to file"
            )

        # QA Pipeline: Only run after successful file patching AND only on Python files
        # This ensures we don't bother the user with QA info when patching fails
        patch_result = (
            f"Successfully applied {applied_blocks} patch blocks to {file_path}"
        )

        if logger:
            logger.debug(
                f"Patch operation completed successfully - applied {applied_blocks} blocks"
            )
            logger.debug(f"Final patch result message: {patch_result}")

        # Only run QA for Python files (.py extension)
        qa_performed = False
        if pp.suffix == ".py":
            if logger:
                logger.debug(
                    f"File has .py extension - initiating QA pipeline for: {file_path}"
                )

            # Find virtual environment
            python_exe = find_venv_directory(file_path)
            if python_exe:
                if logger:
                    logger.debug(f"Found Python executable for QA: '{python_exe}'")

                # Run QA pipeline
                if logger:
                    logger.debug("Starting QA pipeline execution")

                qa_results = run_python_qa_pipeline(file_path, python_exe)
                qa_performed = True

                if logger:
                    logger.debug(f"QA pipeline completed with results: {qa_results}")

                # Update mypy failure count for steering logic
                mypy_passed = qa_results.get("mypy_status") == "passed"
                update_mypy_failure_count(file_path, mypy_passed)

                # Check if mypy information should be suppressed
                suppress_mypy = should_suppress_mypy_info(file_path)

                # Format QA results for response
                qa_summary = "\n\nQA Results:\n"

                # Passed and warnings statuses
                ruff_status = qa_results.get("ruff_status")
                if ruff_status in ["passed", "warnings"]:
                    status_text = "passed" if ruff_status == "passed" else "completed successfully"
                    qa_summary += f"- Ruff: {status_text}\n"

                black_status = qa_results.get("black_status")
                if black_status in ["passed", "warnings"]:
                    status_text = "passed" if black_status == "passed" else "completed successfully"
                    qa_summary += f"- Black: {status_text}\n"

                mypy_status = qa_results.get("mypy_status")
                if mypy_status == "passed" and not suppress_mypy:
                    qa_summary += "- MyPy: passed\n"

                # Collect tools with issues (warnings or failures) for detailed output
                tools_with_output = []

                # Failed tools
                if qa_results.get("ruff_status") == "failed":
                    tools_with_output.append(
                        (
                            "Ruff",
                            qa_results.get("ruff_stdout", ""),
                            qa_results.get("ruff_stderr", ""),
                            "failed"
                        )
                    )
                if qa_results.get("black_status") == "failed":
                    tools_with_output.append(
                        (
                            "Black",
                            qa_results.get("black_stdout", ""),
                            qa_results.get("black_stderr", ""),
                            "failed"
                        )
                    )
                if qa_results.get("mypy_status") == "failed" and not suppress_mypy:
                    tools_with_output.append(
                        (
                            "MyPy",
                            qa_results.get("mypy_stdout", ""),
                            qa_results.get("mypy_stderr", ""),
                            "failed"
                        )
                    )

                # Tools with warnings
                if qa_results.get("ruff_status") == "warnings":
                    tools_with_output.append(
                        (
                            "Ruff",
                            qa_results.get("ruff_stdout", ""),
                            qa_results.get("ruff_stderr", ""),
                            "completed with warnings"
                        )
                    )
                if qa_results.get("black_status") == "warnings":
                    tools_with_output.append(
                        (
                            "Black",
                            qa_results.get("black_stdout", ""),
                            qa_results.get("black_stderr", ""),
                            "completed with warnings"
                        )
                    )

                if tools_with_output:
                    qa_summary += "\nQA Details:\n"
                    for name, out, err, status in tools_with_output:
                        combined = "\n".join([s for s in [out, err] if s])
                        if combined:
                            qa_summary += f"- {name} ({status}):\n{combined}\n"
                        else:
                            qa_summary += f"- {name}: {status} with no output\n"
                    if any(status == "failed" for _, _, _, status in tools_with_output):
                        qa_summary += "\nYou need to perform code linting and QA by manually running ruff and black commands.\n"

                # Warnings
                if qa_results.get("warnings"):
                    qa_summary += "\nQA Warnings:\n"
                    for warning in qa_results["warnings"]:
                        qa_summary += f"- {warning}\n"

                patch_result += qa_summary

                if logger:
                    logger.debug(
                        f"QA summary added to patch result (length: {len(qa_summary)} chars)"
                    )
            else:
                no_venv_msg = "\n\nQA Warning: No virtual environment (.venv or venv) found. Skipping Python QA checks. You need to perform code linting and QA by manually running `ruff`, `black` and `mypy` tools."
                patch_result += no_venv_msg
                if logger:
                    logger.debug(
                        f"No virtual environment found - added warning: {no_venv_msg.strip()}"
                    )
        else:
            if logger:
                logger.debug(
                    f"File extension '{pp.suffix}' is not .py - skipping QA pipeline"
                )

        # Clear failed edit history on successful patch
        clear_failed_edit_history(file_path)

        if logger:
            logger.info(
                f"patch_file success: {file_path} | blocks={applied_blocks} | qa={'yes' if qa_performed else 'no'}"
            )
            logger.debug("=== PATCH_FILE SUCCESS ===")
            logger.debug(f"Returning patch result: {patch_result}")

        return patch_result

    except Exception as e:
        if logger:
            logger.error(f"patch_file error: {file_path} -> {e}")
            logger.debug("=== PATCH_FILE EXCEPTION ===")
            logger.debug(f"Exception type: {type(e).__name__}")
            logger.debug(f"Exception message: {str(e)}")
            logger.debug(f"Exception details: {repr(e)}")
            import traceback

            logger.debug(f"Traceback: {traceback.format_exc()}")

        # Track failed edit attempt
        # Determine failure stage based on exception type and message
        error_msg = str(e)
        if (
            "relative path" in error_msg.lower()
            or "Invalid or relative path" in error_msg
        ):
            failure_stage = "path_validation"
        elif (
            "binary file" in error_msg.lower()
            or "should only be used to edit text files" in error_msg
        ):
            failure_stage = "binary_file_check"
        elif (
            "not in allowed directories" in error_msg.lower()
            or "is not in any of the allowed directories" in error_msg
        ):
            failure_stage = "directory_access"
        elif "does not exist" in error_msg.lower() or "FileNotFoundError" in str(
            type(e)
        ):
            failure_stage = "file_existence"
        elif (
            "search-replace blocks" in error_msg.lower()
            or "patch markers" in error_msg.lower()
            or "Invalid patch format" in error_msg
        ):
            failure_stage = "patch_parsing"
        elif (
            ("appears" in error_msg.lower() and "times" in error_msg.lower())
            or "Could not find the search text" in error_msg
            or "ambiguous" in error_msg.lower()
        ):
            failure_stage = "block_application"
        else:
            failure_stage = "general_error"

        track_failed_edit(file_path, patch_content, failure_stage, error_msg)

        raise RuntimeError(f"Failed to apply patch: {str(e)}")


if __name__ == "__main__":
    # Ensure tools are registered before starting when run with `-m`.
    # The tool definitions above must be imported before `main()` executes.
    main()
