# Kaggle AI Agent Security Lab

Canonical repository slug: **`kaggle-ai-agent-security-lab`**  
Primary competition: **Kaggle — AI Agent Security - Multi-Step Tool Attacks**

This repository is an independent research and evaluation lab for multi-step AI-agent tool security. It preserves the existing deterministic AI-agent control plane as the experiment runtime and adds a BLACK-independent canonical research export boundary.

> Current GitHub slug is still `o-yutaka/AI-AI` until the repository setting is renamed. The project identity and internal architecture are now `Kaggle AI Agent Security Lab`.

## Permanent boundary

```text
KAGGLE LAB != BLACK
Research Finding != BLACK Lesson
Research Bundle != BLACK Experience
External Observation != Independent Verification
Benchmark Result != Adoption Authority
Benchmark Result != Execution Authority
```

The lab can produce hypotheses, probes, observations, trajectories, findings, failure findings, robustness measurements, benchmark results, provenance, and artifact hashes. It does not decide BLACK promotion, adoption, held-out truth, routing, or execution authority.

## Architecture

```text
Competition / local benchmark inputs
              |
       Hypothesis Engine
              |
         Probe Compiler
              |
      Candidate Generator
              |
              v
  +--------------------------+
  | existing control_plane/  |
  | contract / permission    |
  | evidence / privacy gates |
  | deterministic ranking    |
  | approval gate            |
  | fixed tool registry      |
  | fingerprint/idempotency  |
  +--------------------------+
              |
         Trace / Replay
              |
   Failure + Transfer Analysis
              |
     Robustness Evaluation
              |
       research_bundle/
 security-research-bundle.v1
              |
     canonical JSON + SHA-256
              |
        external consumer
```

Canonical architecture: [`docs/KAGGLE_SECURITY_LAB_ARCHITECTURE.md`](docs/KAGGLE_SECURITY_LAB_ARCHITECTURE.md)

## Existing control-plane runtime

The existing implementation remains useful and is not discarded. It already provides:

- untrusted candidate handling
- contract, permission, evidence, sensitive-data, and tool-capability gates
- deterministic candidate ranking
- named approval/rejection before high-impact execution
- stable fingerprints and idempotent replay
- fixed host/method/path/operation HTTP tool surfaces
- environment-only sensitive headers
- redirects disabled and bounded streaming responses
- SQLite-backed durable run, approval, fingerprint, and idempotency state
- FastAPI API and Next.js operations dashboard

Two runtime boundaries remain non-negotiable:

1. Provider output is untrusted input and must pass runtime gates before execution.
2. The model cannot choose an arbitrary host, HTTP method, path, redirect target, or credential.

## Canonical research export

`research_bundle/` defines the external knowledge contract.

```python
from datetime import UTC, datetime

from research_bundle import CompetitionIdentity, SecurityResearchBundle, export_bundle

bundle = SecurityResearchBundle(
    competition=CompetitionIdentity(
        competition_slug="ai-agent-security-multi-step-tool-attacks",
        competition_name="AI Agent Security - Multi-Step Tool Attacks",
    ),
    generated_at=datetime.now(UTC),
)

path, sha256 = export_bundle(bundle, "exports/security-research-bundle.json")
```

The canonical exported vocabulary is:

- `Hypothesis`
- `Probe`
- `Observation`
- `Trajectory`
- `Finding`
- `FailureFinding`
- `RobustnessResult`
- `BenchmarkResult`
- `ProvenanceRecord`
- `SecurityResearchBundle`

BLACK-specific `Experience`, `Lesson`, held-out verification, adoption, promotion, and execution authority are intentionally not minted here.

## Intended BLACK compatibility flow

```text
Kaggle AI Agent Security Lab
  -> security-research-bundle.v1
  -> BLACK-side external adapter
  -> validated external artifact/evidence
  -> authoritative Mission binding
  -> BLACK creates its own Experience
  -> independent held-out evaluation
  -> Decision-gated adoption
```

BLACK remains fully optional. This repository has no BLACK package dependency and should remain independently runnable.

## Research discipline

Use explicit data/evaluation splits:

```text
TRAIN
DEV
HELD_OUT
ADVERSARIAL_HELD_OUT
```

Public leaderboard behavior is an observation channel, not hidden-evaluator ground truth. Prefer falsifiable probes, shortest reproducible winning traces, failure-family separation, transfer measurement, and robustness evaluation before optimization.

## Run the stack

```bash
docker compose up --build
```

Local Python development:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock.txt
pip install --no-deps -e .
ruff check .
pytest -q
uvicorn app:app --reload
```

PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.lock.txt
pip install --no-deps -e .
ruff check .
pytest -q
uvicorn app:app --reload
```

Frontend:

```bash
cd web
npm ci
npm run dev
```

## API

```text
GET  /health
GET  /v1/provider
POST /v1/agent-runs
POST /v1/runs
GET  /v1/runs
GET  /v1/runs/{run_id}
POST /v1/runs/{run_id}/decision
```

## Verification

CI continues to cover Python lint/tests, contract/permission/evidence blocking, approval/rejection, idempotency/replay, provider privacy, tool response limits, SQLite durability, frontend build, container build, and browser proof. The new research bundle tests additionally lock canonical deterministic hashing and BLACK vocabulary separation.

## License

MIT — see [`LICENSE`](LICENSE).
