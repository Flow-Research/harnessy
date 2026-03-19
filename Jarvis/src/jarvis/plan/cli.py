"""CLI command for weekly planning.

This module defines the Click command for `jarvis plan` and its options.
"""

import click
from rich.console import Console

from .formatter import format_plan
from .service import get_plan_service

console = Console()


@click.command("plan")
@click.option(
    "--days", "-d",
    default=7,
    type=click.IntRange(1, 30),
    help="Planning horizon in days (1-30, default: 7)"
)
@click.option(
    "--interactive", "-i",
    is_flag=True,
    default=False,
    help="Enable interactive Q&A mode after generating plan"
)
@click.option(
    "--save", "-s",
    is_flag=True,
    default=False,
    help="Save plan to ~/.jarvis/plans/"
)
def plan_command(days: int, interactive: bool, save: bool) -> None:
    """Generate a weekly plan based on your goals and scheduled tasks.

    Analyzes your context files (goals.md, focus.md, priorities.md, etc.)
    and compares them against your scheduled tasks to identify:

    \b
    - Goals without supporting tasks
    - Focus mode conflicts
    - Overloaded or empty days
    - Recommended actions for alignment

    Examples:

    \b
        jarvis plan              # Generate 7-day plan
        jarvis plan --days 14    # Generate 14-day plan
        jarvis plan -i           # Interactive mode with Q&A
        jarvis plan --save       # Save plan to file
    """
    try:
        # Get plan service
        service = get_plan_service()

        # Generate the plan
        with console.status("[cyan]Generating weekly plan...[/cyan]"):
            plan = service.generate_plan(days=days)

        # Display the plan
        format_plan(plan, console)

        # Save if requested
        if save:
            saved_path = service.save_plan(plan)
            console.print()
            console.print(f"[green]✓ Plan saved to:[/green] {saved_path}")

        # Interactive mode
        if interactive:
            _run_interactive_mode(service, plan)

    except RuntimeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        raise SystemExit(1)


def _run_interactive_mode(service, plan) -> None:
    """Run interactive Q&A session.

    Args:
        service: PlanService instance
        plan: Generated WeeklyPlan
    """
    console.print()
    console.print("━" * 50)
    console.print("[bold]Interactive Planning Session[/bold]")
    console.print("━" * 50)
    console.print()

    # Generate questions
    with console.status("[cyan]Generating questions...[/cyan]"):
        questions = service.generate_interactive_questions(plan)

    if not questions:
        console.print("[dim]No follow-up questions generated. Your plan looks well-aligned.[/dim]")
        return

    console.print("I have a few questions to help refine your plan:")
    console.print("[dim]Type 'q', 'quit', or 'exit' to end the session.[/dim]")
    console.print()

    answers: dict[str, str] = {}

    for i, q in enumerate(questions, 1):
        question = q.get("question", "")
        context = q.get("context", "")

        if context:
            console.print(f"[dim]Context: {context}[/dim]")

        console.print(f"[bold]{i}. {question}[/bold]")
        console.print()

        try:
            answer = click.prompt(">", default="", show_default=False)
        except (KeyboardInterrupt, EOFError):
            console.print()
            console.print("[dim]Session ended.[/dim]")
            return

        # Check for exit commands
        if answer.lower() in ("q", "quit", "exit"):
            console.print("[dim]Session ended.[/dim]")
            return

        answers[question] = answer
        console.print()

    # TODO: Implement plan refinement based on answers
    # For now, just acknowledge the input
    console.print("[green]✓ Thank you for your answers. Plan refinement coming in a future update.[/green]")


# Create alias command
@click.command("p")
@click.option("--days", "-d", default=7, type=click.IntRange(1, 30))
@click.option("--interactive", "-i", is_flag=True, default=False)
@click.option("--save", "-s", is_flag=True, default=False)
@click.pass_context
def plan_alias(ctx: click.Context, days: int, interactive: bool, save: bool) -> None:
    """Alias for 'jarvis plan'. See 'jarvis plan --help' for details."""
    ctx.invoke(plan_command, days=days, interactive=interactive, save=save)
