"""Tests for tools/release_version.py (importable through pytest's ``pythonpath``)."""

from __future__ import annotations

from pathlib import Path

import pytest

import release_version
from release_version import ReleaseTag, parse_tag, read_project_version


def write_pyproject(path: Path, version: str) -> Path:
    pyproject = path / "pyproject.toml"
    pyproject.write_text(f'[project]\nname = "demo"\nversion = "{version}"\n', encoding="utf-8")
    return pyproject


def test_parse_stable_tag() -> None:
    assert parse_tag("v1.2.3") == ReleaseTag("1.2.3", prerelease=False)


@pytest.mark.parametrize("tag", ["v1.2.3-rc.1", "v1.2.3-beta", "v0.1.0-alpha.2"])
def test_parse_prerelease_tag(tag: str) -> None:
    assert parse_tag(tag).prerelease is True


@pytest.mark.parametrize(
    "tag", ["1.2.3", "v1.2", "v1.2.3.4", "stable", "v1.2.3-", "v1.2.3 ", "V1.2.3"]
)
def test_parse_rejects_malformed_tags(tag: str) -> None:
    with pytest.raises(ValueError, match="not of the form"):
        parse_tag(tag)


def test_read_project_version(tmp_path: Path) -> None:
    assert read_project_version(write_pyproject(tmp_path, "0.4.0")) == "0.4.0"


def test_read_project_version_requires_a_string(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "demo"\n', encoding="utf-8")
    with pytest.raises(TypeError, match=r"project\.version"):
        read_project_version(pyproject)


def test_main_accepts_a_matching_stable_tag(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pyproject = write_pyproject(tmp_path, "1.0.0")
    output = tmp_path / "github_output"
    argv = ["--tag", "v1.0.0", "--pyproject", str(pyproject), "--github-output", str(output)]
    assert release_version.main(argv) == 0
    expected = "version=1.0.0\nprerelease=false\n"
    assert output.read_text(encoding="utf-8") == expected
    assert capsys.readouterr().out == expected


def test_main_flags_a_prerelease(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pyproject = write_pyproject(tmp_path, "1.0.0")
    assert release_version.main(["--tag", "v1.0.0-rc.1", "--pyproject", str(pyproject)]) == 0
    assert "prerelease=true" in capsys.readouterr().out


def test_main_rejects_a_mismatch(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pyproject = write_pyproject(tmp_path, "1.0.0")
    assert release_version.main(["--tag", "v1.1.0", "--pyproject", str(pyproject)]) == 1
    err = capsys.readouterr().err
    assert "1.1.0" in err
    assert "1.0.0" in err


def test_main_reports_usage_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pyproject = write_pyproject(tmp_path, "1.0.0")
    assert release_version.main(["--tag", "release-1", "--pyproject", str(pyproject)]) == 2
    assert (
        release_version.main(["--tag", "v1.0.0", "--pyproject", str(tmp_path / "none.toml")]) == 2
    )
    assert "error" in capsys.readouterr().err
