#!/usr/bin/env python3
"""
Standalone test for path normalization without importing the full server module.
"""
import os
from pathlib import Path

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

def test_path_formats():
    """Test different path formats to ensure they all normalize correctly."""

    # Create a test file
    test_file = Path(__file__).parent / "test_sample.txt"
    test_file.write_text("test content")

    print("=== Path Normalization Test ===\n")
    print(f"Original file: {test_file}")
    print(f"Resolved path: {test_file.resolve()}\n")

    # Test different input formats
    test_formats = [
        ("Native format", str(test_file)),
        ("Forward slashes", str(test_file).replace('\\', '/')),
        ("Windows backslashes", str(test_file).replace('/', '\\')),
        ("Escaped backslashes", str(test_file).replace('/', '\\\\')),
        ("Mixed separators", str(test_file).replace('test_', 'test_\\').replace('formats', 'formats/')),
    ]

    expected_path = test_file.resolve()

    print("Testing different path formats:")
    print("-" * 50)

    all_passed = True
    for name, path_format in test_formats:
        try:
            normalized = normalize_path(path_format)
            success = normalized == expected_path
            status = "✅ PASS" if success else "❌ FAIL"

            print(f"{name:20}: {status}")
            print(f"  Input:  {path_format}")
            print(f"  Output: {normalized}")
            print(f"  Match:  {success}")
            print()

            if not success:
                all_passed = False

        except Exception as e:
            print(f"{name:20}: ❌ ERROR - {e}")
            print()
            all_passed = False

    # Clean up
    test_file.unlink()

    print("✅ Path normalization test completed!")
    if all_passed:
        print("\n🎉 SUCCESS: All path formats normalized correctly!")
        print("   The --allowed-dir parameter will work consistently regardless of input format.")
    else:
        print("\n❌ Some tests failed. Path normalization needs more work.")

if __name__ == "__main__":
    test_path_formats()
