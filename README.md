# Patch File MCP

An MCP Server to patch existing files using block format. This allows AI agents (like Claude) to make precise changes to files in your projects.

> **Note**: This is a fork of the original [PyneSys/patch-file-mcp](https://github.com/PyneSys/patch-file-mcp) repository, maintained by [@matdev83](https://github.com/matdev83).

## Overview

Patch File MCP provides a simple way to modify files by applying patches in block format. The key benefits include:

- Makes targeted changes to specific parts of files without rewriting the entire content
- Supports multiple patches to the same file in a single request
- Ensures safety through exact text matching and uniqueness verification
- Better alternative to the `edit_block` tool from `desktop-commander` for most file editing tasks
- **Automatic code quality checks** for Python files (ruff, black, mypy) after successful patching
- **Clean context window** with no unnecessary messages for non-Python files

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
        "--allowed-dir", "/Users/your-username/Documents/code"
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
        "--allowed-dir", "/Users/your-username/Documents/code"
      ]
    }
  }
}
```

> **Note:** Replace `/Users/your-username` with the actual path to your own projects and code directories.

## Arguments

The `--allowed-dir` argument is used to specify the directories that the server has access to. You can use it multiple times to allow access to multiple directories. All directories inside the allowed directories are also allowed.
It is optional. If not provided, the server will only have access to the home directory of the user running the server.

## Usage

The MCP server is started by the client (e.g., Claude Desktop) based on the configuration you provide. You don't need to start the server manually.

### Tools

Patch File MCP provides one main tool:

#### patch_file

Update the file by applying a patch/edit to it using block format with automatic code quality checks for Python files.

```python
patch_file(file_path: str, patch_content: str)
```
- **file_path**: Path to the file to be patched.
- **patch_content**: Content to search and replace in the file using block format with SEARCH/REPLACE markers. Multiple blocks are supported.

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

This tool verifies that each search text appears exactly once in the file to ensure the correct section is modified. If a search text appears multiple times or isn't found, it will report an error.

**For Python files (.py)**: After successful patching, this tool automatically runs:
- **Ruff**: Linting and auto-fixing (may run multiple times if Black reformats)
- **Black**: Code formatting (may trigger additional Ruff checks)
- **MyPy**: Type checking

QA results are included in the response, showing any issues found or confirming clean code.

**For non-Python files**: Only the patch success message is returned (no QA clutter).

## Example Workflow

1. Begin a conversation with Claude about modifying a file in your project
2. Claude generates a block format patch that makes the desired changes
3. Claude uses `patch_file` to apply these changes to your file
4. **For Python files**: Automatic QA runs (Ruff → Black → MyPy) and results are included
5. **For other files**: Clean success message is returned
6. If the patch fails, Claude provides detailed error information to help you fix the issue


## Security Considerations

- All file operations are restricted to allowed directories
- Search texts must appear exactly once in the file to ensure correct targeting
- Detailed error reporting helps identify and fix issues
- Each patch operation is validated before being applied

## Advantages over similar tools

- **Multiple blocks in one operation**: Can apply several changes in a single call
- **Safety checks**: Ensures the correct sections are modified through exact matching
- **Detailed errors**: Provides clear feedback when patches can't be applied

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
- ✅ Virtual environment detection
- ✅ QA pipeline execution (ruff, black, mypy)
- ✅ File patching functionality
- ✅ Error handling and edge cases
- ✅ Cross-platform compatibility

See [tests/README.md](tests/README.md) for detailed information about the test suite.

## Dependencies

- fastmcp (>=2.2.0, <3.0.0)

## License

MIT