# Patch File MCP

An MCP Server to patch existing files using block format. This allows AI agents (like Claude) to make precise changes to files in your projects.

> **Note**: This is a fork of the original [PyneSys/patch-file-mcp](https://github.com/PyneSys/patch-file-mcp) repository, maintained by [@matdev83](https://github.com/matdev83). This fork includes critical security enhancements not present in the original: mandatory `--allowed-dir` chroot-like sandboxing and administrative privilege protection.

## Overview

Patch File MCP provides a secure and intelligent way to modify files using block format patches. The key benefits include:

- Makes targeted changes to specific parts of files without rewriting the entire content
- Supports multiple patches to the same file in a single request
- Ensures safety through exact text matching and uniqueness verification
- **Fork-exclusive security**: Administrative privilege protection prevents running with root/admin access
- **Mandatory sandboxing**: Chroot-like directory enforcement prevents unauthorized file access (fork enhancement)
- **Enhanced security**: Robust path validation and sandboxing for allowed directories
- **Cross-platform compatibility**: Handles Windows, MacOS, and Linux path formats seamlessly
- **Automatic code quality**: Integrated QA pipeline (ruff, black, mypy) for Python files
- **Smart context management**: Clean responses with no clutter for non-Python files
- **Comprehensive logging**: File-only logging with configurable verbosity for debugging and audit trails
  - **Enhanced DEBUG logging**: Extremely detailed parameter logging when DEBUG level is enabled
- Better alternative to the `edit_block` tool from `desktop-commander` for most file editing tasks

## Latest Developments

### 🔒 **Administrative Privilege Protection**

This fork includes a critical security enhancement not present in the original patch-file-mcp server:

- **Privilege Check at Startup**: Server automatically detects and refuses to run with administrative/root privileges
- **OS-Agnostic Security**: Works across Windows (Administrator), Linux (root), and macOS (root)
- **Fail-Safe Design**: If privilege detection fails, defaults to safe behavior (no elevated access)
- **Clear Error Messages**: Provides helpful guidance when administrative access is detected

This prevents potential system damage by ensuring the server operates with minimal necessary permissions.

### 🚀 **Enhanced Path Security & Cross-Platform Support**

The latest version includes significant improvements to path handling and security:

- **Mandatory Directory Sandboxing**: Chroot-like enforcement requires `--allowed-dir` specification (fork enhancement)
- **Universal Path Normalization**: Handles all path formats regardless of input method:
  - Windows backslashes: `C:\path\to\file`
  - Escaped backslashes: `C:\\path\\to\\file`
  - Unix forward slashes: `C:/path/to/file`
  - Mixed separators: `C:\path/to\file`
  - All normalize to OS-native format automatically

- **Robust Directory Validation**: Startup validation ensures:
  - All allowed directories exist
  - Read/write permissions are verified
  - Server exits gracefully with clear error messages if validation fails

- **Enhanced Sandboxing**: File access restricted to explicitly allowed directories with recursive subdirectory support

### 🔧 **Automatic Python QA Pipeline**

For Python files (.py), the server now automatically runs a comprehensive code quality pipeline:

- **Ruff**: Linting and auto-fixing (may run multiple iterations if Black reformats)
- **Black**: Code formatting with intelligent re-run detection
- **MyPy**: Type checking with detailed error reporting

Results are seamlessly integrated into the patch response, showing either clean code confirmation or specific issues to address.

### 🛡️ **Binary File Extension Security**

This fork includes a critical security enhancement that prevents patch attempts on binary files, protecting against data corruption and security issues:

- **Comprehensive Binary File Detection**: Blocks patch operations on 50+ binary file extensions including:
  - **Executables & Libraries**: `.exe`, `.dll`, `.so`, `.dylib`, `.lib`, `.a`, `.o`, `.obj`
  - **Documents**: `.pdf`, `.doc`, `.docx`, `.xls`, `.xlsx`, `.ppt`, `.pptx`, `.odt`, `.ods`, `.odp`, `.rtf`
  - **Media Files**: `.mp3`, `.mp4`, `.avi`, `.mkv`, `.mov`, `.wmv`, `.flv`, `.wav`, `.aac`, `.ogg`, `.wma`, `.flac`, `.m4a`, `.m4v`, `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.tiff`, `.tif`, `.webp`, `.svg`, `.ico`, `.raw`, `.psd`, `.ai`, `.eps`
  - **Archives**: `.zip`, `.rar`, `.7z`, `.tar`, `.gz`, `.bz2`, `.xz`, `.cab`, `.iso`, `.dmg`, `.deb`, `.rpm`
  - **System Files**: `.bin`, `.dat`, `.db`, `.sqlite`, `.mdb`, `.accdb`, `.reg`, `.sys`, `.drv`, `.ocx`, `.cpl`, `.scr`
  - **Additional**: `.msi`, `.pkg`, `.app`, `.dmg`, `.appx`, `.snap`, `.ld`, `.elf`, `.coff`, `.pe`, `.mach-o`, `.class`, `.jar`, `.war`, `.ear`, `.swf`, `.fla`, `.xap`

- **Case-Insensitive Detection**: Automatically handles extensions regardless of case (`.EXE`, `.exe`, `.Exe` all blocked)
- **Text File Allowance**: Permits editing of all text-based files (`.txt`, `.py`, `.js`, `.html`, `.css`, `.json`, `.xml`, `.md`, `.yml`, `.yaml`, `.toml`, `.ini`, `.cfg`, `.log`, `.sh`, `.bat`, `.ps1`, etc.)
- **Files Without Extensions**: Allows editing of files without extensions (treated as text files)
- **Clear Error Messages**: Returns specific rejection message: `"Rejected: patch_file tool should only be used to edit text files. Editing of binary files is not supported"`
- **Safe Input Handling**: Gracefully handles malformed paths and empty inputs (defaults to blocking for safety)
- **Audit Logging**: Logs all binary file rejection attempts for security monitoring

**Security Impact**: Prevents accidental corruption of binary files and blocks potential security exploits that could manipulate binary data through text-based patch operations.

### 🧹 **Context Window Optimization**

- **Clean Non-Python Responses**: No unnecessary QA messages for text, markdown, JSON, etc.
- **Focused Information**: Only relevant feedback based on file type and operation success
- **Reduced Clutter**: Streamlined responses for better AI agent context management

## Installation

### Using uvx

This method uses `uvx` (from the `uv` Python package manager) to run the server without permanent installation:

#### Prerequisites

Install `uvx` from [uv](https://docs.astral.sh/uv/installation/) if you don't have it already.

#### Set up MCP Client (Claude Desktop, Cursor, etc.)

Merge the following config with your existing config file (e.g. `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "patch-file": {
      "command": "uvx",
      "args": [
        "patch-file-mcp",
        "--allowed-dir", "/Users/your-username/projects",
        "--allowed-dir", "/Users/your-username/Documents/code",
        "--log-file", "/Users/your-username/logs/patch-file.log",
        "--log-level", "INFO"
      ]
    }
  }
}
```

> **Note:** Replace `/Users/your-username` with the actual path to your own projects and code directories.

### Install from Source

#### Prerequisites

- Python 3.11 or higher
- Pip package manager

#### Clone the repository

```bash
git clone https://github.com/matdev83/patch-file-mcp-fork.git
cd patch-file-mcp-fork
python -m venv venv
source venv/bin/activate
pip install -e .
```

#### Set up MCP Client (Claude Desktop, Cursor, etc.)

Merge the following config with your existing config file (e.g. `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "patch-file": {
      "command": "path/to/your/venv/bin/patch-file-mcp",
      "args": [
        "--allowed-dir", "/Users/your-username/projects",
        "--allowed-dir", "/Users/your-username/Documents/code",
        "--log-file", "/Users/your-username/logs/patch-file.log",
        "--log-level", "INFO"
      ]
    }
  }
}
```

> **Note:** Replace `/Users/your-username` with the actual path to your own projects and code directories.

## Arguments

### `--log-file PATH` - **Logging Configuration**

Specify the path to the log file where all logging output will be written. The logs directory will be created automatically if it doesn't exist.

**Default:** `logs/app.log`

**Example:**
```bash
./server --allowed-dir /path/to/projects --log-file /var/log/patch-file.log
```

### `--log-level LEVEL` - **Logging Verbosity**

Set the logging verbosity level. Only messages at or above this level will be logged.

**Available Levels:**
- `DEBUG`: Detailed diagnostic information (most verbose)
- `INFO`: General information messages (default)
- `WARNING`: Warning messages
- `ERROR`: Error messages
- `CRITICAL`: Critical error messages (least verbose)

**Default:** `INFO`

**Example:**
```bash
./server --allowed-dir /path/to/projects --log-level DEBUG
```

### `--allowed-dir` (Required) - **Fork-Specific Security Enhancement**

> **🚨 Critical Security Feature**: This mandatory directory restriction is a **fork-exclusive enhancement** not present in the original patch-file-mcp server. It provides chroot-like sandboxing to prevent unauthorized file system access.

The `--allowed-dir` argument specifies the directories the server can access for file operations. This is a **required parameter** - at least one must be provided.

**Key Security Features:**
- **Mandatory Sandboxing**: Server **cannot start** without specifying allowed directories (fork enhancement)
- **Chroot-like Enforcement**: Acts as a security boundary preventing access outside specified directories
- **Multiple directories**: Use `--allowed-dir` multiple times for different paths
- **Recursive access**: All subdirectories within allowed directories are accessible
- **Cross-platform**: Handles all path formats (Windows, Unix, mixed separators)
- **Universal input**: Accepts any of these formats:
  - Windows: `C:\Users\Projects`
  - Unix: `/home/user/projects`
  - Escaped: `C:\\Users\\Projects`
  - Mixed: `C:\Users/Projects`

**Startup Validation:**
- Server validates all directories exist at startup
- Checks read/write permissions for each directory
- Exits with clear error messages if validation fails

**Enhanced Security (Fork-Specific):**
- Files outside allowed directories are **rejected with permission errors**

### QA Controls (Optional)

The server can run QA after successful edits to Python files. Use these flags to control QA steps:

- `--no-ruff`: Skip Ruff checks and autofix.
- `--no-black`: Skip Black formatting.
- `--no-mypy`: Skip MyPy type checking entirely.
- `--no-mypy-on-tests`: Skip MyPy only when the target file path contains `tests` (overridden by `--no-mypy`).

Defaults: all QA steps enabled. Example configurations:

```bash
# Run without Ruff
patch-file-mcp --allowed-dir /path/to/projects --no-ruff

# Run without MyPy for tests only
patch-file-mcp --allowed-dir /path/to/projects --no-mypy-on-tests

# Disable Black and MyPy entirely
patch-file-mcp --allowed-dir /path/to/projects --no-black --no-mypy
```

Notes:
- QA only runs after a successful write to a `.py` file.
- Per-tool timeout defaults to 15s. Total QA wall time defaults to 20s.
- Path normalization ensures consistent security regardless of input format
- **Zero-trust sandboxing** prevents access to unauthorized file system locations
- **Mandatory enforcement** - no bypass possible without modifying the server code

**Example:**
```bash
# Multiple directories with different path formats
./server --allowed-dir C:\Projects --allowed-dir /home/user/docs --allowed-dir "D:\\Work Files"
```

## Logging

This fork includes comprehensive logging capabilities for debugging, diagnostics, and audit purposes. All logging output is written exclusively to file, ensuring no output appears on STDOUT or STDERR.

### Logging Features

- **File-Only Output**: Logging never emits to console, preventing interference with MCP protocol
- **Automatic Directory Creation**: Log directory is created automatically if it doesn't exist
- **Structured Format**: Timestamps, log levels, function names, and line numbers included
- **Guarded Logging**: All log calls check runtime level before execution for optimal performance
- **Cross-Platform**: Works identically on Windows, macOS, and Linux

### Default Configuration

- **Log File**: `logs/app.log`
- **Log Level**: `INFO`
- **Format**: `%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s`

### Log Levels

Choose the appropriate log level based on your needs:

- **DEBUG**: Most verbose, includes detailed diagnostic information, function calls, and variable values
  - **Enhanced DEBUG Logging**: When DEBUG level is enabled, the `patch_file` tool provides extremely detailed logging including:
    - Full input parameters (file_path, patch_content with preview)
    - File validation and path resolution details
    - Original file content preview and metadata
    - Search-replace block parsing with full text content
    - Block-by-block processing with match counts and replacement details
    - File writing operations and content changes
    - QA pipeline execution details for Python files
    - Exception handling with full tracebacks
- **INFO**: General operational messages, successful operations, and important milestones
- **WARNING**: Potentially harmful situations or unexpected events that don't stop operation
- **ERROR**: Error conditions that might allow continued operation but should be investigated
- **CRITICAL**: Critical errors that require immediate attention and may stop operation

### Log File Location

Logs are written to the specified file path. The directory structure is created automatically:

```bash
# Default location
logs/app.log

# Custom location
/var/log/patch-file-mcp/server.log

# Relative path
./logs/debug.log
```

### Viewing Logs

To monitor the server logs in real-time:

```bash
# Linux/macOS
tail -f logs/app.log

# Windows PowerShell
Get-Content logs/app.log -Wait
```

### Log Rotation

For production use, consider implementing log rotation to prevent log files from growing too large:

```bash
# Example: Rotate logs weekly, keep 4 weeks
# Linux/macOS with logrotate
/var/log/patch-file-mcp/*.log {
    weekly
    rotate 4
    compress
    missingok
    notifempty
}
```

## Usage

The MCP server is started by the client (e.g., Claude Desktop) based on the configuration you provide. You don't need to start the server manually.

### Tools

Patch File MCP provides one main tool:

#### patch_file

Update an existing file using a simple block format. Use absolute paths.

```python
patch_file(file_path: str, patch_content: str)
```
- **file_path**: Absolute path to the file to be patched (Windows: `C:/path/file.py` or `C:\\path\\file.py`; Unix: `/path/file.py`). Relative paths are rejected.
- **patch_content**: Content to search and replace using block format with SEARCH/REPLACE markers. Multiple blocks are supported.

The patch content must have the following format:

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

This tool verifies that each SEARCH block matches exactly once; otherwise it errors.

QA note: If the file is Python, the response also includes a brief linter/formatter/type-check summary alongside patch status.

## Example Workflow

1. Begin a conversation with Claude about modifying a file in your project
2. Claude generates a block format patch that makes the desired changes
3. Claude uses `patch_file` to apply these changes to your file
4. **For Python files**: Automatic QA runs (Ruff → Black → MyPy) and results are included
5. **For other files**: Clean success message is returned
6. If the patch fails, Claude provides detailed error information to help you fix the issue


## Security Considerations

### 🔒 **Enhanced Security Features**

- **Administrative Privilege Protection**: Server refuses to start with root/admin privileges (fork-specific enhancement)
- **Mandatory Chroot-like Sandboxing**: `--allowed-dir` creates security boundary preventing access outside specified directories (fork-exclusive)
- **Zero-Trust Directory Restrictions**: Server cannot start without explicit directory permissions (fork enhancement)
- **Startup Validation**: All allowed directories are validated for existence and permissions at server start
- **Path Normalization**: All input paths are normalized to prevent format-based security bypasses
- **Recursive Sandboxing**: Access is restricted to allowed directories and their subdirectories
- **Cross-Platform Security**: Security policies work identically across Windows, MacOS, and Linux

### 🛡️ **Administrative Privilege Protection**

This fork-specific security feature prevents the server from running with elevated privileges:

- **OS Detection**: Automatically detects administrative access on:
  - **Windows**: Uses Windows API to check Administrator status
  - **Linux/macOS**: Checks effective user ID for root access (uid 0)
- **Early Exit**: Privilege check runs before any server initialization
- **Error Handling**: Provides clear error messages and exits with code 1 if privileges detected
- **Fail-Safe**: If privilege detection fails, defaults to safe behavior (assumes no privileges)

**Security Impact**: Prevents potential system damage by ensuring operations run with minimal required permissions.

### 🛡️ **Chroot-like Directory Sandboxing**

This fork-exclusive security feature provides mandatory directory restrictions that act like a chroot jail:

- **Mandatory Configuration**: Server **cannot start** without specifying at least one `--allowed-dir`
- **Security Boundary**: Creates an impenetrable boundary preventing access outside allowed directories
- **Zero-Trust Model**: No implicit trust - all file operations must be within explicitly allowed directories
- **Recursive Protection**: Subdirectories of allowed directories are accessible, but parent directories are not
- **Startup Enforcement**: Directory validation occurs before any server operations begin
- **Fail-Safe Behavior**: Server exits with clear error if directories don't exist or lack permissions

**Security Impact**: Provides chroot-equivalent protection without requiring actual chroot system calls, ensuring the server operates within a controlled file system sandbox.

### 🛡️ **Binary File Protection**

- **Comprehensive Extension Blocking**: Prevents patch operations on 50+ binary file types to avoid data corruption
- **Case-Insensitive Detection**: Blocks binary files regardless of extension case (`.EXE`, `.exe`, `.Exe`)
- **Text File Allowance**: Permits editing of all text-based file formats and files without extensions
- **Clear Rejection Messages**: Provides specific error messages when binary files are targeted
- **Safe Default Behavior**: Defaults to blocking for malformed inputs to ensure security

### 🛡️ **File Operation Security**

- **Exact Text Matching**: Search texts must appear exactly once to prevent ambiguous modifications
- **File Existence Validation**: Files are verified to exist before any operations
- **Permission Checking**: Write permissions are validated before file modifications
- **Atomic Operations**: File changes are applied atomically to prevent corruption

### 📊 **Error Handling & Reporting**

- **Detailed Error Messages**: Clear feedback for configuration and runtime issues
- **Graceful Degradation**: Server exits cleanly with helpful error messages on validation failures
- **Input Validation**: All user inputs are validated and sanitized
- **Audit Trail**: Comprehensive logging for security monitoring

## Advantages over similar tools

- **Multiple blocks in one operation**: Can apply several changes in a single call
- **Safety checks**: Ensures the correct sections are modified through exact matching
- **Detailed errors**: Provides clear feedback when patches can't be applied
- **Fork-exclusive privilege protection**: Prevents running with administrative/root access (not in original)
- **Chroot-like sandboxing**: Mandatory `--allowed-dir` creates security boundary (not in original)
- **Binary file protection**: Prevents patch operations on 50+ binary file types to avoid data corruption (fork-exclusive)
- **Enhanced Security**: Mandatory directory sandboxing with cross-platform path normalization
- **Automatic QA**: Integrated code quality pipeline for Python files (ruff, black, mypy)
- **Context Optimization**: Clean responses that don't clutter AI agent context windows
- **Cross-Platform**: Works identically on Windows, MacOS, and Linux
- **Professional Testing**: Comprehensive test suite with 75%+ pass rate and coverage reporting

## Testing

Patch File MCP includes a comprehensive test suite to ensure reliability and quality.

### Running Tests

```bash
# Install test dependencies
pip install -e .[test]

# Run all tests
python run_tests.py

# Run with coverage
pytest tests/ --cov=src/patch_file_mcp --cov-report=html

# Run specific test categories
pytest tests/ -m unit        # Unit tests only
pytest tests/ -m integration # Integration tests only
```

### Test Coverage

The test suite covers:
- ✅ Virtual environment detection and isolation
- ✅ QA pipeline execution (ruff, black, mypy) with iteration handling
- ✅ File patching functionality with multiple blocks
- ✅ Error handling and edge cases
- ✅ Cross-platform path normalization (Windows/Unix/mixed separators)
- ✅ Directory validation and security sandboxing
- ✅ **Binary file extension security** - Comprehensive testing of 50+ binary file type blocking
- ✅ **Binary file rejection integration** - Verifies patch_file properly rejects binary files
- ✅ **Text file allowance verification** - Ensures text files still work after security implementation
- ✅ MCP configuration and integration testing
- ✅ **STDOUT/STDERR logging isolation** - Ensures logging never leaks to console output
- ✅ **File-only logging verification** - Confirms all logging goes to designated log files
- ✅ **Guarded logging performance** - Validates logging level checks work correctly
- ✅ **DEBUG logging output verification** - Confirms DEBUG logging produces actual log output

**Test Results**: 78/78 passing tests (100% success rate) with comprehensive coverage reporting.

See [tests/README.md](tests/README.md) for detailed information about the test suite.

## Dependencies

### Core Dependencies
- fastmcp (>=2.2.0, <3.0.0)

### Test Dependencies (Optional)
For running the test suite, install with:
```bash
pip install -e .[test]
```

Includes:
- pytest (>=7.0.0)
- pytest-cov (>=4.0.0)
- pytest-mock (>=3.10.0)

## License

MIT
