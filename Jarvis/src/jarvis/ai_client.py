"""AI client for generating scheduling suggestions."""

import json
from datetime import date, datetime
from uuid import uuid4

from rich.console import Console

from jarvis.models import Suggestion, Task, UserContext, WorkloadAnalysis
from jarvis.prompts import SYSTEM_PROMPT, build_suggestion_prompt

console = Console()


class AIClient:
    """Client for generating suggestions using Claude."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514") -> None:
        """Initialize the AI client.

        Args:
            api_key: Anthropic API key
            model: Model to use for suggestions
        """
        try:
            from anthropic import Anthropic
        except ImportError:
            raise RuntimeError(
                "anthropic package not installed. Run: uv pip install anthropic"
            )

        self.client = Anthropic(api_key=api_key)
        self.model = model

    def generate_suggestions(
        self,
        tasks: list[Task],
        analysis: WorkloadAnalysis,
        context: UserContext,
        max_suggestions: int = 10,
    ) -> list[Suggestion]:
        """Generate rescheduling suggestions using AI.

        Args:
            tasks: List of tasks to consider
            analysis: Workload analysis
            context: User context (preferences, patterns, etc.)
            max_suggestions: Maximum number of suggestions

        Returns:
            List of Suggestion objects
        """
        # Filter to only moveable tasks
        moveable_tasks = [t for t in tasks if t.is_moveable]

        if not moveable_tasks:
            return []

        # Build the prompt
        task_list = self._format_tasks(tasks)
        workload_summary = self._format_analysis(analysis)
        user_context = context.to_prompt_context()

        prompt = build_suggestion_prompt(
            task_list=task_list,
            workload_summary=workload_summary,
            user_context=user_context,
            today=date.today().isoformat(),
        )

        # Call Claude
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=0.3,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = getattr(response.content[0], "text", "")
            return self._parse_response(response_text, tasks, max_suggestions)

        except Exception as e:
            console.print(f"[yellow]Warning: AI request failed: {e}[/yellow]")
            return []

    def _format_tasks(self, tasks: list[Task]) -> str:
        """Format tasks for the prompt.

        Args:
            tasks: List of tasks

        Returns:
            Formatted task list string
        """
        lines: list[str] = []
        for t in tasks:
            icon = "🔒" if not t.is_moveable else "📦"
            date_str = t.scheduled_date.isoformat() if t.scheduled_date else "unscheduled"
            deadline = f" (due: {t.due_date})" if t.due_date else ""
            priority = f" [{t.priority}]" if t.priority else ""
            lines.append(f"{icon} [{date_str}] {t.name}{deadline}{priority}")

        return "\n".join(lines)

    def _format_analysis(self, analysis: WorkloadAnalysis) -> str:
        """Format workload analysis for the prompt.

        Args:
            analysis: WorkloadAnalysis object

        Returns:
            Formatted analysis string
        """
        lines: list[str] = [
            f"Period: {analysis.start_date} to {analysis.end_date}",
            f"Total moveable tasks: {analysis.total_moveable}",
            f"Total immovable tasks: {analysis.total_immovable}",
            f"Workload variance: {analysis.variance:.1f}",
            "",
            "Daily breakdown:",
        ]

        for day in analysis.days:
            status = {"overloaded": "⚠️", "light": "○", "balanced": "✓"}[day.status]
            lines.append(
                f"  {day.day_date.strftime('%a %b %d')}: {day.total_tasks} tasks "
                f"({day.moveable_tasks} moveable) {status} {day.status}"
            )

        return "\n".join(lines)

    def _parse_response(
        self,
        text: str,
        tasks: list[Task],
        max_suggestions: int,
    ) -> list[Suggestion]:
        """Parse JSON suggestions from Claude's response.

        Args:
            text: Response text from Claude
            tasks: Original task list (for ID lookup)
            max_suggestions: Maximum suggestions to return

        Returns:
            List of Suggestion objects
        """
        try:
            # Find JSON block in response
            start = text.find("{")
            end = text.rfind("}") + 1

            if start == -1 or end == 0:
                console.print("[yellow]Warning: No JSON found in AI response[/yellow]")
                return []

            data = json.loads(text[start:end])
            raw_suggestions = data.get("suggestions", [])

            # Build task lookup by name
            task_by_name = {t.name: t for t in tasks}

            suggestions: list[Suggestion] = []
            for s in raw_suggestions[:max_suggestions]:
                task_name = s.get("task_name", "")
                task = task_by_name.get(task_name)

                if not task:
                    console.print(
                        f"[yellow]Warning: Task '{task_name}' not found, skipping[/yellow]"
                    )
                    continue

                if not task.is_moveable:
                    console.print(
                        f"[yellow]Warning: Task '{task_name}' is immovable, skipping[/yellow]"
                    )
                    continue

                try:
                    suggestions.append(
                        Suggestion(
                            id=f"sug_{uuid4().hex[:8]}",
                            task_id=task.id,
                            task_name=task_name,
                            current_date=date.fromisoformat(s["current_date"]),
                            proposed_date=date.fromisoformat(s["proposed_date"]),
                            reasoning=s.get("reasoning", "No reason provided"),
                            confidence=float(s.get("confidence", 0.7)),
                            status="pending",
                            created_at=datetime.now(),
                        )
                    )
                except (KeyError, ValueError) as e:
                    console.print(
                        f"[yellow]Warning: Invalid suggestion format: {e}[/yellow]"
                    )
                    continue

            return suggestions

        except json.JSONDecodeError as e:
            console.print(f"[yellow]Warning: Could not parse AI response: {e}[/yellow]")
            return []
