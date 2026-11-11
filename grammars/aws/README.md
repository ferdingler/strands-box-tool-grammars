# AWS CLI v2 (`aws`)

A tool grammar for the [AWS CLI version 2](https://github.com/aws/aws-cli/tree/v2). With it, a
box policy can permit or forbid `aws` commands by service, operation, option value, and effect.

| | |
|---|---|
| Project | aws/aws-cli, branch v2 |
| Executable | `aws` |
| Version checked | 2.40.0 (tag `2.40.0`), from its `help` pages and its source |
| Policy namespace | `Tool::aws` |

The grammar models the global options and a set of common operations. Every other command is
`unmodeled`, and the default-deny refuses it unless a rule permits `Tool::aws::Action::"unmodeled"`.

## Install the CLI

Follow the [AWS CLI install guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html).
The official installer puts a native executable in an install directory (`/usr/local/aws-cli` by
default) and a link named `aws` in `/usr/local/bin`. The CLI v1 from PyPI (`pip install awscli`)
is a different program and is not covered.

## Load the grammar

The link `/usr/local/bin/aws` ends in `aws`, so the grammar binds it. The tool must read its own
install directory. `./scripts/render.sh aws --command /usr/local/bin/aws` prints the full tables.

```toml
[experimental-features]
tool-grammars = true

[tool.aws]
command = ["/usr/local/bin/aws"]

[tool.aws.filesystem]
read = ["/usr/local/aws-cli"]

[tool.aws.grammar]
# The body of aws.grammar.toml: format, version, name, program, and then
# [tool.aws.grammar.effects], [tool.aws.grammar.global], and one
# [tool.aws.grammar.shell.<action>] table per action.
format  = 1
version = 1
name    = "aws"
program = "aws"
```

The CLI also reads its configuration and credentials (`~/.aws/config`, `~/.aws/credentials`).
Grant the tool what your setup needs, in the tool's own filesystem lists.

**Keep `~/.aws/cli/alias` and `~/.aws/config` unwritable by the agent and by the tool.** An alias
can take the name of a built-in service or operation, so `aws sts get-caller-identity` can run
something else, and an alias that starts with `!` runs a shell command. The config file can load
plugins (`[plugins]`) and run a program (`credential_process`). The grammar reads the words as
the built-in command, so it is only correct while those files are what the operator wrote.

## Regenerate

`gen/` holds the generator: from `grammars/aws/gen`, run `python3 gen.py head.toml > ../aws.grammar.toml`.

## Command families

Each action is the command words joined with `_`, such as `s3_cp` or `ec2_terminate_instances`.

| Family | Actions | Effects |
|---|---|---|
| sts | `get-caller-identity`; `assume-role`, `get-session-token` | `read_data`; `credentials` |
| s3 | `ls`; `cp`, `mv`, `sync`; `rm`, `rb`; `mb`; `presign` | read, write, or upload by path; `mv`, `rm`, `rb`, `sync --delete` add `delete_data`; `--dryrun` removes the change |
| s3api | `list-buckets`, `list-objects-v2`, `head-object`, `get-object`, `get-bucket-policy`; `put-object`; `delete-object` | `read_data`; `write_data`; `delete_data` |
| ec2 | `describe-instances`, `-vpcs`, `-subnets`, `-security-groups`, `-images`; `start-instances`, `stop-instances`; `terminate-instances` | `read_data`; `write_data`; `delete_data`; `--dry-run` removes it |
| lambda | `list-functions`, `get-function`; `invoke` | `read_data`; `run_program` (`--invocation-type DryRun` removes it) |
| cloudformation | `describe-stacks`, `list-stacks`, `describe-stack-events`, `list-stack-resources`; `deploy`; `delete-stack` | `read_data`; `write_data` and `delete_data`; `delete_data`; `--role-arn` adds `assume_role` |
| iam | `list-users`, `list-roles`, `list-attached-role-policies`, `get-user`, `get-role`; `create-access-key`, `create-user`, `create-role`, `create-policy`, `attach-role-policy`, `put-role-policy`; `delete-role`, `delete-user` | `read_data`; `iam_write` with `write_data` or `delete_data`; `create-access-key` also `credentials` |
| logs | `tail`, `describe-log-groups`, `filter-log-events`, `get-log-events` | `read_data`; `--unmask` adds `read_secret` |
| dynamodb | `list-tables`, `describe-table`, `get-item`, `query`, `scan`; `put-item`; `delete-item` | `read_data`; `write_data`; `delete_data` |
| ssm | `get-parameter`, `get-parameters`, `get-parameters-by-path`; `put-parameter` | `read_data` (`--with-decryption` adds `read_secret`); `write_data` |
| secretsmanager | `get-secret-value`; `list-secrets`, `describe-secret` | `read_data` and `read_secret`; `read_data` |
| configure | `list`, `list-profiles`, `get`; `export-credentials` | `read_config` (`get` of a secret key adds `read_secret`); `credentials` |

Every action takes the global options anywhere on the line: `--region`, `--profile`,
`--endpoint-url`, `--output`, `--query`, `--no-cli-pager`, `--debug`, `--no-verify-ssl`,
`--ca-bundle`, `--no-paginate`, `--no-sign-request`, `--color`, `--cli-read-timeout`,
`--cli-connect-timeout`, `--cli-binary-format`, `--cli-error-format`, and `--no-cli-auto-prompt`.

## Effects

| Effect | Meaning |
|---|---|
| `read_data` | Reads data or metadata from an AWS account: list, describe, get, download. |
| `write_data` | Creates or changes resources or data in an AWS account. |
| `delete_data` | Deletes resources or data in AWS, or the local files that `s3 mv` and `s3 sync --delete` remove. A `cloudformation deploy` can delete the resources that a template no longer holds. |
| `read_secret` | Returns secret plain text: a secret value, a decrypted parameter, unmasked log data, or a credential from the config file (`aws_secret_access_key`, `aws_session_token`, or the legacy `aws_security_token`). |
| `credentials` | Obtains, creates, or prints AWS credentials. |
| `iam_write` | Changes IAM identities, policies, or permissions, or lets a stack do so (`--capabilities CAPABILITY_IAM`). |
| `make_public` | Grants access to everyone, or to every AWS account: a `public-read`, `public-read-write`, or `authenticated-read` ACL, or a grant to the AllUsers or AuthenticatedUsers group. |
| `grant_access` | Gives another party access to data: a presigned URL or an ACL grant. |
| `run_program` | Runs code in AWS (`lambda invoke`). |
| `upload_local_file` | Sends the content of local files to AWS. |
| `write_local_file` | Writes a local file: a download, or a response saved to a file. |
| `value_from_file` | A value starts with `file://` or `fileb://`. The CLI reads that local file and sends its content, so a rule sees only the file name. |
| `override_endpoint` | Sends the requests to an endpoint URL that the line names (`--endpoint-url`). |
| `assume_role` | Makes AWS act with the permissions of a role that the line names (`cloudformation deploy` and `delete-stack --role-arn`). |
| `change_account` | Selects a named profile (`--profile`), which can hold other credentials, another account, or another role. |
| `insecure_tls` | Skips certificate checks (`--no-verify-ssl`), trusts a CA bundle the line names (`--ca-bundle`), or uses an `http://` endpoint in any letter case. |
| `read_config` | Reads the local AWS CLI configuration. |

## Example rules

```cedar
// Let the agent run every modeled aws command.
@id("aws_modeled")
permit (principal, action in Tool::aws::Action::"*", resource);

// Read-only: no writes, deletes, code runs, or new credentials.
@id("aws_read_only")
@description("Only read commands are allowed.")
forbid (principal, action in Tool::aws::Action::"*", resource)
when {
  context.input.effects.contains(Tool::aws::Effect::"write_data") ||
  context.input.effects.contains(Tool::aws::Effect::"delete_data") ||
  context.input.effects.contains(Tool::aws::Effect::"run_program") ||
  context.input.effects.contains(Tool::aws::Effect::"credentials")
};

// No secret plain text in the agent's context.
@id("aws_no_secrets")
@description("Reading secret values is not allowed.")
forbid (principal, action in Tool::aws::Action::"*", resource)
when { context.input.effects.contains(Tool::aws::Effect::"read_secret") };

// Stay on the default endpoints and on full TLS.
@id("aws_no_endpoint_override")
forbid (principal, action in Tool::aws::Action::"*", resource)
when {
  context.input.effects.contains(Tool::aws::Effect::"override_endpoint") ||
  context.input.effects.contains(Tool::aws::Effect::"insecure_tls")
};

// Only one region. A line without --region uses the configured region, which the grammar cannot see.
@id("aws_one_region")
forbid (principal, action in Tool::aws::Action::"*", resource)
when { context.input has region && context.input.region != "eu-west-1" };
```

A rule that reads an option value, such as `bucket` or `instance_ids`, must also forbid
`value_from_file`, because `--bucket file://name.txt` sends a name that the rule cannot see.

## Exclusions

These are not declared, so a line that uses one is `unmodeled`:

- `--cli-input-json` and `--cli-input-yaml`. The document can set any parameter of the
  operation, such as `WithDecryption` or `ACL`, so the fields would not describe the request.
- `--cli-auto-prompt`. It opens a prompt that can build any command.
- `--generate-cli-skeleton`, `--help`, `--version`, and `help` after an API operation.
- `ec2 --no-dry-run`. argparse keeps the last of `--dry-run` and `--no-dry-run`, so
  `--dry-run --no-dry-run` makes the change. With it undeclared, `--dry-run` can safely remove
  the effect.
- s3 options with an optional value (`--sse`, `--sse-c`, `--request-payer`) or two values
  (`--tags <key> <value>`), and the options that carry customer keys (`--sse-c-key`).
- Every service and operation not in the table, such as `ec2 run-instances`, `ssm send-command`,
  `ssm start-session`, `ecs execute-command`, `configure set`, and `sso login`.

## Known limits

- **The grammar cannot see the environment or the config files.** `AWS_PROFILE`, `AWS_REGION`,
  `AWS_ENDPOINT_URL`, `AWS_CA_BUNDLE`, and the config file can change the account, region,
  endpoint, and TLS trust with nothing on the line. A `credential_process` in the config file
  runs a program.
- **CLI aliases.** `~/.aws/cli/alias` can give a built-in command another meaning, and an alias
  that starts with `!` runs a shell command. The grammar reads the words as the built-in command,
  so keep that file unwritable by the agent (see Load the grammar).
- **Option prefixes.** argparse accepts a unique prefix of a long option (`--reg`). The grammar
  does not, so such a line is `unmodeled`.
- **Required options.** The grammar does not check that a required option, such as `--bucket`,
  is present. The CLI refuses the line.
- **`help` as an s3 path.** `aws s3 ls help` prints help. The grammar reads `help` as the path,
  with the effects of that command, which is more than the CLI does.
- **Lambda configuration.** `lambda list-functions` and `get-function` return the environment
  variables of a function in plain text, and they can hold secrets. They have only `read_data`.
- **An empty list.** The CLI accepts a list option with no value (`--instance-ids` alone). The
  grammar needs at least one value, so such a line is `unmodeled`.
