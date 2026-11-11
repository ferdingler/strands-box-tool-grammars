# valyu

A tool grammar for the [Valyu CLI](https://github.com/valyuAI/valyu-cli), the official command line
for the Valyu search, answer, contents, and deep research APIs.

| | |
|---|---|
| Executable | `valyu` |
| Version checked | 1.3.2 (tag `v1.3.2`, commit `9496e7b`), against `--help` of every command and the source |
| Argument parser | commander 14.0.3 |

## Install the CLI

```sh
curl -fsSL https://get.valyu.ai | bash        # native binary (macOS, Linux)
brew install valyuAI/cli/valyu                 # Homebrew
npm install -g @valyu/cli                      # Node.js script (dist/cli.cjs)
```

## Load the grammar

The release binary is a native executable, so `command` names it directly. With Homebrew, name the
link (for example `/opt/homebrew/bin/valyu`) and restart the box after `brew upgrade`. With npm,
name the `bin/valyu` link, and give the tool read access to the `node` that its shebang finds.

```toml
[experimental-features]
tool-grammars = true

[tool.valyu]
command = ["/usr/local/bin/valyu"]

[tool.valyu.grammar]
format = 1
version = 1
name = "valyu"
program = "valyu"
# ... the rest of valyu.grammar.toml, nested under [tool.valyu.grammar]
```

`./scripts/render.sh valyu --command /usr/local/bin/valyu` prints the full tables.

The CLI reads its API key from `VALYU_API_KEY` or `~/.config/valyu/credentials.json`, so the tool
needs one of them.

## Supported commands

| Family | Actions | Effects (always) |
|---|---|---|
| Search | `search` | `network`, `spend_credits` |
| Answer | `answer` | `network`, `spend_credits` |
| Contents | `contents`, `contents jobs` | `contents`: `network`, `spend_credits`; `jobs`: `network` |
| Deep research | `deepresearch create`, `list`, `status`, `watch`, `cancel`, `update`, `respond`, `delete`, `share` | `create`: `spend_credits`; `cancel`: `cancel_task`; `update`, `respond`: `steer_task`; `delete`: `delete_data`; `share`: `share_public` |
| Batch | `batch create`, `add`, `list`, `status`, `tasks`, `watch`, `cancel` | `create`, `add`: `spend_credits`; `cancel`: `cancel_task` |
| Workflows | `workflows list`, `get`, `versions`, `preview`, `run`, `create`, `update`, `delete` | `run`: `spend_credits`; `create`, `update`: `change_workflow`; `delete`: `delete_data` |
| Sources | `sources list` (alias `sources`), `sources categories` | `network` |
| Account | `account whoami`, `balance`, `datasets`, `keys list` (alias `account keys`), `keys create`, `keys revoke`, `keys rotate`, `topup` | `keys create`, `revoke`, `rotate`: `manage_keys`; `topup`: `payment` |
| Status | `whoami`, `doctor` | `network` |

Every action has `network`. The top-level options `--api-key`, `-p/--profile`, `--json`, and
`-q/--quiet` are accepted before, between, and after the command words, as valyu accepts them.

## Effects

| Effect | Means | Added by |
|---|---|---|
| `network` | Contacts the Valyu API, and the npm registry for the update check | every action |
| `spend_credits` | A paid API call | `search`, `answer`, `contents`, `deepresearch create`, `batch create`, `batch add`, `workflows run` |
| `high_cost` | A heavy or max deep research mode | `-m heavy` or `-m max` on `deepresearch create`, `batch create`, `workflows run` |
| `payment` | Charges the card on file or creates a checkout (moves money) | `account topup` |
| `open_browser` | Opens a URL in the system browser | `account topup --open` |
| `manage_keys` | Creates, revokes, or rotates an API key; a new secret goes to stdout | `account keys create`, `revoke`, `rotate` |
| `share_public` | Toggles public access to a report | `deepresearch share` |
| `delete_data` | Deletes a research task or a workflow | `deepresearch delete`, `workflows delete` |
| `cancel_task` | Cancels a running task or batch | `deepresearch cancel`, `batch cancel` |
| `steer_task` | Changes what a running task does | `deepresearch update`, `deepresearch respond` |
| `change_workflow` | Creates or updates an organisation workflow | `workflows create`, `workflows update` |
| `upload_file` | Sends the content of a local file (or stdin) to Valyu | `--file`, `--structured-file`, `--mcp-config`, `--deliverables-file`, `--response-file`, `--tasks-file`, `--params-file`, and `workflows create`/`update --file` |
| `expose_mcp` | Gives the Valyu research agent MCP servers and their tokens | `--mcp-config` |
| `notify_external` | Valyu sends the result to a webhook or an email | `--webhook-url`, `--alert-email` |
| `skip_prompt` | Skips a confirmation prompt | `-y/--yes` on `deepresearch delete`, `workflows delete`, `account topup` |
| `other_account` | Uses a key or profile that the line names | `--api-key`, `-p/--profile` |
| `option_like_value` | A word that valyu can read as an option, not as the field the grammar shows | see Known limits |

The cost knobs are fields, so a rule can read them: `max_price` (`search --max-price`, CPM),
`data_max_price` (`answer`), `max_price_dollars` (`contents`), `limit`, `response_length`, `mode`,
`browser_use`, `code_execution`, `screenshot(s)`, and `extract_effort`.

Valyu writes no output file. Results go to stdout; only the excluded `login` writes a file (the
credentials).

## Example policy rules

```cedar
// Research, but never move money or change keys.
@id("valyu_research")
permit (principal, action in Tool::valyu::Action::"*", resource)
unless {
  context.input.effects.contains(Tool::valyu::Effect::"payment") ||
  context.input.effects.contains(Tool::valyu::Effect::"manage_keys")
};

// No heavy or max deep research.
@id("no_high_cost")
forbid (principal, action in Tool::valyu::Action::"*", resource)
when { context.input.effects.contains(Tool::valyu::Effect::"high_cost") };

// A search must carry a price cap.
@id("search_needs_cap")
forbid (principal, action == Tool::valyu::Action::"search", resource)
unless { context.input has max_price };

// Local files, MCP tokens, and webhooks must not leave the box.
@id("no_exfiltration")
forbid (principal, action in Tool::valyu::Action::"*", resource)
when {
  context.input.effects.contains(Tool::valyu::Effect::"upload_file") ||
  context.input.effects.contains(Tool::valyu::Effect::"expose_mcp") ||
  context.input.effects.contains(Tool::valyu::Effect::"notify_external")
};

// Refuse lines that valyu can read differently from the grammar.
@id("no_ambiguous_words")
forbid (principal, action in Tool::valyu::Action::"*", resource)
when { context.input.effects.contains(Tool::valyu::Effect::"option_like_value") };
```

## Exclusions

These are `unmodeled`, so only a rule that permits `unmodeled` lets them run.

- `login` and `logout`: they mint, store, delete, or revoke credentials, and `login` opens a browser.
- `upgrade`: `--run` runs an install command through a shell.
- `open`: it only starts the system browser.
- `help` subcommands, `-h/--help`, and `-v/--version`.
- `--version <number>` on `workflows get`, `preview`, and `run`: valyu's top-level `-v/--version`
  takes that flag first and prints the CLI version, so the line does not do what it says.
- A non-repeatable value option given twice: valyu keeps the last value.

## Known limits

- **Top-level options inside a value.** valyu reads `--api-key`, `-p/--profile`, `--json`, `-q`, and
  `-v` wherever they appear, even as the value of another option. In
  `valyu search q --include-source -p prod`, valyu uses profile `prod`, while the grammar shows
  `include_source = ["-p"]`. Each such value (one that starts with `--`, `-p`, `-q`, or `-v`) adds
  `option_like_value`.
- **A dropped `--`.** When `--` comes before any subcommand option, valyu removes it before the
  subcommand reads the line, so `valyu contents -- --webhook-url https://x.example https://a.com`
  sets a webhook. The grammar reads the words after `--` as operands. Each operand that starts with
  `-` adds `option_like_value`. A lone `-` operand adds it too.
- **`contents --summary <word>`.** valyu takes the next word as the summary instructions when it does
  not start with `-`. The grammar reads a bare `--summary` as `""` and the next word as a URL. Use
  `--summary=<instructions>` or put `--summary` last.
- **An option before a subcommand word.** `valyu contents --screenshot jobs cj_1` runs `contents jobs`
  in valyu, but the grammar reads it as `contents` with the URLs `jobs` and `cj_1`.
- **Hidden input.** The grammar cannot see `VALYU_API_KEY`, `VALYU_PROFILE`, the credentials file,
  the content of the files that a line names, or stdin, which `search`, `answer`, `contents`, and
  `batch create` read when the line has no query or URL. `workflows run` without `-m` uses the
  template's own mode, which can be heavy or max.
- **`deepresearch share` toggles.** The same line makes a private report public and a public one
  private; the effect is `share_public` either way.
- **Prompts.** valyu asks for confirmation only on a terminal. Without one, `account topup` charges
  without asking, so do not rely on `skip_prompt` to separate prompted and unprompted top-ups.
