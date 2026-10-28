# keil-build-json

Build a Keil uVision project from the command line and get the result back as JSON:
sizes, warnings and errors with `file:line`, artifact hashes, and a non-zero exit
code when the build fails.

Keil's `UV4.exe` (5.06 and later) only writes a text log. This wrapper runs it in
batch mode, parses that log, and returns something a script can assert on — so a
CI job or an automated assistant does not have to scrape log text.

## Why

- `UV4.exe -r` works, but the only output is `keil.log`, and the exit code alone
  does not tell you whether a *stale* artifact was reused.
- Trimming "0 Error(s), 0 Warning(s)" out of a log with regexes is repeated work
  in every project.

## Usage

```bash
python keil_build.py --project path/to/template.uvprojx --target template \
                     --out build/20261028 [--json]
```

- `--out` receives `keil.log`, `manifest.json` and a copy of `template.axf/.hex/.bin` and the map file.
- `--json` prints only the JSON record (no log tail).
- `--reuse` allows overwriting an existing `keil.log` in `--out`.

Exit code: `0` when the build is clean, `1` when it failed.

## JSON record

```json
{
  "utc": "2026-10-28T10:14:50+00:00",
  "uvprojx": "D:/proj/.../template.uvprojx",
  "target": "template",
  "exit": 0,
  "success": true,
  "code": 212452,
  "ro": 11504,
  "rw": 460,
  "zi": 81028,
  "ram_used": 81488,
  "sizes": [212452, 11504, 460, 81028],
  "warnings": 0,
  "errors": 0,
  "diagnostics": [
    {"level": "warning", "file": "../../../device/dev_spi_flash.c", "line": 106, "msg": "#223-D: ..."}
  ],
  "log": "D:/proj/build/20261028/keil.log",
  "artifacts": {
    "objects/template.axf": {"bytes": 2091736, "sha256": "b7cb...", "fresh": true}
  }
}
```

`success` requires all of: a clean log, `UV4` exit code 0, all four artifacts
present, and every artifact written after the build started (this catches a
build that silently reused old output).

`ram_used` is `rw + zi` — the number that matters for a RAM-limited part.

## Requirements

- Keil MDK installed (`UV4.exe`, default `C:\Keil_v5\UV4\UV4.exe`, override with `--uv4`)
- Python 3.8+
- Windows (UV4.exe is Windows-only)

## Test

```bash
python tests/test_parse.py
```

The parser tests run on captured log fixtures; no Keil and no compiler needed.

## Caveat

`UV4.exe` writes artifacts into the project's own `objects/` directory, so two
builds of the same project cannot run at the same time. Use a separate checkout
(or a separate `--out` per build with serialized execution) when building in parallel.

## License

MIT — see [LICENSE](LICENSE).
