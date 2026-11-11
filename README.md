# Strands Box tool grammars

Tool grammars for [Strands Box](https://github.com/strands-agents/box), one directory per CLI.
This README is a stub.

## Layout

```
BOX_REVISION                         the Box commit every grammar is validated against
grammars/<cli>/<cli>.grammar.toml    the grammar: the body of [tool.<label>.grammar] in box.toml
grammars/<cli>/<cli>.corpus.toml     golden cases: argv, expected action, fields, effects
grammars/<cli>/<cli>.e2e.toml        optional cases that run in a real box
grammars/_example/                   a sample grammar for a fake program
scripts/                             the validation harness
```

## Validate

You need git, rustup (the Box checkout pins its own toolchain), and Python 3.11 or later.

```sh
./scripts/validate.sh            # Level 1, every grammar
./scripts/validate.sh gh         # Level 1, one grammar
./scripts/e2e.sh                 # Level 2, every grammar that has an e2e file
./scripts/e2e.sh gh              # Level 2, one grammar
./scripts/render.sh gh --command /opt/homebrew/bin/gh   # print the box.toml tables
```

Level 1 runs Box's own grammar tests (loader, parser, policy engine, and fuzz) over each grammar
and its corpus. Level 2 builds `strands-box`, starts a box with the grammar and a stub program, and
runs each e2e case through the box's Shell. Box runs on Linux ARM64 and on macOS on Apple silicon. Level 2 is proven on Linux ARM64 only.

The harness fetches Box at `BOX_REVISION` from GitHub into `.cache/`, and never changes a Box
source file. Settings, all optional:

| Variable | Default | Meaning |
|---|---|---|
| `BOX_SRC` | none | A local Box git clone that holds the commit. No fetch then. |
| `BOX_URL` | `https://github.com/strands-agents/box.git` | Where to fetch Box from. |
| `SBTG_CACHE` | `.cache/` | Where the Box copy and build output live. |
| `CARGO_TARGET_DIR` | `$SBTG_CACHE/target` | The cargo target directory. |
| `SBTG_PROFILE` | `release` | `release` or `debug`. |
| `SBTG_E2E_TMP` | `/var/tmp` | Where Level 2 makes its short-lived boxes. |
| `PYTHON` | `python3` | The Python 3.11+ interpreter. |
