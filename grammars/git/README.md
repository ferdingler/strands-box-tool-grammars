# git

A Strands Box tool grammar for [Git](https://git-scm.com). It turns a `git` command line into a
named action, fields, and effects that a policy can permit or forbid.

| | |
|---|---|
| Project | Git, source at git.kernel.org/pub/scm/git/git.git (mirror github.com/git/git) |
| Executable | `git`, a native binary |
| Version checked | 2.56.1 (tag `v2.56.1`) |
| Files | `git.grammar.toml` (the grammar), `git.corpus.toml` (golden cases), `git.e2e.toml` (box cases) |

## Install git

Use your system package manager (`apt install git`, `dnf install git`, `brew install git`), or build
a release from https://git-scm.com/downloads. Check the version with `git --version`. The grammar
was checked against 2.56.1; options added by a later release are `unmodeled` until the grammar
declares them.

## Load the grammar

Tool grammars are an experimental feature. Nest the grammar under `[tool.<label>.grammar]`.
`./scripts/render.sh git --label git --command <path to git>` prints the whole table. Its shape:

```toml
[experimental-features]
tool-grammars = true

[tool.git]
command = ["/usr/bin/git"]          # the git binary itself; its last component must be `git`

[tool.git.grammar]
format = 1
version = 1
name = "git"
program = "git"
# ... the rest of git.grammar.toml, with each table prefixed by `tool.git.grammar.`
```

git is a native binary, so `command` names the binary itself. Box decides only spawns of the name
`git`. Programs that git starts on its own (hooks, `git-<name>` helpers, ssh, credential helpers,
editors, pagers) run inside the tool's sandbox and are not decided by this grammar. On macOS,
`/usr/bin/git` is a launcher that starts another git; point `command` at the git you want, such
as the Homebrew one.

## Supported commands

| Family | Actions |
|---|---|
| Inspect | `status`, `log`, `show`, `diff`, `blame`, `ls_files`, `rev_parse` |
| Working tree and index | `add`, `checkout`, `switch`, `restore`, `reset`, `clean`, `rm`, `mv` |
| Stash | `stash` (no subcommand), `stash_push`, `stash_list`, `stash_show`, `stash_apply`, `stash_pop`, `stash_drop`, `stash_clear`, `stash_branch` |
| History | `commit`, `merge`, `rebase`, `cherry_pick`, `revert` |
| Branches and tags | `branch`, `tag` |
| Remotes | `push`, `fetch`, `pull`, `clone`, `remote`, `remote_add`, `remote_remove` (alias `remote rm`), `remote_rename`, `remote_set_url`, `remote_get_url`, `remote_show`, `remote_prune`, `remote_update` |
| Configuration | `config_list`, `config_get`, `config_set`, `config_unset`, `config` (the older `--list`/`--get`/`<name> <value>` form) |
| Repositories | `init`, `worktree_list`, `worktree_add`, `worktree_remove`, `worktree_prune` |

The global options that git reads before the subcommand (`-C`, `-c`, `--config-env`, `--git-dir`,
`--work-tree`, `--namespace`, `--attr-source`, `--bare`, `-p`, `-P`, `--no-pager`, and the
`--*-pathspecs` and `--no-*` switches) are fields of every action. Git refuses them after the
subcommand, and so does the grammar.

## Effects

| Effect | Meaning | Added by, for example |
|---|---|---|
| `network` | Contacts another repository: a URL, or a path to another local repository | `push`, `fetch`, `pull`, `clone`, `remote show <name>`, `remote add -f` |
| `force_push` | Can replace commits on a remote ref | `push -f`, `--force-with-lease`, `--mirror`, a `+<refspec>` |
| `delete_remote_ref` | Deletes a branch or tag on the remote | `push -d`, `push :<ref>`, `--prune`, `--mirror` |
| `force_fetch` | Can replace commits on a local ref | `fetch -f`, `fetch -P`, a `+<src>:<dst>` refspec |
| `rewrite_history` | Replaces local commits, or moves an existing branch or tag | `commit --amend`, `rebase`, `pull --rebase`, `reset <commit>`, `branch -f`/`-M`/`-C`, `tag -f`, `checkout -B`, `switch -C` |
| `delete_ref` | Deletes a local branch, remote-tracking branch, or tag | `branch -d`/`-D`/`--delete-merged`, `tag -d`, `fetch -P` |
| `discard_changes` | Can overwrite or delete uncommitted changes, or drop stashed changes | `reset --hard`/`--merge`/`--keep`, `restore`, `checkout <x>`, `switch -f`, `rm -f`, `mv -f`, `stash drop`/`clear`, `merge`/`rebase`/`cherry-pick`/`revert --abort`, `worktree remove -f` |
| `delete_files` | Deletes files from the working tree | `clean`, `rm`, `worktree remove` |
| `skip_hooks` | Skips hooks the repository configures | `commit -n`/`--no-verify`, `--no-post-rewrite`, `push`/`merge`/`pull`/`rebase --no-verify`, global `-c` |
| `override_config` | Sets configuration, for one command or in a file | global `-c`/`--config-env`, `clone -c`, `config set`/`unset`, `config <name> <value>`, `remote add`/`remove`/`rename`/`set-url` |
| `run_program` | Makes git run a program that the line names or installs | `rebase -x`, `-s <strategy>`, `--upload-pack`, `--receive-pack`, `--ext-diff`, `--textconv`, `--template`, an `ext::` URL, global `-c` |
| `other_repository` | Points git at another repository or work tree | `-C`, `--git-dir`, `--work-tree` |
| `write_file` | Writes the output to a named file | `log`/`show`/`diff --output` |
| `outside_path` | A path on the line is absolute or contains `..` | `diff /etc/x`, `commit -F /tmp/m`, `clone <url> /tmp/x`, `worktree add ../wt`, `config -f ~/.x` |

Dry runs remove what they do not do: `push -n` keeps `network` but drops `force_push` and
`delete_remote_ref`; `clean -n`, `rm -n`, and `rm --cached` drop `delete_files`; `commit --dry-run`
(and `--short`, `--porcelain`, `--long`, which imply it) drops `rewrite_history` and `skip_hooks`;
`pull --dry-run` stops after the fetch; `restore --staged` touches only the index.

## Example rules

```cedar
// Let the agent use every modeled git command.
@id("git_actions")
permit (principal, action in Tool::git::Action::"*", resource);

// No force push, under any spelling.
@id("no_force_push")
@description("Force pushes are not allowed.")
forbid (principal, action == Tool::git::Action::"push", resource)
when { context.input.effects.contains(Tool::git::Effect::"force_push") };

// Push only to origin.
@id("push_to_origin_only")
forbid (principal, action == Tool::git::Action::"push", resource)
unless { context.input has repository && context.input.repository == "origin" };

// Never skip hooks, never lose uncommitted work.
@id("keep_hooks_and_work")
forbid (principal, action in Tool::git::Action::"*", resource)
when { context.input.effects.containsAny([Tool::git::Effect::"skip_hooks",
                                           Tool::git::Effect::"discard_changes"]) };

// Stay in this repository: no -C, --git-dir, or --work-tree, and no paths outside it.
@id("stay_here")
forbid (principal, action in Tool::git::Action::"*", resource)
when { context.input.effects.containsAny([Tool::git::Effect::"other_repository",
                                           Tool::git::Effect::"outside_path"]) };
```

`push_to_origin_only` also refuses a bare `git push`, which goes to the configured upstream that
the grammar cannot see.

## Exclusions

Each of these makes the line `unmodeled`, so a policy refuses it unless it permits `unmodeled`.

- **Abbreviations and most negations.** Git accepts `--amen` for `--amend` and `--no-<option>` for
  most options. Only the full spellings and the negations the grammar lists are declared.
- **`git log -<n>`** (a count as a bare number). Use `-n <n>` or `--max-count=<n>`.
- **`checkout -f`**, which throws away local changes even on a branch switch. Use `switch -f` or
  `restore`. `checkout -U`, `restore -U`, and the like, because `-U` alone means `-p` there.
- **`restore -W`/`--worktree`**, so that `restore --staged` can mean "index only".
- **`--pathspec-from-file`**, `--stdin`, `fetch --multiple`, `fetch --refmap`, `blame --contents`
  and `-S`, and `ls-files -X`: each reads operands or refs from a file or a stream that the
  grammar cannot see.
- **The older `config` modes** `--add`, `--replace-all`, `--edit`, the section modes, and the color
  modes. `config set`, `config unset`, and `config <name> <value>` cover writes.
- **Global `--exec-path`, `--version`, `--help`, `--list-cmds`**, `<command> -h`, and `--help` after a
  subcommand.
- **Commands not listed above**: `grep`, `bisect`, `submodule`, `am`, `apply`, `format-patch`,
  `send-email`, `reflog`, `gc`, `filter-branch`, plumbing, and the rest. `grep` is left out because
  its first operand is a pattern without `-e` and a revision with it, which one usage line cannot
  say.
- **Git aliases** (`alias.*`) and external `git-<name>` commands.

## Known limits

- **Configuration and environment.** `pull.rebase`, `push.default`, `remote.<name>.mirror`,
  `clean.requireForce`, `core.hooksPath`, `GIT_DIR`, `GIT_CONFIG_PARAMETERS`, and the rest change
  what a command does, and the grammar sees only the command line. `clean` therefore always adds
  `delete_files`, and a bare `git pull` adds no `rewrite_history` even when `pull.rebase` is set.
- **Branch or path.** `git checkout <x>` and `git reset <x>` treat <x> as a branch or a commit when
  one exists, and as a path otherwise. The grammar cannot tell, so `checkout <x>` always adds
  `discard_changes` (unless `-b`, `-B`, `--orphan`, `--detach`, or `--track` is given, because git
  then refuses paths) and `reset <x>` adds `rewrite_history` unless <x> is `HEAD` or `@`. The
  field names (`target`, `commit`, `revision`) name the documented role, not what git decided.
- **One action per command.** `branch` and `tag` have one action for every mode, so
  `branchname`/`tagname` collect every name, start point, and pattern on the line.
- **Value only at the end.** `branch --merged`, `--no-merged`, `--contains`, and `--no-contains`
  are declared with a value. Git also accepts each as the last word with no value (meaning `HEAD`);
  that spelling is `unmodeled`.
- **Options after an operand.** The `config` subcommands stop reading options at the first
  operand, so git reads a later `--global` as a value. The grammar reads it as the option. A write
  still carries `override_config` in both readings; only the field differs.
- **Programs git chooses.** A built-in merge strategy (`-s ort`) runs no external program, but
  `-s` adds `run_program` for every value. `--ext-diff` and `--textconv` add `run_program`, but
  configuration can make `diff` and `log` run them without either flag.
- **`outside_path` is a spelling test.** It matches an absolute path or a path that contains `..`.
  An absolute path inside the repository also matches; a symbolic link that leads out of the
  repository does not.
- **Case.** `--rebase=false`, `no`, `off`, and `0` turn the rebase off; git also accepts other
  letter cases (`FALSE`), which the grammar still reads as a rebase.
