from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum

from .reproducibility import stable_hash


class GeneSlot(StrEnum):
    INSTRUCTION = "INSTRUCTION"
    CLAUSE = "CLAUSE"
    PROTOCOL_EXAMPLE = "PROTOCOL_EXAMPLE"
    LAYOUT = "LAYOUT"
    TERMINATION = "TERMINATION"


@dataclass(frozen=True)
class SemanticGene:
    gene_id: str
    slot: GeneSlot
    text: str
    enabled: bool = True


@dataclass(frozen=True)
class SemanticGenome:
    genes: tuple[SemanticGene, ...]

    def __post_init__(self) -> None:
        gene_ids = [item.gene_id for item in self.genes]
        if len(set(gene_ids)) != len(gene_ids):
            raise ValueError("semantic genome gene IDs must be unique")

    def render(self, *, separator: str = "\n") -> str:
        return separator.join(item.text for item in self.genes if item.enabled)

    def fingerprint(self) -> str:
        return stable_hash(
            [
                {
                    "gene_id": item.gene_id,
                    "slot": item.slot.value,
                    "text": item.text,
                    "enabled": item.enabled,
                }
                for item in self.genes
            ]
        )


def replace_gene_text(
    genome: SemanticGenome,
    gene_id: str,
    text: str,
) -> SemanticGenome:
    found = False
    genes: list[SemanticGene] = []
    for gene in genome.genes:
        if gene.gene_id == gene_id:
            genes.append(replace(gene, text=text))
            found = True
        else:
            genes.append(gene)
    if not found:
        raise KeyError(gene_id)
    return SemanticGenome(tuple(genes))


def toggle_gene(
    genome: SemanticGenome,
    gene_id: str,
    *,
    enabled: bool | None = None,
) -> SemanticGenome:
    found = False
    genes: list[SemanticGene] = []
    for gene in genome.genes:
        if gene.gene_id == gene_id:
            genes.append(
                replace(
                    gene,
                    enabled=not gene.enabled if enabled is None else enabled,
                )
            )
            found = True
        else:
            genes.append(gene)
    if not found:
        raise KeyError(gene_id)
    return SemanticGenome(tuple(genes))


def reorder_genes(
    genome: SemanticGenome,
    ordered_gene_ids: Sequence[str],
) -> SemanticGenome:
    expected = {item.gene_id for item in genome.genes}
    actual = set(ordered_gene_ids)
    if expected != actual or len(ordered_gene_ids) != len(genome.genes):
        raise ValueError("ordered_gene_ids must contain every gene exactly once")
    by_id = {item.gene_id: item for item in genome.genes}
    return SemanticGenome(tuple(by_id[item] for item in ordered_gene_ids))


def build_replacement_neighborhood(
    genome: SemanticGenome,
    replacements: Mapping[str, Sequence[str]],
) -> tuple[SemanticGenome, ...]:
    known = {item.gene_id for item in genome.genes}
    unknown = sorted(set(replacements) - known)
    if unknown:
        raise KeyError("unknown replacement gene IDs: " + ",".join(unknown))

    candidates: dict[str, SemanticGenome] = {}
    for gene_id in sorted(replacements):
        current = next(item for item in genome.genes if item.gene_id == gene_id)
        for text in sorted(set(replacements[gene_id])):
            if text == current.text:
                continue
            candidate = replace_gene_text(genome, gene_id, text)
            candidates[candidate.fingerprint()] = candidate
    return tuple(candidates[key] for key in sorted(candidates))
