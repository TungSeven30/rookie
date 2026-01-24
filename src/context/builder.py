"""Context builder for agent execution.

Assembles complete context (client profile, documents, skills) for agent
execution. This is the primary interface for preparing agent input.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.context.profile import get_client_profile_view
from src.models.client import Client
from src.models.skill import SkillFile
from src.skills.models import SkillFileModel


# Mapping of task types to the skills they require
TASK_TYPE_SKILLS: dict[str, list[str]] = {
    "w2_extraction": ["w2_processing", "income_verification"],
    "1099_extraction": ["1099_processing", "income_verification"],
    "schedule_c_prep": ["schedule_c", "expense_categorization", "depreciation"],
    "schedule_e_prep": ["schedule_e", "rental_income", "depreciation"],
    "tax_return_review": ["return_review", "compliance_check"],
    "interview_prep": ["client_interview", "document_request"],
    "general": [],  # No specific skills required
}


@dataclass
class AgentContext:
    """Complete context for agent execution.

    Contains all information an agent needs to perform a task:
    - Client identification and profile
    - Relevant documents
    - Applicable skills for the task type
    - Prior year return for comparison
    """

    client_id: int
    client_name: str
    tax_year: int
    task_type: str
    client_profile: dict[str, Any] = field(default_factory=dict)
    documents: list[dict[str, Any]] = field(default_factory=list)
    skills: list[dict[str, Any]] = field(default_factory=list)
    prior_year_return: dict[str, Any] | None = None

    def to_prompt_context(self) -> dict[str, Any]:
        """Convert agent context to a dictionary suitable for prompt injection.

        Returns:
            Dictionary with all context formatted for prompt construction
        """
        return {
            "client": {
                "id": self.client_id,
                "name": self.client_name,
            },
            "tax_year": self.tax_year,
            "task_type": self.task_type,
            "profile": self.client_profile,
            "documents": self.documents,
            "skills": self.skills,
            "prior_year_return": self.prior_year_return,
        }

    def has_skill(self, skill_name: str) -> bool:
        """Check if context includes a specific skill.

        Args:
            skill_name: Name of the skill to check for

        Returns:
            True if the skill is loaded in context
        """
        return any(s.get("name") == skill_name for s in self.skills)

    def get_skill(self, skill_name: str) -> dict[str, Any] | None:
        """Get a specific skill from context by name.

        Args:
            skill_name: Name of the skill to retrieve

        Returns:
            Skill dictionary or None if not found
        """
        for skill in self.skills:
            if skill.get("name") == skill_name:
                return skill
        return None


def get_skills_for_task_type(task_type: str) -> list[str]:
    """Get the list of skill names required for a task type.

    Args:
        task_type: Type of task (e.g., "w2_extraction", "schedule_c_prep")

    Returns:
        List of skill names required for the task type.
        Falls back to empty list for unknown task types.

    Example:
        >>> get_skills_for_task_type("w2_extraction")
        ["w2_processing", "income_verification"]
    """
    return TASK_TYPE_SKILLS.get(task_type, TASK_TYPE_SKILLS.get("general", []))


async def load_skill_for_year(
    session: AsyncSession,
    skill_name: str,
    tax_year: int,
) -> SkillFileModel | None:
    """Load the appropriate skill version for a tax year from database.

    Selects the skill version with the latest effective_date that is
    on or before December 31 of the tax year.

    Args:
        session: Database session
        skill_name: Name of the skill to load
        tax_year: Tax year to select skill version for

    Returns:
        SkillFileModel if found, None otherwise

    Example:
        >>> skill = await load_skill_for_year(session, "w2_processing", 2024)
        >>> skill.version
        "2024.1"
    """
    year_end = date(tax_year, 12, 31)

    # Query for the most recent skill version effective on or before year_end
    stmt = (
        select(SkillFile)
        .where(SkillFile.name == skill_name)
        .where(SkillFile.effective_date <= year_end)
        .order_by(SkillFile.effective_date.desc())
        .limit(1)
    )

    result = await session.execute(stmt)
    skill_file = result.scalar_one_or_none()

    if skill_file is None:
        return None

    # Parse the YAML content into a SkillFileModel
    # Note: skill_file.content is stored as YAML text in the database
    from src.skills.loader import load_skill_from_yaml

    try:
        return load_skill_from_yaml(skill_file.content)
    except Exception:
        # If parsing fails, log and return None
        # In production, this would be logged via structlog
        return None


async def get_client_documents(
    session: AsyncSession,
    client_id: int,
    tax_year: int,
) -> list[dict[str, Any]]:
    """Get documents for a client and tax year.

    Stub for Phase 3 (Document Processing).

    Args:
        session: Database session
        client_id: Client ID
        tax_year: Tax year

    Returns:
        List of document dictionaries with metadata
    """
    # TODO: Implement in Phase 3 when document processing is built
    # Will query DocumentEmbedding and related tables
    _ = session, client_id, tax_year  # Acknowledge unused for now
    return []


async def get_prior_year_return(
    session: AsyncSession,
    client_id: int,
    tax_year: int,
) -> dict[str, Any] | None:
    """Get prior year return data for comparison.

    Stub for Phase 3 (Document Processing).

    Args:
        session: Database session
        client_id: Client ID
        tax_year: Current tax year (will fetch tax_year - 1)

    Returns:
        Prior year return data or None if not available
    """
    # TODO: Implement in Phase 3 when prior year data is stored
    # Will query for completed returns from previous year
    _ = session, client_id, tax_year  # Acknowledge unused for now
    return None


async def build_agent_context(
    session: AsyncSession,
    client_id: int,
    task_type: str,
    tax_year: int,
) -> AgentContext:
    """Build complete context for agent execution.

    Assembles all components needed for an agent to execute a task:
    1. Client info and computed profile view
    2. Documents relevant to the task
    3. Skills required for the task type
    4. Prior year return for comparison

    Args:
        session: Database session
        client_id: Client ID
        task_type: Type of task to build context for
        tax_year: Tax year for the task

    Returns:
        AgentContext with all components assembled

    Raises:
        ValueError: If client not found

    Example:
        >>> context = await build_agent_context(
        ...     session,
        ...     client_id=1,
        ...     task_type="w2_extraction",
        ...     tax_year=2024
        ... )
        >>> context.client_name
        "John Doe"
        >>> len(context.skills)
        2
    """
    # Fetch client
    stmt = select(Client).where(Client.id == client_id)
    result = await session.execute(stmt)
    client = result.scalar_one_or_none()

    if client is None:
        raise ValueError(f"Client not found: {client_id}")

    # Get computed profile view
    profile = await get_client_profile_view(session, client_id)

    # Get documents (stub for now)
    documents = await get_client_documents(session, client_id, tax_year)

    # Load skills for task type
    skill_names = get_skills_for_task_type(task_type)
    skills: list[dict[str, Any]] = []

    for skill_name in skill_names:
        skill = await load_skill_for_year(session, skill_name, tax_year)
        if skill is not None:
            skills.append(skill.to_prompt_context())

    # Get prior year return (stub for now)
    prior_return = await get_prior_year_return(session, client_id, tax_year)

    return AgentContext(
        client_id=client_id,
        client_name=client.name,
        tax_year=tax_year,
        task_type=task_type,
        client_profile=profile,
        documents=documents,
        skills=skills,
        prior_year_return=prior_return,
    )
