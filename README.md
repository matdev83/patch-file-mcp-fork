# Patch File MCP

An MCP Server to patch existing files using unified diff format. This allows AI agents (like Claude) to make precise changes to files in your projects.

## Overview

Patch File MCP provides a simple way to modify files by applying patches in unified diff format. The key benefits include:

- Makes targeted changes to specific parts of files without rewriting the entire content
- Supports multiple patches to the same file
- Safer than complete file rewrites since it only affects the specified sections
- Better alternative to the `edit_block` tool from `desktop-commander` for most file editing tasks

## Installation

### Local installation

#### Prerequisites

- Python 3.11 or higher
- Pip package manager

#### Install from PyPI

```bash
pip install patch-file-mcp
```

#### Install from Source

```bash
git clone https://github.com/your-username/patch-file-mcp.git
cd patch-file-mcp
pip install -e .
```

## Usage

The MCP server is started by the client (e.g., Claude Desktop) based on the configuration you provide. You don't need to start the server manually.

### Integration with Claude Desktop

To use this MCP server with Claude Desktop, you need to add it to your `claude_desktop_config.json` file:

#### Using uvx (Recommended)

This method uses `uvx` (from the `uv` Python package manager) to run the server without permanent installation:

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

#### Using pip installed version

If you've installed the package with pip:

```json
{
  "mcpServers": {
    "patch-file": {
      "command": "patch-file-mcp",
      "args": [
        "--allowed-dir", "/Users/your-username/projects",
        "--allowed-dir", "/Users/your-username/Documents/code"
      ]
    }
  }
}
```

### Configuring Claude Desktop

1. Install Claude Desktop from the [official website](https://claude.ai/desktop)
2. Open Claude Desktop
3. From the menu, select Settings → Developer → Edit Config
4. Add the MCP configuration above to your existing config (modify paths as needed)
5. Save and restart Claude Desktop

## Tools

Patch File MCP provides one main tool:

### patch_file

Updates a file by applying a unified diff/patch to it.

```
patch_file(file_path: str, patch_content: str)
```

**Parameters:**
- `file_path`: Path to the file to be patched
- `patch_content`: Unified diff/patch content to apply to the file

**Notes:**
- The file must exist and be within an allowed directory
- The patch must be in valid unified diff format
- If the patch fails to apply, an error is raised

## Example Workflow

1. Begin a conversation with Claude about modifying a file in your project
2. Claude generates a unified diff/patch that makes the desired changes
3. Claude uses `patch_file` to apply these changes to your file
4. If the patch fails, Claude might suggest using `write_file` from another MCP as an alternative

## Creating Unified Diffs

A unified diff typically looks like:

```
--- oldfile
+++ newfile
@@ -start,count +start,count @@
 context line
-removed line
+added line
 context line
```

Claude can generate these diffs automatically when suggesting file changes.

## Recent Changes

### 2025-04-23 Bugfixes
- Fixed an issue where the patch operation would fail with "Not a directory" error when trying to apply patches.
- Updated the patching logic to use the parent directory as the root for patch application, rather than the file itself.

## Security Considerations

- All file operations are restricted to allowed directories
- The tool only modifies specified sections of files
- Each patch operation is validated before being applied

## Dependencies

- fastmcp (>=2.2.0, <3.0.0)
- patch-ng (>=1.18.0, <2.0.0)

## License

MIT