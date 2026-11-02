"""Tests for tools/configure_repository.py (importable through pytest's ``pythonpath``)."""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Sequence
from typing import Any

import pytest

import configure_repository as cr

Call = tuple[tuple[str, ...], str | None]


class FakeRunner:
    """Records every ``gh api`` call and answers the ruleset listing."""

    def __init__(self, existing_rulesets: list[dict[str, Any]] | None = None) -> None:
        self.calls: list[Call] = []
        self.existing = existing_rulesets or []

    def __call__(self, args: Sequence[str], stdin: str | None) -> str:
        self.calls.append((tuple(args), stdin))
        if tuple(args) == ("repos/o/r/rulesets",):
            return json.dumps(self.existing)
        return ""


def posted_bodies(runner: FakeRunner, method: str) -> list[dict[str, Any]]:
    return [
        json.loads(stdin)
        for args, stdin in runner.calls
        if args[:2] == ("-X", method) and stdin is not None
    ]


def test_configure_applies_every_setting_and_creates_both_rulesets(
    capsys: pytest.CaptureFixture[str],
) -> None:
    runner = FakeRunner()
    assert cr.configure("o/r", runner, dry_run=False) == 7
    paths = [args for args, _ in runner.calls]
    assert ("-X", "PUT", "repos/o/r/vulnerability-alerts") in paths
    assert ("-X", "PUT", "repos/o/r/automated-security-fixes") in paths
    assert ("-X", "PUT", "repos/o/r/private-vulnerability-reporting") in paths
    rulesets = posted_bodies(runner, "POST")
    assert [ruleset["name"] for ruleset in rulesets] == ["Protect main", "Protect release tags"]
    out = capsys.readouterr().out
    assert "ruleset Protect main: created" in out


def test_main_ruleset_requires_the_pipeline_checks() -> None:
    ruleset: dict[str, Any] = cr.main_ruleset()
    rules = {rule["type"]: rule for rule in ruleset["rules"]}
    checks = rules["required_status_checks"]["parameters"]["required_status_checks"]
    assert [check["context"] for check in checks] == list(cr.REQUIRED_CHECKS)
    assert rules["pull_request"]["parameters"]["required_review_thread_resolution"] is True
    assert {"deletion", "non_fast_forward"} <= set(rules)


def test_tag_ruleset_covers_version_tags_only() -> None:
    ruleset: dict[str, Any] = cr.tag_ruleset()
    assert ruleset["conditions"] == {"ref_name": {"include": ["refs/tags/v*"], "exclude": []}}
    assert [rule["type"] for rule in ruleset["rules"]] == ["deletion", "update"]


def test_configure_updates_an_existing_ruleset() -> None:
    runner = FakeRunner(existing_rulesets=[{"id": 42, "name": "Protect main"}])
    cr.configure("o/r", runner, dry_run=False)
    puts = [args for args, _ in runner.calls if args[:3] == ("-X", "PUT", "repos/o/r/rulesets/42")]
    assert len(puts) == 1
    assert [ruleset["name"] for ruleset in posted_bodies(runner, "POST")] == [
        "Protect release tags"
    ]


def test_secret_scanning_step_sends_a_json_body() -> None:
    runner = FakeRunner()
    cr.configure("o/r", runner, dry_run=False)
    bodies = posted_bodies(runner, "PATCH")
    assert bodies == [
        {
            "security_and_analysis": {
                "secret_scanning": {"status": "enabled"},
                "secret_scanning_push_protection": {"status": "enabled"},
                "secret_scanning_non_provider_patterns": {"status": "enabled"},
                "secret_scanning_validity_checks": {"status": "enabled"},
            }
        }
    ]


def test_dry_run_calls_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    runner = FakeRunner()
    assert cr.configure("o/r", runner, dry_run=True) == 7
    assert runner.calls == []
    out = capsys.readouterr().out
    assert "would apply: Enable Dependabot alerts" in out
    assert "would create or update ruleset: Protect release tags" in out


@pytest.mark.parametrize("repo", ["nope", "/r", "o/", "a/b/c"])
def test_configure_rejects_a_malformed_repo(repo: str) -> None:
    with pytest.raises(ValueError, match="OWNER/NAME"):
        cr.configure(repo, FakeRunner(), dry_run=False)


def test_main_dry_run_succeeds(capsys: pytest.CaptureFixture[str]) -> None:
    assert cr.main(["--repo", "o/r", "--dry-run"]) == 0
    assert "7 setting(s) checked on o/r" in capsys.readouterr().out


def test_main_reports_runner_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def failing(args: Sequence[str], stdin: str | None) -> str:
        raise RuntimeError("HTTP 403: admin rights needed")

    monkeypatch.setattr(cr, "gh_runner", failing)
    assert cr.main(["--repo", "o/r"]) == 1
    assert "admin rights needed" in capsys.readouterr().err


def test_gh_runner_requires_the_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="not installed"):
        cr.gh_runner(("repos/o/r",), None)


def test_gh_runner_reports_failed_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/gh")

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="HTTP 403 Forbidden")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="HTTP 403"):
        cr.gh_runner(("-X", "PUT", "repos/o/r/vulnerability-alerts"), None)


def test_gh_runner_returns_stdout_and_builds_the_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/gh")
    seen: dict[str, Any] = {}

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen["command"] = command
        seen["input"] = kwargs.get("input")
        return subprocess.CompletedProcess(command, 0, stdout="[]", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert cr.gh_runner(("repos/o/r/rulesets",), "{}") == "[]"
    assert seen["command"] == ["/usr/bin/gh", "api", "repos/o/r/rulesets"]
    assert seen["input"] == "{}"
