# dil.toml Generator And Policy

This directory owns the path from upstream sources to generated runtime rules.

The moving parts are:

- `gen/kondo.py` for upstream Kondo artifact rules
- `gen/tokei.py` for upstream Tokei detector metadata
- `gen/policy.py` for `dil.toml`
- `gen/rules.py` for rendering `dil/rules.toml`

## Hierarchy

**dil** has three layers of rule definition:

1. upstream sources such as Kondo and Tokei
2. repo policy in [`dil.toml`](../dil.toml)
3. generated runtime rules in [`dil/rules.toml`](../dil/rules.toml)

At runtime, those generated rules can then be overridden by:

1. `~/.config/dil/config.toml`
2. project-local `dil.toml`

## Diagram

![policy diagram](diagram.svg)

## Repo Policy Example

For example, [Go](https://github.com/golang/go) is still missing from the generated rule set. A Go service could ship a local `dil.toml` like this:

```toml
[type.go]
priority = 0

[type.go.add]
patterns = [
  "bin/",
  "coverage.out",
  "data/cache/**",
  "data/tmp/**",
]
detect_suffix = [".go"]
```

That does three useful things:

- activates the type when Go source is present
- declares obvious build litter like `bin/` and `coverage.out`
- keeps `data/` itself protected while only targeting the known waste inside it

## Key Semantics

`type.go.add` is easy to misread. It does not mean "start pruning Go." It means "augment the Go type definition with more rules or detector signals."

The most useful way to read the schema is:

- `type.<name>` defines or patches a type
- `.add` extends that type
- `.rm` removes inherited members from that type
- detector fields only affect activation, not prune targets directly

## Type Table

| Key | Where | Meaning |
| --- | --- | --- |
| `type.<name>` | repo policy, local `dil.toml` | declares or patches one project type |
| `priority` | repo policy, local `dil.toml` | tie-break rank when multiple types detect on the same tree; lower wins |
| `require-ancestor` | repo policy, local `dil.toml` | only allow matches when an ancestor contains the detecting suffixes for that type |
| `kondo` | repo policy only | names of upstream Kondo rule groups to import |
| `tokei` | repo policy only | names of upstream Tokei language detectors to import |

## Nested Rule Tables

| Key | Where | Meaning |
| --- | --- | --- |
| `type.<name>.add` | repo policy, local `dil.toml` | add litter rules and detector signals to this type |
| `type.<name>.rm` | repo policy, local `dil.toml` | remove inherited litter rules and detector signals from this type |

## Fields Inside `.add` And `.rm`

| Key | Meaning |
| --- | --- |
| `patterns` | gitignore-like prune patterns; `bin/` is dir-only, `*.pyc` is basename-based, and `data/cache/**` is path-based |
| `detect_files` | exact filenames that help activate the type |
| `detect_suffix` | file suffixes that help activate the type |
| `detect_names` | case-insensitive filenames that help activate the type |
| `detect_env` | shebang env names that help activate the type |
| `detect_shebang` | exact shebang lines that help activate the type |

## Override Order

When **dil** loads runtime config, the order is:

1. built-in generated rules
2. `~/.config/dil/config.toml`
3. project-local `dil.toml`

That lets a project narrow or extend the global defaults for its own tree before **dil** lists or deletes matches.
