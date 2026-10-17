"""Coding task state and result."""

from dataclasses import dataclass
from enum import Enum


class TaskPhase(Enum):
    CREATED = "created"
    INSPECTING = "inspecting"
    PLANNING = "planning"
    EDITING = "editing"
    TESTING = "testing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(slots=True)
class Task:
    description: str
    phase: TaskPhase = TaskPhase.CREATED
    plan: str = ""
    result: str = ""
    checks_passed: bool = False

