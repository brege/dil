# Contributing

The most impactful contributions to **dil** are better litter rules.

If you work in another language, framework, or build tool, the best contribution is usually a `dil.toml` refinement for that ecosystem plus a reduced fixture that proves the rule boundary.

## TLDR

- look at [`dil/rules.toml`](../dil/rules.toml) and find a missing ecosystem
- define the disposable boundary for that ecosystem in `dil.toml`
- prove it with a reduced fixture
- keep user-authored or environment-specific data out of the prune set

## Rules Generator

For the generator pipeline, policy hierarchy, schema tables, and local `dil.toml` examples, see [Generator and Policy](../gen/README.md).

Run the generator pipeline with `uv run python gen/rules.py`.

## Testing

For fixture structure, harness behavior, and local config tests, see [Tests](../test/README.md).

Run the full test suite with `uv run pytest`.
