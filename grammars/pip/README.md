# pip

A tool grammar for [pip](https://pip.pypa.io/), the Python package installer from the
[Python Packaging Authority](https://github.com/pypa/pip).

| | |
|---|---|
| Executable | `pip`, a Python console-script entry point |
| Version checked | pip 26.3 (tag `26.3`), against `pip <command> --help` and the pip source at that tag |
| Policy namespace | `Tool::pip` |

The grammar binds the called name `pip` only. `pip3`, `pip3.14`, and `python -m pip` are other
names: each one is a spawn of another program (`pip3`, or `python`), so this grammar does not
decide it. If you want the agent to use pip, tell it to call `pip`, and do not give the box another
name for the same file.

## Install pip

pip ships with most Python installations. Put a pinned pip in a virtual environment:

```sh
python3 -m venv /path/to/venv
/path/to/venv/bin/python -m pip install pip==26.3
```

## Load the grammar

`pip` is a Python script: its first line names the interpreter
(`#!/path/to/venv/bin/python`). On Linux, Box refuses the tool unless the tool's filesystem
lists cover each interpreter in that chain, so list the virtual environment and the base Python
it links to. pip also needs write access to the environment to install into it.

```toml
[experimental-features]
tool-grammars = true

[tool.pip]
command = ["/path/to/venv/bin/pip"]

[tool.pip.filesystem]
read  = ["/path/to/venv", "/path/to/base-python"]   # the venv and the Python it links to
write = ["/path/to/venv"]                           # only if the agent may install

[tool.pip.grammar]
format = 1
version = 1
name = "pip"
program = "pip"
# ... the rest of pip.grammar.toml, nested under [tool.pip.grammar]
```

`./scripts/render.sh pip --command /path/to/venv/bin/pip` prints the complete `[tool.pip]` and
`[tool.pip.grammar]` tables. Restart the box after you upgrade pip: Box refuses a program file
that changes while the box runs.

## Supported commands

| Family | Actions | Effects the action always has |
|---|---|---|
| Install | `install` | `install_packages`, `network`, `run_build_backend` |
| Fetch and build | `download`, `wheel`, `lock` | `network`, `run_build_backend` |
| Uninstall | `uninstall` | `remove_packages` |
| Read the environment | `list`, `show`, `freeze`, `inspect`, `check`, `hash`, `debug` | none (`list -o`/`-u` add `network`) |
| Query an index | `index_versions` (`pip index versions`), `search` | `network` |
| Cache | `cache_dir`, `cache_info`, `cache_list`, `cache_remove`, `cache_purge` | `delete_cache` for `remove` and `purge` |
| Configuration | `config_list`, `config_get`, `config_debug`, `config_set`, `config_unset`, `config_edit` | `override_config` for `set`, `unset`, `edit`; `edit` also `run_program` |
| Help | `help`, `completion` | none |

Each action has one field per option it declares. The general options (`-v`, `-q`, `--isolated`,
`--no-input`, `--proxy`, `--cert`, `--trusted-host`, `--timeout`, `--retries`, `--cache-dir`,
`--no-cache-dir`, `--disable-pip-version-check`, `--require-virtualenv`, and others) are accepted
before and after the command, as pip accepts them. `--python` is accepted only before the
command, because pip refuses it after the command name.

## Effects

| Effect | Meaning | Added by |
|---|---|---|
| `network` | Contacts a package index or another remote host | `install`, `download`, `wheel`, `lock`, `index versions`, `search`, `list -o`/`-u` |
| `install_packages` | Installs, upgrades, or reinstalls packages | `install`; removed by `--dry-run` |
| `remove_packages` | Uninstalls packages | `uninstall` |
| `run_build_backend` | May build a project or source distribution, which runs that project's code | `install`, `download`, `wheel`, `lock` |
| `run_vcs` | Runs git, hg, svn, or bzr | a requirement or `-e` value that holds `+` and later `:`, such as `git+https://...`, `pkg @ git+https://...`, `GIT+ssh://...`, or `bzr+lp:...` (case of the scheme does not matter) |
| `override_index` | Uses a package source that the command line names | `-i`/`--index-url`, `--extra-index-url`, `-f`/`--find-links`, `search -i`, and a requirement or `-e` value that is a URL (`://`), a VCS URL, or an archive (`.whl`, `.tar.gz`, `.tgz`, `.tar.bz2`, `.tar.xz`, `.zip`) |
| `opaque_input` | Reads requirements or pip options from a file the grammar cannot see | `-r`, `-c`, `--build-constraint`, `--requirements-from-script`, `--group` |
| `write_file` | Writes a file or directory at a path the line names | `install --report <file>` (not `-`, and not removed by `--dry-run`), `download -d`, `wheel -w`, `lock -o <file>` (not `-`) |
| `disable_tls_verification` | Trusts a host without valid HTTPS | `--trusted-host` |
| `override_tls_trust` | Replaces the CA bundle | `--cert` |
| `override_proxy` | Sends traffic through a named proxy | `--proxy` |
| `write_outside_env` | Installs outside the active environment | `--user`, `-t`/`--target`, `--prefix`, `--root`; removed by `--dry-run` |
| `break_system_packages` | Modifies an externally managed (PEP 668) Python | `--break-system-packages`; removed by `--dry-run` on `install` |
| `other_interpreter` | Runs pip under another Python, against its environment | `--python` |
| `override_config` | Changes a pip configuration file | `config set`, `config unset`, `config edit` |
| `run_program` | Runs an editor | `config edit` |
| `delete_cache` | Deletes files from pip's cache | `cache remove`, `cache purge` |
| `skip_prompt` | Skips the uninstall confirmation | `uninstall -y` |

`--dry-run` installs nothing, but pip still resolves, downloads, and builds source distributions
to read their metadata. So it keeps `network` and `run_build_backend`.

## Example rules

```cedar
// Let the agent use pip.
@id("pip_actions")
permit (principal, action in Tool::pip::Action::"*", resource);

// Never modify an externally managed Python.
@id("pip_no_system_break")
@description("Modifying an externally managed Python is not allowed.")
forbid (principal, action in Tool::pip::Action::"*", resource)
when { context.input.effects.contains(Tool::pip::Effect::"break_system_packages") };

// Install only from the default index, over verified TLS. A requirements file can set its own
// index and trusted hosts, so this rule refuses it too.
@id("pip_default_index")
@description("Use the default package index.")
forbid (principal, action in Tool::pip::Action::"*", resource)
when { context.input.effects.contains(Tool::pip::Effect::"override_index") ||
       context.input.effects.contains(Tool::pip::Effect::"opaque_input") ||
       context.input.effects.contains(Tool::pip::Effect::"disable_tls_verification") ||
       context.input.effects.contains(Tool::pip::Effect::"override_tls_trust") };

// Install only into the active environment.
@id("pip_stay_in_env")
@description("Install only into the active environment.")
forbid (principal, action == Tool::pip::Action::"install", resource)
when { context.input.effects.contains(Tool::pip::Effect::"write_outside_env") };

// No uninstall without the prompt.
@id("pip_uninstall_prompt")
@description("Uninstall asks first.")
forbid (principal, action == Tool::pip::Action::"uninstall", resource)
when { context.input.effects.contains(Tool::pip::Effect::"skip_prompt") };
```

## Deliberately unmodeled

A line that uses any of these is `unmodeled`, and only a rule that names
`Tool::pip::Action::"unmodeled"` permits it.

- `--log`, `--log-file`, `--local-log`: write a log file at a named path.
- `--keyring-provider`: credential lookup, which can run the `keyring` program.
- `--client-cert`: a file that holds a private key.
- `--exists-action`: can wipe or back up existing paths.
- `--use-feature`, `--use-deprecated`: change behaviour in ways the grammar does not describe.
- `-h`/`--help`, `-V`/`--version`, and a bare `pip`.
- A prefix of a long option, such as `--upgr`. pip accepts a unique prefix; the grammar reads only
  full spellings.
- An option that pip stores with "last one wins" (for example `-i`, `--target`, `--timeout`),
  given twice.
- A command option between the command words of `cache`, `config`, or `index`, such as
  `pip config --user set ...`. Write `pip config set --user ...` instead.
- `--editor` on any `config` subcommand except `edit`, and `--format` on any `cache` subcommand
  except `list`. pip accepts and ignores them there.

## Known limits

- **The command line is not the whole input.** `PIP_*` environment variables and pip
  configuration files can set any option, including `PIP_INDEX_URL`, `PIP_TRUSTED_HOST`,
  `PIP_BREAK_SYSTEM_PACKAGES`, `PIP_TARGET`, and `PIP_USER`. The grammar does not see them.
  Control the agent's environment and configuration files, or pass `--isolated`.
- **Requirements files are opaque.** A `-r` or `-c` file can hold index options, `--trusted-host`,
  `-e`, VCS URLs, binary options, and nested `-r` files. The grammar sees only the file name, and
  marks the line with `opaque_input`. A rule that restricts sources, TLS, or VCS must also refuse
  `opaque_input`, as the example rule does.
- **Package sources are matched by pattern.** `override_index` and `run_vcs` on a requirement are
  found by its spelling. A local project directory (`.`, `./proj`) adds neither; it adds
  `run_build_backend` only. Patterns over-match on purpose: any value with `+` and later `:` is
  read as a VCS URL.
- **Other written paths.** `--src` (editable checkouts), `--cache-dir`, and the default outputs of
  `download`, `wheel`, and `lock` in the current directory carry no `write_file` effect.
- **`run_build_backend` is always on for install, download, wheel, and lock.** pip may build any
  source distribution it selects, and `--only-binary :all:` does not stop a local path, an `-e`
  project, a VCS URL, or a requirements file entry from building. A rule can still read the
  `only_binary` field.
- **`network` is always on for install, download, wheel, and lock.** `--no-index` does not remove
  it, because `-f`, a URL requirement, or a requirements file can still fetch.
- **The weekly self version check.** `install`, `download`, `wheel`, `lock`, `list`, and `index`
  may contact PyPI once a week unless `--disable-pip-version-check` or `--no-index` is given.
  Plain `list` has no `network` effect for this.
- **Child processes are not decided by Box.** Build backends, VCS programs, the `config edit`
  editor, and the interpreter that `--python` names run inside the tool's own sandbox.
- **A value is accepted as typed.** The grammar does not check that a value is one pip accepts
  (for example a `--format` choice); pip refuses a bad value itself.
