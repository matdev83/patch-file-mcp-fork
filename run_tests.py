#!/usr/bin/env python3
"""
Script to run tests with proper dependencies.
"""
import subprocess
import sys
from pathlib import Path

def run_tests():
    """Run the test suite."""
    print("🚀 Running patch-file-mcp test suite...")

    # Check if we're in a virtual environment
    if not hasattr(sys, 'real_prefix') and sys.base_prefix == sys.prefix:
        print("⚠️  Warning: Not running in a virtual environment")
        print("   It's recommended to run tests in a virtual environment")

    # Install test dependencies if not already installed
    print("📦 Installing test dependencies...")
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "install",
            "-e", ".[test]"
        ], check=True, capture_output=True)
        print("✅ Test dependencies installed")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install test dependencies: {e}")
        return False

    # Run the tests
    print("🧪 Running tests...")
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest",
            "tests/",
            "--verbose",
            "--tb=short",
            "--cov=src/patch_file_mcp",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov",
        ], capture_output=False)

        if result.returncode == 0:
            print("✅ All tests passed!")
            return True
        else:
            print(f"❌ Tests failed with exit code: {result.returncode}")
            return False

    except FileNotFoundError:
        print("❌ pytest not found. Please ensure test dependencies are installed.")
        return False
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False

def run_specific_test(test_path):
    """Run a specific test file."""
    print(f"🧪 Running specific test: {test_path}")

    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest",
            test_path,
            "--verbose",
            "--tb=short",
        ], capture_output=False)

        return result.returncode == 0

    except Exception as e:
        print(f"❌ Error running test: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_path = sys.argv[1]
        success = run_specific_test(test_path)
    else:
        success = run_tests()

    sys.exit(0 if success else 1)
