from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from .semantic_genome import SemanticGenome


@dataclass(frozen=True)
class SemanticScore:
    score: float
    passed: bool = False


@dataclass(frozen=True)
class SemanticSearchCandidate:
    genome: SemanticGenome
    score: SemanticScore
    generation: int
    parent_fingerprint: str | None

    @property
    def fingerprint(self) -> str:
        return self.genome.fingerprint()


@dataclass(frozen=True)
class SemanticSearchResult:
    best: SemanticSearchCandidate
    frontier: tuple[SemanticSearchCandidate, ...]
    evaluated_count: int
    generations_completed: int


SemanticEvaluator = Callable[[SemanticGenome], SemanticScore]
SemanticMutator = Callable[[SemanticGenome], Iterable[SemanticGenome]]


def beam_search_semantic_genomes(
    seeds: Iterable[SemanticGenome],
    *,
    evaluator: SemanticEvaluator,
    mutator: SemanticMutator,
    generations: int,
    beam_width: int,
    stop_on_pass: bool = False,
) -> SemanticSearchResult:
    if generations < 0:
        raise ValueError("generations must be non-negative")
    if beam_width < 1:
        raise ValueError("beam_width must be positive")

    seed_map = {item.fingerprint(): item for item in seeds}
    if not seed_map:
        raise ValueError("semantic search requires at least one seed")

    evaluated: dict[str, SemanticSearchCandidate] = {}
    frontier: list[SemanticSearchCandidate] = []
    for fingerprint in sorted(seed_map):
        genome = seed_map[fingerprint]
        candidate = SemanticSearchCandidate(
            genome=genome,
            score=evaluator(genome),
            generation=0,
            parent_fingerprint=None,
        )
        evaluated[fingerprint] = candidate
        frontier.append(candidate)

    frontier = _rank(frontier)[:beam_width]
    best = frontier[0]
    if stop_on_pass and best.score.passed:
        return SemanticSearchResult(best, tuple(frontier), len(evaluated), 0)

    generations_completed = 0
    for generation in range(1, generations + 1):
        proposed: dict[str, tuple[SemanticGenome, str]] = {}
        for parent in frontier:
            for genome in mutator(parent.genome):
                fingerprint = genome.fingerprint()
                if fingerprint in evaluated or fingerprint in proposed:
                    continue
                proposed[fingerprint] = (genome, parent.fingerprint)

        if not proposed:
            break

        generation_candidates: list[SemanticSearchCandidate] = []
        for fingerprint in sorted(proposed):
            genome, parent_fingerprint = proposed[fingerprint]
            candidate = SemanticSearchCandidate(
                genome=genome,
                score=evaluator(genome),
                generation=generation,
                parent_fingerprint=parent_fingerprint,
            )
            evaluated[fingerprint] = candidate
            generation_candidates.append(candidate)

        frontier = _rank([*frontier, *generation_candidates])[:beam_width]
        best = frontier[0]
        generations_completed = generation
        if stop_on_pass and best.score.passed:
            break

    return SemanticSearchResult(
        best=best,
        frontier=tuple(frontier),
        evaluated_count=len(evaluated),
        generations_completed=generations_completed,
    )


def _rank(candidates: list[SemanticSearchCandidate]) -> list[SemanticSearchCandidate]:
    return sorted(
        candidates,
        key=lambda item: (
            not item.score.passed,
            -item.score.score,
            item.fingerprint,
        ),
    )
