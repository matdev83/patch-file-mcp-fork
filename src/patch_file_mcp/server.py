#! /usr/bin/env python3
import sys
import argparse
from pathlib import Path
import re

from fastmcp import FastMCP
from pydantic.fields import Field


mcp = FastMCP(
    name="Patch File MCP",
    instructions=f"""
This MCP is for patching existing files using block format.

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
"""
)

allowed_directories = []


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def main():
    # Process command line arguments
    global allowed_directories
    parser = argparse.ArgumentParser(description="Patch File MCP server")
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
        if i+2 < len(markers):
            if markers[i] != "<<<<<<< SEARCH" or markers[i+1] != "=======" or markers[i+2] != ">>>>>>> REPLACE":
                raise ValueError(
                    f"Malformed patch format: Incorrect marker sequence at position {i}: "
                    f"Expected [SEARCH, SEPARATOR, REPLACE], got {markers[i:i+3]}"
                )
    
    # Check for nested markers in each block
    sections = patch_content.split("<<<<<<< SEARCH")
    for i, section in enumerate(sections[1:], 1):  # Skip first empty section
        if "<<<<<<< SEARCH" in section and section.find(">>>>>>> REPLACE") > section.find("<<<<<<< SEARCH"):
            raise ValueError(f"Malformed patch format: Nested SEARCH marker in block {i}")


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
                replace_text = "\n".join(lines[separator_idx + 1:replace_end])
                
                # Check for markers in the search or replace text
                if any(marker in search_text for marker in [search_marker, separator, replace_marker]):
                    raise ValueError(f"Block {len(blocks)+1}: Search text contains patch markers")
                if any(marker in replace_text for marker in [search_marker, separator, replace_marker]):
                    raise ValueError(f"Block {len(blocks)+1}: Replace text contains patch markers")
                
                blocks.append((search_text, replace_text))

                i = replace_end + 1
            else:
                i += 1

        if blocks:
            return blocks
        else:
            raise ValueError("Invalid patch format. Expected block format with SEARCH/REPLACE markers.")

    # Check for markers in matched content
    for i, (search_text, replace_text) in enumerate(matches):
        if any(marker in search_text for marker in [search_marker, separator, replace_marker]):
            raise ValueError(f"Block {i+1}: Search text contains patch markers")
        if any(marker in replace_text for marker in [search_marker, separator, replace_marker]):
            raise ValueError(f"Block {i+1}: Replace text contains patch markers")

    return matches


@mcp.tool()
def patch_file(
    file_path: str = Field(description="The path to the file to patch"),
    patch_content: str = Field(
        description="Content to search and replace in the file using block format with SEARCH/REPLACE markers. Multiple blocks are supported.")
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
    """
    pp = Path(file_path).resolve()
    if not pp.exists() or not pp.is_file():
        raise FileNotFoundError(f"File {file_path} does not exist")
    if not any(str(pp).startswith(base) for base in allowed_directories):
        raise PermissionError(f"File {file_path} is not in allowed directories")

    # Read the current file content
    with open(pp, 'r', encoding='utf-8') as f:
        original_content = f.read()

    try:
        # Parse multiple search-replace blocks
        blocks = parse_search_replace_blocks(patch_content)
        if not blocks:
            raise ValueError("No valid search-replace blocks found in the patch content")

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
                raise ValueError(f"Block {i+1}: The search text appears {count} times in the file. "
                                 "Please provide more context to identify the specific occurrence.")

            else:
                # No match found
                raise ValueError(f"Block {i+1}: Could not find the search text in the file. "
                                 "Please ensure the search text exactly matches the content in the file.")

        # Write the final content back to the file
        with open(pp, 'w', encoding='utf-8') as f:
            f.write(current_content)

        return f"Successfully applied {applied_blocks} patch blocks to {file_path}"

    except Exception as e:
        raise RuntimeError(f"Failed to apply patch: {str(e)}")
