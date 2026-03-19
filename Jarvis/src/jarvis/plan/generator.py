"""AI-powered plan generation for weekly planning.

This module handles communication with the Claude API to generate
personalized weekly plans based on context, tasks, and gap analysis.
"""

import json
import logging
from datetime import date

from rich.console import Console

from ..models import Task
from ..models.plan import (
    DailyPlan,
    GapAnalysis,
    PlanContext,
    QuickAction,
)
from .prompts import (
    PLAN_SYSTEM_PROMPT,
    build_plan_prompt,
    build_interactive_questions_prompt,
)

logger = logging.getLogger(__name__)
console = Console()


class PlanGenerator:
    """AI-powered plan generation using Claude."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514") -> None:
        """Initialize the plan generator.

        Args:
            api_key: Anthropic API key
            model: Model to use for generation
        """
        try:
            from anthropic import Anthropic
        except ImportError:
            raise RuntimeError(
                "anthropic package not installed. Run: uv pip install anthropic"
            )

        self.client = Anthropic(api_key=api_key)
        self.model = model

    def generate(
        self,
        context: PlanContext,
        tasks: list[Task],
        gap_analysis: GapAnalysis,
        start_date: date,
        days: int,
    ) -> tuple[list[DailyPlan], list[QuickAction]]:
        """Generate daily plans and quick actions.

        Args:
            context: Parsed planning context
            tasks: Tasks in planning window
            gap_analysis: Detected gaps
            start_date: First day of plan
            days: Planning horizon

        Returns:
            Tuple of (daily_plans, quick_actions)
        """
        from datetime import timedelta

        end_date = start_date + timedelta(days=days - 1)

        # Format inputs for prompt
        task_list = self._format_tasks(tasks)
        gap_summary = self._format_gaps(gap_analysis)

        prompt = build_plan_prompt(
            user_context=context.raw_context,
            task_list=task_list,
            gap_summary=gap_summary,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            days=days,
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=3000,
                temperature=0.3,
                system=PLAN_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = getattr(response.content[0], "text", "")
            return self._parse_plan_response(response_text, start_date, days)

        except Exception as e:
            logger.warning(f"AI plan generation failed: {e}")
            console.print(f"[yellow]Warning: AI generation failed, using fallback plan[/yellow]")
            return self._generate_fallback_plan(tasks, gap_analysis, start_date, days)

    def generate_questions(
        self,
        context: PlanContext,
        gap_analysis: GapAnalysis,
    ) -> list[dict[str, str]]:
        """Generate follow-up questions based on gaps.

        Args:
            context: Planning context
            gap_analysis: Detected gaps

        Returns:
            List of questions with context
        """
        plan_summary = f"Focus: {context.focus.mode.value}, Goals: {len(context.goals)}"
        gaps = self._format_gaps(gap_analysis)

        prompt = build_interactive_questions_prompt(
            plan_summary=plan_summary,
            gaps=gaps,
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.3,
                system=PLAN_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = getattr(response.content[0], "text", "")
            return self._parse_questions_response(response_text)

        except Exception as e:
            logger.warning(f"Failed to generate questions: {e}")
            return []

    def _format_tasks(self, tasks: list[Task]) -> str:
        """Format tasks for the prompt.

        Args:
            tasks: List of tasks

        Returns:
            Formatted task list string
        """
        if not tasks:
            return "No tasks scheduled in this period."

        lines: list[str] = []
        for t in tasks:
            date_str = t.scheduled_date.isoformat() if t.scheduled_date else "unscheduled"
            priority = f" [{t.priority.value}]" if t.priority else ""
            tags = f" #{', #'.join(t.tags)}" if t.tags else ""
            lines.append(f"- [{date_str}] {t.name}{priority}{tags}")

        return "\n".join(lines)

    def _format_gaps(self, gap_analysis: GapAnalysis) -> str:
        """Format gap analysis for the prompt.

        Args:
            gap_analysis: Gap analysis results

        Returns:
            Formatted gap summary
        """
        sections: list[str] = []

        if gap_analysis.goals_without_tasks:
            goals = "\n".join(f"  - {g.text}" for g in gap_analysis.goals_without_tasks)
            sections.append(f"Goals without tasks:\n{goals}")

        if gap_analysis.focus_conflicts:
            conflicts = "\n".join(f"  - {c}" for c in gap_analysis.focus_conflicts)
            sections.append(f"Focus conflicts:\n{conflicts}")

        if gap_analysis.schedule_issues:
            issues = "\n".join(f"  - {i}" for i in gap_analysis.schedule_issues)
            sections.append(f"Schedule issues:\n{issues}")

        if not sections:
            return "No significant gaps detected. Schedule appears well-aligned."

        return "\n\n".join(sections)

    def _parse_plan_response(
        self,
        text: str,
        start_date: date,
        days: int,
    ) -> tuple[list[DailyPlan], list[QuickAction]]:
        """Parse JSON response into plan objects.

        Args:
            text: Response text from Claude
            start_date: Start date for plan
            days: Number of days

        Returns:
            Tuple of (daily_plans, quick_actions)
        """
        try:
            # Extract JSON from response
            start = text.find("{")
            end = text.rfind("}") + 1

            if start == -1 or end == 0:
                logger.warning("No JSON found in plan response")
                return self._generate_fallback_plan([], GapAnalysis.empty(), start_date, days)

            data = json.loads(text[start:end])

            # Parse daily plans
            daily_plans: list[DailyPlan] = []
            for dp in data.get("daily_plans", []):
                try:
                    plan_date = date.fromisoformat(dp["date"])
                    daily_plans.append(
                        DailyPlan(
                            plan_date=plan_date,
                            day_name=dp.get("day_name", plan_date.strftime("%A")),
                            theme=dp.get("theme", ""),
                            existing_tasks=dp.get("existing_tasks", []),
                            suggestions=dp.get("suggestions", []),
                            actions=dp.get("actions", []),
                            warnings=dp.get("warnings", []),
                        )
                    )
                except (KeyError, ValueError) as e:
                    logger.warning(f"Failed to parse daily plan: {e}")

            # Parse quick actions
            quick_actions: list[QuickAction] = []
            for idx, qa in enumerate(data.get("quick_actions", []), 1):
                try:
                    quick_actions.append(
                        QuickAction(
                            label=f"[{idx}]",
                            command=qa["command"],
                            description=qa.get("description", ""),
                        )
                    )
                except KeyError as e:
                    logger.warning(f"Failed to parse quick action: {e}")

            return daily_plans, quick_actions

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse plan JSON: {e}")
            return self._generate_fallback_plan([], GapAnalysis.empty(), start_date, days)

    def _parse_questions_response(self, text: str) -> list[dict[str, str]]:
        """Parse questions response.

        Args:
            text: Response text

        Returns:
            List of question dicts
        """
        try:
            start = text.find("{")
            end = text.rfind("}") + 1

            if start == -1 or end == 0:
                return []

            data = json.loads(text[start:end])
            return data.get("questions", [])

        except json.JSONDecodeError:
            return []

    def _generate_fallback_plan(
        self,
        tasks: list[Task],
        gap_analysis: GapAnalysis,
        start_date: date,
        days: int,
    ) -> tuple[list[DailyPlan], list[QuickAction]]:
        """Generate a basic plan without AI.

        Args:
            tasks: Tasks in planning window
            gap_analysis: Gap analysis results
            start_date: Start date
            days: Number of days

        Returns:
            Basic daily plans and quick actions
        """
        from datetime import timedelta

        daily_plans: list[DailyPlan] = []

        # Group tasks by date
        tasks_by_date: dict[date, list[str]] = {}
        for task in tasks:
            if task.scheduled_date:
                if task.scheduled_date not in tasks_by_date:
                    tasks_by_date[task.scheduled_date] = []
                tasks_by_date[task.scheduled_date].append(task.name)

        current = start_date
        for _ in range(days):
            day_tasks = tasks_by_date.get(current, [])
            task_count = len(day_tasks)

            # Determine theme
            if current.weekday() >= 5:  # Weekend
                theme = "Weekend"
            elif task_count > 6:
                theme = "Heavy day"
            elif task_count <= 2:
                theme = "Light day"
            else:
                theme = "Normal day"

            warnings = []
            if task_count > 6:
                warnings.append(f"Overloaded with {task_count} tasks")

            daily_plans.append(
                DailyPlan(
                    plan_date=current,
                    day_name=current.strftime("%A"),
                    theme=theme,
                    existing_tasks=day_tasks,
                    suggestions=[],
                    actions=[],
                    warnings=warnings,
                )
            )

            current += timedelta(days=1)

        # Generate quick actions from unmatched goals
        quick_actions: list[QuickAction] = []
        for idx, goal in enumerate(gap_analysis.goals_without_tasks[:3], 1):
            # Create a simple task command
            task_title = goal.text[:50]  # Truncate long goals
            quick_actions.append(
                QuickAction(
                    label=f"[{idx}]",
                    command=f'jarvis t "{task_title}" -p high',
                    description=f"Add task for: {goal.text[:30]}...",
                )
            )

        return daily_plans, quick_actions
