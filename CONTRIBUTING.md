# Contributing

The highest-value contributions to **dil** are not Python refactors. They are better litter rules.

## Completeness

`dil` builds its rule set from:

- Kondo's Rust project artifact definitions
- Tokei's language detector metadata
- `dil.toml`, which resolves the mapping and carries local policy

That means the biggest gap is ecosystem familiarity. Python, Node, React, LaTeX, and the other currently covered types reflect the environments I actually use. If you work in another language, framework, or build tool, the most useful contribution is a rule refinement that proves:

- what is truly disposable
- what only looks disposable but is user-authored or environment-specific
- which detector should activate the type
- which detector is too weak and causes false positives

Good rule contributions should include a real project tree or a reduced dummy fixture that shows both sides: what should be removed and what must survive. See `test/fixtures.yml` for the fixtures used by `pytest`.

## Rule Work

`dil.toml` is policy.

- map Kondo project names and Tokei language keys into a `dil` type
- add or remove litter rules
- set canonical priorities where overlapping types exist
- require ancestor-bound matching for types like LaTeX

`dil/rules.toml` is generated output that merges `dil.toml` with extractions from Kondo and Tokei.

## Tests

The end-to-end harness lives under `test/`.

The most useful test contributions are new fixtures in `test/fixtures.yml`. Each fixture should describe:

- the project shape
- the expected matched paths
- the files that must remain
- the exact grouped rule totals

The harness builds those trees under `/tmp` and checks the real CLI against the filesystem and the `--json` output surface.

## Roadmap

The current policy file is repo-global: `dil.toml`.

A natural extension is a local `dil.toml` inside an arbitrary project tree, so a
repo can refine or narrow the generated defaults without forking `dil` itself.
That should stay small in scope:

- local type additions
- local rule drops
- local detector suppression

It should not become an executable config system or a second rules engine.
