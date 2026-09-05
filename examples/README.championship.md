# Championship example

Run:

```bash
kaggle-security-lab championship-run examples/championship-strategy.example.json
```

The example intentionally gives `public-flashy` the higher proxy score while assigning it poor private-survival evidence. `private-stable` has the lower proxy score but higher expected private objective value, so the championship selector chooses `private-stable`.

This demonstrates the V2 invariant: public/proxy rank is an observation channel, not the final objective.
