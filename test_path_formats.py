#!/usr/bin/env python3
"""
Test script to demonstrate that different path formats are normalized correctly.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from patch_file_mcp.server import normalize_path

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

        except Exception as e:
            print(f"{name:20}: ❌ ERROR - {e}")
            print()

    # Clean up
    test_file.unlink()

    print("✅ Path normalization test completed!")
    print("\nAll path formats should resolve to the same absolute path!")

if __name__ == "__main__":
    test_path_formats()
