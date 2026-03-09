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

```bash
dil scan --type python .             # paths to __pycache__, .pyc, etc
dil scan --type python|node .        # python and node litter paths
dil report --type python .           # python litter stats
dil prune --force --type python .    # delete __pycache_, .pyc, etc
```
## Goal

To be able to run
```bash
dil
```
inside a project, provide a digest from a detected project type, and confirm to prune.

## Background

The purpose of **dil** is to provide a review and delete mechanism for disposable project artifacts. It is a Python port of my Bash-only tool, [**ilma**](https://github.com/brege/ilma), to create encrypted archives from the destination node *with the disposable matter excised from detected project branches*.

That made ilma far too broad in scope. The pruning and statistical features of ilma are useful to extract in their own right. 

### Upstream

Here's what's available in the world today.

1. [Kondo](https://github.com/tbillington/kondo) is the closest fit. It is useful, but its built-in project set is small and its rules live in Rust source. It is a good upstream for obvious artifact directories such as `node_modules`, `target`, `__pycache__`, and similar build or cache output.

2. [Tokei](https://github.com/XAMPPRocky/tokei) solves a different problem. Its [`languages.json`](https://github.com/XAMPPRocky/tokei/blob/master/languages.json) is a rich language database with extensions, filenames, env names, and shebangs. That makes it a better upstream for detector metadata than for prune rules.

3. [github/gitignore](https://github.com/github/gitignore) is broader than both, but it mixes true build artifacts with editor litter, machine-local files, and user-generated files that are often ignored but not safely disposable. For `dil`, ignored is not the same thing as removable.

### Approach

- Kondo is not broad enough for dil (LaTeX, React, etc are not in Kondo's `lib.rs`)
- Tokei is fantastic as a detector for filetypes and shebangs (`languages.json`)
- github/gitignore doesn't distinguish between disposable and user generated data.

Therefore, the approach is to map the overlap of Tokei's `languages.json` and Kondo's `lib.rs`, resolve the conflicts, map the keys, and supplement with a manually curated policy file: `dil.toml`.

## References

- Kondo · [github.com/tbillington/kondo](https://github.com/tbillington/kondo)
- Tokei · [github.com/XAMPPRocky/tokei](https://github.com/XAMPPRocky/tokei)
- github/gitignore · [github.com/github/gitignore](https://github.com/github/gitignore)

## License

[GPLv3](https://www.gnu.org/licenses/gpl-3.0.en.html)
