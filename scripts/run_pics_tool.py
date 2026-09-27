#!/usr/bin/env python3
"""Run a PICS set through the CSA beta PICS Tool without a browser session of your own.

CSA asks participants to rebuild their PICS in the tool and submit the tool's output.
The tool is a single self-contained page with no login and no server side, so the whole
step can be driven locally: this loads one endpoint's XMLs at a time, validates them,
and saves out the same two artifacts the Save buttons produce, plus the validation
summary. What it does not do is upload to TEDS, which needs a CSA account.

Requires `spel` (Playwright CLI) on PATH.

  ./scripts/run_pics_tool.py --pics-dir <dir holding ep0/ ep1/ ep2/> --out <dir>

The PICS XMLs are yours to supply. The blank templates are CSA member documents
and are not distributed here; see docs/pics.md.

Exits non-zero if any endpoint reports a validation error.
"""
import argparse
import base64
import json
import pathlib
import re
import shutil
import subprocess
import sys

TOOL_URL = "https://picstool.csa-iot.org/beta/"

# The tool tags loaded files with the endpoint chosen in its "Optional endpoint folder"
# selector, and that tag becomes the EPn/ folder in the saved ZIP. picsfolder() is what
# its onchange handler calls.
LOAD_JS = """(async () => {
  const defs = %(defs)s; const ep = "%(ep)s";
  picsfolder(ep);
  const sel = document.getElementById('picsep'); if (sel) sel.value = ep;
  const fs = defs.map(f => { const b = atob(f.b64); const a = new Uint8Array(b.length);
    for (let i = 0; i < b.length; i++) a[i] = b.charCodeAt(i);
    return new File([a], f.name, {type: 'text/xml'}); });
  const dt = new DataTransfer(); fs.forEach(f => dt.items.add(f));
  await picstool_openfiles(dt.files);
  return 'loaded ' + dt.files.length + ' into EP' + ep;
})()"""

# Validation has to be its own call: it rebuilds the results DOM, and the capture below
# reads that DOM.
VALIDATE_JS = "picstool_validateall(); 'validated'"

SUMMARY_JS = r"""JSON.stringify(
  document.body.innerText.match(/[^\n]*Validated [0-9]+\([0-9]+ selected[^\n]*/g) || [])"""

# saveAs() is how the tool hands a blob to the browser. Swapping it for a collector turns
# each Save button into a value this script can write to disk itself.
CAPTURE_ZIP_JS = """(async () => {
  let zip = null;
  const real = window.saveAs;
  window.saveAs = (blob, name) => { if (name && name.endsWith('.zip')) zip = blob; };
  picstool_downloadall('zip');
  for (let i = 0; i < 300 && !zip; i++) await new Promise(r => setTimeout(r, 100));
  window.saveAs = real;
  if (!zip) return '';
  return await new Promise(r => { const fr = new FileReader();
    fr.onload = () => r(fr.result.split(',')[1]); fr.readAsDataURL(zip); });
})()"""

CAPTURE_TC_JS = """(async () => {
  let tc = null;
  const real = window.saveAs;
  window.saveAs = (blob, name) => { tc = blob; };
  // picstool_savetclist() guards on tclist.length before calling picstool_update(),
  // and it is picstool_update() that fills tclist, not synchronously. After a bare
  // picstool_validateall() tclist is still empty, so prime it and wait for it.
  picstool_update();
  for (let i = 0; i < 200 && tclist.length < 1; i++) await new Promise(r => setTimeout(r, 50));
  if (tclist.length < 1) { window.saveAs = real; return ''; }
  picstool_savetclist();
  for (let i = 0; i < 200 && !tc; i++) await new Promise(r => setTimeout(r, 50));
  window.saveAs = real;
  return tc ? await tc.text() : '';
})()"""


def spel(session, *args, capture_b64=False):
    cmd = ["spel", "--session", session] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"spel failed: {' '.join(cmd[:4])}\n{result.stderr or result.stdout}")
    out = result.stdout.strip()
    return base64.b64decode(out).decode() if capture_b64 else out


def run_endpoint(pics_dir: pathlib.Path, ep: int, out_dir: pathlib.Path) -> list:
    """Drive one endpoint through the tool. Returns its validation summary lines."""
    src = pics_dir / f"ep{ep}"
    if not src.is_dir():
        sys.exit(f"no such endpoint directory: {src}")
    defs = [{"name": f.name, "b64": base64.b64encode(f.read_bytes()).decode()}
            for f in sorted(src.glob("*.xml"))]
    if not defs:
        sys.exit(f"no XML files in {src}")

    session = f"picstool_ep{ep}"
    spel(session, "open", TOOL_URL)
    try:
        print(spel(session, "eval-js", LOAD_JS % {"defs": json.dumps(defs), "ep": ep}))
        spel(session, "eval-js", VALIDATE_JS)
        summary = json.loads(spel(session, "eval-js", "-b", SUMMARY_JS, capture_b64=True))
        zip_b64 = spel(session, "eval-js", "-b", CAPTURE_ZIP_JS, capture_b64=True)
        tclist = spel(session, "eval-js", "-b", CAPTURE_TC_JS, capture_b64=True)
    finally:
        subprocess.run(["spel", "close", "--session", session],
                       capture_output=True, text=True)

    if not zip_b64:
        sys.exit(f"ep{ep}: the tool produced no ZIP")
    (out_dir / f"span-te2-pics-ep{ep}-tool.zip").write_bytes(base64.b64decode(zip_b64))
    if not tclist:
        sys.exit(f"ep{ep}: the tool produced no TC list")
    (out_dir / f"tclist-ep{ep}.json").write_text(tclist)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pics-dir", required=True, help="directory holding ep0/, ep1/, ep2/")
    parser.add_argument("--out", required=True, help="output directory (created)")
    parser.add_argument("--endpoints", nargs="*", type=int, default=[0, 1, 2])
    args = parser.parse_args()

    if shutil.which("spel") is None:
        sys.exit("spel is not on PATH")

    pics_dir = pathlib.Path(args.pics_dir)
    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    errors = 0
    for ep in args.endpoints:
        print(f"\n=== endpoint {ep} ===")
        for line in run_endpoint(pics_dir, ep, out_dir):
            print("  " + line)
            # Each result appears twice, once in the per-file list and once in the
            # per-file section header. Only the first carries the filename.
            match = re.search(r"\.xml: Validated .* and (\d+) errors?\.", line)
            if match:
                errors += int(match.group(1))

    print(f"\nwrote {out_dir}")
    if errors:
        sys.exit(f"{errors} validation error(s); fix the PICS before submitting")
    print("0 validation errors")


if __name__ == "__main__":
    main()
