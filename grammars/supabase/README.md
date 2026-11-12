# Supabase CLI grammar

A Strands Box tool grammar for the [Supabase CLI](https://github.com/supabase/cli). It lets a
policy tell local work (the local stack, the local database, files in the project) apart from
changes to a hosted Supabase project.

| | |
|---|---|
| Executable | `supabase`, a native single-file binary |
| Version checked | 3.1.0 (tag `v3.1.0`), from `--help` output and the command sources at that tag |
| Grammar name and namespace | `supabase`, `Tool::supabase` |

## Install the CLI

Follow the [official install guide](https://supabase.com/docs/guides/local-development/cli/getting-started):
`brew install supabase/tap/supabase` on macOS, or download the release archive for your platform
from the [releases page](https://github.com/supabase/cli/releases) and put the `supabase` binary on
your `PATH`.

The npm package `supabase` is a shim. `npx supabase ...` is a spawn of `npx`, not of `supabase`, so
this grammar does not see it. Point the box at the native binary.

## Load the grammar

Nest the grammar file under `[tool.<label>.grammar]`. `./scripts/render.sh supabase --label supabase
--command <path>` prints the full table. The top of it:

```toml
[experimental-features]
tool-grammars = true

[tool.supabase]
command = ["/opt/homebrew/bin/supabase"]   # the binary, or a link to it whose name is `supabase`

[tool.supabase.grammar]
format = 1
version = 1
name = "supabase"
program = "supabase"
# ... [tool.supabase.grammar.effects], [tool.supabase.grammar.global], and the
# [tool.supabase.grammar.shell.*] tables from supabase.grammar.toml
```

`brew upgrade` replaces the file, so restart the box after an upgrade. The CLI also needs the
filesystem, Docker, and network access of its own `[tool]` table; this grammar does not grant any.

## Supported commands

| Family | Actions |
|---|---|
| Project | `init`, `start`, `stop`, `status`, `link`, `unlink` |
| Database | `db diff`, `db dump`, `db lint`, `db pull`, `db push`, `db reset`, `db query`, `db start` |
| Migrations (alias `migrations`) | `migration new`, `list`, `up`, `down`, `repair`, `squash`, `fetch` |
| Code generation | `gen types` |
| Edge Functions | `functions new`, `serve`, `deploy`, `delete`, `list`, `download` |
| Secrets | `secrets list`, `set`, `unset` |
| Projects and orgs | `projects list`, `create`, `delete`, `api-keys`; `orgs list` |
| Preview branches | `branches list`, `get`, `create`, `delete` |
| Storage | `storage ls`, `cp`, `mv`, `rm` |
| Inspect | `inspect report`, and every `inspect db <query>` that `--help` lists (25) |
| Tests | `test db`, `test new` |

Action names join the command words with `_`, with `-` as `_`: `db push` is `db_push`,
`inspect db long-running-queries` is `inspect_db_long_running_queries`.

Global flags are fields of every action except `db_diff`, and the CLI accepts them before,
between, or after the command words: `--workdir`, `--profile`, `--debug`, `--experimental`,
`--network-id`, `--yes`, `-o/--output`, `--output-format`, `--log-level`, `--dns-resolver`,
`--agent`.

### The target: `--remote`

A local-or-remote command acts on the local stack unless the line has `--remote`. Bare `--remote`
is the linked project; `--remote=<ref|branch|url>` names another one. Either form adds the
`remote` effect, and turns `write_local_db` into `write_remote_db` (and `delete_local_data` into
`delete_remote_data`). The `remote` field holds the value: `""` for a bare `--remote`.

A remote-only command (`functions`, `secrets`, `projects`, `orgs`, `branches`, `link`) always has
`remote`. There, `--remote=<ref>` only picks another project.

**A bare `--remote` before a URL or a true-literal is `unmodeled`.** Before it parses, the CLI rewrites a bare
`--remote <word>` to `--remote=<word>` when the word is a database URL or a true-literal. On a
command with an operand, the grammar reads that word as the operand instead, so that operand
makes the line `unmodeled` (see below).

**A line the grammar may misread is `unmodeled`.** A boolean flag in this CLI takes a following
`true`, `false`, `yes`, `no`, `on`, `off`, `1`, `0`, `y`, or `n` as its value, so `functions
deploy --debug false` deploys *every* function, while the grammar sees a function named `false`.
Any operand that is one of those words (or, on a database command, looks like `postgres://...`)
makes the line `unmodeled`, so no permit over `Tool::supabase::Action::"*"` reaches it. You don't
need a rule for it.

## Effects

| Effect | Meaning |
|---|---|
| `remote` | Contacts the hosted platform, or the database URL given to `--remote` |
| `write_local_db` | Changes the local database (schema, data, or migration history), or runs SQL there that can |
| `write_remote_db` | The same, on a hosted database |
| `delete_local_data` | Drops the local database objects, or deletes the local data volumes (`stop --no-backup`) |
| `delete_remote_data` | Drops hosted database objects, or deletes a project, branch, or Edge Function |
| `create_remote` | Creates a hosted project or preview branch, which can cost money |
| `deploy_remote` | Deploys Edge Functions |
| `write_secret` | Sets or unsets Edge Function secrets |
| `write_storage` | Uploads or moves Storage objects; hosted when the line also has `remote` |
| `delete_storage` | Removes Storage objects; hosted when the line also has `remote` |
| `write_files` | Writes, replaces, or deletes local files: in the project directory, or at a path the line names |
| `write_link_config` | Changes which hosted project the directory is linked to |
| `local_stack` | Starts or stops local Docker containers |
| `run_sql` | Runs SQL from the line or from files it names (`db query`, `test db`) |
| `run_program` | Runs another program (`gen types --lang dart` or `swift`) |
| `reveal_secrets` | Prints secret keys or database passwords (`projects api-keys --reveal`, `branches get`, and `status`, which prints the local `service_role` key and database URL) |
| `dump_data` | Dumps table data (`db dump --data-only`) |
| `skip_confirmation` | `--yes`: answers every prompt, including the prompts before hosted changes. On a line with `clear_network_bans` it also lets the CLI clear the project's network bans |
| `clear_network_bans` | A `--remote` database connection. With `--yes` (or `SUPABASE_YES` in the environment), when the connection fails, the CLI may delete every network ban of the project. Each such connection without `--password` also creates a temporary login role through the Management API |

Besides `--remote` (which swaps a local effect for its hosted pair), only `db push --dry-run` removes an effect: it removes the database write. See Known limits for why the other dry-run style flags do not.

## Example rules

```cedar
// Let the agent use every modeled command.
@id("supabase_actions")
permit (principal, action in Tool::supabase::Action::"*", resource);

// Never change a hosted database.
@id("no_hosted_db_writes")
@description("Changing a hosted Supabase database is not allowed.")
forbid (principal, action in Tool::supabase::Action::"*", resource)
when { context.input.effects.contains(Tool::supabase::Effect::"write_remote_db") };

// Never delete hosted data, deploy functions, or change secrets.
@id("no_hosted_changes")
@description("Hosted deletes, deploys, and secret changes need a human.")
forbid (principal, action in Tool::supabase::Action::"*", resource)
when {
  context.input.effects.containsAny([
    Tool::supabase::Effect::"delete_remote_data",
    Tool::supabase::Effect::"deploy_remote",
    Tool::supabase::Effect::"write_secret"
  ])
};

// Do not skip the CLI's own confirmation prompts.
@id("no_yes")
forbid (principal, action in Tool::supabase::Action::"*", resource)
when { context.input.effects.contains(Tool::supabase::Effect::"skip_confirmation") };

// Never let a remote database command clear the project's network bans.
// SUPABASE_YES in the environment also allows it, so keep it out of the box's environment.
@id("no_network_ban_changes")
forbid (principal, action in Tool::supabase::Action::"*", resource)
when {
  context.input.effects.containsAll([
    Tool::supabase::Effect::"clear_network_bans",
    Tool::supabase::Effect::"skip_confirmation"
  ])
};

// Generate types only from the local database.
@id("types_local_only")
forbid (principal, action == Tool::supabase::Action::"gen_types", resource)
when { context.input has remote };
```

## Exclusions

These lines are `unmodeled`, so a policy must permit `unmodeled` by name to run them:

- Command families outside the table: `login`, `logout`, `config`, `backups`, `domains`, `sso`,
  `network-bans`, `network-restrictions`, `postgres-config`, `ssl-enforcement`, `encryption`,
  `vanity-subdomains`, `snippets`, `notebooks`, `seed`, `pull`, `logs`, `services`, `bootstrap`,
  `completion`, `telemetry`, `feedback`, `issue`, `whoami`, `gen signing-key`, `gen bearer-jwt`,
  `db advisors`, `db schema`, `orgs create`, `branches update/pause/unpause`.
- Hidden and deprecated flags: `--linked`, `--local`, `--db-url`, `--project-ref` (except on
  `link`), `--project-id` (on `gen types`), `stop --backup`, `link --password`, and the other
  flags `--help` hides. Hidden commands such as `db test`.
- `db diff --from` and `--to`: each value can name the local database, the migrations, or a hosted
  project, and a pattern cannot tell a branch name from `local`.
- The negated forms that the CLI adds to every boolean flag (`--no-debug`, `--dry-run=false`).
- `--wizard`, `--help`, `--version`, and a bare `supabase`.
- `--remote <word>` with a separate word on a command that takes no operand: the CLI reads it as
  `--remote=<word>`, so the grammar leaves the word over and the line is `unmodeled`.

## Known limits

- **A boolean literal after a boolean flag.** The CLI reads `--dry-run false` (and `true`, `yes`,
  `no`, `on`, `off`, `1`, `0`, `y`, `n`) as the flag's value. The grammar reads the word as an
  operand. On a command with no operand slot the line is `unmodeled`. On one with an operand
  slot, the word lands in that field and makes the line `unmodeled` too. This is also why `secrets unset --dry-run`, `db query --read-only`, and
  `db pull --declarative` remove no effect. The grammar cannot tell which flag took the literal,
  so a real operand named `true` or `n` is also `unmodeled`.
- **`--remote <word>` on a command with operands.** The CLI joins a database URL or a
  true-literal (in any case) to `--remote`. The grammar puts the word in the operand field, and
  that makes the line `unmodeled`. The URL check is the pattern `p*://*` or `P*://*`, so an
  operand such as `select 'p://x'` is also `unmodeled`. A
  branch-shaped word is joined only when there is one operand too many, which the grammar sees as
  `unmodeled`.
- **Network bans and login roles.** A `--remote` database connection without `--password` creates
  a temporary login role, and with `--yes` or `SUPABASE_YES` it may clear every network ban of the
  project. `clear_network_bans` marks every such line; the grammar cannot see `SUPABASE_YES`.
- **Repeated `-s` and `-x`.** The CLI keeps only the first value of a repeated single-value flag
  and splits one value on commas (`-s public,auth`). The grammar records every repeat and does not
  split, so `schema` or `exclude` can hold more values, or fewer split values, than the CLI uses.
- **Stack backend.** With `[experimental] stack = true` in `config.toml` or
  `SUPABASE_EXPERIMENTAL_STACK=1`, `start`, `stop`, `status`, and `functions serve` become the
  CLI's stack commands, with other flags. The grammar models the default Docker backend.
- **Short options.** The CLI splits `-sx` into `-s -x` and takes a short option's value only as
  `-s value` or `-s=value`. The grammar reads `-svalue` (`-fout.sql`, `-j4`) as `-s` with the
  value `value`; the CLI fails on those lines, so nothing runs. `-s=value` is `unmodeled`.
- **What the grammar cannot see.** Environment variables (`SUPABASE_ACCESS_TOKEN`,
  `SUPABASE_PROJECT_ID`, `SUPABASE_YES`, `SUPABASE_WORKDIR`, `SUPABASE_DB_PASSWORD`), the link state
  in `supabase/.temp/`, `supabase/config.toml`, and what the SQL in a migration, query file, or
  test does. A remote-only command with no `--remote` acts on whichever project the directory is
  linked to. Docker containers, `pg_dump`, and other programs that the CLI starts are not decided.
- **`--remote=<url>` that points at the local stack** still adds `remote`.
- **`db diff` takes no global flags** in this grammar, because its own `-o/--output` (a file)
  shares the spelling of the global `-o/--output`.
