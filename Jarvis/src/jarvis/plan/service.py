"""Plan service for weekly planning orchestration.

This module provides the main PlanService class that orchestrates
all components of the weekly planning feature.
"""

import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path

from ..services.task_service import TaskService
from ..models.plan import WeeklyPlan
from .alignment import calculate_alignment, build_task_reality
from .context_parser import parse_context
from .gaps import detect_gaps
from .generator import PlanGenerator
from .formatter import format_plan_for_file

logger = logging.getLogger(__name__)


class PlanService:
    """Orchestrates weekly plan generation.

    Coordinates context parsing, task retrieval, alignment analysis,
    gap detection, and AI-powered plan generation.

    Usage:
        service = PlanService()
        plan = service.generate_plan(days=7)
    """

    def __init__(self, backend: str | None = None) -> None:
        """Initialize plan service.

        Args:
            backend: Optional backend name override
        """
        self._task_service = TaskService(backend=backend)
        self._generator: PlanGenerator | None = None
        self._backend = backend

    @property
    def generator(self) -> PlanGenerator:
        """Get or create the AI plan generator."""
        if self._generator is None:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY environment variable not set. "
                    "AI-powered planning requires an API key."
                )
            self._generator = PlanGenerator(api_key=api_key)
        return self._generator

    def generate_plan(
        self,
        days: int = 7,
    ) -> WeeklyPlan:
        """Generate a complete weekly plan.

        Args:
            days: Planning horizon (1-30 days)

        Returns:
            WeeklyPlan with all sections populated
        """
        # Validate days
        if days < 1 or days > 30:
            raise ValueError("Planning horizon must be between 1 and 30 days")

        # Calculate date range
        start_date = date.today()
        end_date = start_date + timedelta(days=days - 1)

        # Step 1: Parse context
        context = parse_context()

        # Step 2: Connect and retrieve tasks
        self._task_service.connect()
        tasks = self._task_service.get_tasks(
            start_date=start_date,
            end_date=end_date,
            include_done=False,
        )

        # Step 3: Calculate alignment
        alignment_result = calculate_alignment(tasks, context)

        # Step 4: Build task reality
        task_reality = build_task_reality(
            tasks=tasks,
            alignment_result=alignment_result,
            start_date=start_date,
            end_date=end_date,
        )

        # Step 5: Detect gaps
        gap_analysis = detect_gaps(
            tasks=tasks,
            context=context,
            categories=alignment_result.categories,
            start_date=start_date,
            end_date=end_date,
        )

        # Step 6: Generate AI plan
        daily_plans, quick_actions = self.generator.generate(
            context=context,
            tasks=tasks,
            gap_analysis=gap_analysis,
            start_date=start_date,
            days=days,
        )

        return WeeklyPlan(
            focus_summary=context.focus,
            task_reality=task_reality,
            gap_analysis=gap_analysis,
            daily_plans=daily_plans,
            quick_actions=quick_actions,
            generated_at=datetime.now(),
            planning_horizon=days,
            context_quality=context.context_quality,
        )

    def generate_interactive_questions(
        self,
        plan: WeeklyPlan,
    ) -> list[dict[str, str]]:
        """Generate follow-up questions based on plan gaps.

        Args:
            plan: Initial generated plan

        Returns:
            List of question dicts with 'question' and 'context' keys
        """
        # Reconstruct context for question generation
        context = parse_context()

        return self.generator.generate_questions(
            context=context,
            gap_analysis=plan.gap_analysis,
        )

    def save_plan(self, plan: WeeklyPlan, custom_path: str | None = None) -> Path:
        """Save plan to a markdown file.

        Args:
            plan: WeeklyPlan to save
            custom_path: Optional custom file path

        Returns:
            Path to the saved file
        """
        if custom_path:
            file_path = Path(custom_path)
        else:
            # Default to ~/.jarvis/plans/YYYY-MM-DD.md
            plans_dir = Path.home() / ".jarvis" / "plans"
            plans_dir.mkdir(parents=True, exist_ok=True)
            file_path = plans_dir / f"{date.today().isoformat()}.md"

        # Format and write
        content = format_plan_for_file(plan)
        file_path.write_text(content)

        logger.info(f"Plan saved to {file_path}")
        return file_path


def get_plan_service(backend: str | None = None) -> PlanService:
    """Factory function to get a PlanService instance.

    Args:
        backend: Optional backend name

    Returns:
        PlanService instance
    """
    return PlanService(backend=backend)
