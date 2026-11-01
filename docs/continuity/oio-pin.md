# OIO pin

Precedent pins observational-issue-ops (OIO) at the certified train commit
`6a9a7cd67810debe0da76e847ac9897ebc281248`. The release train
(`Pukujan/agent-stack-train` stack-releases.json) certifies that commit as
**0.3.0**, and the installer writes the same `oio_version` **0.3.0** to
`.oio/install-manifest.json`. Both numbers are recorded in `pins.oio` under
`.coord/assignment.json`; the commit is the source of truth.

None of OIO's source tree is vendored. The installer copies its managed files
into `.oio/`, `.github/ISSUE_TEMPLATE/`, `.github/scripts/oio_*.py`,
`.github/workflows/issue-triage.yml`, and the `<!-- oio:issue-log-guidance -->`
block in `AGENTS.md`. Project-owned data (`.oio/ontology/project.json`) stays
editable.

## What CI checks

The `gates` job checks out the pinned OIO commit into `.oio-src/` (gitignored)
and runs `tools/validate_oio_adoption.py`, which:

1. Confirms `pins.oio.revision` matches the checkout and the pin doc.
2. Runs the installer's `--check` against this repository and expects `VALID`.
3. Confirms the AGENTS.md OIO guidance block is present.

## Install or move the pin

```bash
git clone https://github.com/Pukujan/observational-issue-ops.git .oio-src
git -C .oio-src checkout 6a9a7cd67810debe0da76e847ac9897ebc281248
python3 -m pip install -r .oio-src/requirements.txt
python3 .oio-src/.github/scripts/oio_installer.py --target "$(pwd)"
python3 tools/validate_oio_adoption.py --helper-root .oio-src
```

To move the pin, change the revision (and train/package versions) in
`.coord/assignment.json` (`pins.oio`), this file, and the `ref:` in
`.github/workflows/ci.yml`, reinstall from that checkout, and re-run the
validator.
