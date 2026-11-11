# Strands Box tool grammars

Sample tool grammars for [Strands Box](https://github.com/strands-agents/box), one directory per
CLI. A tool grammar tells Box how to read one program's command line. Box turns each command the
agent runs into a named action, its fields, and its effects, and the box policy decides that action
before the program starts.

Tool grammars are an **experimental** Box feature. They load only when `box.toml` sets
`[experimental-features] tool-grammars = true`, and the format can change before Box 1.0.0. Every
grammar here is validated against one Box commit, pinned in [`BOX_REVISION`](BOX_REVISION)
(`8a5f9ba262a5`). Box's own guide is
[Tool grammars](https://github.com/strands-agents/box/blob/8a5f9ba262a5260b269b25ac6a75bf74abcdc89c/docs/user/tool-grammars.md).

These are samples. Read a grammar and its README before you rely on it, and check the version of
your CLI against the version below. What the feature can and cannot express, and the Box issues we
found, are in [FINDINGS.md](FINDINGS.md).

## The grammars

| CLI | Project | Executable | Version checked | Actions | Corpus cases | E2E cases | Grammar |
|---|---|---|---|---|---|---|---|
| aws | AWS CLI v2, aws/aws-cli | `aws` | 2.40.0 | 70 | 224 | 8 | [grammars/aws](grammars/aws/) |
| cargo | Cargo, rust-lang/cargo | `cargo` | 1.99.1 | 26 | 263 | 10 | [grammars/cargo](grammars/cargo/) |
| gh | GitHub CLI, cli/cli | `gh` | 2.103.3 | 53 | 257 | 12 | [grammars/gh](grammars/gh/) |
| git | Git, git/git | `git` | 2.56.1 | 54 | 386 | 10 | [grammars/git](grammars/git/) |
| gws | Google Workspace CLI, googleworkspace/cli | `gws` | 0.22.5 | 102 | 253 | 8 | [grammars/gws](grammars/gws/) |
| kubectl | Kubernetes, kubernetes/kubectl | `kubectl` | v1.37.2 | 36 | 308 | 12 | [grammars/kubectl](grammars/kubectl/) |
| npm | npm CLI, npm/cli | `npm` | 12.2.2 | 32 | 257 | 9 | [grammars/npm](grammars/npm/) |
| pip | pip, pypa/pip | `pip` | 26.3 | 27 | 175 | 8 | [grammars/pip](grammars/pip/) |
| stripe | Stripe CLI, stripe/stripe-cli | `stripe` | 1.55.10 | 63 | 227 | 8 | [grammars/stripe](grammars/stripe/) |
| supabase | Supabase CLI, supabase/cli | `supabase` | 3.1.0 | 72 | 239 | 8 | [grammars/supabase](grammars/supabase/) |
| uv | uv, astral-sh/uv | `uv` | 0.13.7 | 42 | 229 | 12 | [grammars/uv](grammars/uv/) |
| valyu | Valyu CLI, valyuAI/valyu-cli | `valyu` | 1.3.2 | 40 | 191 | 8 | [grammars/valyu](grammars/valyu/) |
| vercel | Vercel CLI, vercel/vercel (`packages/cli`) | `vercel` | 65.14.0 | 46 | 210 | 11 | [grammars/vercel](grammars/vercel/) |

"Actions" is the number of `[shell.<action>]` tables. A grammar models a chosen set of commands,
not the whole CLI. Everything else is `unmodeled`. Each grammar README says how to install the CLI,
what the grammar covers, its effects, example rules, and its known limits.

## Layout

```
BOX_REVISION                         the Box commit every grammar is validated against
grammars/<cli>/<cli>.grammar.toml    the grammar: the body of [tool.<label>.grammar] in box.toml
grammars/<cli>/<cli>.corpus.toml     golden cases: argv, expected action, fields, effects
grammars/<cli>/<cli>.e2e.toml        cases that run in a real box with a stub program
grammars/<cli>/gen/                  a generator, for the grammars that have one
grammars/<cli>/README.md             install, load, coverage, effects, limits
grammars/_example/                   a small grammar for a fake program
scripts/                             the validation harness
```

## Load a grammar into a box

A grammar file holds its keys at the root. In `box.toml` it goes under `[tool.<label>.grammar]`.
`render.sh` prints the whole set of tables for you:

```sh
./scripts/render.sh git --command /usr/bin/git > git-tool.toml
./scripts/render.sh gh --label gh --command /opt/homebrew/bin/gh
```

The output starts like this. Paste it into `box.toml`, then add the tool's own `env` and
`[tool.<label>.filesystem]` grants, which the grammar README describes:

```toml
[experimental-features]
tool-grammars = true

[tool.git]
command = ["/usr/bin/git"]

[tool.git.grammar]
format = 1
version = 1
name = "git"
program = "git"

[tool.git.grammar.effects]
force_push = "Can replace commits on a remote ref, so the remote loses them"
# ... the rest of git.grammar.toml
```

The last part of `command[0]` must be the grammar's `program` (here `git`). Box decides only that
called name. Another name for the same file, such as `pip3`, `uvx`, `npx`, or `vc`, is a plain
`shell:spawn` and the grammar does not see it.

Then write policy rules against the grammar's actions and effects:

```cedar
permit (principal, action == Box::Action::"shell:exec", resource);

// Let the agent run every modeled git command.
@id("git_actions")
permit (principal, action in Tool::git::Action::"*", resource);

// One rule for every force-push spelling the grammar reads.
@id("no_force_push")
@description("Force pushes are not allowed.")
forbid (principal, action == Tool::git::Action::"push", resource)
when { context.input.effects.contains(Tool::git::Effect::"force_push") };
```

What to know when you write the policy:

- `Tool::<name>::Action::"*"` is every modeled action. It does **not** include
  `Tool::<name>::Action::"unmodeled"`.
- A command line the grammar cannot read (an unknown command, an undeclared option, a long-flag
  prefix, a value spelling the grammar does not model) is `unmodeled`. With no rule that permits it,
  the default-deny refuses it with exit status 126.
- If you permit `unmodeled` by name, you allow every command the grammar cannot read, and a forbid
  over `"*"` does not apply to those lines.
- An effect is something a reviewer cares about, such as `network`, `delete_data`, or `publish`.
  Options such as `--dry-run` remove effects, so `git push -fn origin main` has no `force_push`.
- **Forbid the parser-mismatch effects.** Some grammars declare an effect for a line that the CLI
  can read differently from the grammar: `ambiguous_argv` in cargo, npm, and supabase, and
  `option_like_value` in valyu. The fields of such a line can be wrong. Add a forbid for that effect
  to every policy that uses one of these grammars. The grammar README explains when it applies.
- A denial reads `policy denied this operation on '<program file>' [policy: <@id>]: <@description>`
  and exits 126. The program does not start.

## How the grammars are validated

Four kinds of check, and each claim in this repository names which one it rests on.

| Check | What runs | Where | Proves |
|---|---|---|---|
| **Level 1** | Box's own grammar tests at `BOX_REVISION`: the real loader, the real parser, the real policy engine, and a fuzz test, over each grammar and its corpus | CI, every push and pull request | The grammar loads. Each golden case parses to its expected action, fields, and effects. A rule over the case's exact values permits it, and a rule that negates one value does not. Rules that read a field as the wrong type are refused. Each corpus argv, with an undeclared flag inserted at each position, stays `unmodeled` or keeps the word as data, and 20,000 generated argvs (shared across all grammars) hold the same parser invariants. |
| **Level 2** | A real `strands-box run` with the grammar and the policy in `<cli>.e2e.toml`, and a **stub program** in place of the CLI | CI, Linux ARM64 | The box accepts the config, a permitted command reaches the program with the argv the stub prints, and a forbidden or `unmodeled` command exits 126 with the expected `[policy: ...]` or `[default-deny]`. It does not run the real CLI. |
| **Independent source verification** | For each grammar, a reviewer who did not write it read the CLI's own source and help at the checked version, wrote extra cases, and reported findings by severity. The author fixed them, and the reviewer checked again. Each grammar here passed after two or three rounds. | One-off, before merge | The modeled effects match what the CLI really does, not only what its help text says. See [what it caught](FINDINGS.md#what-independent-verification-caught). |
| **Real-CLI execution** | The real programs, in real boxes, on Linux ARM64 and on macOS on Apple silicon, at `BOX_REVISION`, with one permitted and one forbidden command per CLI | One-off, **not in CI** | Each grammar decides real commands on both systems, and each forbid stops the program before it starts. It also found the Box issues in [FINDINGS.md](FINDINGS.md#box-defects-and-runtime-limits). |

A green CI run means Level 1 and Level 2 passed. It does not mean the real CLI runs in a box on
your system.

## Run the validation

You need git, rustup (the Box checkout pins its own Rust toolchain), and Python 3.11 or later.
Level 2 needs a Linux host where Box runs (CI uses Linux ARM64) and unprivileged user namespaces.

```sh
./scripts/validate.sh            # Level 1, every grammar
./scripts/validate.sh gh         # Level 1, one grammar
./scripts/e2e.sh                 # Level 2, every grammar with an e2e file
./scripts/e2e.sh gh              # Level 2, one grammar
```

The harness fetches Box at `BOX_REVISION` from GitHub into `.cache/` and builds it. The first run
takes a few minutes. It never changes a Box source file. Settings, all optional:

| Variable | Default | Meaning |
|---|---|---|
| `BOX_SRC` | none | A local Box git clone that holds the commit. No fetch then. |
| `BOX_URL` | `https://github.com/strands-agents/box.git` | Where to fetch Box from. |
| `SBTG_CACHE` | `.cache/` | Where the Box copy and build output live. |
| `CARGO_TARGET_DIR` | `$SBTG_CACHE/target` | The cargo target directory. |
| `SBTG_PROFILE` | `release` | `release` or `debug`. |
| `SBTG_E2E_TMP` | `/var/tmp` | Where Level 2 makes its short-lived boxes. |
| `PYTHON` | `python3` | The Python 3.11+ interpreter. |

## What CI checks

[`.github/workflows/validate.yml`](.github/workflows/validate.yml) runs on every push to `main`,
on every pull request, and on demand:

- **Level 1** on `ubuntu-24.04`: `./scripts/validate.sh` over every grammar.
- **Level 2** on `ubuntu-24.04-arm`: `./scripts/e2e.sh` over every grammar with an e2e file.

CI does not run the real CLIs, does not run on macOS, and does not repeat the source verification.

## Versions and updates

Each grammar is checked against one CLI version, named in its README and at the top of its grammar
file. A newer CLI can add commands or options. An option the grammar does not declare makes the line
`unmodeled`, so a new option is refused, not misread. A changed meaning of an existing option is not
caught. Recheck the grammar against the new version's help and source before you rely on it.

To update a grammar for a new CLI version:

1. Read the new version's changelog, help, and source for the modeled commands.
2. Edit the grammar. Four grammars are generated, so edit the generator and not the output:
   [aws](grammars/aws/README.md#regenerate), [gws](grammars/gws/README.md#regenerate),
   [stripe](grammars/stripe/README.md#regenerate), and [uv](grammars/uv/README.md) (each `gen/`
   directory). The grammar README gives the command.
3. Update the version in the grammar comment, the README, and the corpus comments. Add corpus cases
   for each new option and each changed behaviour.
4. Run `./scripts/validate.sh <cli>` and `./scripts/e2e.sh <cli>`.

To move to a new Box commit, change `BOX_REVISION` and run both levels over every grammar.

## Limits you should know

The full list, with an example from a real CLI for each, is in [FINDINGS.md](FINDINGS.md).

- A grammar sees only the command line. Environment variables, config files, CLI aliases defined on
  disk, and programs the CLI starts itself (hooks, plugins, build scripts) are not decided.
- Box binds one called name per grammar. `pip3`, `uvx`, `npx`, and `vc` are not covered.
- Some real commands cannot be spelled as a grammar action: command words are lowercase
  `[a-z0-9-]` only, and a bare program (`vercel`, `gh --version`) has no action. These lines are
  `unmodeled`.
- `removes` always wins and cannot be conditional. Some grammars therefore keep an effect even with
  `--dry-run`, or leave out a `--no-` flag.
- Some CLI parsers read a word differently from the grammar (`--flag false`, an optional value that
  takes the next word). Where this applies, forbid `ambiguous_argv` or `option_like_value`.
- On Linux at this Box revision, Node and V8 programs (npm, vercel, valyu) abort in a tool box, and
  uv cannot take its cache lock. On macOS, a CLI installed outside the operator home can fail.
  See [Box defects and runtime limits](FINDINGS.md#box-defects-and-runtime-limits).
