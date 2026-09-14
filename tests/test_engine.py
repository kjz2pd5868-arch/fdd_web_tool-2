"""
Tests for the free/no-AI engine package. No network access needed —
these test the schema, PDF section isolation, and keyword coding logic.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.schema import Item3Coding, SCHEMA_FIELDS
from engine.pdf_utils import isolate_item3
from engine.keyword_coder import code_item3_keywords


def test_schema_fields_match_model():
    expected = {
        "litigation_disclosed",
        "no_litigation_statement",
        "num_cases_total",
        "num_cases_pending",
        "num_cases_resolved",
        "num_cases_franchisee_plaintiff",
        "num_cases_franchisor_plaintiff",
        "num_cases_regulatory",
    }
    assert set(SCHEMA_FIELDS) == expected


def test_item3_coding_accepts_valid_data():
    coding = Item3Coding(
        litigation_disclosed=1,
        no_litigation_statement=0,
        num_cases_total=3,
        num_cases_pending=1,
        num_cases_resolved=2,
        num_cases_franchisee_plaintiff=1,
        num_cases_franchisor_plaintiff=1,
        num_cases_regulatory=0,
    )
    assert coding.num_cases_total == 3


def test_isolate_item3_finds_section_between_headings():
    full_text = (
        "ITEM 1 THE FRANCHISOR\nSome intro text.\n"
        "ITEM 3 LITIGATION\nThere is one pending lawsuit filed by a franchisee.\n"
        "ITEM 4 BANKRUPTCY\nNo bankruptcy history.\n"
    )
    section = isolate_item3(full_text)
    assert section is not None
    assert "pending lawsuit" in section
    assert "bankruptcy" not in section.lower()


def test_isolate_item3_returns_none_when_missing():
    full_text = "ITEM 1 THE FRANCHISOR\nNo Item 3 heading here.\nITEM 4 BANKRUPTCY\n"
    assert isolate_item3(full_text) is None


def test_isolate_item3_prefers_later_match_over_table_of_contents():
    full_text = (
        "TABLE OF CONTENTS\nITEM 3 Litigation ... 5\nITEM 4 Bankruptcy ... 6\n"
        "ITEM 1 THE FRANCHISOR\nIntro.\n"
        "ITEM 3 LITIGATION\nActual litigation content is here.\n"
        "ITEM 4 BANKRUPTCY\nBankruptcy section.\n"
    )
    section = isolate_item3(full_text)
    assert section is not None
    assert "Actual litigation content" in section


def test_keyword_coder_detects_no_litigation_statement():
    text = "There is no litigation required to be disclosed in this Item 3."
    coding, evidence = code_item3_keywords(text)
    assert coding.no_litigation_statement == 1
    assert coding.litigation_disclosed == 0
    assert len(evidence) >= 1


def test_keyword_coder_counts_case_caption_and_pending():
    text = (
        "Smith v. Acme Franchising, Inc. This case is currently pending in "
        "the Superior Court and remains unresolved."
    )
    coding, evidence = code_item3_keywords(text)
    assert coding.num_cases_total == 1
    assert coding.num_cases_pending == 1
    assert coding.litigation_disclosed == 1
    assert any("PENDING" in e for e in evidence)


def test_keyword_coder_counts_resolved_and_franchisee_plaintiff():
    text = (
        "Jones v. Acme Franchising, Inc. The franchisee filed suit against the "
        "Company. The matter was settled and the case was resolved in 2023."
    )
    coding, evidence = code_item3_keywords(text)
    assert coding.num_cases_resolved == 1
    assert coding.num_cases_franchisee_plaintiff == 1


def test_keyword_coder_detects_regulatory_keyword():
    text = (
        "In the Matter of Acme Franchising, the Federal Trade Commission "
        "brought an administrative action against the Company."
    )
    coding, evidence = code_item3_keywords(text)
    assert coding.num_cases_regulatory >= 1


def test_keyword_coder_no_matches_still_returns_evidence_note():
    text = "This section contains unrelated boilerplate text about fees."
    coding, evidence = code_item3_keywords(text)
    assert coding.num_cases_total == 0
    assert len(evidence) == 1
    assert "No keyword matches" in evidence[0]


def test_keyword_coder_detects_standard_ftc_no_litigation_boilerplate():
    # Real-world pattern: the standard FTC Franchise Rule template states
    # each category negatively when nothing is disclosed. No case captions
    # anywhere in this text.
    text = (
        "Item 3:\n"
        "A. No such party has an administrative, criminal or civil action pending "
        "against that person alleging a felony.\n"
        "B. No such party has pending actions, other than routine litigation.\n"
        "C. No such party has been convicted of a felony.\n"
        "D. No such party is subject to a currently effective injunctive order.\n"
    )
    coding, evidence = code_item3_keywords(text)
    assert coding.no_litigation_statement == 1
    assert coding.litigation_disclosed == 0
    assert coding.num_cases_total == 0


def test_qualified_no_litigation_phrase_does_not_cancel_real_cases():
    # "Other than these actions, no litigation is required to be disclosed"
    # means nothing FURTHER — not that there's no litigation at all. Real
    # cases found elsewhere should still count, and no_litigation_statement
    # should NOT be set to 1 here.
    text = (
        "Smith v. Acme Franchising, Inc. was settled in 2020.\n"
        "Other than these actions, no litigation is required to be disclosed in this Item."
    )
    coding, evidence = code_item3_keywords(text)
    assert coding.num_cases_total == 1
    assert coding.litigation_disclosed == 1
    assert coding.no_litigation_statement == 0


def test_unqualified_no_litigation_phrase_with_no_cases_is_detected():
    text = "There is no litigation required to be disclosed in this Item 3."
    coding, evidence = code_item3_keywords(text)
    assert coding.no_litigation_statement == 1
    assert coding.litigation_disclosed == 0
