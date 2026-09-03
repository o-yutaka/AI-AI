# Kaggle Remote Execution

The Kaggle Security Lab treats Kaggle Notebooks as an external compute surface, not as authority and not as durable BLACK state.

## Default rule

`reuse-only` is the default mode.

It never executes a Kaggle Notebook. The runner first checks the local fingerprint cache and, when no matching cache exists, downloads the latest remote Notebook output only.

A new Kaggle run happens only when the caller explicitly selects `cpu` or `gpu`.

## Flow

```text
editable local notebook
  -> workspace fingerprint
  -> matching local output cache? -> return output, zero Kaggle execution
  -> reuse-only? -> download latest remote output, zero Kaggle execution
  -> explicit cpu/gpu mode
  -> stage copy of notebook workspace
  -> inject security-lab-result.json fingerprint marker into staged copy only
  -> kaggle kernels push
  -> poll kaggle kernels status
  -> kaggle kernels output
  -> hash output directory
  -> cache matching fingerprint
```

The editable notebook is never modified by staging.

## Commands

Collect existing output without running the Notebook:

```bash
kaggle-security-lab kaggle-remote OWNER/NOTEBOOK \
  --workspace-dir ./kaggle/notebook \
  --output-dir ./artifacts/kaggle-output
```

Explicit CPU run:

```bash
kaggle-security-lab kaggle-remote OWNER/NOTEBOOK \
  --workspace-dir ./kaggle/notebook \
  --output-dir ./artifacts/kaggle-output \
  --mode cpu
```

Explicit GPU run:

```bash
kaggle-security-lab kaggle-remote OWNER/NOTEBOOK \
  --workspace-dir ./kaggle/notebook \
  --output-dir ./artifacts/kaggle-output \
  --mode gpu
```

CPU mode requires `enable_gpu=false` and `enable_tpu=false` in `kernel-metadata.json`. GPU mode requires `enable_gpu=true` and `enable_tpu=false`. This prevents accidental GPU quota use when the caller asked for CPU/reuse-only.

## Fingerprint contract

The job fingerprint is SHA-256 over the editable workspace files, excluding `.git`, `.kaggle-lab`, and `__pycache__`.

For explicit execution, the staged notebook receives a final marker cell that writes:

```json
{"job_fingerprint":"<sha256>"}
```

to `security-lab-result.json`. After output download the runner verifies the marker and only then promotes the output to the local fingerprint cache.

## BLACK boundary

The remote runner does not create BLACK Experience, Lesson, held-out truth, adoption authority, or execution authority.

The intended relationship is:

```text
BLACK external launcher
  -> Kaggle Security Lab CLI
  -> Kaggle Notebook
  -> downloaded output + SHA-256
  -> security-research-bundle / external artifact
  -> BLACK-side validation and Decision boundary
```

Authentication is supplied by the user's Kaggle CLI configuration or Kaggle-supported credentials. Credentials are never stored in research bundles or BLACK artifacts by this runner.
