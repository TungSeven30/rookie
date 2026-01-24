"""Context module for client profiles and agent execution context.

This module provides:
- Client profile service with append-only log pattern
- Context builder for assembling agent execution context
"""

from src.context.builder import (
    TASK_TYPE_SKILLS,
    AgentContext,
    build_agent_context,
    get_client_documents,
    get_prior_year_return,
    get_skills_for_task_type,
    load_skill_for_year,
)
from src.context.profile import (
    append_profile_entry,
    get_client_profile_view,
    get_client_with_profile,
    get_profile_history,
    profile_entry_count,
)

__all__ = [
    # Profile service
    "get_client_profile_view",
    "append_profile_entry",
    "get_profile_history",
    "get_client_with_profile",
    "profile_entry_count",
    # Context builder
    "AgentContext",
    "TASK_TYPE_SKILLS",
    "get_skills_for_task_type",
    "load_skill_for_year",
    "get_client_documents",
    "get_prior_year_return",
    "build_agent_context",
]
