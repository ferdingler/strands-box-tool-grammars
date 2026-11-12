# cargo

A tool grammar for [Cargo](https://github.com/rust-lang/cargo), the Rust package manager. It lets a
box policy see what a `cargo` command line does (compile and run code, change `Cargo.toml` or
`Cargo.lock`, publish, install) and decide it.

| | |
|---|---|
| Executable | `cargo`, usually the rustup proxy, which picks a toolchain and runs that toolchain's cargo |
| Version checked | cargo 1.99.1 (`5f94df478`, Rust 1.99.1), with the clippy and rustfmt of that toolchain, against `cargo <command> --help`, `cargo help <command>`, and the cargo source at that commit |
| Policy namespace | `Tool::cargo` |

## Install cargo

Install Rust with [rustup](https://rustup.rs) and pin the toolchain you reviewed the grammar against,
for example `rustup toolchain install 1.99.1 --component clippy --component rustfmt`. This puts the
`cargo` proxy in `$CARGO_HOME/bin` (by default `~/.cargo/bin`).

## Load it in a box

The grammar binds the file that `command[0]` runs, under the name `cargo`. Generate the tables with
`./scripts/render.sh cargo --command /path/to/.cargo/bin/cargo`, which prints:

```toml
[experimental-features]
tool-grammars = true

[tool.cargo]
command = ["/path/to/.cargo/bin/cargo"]

[tool.cargo.grammar]
format = 1
version = 1
name = "cargo"
program = "cargo"
# ... the rest of cargo.grammar.toml, nested under [tool.cargo.grammar]
```

The rustup proxy is a native binary, so no interpreter needs a filesystem grant to start it. Cargo
still needs to read the toolchains under `$RUSTUP_HOME` (`~/.rustup`), read and write
`$CARGO_HOME` (`~/.cargo`: registry cache, git checkouts, installed binaries), and write the
project's `target` directory, so grant those in the tool's own filesystem lists. `rustup update`
replaces the proxy, and Box refuses a grammar whose program file changed until the box restarts.

## Supported commands

| Family | Actions | Notes |
|---|---|---|
| Compile | `build`, `check`, `doc`, `clippy` | `clippy` is the `cargo-clippy` external subcommand; words after `--` go to the lint driver. |
| Run code | `test`, `bench`, `run` | `test`/`bench`: words after `--` go to the test binary. `run`: the first operand and every word after it go to the program. |
| Format | `fmt` | The `cargo-fmt` external subcommand, with its own options; words after `--` go to rustfmt. |
| Dependencies | `add`, `remove`, `update`, `fetch`, `generate_lockfile`, `vendor` | |
| Inspect | `tree`, `metadata`, `locate_project`, `version` | `metadata` and `tree` resolve the workspace; under `--frozen` they do not reach the network or write `Cargo.lock`, and `metadata --no-deps` does not resolve at all. |
| Packages | `new`, `init`, `clean` | |
| Registry | `search`, `publish`, `package`, `install`, `uninstall` | |

The global options `-v`, `-q`, `--color`, `--locked`, `--offline`, `--frozen`, `--config`, and `-Z`
are accepted before and after the command, as cargo accepts them, on every action except `clippy`
and `fmt`. `cargo` does not pass an option given before an external subcommand on to it, so
`cargo --offline clippy` is `unmodeled`. `clippy` accepts those options after the command word,
because cargo-clippy passes them to `cargo check`. `fmt` accepts only its own options.

`cargo +<toolchain> ...` is not modeled, so it is `unmodeled` (see Exclusions).

## Effects

| Effect | Meaning | Added by | Removed by |
|---|---|---|---|
| `network` | Cargo itself can contact a registry or git source | every command that resolves, fetches, or talks to a registry; `clean -p`/`--workspace` | `--offline`, `--frozen`; `metadata --no-deps`; `install --list` |
| `update_lockfile` | Can create or rewrite `Cargo.lock` | every command that resolves the workspace; `clean -p`/`--workspace` | `--locked`, `--frozen`; `--dry-run` on `add`, `remove`, `update`, `clean`; `metadata --no-deps` |
| `run_build_scripts` | Compiles code, which runs build scripts and procedural macros | `build`, `check`, `test`, `bench`, `run`, `doc`, `clippy`, `install`, `publish`, `package` | `--no-verify` and `package --list`; `install --list` |
| `execute_built_code` | Runs a test, bench, or binary that the build produced | `test`, `bench`, `run` | `--no-run` on `test` and `bench` |
| `override_config` | Changes configuration or the manifest from the command line | `--config`, `-Z`, `-m`/`--manifest-path`, `vendor --sync`, `install --path` (cargo reads that directory's `.cargo/config.toml`) | nothing |
| `edit_manifest` | Writes dependency changes to `Cargo.toml` | `add`, `remove` | `--dry-run` |
| `write_source` | Rewrites source files | `fmt`; `clippy --fix` (also when `--fix` is the value of another option, as cargo-clippy reads it) | `fmt --check`, which does not stop a write that words after `--` cause (`-- --print-config default` overwrites a source file); those carry `pass_through_args` |
| `pass_through_args` | Passes words straight to rustfmt or the clippy driver | words after `--` on `fmt` and `clippy` | nothing |
| `create_package` | Creates a package, and can add it to a parent workspace | `new`, `init` | nothing |
| `write_files` | Writes a vendor directory and deletes stale crates there | `vendor` | nothing |
| `delete_files` | Deletes build output | `clean` | `clean --dry-run` |
| `publish_crate` | Uploads a package | `publish` | `publish --dry-run` |
| `install_binary` | Installs binaries into the install root | `install` | `install --list` |
| `uninstall_binary` | Deletes installed binaries | `uninstall` | nothing |
| `open_browser` | Opens the docs with a browser program | `doc --open` | nothing |

`--offline` alone still lets cargo write `Cargo.lock` from its local cache; only `--locked` and
`--frozen` stop that. An action with no effect (`version`, `locate_project`, `fmt --check`,
`metadata --no-deps`, `install --list`) only reads.

## Example policy rules

```cedar
// Allow every modeled cargo command by default.
@id("cargo_actions")
permit (principal, action in Tool::cargo::Action::"*", resource);

// Never publish, except as a dry run.
@id("no_publish")
@description("Publishing a crate is not allowed.")
forbid (principal, action == Tool::cargo::Action::"publish", resource)
when { context.input.effects.contains(Tool::cargo::Effect::"publish_crate") };

// Keep the project's configuration: no --config, -Z, or --manifest-path.
@id("no_config_override")
forbid (principal, action in Tool::cargo::Action::"*", resource)
when { context.input.effects.contains(Tool::cargo::Effect::"override_config") };

// Builds must keep Cargo.lock as reviewed.
@id("locked")
@description("Pass --locked or --frozen so that Cargo.lock does not change.")
forbid (principal, action in [Tool::cargo::Action::"build", Tool::cargo::Action::"check", Tool::cargo::Action::"test"], resource)
when { context.input.effects.contains(Tool::cargo::Effect::"update_lockfile") };

// Formatting may only check.
@id("fmt_check_only")
forbid (principal, action == Tool::cargo::Action::"fmt", resource)
when { context.input.effects.containsAny([
  Tool::cargo::Effect::"write_source",
  Tool::cargo::Effect::"pass_through_args"]) };

// `clean --target-dir <dir>` deletes that directory; only clean the default one.
@id("clean_default_dir")
forbid (principal, action == Tool::cargo::Action::"clean", resource)
when { context.input has target_dir };
```

These rules are the policy of `cargo.e2e.toml`, and each one refuses a line there in a real box.

## Exclusions

These are deliberately not modeled, so their lines are `unmodeled` and fall to default-deny:

- The built-in aliases `b`, `c`, `d`, `r`, `t`, and `rm`. Cargo reads an `[alias]` entry from
  `.cargo/config.toml` before its built-in alias, so a project can make `cargo t` mean
  `cargo publish`. Spell the full command: a config alias cannot replace `build`, `test`, and so on.
- `cargo up`: not a cargo 1.99.1 command or built-in alias.
- `cargo +<toolchain> ...`: the rustup proxy downloads and installs a missing toolchain before cargo
  starts (auto-install is on by default since rustup 1.28.1), even for `cargo +beta --frozen fetch`.
  A grammar cannot put an effect on the toolchain word, so these lines are `unmodeled`.
- `login`, `logout`, `owner`, `yank` (registry credentials and registry writes), `fix`, `rustc`,
  `rustdoc`, `report`, `pkgid`, `info`, `config`, `help`, `miri`, the deprecated `read-manifest` and
  `verify-project`, and every other `cargo-<x>` external subcommand.
- Top-level forms with no command: `cargo --version`, `-V`, `--list`, `--explain`, and `-C <dir>`.
- `--help`/`-h` on any command, and clippy's `--explain` and `-V`.
- Unstable options that stable cargo refuses: `--artifact-dir`, `--unit-graph`, `doc --output-format`,
  `package --message-format`, `add --public/--no-public/--base`, `update --breaking`,
  `install --dry-run`, `generate-lockfile --publish-time`, and `clean gc`.
- Hidden flags: `publish --token` (a secret on the command line), `update -p`/`--aggressive`,
  `tree -a`/`-V`/`--no-indent`, and the hidden suggestion flags (`--debug` on build, `-s`, `-t`, `-x`,
  `--path` on build).

## Known limits

- **Toolchain files are invisible.** `rust-toolchain.toml` and `RUSTUP_TOOLCHAIN` choose the
  toolchain, and rustup can download a missing one even for `cargo version`. Set
  `RUSTUP_AUTO_INSTALL=0` in the tool's environment to stop that.
- **Configuration files and the environment are invisible.** `.cargo/config.toml` (in the project
  and every parent) and `$CARGO_HOME/config.toml` can set `build.rustc-wrapper`,
  `target.<triple>.runner`, `net.offline`, registries, and aliases; so can `CARGO_*` and `RUSTFLAGS`
  environment variables. Any build can then run any program. If the workload can write a
  `.cargo/config.toml`, treat every compiling action as able to run arbitrary code.
- **Child processes are not decided.** Build scripts, procedural macros, tests, the program
  `cargo run` starts, rustfmt, clippy-driver, the browser, and the VCS program `new --vcs` can start
  all run inside the tool's own sandbox. `clippy` and `fmt` are found as `cargo-clippy` and
  `cargo-fmt` on `$CARGO_HOME/bin` or `PATH`, and a config alias can shadow them.
- **A value that looks like a flag.** For an option with a required value, the grammar takes the
  next word as the value, even `--release`, and cargo (clap) refuses that line and runs nothing.
  `-p`, `--bin`, `--example`, `--test`, `--bench`, `--target`, and `tree -i` take an optional
  value. They are `value = "optional-next"`, so the grammar reads a following word that starts
  with `-` as an option, as cargo does.
- **Short `=` values.** `-p=foo` is valid to cargo and `unmodeled` here; write `-pfoo`, `-p foo`, or
  `--package=foo`.
- **Values are sets.** `add serde -F derive tokio -F full` records `features = ["derive", "full"]`
  without which crate each feature belongs to, and `run` arguments lose their order.
- **`network` is cargo's own access.** Build scripts and tests can open connections themselves.
- **`update_lockfile` on a compile is a "can".** A build with an up-to-date `Cargo.lock` writes
  nothing; the grammar cannot know.
