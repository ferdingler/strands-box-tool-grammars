# Findings: tool grammars on 13 real CLIs

This report says how well the Strands Box tool-grammar feature handles real command-line tools.
It is based on 13 grammars, all at Box `8a5f9ba262a5`
(`BOX_REVISION`). Each claim names the check it rests on:

- **Level 1**: Box's loader, parser, policy engine, and fuzz test over the golden cases (CI).
- **Level 2**: a real `strands-box run` with a stub program in place of the CLI (CI, Linux ARM64).
- **Source verification**: an independent review of each grammar against the CLI's own source and
  help, in two or three rounds.
- **Real-CLI execution**: one-off runs of the real programs in real boxes, on Linux ARM64 and on
  macOS on Apple silicon. Not in CI. One permitted and one forbidden command per CLI, on the grammar
  branches just before merge.

## Summary

The feature works. A grammar turns a real CLI's many spellings into one action and a few effects,
and a short policy can then permit or forbid them. Every forbid we tried stopped the real program
before it started, on both systems (real-CLI execution). The safe default holds: a line the grammar
cannot read is `unmodeled`, and the default-deny refuses it.

The limits are in what a grammar can express. Many real CLI parsers do things the grammar format
cannot describe. Each grammar works around them by leaving lines `unmodeled` or by over-stating an
effect. That is safe, but it costs coverage. Golden tests alone were not enough: source verification
found a missed dangerous effect in 11 of the 13 grammars. We also found one Box defect and
two runtime limits that stop some real CLIs from running.

| Worked | Did not work, or needed a workaround |
|---|---|
| One rule covers every spelling of an effect | Command words with `_`, uppercase, or `+` cannot be modeled |
| `unmodeled` default-deny for anything not declared | A bare program (`vercel`, `gh --version`) has no action |
| `removes` for `--dry-run` and similar flags | `removes` always wins and cannot be conditional |
| The Level 1 harness catches grammar and corpus errors | No boolean-value flag kind, and no "make unmodeled if" primitive |
| 13 of 13 forbids enforced before spawn, on Linux and on macOS | `like` is case-sensitive and has only `*` |
| 13 of 13 real CLIs ran on macOS | On Linux, Node/V8 CLIs abort, and uv cannot take its lock |

## Strengths

**One rule covers every spelling.** The git grammar gives `push` the effect `force_push` for `-f`,
`--force`, `--force-with-lease`, `--mirror`, and a `+<refspec>` operand. One forbid over
`Tool::git::Effect::"force_push"` refuses all of them. Level 2 pins `git push -f origin main` and
`git push origin +main`, which both exit 126 with `[policy: no_force_push]`.

**Unknown means refused.** Anything the grammar does not declare makes the whole line `unmodeled`:
an unknown command, an undeclared option, a long-flag prefix such as `git push --forc`, a repeated
single-value option, or `-x=v`. `"*"` does not include `unmodeled`, so a policy that permits `"*"`
still refuses these lines. Level 2 pins `git push --forc origin main`, which exits 126 with
`[default-deny]`. Because there is no prefix matching, a CLI that accepts abbreviations (pip, git,
aws) cannot reach a modeled action through one (Level 1 corpus cases in each grammar).

**`removes` for dry runs.** A flag can take an effect away. `git push -fn origin main` has no
`force_push`, so the same policy lets it run (Level 2). The kubectl grammar removes `cluster_write`
for `--dry-run`, and the sample grammar removes `delete_data` for `-n`.

**The harness catches mistakes.** Level 1 runs the real parser and the real policy engine. A wrong
corpus expectation fails with the case number, the expected result, and the result the parser got.
A grammar that names an undeclared effect fails at load and names the key path. The fuzz test puts an
undeclared flag at each position of each corpus argv, and checks that the line stays `unmodeled` or
keeps the word as data. The engine test also checks that a rule that reads a field with the wrong
type is refused. A policy that reads one field name with two types does not load, and that found a
type clash in the gh grammar during authoring.

**Enforcement before spawn, on both systems.** On Linux ARM64 and on macOS, each of the 13 grammars
loaded in a real box. For each CLI, one forbidden command exited 126 with its `[policy: <id>]`, and
the program did not start. Canary files confirmed that nothing ran for git, cargo, npm, and uv on
Linux, and for git, kubectl, vercel, and pip on macOS (real-CLI execution). On macOS, all 13 real
programs ran their permitted command. On Linux, 9 did (gh, aws, kubectl, cargo, git, stripe,
supabase, gws, pip). See [Box defects and runtime limits](#box-defects-and-runtime-limits) for the
other 4.

## Expressiveness limits

Each limit has an example from a real CLI and what the grammar does about it. Unless it says
otherwise, Level 1 corpus cases pin the grammar's choice, and a small repro grammar showed the limit
in Level 1.

### Command words are lowercase `[a-z0-9-]` only

```
gws drive files emptyTrash        # camelCase Discovery method
gws gmail +send --to ...          # helper command
stripe payment_intents list       # `_` in the command name
```

The loader refuses such a `usage`. The CLIs accept only these exact spellings. **Workaround:** these
commands are `unmodeled`. gws models the generic method that each helper wraps. stripe leaves
`payment_intents`, `payment_methods`, `setup_intents`, `webhook_endpoints`, and every `test_helpers`
group `unmodeled`. These are among stripe's most used objects.

### No action for a bare program

```
vercel                # deploys the current directory
vercel ./site         # deploys a path
gh --version
pip --version
```

Every action needs at least one command word. **Workaround:** these lines are `unmodeled`. A vercel
deploy must be spelled `vercel deploy`.

**Box change:** strands-agents/box#436 lets a usage have no command word. The vercel `deploy`
usage now has none, with the alias `deploy`, so `vercel` and `vercel ./site` deploy. A first operand
that looks like a command word stays `unmodeled`. Real-CLI execution on Linux showed `pip --version` refused
with `[default-deny]`.

### No prefix or abbreviation matching

```
pip install --upgr x          # pip (optparse) accepts a unique prefix
git push --forc origin main   # git expands it to --force
```

The grammar looks a flag up by its exact spelling. **Effect:** the line is `unmodeled`. This is the
safe side, but an agent that uses abbreviations is refused.

### No boolean-value kind, and no "unmodeled if a value matches"

```
npm publish --dry-run false                # nopt reads `false` as the flag's value: it publishes
supabase functions deploy --debug false    # effect/cli reads `false` as the value: deploys every function
gh release create v1 --latest=false
```

A flag in the grammar never takes a value. So `false` becomes an operand, and the flag's `removes`
still applies. **Workaround:** the npm and supabase grammars add `ambiguous_argv` when an operand is a
boolean literal, and their READMEs say to forbid it. Where an action has no operand slot, the word is
left over and the line is `unmodeled`. gh leaves every `--flag=false` spelling `unmodeled`. A grammar
cannot say "this line is `unmodeled` when a value looks like X". It can only add an effect, and the
policy must forbid that effect.

The same kind of mismatch comes from other parser rules. npm gives a string option an empty value
when the next word looks like a flag, so `npm publish --tag --access=public` publishes in public,
while the grammar reads `tag = "--access=public"`. valyu (commander) reads a top-level `-p` inside
another option's value, so `valyu batch create --name -p prod q1` runs on the `prod` profile. Both
grammars add an effect for a value that starts with `-`: `ambiguous_argv` in npm, and
`option_like_value` in valyu.

### `removes` always wins and is unconditional

```
pip install --no-index -f https://example.org/wheels attrs   # still uses the network
aws ec2 terminate-instances --dry-run --no-dry-run ...       # argparse keeps the last one: runs for real
cargo fmt --check -- --print-config default rustfmt.toml    # still writes rustfmt.toml
```

A remove takes the effect off the whole line, whatever else adds it and in any order. There is no
"remove unless", no effect from a combination of fields, and no order-sensitive last-wins pair.
**Workarounds:**

- pip keeps `network` on install, and `--no-index` is only a field.
- aws does not declare `--no-dry-run`, so that line is `unmodeled`.
- valyu keeps `high_cost` on every `workflows run`, because a hidden later `-m max` can win over a
  `-m fast` that would remove it.
- cargo adds a separate `pass_through_args` effect that nothing removes.
- git leaves `checkout -f` `unmodeled`, because `-b` cancels one source of `discard_changes` and
  not the other.
- gh gives every `gh api graphql` call `write_remote`, because a read cannot be told from a
  mutation on the same line.

### `like` is case-sensitive and has only `*`

```
kubectl get Secret db -o yaml
kubectl get SECRETS
kubectl delete customResourceDefinitions x
```

kubectl lowercases resource names. `like` has no case folding, no character class, and no negation.
**Workaround:** the kubectl grammar lists all 64 casings of `*secret*` to add `read_secrets`.
`customresourcedefinition` has about 2^24 casings, so the grammar matches every casing of the
shorter `*efin*` instead, which also over-flags any custom type that contains it. A pattern such as "not localhost" cannot be written (kubectl, vercel).

### Option and value spellings the parser cannot read

| Spelling | Real CLI | The grammar reads it as |
|---|---|---|
| Single-dash long flag `-version` | (a rule of the format) | The cluster `-v -e -r ...` |
| `-n=foo` | kubectl (pflag) reads the value `foo`; pip reads `=foo` | `unmodeled` |
| `-Sacme` | vercel (arg@5) refuses it | `-S` with the value `acme` |
| `-it` | kubectl: two booleans that also accept `--stdin=false` | Only one shape fits. The grammar uses plain flags, so `--stdin=false` is `unmodeled` |
| `-wg` | npm expands it to `-w -g` | `-w` with the value `g`. The npm grammar declares no single-letter option with a value |

### An option between command words

```
pip config --user set global.index-url https://example.org
```

This is pip's documented form. Only `anywhere` global options may sit between command words, and a
global `--user` would be a field of every pip action. **Workaround:** the line is `unmodeled`. The
grammar models `pip config set --user ...`.

### Options that stop at the first operand

```
git config user.name --global     # writes the value "--global" to the local config
```

`git config` and a bare `git stash` stop option parsing at the first operand. The grammar reads
options and operands in any order. **Workaround:** every operand of the older `git config` form adds
`override_config`, so any line with an operand counts as a write.

### An optional value that takes the next word unless it looks like a flag

```
cargo install --bin --root /r foo    # clap: --bin gets no value, and --root is an option
valyu contents --summary https://a.example https://b.example
aws s3 cp x s3://b/k --sse aws:kms
```

clap, commander, and argparse `nargs="?"` take the next word as the value unless it starts with `-`.
The grammar has `required` (always the next word) and `optional` (never the next word).
**Workaround:** cargo uses `required` and adds `ambiguous_argv` when the value starts with `-`. valyu
keeps `optional`, so its URL set is a superset. aws does not declare these options.

### The toolchain word cannot carry an effect

```
cargo +beta version     # the rustup proxy downloads and installs the toolchain first
```

`[+<toolchain>]` gives a field, but no `adds`. **Workaround:** no cargo action declares a toolchain,
so `cargo +<x> ...` is `unmodeled`.

### Global removes are not scoped per action

```
uv publish --offline    # uv hides the global --offline here
```

A global option's `removes` applies to every action that takes global options, so `--offline` would
remove `network` from `publish` too. **Workaround:** uv `publish` takes no global options, so these
lines are `unmodeled`.

### One field name, one type, across actions

In gh, the `repo` field was a String in most actions and a Set in `search`. A rule over
`Tool::gh::Action::"*"` that reads `context.input.repo` then does not load. **Workaround:** the gh
grammar names the search field `repo_filter`. Its README lists the clashes that remain.

### A grammar sees only argv

The grammar cannot see environment variables, config files, files that a flag names, or programs
that the CLI starts. Some of these change what a command means:

- cargo: a project `.cargo/config.toml` `[alias]` can make `cargo t` mean `cargo publish`. The cargo
  grammar leaves the short built-in aliases (`b`, `c`, `d`, `r`, `t`, `rm`) `unmodeled`.
- aws: `~/.aws/cli/alias` can give a built-in command another meaning, or run a shell command. The
  aws README says to keep that file unwritable by the agent and the tool.
- gh: config aliases such as `gh co` can be redefined, so the gh grammar leaves them `unmodeled`.
- vercel: a `vercel.json` `env` array copies local variables, such as `VERCEL_TOKEN`, into a
  deployment with no flag on the line. The vercel grammar adds `export_local_env` to every deploy.
- pip, kubectl, and aws read files that a flag names (`-r reqs.txt`, `-f manifest.yaml`,
  `file://...`). The grammars add an effect for these, such as `opaque_input` or `manifest_input`.
- Hooks, plugins, extensions, build scripts, and lifecycle scripts run inside the tool's sandbox, and
  Box does not decide them.

### One grammar per called name

Box decides only the name in the grammar's `program`. `pip3`, `uvx`, `npx`, and `vc` (vercel's
second name) are plain `shell:spawn`s, and the grammar does not see them. `python -m pip` is a spawn
of `python`.

## Box defects and runtime limits

All at Box `8a5f9ba262a5260b269b25ac6a75bf74abcdc89c`, found by real-CLI execution.

### 1. Defect: `renameat2` is refused in a Linux tool box, so uv cannot take its lock

- **Observed.** In a `[tool.<name>]` box on Linux, `renameat2(..., RENAME_NOREPLACE)` in a directory
  with a write grant returns `EPERM`. `renameat` in the same place works. Outside the box the same
  call succeeds. uv 0.13.7 then fails each command that takes its cache lock, such as `uv venv` and
  `uv pip list`, with `error: Could not acquire lock` (exit 2), also with `--no-cache`. Any Rust
  program that uses `tempfile`'s `persist_noclobber` is likely affected too.
- **Expected.** A rename inside a write grant succeeds, as `renameat` does. `renameat2` is not in the
  workload syscall allowlist (`WORKLOAD_PERMITTED` in
  `crates/containment/src/backend/linux/namespace/syscall.rs`). Because the filter returns `EPERM`
  and not `ENOSYS`, libraries do not fall back to `link` and `unlink`.
- **System.** Linux 6.12, aarch64, non-root.
- **Steps.** Use a standalone CPython install at `<PY>` as the tool, and an empty directory `<W>`
  with `b`, `h`, and `d` in it (mode 0700). `box.toml`:

  ```toml
  name = "renameat2-repro"
  box_dir = "<W>/b"
  policy = "policy.dw"

  [agent]
  command = ["/bin/bash"]
  workspace = "<W>/d"
  env = { HOME = "<W>/h" }

  [agent.filesystem]
  read = ["<W>/h"]
  write = ["<W>/h"]

  [tool.python3]
  command = ["<PY>/bin/python3.14"]

  [tool.python3.filesystem]
  read = ["<PY>", "<W>/d"]
  write = ["<W>/d"]
  ```

  `policy.dw` permits `Box::Action::"shell:exec"` and `Box::Action::"shell:spawn"`. Run this command
  in the box's Shell, and again outside the box from `<W>/d`. `276` is `SYS_renameat2` on aarch64,
  and the last `1` is `RENAME_NOREPLACE`.

  ```sh
  python3.14 -I -c 'import ctypes,os;l=ctypes.CDLL(None,use_errno=True);open("a","w").close();open("c","w").close();r=l.syscall(276,-100,b"a",-100,b"b",1);print("renameat2 rc",r,"errno",ctypes.get_errno());os.rename("c","e");print("renameat ok")'
  ```

  In the box it prints `renameat2 rc -1 errno 1`, then `renameat ok`. Outside the box it prints
  `renameat2 rc 0`.

### 2. Limit: V8 programs abort in a Linux tool box (exit 133)

- **Observed.** npm 12.2.2 and vercel 65.14.0 on Node 22.22.3, and the valyu 1.3.2 single binary
  (Node inside), exit 133 before any output:
  `# Fatal error in , line 0` / `# Check failed: 12 == (*__errno_location ()).`
  `NODE_OPTIONS=--jitless` lets Node start, but npm and vercel then fail with
  `WebAssembly is not defined`, and valyu still aborts. The grammar still decides: the forbid exits
  126, and the permit reaches the program, which then aborts.
- **Expected.** A tool that the box accepts can start, or `run` refuses it, or the user docs say that
  it will not run. The cause is the tool box's W^X restriction on Linux: V8 asks for a writable and
  executable mapping and aborts when it is refused. Box states this only in a contributor note for
  its containment crate, and its user docs have no entry for it. The startup disclosure for the tool
  says `broad exec: may run any reachable binary, and load code it writes into its writable grants
  above`, which reads as if a JIT would work.
- **Not affected.** supabase 3.1.0 (Bun, JavaScriptCore) runs without a JIT and works.
- **System.** Linux 6.12, aarch64.
- **Steps.** Put `npm` in a `[tool.npm]` table with `read` on the Node install,
  `read_file = ["/usr/bin/env"]`, and `env.PATH` with Node's `bin` first. Load the npm grammar, permit
  `Tool::npm::Action::"*"`, and run `npm ls` in the box's Shell. The status is 133.

### 3. Limit: a macOS tool box sees metadata only under the operator home

- **Observed.** When the operator `HOME` (the `HOME` of `strands-box run`) did not enclose the CLI
  install and the workspace, permitted commands failed inside the tool box. The forbids were still
  correct.
  - npm and vercel: `Error: EPERM: operation not permitted, lstat '<install>/bin'`. Node resolves
    the link to its own script.
  - `supabase init`: `PermissionDenied: FileSystem.access (<parent>/.git)`. It walks up to find a
    repository.
  - `uv venv`: ``failed to open file `<parent>/uv.toml`: Operation not permitted``. It walks up to
    find its config.
  - `aws configure list`: exit 255 with no output.

  With an operator `HOME` that enclosed both, all of them ran, and no grant changed.
- **Expected.** This is Box's documented tool-box shape: a tool box gets metadata across the operator
  home only. But a CLI installed outside `$HOME`, such as under `/opt`, gets `EPERM` and not `ENOENT`
  for a parent directory, and programs that walk up from their workspace treat `EPERM` as fatal. No
  startup line says that the tool box cannot see metadata outside the home. The operator sees only
  the program's own error.
- **System.** macOS 27.0.1, Apple silicon.
- **Steps.** Install uv, and make the box's workspace, in a directory outside your home. Run
  `strands-box run` with `HOME` set to a directory that encloses neither, and run `uv venv` in the
  box's Shell. It fails. Run again with `HOME` set to a directory that encloses both. It works.

### 4. Minor: cargo on macOS

- `cargo build` in a tool box prints
  ``warning: invoking "xcrun" "--sdk" "macosx" "--show-sdk-path" to find MacOSX.sdk failed: No such file or directory (os error 2)``.
  The build and the link still succeed. `xcrun` works in a tool box of its own, so the cause is not
  isolated. This may not be a Box defect.
- A denial of `cargo build --release` names `.../cargo/bin/rustup`, not `cargo`. Under rustup,
  `cargo` is a proxy for the same file. The decision is correct, but the path in the message can
  confuse an operator.

### Install notes, not Box defects

- Node 26 for Linux ARM64 needs `libatomic.so.1`, which our Linux host did not have. Box refuses every
  `LD_` name in a tool's `env`, so a private library path is not possible. We used Node 22.22.3 on
  Linux.
- A Python venv made through a path with a symlink in it does not start in a tool box
  (`Failed to import encodings module`), because a filesystem grant may not be a symlink. Make the
  venv from the canonical path, and grant `read` on the whole Python install directory.

## What independent verification caught

Every grammar passed Level 1 and Level 2 before verification. A second reviewer then read the CLI's
source at the checked version and wrote more cases. In round 1, 11 of the 13 grammars had
at least one BLOCKER: a dangerous effect that the grammar missed, so that a policy that forbids the
effect would permit the line. gh and npm had one MAJOR each. Each grammar passed in a later round.

| CLI | Rounds | Round-1 BLOCKERs | Example |
|---|---|---|---|
| aws | 2 | 1 | `aws configure get aws_security_token` prints the session token, but read as `read_config` only |
| cargo | 2 | 2 | `cargo install --bin --root /r foo` (clap gives `--bin` no value); `cargo +beta version` downloads a toolchain |
| gh | 2 | 0 (1 MAJOR) | `gh pr create --dry-run` can still create a fork on GitHub and change git remotes |
| git | 2 | 1 | `git fetch -p origin 'refs/tags/*:refs/tags/*'` deletes local tags, but had no `delete_ref` |
| gws | 3 | 1 | `drive revisions update --json '{"published":true}'` publishes a document to the web, but had no `make_public` |
| kubectl | 3 | 4 | `kubectl describe secret X` prints a service-account token; `patch`, `label`, and `scale` with `--dry-run=client -o yaml` print the Secret |
| pip | 2 | 1 | `pip install "pkg @ git+https://..."` (PEP 508) runs git, but the `git+*` pattern matched only at the start |
| stripe | 2 | 2 | `stripe invoices create -d auto_advance=true` turns on automatic charging; `subscriptions pause` can invoice |
| supabase | 2 | 3 | `functions deploy --debug false` deploys every function; `--remote postgresql://...` writes to that URL |
| uv | 3 | 1 | `uv pip list --python ./x` executes `./x`. Round 2 found one more: `uv python list ./x` |
| valyu | 2 | 2 | `workflows run` with no `-m` can run the most expensive mode; a top-level `-p` inside a value changes the account |
| vercel | 3 | 1 | `vercel deploy --env VERCEL_TOKEN` copies a local secret into the deployment. Round 2 found one more: the same copy through `vercel.json` |
| npm | 3 | 0 (1 MAJOR) | `npm init --workspace x` installs packages and may run scripts, but read as `modify_package_json` only |

Golden cases prove that a grammar does what its author meant. They do not prove that the author
understood the CLI. Most BLOCKERs came from CLI behaviour that the help text does not show: a parser
rule, a server-side default, or a value that names a program.

## Suggestions for the feature

These are suggestions from this work, not decisions. Each one names the limit it would remove.

- **`value = "boolean"`**: a flag that also takes a following `true` or `false` (and `--x=false`),
  and records a Bool. For npm (nopt), supabase (effect/cli), and gh and kubectl (pflag).
- **A value mode "next word unless it looks like an option"**, for clap, commander, and argparse
  `nargs="?"` (cargo, valyu, aws). It would also make `required` exact for most clap CLIs.
- **An "unmodeled when" primitive**: make the line `unmodeled` when a value matches a pattern, such
  as a value that starts with `-`. It would replace the `ambiguous_argv` and `option_like_value`
  effects, which a policy must remember to forbid.
- **Conditional removes**: `unless`, a remove scoped to the field whose add it cancels, or ordered
  last-wins pairs such as `--dry-run` and `--no-dry-run`. For pip, git, aws, valyu, cargo, and gh
  GraphQL.
- **Case-insensitive `like`**, and a negated pattern. For kubectl resource names and "not localhost".
- **Wider command words**: allow `_` and uppercase, and perhaps a leading `+`. For stripe and gws.
- **Effects on the toolchain field**, for `cargo +toolchain`.
- **A bare-program action**, for `vercel`, `vercel <path>`, and `<program> --version`.
- **An action-level "options before operands" switch**, for `git config` and `git stash`.
- **Per-action scope for a global option's effects**, for `uv publish --offline`.
- **Box runtime**: permit `renameat2` in a tool box's write grants; refuse at startup, or document, a
  Linux tool that needs a JIT; and say at startup when a macOS tool's program or workspace is outside
  the operator home.
