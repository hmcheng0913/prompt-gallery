#!/usr/bin/env python3
"""
add_prompts.py — one-shot merger for hmcheng0913/prompt-gallery.

Takes a JSON array of prompt objects (image and/or text prompts mixed),
routes each to the right array in index.html, validates, and syntax-checks
the resulting <script> with `node --check` when node is available.

Usage (run from the repo root):
  python3 tools/add_prompts.py --new-prompts /tmp/new-prompts.json
  python3 tools/add_prompts.py --html index.html --new-prompts new.json --output index.html

Routing rules per object:
  - "type": "image"  → PROMPTS array        (needs previewImage)
  - "type": "text"   → TEXT_PROMPTS array   (no previewImage)
  - no "type"        → image if previewImage present, else text

The "type" key is stripped before writing. Duplicate ids (already in the
HTML or repeated in the batch) are auto-suffixed (-2, -3, …) so a run never
fails on id collisions. Exit code 0 = merged, 1 = nothing merged / error.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import append_prompts as img_mod          # noqa: E402
import append_text_prompts as txt_mod     # noqa: E402


def route(items: list) -> tuple[list, list]:
    images, texts = [], []
    for p in items:
        t = (p.get("type") or "").strip().lower()
        if not t:
            t = "image" if p.get("previewImage") else "text"
        q = {k: v for k, v in p.items() if k != "type"}
        q.setdefault("placeholders", [])
        (images if t == "image" else texts).append(q)
    return images, texts


def dedupe_ids(items: list, html: str) -> list:
    existing = set(re.findall(r'id:\s*"([^"]+)"', html))
    seen = set()
    for p in items:
        base = p.get("id") or "prompt"
        cand, n = base, 1
        while cand in existing or cand in seen:
            n += 1
            cand = f"{base}-{n}"
        if cand != base:
            print(f"   id '{base}' taken → renamed to '{cand}'", file=sys.stderr)
        p["id"] = cand
        seen.add(cand)
    return items


def node_check(html: str) -> bool:
    node = shutil.which("node")
    if not node:
        print("   (node not found — skipping JS syntax check)", file=sys.stderr)
        return True
    scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write("\n".join(scripts))
        path = f.name
    r = subprocess.run([node, "--check", path], capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", default="index.html")
    ap.add_argument("--new-prompts", required=True)
    ap.add_argument("--output", default=None, help="default: overwrite --html")
    args = ap.parse_args()

    html_path = Path(args.html)
    out_path = Path(args.output) if args.output else html_path
    html = html_path.read_text(encoding="utf-8")

    raw = json.loads(Path(args.new_prompts).read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        raw = raw.get("prompts", [raw])
    if not isinstance(raw, list) or not raw:
        print("❌ new-prompts must be a non-empty JSON array", file=sys.stderr)
        sys.exit(1)

    images, texts = route(raw)
    images = dedupe_ids(images, html)
    texts = dedupe_ids(texts, html + json.dumps([p["id"] for p in images]))

    added = 0
    if images:
        html, stats = img_mod.merge(html, images)
        added += stats["added"]
        print(f"✅ PROMPTS      +{stats['added']}")
    if texts:
        html, stats = txt_mod.merge(html, texts)
        added += stats["added"]
        print(f"✅ TEXT_PROMPTS +{stats['added']}")

    if not node_check(html):
        print("❌ JS syntax check failed — output NOT written", file=sys.stderr)
        sys.exit(1)

    out_path.write_text(html, encoding="utf-8")
    total_img = len(re.findall(r"previewImage:", html))
    print(f"📄 wrote {out_path} ({added} added; image prompts now {total_img})")
    sys.exit(0 if added else 1)


if __name__ == "__main__":
    main()
