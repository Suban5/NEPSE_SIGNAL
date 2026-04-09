"""Workflow failure classification primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class WorkflowFailureDetails:
    """Structured metadata describing a workflow failure."""

    workflow: str
    stage: str
    category: str
    retriable: bool
    status_code: int
    message: str
    cause_type: str


class WorkflowError(RuntimeError):
    """Base exception for classified workflow failures."""

    def __init__(
        self,
        workflow: str,
        stage: str,
        category: str,
        message: str,
        *,
        status_code: int = 500,
        retriable: bool = False,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.workflow = workflow
        self.stage = stage
        self.category = category
        self.status_code = status_code
        self.retriable = retriable
        self.details = dict(details or {})

    @property
    def error_id(self) -> str:
        """Return a stable error identifier placeholder for API mapping."""
        return self.details.get("error_id", "")

    def as_details(self) -> WorkflowFailureDetails:
        """Return structured failure metadata for logging and HTTP mapping."""
        return WorkflowFailureDetails(
            workflow=self.workflow,
            stage=self.stage,
            category=self.category,
            retriable=self.retriable,
            status_code=self.status_code,
            message=str(self),
            cause_type=self.__class__.__name__,
        )


class WorkflowValidationError(WorkflowError):
    """Raised when workflow inputs or validated payloads are invalid."""

    def __init__(self, workflow: str, stage: str, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(workflow, stage, "validation", message, status_code=400, retriable=False, details=details)


class WorkflowDataError(WorkflowError):
    """Raised when a workflow cannot continue because required data is missing."""

    def __init__(self, workflow: str, stage: str, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(workflow, stage, "data", message, status_code=422, retriable=False, details=details)


class WorkflowUpstreamError(WorkflowError):
    """Raised when an upstream fetch or transformation step fails."""

    def __init__(self, workflow: str, stage: str, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(workflow, stage, "upstream", message, status_code=502, retriable=True, details=details)


class WorkflowRankingError(WorkflowError):
    """Raised when ranking or scoring output cannot be produced."""

    def __init__(self, workflow: str, stage: str, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(workflow, stage, "ranking", message, status_code=500, retriable=False, details=details)


def classify_workflow_exception(workflow: str, stage: str, exc: Exception) -> WorkflowError:
    """Map a raw exception to a classified workflow error."""
    if isinstance(exc, WorkflowError):
        return exc

    message = str(exc) or exc.__class__.__name__
    if isinstance(exc, (ValueError, TypeError)):
        return WorkflowValidationError(workflow, stage, message)

    if isinstance(exc, RuntimeError) and "No " in message:
        return WorkflowDataError(workflow, stage, message)

    if stage in {"score", "signal", "rank", "backtest", "persist"}:
        return WorkflowRankingError(workflow, stage, message)

    return WorkflowUpstreamError(workflow, stage, message)
