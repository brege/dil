# Contributing

The most useful contributions to **dil** are better litter rules.

## Completeness

**dil** builds its rule set from three sources:

1. [Kondo](https://github.com/tbillington/kondo)'s Rust project artifact definitions -- [kondo: kondo-lib/src/lib.rs](https://github.com/tbillington/kondo/blob/master/kondo-lib/src/lib.rs)
2. [Tokei](https://github.com/XAMPPRocky/tokei)'s language detector metadata -- [tokei: languages.json](https://github.com/XAMPPRocky/tokei/blob/master/languages.json)
3. [dil's `dil.toml`](./dil.toml), which resolves the mapping of the above and extends local policy -- [dil:dil.toml](./dil.toml)

That means the biggest gap is ecosystem familiarity. Python, Node, React, LaTeX, and the other currently covered types reflect the environments I can comfortably work in. If you work in another language, framework, or build tool, the most useful contribution is a rule refinement that proves:

- what is truly disposable
- what only looks disposable but is user-authored or environment-specific
- which sentinel should activate the type
- which detector is too weak and causes false positives

Good rule contributions should include a reduced dummy fixture mocked from a real project tree that shows both sides: what should be removed and what must survive.


## Tests

The most useful test contributions are new fixtures in `test/fixtures.yml`. To run tests on these fixtures:

```bash
uv run pytest
```

The test pipeline is:

1. read fixtures from `test/fixtures.yml`
2. build the project tree dummies under `/tmp` via `test/setup.py`
3. match output vs. expected via `test/harness.py`

Each fixture should describe the artifact shape of the framework or language being added to `fixtures.yml`.

- the project shape
- the expected matched paths
- the files that must remain
- the exact grouped rule totals

The harness builds those trees under `/tmp` and checks the real CLI against the filesystem and the `--json` output surface.

## Roadmap

The current policy file is repo-global: `dil.toml`.

A natural extension is a local `dil.toml` inside an arbitrary project tree, so a repo can refine or narrow the generated defaults without forking **dil** itself. That should stay small in scope:

- local type additions
- local rule drops
- local detector suppression

It should not become an executable config system or a second rules engine.
