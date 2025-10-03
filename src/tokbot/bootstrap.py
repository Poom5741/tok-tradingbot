"""Helpers to bootstrap the tokBot orchestrator."""

from __future__ import annotations

import importlib
from typing import Sequence

from common.config import DEFAULT_AGENT_MODULES

from .agents.base import Agent
from .agents.registry import AgentRegistry


def build_registry(agent_modules: Sequence[str] | None = None) -> AgentRegistry:
    """Construct a registry populated with configured agents."""
    registry = AgentRegistry()
    modules = tuple(agent_modules) if agent_modules is not None else DEFAULT_AGENT_MODULES
    for module_path in modules:
        agent = _load_agent(module_path)
        registry.register(agent)
    return registry


def _load_agent(module_path: str) -> Agent:
    """Import a module and instantiate its agent via a ``build_agent`` factory."""
    module = importlib.import_module(module_path)
    builder = getattr(module, "build_agent", None)
    if builder is None or not callable(builder):
        raise ValueError(f"Module '{module_path}' does not expose a callable build_agent().")
    agent = builder()
    if not hasattr(agent, "name") or not hasattr(agent, "run"):
        raise ValueError(f"Module '{module_path}' build_agent() returned an invalid agent instance.")
    return agent
