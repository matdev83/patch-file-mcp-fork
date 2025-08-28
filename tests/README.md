# Test Suite

This directory contains the comprehensive test suite for patch-file-mcp.

## Test Structure

```
tests/
├── __init__.py              # Test package initialization
├── conftest.py              # Pytest configuration and shared fixtures
├── test_venv_detection.py   # Tests for virtual environment detection
├── test_qa_pipeline.py      # Tests for QA pipeline functionality
├── test_patch_file.py       # Tests for main patch_file function
├── test_integration.py      # Integration tests
└── README.md               # This file
```

## Running Tests

### Option 1: Using the run_tests.py script (Recommended)

```bash
# Run all tests
python run_tests.py

# Run specific test file
python run_tests.py tests/test_venv_detection.py
```

### Option 2: Using pytest directly

```bash
# Install test dependencies
pip install -e .[test]

# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src/patch_file_mcp --cov-report=html

# Run specific test file
pytest tests/test_venv_detection.py

# Run tests with specific marker
pytest tests/ -m unit
```

## Test Categories

- **unit**: Unit tests for individual functions
- **integration**: Integration tests for component interaction
- **slow**: Tests that take longer to run

## Coverage

The test suite aims for high code coverage (>80%) and includes:

- Venv detection logic
- QA pipeline execution
- File patching functionality
- Error handling scenarios
- Edge cases and boundary conditions

## Mocking Strategy

Tests use comprehensive mocking to:
- Avoid actual file system operations
- Simulate subprocess calls
- Mock external dependencies
- Test error conditions safely

## Continuous Integration

Tests are designed to run in CI environments with:
- Isolated test environments
- Comprehensive coverage reporting
- Automated test execution
- Cross-platform compatibility
