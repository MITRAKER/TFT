#!/usr/bin/env python3
"""Apply the repository settings that live in GitHub rather than in files.

Everything else in the pipeline is a file in this repository. These settings are
stored by GitHub and need an administrator's token, so run this once after
creating or transferring the repository, and again whenever the rulesets in
``docs/REPOSITORY_SETTINGS.md`` change::

    gh auth login                                                  # once, as an admin
    python tools/configure_repository.py --repo MITRAKER/TFT --dry-run
    python tools/configure_repository.py --repo MITRAKER/TFT

The script drives the GitHub CLI (``gh``). It switches on Dependabot alerts and
security updates, the wider secret-scanning options, private vulnerability
reporting and automatic deletion of merged branches, and it creates or updates
two rulesets: *Protect main* and *Protect release tags*. Every step can be run
again safely.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass

REQUIRED_CHECKS = ("CI passed", "Standards passed", "Analyze (python)", "Analyze (actions)")
"""Status checks a pull request must pass before it can merge into main."""

REPOSITORY_ADMIN_ROLE = 5
"""GitHub's id for the repository *admin* role, used as a ruleset bypass actor."""

Runner = Callable[[Sequence[str], str | None], str]
"""Runs ``gh api`` with the given arguments and optional stdin; returns stdout."""


@dataclass(frozen=True)
class Step:
    """One ``gh api`` call: what it does, its arguments and an optional JSON body."""

    title: str
    args: tuple[str, ...]
    body: dict[str, object] | None = None


def repository_steps(repo: str) -> tuple[Step, ...]:
    """Return the settings for ``repo`` that are single API calls."""
    scanning: dict[str, object] = {
        "security_and_analysis": {
            "secret_scanning": {"status": "enabled"},
            "secret_scanning_push_protection": {"status": "enabled"},
            "secret_scanning_non_provider_patterns": {"status": "enabled"},
            "secret_scanning_validity_checks": {"status": "enabled"},
        }
    }
    return (
        Step(
            "Delete merged branches automatically and suggest updating pull request branches",
            (
                "-X",
                "PATCH",
                f"repos/{repo}",
                "-F",
                "delete_branch_on_merge=true",
                "-F",
                "allow_update_branch=true",
            ),
        ),
        Step("Enable Dependabot alerts", ("-X", "PUT", f"repos/{repo}/vulnerability-alerts")),
        Step(
            "Enable Dependabot security updates",
            ("-X", "PUT", f"repos/{repo}/automated-security-fixes"),
        ),
        Step(
            "Enable secret scanning, push protection, non-provider patterns and validity checks",
            ("-X", "PATCH", f"repos/{repo}", "--input", "-"),
            scanning,
        ),
        Step(
            "Enable private vulnerability reporting",
            ("-X", "PUT", f"repos/{repo}/private-vulnerability-reporting"),
        ),
    )


def main_ruleset() -> dict[str, object]:
    """Return the ruleset that protects the default branch.

    Repository administrators keep a bypass so the owner can push an urgent fix
    directly; remove it once more than one person maintains the project.
    """
    pull_request = {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": True,
        "require_code_owner_review": False,
        "require_last_push_approval": False,
        "required_review_thread_resolution": True,
        "allowed_merge_methods": ["merge", "squash", "rebase"],
    }
    status_checks = {
        "strict_required_status_checks_policy": True,
        "do_not_enforce_on_create": False,
        "required_status_checks": [{"context": context} for context in REQUIRED_CHECKS],
    }
    return {
        "name": "Protect main",
        "target": "branch",
        "enforcement": "active",
        "bypass_actors": [
            {
                "actor_id": REPOSITORY_ADMIN_ROLE,
                "actor_type": "RepositoryRole",
                "bypass_mode": "always",
            }
        ],
        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            {"type": "pull_request", "parameters": pull_request},
            {"type": "required_status_checks", "parameters": status_checks},
        ],
    }


def tag_ruleset() -> dict[str, object]:
    """Return the ruleset that makes ``vX.Y.Z`` tags immutable; ``stable`` stays movable."""
    return {
        "name": "Protect release tags",
        "target": "tag",
        "enforcement": "active",
        "bypass_actors": [],
        "conditions": {"ref_name": {"include": ["refs/tags/v*"], "exclude": []}},
        "rules": [{"type": "deletion"}, {"type": "update"}],
    }


def gh_runner(args: Sequence[str], stdin: str | None) -> str:
    """Run ``gh api`` with ``args`` and return its standard output.

    Raises:
        RuntimeError: If ``gh`` is not installed or the call fails.
    """
    executable = shutil.which("gh")
    if executable is None:
        msg = "the GitHub CLI (gh) is not installed or not on PATH; see https://cli.github.com"
        raise RuntimeError(msg)
    completed = subprocess.run(  # noqa: S603 - fixed executable, arguments built by this script
        [executable, "api", *args],
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        msg = f"gh api {' '.join(args)} failed: {detail}"
        raise RuntimeError(msg)
    return completed.stdout


def apply_step(step: Step, runner: Runner) -> None:
    """Run one step through ``runner``."""
    stdin = json.dumps(step.body) if step.body is not None else None
    _ = runner(step.args, stdin)


def upsert_ruleset(repo: str, ruleset: dict[str, object], runner: Runner) -> str:
    """Create the ruleset, or update the one that already has its name; return which happened."""
    existing = json.loads(runner((f"repos/{repo}/rulesets",), None) or "[]")
    name = ruleset["name"]
    matches = [item["id"] for item in existing if item.get("name") == name]
    body = json.dumps(ruleset)
    if matches:
        _ = runner(("-X", "PUT", f"repos/{repo}/rulesets/{matches[0]}", "--input", "-"), body)
        return "updated"
    _ = runner(("-X", "POST", f"repos/{repo}/rulesets", "--input", "-"), body)
    return "created"


def configure(repo: str, runner: Runner, *, dry_run: bool) -> int:
    """Apply every setting to ``repo`` and return the number of settings handled.

    Raises:
        ValueError: If ``repo`` is not of the form ``OWNER/NAME``.
    """
    if repo.count("/") != 1 or repo.startswith("/") or repo.endswith("/"):
        msg = f"--repo must be OWNER/NAME, got {repo!r}"
        raise ValueError(msg)
    verb = "would apply" if dry_run else "applying"
    steps = repository_steps(repo)
    for step in steps:
        print(f"{verb}: {step.title}")
        if not dry_run:
            apply_step(step, runner)
    rulesets = (main_ruleset(), tag_ruleset())
    for ruleset in rulesets:
        if dry_run:
            print(f"would create or update ruleset: {ruleset['name']}")
            continue
        outcome = upsert_ruleset(repo, ruleset, runner)
        print(f"ruleset {ruleset['name']}: {outcome}")
    return len(steps) + len(rulesets)


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(
        prog="configure_repository",
        description="Apply the GitHub-side settings (security, Dependabot, rulesets).",
    )
    parser.add_argument(
        "--repo", required=True, help="the repository as OWNER/NAME, e.g. MITRAKER/TFT"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="print the steps without calling GitHub"
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the configuration and return the exit status."""
    args = parse_args(argv)
    try:
        count = configure(args.repo, gh_runner, dry_run=args.dry_run)
    except (RuntimeError, ValueError) as error:
        print(f"configure_repository: error: {error}", file=sys.stderr)
        return 1
    state = "checked" if args.dry_run else "applied"
    print(f"configure_repository: {count} setting(s) {state} on {args.repo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
