"""Command-line interface for tokBot."""

from __future__ import annotations

import argparse
from typing import Sequence

from common import Settings, configure_logging

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
        "--no-save",
        action="store_true",
        help="Skip writing workflow transcript output",
    )
    workflow_parser.set_defaults(handler=_handle_workflow)

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
        transcript_path = write_transcript(
            results,
            orchestrator.settings,
            output_path=args.output,
            metadata={"initial_message": args.message},
        )
        print(f"Transcript saved to {transcript_path}")
    return 0
