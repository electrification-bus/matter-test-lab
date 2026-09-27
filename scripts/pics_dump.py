#!/usr/bin/env python3
"""Dump, compare, or find coverage gaps in CSA PICS XML files.

Usage:
  pics_dump.py dump FILE...                 # itemNumber<TAB>support per file
  pics_dump.py cmp FILE_A FILE_B            # side-by-side, flag differences
  pics_dump.py gap TEMPLATE FILLED...       # what the template defines and
                                            # nothing in FILLED supports

`gap` answers the question a release cycle cares about: does the reference app
exercise the surface the specification defines? The blank template is that
surface, the filled set is what the device reports, and the difference is the
candidate gap. Pass every endpoint's file for the cluster, since an element
unreachable on one endpoint may be present on another.

Its output needs triage, not blind action. Some entries are unreachable by
construction: features under a `choice` conformance are mutually exclusive, so
one endpoint can never offer all of them, and an element whose conformance is
`X` cannot be offered by any conformant server.
"""
import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict


def items(path):
    out = OrderedDict()
    for pi in ET.parse(path).getroot().iter("picsItem"):
        num = pi.findtext("itemNumber", "").strip()
        sup = (pi.findtext("support") or "").strip()
        out[num] = sup
    return out


def gaps(template_path, filled_paths):
    """Template items that no filled file marks supported."""
    supported = set()
    for path in filled_paths:
        supported |= {k for k, v in items(path).items() if v == "true"}
    return [k for k in items(template_path) if k not in supported]


def main(argv):
    mode = argv[1]
    if mode == "dump":
        for p in argv[2:]:
            print(f"### {p}")
            for k, v in items(p).items():
                print(f"{k}\t{v}")
    elif mode == "cmp":
        a, b = items(argv[2]), items(argv[3])
        for k in list(a) + [k for k in b if k not in a]:
            va, vb = a.get(k, "-"), b.get(k, "-")
            flag = "" if va == vb else "  <<< DIFF"
            print(f"{k:40s} {va:8s} {vb:8s}{flag}")
    elif mode == "gap":
        missing = gaps(argv[2], argv[3:])
        for k in missing:
            print(k)
        print(f"# {len(missing)} of {len(items(argv[2]))} template items unsupported",
              file=sys.stderr)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
