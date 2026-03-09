# dil

Remove disposable project artifacts.

Examples include 

- Python artifacts like `__pycache__`, `*.pyc`, etc.
- Node modules like `node_modules`, etc.
- Latex files like `*.{toc,aux,log}`

And many more. See .... TODO

## Features

More to hopefully come. See 

- [tokei's supported types](https://github.com/XAMPPRocky/tokei?tab=readme-ov-file#supported-languages) and its [languages.json](https://github.com/XAMPPRocky/tokei/blob/master/languages.json)
- [kondo's Rust manifest](https://github.com/tbillington/kondo/blob/master/kondo-lib/src/lib.rs)

## Usage

List the artifacts of a Python project:

```bash
dil scan --type python .
```

or of two project types:

```bash
dil scan --type python|node .
```

Get statistics about a Python project's litter:

```bash
dil report --type python .
```

Prune a Python project's litter:

```bash
dil prune --force --type python .
```

## Timeline

This project is a port of [ilma](https://github.com/brege/ilma)'s project pruner which was written in Bash.

## Licence

[GPLv3](https://www.gnu.org/licenses/gpl-3.0.en.html)
