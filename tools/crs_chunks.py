"""Turn the Colorado Revised Statutes' official printout into chunk records for the legal index (#63). Dry run only.

    python tools/crs_chunks.py title-18.txt --prefix 18-12- --out crs_18-12.jsonl

Input is the text of an official title PDF from the General Assembly (leg.colorado.gov, `crs<year>-title-<n>.pdf`,
extracted with any PDF text tool). Output is one JSON line per chunk: `work_id` (the id the citation graph already
uses, `C.R.S. § 18-12-105`), `title`, `ord`, `body`, `source`. It writes a file and nothing else. Loading the
records into `legal_graph.chunk`, embedding them and rebuilding the engine snapshot is a separate, deliberate step.
"""

import argparse
import json
import re
import sys

PAGE_NOISE = re.compile(r"^\s*Colorado Revised Statutes \d{4}\s+Page \d+ of\s+\d+\s+Uncertified Printout\s*$", re.M)
# A section starts a line: "18-12-105.  Unlawfully carrying a concealed weapon - ... (1)  A person ...".
SECTION = re.compile(r"^(\d{1,2}-\d{1,2}(?:\.\d+)?-\d{1,4}(?:\.\d+)?)\.\s{2}(.+)$", re.M)
CHUNK_CHARS = 900


def _heading(body, number):
    """The section's heading: the words after its number up to the first full stop (a heading may wrap lines)."""
    rest = body[len(number) + 1 :].strip()
    m = re.match(r"(.{3,220}?\.)(?:\s|$)", rest)
    return (m.group(1) if m else rest[:120]).strip()


def sections(text, prefix=""):
    """[(section number, heading, body)] in document order, only sections whose number starts with `prefix`."""
    text = PAGE_NOISE.sub("", text)
    marks = list(SECTION.finditer(text))
    out = []
    for i, m in enumerate(marks):
        if not m.group(1).startswith(prefix):
            continue
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = " ".join(text[m.start() : end].split())
        heading = _heading(body, m.group(1))
        out.append((m.group(1), heading, body))
    return out


def chunks(body, size=CHUNK_CHARS):
    """Split a section body into chunks of about `size` characters at sub-section boundaries where possible."""
    parts, current = [], ""
    for piece in re.split(r"(?=\s\(\d+\)\s)", body):
        if current and len(current) + len(piece) > size:
            parts.append(current.strip())
            current = ""
        current += piece
        while len(current) > size * 2:  # a single sub-section far longer than a chunk: cut at a sentence end
            cut = current.rfind(". ", 0, size * 2) + 1 or size * 2
            parts.append(current[:cut].strip())
            current = current[cut:]
    if current.strip():
        parts.append(current.strip())
    return parts


def records(text, prefix="", source="Colorado Revised Statutes (official printout)"):
    for number, heading, body in sections(text, prefix):
        for ord_, part in enumerate(chunks(body)):
            yield {"work_id": f"C.R.S. § {number}", "title": heading, "ord": ord_, "body": part, "source": source}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("text")
    ap.add_argument("--prefix", default="", help="only sections whose number starts with this, e.g. 18-12-")
    ap.add_argument("--out", required=True)
    ap.add_argument("--source", default="Colorado Revised Statutes (official printout)")
    args = ap.parse_args(argv)
    text = open(args.text, encoding="utf-8").read()
    n_sections, n_chunks = set(), 0
    with open(args.out, "w", encoding="utf-8") as f:
        for r in records(text, args.prefix, args.source):
            n_sections.add(r["work_id"])
            n_chunks += 1
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(n_sections)} sections, {n_chunks} chunks -> {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
