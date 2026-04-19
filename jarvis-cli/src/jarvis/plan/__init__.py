"""Weekly planning module for Jarvis.

This module provides the `jarvis plan` command for proactive weekly planning
with gap analysis between context files and scheduled tasks.
"""

from .cli import plan_command, plan_alias
from .service import PlanService, get_plan_service

__all__ = [
    "plan_command",
    "plan_alias",
    "PlanService",
    "get_plan_service",
]
