# dil

Detect and prune disposable project artifacts like `node_modules`, `__pycache__`, LaTeX's build junk, and many others. See [Background](#background) for why **dil** exists and its origin story.

## Installation

Install as a Python tool

```bash
git clone https://github.com/brege/dil
cd dil
uv tool install .
```

## Usage

Auto-detect project types and list litter candidates to remove
```bash
dil
```

### Examples

#### Overview

Example output from a project[^1] that has a Flask server, a React UI, and uses Node packages:

```bash
cd ~/src/aoife
dil
```

You can equivalently do  `dil --type "python|node|react" ~/src/aoife`.

```
 Type     Rule           Matches       Size
 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 node     node_modules         1   391.9 MB
 ──────────────────────────────────────────
 python   .ruff_cache          1      376 B
          .uv-cache            1      944 B
          __pycache__          1    21.3 KB
 ──────────────────────────────────────────
 react    dist                 1   681.9 KB
 ──────────────────────────────────────────
 Total                         5   392.6 MB
 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
[^1]: This example is of [aoife](https://github.com/brege/aoife).

#### Litter Paths

Use `-p` to show paths, `-P` to show absolute paths

```bash
dil -p ~/src/aoife
```

```
 Type     Rule           Path
 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 node     node_modules   node_modules/
 ────────────────────────────────────────────
 python   .ruff_cache    .ruff_cache/
          .uv-cache      .uv-cache/
          __pycache__    backend/__pycache__/
 ────────────────────────────────────────────
 react    dist           dist/
 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

#### Deletion

Use
`-d` to delete (prune junk) with prompt,
`-d -n` for a dry run,
`-P` to preview with absolute paths, and
`-y` to skip the prompt.

```bash
dil -d -P ~/src/aoife
```

```
 Type     Rule           Path
 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 node     node_modules   /home/user/src/aoife/node_modules/
 ───────────────────────────────────────────────────────────────────────────────
 python   .ruff_cache    /home/user/src/aoife/.ruff_cache/
          .uv-cache      /home/user/src/aoife/.uv-cache/
          __pycache__    /home/user/src/aoife/backend/__pycache__/
 ───────────────────────────────────────────────────────────────────────────────
 react    dist           /home/user/src/aoife/dist/
 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Delete matched items? [y/N] y
Deleted 5 item(s)
```

## Background

**dil** exists to prune disposable project artifacts. It was extracted from [ilma](https://github.com/brege/ilma), where project-type excision had grown inside a larger backup orchestration system.

[**ilma**](https://github.com/brege/ilma) is/was an over-engineered Bash-only backup and archival system for syncing remote data to a local machine. Why? Most mirroring and backup tools assume the backup target is the remote side. **ilma** also turned into a context-management tool during the early days of LLM-assisted coding, when large file trees caused massive token churn. To trim that context, it created mirrors of projects with `node_modules`, `.git`, and `__pycache__` excised for debugging and scaffolding.

That filtration system eclipsed ilma's original purpose: backing up hard-to-reproduce remote crap to my laptop. The Bash code sprawled until it was no longer maintainable.

You could call **dil** a port of ilma's scan-and-prune behavior, but not of its architecture. The action is the same; the implementation is not. As a standalone tool, dil benefits from [rich](https://rich.readthedocs.io/en/latest/) output, fast file discovery, TOML configuration, and the usual quality-of-life gains that come from not being buried inside a larger Bash system. It also does not replace ilma's `ilma console`; for that kind of project summary, `tokei` is the cromulent choice.

### Upstream Projects

#### Overview

Here's what's available in the world today.

- Kondo · [github.com/tbillington/kondo](https://github.com/tbillington/kondo)
- Tokei · [github.com/XAMPPRocky/tokei](https://github.com/XAMPPRocky/tokei)
- github/gitignore · [github.com/github/gitignore](https://github.com/github/gitignore)

#### Review

1. [Kondo](https://github.com/tbillington/kondo) is the closest fit. While useful, its built-in project set is small and its rules live in Rust source. It is a good upstream for obvious artifact directories such as `node_modules`, `target`, `__pycache__`, and similar build or cache output.

2. [Tokei](https://github.com/XAMPPRocky/tokei) solves a different problem. Its [`languages.json`](https://github.com/XAMPPRocky/tokei/blob/master/languages.json) is a rich language database with extensions, filenames, env names, and shebangs. That makes it a better upstream for detector metadata than for prune rules.

3. [github/gitignore](https://github.com/github/gitignore) is broader than both, but it mixes true build artifacts with editor litter, machine-local files, and user-generated files that are often ignored but not safely disposable. For **dil**, ignored is not the same thing as forgettable.

#### Limitations

- Kondo is not broad enough for **dil**. LaTeX, React, etc are not in Kondo's `lib.rs`
- Tokei's `languages.json` is fantastic as a detector for file types and shebangs
- github/gitignore doesn't distinguish between disposable and user generated data

#### Implementation

The approach is to **map** the overlap between Tokei's `languages.json` and Kondo's `lib.rs`, resolve conflicts, normalize the keys, and supplement the result with a manually curated policy file: `dil.toml`.

This provides a global `dil.toml` file that can be overridden or augmented for a specific project's needs.

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) if you want to help refine litter rules, detector mappings, or fixture coverage.


## License

[GPLv3](https://www.gnu.org/licenses/gpl-3.0.en.html)
