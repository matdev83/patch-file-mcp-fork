"""
Git repository management for patch file versioning.
Based on Aider's GitRepo implementation but simplified for MCP server use.
"""

from pathlib import Path
from typing import Optional, List, Tuple

try:
    import git  # type: ignore[import-not-found]

    ANY_GIT_ERROR = (
        git.exc.ODBError,
        git.exc.GitError,
        git.exc.InvalidGitRepositoryError,
        git.exc.GitCommandNotFound,
        OSError,
        IndexError,
        BufferError,
        TypeError,
        ValueError,
        AttributeError,
        AssertionError,
        TimeoutError,
    )
except ImportError:
    git = None  # type: ignore[assignment]
    ANY_GIT_ERROR = (  # type: ignore[assignment]
        OSError,
        IndexError,
        BufferError,
        TypeError,
        ValueError,
        AttributeError,
        AssertionError,
        TimeoutError,
    )
    print("Warning: GitPython not available. Git versioning will be disabled.")


class GitRepo:
    """Simplified Git repository handler for MCP server versioning."""

    def __init__(self, root_path: str, logger=None):
        """
        Initialize GitRepo for a given root path.

        Args:
            root_path: Root directory to search for git repository
            logger: Optional logger instance
        """
        self.logger = logger
        self.root = None
        self.repo = None
        self.git_available = git is not None

        if not self.git_available:
            if self.logger:
                self.logger.warning("GitPython not available - git versioning disabled")
            return

        try:
            # Find git repository
            repo_path = Path(root_path).resolve()

            # If root_path is a file, use its parent directory
            if repo_path.is_file():
                repo_path = repo_path.parent

            # Try to find git repo, searching parent directories if needed
            try:
                repo = git.Repo(repo_path, search_parent_directories=True)
                self.repo = repo
                working_dir = repo.working_tree_dir
                if working_dir is None:
                    raise ValueError("Repository has no working tree directory")
                self.root = Path(working_dir).resolve()
                if self.logger:
                    self.logger.info(f"Found git repository at: {self.root}")
            except ANY_GIT_ERROR as e:
                if self.logger:
                    self.logger.debug(f"No git repository found at {repo_path}: {e}")
                return

        except Exception as e:
            if self.logger:
                self.logger.warning(f"Failed to initialize git repo: {e}")
            return

    def is_available(self) -> bool:
        """Check if git is available and repository is valid."""
        return self.git_available and self.repo is not None

    def get_head_commit_sha(self, short: bool = True) -> Optional[str]:
        """Get the current HEAD commit SHA."""
        if not self.is_available():
            return None

        try:
            if self.repo is None:
                return None
            commit = self.repo.head.commit
            if short:
                return commit.hexsha[:7]
            return commit.hexsha
        except ANY_GIT_ERROR:
            return None

    def is_dirty(self, path: Optional[str] = None) -> bool:
        """Check if the repository has uncommitted changes."""
        if not self.is_available():
            return False

        try:
            if self.repo is None:
                return False
            return self.repo.is_dirty(path=path)
        except ANY_GIT_ERROR:
            return False

    def get_dirty_files(self) -> List[str]:
        """Get list of files that have uncommitted changes."""
        if not self.is_available():
            return []

        try:
            if self.repo is None:
                return []
            dirty_files = set()

            # Get staged files
            staged_files = self.repo.git.diff("--name-only", "--cached").splitlines()
            dirty_files.update(staged_files)

            # Get unstaged files
            unstaged_files = self.repo.git.diff("--name-only").splitlines()
            dirty_files.update(unstaged_files)

            return list(dirty_files)
        except ANY_GIT_ERROR:
            return []

    def stage_files(self, file_paths: List[str]) -> bool:
        """
        Stage specific files for commit.

        Args:
            file_paths: List of file paths to stage

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.is_available() or not file_paths:
            return False

        try:
            # Convert to relative paths from repo root
            repo_relative_paths = []
            for file_path in file_paths:
                abs_path = Path(file_path).resolve()
                try:
                    if self.root is None:
                        continue
                    rel_path = abs_path.relative_to(self.root)
                    repo_relative_paths.append(str(rel_path))
                except ValueError:
                    # File is not within repo, skip it
                    if self.logger:
                        self.logger.warning(
                            f"File {file_path} is not within git repository {self.root}"
                        )
                    continue

            if not repo_relative_paths:
                return False

            # Stage the files
            if self.repo is None:
                return False
            for file_to_stage in repo_relative_paths:
                try:
                    self.repo.git.add(file_to_stage)
                    if self.logger:
                        self.logger.debug(f"Staged file: {file_to_stage}")
                except ANY_GIT_ERROR as e:
                    if self.logger:
                        self.logger.warning(f"Failed to stage {file_to_stage}: {e}")
                    continue

            return True

        except ANY_GIT_ERROR as e:
            if self.logger:
                self.logger.error(f"Failed to stage files: {e}")
            return False

    def commit_files(
        self, file_paths: List[str], message: str
    ) -> Optional[Tuple[str, str]]:
        """
        Commit specific files with a commit message.

        Args:
            file_paths: List of file paths to commit
            message: Commit message

        Returns:
            Optional[Tuple[str, str]]: (commit_hash, commit_message) if successful, None otherwise
        """
        if not self.is_available() or not file_paths or not message:
            return None

        try:
            # Stage the files first
            if not self.stage_files(file_paths):
                if self.logger:
                    self.logger.warning("Failed to stage files for commit")
                return None

            # Check if there are actually changes to commit
            if not self.is_dirty():
                if self.logger:
                    self.logger.debug("No changes to commit")
                return None

            # Create commit
            commit_cmd = ["-m", message]

            # Only commit the specific files
            repo_relative_paths = []
            for file_path in file_paths:
                abs_path = Path(file_path).resolve()
                try:
                    if self.root is None:
                        continue
                    rel_path = abs_path.relative_to(self.root)
                    repo_relative_paths.append(str(rel_path))
                except ValueError:
                    continue

            if repo_relative_paths:
                commit_cmd.extend(["--"] + repo_relative_paths)

            if self.repo is None:
                return None
            self.repo.git.commit(commit_cmd)

            # Get the new commit hash
            commit_hash = self.get_head_commit_sha(short=True)

            if commit_hash is None:
                if self.logger:
                    self.logger.warning("Failed to get commit hash after commit")
                return None

            if self.logger:
                self.logger.info(f"Committed {len(file_paths)} files: {commit_hash}")

            return commit_hash, message

        except ANY_GIT_ERROR as e:
            if self.logger:
                self.logger.error(f"Failed to commit files: {e}")
            return None

    def get_commit_message(self, file_paths: List[str]) -> str:
        """
        Generate a commit message for the given files.

        Args:
            file_paths: List of file paths being committed

        Returns:
            str: Generated commit message
        """
        if not file_paths:
            return "Update files"

        if len(file_paths) == 1:
            file_name = Path(file_paths[0]).name
            return f"Update {file_name}"
        else:
            return f"Update {len(file_paths)} files"
