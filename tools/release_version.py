#!/usr/bin/env python3
"""Check that a release tag matches the version in pyproject.toml.

The Release workflow runs this before anything is built or published. A stable
tag ``vMAJOR.MINOR.PATCH`` must equal ``v`` plus ``project.version``. A tag with a
suffix, such as ``v1.2.0-rc.1``, is a pre-release of that same version: the
suffix is dropped before the comparison and ``prerelease=true`` is reported.

Usage::

    python tools/release_version.py --tag v1.2.0 [--pyproject PATH] [--github-output PATH]

The script prints ``version=`` and ``prerelease=`` lines (and appends them to the
``--github-output`` file when given) and exits with 0 on a match, 1 on a
mismatch and 2 on a malformed tag or an unreadable pyproject.toml.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

TAG_PATTERN = re.compile(r"^v(?P<version>\d+\.\d+\.\d+)(?P<suffix>-[0-9A-Za-z.]+)?$")


@dataclass(frozen=True)
class ReleaseTag:
    """The version a tag names and whether the tag marks a pre-release."""

    version: str
    prerelease: bool


def parse_tag(tag: str) -> ReleaseTag:
    """Split a tag such as ``v1.2.0`` or ``v1.2.0-rc.1`` into its parts.

    Raises:
        ValueError: If ``tag`` is not of the form ``vMAJOR.MINOR.PATCH[-label]``.
    """
    match = TAG_PATTERN.match(tag)
    if match is None:
        msg = f"tag {tag!r} is not of the form vMAJOR.MINOR.PATCH or vMAJOR.MINOR.PATCH-label"
        raise ValueError(msg)
    return ReleaseTag(match.group("version"), match.group("suffix") is not None)


def read_project_version(pyproject: Path) -> str:
    """Return ``project.version`` from ``pyproject``.

    Raises:
        TypeError: If the file has no string ``project.version``.
        OSError: If the file cannot be read.
    """
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    version = data.get("project", {}).get("version")
    if not isinstance(version, str):
        msg = f"{pyproject} has no string project.version"
        raise TypeError(msg)
    return version


def write_outputs(release: ReleaseTag, github_output: Path | None) -> None:
    """Print the outputs and append them to ``github_output`` when a path is given."""
    text = f"version={release.version}\nprerelease={'true' if release.prerelease else 'false'}\n"
    if github_output is not None:
        with github_output.open("a", encoding="utf-8") as handle:
            handle.write(text)
    print(text, end="")


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(
        prog="release_version",
        description="Check that a release tag matches the version in pyproject.toml.",
    )
    parser.add_argument("--tag", required=True, help="the git tag being released, e.g. v1.2.0")
    parser.add_argument(
        "--pyproject",
        type=Path,
        default=Path("pyproject.toml"),
        help="path to pyproject.toml (default: ./pyproject.toml)",
    )
    parser.add_argument(
        "--github-output",
        type=Path,
        default=None,
        help="file to append version= and prerelease= lines to (use $GITHUB_OUTPUT)",
    )
    return parser.parse_args(argv)


def compare(tag: str, release: ReleaseTag, version: str, github_output: Path | None) -> int:
    """Report a mismatch (status 1) or write the outputs (status 0)."""
    if version != release.version:
        print(
            f"release_version: tag {tag} names version {release.version} "
            f"but pyproject.toml says {version}; bump one of them",
            file=sys.stderr,
        )
        return 1
    write_outputs(release, github_output)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the check and return the exit status."""
    args = parse_args(argv)
    try:
        release = parse_tag(args.tag)
        version = read_project_version(args.pyproject)
    except (TypeError, ValueError, OSError) as error:
        print(f"release_version: error: {error}", file=sys.stderr)
        return 2
    return compare(args.tag, release, version, args.github_output)


if __name__ == "__main__":
    raise SystemExit(main())
