"""The C.R.S. loader (#63) writes tagged, reversible SQL and the matching engine-cache lines. No database here."""

import json

from tools import crs_load

RECS = [
    {"work_id": "C.R.S. § 18-12-105", "title": "Unlawfully carrying a concealed weapon.", "ord": 0, "body": "18-12-105. text (1) a", "source": "src.pdf"},
    {
        "work_id": "C.R.S. § 18-12-105",
        "title": "Unlawfully carrying a concealed weapon.",
        "ord": 1,
        "body": "(2) b's \"quoted\" $q$ tricky",
        "source": "src.pdf",
    },
]


def test_one_work_one_expression_one_chunk_per_record():
    sql, cache, n_sections, n_chunks = crs_load.build(RECS, "2024", "tag-1")
    assert (n_sections, n_chunks) == (1, 2)
    assert sql.startswith("BEGIN;") and sql.rstrip().endswith("COMMIT;")
    assert sql.count("INSERT INTO legal_graph.work ") == 1 and sql.count("INSERT INTO legal_graph.expression ") == 1
    assert sql.count("INSERT INTO legal_graph.chunk ") == 2
    assert "crs:2024:18-12-105:1" in sql and "'none (not embedded)'" in sql


def test_every_row_is_tagged_and_every_insert_is_idempotent():
    sql, _, _, _ = crs_load.build(RECS, "2024", "tag-1")
    assert "tag-1" in sql
    inserts = [stmt for stmt in sql.split(";\n") if stmt.lstrip().startswith("INSERT")]
    assert len(inserts) == 5 and all("ON CONFLICT" in stmt for stmt in inserts)


def test_chunk_bodies_carry_the_header_the_case_chunks_carry():
    _, cache, _, _ = crs_load.build(RECS, "2024", "t")
    assert cache[0]["body"].startswith("C.R.S. § 18-12-105 | Unlawfully carrying a concealed weapon. | Colorado Revised Statutes 2024\n")
    assert set(cache[0]) == {"chunk_id", "work_id", "ord", "body"}  # the engine cache's row shape


def test_text_with_quotes_and_dollar_tags_is_quoted_safely():
    assert crs_load.q("it's $q$ here") == "$qx$it's $q$ here$qx$"
    sql, _, _, _ = crs_load.build(RECS, "2024", "t")
    assert "b's \"quoted\" $q$ tricky" in sql


def test_rollback_removes_only_what_was_tagged():
    sql = crs_load.rollback("2024", "tag-1")
    assert "crs:2024:%" in sql and "loaded_by' = $q$tag-1$q$" in sql and sql.count("DELETE") == 4
    json.dumps(sql)
