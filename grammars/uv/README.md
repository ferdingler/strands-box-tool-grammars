# uv

A tool grammar for [uv](https://github.com/astral-sh/uv), the Python package and project manager by
Astral. It lets a box policy see what a `uv` command line does (run a program, install packages,
publish, change user state) and decide it.

| | |
|---|---|
| Executable | `uv`, a native binary. `uvx` is a separate program name and is **not** bound by this grammar. |
| Version checked | uv 0.13.7 (commit `316c827e0`), against `uv <command> --help` and the clap definitions in `crates/uv-cli` at that tag |
| Policy namespace | `Tool::uv` |

To change the grammar, edit `gen/head.toml` or `gen/gen.py` and run `python3 grammars/uv/gen/gen.py`,
which rewrites `uv.grammar.toml`.

## Install uv

Use the official standalone installer or a release archive from
<https://github.com/astral-sh/uv/releases>. Either gives a native `uv` binary. Pin the version you
reviewed the grammar against.

## Load it in a box

The grammar binds the file that `command[0]` runs, under the name `uv`. Generate the tables with
`./scripts/render.sh uv --command /path/to/uv`, which prints:

```toml
[experimental-features]
tool-grammars = true

[tool.uv]
command = ["/path/to/uv"]

[tool.uv.grammar]
format = 1
version = 1
name = "uv"
program = "uv"
# ... the rest of uv.grammar.toml, nested under [tool.uv.grammar]
```

uv is a native binary, so no interpreter needs a filesystem grant to start it. uv still needs to read
and write its cache, the project, and (for `tool` and `python`) its user data directories, so grant
those in the tool's own filesystem lists. `uv self update` replaces the binary, and Box refuses a
grammar whose program file changed until the box restarts.

## Supported commands

| Family | Actions | Notes |
|---|---|---|
| Project | `run`, `init`, `add`, `remove`, `sync`, `lock`, `tree`, `export`, `version` | `run` takes the program and its arguments as one `command` operand. |
| Environments and builds | `venv` (aliases `virtualenv`, `v`), `build`, `publish` | `publish` accepts only `-q`, `-v`, and `--no-progress` from the global options. |
| Tools | `tool_run`, `tool_install`, `tool_uninstall`, `tool_upgrade` (alias `tool update`), `tool_list` (alias `tool ls`), `tool_dir`, `tool_update_shell` (alias `tool ensurepath`) | |
| Python | `python_list` (alias `python ls`), `python_install`, `python_upgrade`, `python_find`, `python_pin`, `python_uninstall`, `python_dir`, `python_update_shell` | |
| pip interface | `pip_install`, `pip_sync`, `pip_compile`, `pip_uninstall`, `pip_list` (alias `pip ls`), `pip_show`, `pip_freeze`, `pip_check`, `pip_tree` | |
| Cache and self | `cache_clean` (alias `cache clear`), `cache_prune`, `cache_dir`, `cache_size`, `self_update`, `self_version` | |

The global options (`-q`, `-v`, `--color`, `--offline`, `--allow-insecure-host`/`--trusted-host`,
`--directory`, `--project`, `--config-file`, `--no-config`, `-n`/`--no-cache`, `--cache-dir`,
`--system-certs`, `--native-tls`, `--managed-python`, `--no-managed-python`, `--no-python-downloads`,
`--no-progress`, `--preview`) are accepted before, between, and after the command words, as uv
accepts them. `--python`/`-p` and the index options are per-command in uv, so only the commands that
take them accept them.

## Effects

| Effect | Meaning | Added by | Removed by |
|---|---|---|---|
| `read_only` | Makes no change to files, environments, or settings | list, show, find, dir, `version` alone, `python pin` alone | any `-p/--python`, a request to `python find`/`pin`, `python find --script`, a value or `--bump` on `version`, `--rm` on `python pin` |
| `network` | uv may contact indexes, Git hosts, or Python download servers | resolving, installing, downloading, publishing, `--outdated` | global `--offline` (not on `publish`) |
| `run_program` | Runs a program the line names | `run`, `tool run`, every `-p/--python` value, a `python find`/`python pin` request | nothing |
| `build_code` | May run a package build backend (arbitrary code) | every command that resolves or installs, and `build` | nothing; `--no-build` still builds editables |
| `modify_environment` | Creates or changes a Python environment | `sync`, `add`, `remove`, `run`, `venv`, `pip install/sync/uninstall`, `tool run`, `version` with a value | `--dry-run`, `--check`, `--no-sync` (on `add`, `remove`, `version`) |
| `modify_project` | Writes pyproject.toml, uv.lock, or .python-version | `init`, `add`, `remove`, `sync`, `lock`, `tree`, `export`, `run`, `version` with a value, `python pin` | `--locked`, `--frozen` (where they keep uv.lock unchanged), `--check`, `--dry-run` |
| `modify_user` | Changes tools, managed Pythons, shell files, or uv itself | `tool install/upgrade/uninstall`, `python install/upgrade/uninstall`, `update-shell`, `self update`, `python pin --global`, `python find --script` | `self update --dry-run` |
| `delete_data` | Deletes cache entries, tools, Pythons, packages, or a directory's contents | `cache clean/prune`, uninstalls, `venv --clear`, `build --clear`, `python pin --rm` | `pip uninstall --dry-run` |
| `publish` | Uploads distributions | `publish` | `publish --dry-run` |
| `credentials` | The line carries a secret | `publish -p/-t`, `self update --token`, an index URL with `user@` in it | nothing |
| `disable_tls_verification` | Insecure connections to a host | `--allow-insecure-host`, `--trusted-host` | nothing |
| `override_index` | Uses an index or upload URL that the line names | `--index`, `--default-index`, `-i`, `--extra-index-url`, `-f`, `publish --index/--publish-url/--check-url` | nothing |
| `override_config` | Uses a named config file, or ignores the discovered ones | `--config-file`, `--no-config` | nothing |
| `other_directory` | Runs against another directory or project | `--directory`, `--project` | nothing |
| `system_python` | May change a system Python, not a virtual environment | `pip install/sync/uninstall` with `--system`, `--break-system-packages`, or any `-p/--python` | nothing |
| `write_file` | Writes into, or removes from, a file or directory the line names | `export -o`, `pip compile -o`, `build -o`, `pip install/sync/uninstall -t/--prefix`, `python install/upgrade/uninstall -i`, the `init` and `venv` path | nothing |

## Example policy rules

```cedar
// Allow every modeled uv command by default.
@id("uv_actions")
permit (principal, action in Tool::uv::Action::"*", resource);

// Never publish, except as a dry run.
@id("no_publish")
@description("Publishing packages is not allowed.")
forbid (principal, action == Tool::uv::Action::"publish", resource)
when { context.input.effects.contains(Tool::uv::Effect::"publish") };

// Do not run arbitrary programs through uv.
@id("no_run_program")
forbid (principal, action in [Tool::uv::Action::"run", Tool::uv::Action::"tool_run"], resource)
when { context.input.effects.contains(Tool::uv::Effect::"run_program") };

// Keep installs on the default index and off the system Python.
@id("no_index_override")
forbid (principal, action in Tool::uv::Action::"*", resource)
when { context.input.effects.containsAny([
  Tool::uv::Effect::"override_index",
  Tool::uv::Effect::"disable_tls_verification",
  Tool::uv::Effect::"system_python"]) };

// Require the lockfile to stay as reviewed.
@id("locked_sync_only")
forbid (principal, action == Tool::uv::Action::"sync", resource)
when { context.input.effects.contains(Tool::uv::Effect::"modify_project") };
```

## Exclusions

These are deliberately not modeled, so their lines are `unmodeled` and fall to default-deny:

- `uv auth` (stores and prints credentials), `uv format` (downloads and runs Ruff, rewrites files),
  `uv check`, `uv audit`, `uv workspace`, `uv help`, the hidden `uv tool uvx`, `uv pip debug`, and
  `uv tool audit`.
- `uv --version`, `-V`, `-h`, `--help`.
- Hidden opposite flags such as `--no-offline`, `--no-frozen`, `--no-locked`, `--no-check`: a
  declared `--offline` or `--frozen` could otherwise be cancelled by one the grammar cannot see.
- Options whose effect the grammar cannot state: `-C/--config-setting` (build backend settings),
  `--keyring-provider`, `--cert`, `--python-downloads-json-url`, the Python mirror options,
  `--torch-backend`, `--python-platform`, pip compatibility flags such as `--user`, and the less
  common resolver and install options. Each makes its line `unmodeled`.
- A global option given with `uv publish`: `publish` declares a hidden `--offline` of its own, so a
  global `--offline` could not truthfully remove `network` there.

## Known limits

- `-p/--python` and a `python find`/`pin` request always add `run_program`. uv executes the
  interpreter a request names to query it, and a bare name is looked up on `PATH`. A `like` pattern
  cannot tell `3.12` from `mypython3` or `./x`, so even a version request counts. In the `pip`
  commands that change an environment it also adds `system_python`.
- `publish` can authenticate with ambient credentials (keyring, trusted publishing through OIDC, or
  `UV_PUBLISH_*` variables). Those add no `credentials` effect, which only marks a secret on the line.

- Environment variables (`UV_INDEX_URL`, `UV_OFFLINE`, `UV_PUBLISH_TOKEN`, `UV_INSECURE_HOST`, ...)
  and configuration files (`[tool.uv]` in pyproject.toml, `uv.toml`) can change what a line does.
  The grammar sees only the command line.
- `run_program` and `build_code` mark lines that start other code. That code runs in the tool's own
  sandbox, and Box does not decide its spawns. uv also runs Python interpreters to inspect them
  during discovery, on almost every command.
- `--offline` removes uv's own `network`. The program that `uv run --offline` starts can still use
  the network, subject to the box's egress rules.
- `-w=x` (a short flag, `=`, a value) is `unmodeled`, though uv accepts it. Write `-wx` or `-w x`.
- `python pin --global` with no request only shows the global pin, but the grammar still reports
  `modify_user`, because one flag cannot see whether a request was given.
