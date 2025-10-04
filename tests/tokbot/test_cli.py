"""Unit tests for tokBot CLI entrypoints (microstructure bot)."""

from pathlib import Path

from tokbot.cli import run_cli


def test_paper_command_outputs_states(capsys) -> None:
    exit_code = run_cli(["paper", "--loops", "2"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Paper Trading Outcomes:" in captured.out
    # Expect at least two iteration lines printed
    lines = [l for l in captured.out.splitlines() if l.strip().startswith("[")]
    assert len(lines) >= 2


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
