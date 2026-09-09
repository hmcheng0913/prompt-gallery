#!/usr/bin/env python3
"""
Append new prompts to the existing index.html PROMPTS array.

Usage:
  python append_prompts.py --html current.html --new-prompts new.json --output updated.html

new.json format: array of prompt objects with fields:
  id, title, category, model, source, sourceUrl, previewImage,
  prompt, placeholders, note (optional)
"""

import argparse
import json
import re
import sys
from pathlib import Path

VALID_CATEGORIES = {
    "手繪風格", "照片轉換", "海報設計", "社群圖文",
    "簡報 & 工作", "品牌 & 商品", "插畫 & 3D",
    "建築 & 資訊圖", "時尚 & 攝影"
}

REQUIRED_FIELDS = {
    "id", "title", "category", "model", "source",
    "sourceUrl", "previewImage", "prompt", "placeholders"
}


def js_escape_template(s: str) -> str:
    """Escape a string for JS template literal (backtick string)."""
    return s.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")


def to_js_object(p: dict) -> str:
    """Convert a prompt dict to a JS object literal string."""
    lines = ["  {"]
    lines.append(f'    id: {json.dumps(p["id"], ensure_ascii=False)},')
    lines.append(f'    title: {json.dumps(p["title"], ensure_ascii=False)},')
    lines.append(f'    category: {json.dumps(p["category"], ensure_ascii=False)},')
    lines.append(f'    model: {json.dumps(p["model"], ensure_ascii=False)},')
    lines.append(f'    source: {json.dumps(p["source"], ensure_ascii=False)},')
    lines.append(f'    sourceUrl: {json.dumps(p["sourceUrl"], ensure_ascii=False)},')
    lines.append(f'    previewImage: {json.dumps(p["previewImage"], ensure_ascii=False)},')
    if p.get("note"):
        lines.append(f'    note: {json.dumps(p["note"], ensure_ascii=False)},')
    escaped = js_escape_template(p["prompt"])
    lines.append(f'    prompt: `{escaped}`,')
    placeholders_js = "[" + ", ".join(json.dumps(ph) for ph in p["placeholders"]) + "]"
    lines.append(f'    placeholders: {placeholders_js}')
    lines.append("  }")
    return "\n".join(lines)


def validate(new_prompts: list, existing_html: str) -> list:
    """Validate each prompt; return list of warnings (empty if all good)."""
    warnings = []
    existing_ids = set(re.findall(r'id:\s*"([^"]+)"', existing_html))

    for i, p in enumerate(new_prompts):
        prefix = f"[#{i+1} '{p.get('title', '?')}']"

        # Required fields
        missing = REQUIRED_FIELDS - p.keys()
        if missing:
            warnings.append(f"{prefix} Missing fields: {missing}")

        # ID uniqueness
        if p.get("id") in existing_ids:
            warnings.append(f"{prefix} Duplicate id '{p['id']}' — already in HTML")

        # Category valid
        if p.get("category") not in VALID_CATEGORIES:
            warnings.append(f"{prefix} Unknown category '{p.get('category')}'")

        # Placeholders must be list
        ph = p.get("placeholders")
        if ph is not None and not isinstance(ph, list):
            warnings.append(f"{prefix} placeholders must be a list, got {type(ph).__name__}")

        # If prompt has [VAR] but not in placeholders, flag
        prompt_text = p.get("prompt", "")
        found_vars = set(re.findall(r'\[([A-Z][A-Z0-9_]+)\]', prompt_text))
        declared = set(ph or [])
        undeclared = found_vars - declared
        if undeclared:
            warnings.append(f"{prefix} Prompt contains [{','.join(undeclared)}] not in placeholders")

        # previewImage looks like URL
        if not (p.get("previewImage", "").startswith(("http://", "https://", "data:"))):
            warnings.append(f"{prefix} previewImage doesn't look like a valid URL")

    return warnings


def find_prompts_array_end(html: str) -> int:
    """Find the position right before the closing `];` of PROMPTS array."""
    m = re.search(r"const PROMPTS = \[", html)
    if not m:
        raise ValueError("Cannot find 'const PROMPTS = [' in HTML")
    pos = m.end()
    depth = 0
    while pos < len(html):
        ch = html[pos]
        if ch == "[":
            depth += 1
        elif ch == "]":
            if depth == 0:
                return pos  # position of the closing `]`
            depth -= 1
        pos += 1
    raise ValueError("Cannot find closing `]` of PROMPTS array")


def update_header_count(html: str, new_total: int) -> str:
    """Update '— N 組精選提示詞' in subtitle."""
    new_html = re.sub(
        r'(— )\d+( 組精選提示詞)',
        rf'\g<1>{new_total}\g<2>',
        html,
        count=1
    )
    return new_html


def update_source_count(html: str, source_label: str, new_count: int) -> str:
    """Update source label in meta block, e.g. '蘋果仁 (3)' → '蘋果仁 (5)'."""
    # Match <a ...>{source_label} (N)</a>
    pattern = re.compile(
        r'(<a [^>]+>' + re.escape(source_label) + r' \()\d+(\)</a>)'
    )
    return pattern.sub(rf'\g<1>{new_count}\g<2>', html, count=1)


def merge(html: str, new_prompts: list, strict: bool = False) -> tuple[str, dict]:
    """Insert new prompts into HTML, return (updated_html, stats)."""
    warnings = validate(new_prompts, html)
    if warnings:
        print("⚠️  Validation warnings:", file=sys.stderr)
        for w in warnings:
            print(f"  - {w}", file=sys.stderr)
        if strict:
            raise ValueError("Validation failed (strict mode). Fix warnings or re-run without --strict.")

    # Count existing prompts
    existing_count = html.count("previewImage:")

    # Find insertion point
    closing_pos = find_prompts_array_end(html)

    # Build insertion text
    new_objects = ",\n".join(to_js_object(p) for p in new_prompts)
    insertion = f",\n{new_objects}\n"

    # Insert before the `]`
    # Need to find where to insert: just before the `]`, but after the comma of previous item
    # Look backwards from closing_pos to find the last `}`
    j = closing_pos - 1
    while j > 0 and html[j] in " \n\r\t":
        j -= 1
    if html[j] == ",":
        # Already has trailing comma, just insert
        new_html = html[:j+1] + "\n" + new_objects + "\n" + html[closing_pos:]
    elif html[j] == "}":
        # No trailing comma, add comma and insert
        new_html = html[:j+1] + ",\n" + new_objects + "\n" + html[closing_pos:]
    else:
        # PROMPTS is empty?
        new_html = html[:closing_pos] + "\n" + new_objects + "\n" + html[closing_pos:]

    # Update header total
    new_total = existing_count + len(new_prompts)
    new_html = update_header_count(new_html, new_total)

    # Update source counts in meta block (group by source label)
    from collections import Counter
    source_counts = Counter()
    for p in new_prompts:
        # Map source to display label
        src = p["source"]
        if "蘋果仁" in src:
            source_counts["蘋果仁"] += 1
        elif "MeiGen" in src or "meigen" in p.get("sourceUrl", "").lower():
            source_counts["MeiGen.ai"] += 1
        elif "數位時代" in src or "bnext" in p.get("sourceUrl", "").lower():
            source_counts["數位時代 / 蘇柔瑋"] += 1
        # else: new source, will be flagged below

    for label, add_count in source_counts.items():
        # Find current count in meta
        m = re.search(
            r'<a [^>]+>' + re.escape(label) + r' \((\d+)\)</a>',
            new_html
        )
        if m:
            current = int(m.group(1))
            new_html = update_source_count(new_html, label, current + add_count)
        else:
            print(f"⚠️  Source '{label}' not in meta block — please add manually", file=sys.stderr)

    stats = {
        "added": len(new_prompts),
        "before_total": existing_count,
        "after_total": existing_count + len(new_prompts),
        "warnings": warnings,
        "byte_delta": len(new_html) - len(html),
    }
    return new_html, stats


def main():
    parser = argparse.ArgumentParser(description="Append new prompts to index.html")
    parser.add_argument("--html", required=True, help="Path to current index.html")
    parser.add_argument("--new-prompts", required=True, help="Path to new prompts JSON array")
    parser.add_argument("--output", required=True, help="Output path for updated HTML")
    parser.add_argument("--strict", action="store_true", help="Fail on validation warnings")
    args = parser.parse_args()

    html = Path(args.html).read_text(encoding="utf-8")
    new_prompts = json.loads(Path(args.new_prompts).read_text(encoding="utf-8"))

    if not isinstance(new_prompts, list):
        raise ValueError("--new-prompts must be a JSON array")

    updated_html, stats = merge(html, new_prompts, strict=args.strict)
    Path(args.output).write_text(updated_html, encoding="utf-8")

    print(f"✅ Added {stats['added']} prompts: total {stats['before_total']} → {stats['after_total']}")
    print(f"   File size delta: {stats['byte_delta']:+,} bytes")
    print(f"   Output: {args.output}")
    if stats["warnings"]:
        print(f"   ⚠️  {len(stats['warnings'])} warnings (see above)")


if __name__ == "__main__":
    main()
