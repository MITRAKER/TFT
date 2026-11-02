# TFT

[![CI](https://github.com/MITRAKER/TFT/actions/workflows/ci.yml/badge.svg)](https://github.com/MITRAKER/TFT/actions/workflows/ci.yml)
[![Standards](https://github.com/MITRAKER/TFT/actions/workflows/standards.yml/badge.svg)](https://github.com/MITRAKER/TFT/actions/workflows/standards.yml)
[![CodeQL](https://github.com/MITRAKER/TFT/actions/workflows/codeql.yml/badge.svg)](https://github.com/MITRAKER/TFT/actions/workflows/codeql.yml)
[![Security](https://github.com/MITRAKER/TFT/actions/workflows/security.yml/badge.svg)](https://github.com/MITRAKER/TFT/actions/workflows/security.yml)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/MITRAKER/TFT/badge)](https://scorecard.dev/viewer/?uri=github.com/MITRAKER/TFT)
[![Release](https://img.shields.io/github/v/release/MITRAKER/TFT?include_prereleases&sort=semver)](https://github.com/MITRAKER/TFT/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.11 | 3.12 | 3.13 | 3.14](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue)

The product code lives in [`src/tft`](src/tft). The repository ships with the
quality and security pipeline described below, so every change is tested,
linted, type-checked, scanned and held to the NASA/JPL Power of Ten rules before
it reaches `main`, and every release is a tagged, checksummed build with signed
provenance.

`tft.economy` is a small example module that comes with the scaffold so the
pipeline has real code to run against. Replace it with, or grow it into, the
product.

## Install

```bash
pip install "git+https://github.com/MITRAKER/TFT.git@stable"
python -c "import tft; print(tft.__version__)"
```

`stable` always points at the latest stable release. Pin an exact version with
its tag instead, for example `@v0.1.0`. Release archives, checksums and
provenance attestations are on the [Releases](https://github.com/MITRAKER/TFT/releases) page.

## Development

```bash
git clone https://github.com/MITRAKER/TFT.git
cd TFT
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
python -m pip install -e . -r requirements-dev.txt
pre-commit install
```

Run the same gate CI runs:

```bash
ruff format --check .
ruff check .
mypy
python tools/jpl_check.py --root .
python -m pytest
```

`pre-commit` runs the formatter, the linter, mypy and the Power of Ten checker
on every commit.

## Quality gates

| Workflow | Runs on | What it checks |
| --- | --- | --- |
| [CI](.github/workflows/ci.yml) | pushes to `main`, pull requests | Test suite on Python 3.11 to 3.14 (Linux) and 3.13 (Windows) with 95 % branch coverage required; sdist and wheel build, metadata check and install smoke test |
| [Standards](.github/workflows/standards.yml) | pushes to `main`, pull requests | Formatting, lint (pycodestyle, pyflakes, bugbear, bandit, pylint design limits, Google-style docstrings), `mypy --strict`, and the [NASA/JPL Power of Ten](docs/STANDARDS.md) checker |
| [CodeQL](.github/workflows/codeql.yml) | pushes, pull requests, weekly | GitHub's semantic security analysis of the Python code and of the workflow files themselves |
| [Security](.github/workflows/security.yml) | pushes, pull requests, weekly | `pip-audit` against known vulnerabilities; dependency review of every pull request |
| [Scorecard](.github/workflows/scorecard.yml) | pushes to `main`, weekly | OpenSSF Scorecard supply-chain posture, published to code scanning |
| [Release](.github/workflows/release.yml) | tags `vX.Y.Z` and `vX.Y.Z-label` | Full gate, build, `SHA256SUMS.txt`, SLSA build provenance attestation, GitHub Release with generated notes, and the moving `stable` tag |

[Dependabot](.github/dependabot.yml) opens grouped weekly pull requests for the
GitHub Actions and the Python tooling, and security updates for anything with a
published advisory. Every action is pinned to a full commit SHA and every
workflow token carries the least privilege it needs.

## Standards

The code standards and the mapping of each of the ten NASA/JPL rules to the tool
that enforces it are in [docs/STANDARDS.md](docs/STANDARDS.md).

## Releases and tags

Versions follow [Semantic Versioning](https://semver.org). `vX.Y.Z` tags are
immutable and protected; `stable` moves to the newest stable release. The
step-by-step release process is in [docs/RELEASING.md](docs/RELEASING.md).

## Security

See [SECURITY.md](SECURITY.md) for the supported versions and the private
reporting channel. The repository settings that back the pipeline are listed in
[docs/REPOSITORY_SETTINGS.md](docs/REPOSITORY_SETTINGS.md).

## Repository layout

```text
.github/            workflows, Dependabot, CODEOWNERS, issue and PR templates
docs/               standards, release process, repository settings
src/tft/            the package (product code)
tests/              pytest suite, 95 % branch coverage required
tools/jpl_check.py  NASA/JPL Power of Ten checker
tools/release_version.py  tag-to-version check used by the Release workflow
pyproject.toml      package metadata and every tool's configuration
requirements-dev.txt pinned development and CI tools (Dependabot keeps them current)
```

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

[MIT](LICENSE)
