#!/usr/bin/env python3
"""Build a Keil uVision project from the command line and report the result as JSON.

Keil's UV4.exe only writes a text log. This wrapper runs it, parses that log into
a machine-readable record (sizes, diagnostics with file:line, artifact hashes) and
exits non-zero when the build fails, so a CI job or an agent can assert on it.

Typical use:

    python keil_build.py --project path/to/template.uvprojx --target template \
        --out build/20261028 --json

Nothing is downloaded to a device here; flashing is a separate step.
"""
import argparse
import datetime
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
DEFAULT_UV4 = r"C:\Keil_v5\UV4\UV4.exe"

# ..\..\device\x.c(106): warning:  #223-D: function "y" declared implicitly
# ..\..\device\x.c(58):  error:  #20: identifier "y" is undefined   (no letter suffix)
DIAG_RE = re.compile(r"^(?P<file>.+?)\((?P<line>\d+)\):\s*(?P<level>warning|error):\s*#\d+(?:-[A-Z])?:\s*(?P<msg>.*)$")
BARE_RE = re.compile(r"^(?P<level>error|warning):\s*(?P<msg>.*)$")
SIZE_RE = re.compile(r"Program Size: Code=(\d+) RO-data=(\d+) RW-data=(\d+) ZI-data=(\d+)")
CLEAN_RE = re.compile(r"0 Error\(s\), 0 Warning\(s\)")

ARTIFACTS = ("objects/template.axf", "objects/template.hex", "objects/template.bin", "listings/template.map")


def parse_log(text):
    """Keil log text -> diagnostics, sizes and the clean-build flag."""
    diags = []
    for raw in text.splitlines():
        line = raw.strip()
        hit = DIAG_RE.match(line)
        if hit:
            diags.append({"level": hit.group("level"),
                          "file": hit.group("file").replace("\\", "/"),
                          "line": int(hit.group("line")),
                          "msg": hit.group("msg").strip()})
            continue
        hit = BARE_RE.match(line)
        if hit:
            diags.append({"level": hit.group("level"), "file": "", "line": 0,
                          "msg": hit.group("msg").strip()})
    sizes = SIZE_RE.search(text)
    return {
        "diagnostics": diags,
        "warnings": sum(1 for d in diags if d["level"] == "warning"),
        "errors": sum(1 for d in diags if d["level"] == "error"),
        "sizes": [int(v) for v in sizes.groups()] if sizes else None,
        "clean": bool(CLEAN_RE.search(text)),
    }


def build(uvprojx, target, out_dir, uv4=DEFAULT_UV4, reuse=False):
    uvprojx = pathlib.Path(uvprojx).resolve()
    out = pathlib.Path(out_dir).resolve()
    folder = uvprojx.parent
    out.mkdir(parents=True, exist_ok=True)
    log = out / "keil.log"
    if log.exists() and not reuse:
        raise SystemExit(f"log already exists, pass --reuse to overwrite: {log}")

    started = datetime.datetime.now(datetime.timezone.utc)
    proc = subprocess.run([uv4, "-r", str(uvprojx), "-t", target, "-o", str(log)],
                          cwd=str(folder), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    text = log.read_text(encoding="utf-8", errors="replace")

    parsed = parse_log(text)
    artifacts = {}
    for name in ARTIFACTS:
        path = folder / name
        if not path.exists():
            continue
        stat = path.stat()
        artifacts[name] = {
            "bytes": stat.st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "fresh": stat.st_mtime >= started.timestamp() - 2,
        }
        shutil.copy2(path, out / path.name)

    sizes = parsed["sizes"]
    success = (parsed["clean"] and proc.returncode == 0
               and len(artifacts) == len(ARTIFACTS)
               and all(a["fresh"] for a in artifacts.values()))
    return {
        "utc": started.isoformat(),
        "uvprojx": str(uvprojx),
        "target": target,
        "exit": proc.returncode,
        "success": success,
        "code": sizes[0] if sizes else None,
        "ro": sizes[1] if sizes else None,
        "rw": sizes[2] if sizes else None,
        "zi": sizes[3] if sizes else None,
        "ram_used": (sizes[2] + sizes[3]) if sizes else None,
        "sizes": sizes,
        "warnings": parsed["warnings"],
        "errors": parsed["errors"],
        "diagnostics": parsed["diagnostics"],
        "log": str(log),
        "artifacts": artifacts,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build a Keil project and report JSON")
    parser.add_argument("--project", required=True, help="path to the .uvprojx")
    parser.add_argument("--target", default="template", help="target name inside the project")
    parser.add_argument("--out", required=True, help="directory for keil.log and copied artifacts")
    parser.add_argument("--uv4", default=DEFAULT_UV4, help="path to UV4.exe")
    parser.add_argument("--reuse", action="store_true", help="allow overwriting an existing keil.log")
    parser.add_argument("--json", action="store_true", help="print only the JSON record")
    args = parser.parse_args(argv)

    record = build(args.project, args.target, args.out, args.uv4, args.reuse)
    manifest_path = pathlib.Path(args.out).resolve() / "manifest.json"
    manifest_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    if not args.json:
        print(pathlib.Path(record["log"]).read_text(encoding="utf-8", errors="replace")[-4000:])
    print(json.dumps(record, indent=2))
    return 0 if record["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
