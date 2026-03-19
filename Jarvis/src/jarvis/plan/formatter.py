"""Rich output formatting for weekly planning.

This module handles terminal output formatting using the Rich library,
consistent with other Jarvis commands.
"""

from datetime import date

from rich.console import Console
from rich.panel import Panel

from ..models.plan import (
    DailyPlan,
    FocusSummary,
    GapAnalysis,
    QuickAction,
    TaskReality,
    WeeklyPlan,
)


def format_plan(plan: WeeklyPlan, console: Console) -> None:
    """Display the complete weekly plan with Rich formatting.

    Args:
        plan: WeeklyPlan to display
        console: Rich console for output
    """
    # Section 1: Focus Summary
    format_focus_summary(plan.focus_summary, console)

    console.print()

    # Section 2: Current Reality
    format_task_reality(plan.task_reality, console)

    console.print()

    # Section 3: Gap Analysis
    format_gap_analysis(plan.gap_analysis, console)

    console.print()

    # Section 4: Recommended Plan
    format_daily_plans(plan.daily_plans, console)

    console.print()

    # Section 5: Quick Actions
    if plan.quick_actions:
        format_quick_actions(plan.quick_actions, console)

    # Context quality indicator
    if plan.context_quality != "full":
        _format_context_warning(plan.context_quality, console)


def format_focus_summary(focus: FocusSummary, console: Console) -> None:
    """Format the focus summary section.

    Args:
        focus: Focus summary to display
        console: Rich console for output
    """
    if focus.primary_goal:
        title = f"{focus.mode_emoji} Weekly Focus: {focus.primary_goal[:40]}"
    else:
        title = f"{focus.mode_emoji} Weekly Focus"

    content_lines: list[str] = []

    # Mode with duration
    mode_text = f"Mode: {focus.mode_emoji} {focus.mode.value.title()}"
    if focus.until_date:
        mode_text += f" (until {focus.until_date.strftime('%b %d')})"
    content_lines.append(mode_text)

    # Primary goal
    if focus.primary_goal:
        content_lines.append(f"Primary Goal: {focus.primary_goal}")

    # Decision rule
    if focus.decision_rule:
        content_lines.append(f"Decision Rule: {focus.decision_rule}")

    content = "\n".join(content_lines) if content_lines else "No focus mode set"

    console.print(Panel(content, title=title, border_style="cyan"))


def format_task_reality(reality: TaskReality, console: Console) -> None:
    """Format the current task reality section.

    Args:
        reality: Task reality to display
        console: Rich console for output
    """
    # Build header
    start_date = min(reality.tasks_by_day.keys()) if reality.tasks_by_day else date.today()
    end_date = max(reality.tasks_by_day.keys()) if reality.tasks_by_day else date.today()

    title = f"📋 Scheduled Tasks ({start_date.strftime('%b %d')} - {end_date.strftime('%b %d')})"

    content_lines: list[str] = []

    # Task count summary
    day_count = len(reality.tasks_by_day) if reality.tasks_by_day else 0
    content_lines.append(f"{reality.total_tasks} tasks scheduled across {day_count} days")
    content_lines.append("")

    # Category breakdown
    if reality.tasks_by_category:
        content_lines.append("By Category:")
        for category in reality.tasks_by_category:
            pct = (category.task_count / reality.total_tasks * 100) if reality.total_tasks > 0 else 0
            alignment = "✓ Aligned" if category.is_aligned else "⚠️ Potential conflict"
            content_lines.append(
                f"  {category.emoji} {category.name}: {category.task_count} tasks ({pct:.0f}%) {alignment}"
            )

    content_lines.append("")

    # Alignment score with color
    score = reality.alignment_percent
    if score >= 70:
        score_text = f"[green]Alignment Score: {score}%[/green]"
    elif score >= 40:
        score_text = f"[yellow]Alignment Score: {score}%[/yellow]"
    else:
        score_text = f"[red]Alignment Score: {score}%[/red]"

    content = "\n".join(content_lines)

    console.print(Panel(content, title=title, border_style="white"))
    console.print(f"  {score_text}")


def format_gap_analysis(gaps: GapAnalysis, console: Console) -> None:
    """Format the gap analysis section.

    Args:
        gaps: Gap analysis to display
        console: Rich console for output
    """
    title = "🔍 Gap Analysis"

    if gaps.total_gaps == 0:
        console.print(
            Panel(
                "[green]✓ No significant gaps detected. Schedule appears well-aligned.[/green]",
                title=title,
                border_style="green",
            )
        )
        return

    content_lines: list[str] = []

    # Alert header
    if gaps.has_critical_gaps:
        content_lines.append("[bold red]⚠️  MISALIGNMENT DETECTED[/bold red]")
        content_lines.append("")

    # Goals without tasks
    if gaps.goals_without_tasks:
        content_lines.append("[bold]Goals without tasks:[/bold]")
        for goal in gaps.goals_without_tasks[:5]:  # Limit to 5
            content_lines.append(f"  • \"{goal.text[:50]}\" — No task found")
        if len(gaps.goals_without_tasks) > 5:
            content_lines.append(f"  ... and {len(gaps.goals_without_tasks) - 5} more")
        content_lines.append("")

    # Focus conflicts
    if gaps.focus_conflicts:
        content_lines.append("[bold]Focus conflicts:[/bold]")
        for conflict in gaps.focus_conflicts:
            content_lines.append(f"  • {conflict}")
        content_lines.append("")

    # Schedule issues
    if gaps.schedule_issues:
        content_lines.append("[bold]Schedule issues:[/bold]")
        for issue in gaps.schedule_issues:
            content_lines.append(f"  • {issue}")

    content = "\n".join(content_lines).rstrip()
    border_style = "yellow" if gaps.has_critical_gaps else "white"

    console.print(Panel(content, title=title, border_style=border_style))


def format_daily_plans(plans: list[DailyPlan], console: Console) -> None:
    """Format the recommended weekly plan section.

    Args:
        plans: List of daily plans
        console: Rich console for output
    """
    title = "📅 Recommended Weekly Plan"

    console.print(Panel.fit(title, border_style="cyan"))
    console.print()

    for plan in plans:
        _format_single_day(plan, console)


def _format_single_day(plan: DailyPlan, console: Console) -> None:
    """Format a single day's plan.

    Args:
        plan: DailyPlan to format
        console: Rich console for output
    """
    # Day header
    day_header = f"[bold]{plan.day_name.upper()}[/bold] ({plan.plan_date.strftime('%b %d')})"
    if plan.theme:
        day_header += f" — {plan.theme}"

    console.print(day_header)

    # Warnings first
    for warning in plan.warnings:
        console.print(f"  [yellow]⚠️ {warning}[/yellow]")

    # Existing tasks
    if plan.existing_tasks:
        task_count = len(plan.existing_tasks)
        console.print(f"  [dim]✓ {task_count} task(s) scheduled[/dim]")

    # Suggestions
    for suggestion in plan.suggestions:
        console.print(f"  [blue]+ Suggested: {suggestion}[/blue]")

    # Actions
    for action in plan.actions:
        console.print(f"  [magenta]→ {action}[/magenta]")

    # Empty day placeholder
    if not plan.existing_tasks and not plan.suggestions and not plan.warnings:
        console.print("  [dim]No tasks scheduled[/dim]")

    console.print()


def format_quick_actions(actions: list[QuickAction], console: Console) -> None:
    """Format the quick actions section.

    Args:
        actions: List of quick actions
        console: Rich console for output
    """
    console.print("━" * 50)
    console.print()
    console.print("[bold]Quick Actions:[/bold]")

    for action in actions:
        console.print(f"  {action.label} [cyan]{action.command}[/cyan]")
        if action.description:
            console.print(f"      [dim]{action.description}[/dim]")


def _format_context_warning(quality: str, console: Console) -> None:
    """Format a warning about context quality.

    Args:
        quality: Context quality level
        console: Rich console for output
    """
    console.print()

    warnings = {
        "partial": "[yellow]ℹ️ Partial context: Some context files missing. Run 'jarvis context status' for details.[/yellow]",
        "minimal": "[yellow]⚠️ Minimal context: Limited personalization. Run 'jarvis init' to set up context files.[/yellow]",
        "none": "[red]⚠️ No context files found. Run 'jarvis init --global' to enable personalized planning.[/red]",
    }

    if quality in warnings:
        console.print(warnings[quality])


def format_plan_for_file(plan: WeeklyPlan) -> str:
    """Format plan as markdown for file saving.

    Args:
        plan: WeeklyPlan to format

    Returns:
        Markdown string
    """
    lines: list[str] = []

    # Header
    lines.append(f"# Weekly Plan - {plan.generated_at.strftime('%B %d, %Y')}")
    lines.append("")
    lines.append(f"Generated at: {plan.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # Focus Summary
    lines.append("## Focus Summary")
    lines.append("")
    lines.append(f"**Mode:** {plan.focus_summary.mode_emoji} {plan.focus_summary.mode.value.title()}")
    if plan.focus_summary.until_date:
        lines.append(f"**Until:** {plan.focus_summary.until_date.strftime('%B %d, %Y')}")
    if plan.focus_summary.primary_goal:
        lines.append(f"**Primary Goal:** {plan.focus_summary.primary_goal}")
    if plan.focus_summary.decision_rule:
        lines.append(f"**Decision Rule:** {plan.focus_summary.decision_rule}")
    lines.append("")

    # Current Reality
    lines.append("## Current Reality")
    lines.append("")
    lines.append(f"{plan.task_reality.total_tasks} tasks scheduled")
    lines.append("")

    if plan.task_reality.tasks_by_category:
        lines.append("| Category | Tasks | Alignment |")
        lines.append("|----------|-------|-----------|")
        for cat in plan.task_reality.tasks_by_category:
            pct = (cat.task_count / plan.task_reality.total_tasks * 100) if plan.task_reality.total_tasks > 0 else 0
            alignment = "✓ Aligned" if cat.is_aligned else "⚠️ Conflict"
            lines.append(f"| {cat.emoji} {cat.name} | {cat.task_count} ({pct:.0f}%) | {alignment} |")
        lines.append("")

    lines.append(f"**Alignment Score:** {plan.task_reality.alignment_percent}%")
    lines.append("")

    # Gap Analysis
    lines.append("## Gap Analysis")
    lines.append("")

    if plan.gap_analysis.total_gaps == 0:
        lines.append("✓ No significant gaps detected.")
    else:
        if plan.gap_analysis.has_critical_gaps:
            lines.append("⚠️ **MISALIGNMENT DETECTED**")
            lines.append("")

        if plan.gap_analysis.goals_without_tasks:
            lines.append("**Goals without tasks:**")
            for goal in plan.gap_analysis.goals_without_tasks:
                lines.append(f"- {goal.text}")
            lines.append("")

        if plan.gap_analysis.focus_conflicts:
            lines.append("**Focus conflicts:**")
            for conflict in plan.gap_analysis.focus_conflicts:
                lines.append(f"- {conflict}")
            lines.append("")

        if plan.gap_analysis.schedule_issues:
            lines.append("**Schedule issues:**")
            for issue in plan.gap_analysis.schedule_issues:
                lines.append(f"- {issue}")
            lines.append("")

    # Daily Plans
    lines.append("## Daily Plans")
    lines.append("")

    for dp in plan.daily_plans:
        lines.append(f"### {dp.day_name} ({dp.plan_date.strftime('%b %d')})")
        if dp.theme:
            lines.append(f"**Theme:** {dp.theme}")
        lines.append("")

        for warning in dp.warnings:
            lines.append(f"- ⚠️ {warning}")

        if dp.existing_tasks:
            lines.append(f"- ✓ {len(dp.existing_tasks)} task(s) scheduled")

        for suggestion in dp.suggestions:
            lines.append(f"- + Suggested: {suggestion}")

        for action in dp.actions:
            lines.append(f"- → {action}")

        lines.append("")

    # Quick Actions
    if plan.quick_actions:
        lines.append("## Quick Actions")
        lines.append("")
        for action in plan.quick_actions:
            lines.append(f"{action.label} `{action.command}`")
            if action.description:
                lines.append(f"   {action.description}")
        lines.append("")

    return "\n".join(lines)
