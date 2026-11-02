"""Tests for tools/jpl_check.py (importable through pytest's ``pythonpath``)."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest

import jpl_check
from jpl_check import Config, Finding

REPO_ROOT = Path(__file__).resolve().parents[1]


def check(tmp_path: Path, source: str, **settings: Any) -> list[Finding]:
    module = tmp_path / "mod.py"
    module.write_text(dedent(source), encoding="utf-8")
    return jpl_check.check_file(module, Config(**settings), tmp_path)


def codes(findings: list[Finding]) -> list[str]:
    return [finding.rule for finding in findings]


# JPL01: recursion -----------------------------------------------------------


def test_direct_recursion_is_reported(tmp_path: Path) -> None:
    source = """
        def factorial(n: int) -> int:
            return 1 if n <= 1 else n * factorial(n - 1)
        """
    findings = check(tmp_path, source)
    assert codes(findings) == ["JPL01"]
    assert "factorial" in findings[0].message


def test_mutual_recursion_reports_both_functions(tmp_path: Path) -> None:
    source = """
        def ping(n: int) -> int:
            return pong(n - 1) if n else 0


        def pong(n: int) -> int:
            return ping(n - 1) if n else 0
        """
    assert codes(check(tmp_path, source)) == ["JPL01", "JPL01"]


def test_method_recursion_through_self_is_reported(tmp_path: Path) -> None:
    source = """
        class Walker:
            def walk(self, depth: int) -> int:
                return self.walk(depth - 1) if depth else 0
        """
    assert codes(check(tmp_path, source)) == ["JPL01"]


def test_nested_function_recursion_is_reported_once(tmp_path: Path) -> None:
    source = """
        def outer(n: int) -> int:
            def inner(k: int) -> int:
                return inner(k - 1) if k else 0

            return inner(n)
        """
    findings = check(tmp_path, source)
    assert codes(findings) == ["JPL01"]
    assert "outer.inner" in findings[0].message


def test_delegation_and_super_calls_are_not_recursion(tmp_path: Path) -> None:
    source = """
        class Base:
            def write(self, data: str) -> None:
                pass


        class Wrapper(Base):
            def __init__(self, inner: Base) -> None:
                super().__init__()
                self.inner = inner

            def write(self, data: str) -> None:
                self.inner.write(data)
        """
    assert codes(check(tmp_path, source)) == []


# JPL02: loop bounds ---------------------------------------------------------


def test_while_true_without_exit_is_reported(tmp_path: Path) -> None:
    source = """
        def spin() -> None:
            while True:
                pass
        """
    assert codes(check(tmp_path, source)) == ["JPL02"]


@pytest.mark.parametrize(
    "exit_statement", ["break", "return None", "raise RuntimeError", "sys.exit(1)"]
)
def test_while_true_with_an_exit_is_accepted(tmp_path: Path, exit_statement: str) -> None:
    source = f"""
        import sys


        def spin() -> None:
            while True:
                if sys.argv:
                    {exit_statement}
        """
    assert codes(check(tmp_path, source)) == []


def test_conditional_while_is_accepted(tmp_path: Path) -> None:
    source = """
        def countdown(n: int) -> int:
            while n > 0:
                n -= 1
            return n
        """
    assert codes(check(tmp_path, source)) == []


def test_break_inside_a_nested_loop_does_not_count(tmp_path: Path) -> None:
    source = """
        def spin(items: list[int]) -> None:
            while True:
                for item in items:
                    if item:
                        break
        """
    assert codes(check(tmp_path, source)) == ["JPL02"]


def test_endless_iterator_without_exit_is_reported(tmp_path: Path) -> None:
    source = """
        import itertools


        def spin() -> None:
            for _ in itertools.count():
                pass
        """
    assert codes(check(tmp_path, source)) == ["JPL02"]


def test_bounded_repeat_is_accepted(tmp_path: Path) -> None:
    source = """
        import itertools


        def spin() -> None:
            for _ in itertools.repeat(1, 3):
                pass
        """
    assert codes(check(tmp_path, source)) == []


# JPL04: function length -----------------------------------------------------


def test_long_function_is_reported(tmp_path: Path) -> None:
    body = "\n".join(f"    x{i} = {i}" for i in range(61))
    source = f"def long() -> None:\n{body}\n    raise ValueError(x0)\n"
    findings = check(tmp_path, source, max_function_lines=60)
    assert codes(findings) == ["JPL04"]
    assert "63 lines" in findings[0].message


def test_docstring_does_not_count_toward_length(tmp_path: Path) -> None:
    docstring = "\n".join(['    """Documented.', *(["    more"] * 70), '    """'])
    source = f"def documented() -> int:\n{docstring}\n    return 1\n"
    assert codes(check(tmp_path, source)) == []


# JPL05: assertion density ---------------------------------------------------


def test_many_statements_without_checks_is_reported(tmp_path: Path) -> None:
    body = "\n".join(f"    x{i} = {i}" for i in range(12))
    assert codes(check(tmp_path, f"def compute() -> int:\n{body}\n    return x0\n")) == ["JPL05"]


def test_validation_raise_satisfies_the_density(tmp_path: Path) -> None:
    body = "\n".join(f"    x{i} = {i}" for i in range(12))
    guard = "    if n < 0:\n        raise ValueError(n)\n"
    source = f"def compute(n: int) -> int:\n{guard}{body}\n    return x0 + n\n"
    assert codes(check(tmp_path, source)) == []


def test_short_functions_need_no_checks(tmp_path: Path) -> None:
    source = """
        def tiny(a: int, b: int) -> int:
            total = a + b
            return total * 2
        """
    assert codes(check(tmp_path, source)) == []


def test_min_assertions_is_configurable(tmp_path: Path) -> None:
    body = "\n".join(f"    x{i} = {i}" for i in range(12))
    guard = "    if n < 0:\n        raise ValueError(n)\n"
    source = f"def compute(n: int) -> int:\n{guard}{body}\n    return x0 + n\n"
    assert codes(check(tmp_path, source, min_assertions=2)) == ["JPL05"]


# JPL06: scope ---------------------------------------------------------------


def test_global_and_nonlocal_are_reported(tmp_path: Path) -> None:
    source = """
        COUNTER = 0


        def bump() -> None:
            global COUNTER
            COUNTER += 1


        def outer() -> None:
            total = 0

            def inner() -> None:
                nonlocal total
                total += 1

            return inner()
        """
    findings = check(tmp_path, source)
    assert codes(findings) == ["JPL06", "JPL06"]
    assert "global COUNTER" in findings[0].message


# JPL08: dynamic code --------------------------------------------------------


def test_dynamic_code_is_reported(tmp_path: Path) -> None:
    source = """
        from os import *


        def run(code: str) -> object:
            done = exec(code)
            compiled = compile(code, "<s>", "eval")
            module = __import__("json")
            return eval(code), compiled, module, done
        """
    assert codes(check(tmp_path, source)) == ["JPL08"] * 5


def test_a_method_named_compile_is_not_dynamic_code(tmp_path: Path) -> None:
    source = """
        import re


        def pattern() -> re.Pattern[str]:
            return re.compile("x")
        """
    assert codes(check(tmp_path, source)) == []


# JPL07: discarded results ---------------------------------------------------


def test_discarded_result_is_a_warning(tmp_path: Path) -> None:
    source = """
        def compute() -> int:
            return 1


        def notify(items: list[int]) -> None:
            print(items)


        def run(items: list[int]) -> None:
            compute()
            items.append(1)
            items.sort()
            notify(items)
        """
    findings = check(tmp_path, source)
    assert [(finding.rule, finding.severity) for finding in findings] == [("JPL07", "warning")]
    assert findings[0].line == 11


# Suppressions, parsing, configuration, file discovery -----------------------


def test_noqa_silences_one_rule_or_all(tmp_path: Path) -> None:
    noqa = "# noqa:"
    source = f"""
        def compute() -> int:
            return 1


        def run() -> None:
            compute()  {noqa} JPL07
            compute()  {noqa} JPL
            compute()  {noqa} E501, JPL07
            compute()  {noqa} JPL01
        """
    assert [finding.line for finding in check(tmp_path, source)] == [10]


def test_syntax_error_is_reported_as_jpl00(tmp_path: Path) -> None:
    findings = check(tmp_path, "def broken(:\n    pass\n")
    assert codes(findings) == ["JPL00"]
    assert findings[0].severity == "error"


def test_check_file_rejects_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(jpl_check.UsageError, match="not a file"):
        jpl_check.check_file(tmp_path / "missing.py", Config(), tmp_path)


def test_config_defaults_when_pyproject_is_missing(tmp_path: Path) -> None:
    assert Config.from_pyproject(tmp_path / "pyproject.toml") == Config()


def test_config_reads_the_table(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[tool.jpl_check]\nmax_function_lines = 5\npaths = ["pkg"]\n', encoding="utf-8"
    )
    config = Config.from_pyproject(pyproject)
    assert config.max_function_lines == 5
    assert config.paths == ["pkg"]
    assert config.min_assertions == 1


def test_config_rejects_unknown_settings(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.jpl_check]\nbogus = 1\n", encoding="utf-8")
    with pytest.raises(jpl_check.UsageError, match="bogus"):
        Config.from_pyproject(pyproject)


def test_config_rejects_negative_limits() -> None:
    with pytest.raises(jpl_check.UsageError, match="negative"):
        Config(max_function_lines=-1)


def test_config_rejects_a_non_table(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool]\njpl_check = 3\n", encoding="utf-8")
    with pytest.raises(jpl_check.UsageError, match="table"):
        Config.from_pyproject(pyproject)


def test_iter_python_files_skips_hidden_and_excluded_paths(tmp_path: Path) -> None:
    for relative in ("src/pkg/a.py", "src/pkg/.hidden/b.py", "tests/test_x.py", "src/notes.txt"):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("", encoding="utf-8")
    files = jpl_check.iter_python_files(tmp_path, ["src", "tests"], ["tests"])
    assert [file.relative_to(tmp_path).as_posix() for file in files] == ["src/pkg/a.py"]


def test_iter_python_files_rejects_a_missing_path(tmp_path: Path) -> None:
    with pytest.raises(jpl_check.UsageError, match="does not exist"):
        list(jpl_check.iter_python_files(tmp_path, ["nowhere"], []))


# Command line ---------------------------------------------------------------


def test_main_passes_on_this_repository(capsys: pytest.CaptureFixture[str]) -> None:
    assert jpl_check.main(["--root", str(REPO_ROOT)]) == 0
    assert "0 error(s)" in capsys.readouterr().out


def test_main_reports_errors_in_github_format(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "mod.py").write_text(
        "def spin() -> None:\n    while True:\n        pass\n", encoding="utf-8"
    )
    argv = ["--root", str(tmp_path), "--paths", "mod.py", "--format", "github"]
    assert jpl_check.main(argv) == 1
    out = capsys.readouterr().out
    assert out.startswith("::error file=mod.py,line=2,title=JPL02::")
    assert "1 error(s), 0 warning(s)" in out


def test_main_strict_turns_warnings_into_failures(tmp_path: Path) -> None:
    source = "def compute() -> int:\n    return 1\n\n\ndef run() -> None:\n    compute()\n"
    (tmp_path / "mod.py").write_text(source, encoding="utf-8")
    assert jpl_check.main(["--root", str(tmp_path), "--paths", "mod.py"]) == 0
    assert jpl_check.main(["--root", str(tmp_path), "--paths", "mod.py", "--strict"]) == 1


def test_main_reports_usage_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert jpl_check.main(["--root", str(tmp_path / "missing")]) == 2
    assert jpl_check.main(["--root", str(tmp_path), "--paths", "nope.py"]) == 2
    assert "jpl_check: error" in capsys.readouterr().err


def test_main_lists_the_rules(capsys: pytest.CaptureFixture[str]) -> None:
    assert jpl_check.main(["--list-rules"]) == 0
    out = capsys.readouterr().out
    assert "JPL01" in out
    assert "JPL08" in out
