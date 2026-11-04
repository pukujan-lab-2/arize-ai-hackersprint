"""Write the SQL that loads `crs_chunks.py` output into the legal index, and the matching engine-cache lines (#63).

    python tools/crs_load.py crs_18-12.jsonl --edition 2024 --sql load.sql --cache cache-lines.jsonl --tag claude-2026-11-04

It only writes files. `load.sql` is one transaction that adds a `node:statute` type, one work and one expression
per section and one chunk per record, every row tagged with `--tag` so `rollback.sql` (printed to stderr) removes
exactly what was added. Chunks get no embedding (`embedding` is NULL, `embed_model` says so): the engine embeds at
query time, and the lexical index builds itself from the chunk body.
"""

import argparse
import hashlib
import json
import re
import sys

TYPE = "node:statute"
COURT = "Colorado Revised Statutes"


def q(value):
    """A SQL string literal. Dollar-quoted with a tag the text cannot contain."""
    text = str(value)
    tag = "q"
    while f"${tag}$" in text:
        tag += "x"
    return f"${tag}${text}${tag}$"


def prefix(rec, edition):
    return f"{rec['work_id']} | {rec['title']} | {COURT} {edition}\n"


def build(records, edition, tag):
    sections = {}
    for r in records:
        sections.setdefault(r["work_id"], []).append(r)
    out = [
        "BEGIN;",
        f"INSERT INTO legal_graph.type_registry (type_key, kind, status, schema_version, definition) VALUES ({q(TYPE)}, 'node', 'accepted', '0.1.0', {q('A statute section (official printout of the Colorado Revised Statutes).')}) ON CONFLICT (type_key) DO NOTHING;",
    ]
    cache, n_chunks = [], 0
    for work_id, recs in sections.items():
        recs.sort(key=lambda r: r["ord"])
        number = re.sub(r"^C\.R\.S\. § ", "", work_id)
        expr_id = f"crs:{edition}:{number}"
        sha = hashlib.sha256("\n".join(r["body"] for r in recs).encode()).hexdigest()
        ext = {"loaded_by": tag, "edition": edition, "source": recs[0]["source"], "section": number}
        out.append(
            f"INSERT INTO legal_graph.work (work_id, node_type, court_id, case_name, ext_ids) VALUES ({q(work_id)}, {q(TYPE)}, {q(COURT)}, {q(recs[0]['title'])}, {q(json.dumps(ext))}::jsonb) ON CONFLICT (work_id) DO NOTHING;"
        )
        out.append(
            f"INSERT INTO legal_graph.expression (expr_id, work_id, opinion_type, content_sha256, text_ref) VALUES ({q(expr_id)}, {q(work_id)}, 'statute', {q(sha)}, {q(recs[0]['source'])}) ON CONFLICT (expr_id) DO NOTHING;"
        )
        for r in recs:
            body = prefix(r, edition) + r["body"]
            chunk_id = f"{expr_id}:{r['ord']}"
            out.append(
                f"INSERT INTO legal_graph.chunk (chunk_id, expr_id, ord, body, embed_model) VALUES ({q(chunk_id)}, {q(expr_id)}, {r['ord']}, {q(body)}, 'none (not embedded)') ON CONFLICT (chunk_id) DO NOTHING;"
            )
            cache.append({"chunk_id": chunk_id, "work_id": work_id, "ord": r["ord"], "body": body})
            n_chunks += 1
    out.append("COMMIT;")
    return "\n".join(out) + "\n", cache, len(sections), n_chunks


def rollback(edition, tag):
    return (
        "BEGIN;\n"
        f"DELETE FROM legal_graph.chunk WHERE expr_id IN (SELECT expr_id FROM legal_graph.expression WHERE expr_id LIKE {q(f'crs:{edition}:%')});\n"
        f"DELETE FROM legal_graph.expression WHERE expr_id LIKE {q(f'crs:{edition}:%')};\n"
        f"DELETE FROM legal_graph.work WHERE ext_ids->>'loaded_by' = {q(tag)};\n"
        f"DELETE FROM legal_graph.type_registry WHERE type_key = {q(TYPE)} AND NOT EXISTS (SELECT 1 FROM legal_graph.work WHERE node_type = {q(TYPE)});\n"
        "COMMIT;\n"
    )


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("records")
    ap.add_argument("--edition", required=True)
    ap.add_argument("--sql", required=True)
    ap.add_argument("--cache", required=True)
    ap.add_argument("--rollback")
    ap.add_argument("--tag", required=True)
    args = ap.parse_args(argv)
    records = [json.loads(line) for line in open(args.records, encoding="utf-8")]
    sql, cache, n_sections, n_chunks = build(records, args.edition, args.tag)
    open(args.sql, "w", encoding="utf-8").write(sql)
    with open(args.cache, "w", encoding="utf-8") as f:
        for row in cache:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")
    if args.rollback:
        open(args.rollback, "w", encoding="utf-8").write(rollback(args.edition, args.tag))
    print(f"{n_sections} sections, {n_chunks} chunks -> {args.sql}, {args.cache}", file=sys.stderr)


if __name__ == "__main__":
    main()
