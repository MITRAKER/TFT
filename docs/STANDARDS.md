# Code standards

Two layers apply to every line in this repository: general Python code
standards, enforced by `ruff` and `mypy`, and the NASA/JPL Power of Ten rules
for safety-critical code, enforced by `tools/jpl_check.py` together with the
other stages. The **Standards** workflow runs both on every push and pull
request; `pre-commit` runs them before every commit.

## General code standards

| Standard | Rule | Enforced by |
| --- | --- | --- |
| Layout | PEP 8, 100-character lines, LF line endings, UTF-8 | `ruff format`, `.editorconfig`, `.gitattributes` |
| Lint | pycodestyle, pyflakes, bugbear, comprehensions, simplify, performance, pie, return consistency, pathlib over `os.path`, no commented-out code, no shadowed builtins | `ruff check` (`E W F B C4 SIM PERF PIE RET PTH ERA A`) |
| Naming | PEP 8 names | `ruff` (`N`) |
| Imports | sorted, first-party aware, no star imports | `ruff` (`I`), JPL08 |
| Documentation | Google-style docstrings on every public module, class and function | `ruff` (`D`, `convention = "google"`) |
| Typing | every parameter and return type annotated; checked in strict mode; the package ships `py.typed` | `ruff` (`ANN`), `mypy --strict` |
| Complexity | cyclomatic complexity 10 or less; at most 6 arguments, 12 branches, 6 returns and 50 statements per function; no magic numbers | `ruff` (`C90`, `PL`) |
| Security | bandit rules: no `eval`/`exec`, no shell injection, no weak hashes, no hard-coded passwords, no `assert` in product code | `ruff` (`S`), CodeQL, `pip-audit` |
| Logging | no stray `print` in library code | `ruff` (`T20`) |
| Exceptions | explicit exception types, `raise ... from`, no bare `except` | `ruff` (`TRY`, `B`) |
| Tests | pytest style; warnings are errors; 95 % branch coverage | `ruff` (`PT`), `pytest` configuration |
| Modern syntax | current syntax for the minimum supported Python | `ruff` (`UP`, `target-version = "py311"`) |

## The NASA/JPL Power of Ten

Gerard J. Holzmann of the NASA/JPL Laboratory for Reliable Software published
the *Power of Ten* in 2006: ten rules that keep code analysable and testable.
They target C, so each rule below is paired with how it translates to Python
and the tool that enforces it here. Rules marked with a code `JPLnn` are
checked by `tools/jpl_check.py`; run it with `--list-rules` to see them, and
silence a single line with `# noqa: JPL04` (one rule) or `# noqa: JPL` (all).

| # | Rule (abridged) | In this repository |
| --- | --- | --- |
| 1 | Restrict all code to very simple control flow constructs: no `goto`, no `setjmp`/`longjmp`, no direct or indirect recursion. | Python has no `goto`. **JPL01** rejects direct and mutual recursion within a module, including through `self.` method calls and nested functions. `ruff` caps cyclomatic complexity at 10 and branches at 12. |
| 2 | All loops must have a fixed upper bound that a checking tool can verify statically. | `for` loops over finite data are bounded by construction. **JPL02** rejects `while True` (or any constant condition) without a `break`, `return`, `raise` or exit call, and loops over `itertools.count`, `cycle` or unbounded `repeat` without an exit. Conditional `while` loops must make visible progress toward their condition; reviewers check this. |
| 3 | Do not use dynamic memory allocation after initialisation. | Not applicable to a garbage-collected language. The Python analogue is unbounded growth of caches, queues and lists in long-running code; `ruff` `PERF` rules flag wasteful allocation patterns and reviewers check growth bounds. |
| 4 | No function longer than what fits on one sheet of paper, about 60 lines. | **JPL04** rejects any function longer than 60 lines, docstring excluded. `ruff` additionally caps a function at 50 statements. |
| 5 | Assertion density of at least two assertions per function, checking conditions that should never happen. | **JPL05** requires every function with 10 or more statements to contain at least one `assert` or validation `raise` (both thresholds are configurable). Product code validates inputs with explicit exceptions because `assert` is stripped under `python -O`; `assert` is reserved for internal invariants and tests. `mypy --strict` removes a large class of impossible states before the code runs. |
| 6 | Declare data objects at the smallest possible scope. | **JPL06** rejects `global` and `nonlocal`. `ruff` rejects mutable default arguments (`B006`) and the `global` statement (`PLW0603`); module constants are `UPPER_CASE` and treated as read-only. |
| 7 | Check the return value of every non-void function and the validity of every parameter. | **JPL07** warns when a call's result is discarded; calls to functions annotated `-> None` in the same file and to conventional effect-only methods are exempt, and a deliberate case is silenced with `# noqa: JPL07`. `ruff` `ANN` plus `mypy --strict` make every parameter and return type explicit and checked; JPL05 drives the input validation. |
| 8 | Limit the preprocessor to header inclusion and simple macros. | Python has no preprocessor. The analogue is code created or executed at run time: **JPL08** rejects `eval`, `exec`, `compile`, `__import__` and `from module import *`; `ruff` `S102`/`S307` flag the same as security findings. |
| 9 | Restrict pointer use to one level of dereferencing; no function pointers. | Python has no raw pointers. The spirit of the rule, keeping indirection explicit and readable, is served by `mypy --strict` (no untyped or `Any`-typed calls), by `ruff` `A` (no shadowed builtins) and by review of any `ctypes` or reflection use. |
| 10 | Compile with all warnings enabled from day one; use several static analysers daily; pass with zero warnings. | The Standards workflow runs `ruff` with the full rule set and `mypy --strict` with zero tolerance, `pytest` turns every warning into an error, CodeQL analyses the code and the workflows on every change and weekly, `pip-audit` and dependency review watch the dependencies, and OpenSSF Scorecard reviews the repository's own posture. |

### Configuration

```toml
[tool.jpl_check]
paths = ["src", "tools"]
exclude = ["tests"]
max_function_lines = 60
min_statements_for_assertions = 10
min_assertions = 1
```

Errors (rules 1, 2, 4, 5, 6, 8 and unparsable files) fail the Standards
workflow. Rule 7 is a warning that is annotated on the pull request; pass
`--strict` to fail on it as well.

### Running the checker

```bash
python tools/jpl_check.py --root .                 # as CI runs it
python tools/jpl_check.py --root . --strict        # warnings fail too
python tools/jpl_check.py --root . --paths src/tft/economy.py
python tools/jpl_check.py --list-rules
```

## References

- G. J. Holzmann, "The Power of Ten: Rules for Developing Safety-Critical Code", *IEEE Computer* 39(6), 2006.
- JPL Institutional Coding Standard for the C Programming Language, JPL DOCID D-60411, 2009.
