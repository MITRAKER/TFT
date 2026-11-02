# Releasing

## Versions and tags

- Versions follow [Semantic Versioning](https://semver.org): `MAJOR.MINOR.PATCH`.
- A release is a git tag `vMAJOR.MINOR.PATCH` on `main`, for example `v0.1.0`. These tags are **immutable**: a repository ruleset blocks updating or deleting them. To fix a bad release, ship the next patch version.
- A pre-release is a tag with a suffix, for example `v0.2.0-rc.1`. The package version stays `0.2.0`; the suffix only marks the candidate.
- `stable` is a **moving** tag that the Release workflow points at the newest stable release. `pip install "git+https://github.com/MITRAKER/TFT.git@stable"` always installs that release; pin `@v0.1.0` for an exact version.
- The single source of truth for the version is `project.version` in `pyproject.toml`. `tft.__version__` reads it from the installed metadata, and the Release workflow refuses a tag that does not match it.

## Cutting a release

1. Make sure `main` is green: CI, Standards, CodeQL and Security.
2. On a branch, set `version` in `pyproject.toml`, move the **Unreleased** entries in `CHANGELOG.md` under a new `## [X.Y.Z] - YYYY-MM-DD` heading, and open a pull request titled `release: vX.Y.Z`.
3. Merge it. Then tag the merge commit and push the tag:

   ```bash
   git checkout main
   git pull
   git tag -a vX.Y.Z -m "Release vX.Y.Z"
   git push origin vX.Y.Z
   ```

4. Watch the **Release** workflow. It:
   - checks that the tag matches `pyproject.toml` (`tools/release_version.py`);
   - runs the full gate again: formatting, lint, `mypy`, Power of Ten, tests;
   - builds the sdist and the wheel, checks their metadata and writes `SHA256SUMS.txt`;
   - signs a SLSA build provenance attestation for the artifacts;
   - creates the GitHub Release with notes generated from the merged pull requests (categories in `.github/release.yml`);
   - for a stable release, moves the `stable` tag to the release commit and marks the release as *Latest*.

**Without a local git push:** open the Release workflow under Actions, press *Run workflow*,
choose `main` and type the version (for example `0.2.0`). The workflow creates the tag
itself and continues exactly as above. The version must already match `pyproject.toml`.

For a release candidate, tag `vX.Y.Z-rc.N` instead. The workflow marks it as a
pre-release and leaves `stable` where it is.

## Verifying a release

```bash
gh release download vX.Y.Z --repo MITRAKER/TFT
sha256sum --check SHA256SUMS.txt
gh attestation verify tft-X.Y.Z-py3-none-any.whl --repo MITRAKER/TFT
```

## If something goes wrong

- A failed **verify** job means the tag and `pyproject.toml` disagree, or the gate failed. Fix `main`, bump the version, and tag again with the next number. Do not move or delete the tag.
- A failed **publish** job after the release exists: re-run the job. `gh release create` fails on an existing release, so delete the half-made release (not the tag) in the GitHub UI first.
