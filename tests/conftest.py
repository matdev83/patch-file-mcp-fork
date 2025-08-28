"""
Pytest configuration and shared fixtures for patch-file-mcp tests.
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Mock fastmcp to avoid import errors during testing
from unittest.mock import MagicMock
sys.modules['fastmcp'] = MagicMock()
sys.modules['fastmcp.fields'] = MagicMock()
sys.modules['pydantic'] = MagicMock()
sys.modules['pydantic.fields'] = MagicMock()


@pytest.fixture
def mock_file_path(tmp_path):
    """Create a mock file path for testing."""
    return tmp_path / "test_file.py"


@pytest.fixture
def mock_venv_path(tmp_path):
    """Create a mock virtual environment path."""
    venv_path = tmp_path / ".venv"
    venv_path.mkdir()
    scripts_path = venv_path / "Scripts"
    scripts_path.mkdir()
    python_exe = scripts_path / "python.exe"
    python_exe.write_text("# Mock Python executable")
    return venv_path


@pytest.fixture
def mock_project_structure(tmp_path):
    """Create a mock project structure with venv."""
    # Create project root
    project_root = tmp_path / "mock_project"
    project_root.mkdir()

    # Create .venv
    venv_path = project_root / ".venv"
    venv_path.mkdir()
    scripts_path = venv_path / "Scripts"
    scripts_path.mkdir()
    python_exe = scripts_path / "python.exe"
    python_exe.write_text("# Mock Python executable")

    # Create test file
    test_file = project_root / "test.py"
    test_file.write_text("print('Hello, World!')")

    return project_root


@pytest.fixture
def sample_patch_content():
    """Sample patch content for testing."""
    return """<<<<<<< SEARCH
def hello():
    print("Hello")
=======
def hello():
    print("Hello, World!")
>>>>>>> REPLACE"""


@pytest.fixture
def mock_subprocess_run():
    """Mock subprocess.run for testing."""
    with patch('patch_file_mcp.server.run_command_with_timeout') as mock_run:
        def mock_command(cmd, cwd=None, timeout=30):
            # Return success for all commands by default
            return (True, "", "", 0)
        mock_run.side_effect = mock_command
        yield mock_run


@pytest.fixture
def mock_path_exists():
    """Mock Path.exists for testing."""
    with patch('pathlib.Path.exists') as mock_exists:
        mock_exists.return_value = True
        yield mock_exists


@pytest.fixture(autouse=True)
def mock_sys_executable():
    """Mock sys.executable to return a consistent path."""
    with patch('sys.executable', '/mock/python.exe'):
        yield
