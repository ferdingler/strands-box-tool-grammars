"""Generate ../aws.grammar.toml from head.toml and the compact spec below. Run: python3 gen.py head.toml > ../aws.grammar.toml"""
import sys

FILE = '{ like = "file*://*", adds = ["value_from_file"] }'
PUBLIC = '{ like = ["public-read", "public-read-write", "authenticated-read"], adds = ["make_public"] }'
PUBLIC_FILE = '{ like = "file*://*", adds = ["make_public", "value_from_file"] }'
ALLUSERS = '{ like = ["*AllUsers*", "*AuthenticatedUsers*"], adds = ["make_public"] }'


def key_of(flag):
    return flag.lstrip('-').replace('-', '_')


def opt(flag, kind='v', adds=None, removes=None, when=None, key=None, file=True):
    """kind: 'f' flag, 'v' required value, 'm' many."""
    parts = [f'flag = "{flag}"']
    if kind == 'v':
        parts.append('value = "required"')
    elif kind == 'm':
        parts.append('value = "many"')
    if adds:
        parts.append('adds = [' + ', '.join(f'"{a}"' for a in adds) + ']')
    if removes:
        parts.append('removes = [' + ', '.join(f'"{a}"' for a in removes) + ']')
    w = list(when or [])
    if kind != 'f' and file:
        w.append(FILE)
    if w:
        parts.append('when = [' + ', '.join(w) + ']')
    return (key or key_of(flag), '{ ' + ', '.join(parts) + ' }')


def V(flag, **kw):
    return opt(flag, 'v', **kw)


def M(flag, **kw):
    return opt(flag, 'm', **kw)


def F(flag, **kw):
    return opt(flag, 'f', **kw)


def C(flag, **kw):
    """A value option with argparse `choices`: argparse refuses a file:// value before it is loaded."""
    return opt(flag, 'v', file=False, **kw)


PAGE = [V('--starting-token'), V('--page-size'), V('--max-items')]
PAGE_NO_SIZE = [V('--starting-token'), V('--max-items')]
EC2_DRY = F('--dry-run', removes=['read_data'])
EC2_DRY_W = F('--dry-run', removes=['write_data'])
EC2_DRY_D = F('--dry-run', removes=['delete_data'])

S3_COMMON_XFER = [
    F('--dryrun', removes=['write_data', 'delete_data', 'upload_local_file', 'write_local_file',
                            'make_public', 'grant_access']),
    F('--quiet'),
    V('--include', file=False, key='include'),
    V('--exclude', file=False, key='exclude'),
    C('--acl', when=[PUBLIC]),
    M('--grants', adds=['grant_access'], when=[ALLUSERS, PUBLIC_FILE], file=False),
    F('--follow-symlinks'),
    F('--no-follow-symlinks'),
    F('--no-guess-mime-type'),
    V('--sse-kms-key-id'),
    C('--storage-class'),
    V('--content-type'),
    V('--cache-control'),
    V('--content-disposition'),
    V('--content-encoding'),
    V('--content-language'),
    V('--expires'),
    V('--source-region'),
    F('--only-show-errors'),
    F('--no-progress'),
    V('--page-size'),
    F('--ignore-glacier-warnings'),
    F('--force-glacier-transfer'),
    C('--checksum-mode'),
    C('--checksum-algorithm'),
    C('--metadata-directive'),
    F('--no-overwrite'),
]


def repeated(o):
    k, v = o
    return (k, v.replace('value = "required"', 'value = "required", repeated = true'))


S3_COMMON_XFER = [repeated(o) if o[0] in ('include', 'exclude') else o for o in S3_COMMON_XFER]

SRC = ('source', '{ adds = ["upload_local_file"], when = [{ like = "s3://*", adds = ["read_data"], removes = ["upload_local_file"] }] }')
DST = ('destination', '{ adds = ["write_local_file"], when = [{ like = "s3://*", adds = ["write_data"], removes = ["write_local_file"] }] }')
PATH_FILE = '{ when = [' + FILE + '] }'

# (words, usage tail, adds, options, operands, comment)
A = []


def act(words, tail='', adds=(), options=(), operands=(), comment=None, aliases=()):
    A.append(dict(words=words, tail=tail, adds=list(adds), options=list(options),
                  operands=list(operands), comment=comment, aliases=list(aliases)))


# ---------------------------------------------------------------- sts
act('sts get-caller-identity', adds=['read_data'],
    comment='sts: who am I, and temporary credentials. `aws sts <op> help`, 2.40.0.')
act('sts assume-role', adds=['credentials'], options=[
    V('--role-arn'), V('--role-session-name'), V('--duration-seconds'), V('--external-id'),
    V('--policy'), M('--policy-arns'), V('--serial-number'), V('--token-code'),
    V('--source-identity')])
act('sts get-session-token', adds=['credentials'], options=[
    V('--duration-seconds'), V('--serial-number'), V('--token-code')])

# ---------------------------------------------------------------- s3 (high-level)
act('s3 ls', '[<path>]', adds=['read_data'], options=[
    F('--recursive'), V('--page-size'), F('--human-readable'), F('--summarize'),
    V('--bucket-name-prefix'), V('--bucket-region')],
    operands=[('path', PATH_FILE)],
    comment='s3: the high-level transfer commands (awscli/customizations/s3/subcommands.py, 2.40.0).\n'
            '# A single path is loaded from a file when it starts with file://; the two paths of cp, mv,\n'
            '# and sync are not (they are a two-item list, and the loader reads only a one-item list).')
act('s3 cp', '<source> <destination>', options=S3_COMMON_XFER + [F('--recursive'), V('--expected-size')],
    operands=[SRC, DST])
act('s3 mv', '<source> <destination>', adds=['delete_data'],
    options=S3_COMMON_XFER + [F('--recursive'), F('--validate-same-s3-paths')], operands=[SRC, DST])
act('s3 sync', '<source> <destination>',
    options=S3_COMMON_XFER + [F('--size-only'), F('--exact-timestamps'), F('--delete', adds=['delete_data'])],
    operands=[SRC, DST])
act('s3 rm', '<path>', adds=['delete_data'], options=[
    F('--dryrun', removes=['delete_data']), F('--quiet'), F('--recursive'),
    repeated(V('--include', file=False)), repeated(V('--exclude', file=False)),
    F('--only-show-errors'), V('--page-size')],
    operands=[('path', PATH_FILE)])
act('s3 mb', '<path>', adds=['write_data'], operands=[('path', PATH_FILE)])
act('s3 rb', '<path>', adds=['delete_data'], options=[F('--force')], operands=[('path', PATH_FILE)])
act('s3 presign', '<path>', adds=['grant_access'], options=[V('--expires-in')],
    operands=[('path', PATH_FILE)])

# ---------------------------------------------------------------- s3api
act('s3api list-buckets', adds=['read_data'], options=[V('--prefix'), V('--bucket-region')] + PAGE,
    comment='s3api: one API operation per command. Every value of these options is loaded from a local\n'
            '# file when it starts with file:// or fileb:// (awscli/paramfile.py), so each one carries\n'
            '# `value_from_file`.')
act('s3api list-objects-v2', adds=['read_data'], options=[
    V('--bucket'), V('--prefix'), V('--delimiter'), V('--start-after'), F('--fetch-owner'),
    F('--no-fetch-owner'), V('--expected-bucket-owner')] + PAGE)
act('s3api head-object', adds=['read_data'], options=[
    V('--bucket'), V('--key'), V('--version-id'), V('--expected-bucket-owner')])
act('s3api get-object', '<outfile>', adds=['read_data', 'write_local_file'], options=[
    V('--bucket'), V('--key'), V('--version-id'), V('--range'), V('--expected-bucket-owner')])
act('s3api get-bucket-policy', adds=['read_data'], options=[V('--bucket'), V('--expected-bucket-owner')])
act('s3api put-object', adds=['write_data'], options=[
    V('--bucket'), V('--key'),
    V('--body', adds=['upload_local_file'], file=False),
    V('--acl', when=[PUBLIC, PUBLIC_FILE], file=False),
    V('--grant-read', adds=['grant_access'], when=[ALLUSERS, PUBLIC_FILE], file=False),
    V('--grant-read-acp', adds=['grant_access'], when=[ALLUSERS, PUBLIC_FILE], file=False),
    V('--grant-write-acp', adds=['grant_access'], when=[ALLUSERS, PUBLIC_FILE], file=False),
    V('--grant-full-control', adds=['grant_access'], when=[ALLUSERS, PUBLIC_FILE], file=False),
    V('--content-type'), V('--cache-control'), V('--storage-class'), V('--server-side-encryption'),
    V('--ssekms-key-id'), V('--tagging'), V('--expected-bucket-owner'), V('--if-none-match'),
    V('--if-match')])
act('s3api delete-object', adds=['delete_data'], options=[
    V('--bucket'), V('--key'), V('--version-id'), V('--expected-bucket-owner')])

# ---------------------------------------------------------------- ec2
act('ec2 describe-instances', adds=['read_data'], options=[
    M('--instance-ids'), M('--filters'), EC2_DRY] + PAGE,
    comment='ec2: `--dry-run` asks EC2 to check permission and make no change. `--no-dry-run` is not\n'
            '# declared: argparse keeps the last of the pair, so `--dry-run --no-dry-run` runs for real.')
act('ec2 describe-vpcs', adds=['read_data'], options=[M('--vpc-ids'), M('--filters'), EC2_DRY] + PAGE)
act('ec2 describe-subnets', adds=['read_data'], options=[M('--subnet-ids'), M('--filters'), EC2_DRY] + PAGE)
act('ec2 describe-security-groups', adds=['read_data'], options=[
    M('--group-ids'), M('--group-names'), M('--filters'), EC2_DRY] + PAGE)
act('ec2 describe-images', adds=['read_data'], options=[
    M('--image-ids'), M('--owners'), M('--executable-users'), M('--filters'),
    F('--include-deprecated'), F('--include-disabled'), EC2_DRY] + PAGE)
act('ec2 start-instances', adds=['write_data'], options=[
    M('--instance-ids'), V('--additional-info'), EC2_DRY_W])
act('ec2 stop-instances', adds=['write_data'], options=[
    M('--instance-ids'), F('--hibernate'), F('--force'), EC2_DRY_W])
act('ec2 terminate-instances', adds=['delete_data'], options=[M('--instance-ids'), EC2_DRY_D])

# ---------------------------------------------------------------- lambda
act('lambda list-functions', adds=['read_data'], options=[
    V('--function-version'), V('--master-region')] + PAGE,
    comment='lambda: a function configuration includes its environment variables in plain text, so\n'
            '# list-functions and get-function can return values that hold secrets.')
act('lambda get-function', adds=['read_data'], options=[V('--function-name'), V('--qualifier')])
act('lambda invoke', '<outfile>', adds=['run_program', 'write_local_file'], options=[
    V('--function-name'), V('--qualifier'),
    V('--invocation-type', when=['{ like = "DryRun", removes = ["run_program"] }']),
    V('--payload'), V('--log-type'), V('--client-context')])

# ---------------------------------------------------------------- cloudformation
act('cloudformation describe-stacks', adds=['read_data'], options=[V('--stack-name')] + PAGE_NO_SIZE,
    comment='cloudformation. `deploy` is a custom command (customizations/cloudformation/deploy.py): it\n'
            '# reads a local template, and an update deletes each resource that the template no longer\n'
            '# holds. `--no-execute-changeset` only creates the change set. `--role-arn` makes CloudFormation act\n'
            '# with that service role, so it adds `assume_role`.')
act('cloudformation list-stacks', adds=['read_data'], options=[M('--stack-status-filter')] + PAGE_NO_SIZE)
act('cloudformation describe-stack-events', adds=['read_data'], options=[V('--stack-name')] + PAGE_NO_SIZE)
act('cloudformation list-stack-resources', adds=['read_data'], options=[V('--stack-name')] + PAGE_NO_SIZE)
act('cloudformation deploy', adds=['write_data', 'delete_data', 'upload_local_file'], options=[
    V('--template-file'), V('--stack-name'), V('--s3-bucket'), V('--s3-prefix'), F('--force-upload'),
    V('--kms-key-id'), M('--parameter-overrides'),
    M('--capabilities', file=False, when=['{ like = ["CAPABILITY_IAM", "CAPABILITY_NAMED_IAM"], adds = ["iam_write"] }',
                                          '{ like = "file*://*", adds = ["iam_write", "value_from_file"] }']),
    F('--no-execute-changeset', removes=['delete_data', 'iam_write']),
    F('--disable-rollback'), F('--no-disable-rollback'), V('--role-arn', adds=['assume_role']), M('--notification-arns'),
    F('--fail-on-empty-changeset'), F('--no-fail-on-empty-changeset'), M('--tags')])
act('cloudformation delete-stack', adds=['delete_data'], options=[
    V('--stack-name'), M('--retain-resources'), V('--role-arn', adds=['assume_role']), V('--deletion-mode')])

# ---------------------------------------------------------------- iam
IAM_PAGE = [V('--path-prefix')] + PAGE
act('iam list-users', adds=['read_data'], options=IAM_PAGE,
    comment='iam: each change to an identity or a policy carries `iam_write` beside `write_data` or\n'
            '# `delete_data`.')
act('iam list-roles', adds=['read_data'], options=IAM_PAGE)
act('iam list-attached-role-policies', adds=['read_data'], options=[V('--role-name')] + IAM_PAGE)
act('iam get-user', adds=['read_data'], options=[V('--user-name')])
act('iam get-role', adds=['read_data'], options=[V('--role-name')])
act('iam create-access-key', adds=['credentials', 'iam_write', 'write_data'], options=[V('--user-name')])
act('iam create-user', adds=['iam_write', 'write_data'], options=[
    V('--user-name'), V('--path'), V('--permissions-boundary')])
act('iam create-role', adds=['iam_write', 'write_data'], options=[
    V('--role-name'), V('--path'), V('--assume-role-policy-document'), V('--description'),
    V('--max-session-duration'), V('--permissions-boundary')])
act('iam create-policy', adds=['iam_write', 'write_data'], options=[
    V('--policy-name'), V('--path'), V('--policy-document'), V('--description')])
act('iam attach-role-policy', adds=['iam_write', 'write_data'], options=[V('--role-name'), V('--policy-arn')])
act('iam put-role-policy', adds=['iam_write', 'write_data'], options=[
    V('--role-name'), V('--policy-name'), V('--policy-document')])
act('iam delete-role', adds=['iam_write', 'delete_data'], options=[V('--role-name')])
act('iam delete-user', adds=['iam_write', 'delete_data'], options=[V('--user-name')])

# ---------------------------------------------------------------- logs
act('logs tail', '<group_name>', adds=['read_data'], options=[
    V('--since'), F('--follow'), C('--format'), V('--filter-pattern'), M('--log-stream-names'),
    V('--log-stream-name-prefix')],
    operands=[('group_name', PATH_FILE)],
    comment='logs. `--unmask` returns log data that a data protection policy masks, so it adds\n'
            '# `read_secret`. `tail` is a custom command (customizations/logs/tail.py).')
act('logs describe-log-groups', adds=['read_data'], options=[
    V('--log-group-name-prefix'), V('--log-group-name-pattern'), V('--log-group-class')] + PAGE)
act('logs filter-log-events', adds=['read_data'], options=[
    V('--log-group-name'), V('--log-group-identifier'), M('--log-stream-names'),
    V('--log-stream-name-prefix'), V('--start-time'), V('--end-time'), V('--filter-pattern'),
    F('--unmask', adds=['read_secret']), F('--no-unmask')] + PAGE)
act('logs get-log-events', adds=['read_data'], options=[
    V('--log-group-name'), V('--log-group-identifier'), V('--log-stream-name'), V('--start-time'),
    V('--end-time'), V('--next-token'), V('--limit'), F('--start-from-head'), F('--no-start-from-head'),
    F('--unmask', adds=['read_secret']), F('--no-unmask')])

# ---------------------------------------------------------------- dynamodb
DDB_READ = [V('--projection-expression'), V('--expression-attribute-names'), F('--consistent-read'),
            F('--no-consistent-read'), V('--return-consumed-capacity')]
act('dynamodb list-tables', adds=['read_data'], options=PAGE,
    comment='dynamodb: items, keys, and expressions are JSON values, often given as file://.')
act('dynamodb describe-table', adds=['read_data'], options=[V('--table-name')])
act('dynamodb get-item', adds=['read_data'], options=[V('--table-name'), V('--key')] + DDB_READ)
act('dynamodb query', adds=['read_data'], options=[
    V('--table-name'), V('--index-name'), V('--key-condition-expression'), V('--filter-expression'),
    V('--expression-attribute-values'), V('--select'), F('--scan-index-forward'),
    F('--no-scan-index-forward')] + DDB_READ + PAGE)
act('dynamodb scan', adds=['read_data'], options=[
    V('--table-name'), V('--index-name'), V('--filter-expression'), V('--expression-attribute-values'),
    V('--select'), V('--segment'), V('--total-segments')] + DDB_READ + PAGE)
DDB_WRITE = [V('--table-name'), V('--condition-expression'), V('--expression-attribute-names'),
             V('--expression-attribute-values'), V('--return-values'), V('--return-consumed-capacity')]
act('dynamodb put-item', adds=['write_data'], options=[V('--item')] + DDB_WRITE)
act('dynamodb delete-item', adds=['delete_data'], options=[V('--key')] + DDB_WRITE)

# ---------------------------------------------------------------- ssm
WD = [F('--with-decryption', adds=['read_secret']), F('--no-with-decryption')]
act('ssm get-parameter', adds=['read_data'], options=[V('--name')] + WD,
    comment='ssm Parameter Store. `--with-decryption` returns the plain text of a SecureString, so it\n'
            '# adds `read_secret`. A String parameter is plain text with or without it.')
act('ssm get-parameters', adds=['read_data'], options=[M('--names')] + WD)
act('ssm get-parameters-by-path', adds=['read_data'], options=[
    V('--path'), F('--recursive'), F('--no-recursive'), M('--parameter-filters')] + WD + PAGE)
act('ssm put-parameter', adds=['write_data'], options=[
    V('--name'), V('--value'), V('--type'), V('--description'), V('--key-id'), F('--overwrite'),
    F('--no-overwrite'), V('--tier'), V('--data-type'), V('--allowed-pattern')])

# ---------------------------------------------------------------- secretsmanager
act('secretsmanager get-secret-value', adds=['read_data', 'read_secret'], options=[
    V('--secret-id'), V('--version-id'), V('--version-stage')],
    comment='secretsmanager.')
act('secretsmanager list-secrets', adds=['read_data'], options=[
    F('--include-planned-deletion'), F('--no-include-planned-deletion'), M('--filters'),
    V('--sort-order'), V('--sort-by')] + PAGE)
act('secretsmanager describe-secret', adds=['read_data'], options=[V('--secret-id')])

# ---------------------------------------------------------------- configure
act('configure list', adds=['read_config'],
    comment='configure: reads the local configuration (customizations/configure/). Only the read verbs\n'
            '# are modeled; `configure set`, `configure sso`, and the bare `configure` prompt are not.')
act('configure list-profiles', adds=['read_config'])
act('configure get', '<varname>', adds=['read_config'],
    operands=[('varname', '{ when = [{ like = ["aws_secret_access_key", "aws_session_token", "aws_security_token", '
               '"*.aws_secret_access_key", "*.aws_session_token", "*.aws_security_token"], adds = ["read_secret"] }, '
               '{ like = "file*://*", adds = ["read_secret", "value_from_file"] }] }')])
act('configure export-credentials', adds=['credentials', 'read_config'], options=[C('--format')])


def usage(a):
    u = 'aws [global options] ' + a['words']
    if a['options']:
        u += ' [options]'
    if a['tail']:
        u += ' ' + a['tail']
    return u


def name(a):
    return a['words'].replace(' ', '_').replace('-', '_')


out = []
w = out.append
w(open(sys.argv[1]).read().rstrip())
for a in A:
    if a['comment']:
        w('\n# ' + '-' * 98)
        w('# ' + a['comment'])
    w(f'\n[shell.{name(a)}]')
    w(f'usage = "{usage(a)}"')
    if a['aliases']:
        w('aliases = [' + ', '.join(f'"{x}"' for x in a['aliases']) + ']')
    if a['adds']:
        w('adds  = [' + ', '.join(f'"{x}"' for x in sorted(a['adds'])) + ']')
    width = max([len(k) for k, _ in a['options']] + [len(k) for k, _ in a['operands']] + [0])
    for k, v in a['options']:
        w(f'options.{k.ljust(width)} = {v}')
    for k, v in a['operands']:
        w(f'operands.{k.ljust(width - 1 if width else 0)} = {v}')
print('\n'.join(out))
