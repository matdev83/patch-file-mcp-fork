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

# Create a mock FastMCP class that doesn't interfere with function execution
class MockFastMCP:
    def __init__(self, **kwargs):
        pass

    def tool(self, func=None):
        # Don't modify the function, just return it as-is
        if func is None:
            return lambda f: f
        return func

    def run(self):
        pass

# Mock the modules
fastmcp_mock = MagicMock()
fastmcp_mock.FastMCP = MockFastMCP
sys.modules['fastmcp'] = fastmcp_mock
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
def mock_qa_pipeline_complex():
    """Mock subprocess.run with complex QA pipeline behavior."""
    with patch('patch_file_mcp.server.run_command_with_timeout') as mock_run, \
         patch('patch_file_mcp.server.get_file_modification_time') as mock_time:

        call_count = {'ruff': 0, 'black': 0, 'mypy': 0}
        file_modified = True  # Start with file needing modification

        def mock_command(cmd, cwd=None, timeout=30):
            if 'ruff' in cmd and 'check' in cmd and '--fix' in cmd:
                call_count['ruff'] += 1
                return (True, "", "", 0)  # ruff succeeds

            elif 'black' in cmd:
                call_count['black'] += 1
                # First black call should simulate file modification
                nonlocal file_modified
                if call_count['black'] == 1:
                    file_modified = False  # File was modified
                return (True, "", "", 0)  # black succeeds

            elif 'mypy' in cmd:
                call_count['mypy'] += 1
                return (True, "", "", 0)  # mypy succeeds

            return (True, "", "", 0)

        # Mock file modification time to simulate file changes
        def mock_get_time(file_path):
            if file_modified:
                return 100.0  # Initial time
            else:
                return 200.0  # Modified time (different)

        mock_time.side_effect = mock_get_time
        mock_run.side_effect = mock_command
        yield mock_run


@pytest.fixture
def mock_qa_pipeline_timeout():
    """Mock subprocess.run that simulates timeout."""
    import subprocess
    with patch('patch_file_mcp.server.run_command_with_timeout') as mock_run:
        def mock_command(cmd, cwd=None, timeout=30):
            if 'ruff' in cmd and 'check' in cmd and '--fix' in cmd:
                return (False, "", f"Command timed out after {timeout} seconds", -1)
            return (True, "", "", 0)
        mock_run.side_effect = mock_command
        yield mock_run


@pytest.fixture
def mock_qa_pipeline_warnings():
    """Mock subprocess.run that simulates warnings."""
    with patch('patch_file_mcp.server.run_command_with_timeout') as mock_run, \
         patch('patch_file_mcp.server.get_file_modification_time') as mock_time:

        def mock_command(cmd, cwd=None, timeout=30):
            if 'ruff' in cmd and 'check' in cmd and '--fix' in cmd:
                return (True, "", "", 0)  # ruff succeeds
            elif 'black' in cmd:
                # Simulate black with warnings (return code != 0)
                return (True, "", "warning: some warning message", 1)
            elif 'mypy' in cmd:
                return (True, "", "", 0)  # mypy succeeds
            return (True, "", "", 0)

        # Mock file modification time to simulate no changes
        mock_time.return_value = 100.0
        mock_run.side_effect = mock_command
        yield mock_run


@pytest.fixture
def mock_qa_pipeline_iteration_limit():
    """Mock subprocess.run that simulates infinite reformatting loop."""
    with patch('patch_file_mcp.server.run_command_with_timeout') as mock_run, \
         patch('patch_file_mcp.server.get_file_modification_time') as mock_time:

        # Always return different times to simulate continuous file modifications
        time_call_count = 0

        def mock_command(cmd, cwd=None, timeout=30):
            if 'ruff' in cmd and 'check' in cmd and '--fix' in cmd:
                return (True, "", "", 0)  # ruff always succeeds
            elif 'black' in cmd:
                # Black always succeeds and modifies file
                return (True, "", "", 0)
            elif 'mypy' in cmd:
                return (True, "", "", 0)  # mypy succeeds
            return (True, "", "", 0)

        # Mock file modification time to always return increasing values
        # This simulates the file being continuously modified
        def mock_get_time(file_path):
            nonlocal time_call_count
            time_call_count += 1
            return float(time_call_count * 100)  # Always increasing time

        mock_time.side_effect = mock_get_time
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
