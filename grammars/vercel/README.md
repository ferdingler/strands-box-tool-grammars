# vercel

A tool grammar for the [Vercel CLI](https://vercel.com/docs/cli), from
[vercel/vercel](https://github.com/vercel/vercel) (`packages/cli`).

| | |
|---|---|
| Executable | `vercel`, a Node.js script (`dist/vc.js` in the npm package `vercel`) |
| Version checked | Vercel CLI 65.14.0 (npm `vercel@65.14.0`), against `vercel <command> --help` and the published JavaScript CLI in `@vercel/cli-support@65.14.0` |
| Policy namespace | `Tool::vercel` |

The grammar binds the called name `vercel` only. The npm package installs the same script as `vc`
too. `vc` is another name, so this grammar does not decide `vc ...`: Box treats it as a
`shell:spawn` of `vc`. Tell the agent to call `vercel`, and do not put `vc` in the box.

## Install the Vercel CLI

```sh
npm install -g --prefix /path/to/prefix vercel@65.14.0
```

This makes `/path/to/prefix/bin/vercel`, a link to
`/path/to/prefix/lib/node_modules/vercel/dist/vc.js`.

## Load the grammar

`vc.js` starts with `#!/usr/bin/env node`, and it runs a native `vercel` binary from the optional
package `@vercel/vc-native-<platform>` (or the JavaScript CLI in `@vercel/cli-support`) as its child.
Point `command` at the link, so that its last component is `vercel`:

```sh
./scripts/render.sh vercel --command /path/to/prefix/bin/vercel
```

```toml
[experimental-features]
tool-grammars = true

[tool.vercel]
command = ["/path/to/prefix/bin/vercel"]

[tool.vercel.filesystem]
read      = ["/path/to/prefix/lib/node_modules"]      # vc.js, cli-support, and the native binary
read_file = ["/usr/bin/env", "/path/to/node/bin/node"] # the shebang chain, on Linux
write     = ["/path/to/home/.local/share/com.vercel.cli"]  # auth.json, config.json, telemetry

[tool.vercel.grammar]
format = 1
version = 1
name = "vercel"
program = "vercel"
# ... [tool.vercel.grammar.effects] and [tool.vercel.grammar.shell.*] from vercel.grammar.toml
```

On Linux, Box refuses the tool unless its filesystem lists cover each interpreter in the shebang
chain: `env` and the `node` that `env` finds. The global configuration directory is
`~/.local/share/com.vercel.cli` on Linux and `~/Library/Application Support/com.vercel.cli` on
macOS. The CLI reads the login token there and writes its config and telemetry files. When the
native binary is missing, the launcher downloads it once into the CLI cache, so either install the
optional package or let the tool write its cache. The commands that build or deploy also need to
read the project directory, and `build`, `dev`, `pull`, `link`, and `env pull` write into it. Restart
the box after you upgrade the CLI.

## Supported commands

Every action takes the global options before, between, or after the command words, as the CLI does:
`--cwd`, `-S`/`--scope`, `-t`/`--token`, `-A`/`--local-config`, `-Q`/`--global-config`,
`-d`/`--debug`, `--no-color`, and `--non-interactive`. `--cwd` is the field `cwd_option`.

| Family | Actions | Effects the action always has |
|---|---|---|
| Deploy | `deploy`, `deploy_init`, `deploy_continue`, `redeploy` | `deploy`, `deploy_production`, `change_traffic` (see below) |
| Deploy artifacts | `deploy_describe` | `read_remote`, `write_local_files` |
| Production traffic | `promote`, `rollback` | `change_traffic` |
| Status | `promote_status`, `rollback_status` | `read_remote` |
| Delete deployments | `remove` (`rm`) | `delete_remote` |
| Read deployments | `list` (`ls`), `inspect`, `logs` (`log`), `logs_runtime`, `logs_requests` | `read_remote` |
| Environment Variables | `env_list` (`env ls`), `env_add`, `env_update`, `env_remove` (`env rm`), `env_pull`, `env_run` | `read_remote`; `write_secret`; `write_secret`, `production_env`; `delete_remote`, `production_env`; `read_secret`, `write_local_files`; `run_local_code`, `read_secret` |
| Local project | `pull`, `build`, `dev` (`develop`), `link`, `link_add` | `read_secret`, `write_local_files`; `build` and `dev` add `run_local_code`; `dev` adds `listen`; `link` writes remote |
| Git | `git_connect`, `git_disconnect` | `write_remote` |
| Aliases | `alias_list`, `alias_set`, `alias_remove` (and the spellings `aliases`, `ln`) | `read_remote`; `write_remote`, `change_traffic`; `delete_remote`, `change_traffic` |
| Domains | `domains_list`, `domains_inspect`, `domains_add`, `domains_remove` (and `domain`) | `read_remote`; `write_remote`; `delete_remote`, `change_traffic` |
| Projects | `project_list`, `project_inspect`, `project_create`, `project_delete` (and `projects`) | `read_remote`; `write_remote`; `delete_remote` |
| Certificates | `certs_list`, `certs_add`, `certs_issue`, `certs_delete` (and `cert`) | `read_remote`; `write_remote`; `delete_remote` |
| Account | `whoami`, `teams_list`, `teams_switch` (and `vercel switch`) | `read_remote`; `write_local_config` |

`vercel alias <deployment> <alias>` is `alias_set`, and `vercel domains` is `domains_list`, because
those are the CLI's default subcommands.

### Production

A deployment without an explicit target can still go to production: the CLI sends a project's
first deployment, and each `--temporary` deployment, to production, and `redeploy` keeps the
original deployment's environment. So `deploy`, `deploy_init`, `deploy_continue`, and `redeploy`
always have `deploy_production` and `change_traffic`, unless `--environment preview` (`-e preview`
on `redeploy`) names the preview target. The CLI ignores `--prod` when `--environment` is set, and
the grammar does the same. A custom environment name keeps the production effects, because the
grammar cannot tell that it is not production. `--skip-domain` removes `change_traffic`, and `--dry`
removes all three.

## Effects

| Effect | Meaning | Added by |
|---|---|---|
| `read_remote` | Reads from the Vercel API and changes nothing | each list, inspect, logs, and status action, `deploy describe`, and `whoami` (not `--cached`) |
| `deploy` | Creates a deployment | `deploy`, `deploy init`, `deploy continue`, `redeploy`; removed by `--dry` |
| `deploy_production` | Can create a production deployment | as above; removed by `--environment preview` |
| `change_traffic` | Changes which deployment a production domain or alias serves | the deploy actions, `promote`, `rollback`, `alias set`, `alias rm`, `domains rm`, `domains add` with a project, `--force`, or `--redirect` |
| `write_remote` | Creates or changes a Vercel resource | `link`, `git`, `alias set`, `domains add`, `project create`, `certs add`/`issue`, `deploy --create-if-missing`/`--verify`, `pull -y` |
| `delete_remote` | Deletes a Vercel resource | `remove`, `env rm`, `alias rm`, `domains rm`, `project delete`, `certs delete` |
| `write_secret` | Sets an Environment Variable value | `env add`, `env update` |
| `read_secret` | Reads decrypted Environment Variable values | `env pull`, `env run`, `env ls --json`, `pull`, `build`, `dev` |
| `production_env` | Acts on production Environment Variables | `-e` naming `production` on `env add`/`pull`/`run`, `pull`, `build`, and `build --prod`; always on `env update`, and on `env rm` without `-e preview` or `-e development` |
| `write_local_files` | Writes files in the project directory | `pull`, `env pull`, `build`, `link`, `deploy --temporary`, `deploy describe` |
| `run_local_code` | Runs project code or a named command on this machine | `build`, `dev`, `env run`, `deploy --temporary` |
| `listen` | Starts a local server on a network port | `dev` |
| `write_local_config` | Changes the saved current team | `teams switch`, `switch` |
| `skip_prompt` | Skips a confirmation prompt | `-y`/`--yes`, `project delete --confirm-name` |
| `token_argument` | Passes a login token on the command line | `-t`/`--token` |
| `override_config` | Reads CLI configuration from a named path | `-A`/`--local-config`, `-Q`/`--global-config` |

## Example rules

```cedar
// Let the agent use the Vercel CLI.
@id("vercel_actions")
permit (principal, action in Tool::vercel::Action::"*", resource);

// Production needs a person: no production deployment, promote, rollback, or alias change.
@id("vercel_no_production")
@description("Production deployments and production traffic changes need a person.")
forbid (principal, action in Tool::vercel::Action::"*", resource)
when { context.input.effects.contains(Tool::vercel::Effect::"deploy_production") ||
       context.input.effects.contains(Tool::vercel::Effect::"change_traffic") };

// Never delete Vercel resources.
@id("vercel_no_delete")
@description("Deleting Vercel resources is not allowed.")
forbid (principal, action in Tool::vercel::Action::"*", resource)
when { context.input.effects.contains(Tool::vercel::Effect::"delete_remote") };

// Keep decrypted secrets off this machine, and do not change production variables.
@id("vercel_no_secrets")
@description("Reading secrets and changing production variables is not allowed.")
forbid (principal, action in Tool::vercel::Action::"*", resource)
when { context.input.effects.contains(Tool::vercel::Effect::"read_secret") ||
       context.input.effects.contains(Tool::vercel::Effect::"production_env") };

// Work only in one team.
@id("vercel_one_team")
@description("Use the acme team.")
forbid (principal, action in Tool::vercel::Action::"*", resource)
when { context.input has scope && context.input.scope != "acme" };
```

The last rule sees only `--scope`. The team also comes from `.vercel/project.json`, the saved
current team, and `VERCEL_ORG_ID`, which the grammar cannot see.

## Exclusions

Each of these is `unmodeled`, so only a rule that permits `unmodeled` lets it run.

- `vercel` with no command, and `vercel <path>`: both deploy, but a grammar needs a command word.
  Use `vercel deploy [<path>]`.
- `-h`/`--help`, `-v`/`--version`, `help`, `--changelog`, the hidden `-T`/`--team` and `link --team`,
  and `--api`, which sends every request, with the login token, to another API URL.
- Deprecated or hidden options: `deploy -e`/`-b` (short forms of `--env`/`--build-env`), `--target`,
  `--format`/`-F`, `--confirm`/`-c`, `list --prod`, `pull --prod`, `remove --hard`, `dev -p`/`--port`,
  `dev --tunnel`, `logs -f`/`--follow`, `env add`/`env update --visibility`, and each deprecated
  single-letter shorthand.
- Legacy positional forms: `env ls <environment> [<branch>]`, `env add <name> <environment>`, and
  `alias set` with one operand (it reads `vercel.json`). `inspect` with the deployment on stdin.
- Bare `rollback` and `promote` (they show the status), bare `project`, `env`, `teams`, and `git`.
- Every other command family: `login`, `logout`, `domains buy`/`renew`/`move`/`transfer-in`, `dns`,
  `blob`, `flags`, `firewall`, `integration`, `api`, `curl`, `billing`, `tokens`, `cache`, `crons`,
  `rolling-release`, `teams invite`/`members`, `project` subcommands other than the four above, and
  the rest of `vercel --help`. An unknown command runs a `vercel-<name>` extension.

## Known limits

- The grammar decides the command line, not what the CLI reads: `VERCEL_TOKEN`, `VERCEL_ORG_ID`,
  `VERCEL_PROJECT_ID`, `.vercel/project.json`, `vercel.json`, and the global config choose the
  account, team, and project.
- Box does not decide programs that the CLI starts itself: the native binary, project build scripts
  and frameworks (`build`, `dev`, `deploy --temporary`), the command after `env run --`, `git`,
  extensions, and the update check. The effect `run_local_code` marks the commands that run project
  code.
- arg@5, the CLI's parser, does not take a value attached to a short flag. The grammar reads `-Sacme`
  as `--scope acme` and `-ep` as `-e p`, and a value word that starts with `-` as the value. The CLI
  refuses each of these and exits with an error, so nothing runs that the grammar did not show.
- When an option sits between `promote` (or `rollback`) and `status`, the grammar reads `status` as
  the deployment, so the line has `change_traffic`. The CLI runs the read-only status command. The
  grammar overstates the effect here and never understates it.
