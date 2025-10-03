"""Unit tests for tokBot CLI entrypoints."""

import json
from pathlib import Path

from tokbot.cli import run_cli


def test_list_command_outputs_agent(capsys) -> None:
    exit_code = run_cli(["list"])
    captured = capsys.readouterr()

    assert exit_code == 0
    output = captured.out.lower()
    assert "available agents:" in output
    for name in ("echo", "uppercase", "planner", "builder", "auditor"):
        assert name in output


def test_run_command_returns_echo(capsys) -> None:
    exit_code = run_cli(["run", "echo", "--message", "Hello"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Agent: echo" in captured.out
    assert "Hello" in captured.out
    assert "Echoing:" in captured.out


def test_run_command_uses_env_file_default(tmp_path: Path, capsys) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("TOKBOT_DEFAULT_AGENT=echo\n", encoding="utf-8")

    exit_code = run_cli(["--env-file", str(env_file), "run", "--message", "Test"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Agent: echo" in captured.out


def test_workflow_runs_default_sequence(capsys) -> None:
    exit_code = run_cli(["workflow", "--message", "Ship feature X", "--no-save"])
    captured = capsys.readouterr()

    assert exit_code == 0
    output = captured.out
    for name in ("planner", "builder", "auditor"):
        assert f"Agent: {name}" in output
    assert "Workflow completed." in output


def test_custom_agent_module_loaded(tmp_path: Path, capsys, monkeypatch) -> None:
    pkg_dir = tmp_path / "custom_agent"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text(
        """
from __future__ import annotations

from dataclasses import dataclass

from tokbot.agents.base import Agent


@dataclass(slots=True)
class CustomAgent:
    name: str = "custom"
    description: str = "Custom agent for testing."

    def run(self, message: str) -> str:
        return f"processed {message.strip() or '(empty)'}"


def build_agent() -> Agent:
    return CustomAgent()
""",
        encoding="utf-8",
    )

    monkeypatch.syspath_prepend(str(tmp_path))

    env_file = tmp_path / "custom.env"
    env_file.write_text(
        "TOKBOT_DEFAULT_AGENT=custom\nTOKBOT_AGENT_MODULES=custom_agent\n",
        encoding="utf-8",
    )

    exit_code = run_cli(["--env-file", str(env_file), "run", "--message", "hello"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Agent: custom" in captured.out
    assert "processed hello" in captured.out


def test_workflow_writes_transcript(tmp_path: Path, capsys) -> None:
    destination = tmp_path / "transcript.json"
    exit_code = run_cli([
        "workflow",
        "--message",
        "Ship feature",
        "--output",
        str(destination),
    ])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Transcript saved" in captured.out
    assert destination.exists()

    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["agents"] == ["planner", "builder", "auditor"]
    assert payload["metadata"]["initial_message"] == "Ship feature"


def test_workflow_no_save_respects_flag(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.setenv("TOKBOT_TRANSCRIPTS_DIR", str(tmp_path))

    exit_code = run_cli(["workflow", "--message", "Ship feature", "--no-save"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Transcript saved" not in captured.out
    assert not any(tmp_path.iterdir())


def test_workflow_namespace_and_meta(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.setenv("TOKBOT_TRANSCRIPTS_DIR", str(tmp_path))

    exit_code = run_cli([
        "workflow",
        "--message",
        "Ship feature",
        "--namespace",
        "demo",
        "--filename",
        "summary",
        "--meta",
        "issue=123",
        "--meta",
        "priority=high",
    ])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Transcript saved" in captured.out

    transcript_file = tmp_path / "demo" / "summary.json"
    assert transcript_file.exists()

    payload = json.loads(transcript_file.read_text(encoding="utf-8"))
    assert payload["metadata"]["initial_message"] == "Ship feature"
    assert payload["metadata"]["issue"] == "123"
    assert payload["metadata"]["priority"] == "high"


def test_issue_read_uses_github_client(monkeypatch, capsys) -> None:
    captured_args = {}

    class FakeClient:
        def __init__(self, repo=None):
            captured_args["repo"] = repo

        def read_issue(self, issue_number: int) -> dict:
            captured_args["issue"] = issue_number
            return {
                "number": issue_number,
                "title": "Demo Issue",
                "body": "Issue body",
                "comments_data": [
                    {"user": {"login": "alice"}, "body": "Looks good"},
                    {"user": {"login": "bob"}, "body": "Needs work"},
                ],
            }

    monkeypatch.setattr("tokbot.cli.GitHubClient", FakeClient)

    exit_code = run_cli([
        "issue",
        "read",
        "--issue",
        "7",
        "--repo",
        "octo/demo",
        "--limit",
        "1",
    ])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured_args == {"repo": "octo/demo", "issue": 7}
    assert "Issue #7 | Demo Issue" in captured.out
    assert "@alice" in captured.out
    assert "@bob" not in captured.out  # limited to 1 comment


def test_issue_comment_posts_using_client(monkeypatch, capsys) -> None:
    calls: list[tuple[int, str]] = []

    class FakeClient:
        def __init__(self, repo=None):
            self.repo = repo

        def create_comment(self, issue_number: int, body: str) -> None:
            calls.append((issue_number, body))

    monkeypatch.setattr("tokbot.cli.GitHubClient", FakeClient)

    exit_code = run_cli([
        "issue",
        "comment",
        "--issue",
        "9",
        "--body",
        "Automated note",
    ])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert calls == [(9, "Automated note")]
    assert "Comment posted to issue #9." in captured.out
