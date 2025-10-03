"""Lightweight wrapper around the GitHub CLI for issue interactions."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional


class GitHubError(RuntimeError):
    """Represents an error returned by the GitHub CLI."""


Runner = Callable[[List[str]], subprocess.CompletedProcess]


def _default_runner(args: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=False, capture_output=True, text=True)


@dataclass(slots=True)
class GitHubClient:
    """Interact with GitHub Issues via the ``gh`` CLI."""

    repo: Optional[str] = None
    executable: str = "gh"
    runner: Runner = _default_runner

    def _invoke(self, args: Iterable[str]) -> subprocess.CompletedProcess:
        command = [self.executable, *args]
        result = self.runner(command)
        if result.returncode != 0:
            raise GitHubError(result.stderr.strip() or result.stdout.strip())
        return result

    def read_issue(self, issue_number: int) -> dict:
        """Return issue metadata and comments as a dictionary."""
        repo = self._require_repo()
        endpoint = f"repos/{repo}/issues/{issue_number}"
        issue_result = self._invoke(["api", endpoint])
        issue_data = json.loads(issue_result.stdout or "{}")

        comments_result = self._invoke(["api", f"{endpoint}/comments"])
        comments_data = json.loads(comments_result.stdout or "[]")
        issue_data["comments_data"] = comments_data
        return issue_data

    def list_comments(self, issue_number: int, limit: int | None = None) -> list[dict]:
        """Fetch comments for an issue."""
        comments = self.read_issue(issue_number)["comments_data"]
        if limit is not None:
            return comments[:limit]
        return comments

    def create_comment(self, issue_number: int, body: str) -> None:
        """Post a comment to an issue."""
        repo = self._require_repo()
        endpoint = f"repos/{repo}/issues/{issue_number}/comments"
        self._invoke(["api", endpoint, "-f", f"body={body}"])

    def _require_repo(self) -> str:
        if not self.repo:
            raise GitHubError("A repository must be specified (e.g. owner/repo).")
        return self.repo
