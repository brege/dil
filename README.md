# dil

Detect and prune disposable project artifacts.

## Installation

Install as a Python tool:

```bash
git clone https://github.com/brege/dil
cd dil
uv tool install .
```

## Usage

Compact grouped litter summary.
```bash
dil
```

### Examples

#### Litter Stats

Example output from a project[^1] that has a Flask server, a React UI, and uses Node packages:

```bash
cd ~/src/aoife
dil
```

You can equivalently do  `dil --type python|node|react ~/src/aoife`.

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

#### Project Litter Paths

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

#### Delete / Prune

Use `-n` for a dry run, `-d` to prompt before deleting, and `-d -y` to skip the prompt.

```bash
dil -d ~/src/aoife
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

The purpose of **dil** is to provide a review and delete mechanism for disposable project artifacts. It is a Python port of my Bash-only tool, [**ilma**](https://github.com/brege/ilma), to create encrypted archives from the destination node *with the disposable matter excised from detected project branches*.

That made ilma far too broad in scope. The pruning and review features of ilma are useful to extract in their own right.

### Upstream

Here's what's available in the world today.

1. [Kondo](https://github.com/tbillington/kondo) is the closest fit. It is useful, but its built-in project set is small and its rules live in Rust source. It is a good upstream for obvious artifact directories such as `node_modules`, `target`, `__pycache__`, and similar build or cache output.

2. [Tokei](https://github.com/XAMPPRocky/tokei) solves a different problem. Its [`languages.json`](https://github.com/XAMPPRocky/tokei/blob/master/languages.json) is a rich language database with extensions, filenames, env names, and shebangs. That makes it a better upstream for detector metadata than for prune rules.

3. [github/gitignore](https://github.com/github/gitignore) is broader than both, but it mixes true build artifacts with editor litter, machine-local files, and user-generated files that are often ignored but not safely disposable. For **dil**, ignored is not the same thing as removable.

### Approach

- Kondo is not broad enough for **dil**. LaTeX, React, etc are not in Kondo's `lib.rs`.
- Tokei's `languages.json` is fantastic as a detector for file types and shebangs
- github/gitignore doesn't distinguish between disposable and user generated data.

Therefore, the approach is to map the overlap of Tokei's `languages.json` and Kondo's `lib.rs`, resolve the conflicts, map the keys, and supplement with a manually curated policy file: `dil.toml`.

## References

- Kondo · [github.com/tbillington/kondo](https://github.com/tbillington/kondo)
- Tokei · [github.com/XAMPPRocky/tokei](https://github.com/XAMPPRocky/tokei)
- github/gitignore · [github.com/github/gitignore](https://github.com/github/gitignore)

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) if you want to help refine litter
rules, detector mappings, or fixture coverage.


## License

[GPLv3](https://www.gnu.org/licenses/gpl-3.0.en.html)
