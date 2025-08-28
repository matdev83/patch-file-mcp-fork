#! /usr/bin/env python3
import sys
import argparse
import subprocess
import os
import time
from pathlib import Path
import re

from fastmcp import FastMCP
from pydantic.fields import Field


mcp = FastMCP(
    name="Patch File MCP",
    instructions="""
This MCP is for patching existing files using block format with automatic code quality checks.

Use the block format with SEARCH/REPLACE markers:
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

This tool verifies that each search text appears exactly once in the file to ensure
the correct section is modified. If a search text appears multiple times or isn't
found, it will report an error.

For Python files (.py), after successful patching, this tool automatically runs:
- Ruff: Linting and auto-fixing
- Black: Code formatting (may trigger additional ruff checks)
- MyPy: Type checking

QA results are included in the response, showing any issues found or confirming clean code.
For non-Python files, only the patch success message is returned.
""",
)

allowed_directories = []


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def normalize_path(path_str):
    """
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
    if '\\\\' in path_str:
        try:
            unescaped = path_str.encode().decode('unicode_escape')
        except UnicodeDecodeError:
            # If unicode_escape fails, use the original string
            unescaped = path_str
    else:
        unescaped = path_str

    # Step 2: Normalize path separators
    # Convert all separators to OS-native format
    if os.name == 'nt':  # Windows
        # On Windows, ensure we use backslashes
        normalized = unescaped.replace('/', '\\')
    else:  # Unix-like systems
        # On Unix, ensure we use forward slashes
        normalized = unescaped.replace('\\', '/')

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
        eprint(
            "ERROR: No allowed directories specified. At least one --allowed-dir is required."
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
                eprint(f"ERROR: {error_msg}")
                sys.exit(1)

            validated_dirs.append(str(dir_path))
            eprint(f"✓ Validated allowed directory: {dir_path}")

        except Exception as e:
            eprint(f"ERROR: Failed to process directory '{dir_path_str}': {e}")
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
        eprint(f"ERROR: Failed to validate file path '{file_path}': {e}")
        return False, None


def main():
    # Process command line arguments
    global allowed_directories
    parser = argparse.ArgumentParser(description="Patch File MCP server")
    parser.add_argument(
        "--allowed-dir",
        action="append",
        dest="allowed_dirs",
        required=True,
        help="Allowed base directory for project paths (can be used multiple times)",
    )
    args = parser.parse_args()

    # Validate allowed directories at startup
    allowed_directories = validate_allowed_directories(args.allowed_dirs)

    eprint(
        f"Server started successfully with {len(allowed_directories)} allowed directories"
    )

    # Run the MCP server
    mcp.run()


if __name__ == "__main__":
    main()


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

    eprint(f"Looking for venv starting from: {current_path}")
    eprint(f"Current Python executable (MCP server): {current_python_exe}")

    # Walk up the directory tree looking for venv
    for depth in range(10):  # Limit search depth to prevent infinite loops
        eprint(f"Checking directory {depth}: {current_path}")

        # Check for .venv first (preferred)
        venv_path = current_path / ".venv"
        if venv_path.exists() and venv_path.is_dir():
            python_exe = venv_path / "Scripts" / "python.exe"
            if python_exe.exists():
                found_exe_path = str(python_exe)
                if is_same_venv(found_exe_path, current_python_exe):
                    eprint(
                        f"Found .venv at {venv_path}, but it's the same as MCP server's venv - skipping"
                    )
                    continue
                else:
                    eprint(
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
                    eprint(
                        f"Found venv at {venv_path}, but it's the same as MCP server's venv - skipping"
                    )
                    continue
                else:
                    eprint(
                        f"Found venv at: {venv_path} (different from MCP server venv)"
                    )
                    return found_exe_path

        # Move up one directory
        parent = current_path.parent
        if parent == current_path:  # Reached root
            eprint("Reached filesystem root, no venv found")
            break
        current_path = parent

    eprint(
        "No venv found in directory tree (or all found venvs are the same as MCP server)"
    )
    return None


def get_file_modification_time(file_path):
    """Get the modification time of a file."""
    return os.path.getmtime(file_path)


def run_command_with_timeout(cmd, cwd=None, timeout=30):
    """
    Run a command with a timeout and return the result.
    Returns a tuple: (success: bool, stdout: str, stderr: str, return_code: int)
    """
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=True,  # Allow shell commands for Windows
        )
        return True, result.stdout, result.stderr, result.returncode
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
    file_name = file_path.name
    max_iterations = 4
    iteration = 0

    qa_results = {
        "qa_performed": True,
        "iterations_used": 0,
        "ruff_status": None,
        "black_status": None,
        "mypy_status": None,
        "errors": [],
        "warnings": [],
    }

    while iteration < max_iterations:
        iteration += 1
        qa_results["iterations_used"] = iteration

        # Step 1: Run ruff check --fix
        eprint(f"QA Iteration {iteration}: Running ruff check --fix on {file_name}")
        ruff_cmd = f'"{python_exe}" -m ruff check --fix "{file_name}"'
        success, stdout, stderr, return_code = run_command_with_timeout(
            ruff_cmd, cwd=file_dir
        )

        if not success:
            qa_results["ruff_status"] = "failed"
            qa_results["errors"].append(
                f"Ruff execution failed: {stderr}. You need to perform code linting and QA by manually running `ruff`, `black` and `mypy` tools."
            )
            return qa_results

        # Check if ruff made any changes or found unfixable errors
        if return_code != 0:
            # Check if there are unfixable errors by looking at stderr
            if stderr and "unfixable" in stderr.lower():
                qa_results["ruff_status"] = "failed"
                qa_results["errors"].append(
                    f"Ruff found unfixable errors: {stderr}. You need to perform code linting and QA by manually running `ruff`, `black` and `mypy` tools."
                )
                return qa_results
            elif stderr:
                qa_results["warnings"].append(f"Ruff warnings: {stderr}")

        # Check if file was modified by ruff
        original_mod_time = get_file_modification_time(file_path)
        time.sleep(0.1)  # Small delay to ensure filesystem timestamp updates

        # Step 2: Run black if ruff passed without unfixable errors
        if return_code == 0 or (stderr and "unfixable" not in stderr.lower()):
            qa_results["ruff_status"] = "passed"
            eprint(f"QA Iteration {iteration}: Running black on {file_name}")

            black_cmd = f'"{python_exe}" -m black "{file_name}"'
            success, stdout, stderr, return_code = run_command_with_timeout(
                black_cmd, cwd=file_dir
            )

            if not success:
                qa_results["black_status"] = "failed"
                qa_results["errors"].append(
                    f"Black execution failed: {stderr}. You need to perform code linting and QA by manually running `ruff`, `black` and `mypy` tools."
                )
                return qa_results

            # Check if black modified the file
            new_mod_time = get_file_modification_time(file_path)
            if new_mod_time > original_mod_time:
                eprint(
                    f"QA Iteration {iteration}: Black reformatted {file_name}, restarting ruff check"
                )
                continue  # Restart the loop to run ruff again
            else:
                qa_results["black_status"] = (
                    "passed" if return_code == 0 else "warnings"
                )
                if stderr:
                    qa_results["warnings"].append(f"Black warnings: {stderr}")
                break  # No more modifications, exit loop
        else:
            qa_results["ruff_status"] = "failed"
            qa_results["errors"].append(
                f"Ruff failed: {stderr}. You need to perform code linting and QA by manually running `ruff`, `black` and `mypy` tools."
            )
            return qa_results

    # Check for iteration limit exceeded
    if iteration >= max_iterations:
        qa_results["errors"].append(
            f"QA pipeline exceeded maximum iterations ({max_iterations}). You need to perform code linting and QA by manually running `ruff`, `black` and `mypy` tools."
        )
        return qa_results

    # Step 3: Run mypy if we got here without errors
    eprint(f"QA Pipeline: Running mypy on {file_name}")
    mypy_cmd = f'"{python_exe}" -m mypy "{file_name}"'
    success, stdout, stderr, return_code = run_command_with_timeout(
        mypy_cmd, cwd=file_dir
    )

    if not success:
        qa_results["mypy_status"] = "failed"
        qa_results["errors"].append(
            f"MyPy execution failed: {stderr}. You need to perform code linting and QA by manually running `ruff`, `black` and `mypy` tools."
        )
    else:
        if return_code == 0:
            qa_results["mypy_status"] = "passed"
        else:
            qa_results["mypy_status"] = "failed"
            qa_results["errors"].append(
                f"MyPy found errors: {stderr}. You need to perform code linting and QA by manually running `ruff`, `black` and `mypy` tools."
            )

    return qa_results


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

    This tool verifies that each search text appears exactly once in the file to ensure
    the correct section is modified. If a search text appears multiple times or isn't
    found, it will report an error.

    Automatic QA Pipeline for Python files (.py):
    After successful patching, this tool automatically runs:
    - Ruff: Linting and auto-fixing (may run multiple times if Black reformats)
    - Black: Code formatting (may trigger additional Ruff checks)
    - MyPy: Type checking

    QA results are appended to the response, showing any issues found or confirming clean code.
    For non-Python files, only the patch success message is returned.
    If patching fails, only patch error information is returned (no QA is performed).
    """
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
    if not pp.exists() or not pp.is_file():
        raise FileNotFoundError(f"File {file_path} does not exist")

    # Read the current file content
    with open(pp, "r", encoding="utf-8") as f:
        original_content = f.read()

    try:
        # Parse multiple search-replace blocks
        blocks = parse_search_replace_blocks(patch_content)
        if not blocks:
            raise ValueError(
                "No valid search-replace blocks found in the patch content"
            )

        eprint(f"Found {len(blocks)} search-replace blocks")

        # Apply each block sequentially
        current_content = original_content
        applied_blocks = 0

        for i, (search_text, replace_text) in enumerate(blocks):
            eprint(f"Processing block {i+1}/{len(blocks)}")

            # Check exact match count
            count = current_content.count(search_text)

            if count == 1:
                # Exactly one match - perfect!
                eprint(f"Block {i+1}: Found exactly one exact match")
                current_content = current_content.replace(search_text, replace_text)
                applied_blocks += 1

            elif count > 1:
                # Multiple matches - too ambiguous
                raise ValueError(
                    f"Block {i+1}: The search text appears {count} times in the file. "
                    "Please provide more context to identify the specific occurrence."
                )

            else:
                # No match found
                raise ValueError(
                    f"Block {i+1}: Could not find the search text in the file. "
                    "Please ensure the search text exactly matches the content in the file."
                )

        # Write the final content back to the file
        with open(pp, "w", encoding="utf-8") as f:
            f.write(current_content)

        # QA Pipeline: Only run after successful file patching AND only on Python files
        # This ensures we don't bother the user with QA info when patching fails
        patch_result = (
            f"Successfully applied {applied_blocks} patch blocks to {file_path}"
        )

        # Only run QA for Python files (.py extension)
        if pp.suffix == ".py":
            eprint(f"Running Python QA pipeline for {file_path}")

            # Find virtual environment
            python_exe = find_venv_directory(file_path)
            if python_exe:
                eprint(f"Found Python executable: {python_exe}")

                # Run QA pipeline
                qa_results = run_python_qa_pipeline(file_path, python_exe)

                # Format QA results for response
                qa_summary = "\n\nQA Results:\n"
                qa_summary += f"- Iterations used: {qa_results['iterations_used']}\n"

                if qa_results["ruff_status"]:
                    qa_summary += f"- Ruff: {qa_results['ruff_status']}\n"
                if qa_results["black_status"]:
                    qa_summary += f"- Black: {qa_results['black_status']}\n"
                if qa_results["mypy_status"]:
                    qa_summary += f"- MyPy: {qa_results['mypy_status']}\n"

                if qa_results["errors"]:
                    qa_summary += "\nQA Errors:\n"
                    for error in qa_results["errors"]:
                        qa_summary += f"- {error}\n"

                if qa_results["warnings"]:
                    qa_summary += "\nQA Warnings:\n"
                    for warning in qa_results["warnings"]:
                        qa_summary += f"- {warning}\n"

                patch_result += qa_summary
            else:
                patch_result += "\n\nQA Warning: No virtual environment (.venv or venv) found. Skipping Python QA checks. You need to perform code linting and QA by manually running `ruff`, `black` and `mypy` tools."

        return patch_result

    except Exception as e:
        raise RuntimeError(f"Failed to apply patch: {str(e)}")
