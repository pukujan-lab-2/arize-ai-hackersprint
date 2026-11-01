# Vendored ACS runtime

From `Pukujan/agent-custom-setup` 0.2.0 @ `470013ed3380262cc85568bff83e563ecdbab491` (the agent-stack-train certified commit), path `modules/coordination/multi-agent-hotload/v0.1.0/`:
`scripts/seat_protocol.py`, `scripts/watchdog_check.py`, `schema/assignment.schema.json` (stdlib only). The three files are byte-identical to the previous pin (`b8c492b`); only the pin moved.

The full hot-loader install (PCM + CGM + OIO + this runtime, see HOTLOAD.md upstream) lives in the ACS repo and is
installed with its `acs_install.py`. This app vendors only the runtime pieces it uses at run time.

**Hot reload in the app** (`acs_hotload.py`): a daemon thread polls the mtimes of the ACS files
(`.coord/assignment.json`, the ACS board/events under `$ACS_ROOT/.coord/hackathon`, `$ACS_ROOT/.coord/hotload.lock.json`,
and `acs/config.json`) every `ACS_HOTLOAD_INTERVAL` seconds (default 2) and re-reads whatever changed, with no process restart.
`GET /api/acs/hotload` shows the loaded snapshot and version; `POST /api/acs/reload` forces a reload. Set `ACS_HOTLOAD=0` to turn the watcher off.

To update: re-copy the files from a newer ACS commit and bump the SHA above.
