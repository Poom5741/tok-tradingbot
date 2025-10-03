"""Command-line interface for tokBot."""

from __future__ import annotations

import argparse
from typing import Sequence

from common import GitHubClient, GitHubError, Settings, configure_logging

from .bootstrap import build_registry
from .orchestrator import TokBotOrchestrator
from .transcript import write_transcript


def create_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(description="tokBot automation agent controller")
    parser.add_argument(
        "--env-file",
        action="append",
        default=None,
        help="Path to a .env file to read before executing commands. Can be provided multiple times.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List available agents")
    list_parser.set_defaults(handler=_handle_list)

    run_parser = subparsers.add_parser("run", help="Execute an agent")
    run_parser.add_argument("agent", nargs="?", help="Agent name to execute")
    run_parser.add_argument(
        "--message",
        default="",
        help="Message payload to pass to the agent",
    )
    run_parser.set_defaults(handler=_handle_run)

    workflow_parser = subparsers.add_parser(
        "workflow",
        help="Run planner, builder, and auditor agents in sequence",
    )
    workflow_parser.add_argument(
        "--agents",
        help="Comma-separated list of agents to invoke in order (defaults to planner,builder,auditor)",
    )
    workflow_parser.add_argument(
        "--message",
        default="",
        help="Initial message or objective to seed the workflow",
    )
    workflow_parser.add_argument(
        "--output",
        help="Optional file path to write a workflow transcript",
    )
    workflow_parser.add_argument(
        "--namespace",
        help="Optional sub-directory name under the transcripts directory",
    )
    workflow_parser.add_argument(
        "--filename",
        help="Optional custom transcript file name (appends .json if missing)",
    )
    workflow_parser.add_argument(
        "--meta",
        action="append",
        metavar="KEY=VALUE",
        help="Attach additional metadata entries to the transcript (repeatable)",
    )
    workflow_parser.add_argument(
        "--no-save",
        action="store_true",
        help="Skip writing workflow transcript output",
    )
    workflow_parser.set_defaults(handler=_handle_workflow)

    issue_parser = subparsers.add_parser(
        "issue",
        help="Interact with GitHub issues for agent memory",
    )
    issue_subparsers = issue_parser.add_subparsers(dest="issue_command", required=True)

    issue_read = issue_subparsers.add_parser(
        "read",
        help="Read an issue and recent comments",
    )
    issue_read.add_argument("--issue", type=int, required=True, help="Issue number to read")
    issue_read.add_argument("--repo", help="Repository override in owner/repo form")
    issue_read.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of most recent comments to display (default: 5)",
    )
    issue_read.set_defaults(handler=_handle_issue_read)

    issue_comment = issue_subparsers.add_parser(
        "comment",
        help="Append a comment to an issue",
    )
    issue_comment.add_argument("--issue", type=int, required=True, help="Issue number to comment on")
    issue_comment.add_argument("--repo", help="Repository override in owner/repo form")
    issue_comment.add_argument(
        "--body",
        required=True,
        help="Comment body to append. Use quotes for multi-line text.",
    )
    issue_comment.set_defaults(handler=_handle_issue_comment)

    return parser


def run_cli(argv: Sequence[str] | None = None) -> int:
    """Entry point for handling CLI execution."""
    parser = create_parser()
    args = parser.parse_args(argv)

    configure_logging()
    settings = Settings.from_env(env_files=args.env_file)
    orchestrator = TokBotOrchestrator(
        registry=build_registry(settings.agent_modules),
        settings=settings,
    )

    handler = getattr(args, "handler", None)
    if handler is None:
        parser.error("No handler configured for the provided command")
    return handler(args, orchestrator)


def _handle_list(args: argparse.Namespace, orchestrator: TokBotOrchestrator) -> int:
    """List all registered agents."""
    _ = args  # unused but kept for signature parity
    agents = sorted(orchestrator.registry.values(), key=lambda agent: agent.name.lower())
    if not agents:
        print("No agents registered.")
    else:
        print("Available agents:")
        for agent in agents:
            print(f"- {agent.name}: {agent.description}")
    return 0


def _handle_run(args: argparse.Namespace, orchestrator: TokBotOrchestrator) -> int:
    """Execute the requested agent and display its response."""
    result = orchestrator.run(agent_name=args.agent, message=args.message)
    print(f"Agent: {result.agent_name}")
    print(f"Input: {result.request or '(no content)'}")
    print(f"Output: {result.response}")
    return 0


def _handle_workflow(args: argparse.Namespace, orchestrator: TokBotOrchestrator) -> int:
    """Execute a sequence of agents, passing each response to the next."""
    if args.agents:
        agent_sequence = [name.strip() for name in args.agents.split(",") if name.strip()]
    else:
        agent_sequence = ["planner", "builder", "auditor"]

    if not agent_sequence:
        print("No agents specified for workflow execution.")
        return 0

    results = orchestrator.run_sequence(agent_sequence, args.message)
    for result in results:
        print("=" * 40)
        print(f"Agent: {result.agent_name}")
        print(f"Input: {result.request or '(no content)'}")
        print(f"Output:\n{result.response}")
    print("=" * 40)
    print("Workflow completed.")

    if not args.no_save:
        metadata = {"initial_message": args.message}
        if args.meta:
            metadata.update(_parse_meta(args.meta))
        transcript_path = write_transcript(
            results,
            orchestrator.settings,
            output_path=args.output,
            metadata=metadata,
            namespace=args.namespace,
            filename=args.filename,
        )
        print(f"Transcript saved to {transcript_path}")
    return 0


def _parse_meta(kv_pairs: list[str]) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for raw in kv_pairs:
        if "=" not in raw:
            raise SystemExit(f"Invalid metadata entry '{raw}'. Use KEY=VALUE format.")
        key, value = raw.split("=", 1)
        key = key.strip()
        if not key:
            raise SystemExit("Metadata key cannot be empty.")
        metadata[key] = value.strip()
    return metadata


def _build_github_client(args_repo: str | None, settings: Settings) -> GitHubClient:
    repo = args_repo or settings.github_repo
    return GitHubClient(repo=repo)


def _handle_issue_read(args: argparse.Namespace, orchestrator: TokBotOrchestrator) -> int:
    client = _build_github_client(args.repo, orchestrator.settings)
    try:
        issue_data = client.read_issue(args.issue)
    except GitHubError as exc:  # pragma: no cover - CLI error path
        print(f"GitHub error: {exc}")
        return 1

    title = issue_data.get("title", "(no title)")
    body = issue_data.get("body", "")
    print(f"Issue #{issue_data.get('number', args.issue)} | {title}")
    if body:
        print("-" * 40)
        print(body.strip())
    comments: list[dict] = issue_data.get("comments_data", [])
    if comments:
        print("-" * 40)
        for comment in comments[: args.limit]:
            author = comment.get("user", {}).get("login", "unknown")
            print(f"@{author}: {comment.get('body', '').strip()}")
    else:
        print("(No comments found)")
    return 0


def _handle_issue_comment(args: argparse.Namespace, orchestrator: TokBotOrchestrator) -> int:
    client = _build_github_client(args.repo, orchestrator.settings)
    try:
        client.create_comment(args.issue, args.body)
    except GitHubError as exc:  # pragma: no cover - CLI error path
        print(f"GitHub error: {exc}")
        return 1
    print(f"Comment posted to issue #{args.issue}.")
    return 0
