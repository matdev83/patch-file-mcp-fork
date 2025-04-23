#! /usr/bin/env python3
import sys
import argparse
import re
from pathlib import Path

from fastmcp import FastMCP
from pydantic.fields import Field
import patch_ng


mcp = FastMCP(
    name="Patch File MCP",
    instructions=f"""
This MCP is for patching existing files.
This can be used to patch files in projects, if project is specified, and the full path to the project
is provided. This should be used most of the time instead of `edit_block` tool from `desktop-commander`.
It can be used to patch multiple parts of the same file.
"""
)

allowed_directories = []


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def main():
    # Process command line arguments
    global allowed_directories
    parser = argparse.ArgumentParser(description="Project Memory MCP server")
    parser.add_argument(
        '--allowed-dir',
        action='append',
        dest='allowed_dirs',
        required=True,
        help='Allowed base directory for project paths (can be used multiple times)'
    )
    args = parser.parse_args()
    allowed_directories = [str(Path(d).resolve()) for d in args.allowed_dirs]

    if not allowed_directories:
        allowed_directories = [str(Path.home().resolve())]

    eprint(f"Allowed directories: {allowed_directories}")

    # Run the MCP server
    mcp.run()


if __name__ == "__main__":
    main()


#
# Tools
#

@mcp.tool()
def patch_file(
    file_path: str = Field(description="The path to the file to patch"),
    patch_content: str = Field(description="Unified diff/patch to apply to the file.")
):
    """
    Update the file by applying a unified diff/patch to it.
    The patch must be in unified diff format and will be applied to the current file content.
    """
    pp = Path(file_path).resolve()
    if not pp.exists() or not pp.is_file():
        raise FileNotFoundError(f"File {file_path} does not exist")
    if not any(str(pp).startswith(base) for base in allowed_directories):
        raise PermissionError(f"File {file_path} is not in allowed directories")

    # Extract all hunks (sections starting with @@)
    # First try to find all hunks in the patch content
    hunks = re.findall(r'@@[^@]*(?:\n(?!@@)[^\n]*)*', patch_content)
    
    if not hunks:
        # If no complete hunks found, check if the patch itself is a single hunk
        if patch_content.strip().startswith("@@"):
            hunks = [patch_content.strip()]
        else:
            raise RuntimeError(
                "No valid patch hunks found. Make sure the patch contains @@ line markers.\n"
                "You can use `write_file` tool to write the whole file content instead."
            )
    
    # Join all hunks and create a standardized patch with proper headers
    hunks_content = '\n'.join(hunks)
    filename = pp.name
    standardized_patch = f"--- {filename}\n+++ {filename}\n{hunks_content}"
    eprint(f"Created standardized patch for {filename}")

    # Ensure patch_content is properly encoded
    encoded_content = standardized_patch.encode("utf-8")
    patchset = patch_ng.fromstring(encoded_content)
    if not patchset:
        raise RuntimeError(
            "Failed to parse patch string. You can use `write_file` tool to write the "
            "whole file content instead.\n"
            "Make sure the patch follows the unified diff format with @@ line markers."
        )
    
    # Use the parent directory as root and the filename for patching
    parent_dir = str(pp.parent)
    success = patchset.apply(root=parent_dir)
    
    if not success:
        raise RuntimeError(
            "Failed to apply patch to file. Use `write_file` tool to write the "
            "whole file content instead.\n"
            "Check that the patch lines match the target file content."
        )
