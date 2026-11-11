# gws (Google Workspace CLI)

A tool grammar for [`gws`](https://github.com/googleworkspace/cli), the Google Workspace CLI. It
lets a policy tell Drive, Gmail, Calendar, Sheets, and Docs reads apart from writes, deletes,
sending mail, and sharing.

| | |
|---|---|
| Executable | `gws`, a native Rust binary |
| Version checked | gws 0.22.5 (tag `v0.22.5`, commit `705fb0ec`) |
| Discovery revisions checked | drive v3 `20261106`, gmail v1 `20261106`, calendar v3 `20261109`, sheets v4 `20261109`, docs v1 `20261106` |

gws builds its commands at run time from Google's public Discovery documents. Google can add or
remove a method without a new gws release. A new method is unmodeled here until the grammar adds
it.

## Install the CLI

Download the archive for your platform from the
[v0.22.5 release](https://github.com/googleworkspace/cli/releases/tag/v0.22.5), extract it, and
note the path of the `gws` binary. The gws README also lists Homebrew
(`brew install googleworkspace-cli`). Restart the box after an upgrade, because Box refuses a
program file that changes while the box runs.

Avoid the npm package for a box. Its `gws` is a Node script (`run.js`) that starts the binary, so the
tool needs `node` in its filesystem grants and the binding is to the script.

## Load the grammar

`./scripts/render.sh gws --command /path/to/gws` prints the full tables. The shape is:

```toml
[experimental-features]
tool-grammars = true

[tool.gws]
command = ["/path/to/gws"]

[tool.gws.grammar]
format = 1
version = 1
name = "gws"
program = "gws"
# ... the rest of gws.grammar.toml, nested under [tool.gws.grammar]
```

The tool also needs what gws needs at run time: its configuration directory (default
`~/.config/gws`, which holds the credentials, the token cache, and a Discovery cache) and network
access to `*.googleapis.com`. Grant those in the tool's own sections. This page covers only the
grammar.

## Supported commands

Every method takes `--params <JSON>`, `-o`/`--output <PATH>`, `--format <FMT>`, `--dry-run`,
`--page-all`, `--page-limit <N>`, and `--page-delay <MS>` after the method name. A method that has a
request body also takes `--json <JSON>`. A method that supports media upload also takes
`--upload <PATH>` and `--upload-content-type <MIME>`.

| Family | Methods | Effects |
|---|---|---|
| `drive files` | `list`, `get`, `export`, `download` | `read_data` |
| | `copy`, `create`, `update` | `write_data`, plus `share_external` when the body names `parents` or `inherit` (or update's `--params` names `parents`, as in `addParents`), and `change_sharing_rules` when the body names `writers`, `requires`, or `download` |
| | `delete` | `delete_data` |
| `drive permissions` | `list`, `get` | `read_data` |
| | `create` | `share_external`, `send_email`, plus `make_public` when the body may name `anyone` |
| | `update` | `share_external`, `make_public`, plus `send_email` when `--params` names `transfer` (`transferOwnership`) |
| | `delete` | `delete_data` |
| `drive drives`, `comments`, `replies`, `revisions` | `list`, `get` / `create`, `update`, `hide`, `unhide` / `delete` | `read_data` / `write_data` / `delete_data` |
| | `drives create`, `drives update` | `write_data`, plus `change_sharing_rules` when the body names `restrict` (`restrictions`) |
| | `revisions update` | `write_data`, plus `make_public` and `share_external` when the body names `publish` (such as `published`) |
| `drive about get`, `drive changes list` | | `read_data` |
| `gmail users messages` | `list`, `get`, `attachments get` | `read_data` |
| | `send` | `send_email` |
| | `modify`, `import`, `insert`, `untrash` | `write_data`; `modify` also `trash_data` when the body names `trash` |
| | `trash` | `trash_data` |
| | `delete` | `delete_data` |
| `gmail users drafts` | `list`, `get` / `create`, `update` / `send` / `delete` | `read_data` / `write_data` / `send_email` / `delete_data` |
| `gmail users threads` | `list`, `get` / `modify`, `untrash` / `trash` / `delete` | `read_data` / `write_data` (`modify` as for messages) / `trash_data` / `delete_data` |
| `gmail users labels` | `list`, `get` / `create`, `patch`, `update` / `delete` | `read_data` / `write_data` / `delete_data` |
| `gmail users history list`, `gmail users settings filters list`, `get` | | `read_data` |
| `calendar events` | `list`, `get`, `instances` | `read_data` |
| | `insert`, `patch`, `update`, `move`, `import` | `write_data`, plus `send_email` (not on `import`) when `--params` names `sendUpdates` or `sendNotifications`; `move` always adds `share_external` |
| | `delete` | `delete_data`, plus `send_email` as above |
| `calendar calendars` | `get` / `insert`, `patch`, `update` / `clear`, `delete` | `read_data` / `write_data` / `delete_data` |
| `calendar acl` | `list`, `get` / `insert`, `patch`, `update` / `delete` | `read_data` / `share_external`, `make_public`, `send_email` / `delete_data` |
| `calendar freebusy query`, `colors get`, `settings list`, `get` | | `read_data` |
| `sheets spreadsheets` | `get` / `create` | `read_data` / `write_data` |
| `sheets spreadsheets values` | `get` / `append`, `update` / `clear` | `read_data` / `write_data` / `delete_data` |
| `docs documents` | `get` / `create` | `read_data` / `write_data` |
| `gws auth status` | | `read_credentials` |
| `gws schema <service.resource.method>` | `--resolve-refs` | none |

Each action is the command words joined with `_`, such as `drive_permissions_create` or
`gmail_users_messages_send`.

## Effects

| Effect | Meaning |
|---|---|
| `read_data` | Reads data from the user's Workspace account. |
| `write_data` | Creates or changes a file, message, label, event, calendar, sheet, or document. |
| `delete_data` | Deletes for good, or clears: a file, message, thread, draft, label, event, calendar's events, sheet range, permission, or ACL rule. |
| `trash_data` | Moves a Gmail message or thread to the trash, where it can be restored. |
| `send_email` | Sends a message or a draft, or a notification that Google sends for the agent: a Drive share (on by default), a calendar ACL change (on by default), or an event change that `--params` asks for. |
| `share_external` | Grants or changes access for another user, group, domain, or anyone, publishes a revision, gives a file a folder's audience (`parents`, or turning inherited permissions back on), or moves an event to a calendar with its own audience. A whole-domain share is `share_external` only, not `make_public`. The grammar cannot tell your own domain from another one. |
| `make_public` | Can grant access to anyone. See the limits below for how it is decided. |
| `change_sharing_rules` | Changes who may reshare or copy a file (`writersCanShare`, `copyRequiresWriterPermission`, `downloadRestrictions`) or a shared drive's sharing limits (`restrictions`). It grants no access itself. |
| `upload_file` | Sends a local file's content to Google (`--upload`). |
| `write_local_file` | Writes the response to a local file (`-o`, `--output`). |
| `read_credentials` | Reads the stored credentials and asks Google which account they belong to. |

`--dry-run` removes every effect. gws then builds the request and prints it without sending it to
the API. It still loads the credentials and can refresh the access token.

## Example policy rules

```cedar
// The agent may use every modeled gws command...
@id("gws_actions")
permit (principal, action in Tool::gws::Action::"*", resource);

// ...but not send mail.
@id("no_send_email")
@description("The agent may not send email.")
forbid (principal, action in Tool::gws::Action::"*", resource)
when { context.input.effects.contains(Tool::gws::Effect::"send_email") };

// ...and not make anything public.
@id("no_public_share")
@description("The agent may not make a file or calendar public.")
forbid (principal, action in Tool::gws::Action::"*", resource)
when { context.input.effects.contains(Tool::gws::Effect::"make_public") };

// ...and not delete for good. Trash is still allowed.
@id("no_delete")
@description("The agent may not delete Workspace data.")
forbid (principal, action in Tool::gws::Action::"*", resource)
when { context.input.effects.contains(Tool::gws::Effect::"delete_data") };

// A read-only agent: in a policy of its own, permit a gws command only when every effect it
// has is a read. The dry-run case, with no effect, is permitted too.
@id("gws_read_only")
permit (principal, action in Tool::gws::Action::"*", resource)
when {
  [Tool::gws::Effect::"read_data", Tool::gws::Effect::"write_local_file"]
    .containsAll(context.input.effects)
};
```

## Exclusions

These lines are unmodeled, so a policy refuses them unless it permits `unmodeled`:

- **Helper commands** such as `gmail +send`, `+reply`, `+forward`, `drive +upload`,
  `sheets +append`, `docs +write`, `calendar +agenda`, and every `workflow` helper. A command word
  cannot start with `+`. The generic method each helper wraps is modeled.
- **camelCase methods and resources**, such as `drive files emptyTrash`, `gmail users getProfile`,
  `gmail users messages batchDelete`, `calendar calendarList`, `calendar events quickAdd`,
  `sheets spreadsheets batchUpdate`, `sheets spreadsheets values batchGet`, and
  `docs documents batchUpdate`. A command word is lowercase, and gws does not accept a lowercase
  spelling of these names.
- **`--api-version` and `<service>:<version>`.** They switch the API version, which changes what a
  method name means.
- **`--sanitize`**, which sends responses through a Model Armor template.
- **Root flags before or between the command words**, such as `gws --dry-run drive files list`.
  gws accepts them there; the grammar reads them only after the method.
- **`watch` methods**, which register a push channel to a URL, and Gmail `users watch` and
  `users stop`.
- **Gmail settings that route mail**: `settings filters create` and `delete`, delegates,
  forwarding addresses, and send-as addresses.
- **`gws auth login`, `logout`, `setup`, and `export`**: they change or print credentials. `setup`
  also runs `gcloud`.
- **Every other service**: admin-reports, slides, tasks, people, chat, classroom, forms, keep, meet,
  events, modelarmor, workflow, and script.

## Known limits

- **The JSON is opaque.** `--params` and `--json` are single string fields. A rule that needs the
  file ID, the recipient, or the query must match the string with `like`, and must allow for any
  key order, spacing, and JSON `\u` escapes.
- **`make_public` on Drive covers permissions and publishing only.** `drive permissions create`
  adds it when the `--json` body contains `anyone` in any letter case, or any `\u` escape; this
  also flags a body such as `"emailAddress":"anyone@example.com"`. `permissions update` always adds
  it, because it can widen an existing `anyone` permission. `revisions update` adds it when the
  body contains `publish` in any letter case, or any `\u`. It does **not** catch a file that becomes
  public because it is created, copied, or moved into a folder or shared drive that is already
  shared with anyone, or that turns inherited permissions back on
  (`inheritedPermissionsDisabled: false`): the grammar cannot see a folder's sharing. Such a line
  has `share_external` (the `parents` and `inherit` checks), so forbid `share_external` if that
  matters.
- **An ownership transfer** (`permissions update` with `transferOwnership` in `--params`) adds
  `send_email`, because Google can notify the new owner. This is not verified against a live
  account.
- **A whole-domain share** (`type: domain`) is `share_external` only, not `make_public`.
- **`send_email` on Drive shares is always added.** `sendNotificationEmail` defaults to true for a
  user or group, and `emailMessage` carries any text. A `false` in `--params` cannot be proven with
  `like`, because a later duplicate key overrides it.
- **`make_public` on Calendar is always added** to an ACL write, because the public scope
  `default` is also the scope a rule gets when its body names none.
- **`send_email` on Calendar** is always added to an ACL insert, patch, or update, because
  `sendNotifications` defaults to true there. On an event write it is added when `--params` names
  `sendUpdates`, `sendNotifications`, `send_updates`, or `send_notifications`, whatever the value,
  or holds a `\u` escape. Google states that some emails can still be sent without them.
- **`share_external` covers every share.** The grammar cannot tell an address in your own domain
  from one outside it.
- **Drive trash is a write.** `files update --json '{"trashed":true}'` moves a file to the trash
  and is `write_data`. Gmail `modify` with the `TRASH` label is `trash_data`, because the body
  names `trash`.
- **The `like` checks over-flag.** Each one is a substring test over every letter case of its
  word, plus any `\u` escape, so it also fires on unrelated text that contains the word.
- **`-o=PATH`** is accepted by gws but unmodeled here; use `-o PATH`, `-oPATH`, or `--output=PATH`.
- **Which account is used** depends on environment variables (`GOOGLE_WORKSPACE_CLI_TOKEN`,
  `GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE`, `GOOGLE_WORKSPACE_CLI_CONFIG_DIR`), on a `.env` file
  that gws loads from the working directory or a parent, and on the files in its configuration
  directory. The grammar sees none of them.
- **`gws schema --resolve-refs <path>`** reads the flag as the path in gws and fails. The grammar
  reads the path correctly, so the decision can differ from what gws does, but gws makes no
  request.

## Regenerate

`gws.grammar.toml` is generated: from this directory, run `python3 -I gen/gen_grammar.py > gws.grammar.toml`.
