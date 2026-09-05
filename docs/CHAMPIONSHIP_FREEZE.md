# Championship freeze and rehearsal gate

The championship stack now has a final reproducibility boundary after candidate selection.

```text
research -> hard gates -> private objective -> replay-wall risk -> final candidate set
  -> championship-freeze
  -> rehearsal
  -> exact-match only
  -> Kaggle run / explicit submit
```

`championship-freeze` binds the final competition slug, exact source commit, sorted candidate identities, and SHA-256 identities of the runtime contract, candidate pack, championship-risk spec, and any other caller-owned final artifacts.

`championship-rehearsal` rebuilds the same canonical identity from the observed rehearsal input. Any source-commit, candidate-set, artifact, or canonical identity drift rejects the rehearsal. This is intentionally strict: a high-scoring plan that cannot be replayed exactly is not treated as final-ready.

```bash
kaggle-security-lab championship-freeze examples/championship-freeze.example.json
kaggle-security-lab championship-rehearsal \
  examples/championship-freeze.example.json \
  examples/championship-freeze.example.json
```

The gate is competition plumbing only. It generates no attack payloads and carries no BLACK authority.
