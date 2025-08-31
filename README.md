# Patch File MCP

An MCP Server to patch existing files using block format. This allows AI agents (like Claude) to make precise changes to files in your projects.

## Overview

Patch File MCP provides a secure and intelligent way to modify files using block format patches. The key benefits include:

- Makes targeted changes to specific parts of files without rewriting the entire content
- Supports multiple patches to the same file in a single request
- Ensures safety through exact text matching and uniqueness verification
- Cross-platform compatibility: Handles Windows, MacOS, and Linux path formats seamlessly
- Better alternative to the `edit_block` tool from `desktop-commander` for most file editing tasks

**This fork includes extensive enhancements** that transform the basic file patching functionality into a comprehensive, secure, and intelligent development tool. See the [Fork-Exclusive Features](#-fork-exclusive-features) section below for details on all enhancements.

## Why This Fork

Modern agents frequently fail at char‑precise, in‑place string edits. This is especially visible with the Gemini 2.5 family, which is excellent overall but unreliable at exact file mutations when given free‑form instructions. After testing multiple edit encodings across models, a structured block‑based approach with explicit SEARCH/REPLACE markers provided the highest cross‑model success rate and dramatically improved edit reliability for Gemini while remaining friendly to other models.

Because I work extensively in Python, I also found that running automated QA immediately after each successful Python edit catches errors at the moment they are introduced. This allows the agent to fix issues while the context window is still focused on the task, reducing round trips and avoiding context pollution that would otherwise include separate tool calls and their outputs. Automated QA (Ruff → Black → MyPy) improves quality, shortens feedback loops, and keeps the agent’s context clean.

## 🚀 Fork-Exclusive Features

This fork provides extensive enhancements that transform the basic file patching functionality into a comprehensive, secure, and intelligent development tool. All features listed below are **exclusive to this fork** and not present in the original patch-file-mcp server.

### 🛡️ **Security Enhancements**

#### **Administrative Privilege Protection**
- **OS-Agnostic Privilege Detection**: Automatically detects and refuses to run with administrative/root privileges on Windows (Administrator), Linux (root), and macOS (root)
- **Early Exit Strategy**: Privilege check runs before any server initialization
- **Fail-Safe Design**: Defaults to safe behavior if privilege detection fails
- **Clear Error Messages**: Provides helpful guidance when administrative access is detected

#### **Mandatory Directory Sandboxing**
- **Chroot-like Enforcement**: Creates impenetrable security boundaries preventing access outside specified directories
- **Zero-Trust Model**: No implicit trust - all file operations must be within explicitly allowed directories
- **Startup Validation**: Server validates directory existence and permissions before any operations
- **Recursive Protection**: Subdirectories of allowed directories are accessible, but parent directories are not

#### **Binary File Protection**
- **Comprehensive Extension Blocking**: Prevents patch operations on 50+ binary file types to avoid data corruption
- **Case-Insensitive Detection**: Blocks binary files regardless of extension case (.EXE, .exe, .Exe all blocked)
- **Safe Input Handling**: Gracefully handles malformed paths with safe defaults
- **Audit Logging**: Logs all binary file rejection attempts for security monitoring

### 🧠 **Intelligent Agent Steering**

#### **Failed Edit Attempt Tracking**
- **Smart Failure Detection**: Tracks consecutive failed file edit attempts with detailed metadata
- **Progressive Awareness Messages**: Provides contextual guidance to prevent repetitive failures
- **Automatic History Cleanup**: Failed edit history is completely cleared on successful file edits
- **Memory-Efficient Storage**: In-memory only with automatic garbage collection

#### **Mypy Failure Suppression**
- **Consecutive Failure Monitoring**: Tracks consecutive mypy failures per file independently of file edit status
- **Intelligent Suppression**: After 3+ consecutive mypy failures, silently removes mypy information from tool output
- **Focus Enhancement**: Helps agents avoid getting distracted by repeated mypy failures
- **Automatic Reset**: Mypy failure count resets to 0 when mypy passes

#### **Memory Management**
- **Automatic Garbage Collection**: Every 100 tool calls, removes failed edit history older than 1 hour
- **Memory Bounded Operation**: Prevents memory bloat from historical data accumulation
- **Performance Optimized**: Garbage collection is lightweight and doesn't impact normal operation
- **Cross-Feature Cleanup**: Cleans up both failed edit history and mypy failure counts

### 🔧 **Usability & Quality Enhancements**

#### **Automatic Python QA Pipeline**
- **Integrated Code Quality**: Runs Ruff → Black → MyPy pipeline automatically after successful Python file edits
- **Real-time Error Detection**: Catches errors immediately, allowing agents to fix issues while context is fresh
- **Quality Assurance**: Ensures code quality standards are maintained throughout development
- **Context Preservation**: Keeps agent context clean by handling QA within the same interaction

#### **Enhanced Path Handling**
- **Universal Path Normalization**: Handles all path formats regardless of input method
- **Cross-Platform Compatibility**: Works identically on Windows, MacOS, and Linux
- **Robust Input Processing**: Accepts Windows backslashes, Unix forward slashes, and mixed separators
- **Consistent Security**: Security policies work identically across all supported path formats

#### **Advanced Logging System**
- **File-Only Output**: Logging never interferes with MCP protocol communication
- **Configurable Verbosity**: Multiple log levels from DEBUG to CRITICAL
- **Structured Format**: Timestamps, log levels, function names, and line numbers included
- **Performance Optimized**: Guarded logging prevents unnecessary string formatting

### 🎯 **Impact Summary**

These fork-exclusive features provide:
- **Security**: Administrative privilege protection, mandatory sandboxing, binary file protection
- **Intelligence**: Failed edit tracking, mypy suppression, automatic QA pipeline
- **Usability**: Enhanced path handling, advanced logging, memory management
- **Productivity**: Helps AI agents work more effectively and avoid repetitive failures

**Total**: 15+ major enhancements, all exclusive to this fork.

## Latest Developments

*This section tracks recent updates and improvements to the fork. For a complete list of all fork-exclusive features, see the [Fork-Exclusive Features](#-fork-exclusive-features) section above.*

### 🎯 **Recent Feature Additions**

#### **Agent Steering & Awareness System (Latest)**
- **Failed Edit Attempt Tracking**: Intelligent monitoring of consecutive file edit failures with progressive guidance
- **Mypy Failure Suppression**: Automatic suppression of mypy output after repeated failures to maintain agent focus
- **Memory Management**: Automatic garbage collection system for optimal performance

*These features work together to dramatically improve AI agent productivity and reduce repetitive failure cycles.*

### 🔄 **Continuous Improvements**

*This fork is actively maintained with ongoing enhancements. Recent updates focus on improving AI agent productivity and system reliability.*

#### **Future Roadmap**
- Enhanced error recovery mechanisms
- Additional QA tool integrations
- Performance optimizations for large file operations
- Extended binary file type detection

*All existing features are stable and production-ready. Check the [Fork-Exclusive Features](#-fork-exclusive-features) section for the complete list of enhancements.*

## Installation

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
- `--run-mypy-on-tests`: Run MyPy even when the target file path contains `tests` (overridden by `--no-mypy`).

Defaults: Ruff, Black, and MyPy are enabled. MyPy is skipped on test files by default. Example configurations:

```bash
# Run without Ruff
patch-file-mcp --allowed-dir /path/to/projects --no-ruff

# Run MyPy on test files too
patch-file-mcp --allowed-dir /path/to/projects --run-mypy-on-tests

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

*For comprehensive security information, see the [Fork-Exclusive Features](#-fork-exclusive-features) section above, which details all security enhancements including:*

### 🔒 **Key Security Features**

- **Administrative Privilege Protection**: Prevents running with elevated privileges
- **Mandatory Directory Sandboxing**: Chroot-like enforcement of directory restrictions
- **Binary File Protection**: Comprehensive blocking of 50+ binary file types
- **Cross-Platform Path Security**: Consistent security policies across all platforms
- **Startup Validation**: All security measures validated before server operation
- **Audit Logging**: Comprehensive security event logging

### 🛡️ **Security Philosophy**

This fork implements a **defense-in-depth** security approach with multiple layers of protection:

1. **Prevention**: Administrative privilege detection and directory sandboxing prevent unauthorized access
2. **Protection**: Binary file blocking prevents data corruption and security exploits
3. **Detection**: Comprehensive logging provides audit trails for security monitoring
4. **Recovery**: Graceful error handling and fail-safe behaviors ensure system stability

**Security Impact**: The combination of these features provides enterprise-grade security for AI-assisted file operations, preventing both accidental damage and malicious exploitation.

## Advantages over similar tools

- **Multiple blocks in one operation**: Can apply several changes in a single call
- **Safety checks**: Ensures the correct sections are modified through exact matching
- **Detailed errors**: Provides clear feedback when patches can't be applied
- **Intelligent agent steering**: Failed edit tracking and progressive awareness messages prevent repetitive failures
- **Mypy failure suppression**: Automatically suppresses mypy output after repeated failures to maintain focus on main tasks
- **Memory management**: Automatic garbage collection prevents memory bloat from historical tracking data
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
- ✅ **Failed edit tracking** - Tests awareness messages and history management
- ✅ **Mypy failure suppression** - Tests consecutive failure tracking and silent suppression
- ✅ **Memory management** - Tests garbage collection and cleanup mechanisms
- ✅ **Agent steering features** - Tests intelligent guidance and focus enhancement
- ✅ MCP configuration and integration testing
- ✅ **STDOUT/STDERR logging isolation** - Ensures logging never leaks to console output
- ✅ **File-only logging verification** - Confirms all logging goes to designated log files
- ✅ **Guarded logging performance** - Validates logging level checks work correctly
- ✅ **DEBUG logging output verification** - Confirms DEBUG logging produces actual log output

**Test Results**: 139/139 passing tests (100% success rate) with comprehensive coverage reporting and 80%+ code coverage.

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

## Acknowledgements

Special thanks to Adam Wallner (https://github.com/wallneradam) for the original patch-file MCP server this project is forked from. If GitHub mentions are supported for READMEs: @wallneradam — thanks for the inspiration and groundwork.

## License

MIT
