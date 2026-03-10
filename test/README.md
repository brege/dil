# Tests

The test suite is fixture-driven. Most behavior changes in **dil** should be expressed first as a project tree in `test/fixtures.yml`, then validated through the real CLI in `test/harness.py`.

## Running Tests

Run the full suite:

```bash
uv run pytest
```

Run one test:

```bash
uv run pytest test/harness.py -k short_dry
```

## Test Layout

- `test/fixtures.yml` defines project trees and expectations
- `test/setup.py` builds those trees under `/tmp`
- `test/harness.py` runs the real CLI and checks output, filesystem state, and config behavior

The general pipeline is:

1. read a fixture from `test/fixtures.yml`
2. build a dummy project tree under `/tmp`
3. run `dil` against that tree
4. compare the result with expected matches, totals, and surviving files

## Fixture Shape

Each fixture should model both sides of the decision:

- the project shape
- the paths that should be matched
- the files that must remain
- the grouped rule totals

Keep fixtures reduced. They should prove one rule family or one detection edge without dragging in unrelated project noise.

## What The Harness Checks

`test/harness.py` covers the public CLI surface, not just internal functions. That includes:

- grouped summary output through `--json`
- relative and absolute path output
- dry-run and delete behavior
- prompt and short-output behavior
- empty-result messaging
- local `dil.toml` loading, additive overrides, rule removal, and detector suppression

The harness also pins `HOME` to a test directory so user-level config does not leak into the suite.

## Local Config Tests

Runtime config discovery looks for:

- `~/.config/dil/config.toml`
- `dil.toml` at the project root

When testing local overrides, prefer putting a small `dil.toml` into the fixture tree and asserting the resulting CLI behavior, not just the loaded config object.

Use the same policy shape that the repo-level `dil.toml` uses:

- `[type.<name>.add]` for local additions
- `[type.<name>.rm]` for local removals and detector suppression

That keeps runtime config and repo policy aligned instead of creating two parallel configuration styles.
