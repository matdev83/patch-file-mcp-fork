"""
Tests for virtual environment detection functionality.
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import the functions we want to test
from patch_file_mcp.server import (
    find_venv_directory,
    get_current_python_executable,
    is_same_venv,
)


class TestVenvDetection:
    """Test cases for venv detection functionality."""

    def test_get_current_python_executable(self):
        """Test getting current Python executable path."""
        with patch('sys.executable', '/usr/bin/python3'):
            result = get_current_python_executable()
            assert result == '/usr/bin/python3'

    def test_is_same_venv_identical_paths(self):
        """Test venv comparison with identical paths."""
        path1 = '/path/to/python.exe'
        path2 = '/path/to/python.exe'

        assert is_same_venv(path1, path2) is True

    def test_is_same_venv_different_paths(self):
        """Test venv comparison with different paths."""
        path1 = '/venv1/Scripts/python.exe'
        path2 = '/venv2/Scripts/python.exe'

        assert is_same_venv(path1, path2) is False

    def test_is_same_venv_same_scripts_directory(self):
        """Test venv comparison with same Scripts directory."""
        path1 = '/venv/Scripts/python.exe'
        path2 = '/venv/Scripts/python.exe'

        assert is_same_venv(path1, path2) is True

    def test_is_same_venv_same_venv_root(self):
        """Test venv comparison with same venv root directory."""
        path1 = '/project/.venv/Scripts/python.exe'
        path2 = '/project/.venv/Scripts/python.exe'

        assert is_same_venv(path1, path2) is True

    def test_is_same_venv_none_paths(self):
        """Test venv comparison with None paths."""
        assert is_same_venv(None, '/path/to/python.exe') is False
        assert is_same_venv('/path/to/python.exe', None) is False
        assert is_same_venv(None, None) is False

    def test_find_venv_directory_with_dot_venv(self, tmp_path, mock_venv_path):
        """Test finding .venv directory."""
        # Create a file in the tmp_path directory
        test_file = tmp_path / "test.py"
        test_file.write_text("print('test')")

        # Create .venv in the same directory
        venv_dir = tmp_path / ".venv"
        venv_dir.mkdir(exist_ok=True)
        scripts_dir = venv_dir / "Scripts"
        scripts_dir.mkdir(exist_ok=True)
        python_exe = scripts_dir / "python.exe"
        python_exe.write_text("# Mock python")

        with patch('sys.executable', str(python_exe)):
            result = find_venv_directory(str(test_file))

            # Should not find the venv because it's the same as current executable
            assert result is None

    def test_find_venv_directory_with_different_venv(self, tmp_path):
        """Test finding a different venv directory."""
        # Create project structure
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create test file
        test_file = project_dir / "test.py"
        test_file.write_text("print('test')")

        # Create different venv
        venv_dir = project_dir / ".venv"
        venv_dir.mkdir()
        scripts_dir = venv_dir / "Scripts"
        scripts_dir.mkdir()
        python_exe = scripts_dir / "python.exe"
        python_exe.write_text("# Mock python")

        # Mock current executable to be different
        with patch('sys.executable', '/different/python.exe'):
            result = find_venv_directory(str(test_file))

            assert result == str(python_exe)

    def test_find_venv_directory_walks_up(self, tmp_path):
        """Test that venv detection walks up directory tree."""
        # Create nested structure
        root_dir = tmp_path / "root"
        root_dir.mkdir()

        sub_dir = root_dir / "sub"
        sub_dir.mkdir()

        # Create venv in root
        venv_dir = root_dir / ".venv"
        venv_dir.mkdir()
        scripts_dir = venv_dir / "Scripts"
        scripts_dir.mkdir()
        python_exe = scripts_dir / "python.exe"
        python_exe.write_text("# Mock python")

        # Create test file in sub directory
        test_file = sub_dir / "test.py"
        test_file.write_text("print('test')")

        with patch('sys.executable', '/different/python.exe'):
            result = find_venv_directory(str(test_file))

            assert result == str(python_exe)

    def test_find_venv_directory_prefers_dot_venv(self, tmp_path):
        """Test that .venv is preferred over venv."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        test_file = project_dir / "test.py"
        test_file.write_text("print('test')")

        # Create both .venv and venv
        dot_venv = project_dir / ".venv"
        dot_venv.mkdir()
        dot_scripts = dot_venv / "Scripts"
        dot_scripts.mkdir()
        dot_python = dot_scripts / "python.exe"
        dot_python.write_text("# Dot venv python")

        venv = project_dir / "venv"
        venv.mkdir()
        scripts = venv / "Scripts"
        scripts.mkdir()
        python = scripts / "python.exe"
        python.write_text("# Regular venv python")

        with patch('sys.executable', '/different/python.exe'):
            result = find_venv_directory(str(test_file))

            # Should prefer .venv
            assert result == str(dot_python)

    def test_find_venv_directory_no_venv_found(self, tmp_path, monkeypatch):
        """Test when no venv is found."""
        test_file = tmp_path / "test.py"
        test_file.write_text("print('test')")

        # Mock sys.executable to avoid finding system venvs
        monkeypatch.setattr('sys.executable', '/completely/different/python.exe')

        # Also mock Path.exists to ensure no venvs are found
        original_exists = Path.exists
        def mock_exists(self):
            if '.venv' in str(self) or 'venv' in str(self):
                # Only allow the tmp_path to exist, not any parent directories
                if str(tmp_path) in str(self):
                    return original_exists(self)
                else:
                    return False
            return original_exists(self)

        monkeypatch.setattr(Path, 'exists', mock_exists)

        result = find_venv_directory(str(test_file))

        assert result is None

    def test_find_venv_directory_depth_limit(self, tmp_path):
        """Test that search depth is limited."""
        # Create a deeply nested structure
        current_dir = tmp_path
        for i in range(15):  # More than the 10 depth limit
            current_dir = current_dir / f"level_{i}"
            current_dir.mkdir()

        test_file = current_dir / "test.py"
        test_file.write_text("print('test')")

        # Create venv at root level
        venv_dir = tmp_path / ".venv"
        venv_dir.mkdir()
        scripts_dir = venv_dir / "Scripts"
        scripts_dir.mkdir()
        python_exe = scripts_dir / "python.exe"
        python_exe.write_text("# Mock python")

        with patch('sys.executable', '/different/python.exe'):
            result = find_venv_directory(str(test_file))

            # Should not find the venv because it's too deep
            assert result is None
