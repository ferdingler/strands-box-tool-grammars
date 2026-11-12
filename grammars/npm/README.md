# npm

A Strands Box tool grammar for **npm**, the Node.js package manager
([npm/cli](https://github.com/npm/cli)).

| | |
|---|---|
| Executable | `npm` (`bin/npm-cli.js`, a Node.js script run by `node`) |
| Version checked | npm 12.2.2 (tag `v12.2.2`) on Node.js 26.13.0 |
| Sources | `npm <cmd> --help`, the npm-<cmd>(1) and npm-config(7) man pages that npm 12.2.2 ships, and the v12.2.2 source (`lib/commands/`, `lib/utils/cmd-list.js`, Arborist, nopt 10.0.1) |

## Install npm

npm ships with Node.js. Install Node.js from [nodejs.org](https://nodejs.org/) (or your package
manager), then pin npm if you need this exact version:

```sh
npm install -g npm@12.2.2
```

## Load the grammar

The npm install shape is a link: `<node prefix>/bin/npm` points to
`<node prefix>/lib/node_modules/npm/bin/npm-cli.js`, which starts with `#!/usr/bin/env node`. Point
`command` at the link, so that the bare name `npm` runs that file. On Linux, the tool must also be
able to read each interpreter in the shebang chain: `/usr/bin/env` and the `node` it finds.

```toml
[experimental-features]
tool-grammars = true

[tool.npm]
command = ["/opt/node/bin/npm"]

[tool.npm.filesystem]
read      = ["/opt/node"]          # npm-cli.js, its modules, and the node binary
read_file = ["/usr/bin/env"]       # the shebang interpreter (Linux)
# Add write grants for the project directory and the npm cache (~/.npm) that your agent needs.

[tool.npm.grammar]
# the body of npm.grammar.toml goes here
```

`./scripts/render.sh npm --command /opt/node/bin/npm` prints the full `[tool.npm.grammar]` tables.
npm also needs egress to its registry (`registry.npmjs.org` by default).

## Supported commands

| Family | Actions | Spellings (aliases) |
|---|---|---|
| Install | `install` | `install`, `add`, `i`, `in`, `ins`, `inst`, `insta`, `instal`, `isnt`, `isnta`, `isntal`, `isntall` |
| Clean install | `ci` | `ci`, `clean-install`, `ic`, `install-clean`, `isntall-clean` |
| Remove | `uninstall` | `uninstall`, `unlink`, `remove`, `rm`, `r`, `un` |
| Update | `update` | `update`, `u`, `up`, `upgrade`, `udpate` |
| Tree maintenance | `dedupe`, `prune`, `link` | `dedupe`/`ddp`, `prune`, `link`/`ln` |
| Scripts | `run`, `test`, `start`, `stop`, `restart` | `run`/`run-script`/`rum`/`urn`, `test`/`tst`/`t` |
| Run a package binary | `exec` | `exec`, `x` |
| Read | `ls`, `outdated`, `view` | `ls`/`list`, `outdated`, `view`/`info`/`show`/`v` |
| Audit | `audit`, `audit_fix`, `audit_signatures` | `audit`, `audit fix`, `audit signatures` |
| Package and release | `pack`, `publish`, `version` | `pack`, `publish`, `version`/`verison` |
| Scaffold | `init` | `init`, `create`, `innit` |
| Configuration | `config_get`, `config_list`, `config_set`, `config_delete`, `get`, `set` | `config`/`c` + `get`, `list`/`ls`, `set`, `delete`/`rm`/`del` |
| Cache | `cache_clean`, `cache_verify`, `cache_ls` | `cache clean`/`rm`/`clear`, `cache verify`/`check`, `cache ls` |

Global options on every action, before or after the command: `--registry`, `--userconfig`,
`--globalconfig`, `--prefix`, `--loglevel`, `-s`/`--silent`, `-q`/`--quiet`.

## Effects

| Effect | Meaning |
|---|---|
| `network` | Contacts the registry or another remote host. `--offline` removes it from `install` and `ci`. |
| `modify_node_modules` | Changes the installed package tree (also `init --workspace` and `version <v> --workspace`, unless `--no-workspaces-update`). `--dry-run` removes it; `--package-lock-only` removes it from `install` and `audit fix`. |
| `modify_lockfile` | Writes `package-lock.json`. `--no-package-lock`, `--no-save`, `-g`, and `--dry-run` remove it where npm skips the write. `npm ci` never has it. |
| `modify_package_json` | Writes `package.json`: `install <pkg>`, `uninstall`, `update --save`, `link --save*`, `version <v>`, `init`, `audit fix`. |
| `run_lifecycle_scripts` | May run package.json lifecycle scripts (the project's own, or dependency scripts that npm 12's allowScripts policy approves). `--ignore-scripts` removes it. **`--dry-run` does not remove it** from `install`, `ci`, `pack`, or `publish`, because npm still runs those scripts. |
| `run_program` | Runs a package script or binary: `run`, `test`, `start`, `stop`, `restart`, `exec`, `init <initializer>`. |
| `global_install` | Acts on the global prefix: `-g`/`--global`, and every `npm link`. |
| `bypass_script_policy` | `--allow-scripts` or `--dangerously-allow-all-scripts`: dependency install scripts run that the project did not approve. |
| `override_registry` | `--registry`, or `config set registry ...` / `@scope:registry ...`. |
| `override_config` | `--userconfig`, `--globalconfig`, or a saved config change (`config set`, `config delete`, `set`). |
| `override_prefix` | `--prefix`: acts on another project directory. |
| `publish` | `npm publish`. `--dry-run` removes it (npm still contacts the registry). |
| `make_public` | `npm publish --access public`. |
| `git_commit` | `npm version <v>` commits and tags. `--no-git-tag-version` removes it. |
| `force` | `-f`/`--force`. |
| `delete_cache` | `npm cache clean`. |
| `ambiguous_argv` | A word that npm reads differently from this grammar (see Known limits). Forbid it. |

## Example policy rules

```cedar
// Let the agent use every modeled npm command.
@id("npm_actions")
permit (principal, action in Tool::npm::Action::"*", resource);

// Never publish. --dry-run removes the effect, so a dry run is still allowed.
@id("no_publish")
forbid (principal, action == Tool::npm::Action::"publish", resource)
when { context.input.effects.contains(Tool::npm::Effect::"publish") };

// Installs must not run lifecycle scripts or bypass the allowScripts policy.
@id("no_install_scripts")
forbid (principal, action in [Tool::npm::Action::"install", Tool::npm::Action::"ci",
                              Tool::npm::Action::"update"], resource)
when { context.input.effects.contains(Tool::npm::Effect::"run_lifecycle_scripts") ||
       context.input.effects.contains(Tool::npm::Effect::"bypass_script_policy") };

// No global installs and no other registry.
@id("project_only")
forbid (principal, action in Tool::npm::Action::"*", resource)
when { context.input.effects.contains(Tool::npm::Effect::"global_install") ||
       context.input.effects.contains(Tool::npm::Effect::"override_registry") };

// Refuse every line that npm would read differently from the grammar.
@id("no_ambiguous_argv")
forbid (principal, action in Tool::npm::Action::"*", resource)
when { context.input.effects.contains(Tool::npm::Effect::"ambiguous_argv") };
```

## Exclusions

These are `unmodeled`, so a policy refuses them unless it permits `unmodeled`:

- Account and registry-mutating commands: `login`, `logout`, `adduser`, `token`, `access`, `owner`,
  `team`, `org`, `dist-tag`, `deprecate`, `undeprecate`, `unpublish`, `stage`, `trust`, `profile`.
  Each one changes registry state, and none is part of an everyday agent workflow.
- `publish --otp`: a one-time password does not belong on an agent's command line.
- `approve-scripts`, `deny-scripts`, `install-scripts`, `rebuild`, `explore`, `edit`, `pkg`,
  `patch`, `query`, `sbom`, `diff`, `doctor`, `fund`, `search`, `help`, `install-test`,
  `install-ci-test`, `cache add`, `cache npx`, `config edit`, `config fix`.
- Single-letter options that take a value (`-w`, `-C`, `-c`, `-L`, `-m`): use `--workspace`,
  `--prefix`, `--call`, `--location`. npm expands `-wg` into `--workspace --global`, which this
  parser cannot express.
- `--location=global` (another spelling of `-g`), `-v` (npm reads it as `--version`), `--help`/`-h`,
  every `--no-<flag>` the grammar does not declare, and every abbreviated flag (npm 12 refuses those too).
- Command abbreviations and camelCase (`npm pub`, `npm runScript`): npm resolves them, the grammar
  does not.
- Positional script arguments without `--` (`npm test unit`): npm passes them to the script; write
  `npm test -- unit`. Likewise `npm exec eslint --fix` must be `npm exec -- eslint --fix`.

## Known limits

- **Configuration outside argv.** npm reads every setting from `.npmrc` files (project, user,
  global) and from `npm_config_*` environment variables. An `.npmrc` with `ignore-scripts=true`
  removes no effect, and `registry=` there adds no `override_registry`. Effects come from the
  command line only.
- **Package contents.** `run_lifecycle_scripts` and `run_program` mean "may run code that
  package.json or a package names". Those scripts, `exec` binaries, `init` initializers, and git
  (for `version` and git dependencies) run inside the tool's sandbox; the Shell does not decide them.
- **`~/.npm-init.js`.** A bare `npm init` runs the `init-module` file (default `~/.npm-init.js`,
  settable in `.npmrc`) as code. The grammar does not see it.
- **`npx` is a different program** and is not bound by this grammar.
- **A word after a boolean flag.** npm takes `--ignore-scripts false` as "ignore-scripts is
  false". Each flag is `value = "boolean"`, so the grammar reads `true` and `false` the same way.
  A following `yes`, `no`, `1`, `0`, or another casing of `true` or `false` is `unmodeled`, though
  npm reads it as an operand.
- **A value that starts with `-`.** npm gives a String option the empty value when the next word
  looks like a flag, and reads that word as a flag (`--tag --access=public` publishes publicly).
  `--tag` is `value = "optional-next"`, so the grammar reads that line the same way. Each other
  value option adds `ambiguous_argv` when its value starts with `-`.
- **Over-statement.** `pack <spec>` adds `network` also for a local folder; `init <initializer>`
  adds `modify_package_json` though the initializer, not npm, writes it; `init --workspace` and
  `version --workspace` add the reify effects (`network`, `modify_node_modules`, and for init
  `modify_lockfile` and `run_lifecycle_scripts`) also where npm skips the reify (an initializer, or no
  new version); `ls -all` is `--all` to npm but `-a -l -l` here; `uninstall` and `prune`
  add `network` for the audit report even with `--no-audit`.
