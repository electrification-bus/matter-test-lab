#!/usr/bin/env python3
"""Dump or compare picsItem itemNumber/support pairs in CSA PICS XML files.

Usage:
  pics_dump.py dump FILE...                 # itemNumber<TAB>support per file
  pics_dump.py cmp FILE_A FILE_B            # side-by-side, flag differences
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
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
