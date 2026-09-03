from security_lab.runtime_matrix import RuntimeVariant
from security_lab.runtime_sensitivity import (
    RuntimeOutcome,
    analyze_runtime_sensitivity,
)
from security_lab.semantic_genome import (
    GeneSlot,
    SemanticGene,
    SemanticGenome,
    build_replacement_neighborhood,
    reorder_genes,
)
from security_lab.semantic_search import SemanticScore, beam_search_semantic_genomes


def _seed_genome() -> SemanticGenome:
    return SemanticGenome(
        (
            SemanticGene("instruction", GeneSlot.INSTRUCTION, "short"),
            SemanticGene("layout", GeneSlot.LAYOUT, "plain"),
        )
    )


def test_semantic_genome_tracks_clause_order_in_identity() -> None:
    seed = _seed_genome()
    reordered = reorder_genes(seed, ("layout", "instruction"))
    assert seed.render() == "short\nplain"
    assert reordered.render() == "plain\nshort"
    assert seed.fingerprint() != reordered.fingerprint()


def test_replacement_neighborhood_is_deterministic() -> None:
    seed = _seed_genome()
    left = build_replacement_neighborhood(
        seed,
        {"instruction": ["medium", "long"], "layout": ["compact"]},
    )
    right = build_replacement_neighborhood(
        seed,
        {"layout": ["compact"], "instruction": ["long", "medium"]},
    )
    assert [item.fingerprint() for item in left] == [
        item.fingerprint() for item in right
    ]


def test_semantic_beam_search_keeps_best_reproducible_candidate() -> None:
    seed = _seed_genome()

    def evaluator(genome: SemanticGenome) -> SemanticScore:
        score = float(len(genome.render()))
        return SemanticScore(score=score, passed=score >= 12)

    def mutator(genome: SemanticGenome):
        return build_replacement_neighborhood(
            genome,
            {"instruction": ["short", "substantially-longer"]},
        )

    result = beam_search_semantic_genomes(
        [seed],
        evaluator=evaluator,
        mutator=mutator,
        generations=2,
        beam_width=2,
        stop_on_pass=True,
    )
    assert result.best.score.passed is True
    assert "substantially-longer" in result.best.genome.render()
    assert result.evaluated_count == 2


def test_runtime_sensitivity_marks_version_shape_fragility() -> None:
    outcomes = [
        RuntimeOutcome(
            "candidate-a",
            RuntimeVariant("model", "runtime-v1", "compiler", "proxy"),
            1.0,
            True,
        ),
        RuntimeOutcome(
            "candidate-a",
            RuntimeVariant("model", "runtime-v2", "compiler", "target"),
            0.2,
            False,
        ),
    ]
    report = analyze_runtime_sensitivity(
        outcomes,
        minimum_success_rate=1.0,
        maximum_score_range=0.5,
    )
    assert report.runtime_count == 2
    assert report.success_rate == 0.5
    assert report.score_range == 0.8
    assert report.fragile is True
    assert report.failed_runtime_keys == (
        "model|runtime-v2|compiler|target",
    )
