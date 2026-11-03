"""The C.R.S. chunker (#63): sections out of an official printout, ids that match the citation graph."""

from tools import crs_chunks

TEXT = """18-12-101.  Definitions. (1)  As used in this article, "firearm" means a weapon.
(2)  "Handgun" means a firearm.
Colorado Revised Statutes 2024 Page 569 of  783 Uncertified Printout
18-12-105.  Unlawfully carrying a concealed weapon - unlawful possession of
weapons. (1)  A person commits a class 1 misdemeanor if the person knowingly and unlawfully:
(a)  Carries a firearm concealed on or about his or her person.
(2)  It is not an offense if the defendant was in his or her own dwelling.
19-1-101.  Another title. (1)  Not firearms.
"""


def test_sections_use_the_ids_the_citation_graph_uses():
    ids = [r["work_id"] for r in crs_chunks.records(TEXT, prefix="18-12-")]
    assert set(ids) == {"C.R.S. § 18-12-101", "C.R.S. § 18-12-105"}


def test_a_heading_that_wraps_lines_is_whole_and_page_noise_is_dropped():
    rs = list(crs_chunks.records(TEXT, prefix="18-12-"))
    heading = next(r["title"] for r in rs if r["work_id"].endswith("105"))
    assert heading == "Unlawfully carrying a concealed weapon - unlawful possession of weapons."
    assert not any("Uncertified Printout" in r["body"] for r in rs)


def test_long_sections_are_split_and_short_ones_are_not():
    long_body = "18-12-300.  Big. " + " ".join(f"({i})  " + "A sentence about permits. " * 8 for i in range(1, 12))
    parts = [r for r in crs_chunks.records(long_body, prefix="18-12-")]
    assert len(parts) > 1 and [r["ord"] for r in parts] == list(range(len(parts)))
    assert len([r for r in crs_chunks.records(TEXT, prefix="18-12-101")]) == 1


def test_the_prefix_filters_sections():
    assert not [r for r in crs_chunks.records(TEXT, prefix="19-") if r["work_id"].startswith("C.R.S. § 18")]
