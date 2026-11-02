#!/usr/bin/env python3
"""Check Python sources against the NASA/JPL "Power of Ten" rules, adapted for Python.

The Power of Ten (Gerard J. Holzmann, NASA/JPL, 2006) are ten rules for writing
safety-critical code. They were written for C. This tool enforces the rules that
translate to Python and leaves the others to the language runtime and to the rest
of the pipeline; ``docs/STANDARDS.md`` holds the complete mapping.

Rules checked here::

    JPL00  the file must parse
    JPL01  simple control flow: no recursion, direct or mutual
    JPL02  every loop has a fixed bound or an explicit exit
    JPL04  no function longer than ``max_function_lines`` lines (docstring excluded)
    JPL05  functions with ``min_statements_for_assertions`` statements or more hold
           at least ``min_assertions`` assertions or validation raises
    JPL06  data lives in the smallest scope: no ``global`` or ``nonlocal``
    JPL07  return values are not silently discarded (warning)
    JPL08  no dynamic code: eval, exec, compile, __import__ or ``from x import *``

A finding is silenced on its line with ``# noqa: JPL04`` (one rule) or
``# noqa: JPL`` (every rule). Settings live in ``[tool.jpl_check]`` in
``pyproject.toml``. The exit status is 0 when nothing failed, 1 when errors were
found (or warnings, with ``--strict``) and 2 on a usage error.
"""

from __future__ import annotations

import argparse
import ast
import sys
import tomllib
from collections import deque
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import NamedTuple

ERROR = "error"
WARNING = "warning"

FUNCTION_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef)
LOOP_TYPES = (ast.For, ast.AsyncFor, ast.While)
SCOPE_TYPES = (*FUNCTION_TYPES, ast.ClassDef, ast.Lambda)
EXIT_TYPES = (ast.Return, ast.Raise)
CHECK_TYPES = (ast.Assert, ast.Raise)

DYNAMIC_CODE_CALLS = frozenset({"eval", "exec", "compile", "__import__"})
ENDLESS_ITERATORS = frozenset({"count", "cycle", "repeat"})
EXIT_CALLS = frozenset({"exit", "_exit"})
SELF_NAMES = frozenset({"self", "cls"})
VOID_CALLS = frozenset(
    {
        "add",
        "add_argument",
        "append",
        "chdir",
        "clear",
        "close",
        "critical",
        "debug",
        "discard",
        "error",
        "exception",
        "extend",
        "flush",
        "info",
        "insert",
        "join",
        "log",
        "makedirs",
        "mkdir",
        "pop",
        "print",
        "put",
        "remove",
        "rename",
        "reverse",
        "rmdir",
        "rmtree",
        "seed",
        "seek",
        "setdefault",
        "shuffle",
        "sleep",
        "sort",
        "start",
        "touch",
        "truncate",
        "unlink",
        "update",
        "wait",
        "warn",
        "warning",
        "write",
        "writelines",
    }
)
VOID_PREFIXES = (
    "add_",
    "clear_",
    "emit_",
    "log_",
    "notify_",
    "print_",
    "register_",
    "remove_",
    "set_",
    "update_",
    "write_",
)
NOQA_MARKER = "# noqa:"
REPEAT_ARGS_WITH_LIMIT = 2

RULES: dict[str, str] = {
    "JPL00": "The file must parse.",
    "JPL01": "Simple control flow: no recursion, direct or mutual.",
    "JPL02": "Every loop has a fixed bound or an explicit exit.",
    "JPL04": "No function longer than the configured number of lines.",
    "JPL05": "Functions with many statements contain assertions or validation raises.",
    "JPL06": "Data lives in the smallest scope: no global or nonlocal.",
    "JPL07": "Return values are not silently discarded (warning).",
    "JPL08": "No dynamic code: eval, exec, compile, __import__ or star imports.",
}

FuncNode = ast.FunctionDef | ast.AsyncFunctionDef
LoopNode = ast.For | ast.AsyncFor | ast.While


class UsageError(Exception):
    """Raised for a bad root, configuration or path; ``main`` turns it into exit status 2."""


@dataclass(frozen=True)
class Finding:
    """One rule violation at one line of one file."""

    path: str
    line: int
    rule: str
    severity: str
    message: str

    def render(self, style: str) -> str:
        """Return the finding as a text line or as a GitHub Actions annotation."""
        if style == "github":
            return (
                f"::{self.severity} file={self.path},line={self.line},"
                f"title={self.rule}::{self.message}"
            )
        return f"{self.path}:{self.line}: {self.rule} {self.severity}: {self.message}"


@dataclass
class Config:
    """Settings, normally read from ``[tool.jpl_check]`` in pyproject.toml."""

    paths: list[str] = field(default_factory=lambda: ["src"])
    exclude: list[str] = field(default_factory=lambda: ["tests"])
    max_function_lines: int = 60
    min_statements_for_assertions: int = 10
    min_assertions: int = 1

    def __post_init__(self) -> None:
        """Reject negative limits.

        Raises:
            UsageError: If a limit is negative.
        """
        limits = (self.max_function_lines, self.min_statements_for_assertions, self.min_assertions)
        if any(limit < 0 for limit in limits):
            msg = "[tool.jpl_check] limits must not be negative"
            raise UsageError(msg)

    @classmethod
    def from_pyproject(cls, pyproject: Path) -> Config:
        """Build a Config from pyproject.toml; a missing file or table gives the defaults.

        Raises:
            UsageError: If the table is malformed or names unknown settings.
        """
        if not pyproject.is_file():
            return cls()
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        table = data.get("tool", {}).get("jpl_check", {})
        if not isinstance(table, dict):
            msg = "[tool.jpl_check] in pyproject.toml must be a table"
            raise UsageError(msg)
        unknown = sorted(set(table) - {setting.name for setting in fields(cls)})
        if unknown:
            msg = f"[tool.jpl_check] has unknown settings: {', '.join(unknown)}"
            raise UsageError(msg)
        return cls(**table)


@dataclass(frozen=True)
class Function:
    """A function definition, where it sits, and the functions it may call."""

    node: FuncNode
    qualname: str
    class_name: str | None
    enclosing_functions: tuple[str, ...]
    plain_calls: frozenset[str]
    self_calls: frozenset[str]

    @property
    def body_lines(self) -> int:
        """Return the number of source lines the function spans, docstring excluded."""
        end = self.node.end_lineno or self.node.lineno
        total = end - self.node.lineno + 1
        if self.has_docstring:
            docstring = self.node.body[0]
            doc_end = docstring.end_lineno or docstring.lineno
            total -= doc_end - docstring.lineno + 1
        return total

    @property
    def has_docstring(self) -> bool:
        """Return whether the first statement of the body is a docstring."""
        first = self.node.body[0] if self.node.body else None
        return isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)

    @property
    def statement_count(self) -> int:
        """Return the number of statements in the function's own scope, docstring excluded."""
        statements = sum(1 for node in walk_scope(self.node) if isinstance(node, ast.stmt))
        return statements - 1 if self.has_docstring else statements


class Frame(NamedTuple):
    """A position in the tree walk: the node, its qualname prefix, its class and its functions."""

    node: ast.AST
    prefix: str
    class_name: str | None
    enclosing_functions: tuple[str, ...]


def call_name(call: ast.Call) -> str | None:
    """Return the simple name a call targets: ``f`` for both ``f()`` and ``obj.f()``."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def call_target(call: ast.Call) -> tuple[str, bool] | None:
    """Return ``(name, via_self)`` for ``name()`` and ``self.name()`` or ``cls.name()`` calls.

    Calls on any other object, including ``super()``, belong to code outside the
    current definition and give ``None``.
    """
    func = call.func
    if isinstance(func, ast.Name):
        return func.id, False
    if (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id in SELF_NAMES
    ):
        return func.attr, True
    return None


def walk_scope(node: ast.AST) -> Iterator[ast.AST]:
    """Yield the nodes under ``node`` without entering nested functions, classes or lambdas."""
    stack = list(ast.iter_child_nodes(node))
    while stack:  # bounded: every node of the finite subtree is pushed at most once
        current = stack.pop()
        if isinstance(current, SCOPE_TYPES):
            continue
        yield current
        stack.extend(ast.iter_child_nodes(current))


def split_calls(function: FuncNode) -> tuple[frozenset[str], frozenset[str]]:
    """Return the names called as ``name()`` and as ``self.name()`` or ``cls.name()``."""
    plain: set[str] = set()
    via_self: set[str] = set()
    for node in walk_scope(function):
        target = call_target(node) if isinstance(node, ast.Call) else None
        if target is None:
            continue
        name, is_self_call = target
        (via_self if is_self_call else plain).add(name)
    return frozenset(plain), frozenset(via_self)


def visit(child: ast.AST, frame: Frame, found: list[Function]) -> Frame:
    """Record ``child`` in ``found`` if it defines a function; return the frame to walk it."""
    if isinstance(child, FUNCTION_TYPES):
        qualname = frame.prefix + child.name
        plain, via_self = split_calls(child)
        found.append(
            Function(child, qualname, frame.class_name, frame.enclosing_functions, plain, via_self)
        )
        return Frame(
            child, qualname + ".", frame.class_name, (*frame.enclosing_functions, qualname)
        )
    if isinstance(child, ast.ClassDef):
        qualname = frame.prefix + child.name
        return Frame(child, qualname + ".", qualname, frame.enclosing_functions)
    return Frame(child, frame.prefix, frame.class_name, frame.enclosing_functions)


def collect_functions(tree: ast.Module) -> list[Function]:
    """Return every function in ``tree`` with its qualified name, in source order."""
    found: list[Function] = []
    stack = [Frame(tree, "", None, ())]
    while stack:  # bounded: every node of the finite tree is pushed at most once
        frame = stack.pop()
        stack.extend(visit(child, frame, found) for child in ast.iter_child_nodes(frame.node))
    return sorted(found, key=lambda function: function.node.lineno)


def resolve_plain_calls(function: Function, known: frozenset[str]) -> set[str]:
    """Resolve ``name()`` calls to the innermost enclosing definition of ``name`` in this file."""
    own_scopes = (*function.enclosing_functions, function.qualname)
    scopes = ("", *(f"{scope}." for scope in own_scopes))
    targets: set[str] = set()
    for name in function.plain_calls:
        candidates = (f"{scope}{name}" for scope in reversed(scopes))
        match = next((candidate for candidate in candidates if candidate in known), None)
        if match is not None:
            targets.add(match)
    return targets


def resolve_self_calls(function: Function, known: frozenset[str]) -> set[str]:
    """Resolve ``self.name()`` and ``cls.name()`` calls to methods of the enclosing class."""
    if function.class_name is None:
        return set()
    return {f"{function.class_name}.{name}" for name in function.self_calls} & known


def resolve_callees(function: Function, known: frozenset[str]) -> set[str]:
    """Return the qualified names of the functions in this file that ``function`` can call.

    Calls on other objects, other modules and inherited methods are outside the
    file and are not resolved; recursion through them is not detected here.
    """
    return resolve_plain_calls(function, known) | resolve_self_calls(function, known)


def reaches(graph: dict[str, set[str]], start: str, target: str) -> bool:
    """Return whether ``target`` can be reached from the callees of ``start``.

    Raises:
        KeyError: If ``start`` is not a node of ``graph``.
    """
    if start not in graph:
        msg = f"unknown function {start!r}"
        raise KeyError(msg)
    seen: set[str] = set()
    pending = deque(graph[start])
    while pending:  # bounded: each name is expanded at most once
        name = pending.popleft()
        if name == target:
            return True
        if name in seen:
            continue
        seen.add(name)
        pending.extend(graph.get(name, set()))
    return False


def check_recursion(functions: Sequence[Function], path: str) -> list[Finding]:
    """JPL01: report every function that can call itself, directly or through others."""
    known = frozenset(function.qualname for function in functions)
    graph = {function.qualname: resolve_callees(function, known) for function in functions}
    return [
        Finding(
            path,
            function.node.lineno,
            "JPL01",
            ERROR,
            f"'{function.qualname}' is recursive, directly or through the functions it "
            "calls; rewrite it as a loop with an explicit bound",
        )
        for function in functions
        if reaches(graph, function.qualname, function.qualname)
    ]


def has_exit(loop: LoopNode) -> bool:
    """Return whether the loop body can leave the loop: break, return, raise or an exit call.

    Raises:
        ValueError: If the loop has no body, which a parsed tree never produces.
    """
    if not loop.body:
        msg = f"loop at line {loop.lineno} has no body"
        raise ValueError(msg)
    stack: list[tuple[ast.AST, bool]] = [(node, False) for node in loop.body]
    while stack:  # bounded: every node of the finite subtree is pushed at most once
        node, in_nested_loop = stack.pop()
        if isinstance(node, EXIT_TYPES) or (isinstance(node, ast.Break) and not in_nested_loop):
            return True
        if isinstance(node, ast.Call) and call_name(node) in EXIT_CALLS:
            return True
        if isinstance(node, SCOPE_TYPES):
            continue
        nested = in_nested_loop or isinstance(node, LOOP_TYPES)
        stack.extend((child, nested) for child in ast.iter_child_nodes(node))
    return False


def is_constant_true(test: ast.expr) -> bool:
    """Return whether a loop condition is a truthy constant such as ``True`` or ``1``."""
    return isinstance(test, ast.Constant) and bool(test.value)


def is_endless(iterable: ast.expr) -> bool:
    """Return whether ``iterable`` is ``count()``, ``cycle()`` or ``repeat()`` without a limit."""
    if not isinstance(iterable, ast.Call):
        return False
    name = call_name(iterable)
    if name not in ENDLESS_ITERATORS:
        return False
    has_limit = len(iterable.args) + len(iterable.keywords) >= REPEAT_ARGS_WITH_LIMIT
    return not (name == "repeat" and has_limit)


def loop_problem(loop: LoopNode) -> str | None:
    """Return why ``loop`` breaks JPL02, or ``None`` when it is bounded or can exit."""
    if isinstance(loop, ast.While) and is_constant_true(loop.test) and not has_exit(loop):
        return "'while True' has no break, return or raise; give the loop a bound or an exit"
    if isinstance(loop, ast.For | ast.AsyncFor) and is_endless(loop.iter) and not has_exit(loop):
        return "loop over an endless iterator has no break, return or raise"
    return None


def check_loops(tree: ast.Module, path: str) -> list[Finding]:
    """JPL02: report ``while True`` loops and endless-iterator loops that cannot exit."""
    loops = (node for node in ast.walk(tree) if isinstance(node, LOOP_TYPES))
    problems = ((loop, loop_problem(loop)) for loop in loops)
    return [
        Finding(path, loop.lineno, "JPL02", ERROR, message)
        for loop, message in problems
        if message is not None
    ]


def check_function_length(
    functions: Sequence[Function], config: Config, path: str
) -> list[Finding]:
    """JPL04: report functions longer than ``config.max_function_lines`` lines."""
    return [
        Finding(
            path,
            function.node.lineno,
            "JPL04",
            ERROR,
            f"'{function.qualname}' is {function.body_lines} lines long "
            f"(limit {config.max_function_lines}); split it into smaller functions",
        )
        for function in functions
        if function.body_lines > config.max_function_lines
    ]


def density_problem(function: Function, config: Config) -> str | None:
    """Return why ``function`` breaks JPL05, or ``None`` when its check density is fine."""
    statements = function.statement_count
    if statements < config.min_statements_for_assertions:
        return None
    checks = sum(1 for node in walk_scope(function.node) if isinstance(node, CHECK_TYPES))
    if checks >= config.min_assertions:
        return None
    return (
        f"'{function.qualname}' has {statements} statements but only {checks} "
        f"assertion(s) or validation raise(s); at least {config.min_assertions} "
        "required: validate the inputs and the invariants"
    )


def check_assertions(functions: Sequence[Function], config: Config, path: str) -> list[Finding]:
    """JPL05: report long functions that hold no assertion or validation raise."""
    problems = ((function, density_problem(function, config)) for function in functions)
    return [
        Finding(path, function.node.lineno, "JPL05", ERROR, message)
        for function, message in problems
        if message is not None
    ]


def check_scope(tree: ast.Module, path: str) -> list[Finding]:
    """JPL06: report ``global`` and ``nonlocal`` statements."""
    return [
        Finding(
            path,
            node.lineno,
            "JPL06",
            ERROR,
            f"'{type(node).__name__.lower()} {', '.join(node.names)}' widens the scope of "
            "data; pass values in and return them instead",
        )
        for node in ast.walk(tree)
        if isinstance(node, ast.Global | ast.Nonlocal)
    ]


def dynamic_code_problem(node: ast.Call | ast.ImportFrom) -> str | None:
    """Return why ``node`` breaks JPL08, or ``None``."""
    if isinstance(node, ast.ImportFrom):
        if any(alias.name == "*" for alias in node.names):
            return f"'from {node.module} import *' hides what is in scope; import names explicitly"
        return None
    if isinstance(node.func, ast.Name) and node.func.id in DYNAMIC_CODE_CALLS:
        return f"{node.func.id}() runs code built at runtime; make the behaviour static"
    return None


def check_dynamic_code(tree: ast.Module, path: str) -> list[Finding]:
    """JPL08: report eval, exec, compile, __import__ and star imports."""
    nodes = (node for node in ast.walk(tree) if isinstance(node, ast.Call | ast.ImportFrom))
    problems = ((node, dynamic_code_problem(node)) for node in nodes)
    return [
        Finding(path, node.lineno, "JPL08", ERROR, message)
        for node, message in problems
        if message is not None
    ]


def is_void_name(name: str) -> bool:
    """Return whether a call by this name is conventionally made for its effect only."""
    if name in VOID_CALLS or name in EXIT_CALLS:
        return True
    return name.startswith(VOID_PREFIXES) or name.startswith("__")


def returns_none(function: FuncNode) -> bool:
    """Return whether ``function`` is annotated as returning ``None``."""
    returns = function.returns
    return isinstance(returns, ast.Constant) and returns.value is None


def discarded_result_problem(statement: ast.Expr, void_functions: frozenset[str]) -> str | None:
    """Return why an expression statement breaks JPL07, or ``None``.

    ``void_functions`` holds the names of the functions in the file that are
    annotated ``-> None``; calling them for their effect is the intended use.
    """
    if not isinstance(statement.value, ast.Call):
        return None
    name = call_name(statement.value)
    if name is None or name in void_functions or is_void_name(name):
        return None
    return (
        f"the result of {name}() is discarded; use it, assign it, or add "
        "'# noqa: JPL07' if the call is made for its effect"
    )


def check_discarded_results(
    tree: ast.Module, functions: Sequence[Function], path: str
) -> list[Finding]:
    """JPL07 (warning): report calls whose result is thrown away."""
    void = frozenset(function.node.name for function in functions if returns_none(function.node))
    statements = (node for node in ast.walk(tree) if isinstance(node, ast.Expr))
    problems = ((statement, discarded_result_problem(statement, void)) for statement in statements)
    return [
        Finding(path, statement.lineno, "JPL07", WARNING, message)
        for statement, message in problems
        if message is not None
    ]


def suppressed(lines: Sequence[str], finding: Finding) -> bool:
    """Return whether the finding's line carries ``# noqa: JPL`` or ``# noqa: <rule>``."""
    if not 1 <= finding.line <= len(lines):
        return False
    text = lines[finding.line - 1]
    marker = text.find(NOQA_MARKER)
    if marker < 0:
        return False
    codes = text[marker + len(NOQA_MARKER) :].replace(",", " ").split()
    return any(code in {"JPL", finding.rule} for code in codes)


def display_path(file: Path, root: Path) -> str:
    """Return ``file`` relative to ``root`` with forward slashes, for readable annotations."""
    resolved = file.resolve()
    if resolved.is_relative_to(root):
        return resolved.relative_to(root).as_posix()
    return file.as_posix()


def check_file(file: Path, config: Config, root: Path) -> list[Finding]:
    """Run every rule on one file and return its findings, sorted by line.

    Raises:
        UsageError: If ``file`` is not a readable file.
    """
    if not file.is_file():
        msg = f"not a file: {file}"
        raise UsageError(msg)
    path = display_path(file, root.resolve())
    source = file.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(file))
    except SyntaxError as error:
        return [Finding(path, error.lineno or 1, "JPL00", ERROR, f"cannot parse: {error.msg}")]
    functions = collect_functions(tree)
    findings = [
        *check_recursion(functions, path),
        *check_loops(tree, path),
        *check_function_length(functions, config, path),
        *check_assertions(functions, config, path),
        *check_scope(tree, path),
        *check_dynamic_code(tree, path),
        *check_discarded_results(tree, functions, path),
    ]
    lines = source.splitlines()
    kept = [finding for finding in findings if not suppressed(lines, finding)]
    return sorted(kept, key=lambda finding: (finding.line, finding.rule))


def iter_python_files(root: Path, paths: Iterable[str], exclude: Iterable[str]) -> Iterator[Path]:
    """Yield the ``.py`` files under ``paths``, skipping excluded and hidden entries.

    Raises:
        UsageError: If one of ``paths`` does not exist.
    """
    excluded = [(root / pattern).resolve() for pattern in exclude]
    for entry in paths:
        base = root / entry
        if not base.exists():
            msg = f"path does not exist: {base}"
            raise UsageError(msg)
        files = [base] if base.is_file() else sorted(base.rglob("*.py"))
        for file in files:
            relative = file.relative_to(root) if file.is_relative_to(root) else file
            hidden = any(part.startswith(".") for part in relative.parts)
            if hidden or any(file.resolve().is_relative_to(skip) for skip in excluded):
                continue
            yield file


def report(findings: Sequence[Finding], file_count: int, style: str, *, strict: bool) -> int:
    """Print the findings and a summary line; return 1 when the run failed, else 0."""
    for finding in sorted(findings, key=lambda item: (item.path, item.line, item.rule)):
        print(finding.render(style))
    errors = sum(1 for finding in findings if finding.severity == ERROR)
    warnings = len(findings) - errors
    print(f"jpl_check: {file_count} file(s) checked, {errors} error(s), {warnings} warning(s)")
    failed = errors > 0 or (strict and warnings > 0)
    return 1 if failed else 0


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(
        prog="jpl_check",
        description="Check Python sources against the NASA/JPL Power of Ten rules.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="project root that holds pyproject.toml (default: the current directory)",
    )
    parser.add_argument(
        "--paths",
        nargs="+",
        metavar="PATH",
        help="files or directories to check, relative to the root "
        "(default: [tool.jpl_check].paths, else src)",
    )
    parser.add_argument(
        "--format",
        choices=("text", "github"),
        default="text",
        help="output style; 'github' prints workflow annotations",
    )
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    parser.add_argument("--list-rules", action="store_true", help="print the rules and exit")
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> int:
    """Check the configured paths under ``args.root`` and return the exit status.

    Raises:
        UsageError: If the root, the configuration or a path is unusable.
    """
    root = Path(args.root).resolve()
    if not root.is_dir():
        msg = f"{root} is not a directory"
        raise UsageError(msg)
    config = Config.from_pyproject(root / "pyproject.toml")
    files = list(iter_python_files(root, args.paths or config.paths, config.exclude))
    findings = [finding for file in files for finding in check_file(file, config, root)]
    return report(findings, len(files), args.format, strict=args.strict)


def print_rules() -> None:
    """Print the rule table."""
    for code, text in RULES.items():
        print(f"{code}  {text}")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the checker from the command line and return the exit status."""
    args = parse_args(argv)
    if args.list_rules:
        print_rules()
        return 0
    try:
        return run(args)
    except UsageError as error:
        print(f"jpl_check: error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
