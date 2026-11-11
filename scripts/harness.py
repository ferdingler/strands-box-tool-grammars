#!/usr/bin/env python3
"""Validate the grammars in this collection with the real Box implementation.

Subcommands:
  validate [CLI ...]   Level 1: Box's loader, parser, policy engine, and fuzz tests.
  e2e [CLI ...]        Level 2: a real `strands-box run` with each grammar and a stub program.
  render CLI           Print the `[tool.<name>]` table that loads one grammar in box.toml.

With no CLI, each command takes every directory under grammars/.
Python 3.11 or later. No package outside the standard library.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRAMMARS = ROOT / "grammars"
PREFIX = "collection-"
DEFAULT_BOX_URL = "https://github.com/strands-agents/box.git"
CLI_NAME = re.compile(r"^[a-z0-9_][a-z0-9_-]*$")

LOAD_TESTS = [
    "grammar::tests::every_grammar_in_the_corpus_loads_or_is_refused_as_it_expects",
]
CASE_TESTS = [
    "grammar::schema::tests::every_valid_grammar_composes_with_the_canonical_and_an_mcp_schema_and_loads_in_dogwood",
    "grammar::corpus::every_corpus_case_parses_to_its_action_fields_and_effects",
    "grammar::corpus::every_corpus_case_is_typed_and_decided_by_the_policy_engine",
    "grammar::fuzz::every_corpus_argv_holds_each_parser_invariant",
    "grammar::fuzz::a_generated_argv_holds_each_parser_invariant",
]
SHORT_NAMES = {
    LOAD_TESTS[0]: "load",
    CASE_TESTS[0]: "schema",
    CASE_TESTS[1]: "corpus-parse",
    CASE_TESTS[2]: "corpus-engine",
    CASE_TESTS[3]: "fuzz-corpus",
    CASE_TESTS[4]: "fuzz-generated",
}

# Rules that every e2e box gets, so the agent can reach the Shell. They are harness scaffolding.
E2E_BASE_POLICY = """\
@id("e2e_shell_exec")
permit (principal, action == Box::Action::"shell:exec", resource);
"""

STUB = """\
#!/bin/sh
# A stand-in for a real program. It prints its arguments and exits 0.
printf 'stub-argv:'
for word in "$@"; do printf ' [%s]' "$word"; done
printf '\\n'
exit 0
"""


class HarnessError(Exception):
    pass


def say(message: str = "") -> None:
    print(message, flush=True)


# ---------------------------------------------------------------- settings


def box_revision() -> str:
    path = ROOT / "BOX_REVISION"
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            if not re.fullmatch(r"[0-9a-f]{40}", line):
                raise HarnessError(f"{path}: {line!r} is not a 40-character commit id")
            return line
    raise HarnessError(f"{path} holds no commit id")


def cache_dir() -> Path:
    path = Path(os.environ.get("SBTG_CACHE", ROOT / ".cache")).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def target_dir(level: str) -> Path:
    """One target directory per level: the two builds unify features differently and evict each other."""
    base = Path(os.environ.get("CARGO_TARGET_DIR", cache_dir() / "target")).expanduser().resolve()
    return base / level


def profile() -> str:
    value = os.environ.get("SBTG_PROFILE", "release")
    if value not in ("release", "debug"):
        raise HarnessError(f"SBTG_PROFILE is {value!r}; use release or debug")
    return value


def run(command: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command, text=True, **kwargs)


# ---------------------------------------------------------------- the Box copy


def box_source(revision: str) -> Path:
    """A git repository that holds `revision`: BOX_SRC, or a bare clone in the cache."""
    given = os.environ.get("BOX_SRC")
    if given:
        repository = Path(given).expanduser().resolve()
        found = run(["git", "-C", str(repository), "cat-file", "-e", f"{revision}^{{commit}}"],
                    capture_output=True)
        if found.returncode != 0:
            raise HarnessError(
                f"BOX_SRC={repository} does not hold commit {revision}; fetch it there, "
                "or unset BOX_SRC to let the harness fetch it")
        return repository
    repository = cache_dir() / "box.git"
    if not repository.exists():
        run(["git", "init", "--quiet", "--bare", str(repository)], check=True)
    found = run(["git", "-C", str(repository), "cat-file", "-e", f"{revision}^{{commit}}"],
                capture_output=True)
    if found.returncode != 0:
        url = os.environ.get("BOX_URL", DEFAULT_BOX_URL)
        say(f"fetching Box {revision} from {url}")
        run(["git", "-C", str(repository), "fetch", "--quiet", "--depth", "1", url, revision],
            check=True)
    return repository


def box_copy() -> Path:
    """A throwaway copy of the Box sources at BOX_REVISION, made once and kept in the cache."""
    revision = box_revision()
    copy = cache_dir() / f"box-{revision[:12]}"
    marker = copy / ".sbtg-complete"
    if marker.exists():
        return copy
    with (cache_dir() / "extract.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not marker.exists():
            extract(revision, copy)
    return copy


def extract(revision: str, copy: Path) -> None:
    repository = box_source(revision)
    partial = copy.with_name(copy.name + ".partial")
    shutil.rmtree(partial, ignore_errors=True)
    partial.mkdir(parents=True)
    say(f"extracting Box {revision[:12]} to {copy}")
    archive = subprocess.Popen(["git", "-C", str(repository), "archive", revision],
                               stdout=subprocess.PIPE)
    run(["tar", "-x", "-C", str(partial)], stdin=archive.stdout, check=True)
    if archive.wait() != 0:
        raise HarnessError(f"git archive {revision} failed")
    (partial / ".sbtg-complete").write_text(revision + "\n")
    shutil.rmtree(copy, ignore_errors=True)
    partial.rename(copy)


def fixture_dirs(copy: Path) -> tuple[Path, Path]:
    base = copy / "crates" / "policy" / "tests" / "grammars"
    return base / "valid", base / "corpus"


def clear_fixtures(copy: Path) -> None:
    for directory in fixture_dirs(copy):
        for path in directory.glob(PREFIX + "*"):
            path.unlink()


def install_fixtures(copy: Path, clis: list[str]) -> None:
    """Add each grammar to valid/ and each corpus to corpus/ as `collection-<cli>.*.toml`."""
    clear_fixtures(copy)
    valid, corpus = fixture_dirs(copy)
    for cli in clis:
        shutil.copyfile(grammar_file(cli), valid / f"{PREFIX}{cli}.grammar.toml")
        shutil.copyfile(corpus_file(cli), corpus / f"{PREFIX}{cli}.corpus.toml")


# ---------------------------------------------------------------- the collection


def grammar_file(cli: str) -> Path:
    return GRAMMARS / cli / f"{cli}.grammar.toml"


def corpus_file(cli: str) -> Path:
    return GRAMMARS / cli / f"{cli}.corpus.toml"


def e2e_file(cli: str) -> Path:
    return GRAMMARS / cli / f"{cli}.e2e.toml"


def every_cli() -> list[str]:
    return sorted(path.name for path in GRAMMARS.iterdir()
                  if path.is_dir() and grammar_file(path.name).exists())


def chosen(clis: list[str]) -> list[str]:
    names = clis or every_cli()
    for cli in names:
        if not CLI_NAME.match(cli):
            raise HarnessError(f"{cli!r}: a CLI directory name is lowercase letters, digits, `_`, `-`")
        if not grammar_file(cli).exists():
            raise HarnessError(f"{grammar_file(cli).relative_to(ROOT)} does not exist")
    if not names:
        raise HarnessError("grammars/ holds no grammar")
    return names


def read_toml(path: Path) -> dict:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as error:
        raise HarnessError(f"{path.relative_to(ROOT)}: not valid TOML: {error}") from None


def precheck(cli: str) -> list[str]:
    """Problems the harness reports before Box runs, so the Box output stays about grammars."""
    problems = []
    try:
        read_toml(grammar_file(cli))
    except HarnessError as error:
        problems.append(str(error))
    if not corpus_file(cli).exists():
        problems.append(f"{corpus_file(cli).relative_to(ROOT)} does not exist; "
                        "a grammar needs at least one corpus case")
        return problems
    try:
        corpus = read_toml(corpus_file(cli))
        if not corpus.get("case"):
            problems.append(f"{corpus_file(cli).relative_to(ROOT)} holds no [[case]]")
    except HarnessError as error:
        problems.append(str(error))
    return problems


# ---------------------------------------------------------------- Level 1


def cargo_test(copy: Path, tests: list[str]) -> subprocess.CompletedProcess:
    command = ["cargo", "test"]
    if profile() == "release":
        command.append("--release")
    command += ["-p", "strands-box-policy", "--all-features", "--lib", "--", "--exact", *tests]
    env = dict(os.environ, CARGO_TARGET_DIR=str(target_dir("level1")))
    return run(command, cwd=copy, env=env, capture_output=True)


def readable(text: str) -> str:
    """Name each collection file by its place in this repository, not in the Box copy."""
    text = re.sub(r"\S*/(?:valid|corpus)/" + PREFIX + r"([a-z0-9_-]+)\.(grammar|corpus)\.toml",
                  r"grammars/\1/\1.\2.toml", text)
    text = re.sub(r"(?:valid/)?" + PREFIX + r"([a-z0-9_-]+)\.(grammar|corpus)\.toml",
                  r"grammars/\1/\1.\2.toml", text)
    return text


def failures(output: str) -> dict[str, str]:
    """The panic message of each failed test, by test name."""
    found = {}
    sections = re.split(r"^---- (\S+) stdout ----$", output, flags=re.MULTILINE)
    for name, body in zip(sections[1::2], sections[2::2]):
        body = body.split("\nfailures:\n", 1)[0]
        lines = []
        for line in body.splitlines():
            if line.startswith("note: run with `RUST_BACKTRACE"):
                break
            if line.startswith("thread '") and "panicked at" in line:
                continue
            lines.append(line)
        found[name] = "\n".join(lines).strip("\n")
    return found


def records(test: str, message: str) -> list[str]:
    """Split one test's failure message into one record per failure."""
    if test in (LOAD_TESTS[0],):
        return [part.strip() for part in re.split(r"\n\s*\n", message) if part.strip()]
    if test.startswith("grammar::fuzz::"):
        return [message.strip()]
    parts: list[str] = []
    for line in message.splitlines():
        if not line.strip():
            continue
        if line[0].isspace() and parts:
            parts[-1] += "\n" + line
        else:
            parts.append(line)
    return parts


def owner(record: str, clis: list[str]) -> str | None:
    for cli in clis:
        if f"{PREFIX}{cli}." in record:
            return cli
    return None


def run_level1(copy: Path, clis: list[str], tests: list[str],
               results: dict[str, list[str]]) -> tuple[set[str], list[str]]:
    """Run `tests`, file each failure under its CLI, and return the failing CLIs."""
    completed = cargo_test(copy, tests)
    output = completed.stdout + completed.stderr
    if "test result:" not in output:
        raise HarnessError("cargo test did not run the tests:\n" + output[-4000:])
    failed: set[str] = set()
    unowned: list[str] = []
    found = failures(completed.stdout)
    for test, message in found.items():
        short = SHORT_NAMES.get(test, test)
        for record in records(test, message):
            cli = owner(record, clis)
            text = f"[{short}] {readable(record)}"
            if cli is None:
                unowned.append(text)
            else:
                failed.add(cli)
                results.setdefault(cli, []).append(text)
    if completed.returncode != 0 and not found:
        unowned.append(output[-4000:])
    return failed, unowned


def validate(clis: list[str]) -> int:
    started = time.monotonic()
    clis = chosen(clis)
    results: dict[str, list[str]] = {}
    for cli in clis:
        for problem in precheck(cli):
            results.setdefault(cli, []).append(f"[precheck] {problem}")
    ready = [cli for cli in clis if cli not in results]
    copy = box_copy()
    say(f"Box {box_revision()[:12]} at {copy} ({profile()} profile)")
    unowned: list[str] = []
    lock = (cache_dir() / f"{copy.name}.lock").open("w")
    if ready:
        # One run at a time owns the copy's fixture directories.
        fcntl.flock(lock, fcntl.LOCK_EX)
        install_fixtures(copy, ready)
        say(f"level 1, load: {' '.join(ready)}")
        failed, more = run_level1(copy, ready, LOAD_TESTS, results)
        unowned += more
        loaded = [cli for cli in ready if cli not in failed]
        if loaded:
            install_fixtures(copy, loaded)
            say(f"level 1, cases and fuzz: {' '.join(loaded)}")
            _, more = run_level1(copy, loaded, CASE_TESTS, results)
            unowned += more
        clear_fixtures(copy)
    say()
    for cli in clis:
        cases = len(read_toml(corpus_file(cli)).get("case", [])) if corpus_file(cli).exists() else 0
        if cli in results:
            say(f"FAIL {cli} ({cases} cases)")
            for text in results[cli]:
                say("  " + text.replace("\n", "\n    "))
        else:
            say(f"PASS {cli} ({cases} cases)")
    if unowned:
        say("\nFailures that name no collection file (a Box fixture or the harness):")
        for text in unowned:
            say("  " + text.replace("\n", "\n    "))
    say(f"\nlevel 1 finished in {time.monotonic() - started:.1f}s")
    return 1 if results or unowned else 0


# ---------------------------------------------------------------- box.toml rendering


def toml_key(key: str) -> str:
    return key if re.fullmatch(r"[A-Za-z0-9_-]+", key) else json.dumps(key)


def toml_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{toml_key(k)} = {toml_value(v)}" for k, v in value.items()) + " }"
    raise HarnessError(f"cannot write {value!r} as TOML")


def toml_table(table: dict, header: str) -> str:
    """`table` as TOML under `[header]`; `options` and `operands` entries stay inline."""
    lines = [f"[{header}]"]
    nested = []
    for key, value in table.items():
        if isinstance(value, dict) and key in ("options", "operands"):
            for name, entry in value.items():
                lines.append(f"{toml_key(key)}.{toml_key(name)} = {toml_value(entry)}")
        elif isinstance(value, dict):
            nested.append((key, value))
        else:
            lines.append(f"{toml_key(key)} = {toml_value(value)}")
    text = "\n".join(lines) + "\n" if len(lines) > 1 or not nested else ""
    for key, value in nested:
        text += ("\n" if text else "") + toml_table(value, f"{header}.{toml_key(key)}")
    return text


def render_tool(cli: str, label: str | None, command: str | None) -> str:
    grammar = read_toml(grammar_file(cli))
    label = label or grammar["name"]
    command = command or grammar["program"]
    return (f"[tool.{toml_key(label)}]\ncommand = {toml_value([command])}\n\n"
            + toml_table(grammar, f"tool.{toml_key(label)}.grammar"))


def render(cli: str, label: str | None, command: str | None) -> int:
    chosen([cli])
    say("[experimental-features]\ntool-grammars = true\n")
    say(render_tool(cli, label, command).rstrip("\n"))
    return 0


# ---------------------------------------------------------------- Level 2


def build_box(copy: Path) -> Path:
    command = ["cargo", "build"]
    if profile() == "release":
        command.append("--release")
    command += ["-p", "strands-box", "-p", "strands-box-containment", "--bins"]
    env = dict(os.environ, CARGO_TARGET_DIR=str(target_dir("level2")))
    completed = run(command, cwd=copy, env=env, capture_output=True)
    if completed.returncode != 0:
        raise HarnessError("building strands-box failed:\n" + completed.stderr[-4000:])
    binary = target_dir("level2") / profile() / "strands-box"
    if not binary.exists():
        raise HarnessError(f"{binary} is missing after the build")
    return binary


def shell_words(argv: list[str]) -> str:
    return " ".join("'" + word.replace("'", "'\\''") + "'" for word in argv)


def e2e_box(work: Path, number: int, cli: str, policy: str, stubs: Path) -> Path:
    """Write one box: its config, its policy, and an empty box directory. Return the config."""
    grammar = read_toml(grammar_file(cli))
    box_dir = work / f"b{number}"
    box_dir.mkdir(mode=0o700)
    config_dir = work / f"c{number}"
    config_dir.mkdir()
    home = work / "agent-home"
    (home / ".tmp").mkdir(parents=True, exist_ok=True)
    home.chmod(0o700)
    workspace = work / "workspace"
    workspace.mkdir(exist_ok=True)
    program = stubs / grammar["program"]
    label = grammar["name"]
    tool = render_tool(cli, label, str(program))
    tool = tool.replace(f"[tool.{toml_key(label)}.grammar]",
                        f"[tool.{toml_key(label)}.filesystem]\nread = {toml_value([str(stubs)])}\n"
                        f"read_file = {toml_value([os.path.realpath('/bin/sh')])}\n\n"
                        f"[tool.{toml_key(label)}.grammar]", 1)
    config = (
        f"name = {toml_value(f'grammar-e2e-{number}')}\n"
        f"box_dir = {toml_value(str(box_dir))}\n"
        'policy = "policy.dw"\n\n'
        "[agent]\n"
        'command = ["/bin/bash"]\n'
        f"workspace = {toml_value(str(workspace))}\n"
        f"env = {{ HOME = {toml_value(str(home))}, TMPDIR = {toml_value(str(home / '.tmp'))} }}\n\n"
        "[agent.filesystem]\n"
        f"read = {toml_value([str(home)])}\n"
        f"write = {toml_value([str(home)])}\n\n"
        f"{tool}\n"
        "[experimental-features]\n"
        "tool-grammars = true\n"
    )
    (config_dir / "box.toml").write_text(config)
    (config_dir / "policy.dw").write_text(E2E_BASE_POLICY + "\n" + policy)
    return config_dir / "box.toml"


def workload_lines(stderr: str, failed_start: bool) -> str:
    """stderr without the box's startup disclosure, unless the box did not start."""
    if failed_start:
        return stderr.strip()
    kept = []
    disclosure = False
    for line in stderr.splitlines():
        if line.startswith("strands-box: ") and not line.startswith("strands-box: error"):
            disclosure = True
            continue
        if disclosure and line.startswith("  "):
            continue
        disclosure = False
        kept.append(line)
    return "\n".join(kept).strip()


def e2e_one(binary: Path, cli: str, keep: bool) -> tuple[int, int, list[str]]:
    spec = read_toml(e2e_file(cli))
    grammar = read_toml(grammar_file(cli))
    program = grammar["program"]
    cases = spec.get("case", [])
    if not cases:
        return 0, 0, [f"{e2e_file(cli).relative_to(ROOT)} holds no [[case]]"]
    base = Path(os.environ.get("SBTG_E2E_TMP", "/var/tmp"))
    work = Path(tempfile.mkdtemp(prefix="sbg", dir=base)).resolve()
    problems: list[str] = []
    passed = 0
    try:
        stubs = work / "stubs"
        stubs.mkdir()
        stub = stubs / program
        stub.write_text(STUB)
        stub.chmod(stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
        boxes: dict[str, Path] = {}
        env = dict(os.environ, HOME=str(work), PATH=f"{stubs}:/usr/bin:/bin")
        for index, case in enumerate(cases, start=1):
            argv = case.get("argv")
            at = f"{e2e_file(cli).relative_to(ROOT)} case {index} {argv}"
            if not argv or argv[0] != program:
                problems.append(f"{at}: argv must start with the program {program!r}")
                continue
            policy = case.get("policy", spec.get("policy", ""))
            if policy not in boxes:
                boxes[policy] = e2e_box(work, len(boxes) + 1, cli, policy, stubs)
            script = 'zsh -c "$1"; printf "\\n|status=%s\\n" "$?"'
            completed = run([str(binary), "run", "--config", str(boxes[policy]), "--",
                             "-c", script, "bash", shell_words(argv)],
                            env=env, capture_output=True, timeout=120)
            stdout, stderr = completed.stdout, completed.stderr
            status = re.search(r"\|status=(\d+)", stdout)
            got = int(status.group(1)) if status else None
            wrong = []
            if got is None:
                wrong.append(f"the box did not run the command (run exited {completed.returncode})")
            elif got != case.get("exit", 0):
                wrong.append(f"exit: expected {case.get('exit', 0)}, got {got}")
            if "stdout" in case and case["stdout"] not in stdout:
                wrong.append(f"stdout: expected to contain {case['stdout']!r}")
            if "stderr" in case and case["stderr"] not in stderr:
                wrong.append(f"stderr: expected to contain {case['stderr']!r}")
            if wrong:
                shown_out = stdout.replace(str(work), "<work>").strip()
                shown_err = workload_lines(stderr, got is None).replace(str(work), "<work>")
                problems.append(f"{at}\n  " + "\n  ".join(wrong)
                                + f"\n  got stdout: {shown_out[-1500:]!r}\n  got stderr: {shown_err[-1500:]!r}")
            else:
                passed += 1
    finally:
        if keep:
            say(f"  kept {work}")
        else:
            shutil.rmtree(work, ignore_errors=True)
    return passed, len(cases), problems


def e2e(clis: list[str], keep: bool) -> int:
    started = time.monotonic()
    names = chosen(clis)
    names = [cli for cli in names if e2e_file(cli).exists() or clis]
    if os.uname().machine not in ("aarch64", "arm64"):
        raise HarnessError("Box runs only on Linux ARM64 and macOS on Apple silicon; use Level 1 here")
    copy = box_copy()
    say(f"building strands-box {box_revision()[:12]} ({profile()} profile)")
    binary = build_box(copy)
    failed = False
    for cli in names:
        if not e2e_file(cli).exists():
            say(f"FAIL {cli}: {e2e_file(cli).relative_to(ROOT)} does not exist")
            failed = True
            continue
        passed, total, problems = e2e_one(binary, cli, keep)
        if problems:
            failed = True
            say(f"FAIL {cli} ({passed}/{total} cases)")
            for problem in problems:
                say("  " + problem.replace("\n", "\n  "))
        else:
            say(f"PASS {cli} ({passed}/{total} cases)")
    say(f"\nlevel 2 finished in {time.monotonic() - started:.1f}s")
    return 1 if failed else 0


# ---------------------------------------------------------------- entry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    one = commands.add_parser("validate", help="Level 1")
    one.add_argument("clis", nargs="*")
    two = commands.add_parser("e2e", help="Level 2")
    two.add_argument("clis", nargs="*")
    two.add_argument("--keep", action="store_true", help="keep the box directories")
    show = commands.add_parser("render", help="print the box.toml table for one grammar")
    show.add_argument("cli")
    show.add_argument("--label", help="the [tool.<label>] name (default: the grammar name)")
    show.add_argument("--command", help="command[0] for the tool (default: the program)")
    arguments = parser.parse_args()
    try:
        if arguments.command == "validate":
            return validate(arguments.clis)
        if arguments.command == "e2e":
            return e2e(arguments.clis, arguments.keep)
        return render(arguments.cli, arguments.label, arguments.command)
    except HarnessError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
