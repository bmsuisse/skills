#!/usr/bin/env python3
"""Checks for prepare.py's route handling and batching and for crawl.py's overlap check. Run it after a change:

    uv run --with playwright python selfcheck.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from crawl import PROBE  # noqa: E402
from prepare import fill, find_ids, norm, pack, route_rx  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

# routes
assert norm("/_auth/(admin)/datasets/$id/") == "/datasets/$id"
assert route_rx("/datasets/$id/fields").match("/datasets/ds_1/fields/") and not route_rx("/datasets/$id").match("/datasets/ds_1/fields")
ids = find_ids(["/datasets/$datasetId", "/datasets/$datasetId/fields", "/r/$reportId/edit"], ["/", "/datasets/ds_1", "/r/sales"])
assert ids == {"datasetId": "ds_1", "reportId": "sales"}, ids
assert fill("/datasets/$datasetId/fields", ids) == ("/datasets/ds_1/fields", None)
assert fill("/pbi/$linkId", ids) == (None, "$linkId")

# batches: an area too big for one batch is split, every screen lands once, sizes stay close
screens = [{"area": a, "path": f"/{a}/{i}", "w": 1} for a, n in (("datasets", 9), ("r", 5), ("help", 2)) for i in range(n)]
bs = pack(screens, lambda s: s["w"], 4, 4)
assert len(bs) == 4 and sorted(s["path"] for b in bs for s in b["screens"]) == sorted(s["path"] for s in screens)
assert max(len(b["screens"]) for b in bs) - min(len(b["screens"]) for b in bs) <= 1, [len(b["screens"]) for b in bs]

# overlap: what it must find, and the designs it must leave alone
PAGE = """<body style="font: 14px sans-serif">
<div style="position:relative;width:220px"><button>Option very long label</button>
  <button style="position:absolute;left:60px;top:0">Reset to default</button></div>
<div style="position:relative;width:220px;margin-top:20px"><input style="width:200px;padding-right:30px" value="x">
  <button aria-label="Clear" style="position:absolute;right:4px;top:2px;width:20px">x</button></div>
<div style="position:relative;margin-top:20px"><button aria-label="Inbox"><svg width="16" height="16"></svg></button>
  <span style="position:absolute;left:12px;top:-6px">3</span></div>
<div style="height:80px;overflow:auto;margin-top:20px;position:relative"><div style="height:200px"><button>Hidden row</button></div>
  <div style="position:sticky;bottom:0;background:#fff"><button>Save</button></div></div>
<span style="position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap">Skip to content</span>
</body>"""
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.set_content(PAGE)
    found = page.evaluate(PROBE)["problems"]
    browser.close()
overlaps = [f["where"] for f in found if f["kind"] == "overlap"]
assert overlaps == ["Option very long label / Reset to default"], overlaps
assert not [f for f in found if f["kind"] == "clipped-text"], found
print("ok")
