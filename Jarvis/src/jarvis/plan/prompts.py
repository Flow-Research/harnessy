"""AI prompt templates for weekly planning.

This module contains the system and user prompts used for AI-powered
plan generation via the Anthropic Claude API.
"""

PLAN_SYSTEM_PROMPT = """You are Jarvis, a proactive planning assistant.
Your job is to help users align their weekly schedule with their stated goals and priorities.

You will receive:
1. User context (goals, focus mode, constraints)
2. Scheduled tasks for the planning period
3. Gap analysis (goals without tasks, conflicts)

Generate a personalized weekly plan that:
- Respects the user's stated focus mode
- Suggests tasks for unaddressed goals
- Identifies days that need rebalancing
- Provides ready-to-run jarvis commands

Be concise and actionable. Do not lecture or over-explain.
Focus on practical recommendations the user can act on immediately."""


def build_plan_prompt(
    user_context: str,
    task_list: str,
    gap_summary: str,
    start_date: str,
    end_date: str,
    days: int,
) -> str:
    """Build the user prompt for plan generation.

    Args:
        user_context: Formatted user context from context files
        task_list: Formatted list of scheduled tasks
        gap_summary: Summary of detected gaps
        start_date: Start of planning window (ISO format)
        end_date: End of planning window (ISO format)
        days: Number of days in planning window

    Returns:
        Formatted prompt string
    """
    return f"""# Weekly Planning Request

## User Context
{user_context}

## Scheduled Tasks ({start_date} to {end_date})
{task_list}

## Gap Analysis
{gap_summary}

## Instructions

Generate a {days}-day plan with the following JSON structure:

```json
{{
  "daily_plans": [
    {{
      "date": "YYYY-MM-DD",
      "day_name": "Monday",
      "theme": "Deep work day",
      "suggestions": ["Task suggestion 1", "Task suggestion 2"],
      "actions": ["Defer X to next week", "Protect morning for Y"],
      "warnings": ["Day is overloaded with N tasks"]
    }}
  ],
  "quick_actions": [
    {{
      "command": "jarvis t \\"Task title\\" -d monday -p high -t tag",
      "description": "Add missing task for goal X"
    }}
  ]
}}
```

Guidelines:
- Generate one daily_plan entry for each day in the planning window
- Keep suggestions actionable and specific
- Provide 2-4 quick_actions for the most impactful missing tasks
- If a day is overloaded (>6 tasks), include a warning
- Match task suggestions to unaddressed goals from the gap analysis
- Respect the user's focus mode when making suggestions

Output ONLY the JSON, no additional text."""


def build_interactive_questions_prompt(
    plan_summary: str,
    gaps: str,
) -> str:
    """Build prompt for generating interactive follow-up questions.

    Args:
        plan_summary: Summary of the generated plan
        gaps: Detected gaps and conflicts

    Returns:
        Formatted prompt string
    """
    return f"""Based on this weekly plan and detected gaps, generate 2-5 clarifying questions
to help refine the plan.

## Current Plan Summary
{plan_summary}

## Detected Gaps
{gaps}

## Instructions

Generate questions that:
1. Address the most critical gaps first
2. Help prioritize conflicting tasks
3. Clarify user preferences for scheduling

Output as JSON:
```json
{{
  "questions": [
    {{
      "question": "The business research tasks conflict with your shipping focus. Are these urgent this week?",
      "context": "9 business tasks scheduled but focus mode is Shipping"
    }}
  ]
}}
```

Output ONLY the JSON, no additional text."""


def build_refinement_prompt(
    original_plan: str,
    questions_and_answers: str,
) -> str:
    """Build prompt for refining plan based on Q&A answers.

    Args:
        original_plan: The original generated plan
        questions_and_answers: Questions with user's answers

    Returns:
        Formatted prompt string
    """
    return f"""Refine this weekly plan based on the user's answers.

## Original Plan
{original_plan}

## User Answers
{questions_and_answers}

## Instructions

Update the plan to reflect the user's preferences:
- Adjust suggestions based on their answers
- Update quick_actions if priorities changed
- Keep the same JSON structure

Output ONLY the updated JSON, no additional text."""
