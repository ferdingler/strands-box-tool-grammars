# Generates ../uv.grammar.toml from head.toml and the shared option blocks below.
# Run: python3 grammars/uv/gen/gen.py   (from anywhere; it writes the grammar in place)
import sys, pathlib
CRED = '{ like = "*://*@*", adds = ["credentials"] }'
def idx():
    w = f'when = [{CRED}]'
    return [
     ('index',          f'{{ flag = ["--index"], value = "required", repeated = true, adds = ["override_index"], {w} }}'),
     ('default_index',  f'{{ flag = ["--default-index"], value = "required", adds = ["override_index"], {w} }}'),
     ('index_url',      f'{{ flag = ["-i", "--index-url"], value = "required", adds = ["override_index"], {w} }}'),
     ('extra_index_url',f'{{ flag = ["--extra-index-url"], value = "required", repeated = true, adds = ["override_index"], {w} }}'),
     ('find_links',     f'{{ flag = ["-f", "--find-links"], value = "required", repeated = true, adds = ["override_index"], {w} }}'),
     ('no_index',       '{ flag = ["--no-index"] }'),
    ]
RES_ALL = [
 ('upgrade',        '{ flag = ["-U", "--upgrade"] }'),
 ('upgrade_package','{ flag = ["-P", "--upgrade-package"], value = "required", repeated = true }'),
 ('resolution',     '{ flag = ["--resolution"], value = "required" }'),
 ('prerelease',     '{ flag = ["--prerelease"], value = "required" }'),
]
EXN = [('exclude_newer', '{ flag = ["--exclude-newer"], value = "required" }')]
INS = [
 ('reinstall',        '{ flag = ["--reinstall"] }'),
 ('reinstall_package','{ flag = ["--reinstall-package"], value = "required", repeated = true }'),
 ('compile_bytecode', '{ flag = ["--compile-bytecode"] }'),
]
BLD = [
 ('no_build',           '{ flag = ["--no-build"] }'),
 ('no_build_isolation', '{ flag = ["--no-build-isolation"] }'),
]
REF = [
 ('refresh',         '{ flag = ["--refresh"] }'),
 ('refresh_package', '{ flag = ["--refresh-package"], value = "required", repeated = true }'),
]
# `--python` names an interpreter that uv executes to query it (`InterpreterInfo::query`); a bare name is
# looked up on PATH. `like` cannot tell a version from a name or a path, so every value adds `run_program`.
PY = [('python', '{ flag = ["-p", "--python"], value = "required", adds = ["run_program"], removes = ["read_only"] }')]
# In the pip commands that change an environment, `--python` may name a system interpreter.
PY_SYS = [('python', '{ flag = ["-p", "--python"], value = "required", adds = ["run_program", "system_python"] }')]
WF = '["write_file"]'
EXTRAS = [
 ('extra',      '{ flag = ["--extra"], value = "required", repeated = true }'),
 ('all_extras', '{ flag = ["--all-extras"] }'),
]
GROUPS = [
 ('no_dev',            '{ flag = ["--no-dev"] }'),
 ('only_dev',          '{ flag = ["--only-dev"] }'),
 ('group',             '{ flag = ["--group"], value = "required", repeated = true }'),
 ('no_group',          '{ flag = ["--no-group"], value = "required", repeated = true }'),
 ('only_group',        '{ flag = ["--only-group"], value = "required", repeated = true }'),
 ('all_groups',        '{ flag = ["--all-groups"] }'),
 ('no_default_groups', '{ flag = ["--no-default-groups"] }'),
]
def flag(f, **kw):
    parts = [f'flag = {f}']
    for k, v in kw.items(): parts.append(f'{k} = {v}')
    return '{ ' + ', '.join(parts) + ' }'

out = []
def action(name, usage, adds=None, aliases=None, opts=(), operands=(), comment=None):
    out.append('')
    if comment:
        for c in comment.strip().splitlines(): out.append('# ' + c if c else '#')
    out.append(f'[shell.{name}]')
    out.append(f'usage   = "{usage}"')
    if aliases: out.append('aliases = ' + '[' + ', '.join(f'"{a}"' for a in aliases) + ']')
    if adds is not None: out.append('adds    = ' + '[' + ', '.join(f'"{a}"' for a in adds) + ']')
    w = max([len(k) for k, _ in opts] + [0])
    for k, v in opts: out.append(f'options.{k.ljust(w)} = {v}')
    for k, v in operands: out.append(f'operands.{k} = {v}')

L = lambda *xs: '[' + ', '.join(f'"{x}"' for x in xs) + ']'
LOCKMODE = lambda frozen_removes, locked_removes: [
 ('locked', flag('["--locked"]', removes=L(*locked_removes))),
 ('frozen', flag('["--frozen"]', removes=L(*frozen_removes))),
]
G = 'uv [global options]'

# ---------------- project ----------------
action('run', f'{G} run [options] <command>...',
  adds=['run_program', 'network', 'modify_environment', 'modify_project', 'build_code'],
  opts=EXTRAS + GROUPS + [
   ('module',            flag('["-m", "--module"]')),
   ('script',            flag('["-s", "--script"]')),
   ('with',              flag('["-w", "--with"]', value='"required"', repeated='true')),
   ('with_editable',     flag('["--with-editable"]', value='"required"', repeated='true')),
   ('with_requirements', flag('["--with-requirements"]', value='"required"', repeated='true')),
   ('isolated',          flag('["--isolated"]')),
   ('active',            flag('["--active"]')),
   ('exact',             flag('["--exact"]')),
   ('no_sync',           flag('["--no-sync"]', removes=L('modify_project'))),
   ('env_file',          flag('["--env-file"]', value='"required"', repeated='true')),
   ('no_env_file',       flag('["--no-env-file"]')),
   ('all_packages',      flag('["--all-packages"]')),
   ('package',           flag('["--package"]', value='"required"')),
   ('no_project',        flag('["--no-project"]')),
  ] + LOCKMODE(['modify_project'], ['modify_project']) + idx() + RES_ALL + EXN + INS + BLD + REF + PY,
  operands=[('command', '{ rest = true }')],
  comment='''`uv run <cmd> [args]` runs a program that the line names, after uv locks and syncs the project.
The command and every word after it belong to that program, so they are one `rest` operand.''')

action('init', f'{G} init [options] [<path>]',
  adds=['modify_project', 'network'],
  opts=[
   ('name',          flag('["--name"]', value='"required"')),
   ('bare',          flag('["--bare"]')),
   ('package',       flag('["--package"]')),
   ('no_package',    flag('["--no-package"]')),
   ('app',           flag('["--app"]')),
   ('lib',           flag('["--lib"]')),
   ('script',        flag('["--script"]')),
   ('description',   flag('["--description"]', value='"required"')),
   ('no_description',flag('["--no-description"]')),
   ('vcs',           flag('["--vcs"]', value='"required"')),
   ('build_backend', flag('["--build-backend"]', value='"required"')),
   ('no_readme',     flag('["--no-readme"]')),
   ('author_from',   flag('["--author-from"]', value='"required"')),
   ('no_pin_python', flag('["--no-pin-python"]')),
   ('no_workspace',  flag('["--no-workspace"]')),
  ] + PY,
  operands=[('path', '{ adds = ["write_file"] }')])

ADD_COMMON = [
   ('dev',      flag('["--dev"]')),
   ('optional', flag('["--optional"]', value='"required"')),
   ('group',    flag('["--group"]', value='"required"')),
   ('no_sync',  flag('["--no-sync"]', removes=L('modify_environment'))),
   ('active',   flag('["--active"]')),
   ('locked',   flag('["--locked"]')),
   ('frozen',   flag('["--frozen"]')),
   ('package',  flag('["--package"]', value='"required"')),
   ('script',   flag('["--script"]', value='"required"')),
]
action('add', f'{G} add [options] [--] [<packages>...]',
  adds=['modify_project', 'network', 'modify_environment', 'build_code'],
  opts=[
   ('requirements', flag('["-r", "--requirements"]', value='"required"', repeated='true')),
   ('constraints',  flag('["-c", "--constraints"]', value='"required"', repeated='true')),
   ('editable',     flag('["--editable"]')),
   ('raw',          flag('["--raw"]')),
   ('bounds',       flag('["--bounds"]', value='"required"')),
   ('rev',          flag('["--rev"]', value='"required"')),
   ('tag',          flag('["--tag"]', value='"required"')),
   ('branch',       flag('["--branch"]', value='"required"')),
   ('extra',        flag('["--extra"]', value='"required"', repeated='true')),
   ('no_install_project', flag('["--no-install-project"]')),
  ] + ADD_COMMON + idx() + RES_ALL + EXN + INS + BLD + REF + PY,
  comment='''`uv add` edits pyproject.toml, then locks and syncs. `--frozen` skips the lock and `--locked` asserts it,
but both still edit pyproject.toml, so neither removes `modify_project`.''')

action('remove', f'{G} remove [options] [--] <packages>...',
  adds=['modify_project', 'network', 'modify_environment', 'build_code'],
  opts=ADD_COMMON + idx() + RES_ALL + EXN + INS + BLD + REF + PY)

action('sync', f'{G} sync [options]',
  adds=['modify_environment', 'modify_project', 'network', 'build_code'],
  opts=EXTRAS + GROUPS + [
   ('inexact',            flag('["--inexact"]')),
   ('active',             flag('["--active"]')),
   ('no_install_project', flag('["--no-install-project"]')),
   ('no_install_workspace', flag('["--no-install-workspace"]')),
   ('no_install_package', flag('["--no-install-package"]', value='"required"', repeated='true')),
   ('dry_run',            flag('["--dry-run"]', removes=L('modify_environment', 'modify_project'))),
   ('check',              flag('["--check"]', removes=L('modify_environment', 'modify_project'))),
   ('all_packages',       flag('["--all-packages"]')),
   ('package',            flag('["--package"]', value='"required"', repeated='true')),
   ('script',             flag('["--script"]', value='"required"')),
  ] + LOCKMODE(['modify_project'], ['modify_project']) + idx() + RES_ALL + EXN + INS + BLD + REF + PY,
  comment='''`uv sync` may update uv.lock, then installs into the project environment. `--locked` and `--frozen`
keep uv.lock unchanged. `--dry-run` and `--check` change neither the lockfile nor the environment.''')

action('lock', f'{G} lock [options]',
  adds=['modify_project', 'network', 'build_code'],
  opts=[
   ('check',        flag('["--check"]', removes=L('modify_project'))),
   ('check_exists', flag('["--check-exists"]', removes=L('modify_project'))),
   ('dry_run',      flag('["--dry-run"]', removes=L('modify_project'))),
   ('script',       flag('["--script"]', value='"required"')),
  ] + idx() + RES_ALL + EXN + BLD + REF + PY)

action('tree', f'{G} tree [options]',
  adds=['modify_project', 'network', 'build_code'],
  opts=GROUPS + [
   ('universal', flag('["--universal"]')),
   ('format',    flag('["--format"]', value='"required"')),
   ('depth',     flag('["-d", "--depth"]', value='"required"')),
   ('prune',     flag('["--prune"]', value='"required"', repeated='true')),
   ('package',   flag('["--package"]', value='"required"', repeated='true')),
   ('no_dedupe', flag('["--no-dedupe"]')),
   ('invert',    flag('["--invert"]')),
   ('outdated',  flag('["--outdated"]')),
   ('script',    flag('["--script"]', value='"required"')),
  ] + LOCKMODE(['modify_project'], ['modify_project']) + idx() + RES_ALL + EXN + BLD + PY,
  comment='''`uv tree` locks the project first (it may write uv.lock); `--frozen` and `--locked` keep uv.lock unchanged.''')

action('export', f'{G} export [options]',
  adds=['modify_project', 'network', 'build_code'],
  opts=EXTRAS + GROUPS + [
   ('format',          flag('["--format"]', value='"required"')),
   ('all_packages',    flag('["--all-packages"]')),
   ('package',         flag('["--package"]', value='"required"', repeated='true')),
   ('no_hashes',       flag('["--no-hashes"]')),
   ('no_header',       flag('["--no-header"]')),
   ('no_annotate',     flag('["--no-annotate"]')),
   ('no_emit_project', flag('["--no-emit-project"]')),
   ('output_file',     flag('["-o", "--output-file"]', value='"required"', adds=WF)),
   ('script',          flag('["--script"]', value='"required"')),
  ] + LOCKMODE(['modify_project'], ['modify_project']) + idx() + RES_ALL + EXN + BLD + REF + PY)

action('venv', f'{G} venv [options] [<path>]',
  aliases=['virtualenv', 'v'],
  adds=['modify_environment', 'network'],
  opts=[
   ('no_project',           flag('["--no-project"]')),
   ('seed',                 flag('["--seed"]')),
   ('clear',                flag('["-c", "--clear"]', adds=L('delete_data'))),
   ('allow_existing',       flag('["--allow-existing"]')),
   ('prompt',               flag('["--prompt"]', value='"required"')),
   ('system_site_packages', flag('["--system-site-packages"]')),
   ('relocatable',          flag('["--relocatable"]')),
  ] + idx() + EXN + REF + PY,
  operands=[('path', '{ adds = ["write_file"] }')],
  comment='''`uv venv` creates an environment and may download a Python. `--clear` removes what is at the path.''')

action('build', f'{G} build [options] [<src>]',
  adds=['build_code', 'network'],
  opts=[
   ('package',       flag('["--package"]', value='"required"')),
   ('all_packages',  flag('["--all-packages"]')),
   ('out_dir',       flag('["-o", "--out-dir"]', value='"required"', adds=WF)),
   ('sdist',         flag('["--sdist"]')),
   ('wheel',         flag('["--wheel"]')),
   ('no_build_logs', flag('["--no-build-logs"]')),
   ('clear',         flag('["--clear"]', adds=L('delete_data'))),
  ] + idx() + RES_ALL + EXN + BLD + REF + PY)

action('publish', 'uv [global options] publish [options] [<files>...]',
  adds=['publish', 'network'],
  opts=[
   ('offline',            flag('["--offline"]', overrides='true')),
   ('index',              flag('["--index"]', value='"required"', adds=L('override_index'))),
   ('username',           flag('["-u", "--username"]', value='"required"')),
   ('password',           flag('["-p", "--password"]', value='"required"', adds=L('credentials'))),
   ('token',              flag('["-t", "--token"]', value='"required"', adds=L('credentials'))),
   ('trusted_publishing', flag('["--trusted-publishing"]', value='"required"')),
   ('publish_url',        flag('["--publish-url"]', value='"required"', adds=L('override_index'), when=f'[{CRED}]')),
   ('check_url',          flag('["--check-url"]', value='"required"', adds=L('override_index'), when=f'[{CRED}]')),
   ('dry_run',            flag('["--dry-run"]', removes=L('publish'))),
   ('no_attestations',    flag('["--no-attestations"]')),
  ],
  comment='''`uv publish` declares a hidden `--offline` of its own that shadows the global one (uv 0.13.7,
crates/uv-cli/src/lib.rs `PublishArgs::offline`), so a global `--offline` could not truthfully remove
`network` here. Its own `offline` option takes the place of the global one (`overrides`), and removes nothing.''')

action('version', f'{G} version [options] [<value>]',
  adds=['read_only'],
  opts=[
   ('bump',          flag('["--bump"]', value='"required"', repeated='true', adds=L('modify_project', 'network', 'modify_environment', 'build_code'), removes=L('read_only'))),
   ('dry_run',       flag('["--dry-run"]', removes=L('modify_project', 'network', 'modify_environment', 'build_code'))),
   ('short',         flag('["--short"]')),
   ('output_format', flag('["--output-format"]', value='"required"')),
   ('no_sync',       flag('["--no-sync"]', removes=L('modify_environment'))),
   ('active',        flag('["--active"]')),
   ('locked',        flag('["--locked"]')),
   ('frozen',        flag('["--frozen"]')),
   ('package',       flag('["--package"]', value='"required"')),
  ] + idx() + RES_ALL + EXN + INS + BLD + REF + PY,
  operands=[('value', '{ adds = ["modify_project", "network", "modify_environment", "build_code"], removes = ["read_only"] }')],
  comment='''`uv version` alone reads the project version. A `<value>` or `--bump` writes pyproject.toml, then
locks and syncs; `--dry-run` writes nothing and skips the lock and sync (crates/uv-project-commands/src/version.rs).''')

# ---------------- tool ----------------
TOOLRUN_COMMON = [
   ('with',              flag('["-w", "--with"]', value='"required"', repeated='true')),
   ('with_editable',     flag('["--with-editable"]', value='"required"', repeated='true')),
   ('with_requirements', flag('["--with-requirements"]', value='"required"', repeated='true')),
   ('constraints',       flag('["-c", "--constraints"]', value='"required"', repeated='true')),
   ('overrides',         flag('["--overrides"]', value='"required"', repeated='true')),
]
action('tool_run', f'{G} tool run [options] <command>...',
  adds=['run_program', 'network', 'modify_environment', 'build_code'],
  opts=[('from', flag('["--from"]', value='"required"'))] + TOOLRUN_COMMON + [
   ('isolated',    flag('["--isolated"]')),
   ('env_file',    flag('["--env-file"]', value='"required"', repeated='true')),
   ('no_env_file', flag('["--no-env-file"]')),
  ] + idx() + RES_ALL + EXN + INS + BLD + REF + PY,
  operands=[('command', '{ rest = true }')],
  comment='''`uv tool run` installs a package into a cached environment and runs its command. `uvx` is a separate
executable and this grammar does not bind it.''')

action('tool_install', f'{G} tool install [options] <package>',
  adds=['modify_user', 'network', 'build_code'],
  opts=[
   ('editable', flag('["-e", "--editable"]')),
   ('force',    flag('["--force"]')),
  ] + TOOLRUN_COMMON + idx() + RES_ALL + EXN + INS + BLD + REF + PY)

action('tool_uninstall', f'{G} tool uninstall [options] [<name>...]',
  adds=['modify_user', 'delete_data'],
  opts=[('all', flag('["--all"]'))])

action('tool_upgrade', f'{G} tool upgrade [options] [<name>...]',
  aliases=['tool update'],
  adds=['modify_user', 'network', 'build_code'],
  opts=[('all', flag('["--all"]'))] + idx() + RES_ALL[2:] + EXN + INS + BLD + PY)

action('tool_list', f'{G} tool list [options]',
  aliases=['tool ls'],
  adds=['read_only'],
  opts=[
   ('show_paths',              flag('["--show-paths"]')),
   ('show_version_specifiers', flag('["--show-version-specifiers"]')),
   ('show_with',               flag('["--show-with"]')),
   ('show_extras',             flag('["--show-extras"]')),
   ('show_python',             flag('["--show-python"]')),
   ('outdated',                flag('["--outdated"]', adds=L('network'))),
  ])

action('tool_dir', f'{G} tool dir [options]', adds=['read_only'], opts=[('bin', flag('["--bin"]'))])

action('tool_update_shell', f'{G} tool update-shell',
  aliases=['tool ensurepath'], adds=['modify_user'],
  comment='Adds the tool executable directory to PATH in the shell configuration files.')

# ---------------- python ----------------
action('python_list', f'{G} python list [options] [<request>]',
  aliases=['python ls'], adds=['read_only'],
  opts=[
   ('all_versions',   flag('["--all-versions"]')),
   ('all_platforms',  flag('["--all-platforms"]')),
   ('all_arches',     flag('["--all-arches"]')),
   ('only_installed', flag('["--only-installed"]')),
   ('only_downloads', flag('["--only-downloads"]')),
   ('show_urls',      flag('["--show-urls"]')),
   ('output_format',  flag('["--output-format"]', value='"required"')),
  ],
  operands=[('request', '{ adds = ["run_program"], removes = ["read_only"] }')],
  comment='''A `<request>` is passed to `find_all_python_installations`, which queries the file it names, so it
adds `run_program` (crates/uv-python-commands/src/list.rs).
`uv python list` reads the download list built into uv. `--python-downloads-json-url` can fetch one,
so it is not declared and makes the line `unmodeled`.''')

action('python_install', f'{G} python install [options] [<targets>...]',
  adds=['modify_user', 'network'],
  opts=[
   ('install_dir',      flag('["-i", "--install-dir"]', value='"required"', adds=WF)),
   ('no_bin',           flag('["--no-bin"]')),
   ('reinstall',        flag('["-r", "--reinstall"]')),
   ('force',            flag('["-f", "--force"]')),
   ('upgrade',          flag('["-U", "--upgrade"]')),
   ('default',          flag('["--default"]')),
   ('compile_bytecode', flag('["--compile-bytecode"]')),
  ],
  comment='''Mirror and download-list options (`--mirror`, `--python-downloads-json-url`, ...) choose where Python
comes from; they are not declared.''')

action('python_upgrade', f'{G} python upgrade [options] [<targets>...]',
  adds=['modify_user', 'network'],
  opts=[
   ('install_dir', flag('["-i", "--install-dir"]', value='"required"', adds=WF)),
   ('reinstall',   flag('["-r", "--reinstall"]')),
  ])

action('python_find', f'{G} python find [options] [<request>]',
  adds=['read_only'],
  opts=[
   ('no_project',    flag('["--no-project"]')),
   ('system',        flag('["--system"]')),
   ('script',        flag('["--script"]', value='"required"', adds=L('network', 'modify_user'), removes=L('read_only'))),
   ('show_version',  flag('["--show-version"]')),
   ('resolve_links', flag('["--resolve-links"]')),
  ],
  operands=[('request', '{ adds = ["run_program"], removes = ["read_only"] }')],
  comment='''`uv python find <request>` executes the interpreter that the request names to query it, and a bare
name is looked up on PATH, so a request adds `run_program`. `--script` may download and install the
Python the script needs (`ScriptInterpreter::discover` -> `PythonInstallation::find_or_download`).''')

action('python_pin', f'{G} python pin [options] [<request>]',
  adds=['read_only'],
  opts=[
   ('resolved',   flag('["--resolved"]')),
   ('no_project', flag('["--no-project"]')),
   ('global',     flag('["--global"]', adds=L('modify_user'), removes=L('modify_project', 'read_only'))),
   ('rm',         flag('["--rm"]', adds=L('modify_project', 'delete_data'), removes=L('read_only'))),
  ],
  operands=[('request', '{ adds = ["modify_project", "network", "run_program"], removes = ["read_only"] }')],
  comment='''`uv python pin` alone shows the pin. A `<request>` writes .python-version and may download a Python
(`find_or_download` in crates/uv-python-commands/src/pin.rs); `--rm` deletes the pin. `--global` acts on the
user-level pin instead of the project, so it adds `modify_user` even when it only shows the pin.''')

action('python_uninstall', f'{G} python uninstall [options] [<targets>...]',
  adds=['modify_user', 'delete_data'],
  opts=[
   ('install_dir', flag('["-i", "--install-dir"]', value='"required"', adds=WF)),
   ('all',         flag('["--all"]')),
  ])

action('python_dir', f'{G} python dir [options]', adds=['read_only'], opts=[('bin', flag('["--bin"]'))])

action('python_update_shell', f'{G} python update-shell',
  aliases=['python ensurepath'], adds=['modify_user'])

# ---------------- pip ----------------
TARGET = [
   ('system',  flag('["--system"]', adds=L('system_python'))),
   ('target',  flag('["-t", "--target"]', value='"required"', adds=WF)),
   ('prefix',  flag('["--prefix"]', value='"required"', adds=WF)),
]
SYSMOD = TARGET + [('break_system_packages', flag('["--break-system-packages"]', adds=L('system_python')))]
TARGET_RO = [
   ('system',  flag('["--system"]')),
   ('target',  flag('["-t", "--target"]', value='"required"')),
   ('prefix',  flag('["--prefix"]', value='"required"')),
]
action('pip_install', f'{G} pip install [options] [--] [<package>...]',
  adds=['modify_environment', 'network', 'build_code'],
  opts=[
   ('requirements', flag('["-r", "--requirements"]', value='"required"', repeated='true')),
   ('editable',     flag('["-e", "--editable"]', value='"required"', repeated='true')),
   ('constraints',  flag('["-c", "--constraints"]', value='"required"', repeated='true')),
   ('overrides',    flag('["--overrides"]', value='"required"', repeated='true')),
   ('extra',        flag('["--extra"]', value='"required"', repeated='true')),
   ('all_extras',   flag('["--all-extras"]')),
   ('group',        flag('["--group"]', value='"required"', repeated='true')),
   ('no_deps',      flag('["--no-deps"]')),
   ('require_hashes', flag('["--require-hashes"]')),
   ('exact',        flag('["--exact"]')),
   ('strict',       flag('["--strict"]')),
   ('dry_run',      flag('["--dry-run"]', removes=L('modify_environment'))),
   ('check',        flag('["--check"]', removes=L('modify_environment'))),
  ] + SYSMOD + idx() + RES_ALL + EXN + INS + BLD + REF + PY_SYS,
  comment='''`--no-build` does not remove `build_code`: uv still builds editable requirements
(the `--no-build` doc comment in crates/uv-cli/src/lib.rs, uv 0.13.7).''')

action('pip_sync', f'{G} pip sync [options] <src_file>...',
  adds=['modify_environment', 'network', 'build_code'],
  opts=[
   ('constraints',    flag('["-c", "--constraints"]', value='"required"', repeated='true')),
   ('extra',          flag('["--extra"]', value='"required"', repeated='true')),
   ('all_extras',     flag('["--all-extras"]')),
   ('group',          flag('["--group"]', value='"required"', repeated='true')),
   ('require_hashes', flag('["--require-hashes"]')),
   ('strict',         flag('["--strict"]')),
   ('dry_run',        flag('["--dry-run"]', removes=L('modify_environment'))),
   ('check',          flag('["--check"]', removes=L('modify_environment'))),
  ] + SYSMOD + idx() + EXN + INS + BLD + REF + PY_SYS)

action('pip_compile', f'{G} pip compile [options] [<src_file>...]',
  adds=['network', 'build_code'],
  opts=[
   ('constraints',     flag('["-c", "--constraints"]', value='"required"', repeated='true')),
   ('overrides',       flag('["--overrides"]', value='"required"', repeated='true')),
   ('extra',           flag('["--extra"]', value='"required"', repeated='true')),
   ('all_extras',      flag('["--all-extras"]')),
   ('group',           flag('["--group"]', value='"required"', repeated='true')),
   ('no_deps',         flag('["--no-deps"]')),
   ('output_file',     flag('["-o", "--output-file"]', value='"required"', adds=WF)),
   ('format',          flag('["--format"]', value='"required"')),
   ('universal',       flag('["--universal"]')),
   ('generate_hashes', flag('["--generate-hashes"]')),
   ('no_header',       flag('["--no-header"]')),
   ('no_annotate',     flag('["--no-annotate"]')),
   ('python_version',  flag('["--python-version"]', value='"required"')),
  ] + idx() + RES_ALL + EXN + BLD + REF + PY)

action('pip_uninstall', f'{G} pip uninstall [options] [--] [<package>...]',
  adds=['modify_environment', 'delete_data'],
  opts=[
   ('requirements', flag('["-r", "--requirements"]', value='"required"', repeated='true')),
   ('dry_run',      flag('["--dry-run"]', removes=L('modify_environment', 'delete_data'))),
  ] + SYSMOD + PY_SYS)

action('pip_list', f'{G} pip list [options]',
  aliases=['pip ls'], adds=['read_only'],
  opts=[
   ('editable',         flag('["-e", "--editable"]')),
   ('exclude_editable', flag('["--exclude-editable"]')),
   ('exclude',          flag('["--exclude"]', value='"required"', repeated='true')),
   ('format',           flag('["--format"]', value='"required"')),
   ('outdated',         flag('["--outdated"]', adds=L('network'))),
   ('strict',           flag('["--strict"]')),
  ] + TARGET_RO + PY)

action('pip_show', f'{G} pip show [options] [<package>...]',
  adds=['read_only'],
  opts=[('strict', flag('["--strict"]')), ('files', flag('["-f", "--files"]'))] + TARGET_RO + PY)

action('pip_freeze', f'{G} pip freeze [options]',
  adds=['read_only'],
  opts=[
   ('exclude_editable', flag('["--exclude-editable"]')),
   ('exclude',          flag('["--exclude"]', value='"required"', repeated='true')),
   ('strict',           flag('["--strict"]')),
   ('path',             flag('["--path"]', value='"required"', repeated='true')),
  ] + TARGET_RO + PY)

action('pip_check', f'{G} pip check [options]',
  adds=['read_only'],
  opts=[('system', flag('["--system"]')), ('python_version', flag('["--python-version"]', value='"required"'))] + PY)

action('pip_tree', f'{G} pip tree [options]',
  adds=['read_only'],
  opts=[
   ('show_version_specifiers', flag('["--show-version-specifiers"]')),
   ('depth',     flag('["-d", "--depth"]', value='"required"')),
   ('prune',     flag('["--prune"]', value='"required"', repeated='true')),
   ('package',   flag('["--package"]', value='"required"', repeated='true')),
   ('no_dedupe', flag('["--no-dedupe"]')),
   ('invert',    flag('["--invert"]')),
   ('outdated',  flag('["--outdated"]', adds=L('network'))),
   ('strict',    flag('["--strict"]')),
   ('system',    flag('["--system"]')),
  ] + PY)

# ---------------- cache ----------------
action('cache_clean', f'{G} cache clean [options] [<package>...]',
  aliases=['cache clear'], adds=['delete_data'], opts=[('force', flag('["--force"]'))])
action('cache_prune', f'{G} cache prune [options]',
  adds=['delete_data'], opts=[('ci', flag('["--ci"]')), ('force', flag('["--force"]'))])
action('cache_dir', f'{G} cache dir', adds=['read_only'])
action('cache_size', f'{G} cache size [options]', adds=['read_only'],
  opts=[('human', flag('["-H", "--human", "--human-readable"]'))])

# ---------------- self ----------------
action('self_update', f'{G} self update [options] [<target_version>]',
  adds=['modify_user', 'network'],
  opts=[
   ('token',   flag('["--token"]', value='"required"', adds=L('credentials'))),
   ('dry_run', flag('["--dry-run"]', removes=L('modify_user'))),
  ],
  comment='''`uv self update` replaces the uv executable. Box refuses a grammar whose program file changed
until the box restarts.''')
action('self_version', f'{G} self version [options]', adds=['read_only'],
  opts=[('short', flag('["--short"]')), ('output_format', flag('["--output-format"]', value='"required"'))])

here = pathlib.Path(__file__).resolve().parent
head = (here / 'head.toml').read_text()
(here.parent / 'uv.grammar.toml').write_text(head.rstrip('\n') + '\n' + '\n'.join(out) + '\n')
