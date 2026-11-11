# kubectl

A Strands Box tool grammar for `kubectl`, the Kubernetes command-line client. It reads the common
agent workflows (inspect, read logs, apply with a dry run, roll out, exec) and gives a policy the
effect of each line: a cluster read or write, a delete, a Secret read, a container exec, or a
change of target cluster or identity.

| | |
|---|---|
| Project | [kubernetes/kubernetes](https://github.com/kubernetes/kubernetes) (source in [kubernetes/kubectl](https://github.com/kubernetes/kubectl)) |
| Executable | `kubectl`, a native Go binary |
| Version checked | v1.37.2 (kubectl staging tag v0.37.2) |
| Policy namespace | `Tool::kubectl` |

## Install kubectl

Follow the [official install guide](https://kubernetes.io/docs/tasks/tools/), or download the
pinned release directly, for example
`https://dl.k8s.io/release/v1.37.2/bin/darwin/arm64/kubectl`. Check the SHA-256 that the release
publishes beside it.

## Load the grammar

kubectl is a native binary, so `command` names the file. A Homebrew link also works, because it
ends in `kubectl`; restart the box after `brew upgrade`. Print the tables with:

```sh
./scripts/render.sh kubectl --label kubectl --command /usr/local/bin/kubectl
```

It prints a block that starts like this, followed by every `[tool.kubectl.grammar.*]` table:

```toml
[experimental-features]
tool-grammars = true

[tool.kubectl]
command = ["/usr/local/bin/kubectl"]
env = { KUBECTL_KUBERC = "false" }   # turn off kuberc defaults and aliases (see Known limits)

[tool.kubectl.grammar]
format = 1
version = 1
name = "kubectl"
program = "kubectl"
```

kubectl reads its kubeconfig (by default `~/.kube/config`), so name it in
`[tool.kubectl.filesystem]`, and let the tool reach the API server through the box's egress
settings.

## Command families

| Family | Actions | Effects |
|---|---|---|
| Reads | `get`, `describe`, `logs`, `explain`, `api-resources`, `api-versions`, `cluster-info`, `top pod` (`pods`, `po`), `top node` (`nodes`, `no`), `auth can-i`, `auth whoami`, `rollout status`, `rollout history` | `cluster_read`; `get` of a Secret adds `read_secrets` |
| Version | `version` | `cluster_read`, removed by `--client` |
| Kubeconfig | `config view`, `config get-contexts`, `config current-context`, `config use-context` (`use`) | none; `view --raw` or `--flatten` adds `read_secrets`; `use-context` adds `override_config` |
| Apply and create | `apply`, `create -f`, `create namespace` (`ns`), `create secret generic`, `create configmap` (`cm`), `create deployment` (`deploy`) | `cluster_write`; `-f`/`-k` add `manifest_input`; `apply --prune` adds `cluster_delete` and `broad_delete`; `--from-file` adds `upload_files` |
| Change | `patch`, `label`, `annotate`, `scale`, `rollout restart`, `rollout pause`, `rollout resume`, `rollout undo` | `cluster_write`; a patch to a Secret adds `write_secrets` |
| Delete | `delete` | `cluster_delete`; `--all`, `-A`, `-l`, `--field-selector` add `broad_delete` |
| Containers | `exec POD -- CMD...`, `cp`, `port-forward` | `run_program`; `cp` adds `upload_files` or `write_local_files`; `port-forward` adds `network_listen`, and `--address` adds `listen_address` |

The persistent flags `-n/--namespace`, `--context`, `--kubeconfig`, `--cluster`, `--user`,
`-s/--server`, `--as`, `--as-group`, `--as-uid`, `--token`, `--username`, `--password`,
`--insecure-skip-tls-verify`, `--request-timeout`, `-v/--v`, `--warnings-as-errors`, and
`--match-server-version` are accepted before, between, and after the command words.

`--dry-run=client`, `--dry-run=server`, a bare `--dry-run`, and a true boolean value remove the
write and delete effects. `--dry-run=none` and `--dry-run=false` keep them.

## Effects

| Effect | Meaning |
|---|---|
| `cluster_read` | Reads objects or state from the cluster API server |
| `cluster_write` | Creates or changes objects in the cluster |
| `cluster_delete` | Deletes objects in the cluster |
| `broad_delete` | Can delete many objects at once: `--all`, `--all-namespaces`, a selector, or `--prune` |
| `read_secrets` | Reads Secret objects, or kubeconfig credentials without redaction |
| `write_secrets` | Creates or changes a Secret |
| `run_program` | Runs a program inside a container (`exec`, and the `tar` that `cp` runs) |
| `network_listen` | Opens a listening port on this host that forwards to the cluster |
| `listen_address` | Sets the listen address; a value other than localhost exposes the port to other hosts |
| `upload_files` | Sends the contents of local files to the cluster |
| `write_local_files` | Writes files on this host |
| `manifest_input` | Reads objects or changes from a file, directory, URL, or kustomization the grammar cannot see |
| `impersonate` | Acts as another user, group, or UID |
| `change_target` | Names a cluster, context, user, server, or kubeconfig on the command line |
| `override_config` | Changes the kubeconfig file on disk |
| `credentials` | Passes a credential on the command line |
| `insecure_tls` | Turns off the server certificate check |

## Example policy rules

```cedar
// Allow every modeled kubectl command, then narrow it.
@id("kubectl_actions")
permit (principal, action in Tool::kubectl::Action::"*", resource);

// Read-only: no write or delete unless it is a dry run.
@id("kubectl_read_only")
@description("Changing the cluster is not allowed; use --dry-run.")
forbid (principal, action in Tool::kubectl::Action::"*", resource)
when { context.input.effects.contains(Tool::kubectl::Effect::"cluster_write") ||
       context.input.effects.contains(Tool::kubectl::Effect::"cluster_delete") };

// Never print Secret data.
@id("kubectl_no_secrets")
forbid (principal, action in Tool::kubectl::Action::"*", resource)
when { context.input.effects.contains(Tool::kubectl::Effect::"read_secrets") };

// Stay on the current context and identity.
@id("kubectl_one_target")
forbid (principal, action in Tool::kubectl::Action::"*", resource)
when { context.input.effects.contains(Tool::kubectl::Effect::"change_target") ||
       context.input.effects.contains(Tool::kubectl::Effect::"impersonate") };

// Keep the agent out of kube-system.
@id("kubectl_not_kube_system")
forbid (principal, action in Tool::kubectl::Action::"*", resource)
when { context.input has namespace && context.input.namespace == "kube-system" };
```

A command line the grammar cannot read is `Tool::kubectl::Action::"unmodeled"`, which `"*"` does
not include, so default deny refuses it.

## Exclusions

These are deliberately `unmodeled`:

- `edit`, `apply edit-last-applied`, and `create --edit`, because they open an editor.
- `get --raw`, `delete --raw`, and `create --raw`, because a raw request can reach any API path.
- `run`, `debug`, `attach`, `proxy`, `drain`, `cordon`, `taint`, `replace`, `set`, `expose`,
  `autoscale`, `certificate`, `wait`, `diff`, `events`, `kustomize`, `cluster-info dump`, the
  `config set*`/`delete*`/`rename-context` verbs, other `create` kinds, `create secret tls` and
  `docker-registry`, `create token`, `auth reconcile`, `plugin`, `kuberc`, and `completion`.
- `label --list`, `delete --interactive`, `exec -f`, and the persistent flags `--kuberc`,
  `--client-key`, `--client-certificate`, `--certificate-authority`, `--tls-server-name`,
  `--proxy-url`, `--cache-dir`, `--profile`, `--profile-output`, `--as-user-extra`, and
  `--disable-compression`.
- `--help`, `-h`, `kubectl help`, and kubectl plugins (`kubectl <name>` that runs `kubectl-<name>`).

## Known limits

- **kuberc.** kubectl reads `~/.kube/kuberc` (or `--kuberc`). Its `defaults` can set flag values on
  built-in commands, such as `--prune` on `apply`, which the grammar cannot see. Set
  `KUBECTL_KUBERC=false` in the tool's `env`, or keep the kuberc file out of the tool's filesystem
  lists. A kuberc alias cannot shadow a built-in command, so an alias line is `unmodeled`.
- **The kubeconfig.** The grammar sees only the command line. The current context, its cluster,
  user, and namespace come from the kubeconfig, and a credential `exec` plugin there (such as
  `aws eks get-token`) runs as a child of kubectl that the policy does not decide.
- **Value spellings.** pflag accepts `-n=foo`, `-o=json`, and `_` for `-` in a flag name
  (`--all_namespaces`). The grammar reads each as `unmodeled`. A boolean that has a short form
  (`-A`, `-R`, `-w`, `-f`, `-p`, `-i`, `-t`, `-q`) is a plain flag, so `--all-namespaces=true` and
  `--watch=false` are `unmodeled`. A long-only boolean accepts `--flag=false`; its field then holds
  `"false"` and its effects do not apply.
- **Secrets.** `read_secrets` follows the resource type, in any case: `secret`, `secrets`,
  `secret/x`, `pods,secrets`, `Secret/x`. It also matches any type whose name contains `secret`,
  such as a custom resource. Objects named only in a `-f` file carry `manifest_input`, not
  `read_secrets`. `describe secret` prints key names and sizes, not values, so it carries no
  `read_secrets`. `apply` and `create -f` of a Secret manifest carry `manifest_input`.
- **Operands.** `label` and `annotate` take the type, names, and `KEY=VAL` words as one set,
  `operands`. In `get`, `delete`, `scale`, and the rollout verbs, the first word is `type` and the
  rest are `name`. `exec` and `create deployment` keep the command after `--` as a set, so word
  order is lost.
- **Selectors.** `broad_delete` is added for any `-l` or `--field-selector` on `delete`, even one
  that matches a single object.
