#!/usr/bin/env python3
"""sharing_guard.py — HARD GATE for guest consent. Given a project and a candidate clip's
source time window(s), reject if it overlaps any family/consent exclusion range.

Load once per project: g = SharingGuard(project_dir)
Check a candidate:     g.violates([(in1,out1),(in2,out2),...])  -> list of overlapped ranges (empty=OK)
CLI: sharing_guard.py <project_dir> <in> <out> [<in> <out> ...]  (exit 1 if it violates)
"""
import sys, json
from pathlib import Path

class SharingGuard:
    def __init__(self, project_dir):
        self.ranges = []
        p = Path(project_dir) / "sharing_exclusions.json"
        if p.exists():
            d = json.loads(p.read_text())
            self.ranges = [(r["start"], r["end"], r.get("reason","")) for r in d.get("exclude", [])]
        self.loaded = p.exists()

    def violates(self, windows, pad=0.5):
        """windows: list of (source_in, source_out) in the SAME time base as the exclusions.
        Returns list of (start,end,reason) exclusion ranges the windows overlap."""
        hits = []
        for (a, b) in windows:
            for (s, e, why) in self.ranges:
                if a < e + pad and b > s - pad:
                    hits.append((s, e, why))
        return hits

if __name__ == "__main__":
    if len(sys.argv) < 4 or len(sys.argv) % 2 != 0:
        print("usage: sharing_guard.py <project_dir> <in> <out> [<in> <out> ...]"); sys.exit(2)
    proj = sys.argv[1]
    nums = [float(x) for x in sys.argv[2:]]
    wins = list(zip(nums[0::2], nums[1::2]))
    g = SharingGuard(proj)
    if not g.loaded:
        print(f"WARN: no sharing_exclusions.json in {proj} — no consent file. For a named guest, STOP and check.")
    h = g.violates(wins)
    if h:
        print("BLOCKED — clip overlaps consent-excluded content:")
        for s,e,why in h: print(f"  {s:.0f}-{e:.0f}s: {why}")
        sys.exit(1)
    print("OK — no consent-excluded content in this clip.")
