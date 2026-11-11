# gh (GitHub CLI)

A Strands Box tool grammar for the [GitHub CLI](https://github.com/cli/cli). It lets a policy see
which `gh` command an agent runs, its flags and operands, and what the command does, such as
merging a pull request, deleting a repository, or writing through `gh api`.

| | |
|---|---|
| Project | GitHub CLI, github.com/cli/cli |
| Executable | `gh`, a native Go binary |
| Version checked | 2.103.3 (tag `v2.103.3`), against its `--help` output and its source |
| Grammar | `gh.grammar.toml`, policy namespace `Tool::gh` |

## Install gh

Use an official release: `brew install gh` on macOS, the release archive from
<https://github.com/cli/cli/releases>, or a package from <https://cli.github.com>. Run
`gh --version` and compare it with the version above. A newer gh may add flags; an added flag is
`unmodeled` until the grammar declares it.

## Load the grammar

`gh` is a native binary, so `command` names the file itself, or a link to it whose name is `gh`
(Homebrew's `/opt/homebrew/bin/gh` is fine). After `brew upgrade gh`, restart the box. Print the
tables with the collection's renderer:

```sh
./scripts/render.sh gh --label gh --command /opt/homebrew/bin/gh
```

It prints this, followed by every action of the grammar:

```toml
[experimental-features]
tool-grammars = true

[tool.gh]
command = ["/opt/homebrew/bin/gh"]

[tool.gh.grammar]
format = 1
version = 1
name = "gh"
program = "gh"
# ... [tool.gh.grammar.effects] and [tool.gh.grammar.shell.*] from gh.grammar.toml
```

gh also needs to read its configuration (`~/.config/gh`, or `GH_CONFIG_DIR`), to reach the GitHub
API, and, for `pr checkout` and `repo clone`, to run `git`. Grant those through the tool's own
filesystem lists and the box's egress settings, as the Box configuration guide describes.

## Supported commands

| Family | Actions |
|---|---|
| `pr` | `list` (`ls`), `view`, `diff`, `checks`, `status`, `checkout` (`co`), `create` (`new`), `comment`, `review`, `merge`, `close`, `reopen`, `edit`, `ready` |
| `issue` | `list` (`ls`), `view`, `status`, `create` (`new`), `comment`, `close`, `reopen`, `edit` |
| `repo` | `view`, `list` (`ls`), `clone`, `create` (`new`), `fork`, `delete`, `archive`, `edit` |
| `run` | `list` (`ls`), `view`, `watch`, `rerun`, `cancel`, `delete`, `download` |
| `workflow` | `list` (`ls`), `view`, `run` |
| `release` | `list` (`ls`), `view`, `create` (`new`), `download`, `delete` |
| `search` | `code`, `commits`, `issues`, `prs`, `repos` |
| `auth` | `status`, `token` |
| `api` | `gh api <endpoint>` |

An action is named by its command words joined with `_`: `pr_merge`, `repo_edit`, `api`. Each flag
is a field named after its long form (`--delete-branch` is `delete_branch`), and each operand is a
field: `pr`, `issue`, `repository`, `tag`, `run_id`, `workflow`, `endpoint`, `query`. `-R/--repo`
is the String field `repo` in every action that has it as a target. In `search`, `-R/--repo` is a
repeated filter, so its field is `repo_filter`, a set.

## Effects

| Effect | Meaning | Added by |
|---|---|---|
| `read_remote` | Reads data from GitHub | Every read, and `gh api` |
| `write_remote` | Creates or changes data on GitHub | Every create, edit, comment, close, and `gh api` with `-f`, `-F`, `--input`, or a `-X` other than GET or HEAD |
| `delete_remote` | Deletes data on GitHub | `repo delete`, `release delete`, `run delete`, `--delete-branch`, `--delete-last`, `gh api -X DELETE` |
| `merge` | Merges a pull request or turns on auto-merge | `pr merge`, except with `--disable-auto` |
| `admin_bypass` | Merges without meeting branch protection or the merge queue | `pr merge --admin` |
| `approve` | Approves a pull request | `pr review --approve` |
| `make_public` | Makes a repository public | `repo create --public`; `repo edit --visibility` with any value but `private` or `internal` |
| `trigger_ci` | Starts or reruns a workflow, which runs with the repository's secrets | `workflow run`, `run rerun` |
| `git_push` | May push local commits or branches | `pr create` (removed by `--head`), `repo create --push` |
| `write_local` | Writes local files, branches, or remotes | `pr checkout`, `repo clone`, downloads, `--clone`, `--delete-branch`, `repo create --source` or `--remote`, `repo fork --remote` |
| `overwrite_local` | Overwrites or resets existing local files or branches | `pr checkout --force`, `release download --clobber` |
| `git_passthrough` | Passes extra arguments to git | Words after `--` in `repo clone` and `repo fork` |
| `upload_file` | Sends a local file's content to GitHub | `--attach`, `--body-file`, `--notes-file`, release assets, `--input`, `-F key=@file` |
| `open_browser` | Opens a web browser | `--web` |
| `target_override` | Names the target repository or host on the command line | `-R/--repo`, `gh api --hostname`, a `gh api` endpoint with `://` |
| `reveal_token` | Prints a stored token | `auth status --show-token`, `auth token` |
| `write_credentials` | May change stored credentials (token refresh) | `auth status` and `auth token`, unless `--no-refresh` |

`--dry-run` on `pr create` removes `write_remote` and `upload_file`, but keeps `git_push`, because
gh says it "may still push git changes". `--web` on a create or comment removes `write_remote`,
because gh then opens the browser and creates nothing.

## Example rules

```cedar
// Let the agent use every modeled gh command.
@id("gh_actions")
permit (principal, action in Tool::gh::Action::"*", resource);

// No merges, and never an admin bypass.
@id("gh_no_merge")
@description("An agent may not merge pull requests.")
forbid (principal, action in Tool::gh::Action::"*", resource)
when { context.input.effects.contains(Tool::gh::Effect::"merge") ||
       context.input.effects.contains(Tool::gh::Effect::"admin_bypass") };

// Nothing is deleted, and no repository becomes public.
@id("gh_no_delete_or_public")
@description("An agent may not delete on GitHub or make a repository public.")
forbid (principal, action in Tool::gh::Action::"*", resource)
when { context.input.effects.contains(Tool::gh::Effect::"delete_remote") ||
       context.input.effects.contains(Tool::gh::Effect::"make_public") };

// gh api is for reads only.
@id("gh_api_read_only")
@description("gh api is read only.")
forbid (principal, action == Tool::gh::Action::"api", resource)
when { context.input.effects.contains(Tool::gh::Effect::"write_remote") };

// Stay in one repository when -R is given.
@id("gh_one_repo")
@description("An agent may only target my-org/my-repo.")
forbid (principal, action in Tool::gh::Action::"*", resource)
when { context.input.effects.contains(Tool::gh::Effect::"target_override") &&
       !(context.input has repo && context.input.repo == "my-org/my-repo") };
```

## Exclusions

Each of these is `unmodeled`, so only a rule that permits `Tool::gh::Action::"unmodeled"` lets it
run.

- The top-level alias `gh co`, and every alias in the gh config, because the operator can redefine
  them, even as shell commands. `gh pr co` is built in and is modeled.
- `gh extension`, and every extension command, because an extension is another program.
- `auth login`, `logout`, `refresh`, `switch`, and `setup-git`, `secret`, `variable`, `ssh-key`,
  `gpg-key`, `codespace`, `config`, `alias`, `cache`, `project`, `gist`, `label`, `ruleset`,
  `attestation`, `org`, `browse`, `status`, `skill`, `copilot`, `agent-task`, and the commands of the
  modeled families that are not in the table above (for example `pr revert`, `issue delete`,
  `repo rename`, `release upload`, `workflow disable`).
- Interactive flags: `--editor` and `--recover`.
- Hidden or deprecated flags, such as `repo create --confirm`; `gh api --verbose`; `--help`;
  `--version`.

## Known limits

- **Flag placement.** gh accepts `-R` before the subcommand (`gh -R o/r pr list`, `gh pr -R o/r
  list`). The grammar accepts it only after the command words; the other forms are `unmodeled`.
- **Value spellings.** gh accepts `-R=o/r`, `--draft=false`, and a single-valued flag given twice
  (the last wins). The grammar makes each of those `unmodeled`. So does `--latest=false` on
  `release create` and `--enable-wiki=false` on `repo edit`.
- **Environment and config.** `GH_REPO` and `GH_HOST` change the target without `-R`, and `GH_TOKEN`
  changes the identity. The grammar cannot see the environment or the gh config.
- **GraphQL.** `gh api graphql -f query=...` is a POST, so it has `write_remote` even when the query
  only reads. A rule that permits GraphQL reads has to permit `write_remote` for that endpoint.
- **`gh api -X`.** Only the exact spellings `GET`/`get` and `HEAD`/`head` count as reads. A
  mixed-case method such as `Get` gets every write effect.
- **Prompts.** On a terminal, `repo edit`, `repo create`, and `pr review` with no flags ask
  questions, and the answers can change visibility or approve. The grammar sees only the command
  line.
- **One name, two types.** A few fields have one name and a different type in different actions,
  because gh's own flags do: `assignee`, `comment`, `comments`, `issue`, `json`, `license`, `name`,
  `owner`, `project`, `remote`, `source`, `template`, and `visibility`. A rule over
  `Tool::gh::Action::"*"` that reads one of them is refused when the box starts. Name the actions
  in such a rule instead.
- **Child processes.** gh runs git (and its hooks), the pager, the browser, and the editor
  itself. Box does not decide those; the effects `write_local`, `git_push`, `git_passthrough`, and
  `open_browser` name the commands that start them.
