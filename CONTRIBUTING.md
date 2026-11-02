# Contributing

Thank you for helping. This page is short on purpose; the tools enforce the rest.

## Workflow

1. Open an issue first for anything bigger than a small fix, so the design can be agreed before the code is written.
2. Create a branch from `main`: `feat/<topic>`, `fix/<topic>`, `docs/<topic>` or `chore/<topic>`.
3. Keep commits focused and write them in the [Conventional Commits](https://www.conventionalcommits.org) form, for example `fix: cap interest at five gold`.
4. Open a pull request against `main` and fill in the template. The pull request must pass **CI passed**, **Standards passed** and both **CodeQL** analyses before it can merge.
5. Add a line to `CHANGELOG.md` under **Unreleased** for anything a user would notice.

## Local setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
python -m pip install -e . -r requirements-dev.txt
pre-commit install
```

## Before you push

```bash
ruff format .
ruff check --fix .
mypy
python tools/jpl_check.py --root .
python -m pytest
```

All five must pass. They are the same commands the Standards and CI workflows run.

## Standards in one paragraph

Python 3.11 or newer. Formatting and lint by `ruff` with the rule set in
`pyproject.toml`; full type annotations checked by `mypy --strict`; Google-style
docstrings on every public module, class and function; no function longer than
60 lines, no recursion, no `global`, no `eval`; inputs validated with explicit
exceptions; 95 % branch coverage. The reasoning behind each rule is in
[docs/STANDARDS.md](docs/STANDARDS.md).

## Tests

Put tests in `tests/`, name them after the behaviour they prove, and prefer
small parametrised cases over one large test. New code without tests is not
merged.

## Releases

Only maintainers cut releases. The process is in [docs/RELEASING.md](docs/RELEASING.md).
