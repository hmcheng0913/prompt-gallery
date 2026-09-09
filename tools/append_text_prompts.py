#!/usr/bin/env python3
"""
Append new TEXT prompts to the TEXT_PROMPTS array in index.html.

Usage:
  python append_text_prompts.py --html current.html --new-prompts new.json --output updated.html

new.json format: array of text prompt objects with fields:
  id, title, category, model, source, sourceUrl,
  prompt, placeholders, note (optional), tags (optional)
"""

import argparse
import json
import re
import sys
from pathlib import Path

VALID_CATEGORIES = {
    "提示詞技巧", "模型指南", "職場商業", "AI圖像",
    "工具專屬", "翻譯校正", "學習成長", "AI觀念"
}

REQUIRED_FIELDS = {
    "id", "title", "category", "model", "source",
    "sourceUrl", "prompt", "placeholders"
}


def js_escape_template(s: str) -> str:
    return s.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")


def to_js_object(p: dict) -> str:
    lines = ["  {"]
    lines.append(f'    id: {json.dumps(p["id"], ensure_ascii=False)},')
    lines.append(f'    title: {json.dumps(p["title"], ensure_ascii=False)},')
    lines.append(f'    category: {json.dumps(p["category"], ensure_ascii=False)},')
    lines.append(f'    model: {json.dumps(p["model"], ensure_ascii=False)},')
    lines.append(f'    source: {json.dumps(p["source"], ensure_ascii=False)},')
    lines.append(f'    sourceUrl: {json.dumps(p["sourceUrl"], ensure_ascii=False)},')
    if p.get("note"):
        lines.append(f'    note: {json.dumps(p["note"], ensure_ascii=False)},')
    if p.get("tags"):
        tags_js = "[" + ", ".join(json.dumps(t, ensure_ascii=False) for t in p["tags"]) + "]"
        lines.append(f'    tags: {tags_js},')
    escaped = js_escape_template(p["prompt"])
    lines.append(f'    prompt: `{escaped}`,')
    placeholders_js = "[" + ", ".join(json.dumps(ph) for ph in p["placeholders"]) + "]"
    lines.append(f'    placeholders: {placeholders_js}')
    lines.append("  }")
    return "\n".join(lines)


def validate(new_prompts: list, existing_html: str) -> list:
    warnings = []
    existing_ids = set(re.findall(r'id:\s*"([^"]+)"', existing_html))
    for i, p in enumerate(new_prompts):
        prefix = f"[#{i+1} '{p.get('title', '?')}']"
        missing = REQUIRED_FIELDS - p.keys()
        if missing:
            warnings.append(f"{prefix} Missing fields: {missing}")
        if p.get("id") in existing_ids:
            warnings.append(f"{prefix} Duplicate id '{p['id']}' — already in HTML")
        if p.get("category") not in VALID_CATEGORIES:
            warnings.append(f"{prefix} Unknown category '{p.get('category')}'")
        ph = p.get("placeholders")
        if ph is not None and not isinstance(ph, list):
            warnings.append(f"{prefix} placeholders must be a list")
    return warnings


def find_text_prompts_end(html: str) -> int:
    """Find position right before the closing ]; of TEXT_PROMPTS array."""
    m = re.search(r"const TEXT_PROMPTS = \[", html)
    if not m:
        raise ValueError("Cannot find 'const TEXT_PROMPTS = [' in HTML")
    pos = m.end()
    depth = 0
    while pos < len(html):
        ch = html[pos]
        if ch == "[":
            depth += 1
        elif ch == "]":
            if depth == 0:
                return pos
            depth -= 1
        pos += 1
    raise ValueError("Cannot find closing ] of TEXT_PROMPTS array")


def merge(html: str, new_prompts: list) -> tuple[str, dict]:
    warnings = validate(new_prompts, html)
    if warnings:
        print("⚠️  Validation warnings:", file=sys.stderr)
        for w in warnings:
            print(f"  - {w}", file=sys.stderr)

    existing_count = html.count("// 由 prompt-gallery-curator") + len(
        re.findall(r'id:\s*"[^"]*"', html.split("const TEXT_PROMPTS")[1].split("const TEXT_CATEGORIES")[0])
        if "const TEXT_PROMPTS" in html and "const TEXT_CATEGORIES" in html else []
    )

    closing_pos = find_text_prompts_end(html)
    new_objects = ",\n".join(to_js_object(p) for p in new_prompts)

    j = closing_pos - 1
    while j > 0 and html[j] in " \n\r\t":
        j -= 1

    if html[j] == ",":
        new_html = html[:j+1] + "\n" + new_objects + "\n" + html[closing_pos:]
    elif html[j] == "}":
        new_html = html[:j+1] + ",\n" + new_objects + "\n" + html[closing_pos:]
    else:
        # Empty array (comment only)
        new_html = html[:closing_pos] + "\n" + new_objects + "\n" + html[closing_pos:]

    stats = {
        "added": len(new_prompts),
        "warnings": warnings,
        "byte_delta": len(new_html) - len(html),
    }
    return new_html, stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", required=True)
    parser.add_argument("--new-prompts", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    html = Path(args.html).read_text(encoding="utf-8")
    new_prompts = json.loads(Path(args.new_prompts).read_text(encoding="utf-8"))
    if not isinstance(new_prompts, list):
        raise ValueError("--new-prompts must be a JSON array")

    updated_html, stats = merge(html, new_prompts)
    Path(args.output).write_text(updated_html, encoding="utf-8")

    print(f"✅ Added {stats['added']} text prompts to TEXT_PROMPTS array")
    print(f"   File size delta: {stats['byte_delta']:+,} bytes")
    print(f"   Output: {args.output}")
    if stats["warnings"]:
        print(f"   ⚠️  {len(stats['warnings'])} warnings")


if __name__ == "__main__":
    main()
