# Contributing a grammar

A new grammar, or a change to one, needs these files under `grammars/<cli>/`, with the file stem
equal to the directory name:

- `<cli>.grammar.toml`: the grammar. Start from [`grammars/_example`](grammars/_example/).
- `<cli>.corpus.toml`: golden cases. Cover each action, each effect being added and removed, each
  value spelling the CLI accepts (`--x=v`, `--x v`, clusters), and at least one `unmodeled` line per
  command family.
- `<cli>.e2e.toml`: a policy and cases that run in a real box with a stub program.
- `README.md`: the project, the executable, the version you checked, how to install and load it,
  the effects, example rules, and the known limits. Follow the shape of the other grammar READMEs.

Rules the grammars here follow:

1. **Model only what you would allow.** Leave out an option when you cannot say what it does. An
   undeclared option makes the line `unmodeled`, which the default-deny refuses.
2. **No catch-alls.** No `rest` operand, `value = "many"`, or `like = "*"` only to make lines match.
3. **Check the source, not only the help.** Read the CLI's argument parser and the code of each
   modeled command at the version you pin. Pin that version at the top of the grammar.
4. **Use `removes` only for a flag that really cancels an effect**, such as `--dry-run`, and check in
   the source that it does.
5. **State what the grammar cannot see** at the top of the grammar and in the README: environment
   variables, config files, aliases on disk, and programs the CLI starts.
6. **When the CLI can read a line differently from the grammar**, make it `unmodeled`, or add an
   effect such as `ambiguous_argv` and tell the operator to forbid it.

Before you open a pull request, run:

```sh
./scripts/validate.sh <cli>
./scripts/e2e.sh <cli>
```

Ask someone who did not write the grammar to review it against the CLI's source. In this collection
that review found a missed dangerous effect in most grammars that already passed both levels. See
[FINDINGS.md](FINDINGS.md#what-independent-verification-caught).
