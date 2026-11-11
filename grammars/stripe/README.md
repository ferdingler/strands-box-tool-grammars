# Stripe CLI grammar

A Strands Box tool grammar for the [Stripe CLI](https://github.com/stripe/stripe-cli).

| | |
|---|---|
| Executable | `stripe`, a native Go binary |
| Version checked | 1.55.10 (tag `v1.55.10`), against `--help` and the source at that tag |
| Policy namespace | `Tool::stripe` |

## Install the CLI

Download the release archive for your platform from
[github.com/stripe/stripe-cli/releases](https://github.com/stripe/stripe-cli/releases) and unpack
the `stripe` binary, or use `brew install stripe/stripe-cli/stripe`. Log in outside the box
(`stripe login`), or give the box an API key some other way: the grammar does not model `login`.

## Load it in a box

The CLI is a native binary, so `command` names the binary itself. A Homebrew link works too,
because its last component is also `stripe`; restart the box after `brew upgrade`.

```toml
[experimental-features]
tool-grammars = true

[tool.stripe]
command = ["/usr/local/bin/stripe"]

[tool.stripe.filesystem]
read  = ["~/.config/stripe"]   # the config file: keys, profiles, machine ID
write = ["~/.config/stripe"]   # the CLI writes it on `config --set` and when it saves a machine ID

[tool.stripe.grammar]
format = 1
version = 1
name = "stripe"
program = "stripe"
# ... the rest of stripe.grammar.toml, each table nested under [tool.stripe.grammar]
```

Print the complete grammar tables with
`./scripts/render.sh stripe --label stripe --command /usr/local/bin/stripe`, and add the
`[tool.stripe.filesystem]` table above them. Without `read` on `~/.config/stripe` every command
that needs the config fails with `no such file or directory`; without `write`, `config --set`
fails with `read-only file system`. `~/.config/stripe` is a credential store: the tool can read
the test-mode keys in it. On macOS the CLI keeps live-mode keys in the login Keychain; this
snippet was checked on Linux only. The box policy must also permit the tool's outbound requests
(`api.stripe.com`, and the Stripe websocket hosts for `listen` and `logs tail`).

## Supported commands

Every action also takes the root flags `--api-key`, `--color`, `--config`, `--device-name`,
`--log-level`, and `-p`/`--project-name`, before, between, or after the command words.

| Family | Actions | Base effects |
|---|---|---|
| Webhooks | `listen` | `network` |
| | `trigger <event>` | `network`, `write_data`, `move_money` |
| Fixtures | `fixtures <file>` | `network`, `write_data`, `delete_data`, `move_money`, `raw_request`, `write_files` |
| Logs | `logs tail` | `network` |
| Raw API | `get <id or path>` | `network`, `raw_request` |
| | `post <path>` | `network`, `raw_request`, `write_data`, `move_money` |
| | `delete <path>` | `network`, `raw_request`, `delete_data`, `move_money` |
| Reads | `list`, `retrieve`, `search` on `customers`, `charges`, `refunds`, `subscriptions`, `invoices`, `products`, `prices`, `checkout sessions`, `events`; `balance retrieve` | `network` |
| Writes | `create`, `update` on `customers`, `products`, `prices`, `checkout sessions`; `charges update`, `refunds update`, `refunds cancel`, `subscriptions migrate`, `checkout sessions expire`, `events resend` | `network`, `write_data` |
| Money | `charges create`, `charges capture`, `refunds create`, `invoices create`, `invoices update`, `invoices pay`, `subscriptions create`, `subscriptions update`, `subscriptions pause`, `subscriptions resume` | `network`, `write_data`, `move_money` |
| Deletes | `customers delete`, `products delete`, `invoices delete`; `subscriptions cancel` (also `move_money`: it can bill a final invoice) | `network`, `delete_data` |
| Local | `config`, `version`, `whoami` | see effects |

An action name is the command words joined with `_`: `checkout sessions create` is
`checkout_sessions_create`. A resource command declares each request parameter that the CLI
registers as a flag, in the spelling that its help prints (`--address.city`, `--unit-amount`), plus
the shared request flags (`-d`, `-e`, `-i`, `-v`, `-s`, `-c`, `--live`, `--dry-run`,
`--stripe-account`, `--stripe-context`, and on reads `-l`, `-a`, `-b`). Each flag is a field.

## Effects

| Effect | Added by |
|---|---|
| `network` | Every command that calls Stripe, GitHub (`version`), or forwards events. |
| `write_data` | Creates or changes Stripe objects. |
| `delete_data` | Deletes or cancels an object (`delete`, the resource `delete`s, `subscriptions cancel`). |
| `move_money` | A command that can charge, capture, pay, or refund. `post`, `delete`, `trigger`, and `fixtures` always carry it, because the grammar cannot tell which endpoint does what. `invoices create/update` always carry it, because `auto_advance` (a flag or `-d`) lets Stripe collect the invoice; so does `subscriptions pause` (`invoicing_behavior=invoice` bills at once). `refunds cancel` does not: it keeps the money in the account. |
| `live_mode` | `--live`, or an `--api-key` value with a `_live` segment (`sk_live_…`, `rk_live_…`). |
| `api_key_override` | `--api-key`. |
| `select_project` | `-p`/`--project-name`. |
| `override_config` | `--config`, and `config --set`, `--unset`, `--remove-profile`. |
| `credentials` | `config --list` (prints the config file, test keys included), `config --remove-profile`, and `listen --print-secret` (prints the webhook signing secret). |
| `connected_account` | `--stripe-account` and `--stripe-context`. |
| `skip_prompt` | `-c`/`--confirm` on a command that deletes, or on `config --remove-profile`. |
| `raw_request` | `get`, `post`, `delete`, and `fixtures`. |
| `forward_events` | `listen -f`, `-c`, or `-a`; `events resend --webhook-endpoint` or `-d` (it can name the endpoint). |
| `insecure_tls` | `listen --skip-verify`. |
| `write_files` | `fixtures` (it can update `.env` in the working directory). |

`--dry-run` removes `write_data`, `delete_data`, and `move_money`. It keeps `network`, because the
CLI can still refresh its login token.

## Example rules

```cedar
// Let the agent use every modeled command.
permit (principal, action in Tool::stripe::Action::"*", resource);

// Never touch live-mode data.
@id("stripe_no_live")
forbid (principal, action in Tool::stripe::Action::"*", resource)
when { context.input.effects.contains(Tool::stripe::Effect::"live_mode") };

// No charges, captures, payments, or refunds, except as a dry run.
@id("stripe_no_money")
forbid (principal, action in Tool::stripe::Action::"*", resource)
when { context.input.effects.contains(Tool::stripe::Effect::"move_money") };

// No other key, profile, config, or connected account on the command line. This does not see
// STRIPE_API_KEY, which wins over both the login and `--api-key`.
@id("stripe_own_account")
forbid (principal, action in Tool::stripe::Action::"*", resource)
when { context.input.effects.containsAny([
  Tool::stripe::Effect::"api_key_override", Tool::stripe::Effect::"select_project",
  Tool::stripe::Effect::"override_config", Tool::stripe::Effect::"connected_account"]) };

// Forward webhooks only to a local port.
@id("stripe_listen_local")
forbid (principal, action == Tool::stripe::Action::"listen", resource)
when { context.input.effects.contains(Tool::stripe::Effect::"forward_events") &&
       !(context.input has forward_to && context.input.forward_to like "localhost:*") };
```

The last rule is a sketch: `-c` and `-a` also forward, and a `like` pattern over a URL is easy to
get wrong. A rule that forbids `forward_events` outright is safer.

## Left out on purpose (`unmodeled`)

- `login`, `logout`, and `switch`: they change the stored credentials or the active account, which
  changes what every later command means.
- `open`, `docs`, `community`, `feedback`, `completion`, `agent`, `data`, `sandboxes`, `resources`,
  `v2 …`, `help`, `provision`, and every plugin (`apps`, `projects`, `tools`, `pay`, …). Plugins
  and `provision` are other programs that the CLI starts.
- `--edit` on `trigger`, `fixtures`, and `config` (opens an editor), and `trigger --raw` (an inline
  fixture).
- `-H`/`--request-header` on API commands: it can set any header, the account and the
  authorization included.
- The hidden flags `--api-base`, `--access-base`, `--dashboard-base`, `--no-wss`, `--timeout`, and
  the root `--map`, `-h`/`--help`, and `-v`/`--version`.
- Deprecated `listen` flags (`--thin-events`, `--forward-thin-to`, `--forward-thin-connect-to`,
  `-j`/`--print-json`).

## Known limits

- **Names with `_` cannot be modeled.** Box command words allow lowercase letters, digits, and `-`
  only. The CLI keeps the API's `_`, so `payment_intents`, `payment_methods`, `setup_intents`,
  `webhook_endpoints`, `payment_links`, the `test_helpers` groups, and operations such as
  `invoices finalize_invoice` or `customers list_payment_methods` are `unmodeled`. The raw
  `get`/`post`/`delete` commands reach the same endpoints.
- **The bracket spelling of a nested parameter** (`--address[city]=Paris`), which the CLI maps to
  `--address.city`, is `unmodeled`. Use the dotted spelling, or `-d "address[city]=Paris"`.
- **A boolean request parameter with a separate value** (`--validate true`) is `unmodeled`. The CLI
  rewrites it to `--validate=true`; write that, or the bare flag.
- **The mode comes from outside the command line too.** `STRIPE_API_KEY` wins over both the
  stored login and `--api-key`, so `--api-key sk_test_…` on the line does not prove test mode: a
  live key in the environment still makes the command live. A key stored in the config file and
  `stripe switch` also decide the account and mode of a command without `--live`. `live_mode`
  sees only `--live` and an `--api-key` value, so its absence means only that the line did not ask
  for live mode. An OAuth login in live mode refuses a command without `--live`. A sandbox-only box
  must keep live keys out of the tool's environment and config, not rely on this effect alone.
- **`--api-key` values are fields.** A policy decision can read the key, and so can anything that
  records the decision. Prefer a stored login.
- **`move_money` is conservative.** `post`, `delete`, `trigger`, `fixtures`, `invoices
  create/update`, and every subscription change except `migrate` carry it even when a given call
  moves no money, because `-d` can send any request parameter.
- Persistent root flags are `anywhere` globals, so they are accepted between command words, as
  Cobra does. A flag that a command does not declare makes the whole line `unmodeled`.

## Regenerate

From `grammars/stripe/`, with stripe-cli checked out at the release tag: `python3 -I gen/parse_specs.py <stripe-cli>/pkg/cmd/resources/specs_gen.go > /tmp/specs.json && python3 -I gen/gen_grammar.py /tmp/specs.json gen/head.toml > stripe.grammar.toml` (edit `gen/head.toml` for the hand-written commands, `gen/gen_grammar.py` for the resource list and its effects).
