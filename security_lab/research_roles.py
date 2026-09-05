from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol


class ResearchRole(StrEnum):
    RED = "RED"
    TRACE = "TRACE"
    BLUE = "BLUE"
    META = "META"
    JUDGE = "JUDGE"


@dataclass(frozen=True)
class ResearchContext:
    subject_ref: str
    payload: Mapping[str, Any]
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResearchArtifact:
    artifact_id: str
    role: ResearchRole
    kind: str
    subject_ref: str
    statement: str
    evidence_refs: tuple[str, ...] = ()
    authority: str = "NONE"


class ResearchRolePort(Protocol):
    role: ResearchRole

    def run(self, context: ResearchContext) -> Sequence[ResearchArtifact]: ...


@dataclass(frozen=True)
class ResearchOrchestrationResult:
    artifacts: tuple[ResearchArtifact, ...]
    roles_completed: tuple[ResearchRole, ...]


def orchestrate_research_roles(
    context: ResearchContext,
    ports: Sequence[ResearchRolePort],
    *,
    order: Sequence[ResearchRole] = (
        ResearchRole.RED,
        ResearchRole.TRACE,
        ResearchRole.BLUE,
        ResearchRole.META,
        ResearchRole.JUDGE,
    ),
) -> ResearchOrchestrationResult:
    by_role: dict[ResearchRole, ResearchRolePort] = {}
    for port in ports:
        if port.role in by_role:
            raise ValueError(f"duplicate research role port: {port.role}")
        by_role[port.role] = port

    artifacts: list[ResearchArtifact] = []
    completed: list[ResearchRole] = []
    artifact_ids: set[str] = set()
    for role in order:
        port = by_role.get(role)
        if port is None:
            continue
        produced = tuple(port.run(context))
        for artifact in produced:
            if artifact.role is not role:
                raise ValueError(
                    f"research role {role} emitted artifact for {artifact.role}"
                )
            if artifact.authority != "NONE":
                raise ValueError("research artifacts cannot carry authority")
            if artifact.artifact_id in artifact_ids:
                raise ValueError(f"duplicate research artifact id: {artifact.artifact_id}")
            artifact_ids.add(artifact.artifact_id)
            artifacts.append(artifact)
        completed.append(role)

    return ResearchOrchestrationResult(
        artifacts=tuple(artifacts),
        roles_completed=tuple(completed),
    )
