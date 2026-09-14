"""
Free, no-AI keyword/pattern-based coder for Item 3 (Litigation) sections.

This trades accuracy for zero cost and zero external API calls. It reliably
catches "no litigation" statements and gives a reasonable approximation of
case counts. The more nuanced fields (pending vs. resolved, who's plaintiff,
regulatory) are heuristic guesses based on nearby keywords — not real
comprehension — and should be spot-checked against the source PDF,
especially for FDDs with unusual wording or several cases in Item 3.

Every count comes with an "evidence" snippet explaining what was matched,
so results can be quickly verified by a human instead of trusted blindly.
"""

import re
from typing import List, Tuple

from .schema import Item3Coding

GOVERNMENT_PLAINTIFF_PREFIX = (
    r"(?:State of |Commonwealth of |People of the State of |"
    r"United States of America|United States|U\.S\.)?\s*"
)
ENTITY_SUFFIX = r"(?:,?\s*(?:Inc|L\.?L\.?C\.?|Corp(?:oration)?|Co(?:mpany)?|Ltd)\.?)?"

NO_LITIGATION_PATTERNS = [
    r"no litigation is required to be disclosed",
    r"there is no litigation required to be disclosed",
    r"there (?:is|are) no (?:pending )?litigation",
    r"(?:we are|the company is) not (?:currently |presently )?(?:a party to|involved in) any (?:litigation|lawsuit)",
    r"no lawsuits? (?:is|are|have been) required to be disclosed",
    r"item 3 (?:states|contains) no litigation",
    r"there (?:is|are|were|was) no (?:material )?(?:pending )?(?:lawsuit|lawsuits|legal proceeding)",
]

# The standard FTC Franchise Rule Item 3 template states each disclosure
# category (A, B, C, D...) in the negative when there's nothing to report.
# Two different standard phrasings show up across real FDDs for this same
# boilerplate, e.g. "No such party has an administrative..." vs. "No person
# or company identified in Items 1 or 2 of this Disclosure Document has an
# administrative...". Both mean the same thing, so both are matched here.
NO_SUCH_PARTY_PATTERN = re.compile(
    r"no such party (?:has|is)\b|"
    r"no person or company identified in items? 1 or 2 of this disclosure document (?:has|is)\b",
    re.IGNORECASE,
)
NO_SUCH_PARTY_MIN_COUNT = 2  # require this many repeats before treating as a real signal

# Phrases like "Other than these actions..." or "Except as described above..."
# right before a no-litigation phrase mean "nothing FURTHER" — not "nothing at
# all". If real case captions were already found, a no-litigation phrase should
# not override that.
QUALIFIER_PREFIX_PATTERN = re.compile(
    r"(?:other than|except as|aside from|apart from)[^.]{0,80}$", re.IGNORECASE
)

# Matches case captions like "Smith v. Acme Franchising, Inc." and
# "State of Washington v. JMFS, LLC". The government-plaintiff prefix and the
# entity suffix on BOTH sides fix the two truncation bugs seen in real output:
# lowercase joiner words ("State of California v. ...") and commas before a
# corporate suffix ("XYZ Enterprises, LLC v. ...") were breaking the match
# early, leaving fragments like "California v. Arby" or "LLC v. RS&S LLC".
CASE_CAPTION_PATTERN = re.compile(
    r"\b" + GOVERNMENT_PLAINTIFF_PREFIX +
    r"[A-Z][\w&'\-]*(?:\s+[A-Z][\w&'\-]*){0,4}" + ENTITY_SUFFIX +
    r"\s+v\.?\s+"
    r"[A-Z][\w&'\-]*(?:\s+[A-Z][\w&'\-]*){0,6}" + ENTITY_SUFFIX
)

PENDING_KEYWORDS = [
    "pending", "ongoing", "unresolved", "remains pending", "currently pending",
    "active litigation", "still pending", "case is active",
]

RESOLVED_KEYWORDS = [
    "settled", "dismissed", "resolved", "judgment was entered", "judgment entered",
    "closed", "completed", "concluded", "case was resolved", "matter was settled",
]

FRANCHISEE_PLAINTIFF_KEYWORDS = [
    "franchisee filed", "former franchisee filed", "filed suit against the company",
    "filed a complaint against", "plaintiff franchisee", "franchisee alleges",
    "franchisee brought", "franchisees brought", "filed against the franchisor",
]

FRANCHISOR_PLAINTIFF_KEYWORDS = [
    "the company filed", "we filed suit against", "the company initiated",
    "franchisor filed", "we brought an action against", "the company commenced",
    "filed against the franchisee", "company brought",
]

REGULATORY_KEYWORDS = [
    "federal trade commission", " ftc ", "attorney general",
    "state franchise administrator", "regulatory action", "administrative action by",
    "franchise regulator", "assurance of discontinuance", "consent decree",
    "consent order", "cease and desist",
]

# A regulatory keyword found on its own (not near a case caption) is only
# meaningful if it's (a) actually describing an action, not denying one,
# (b) not just part of the standard state-administrator contact address list
# that appears in every FDD's Item 3 exhibit, and (c) not the standard state
# addendum condition requiring a franchisor to defer fee collection due to
# its financial condition — common regulatory-office boilerplate, not
# litigation or enforcement.
REGULATORY_NEGATION_PATTERN = re.compile(
    r"\b(?:is not|are not|isn't|aren't|not subject to|"
    r"no (?:currently )?(?:effective )?(?:order|action|proceeding)|"
    r"no (?:person|party|company)[^.]{0,90}(?:is|are) subject to)\b",
    re.IGNORECASE,
)
ADDRESS_BLOCK_INDICATOR_PATTERN = re.compile(
    r"\(\d{3}\)\s?\d{3}[-.]?\d{4}"        # phone number, e.g. (217) 782-4465
    r"|\b[A-Z]{2}\s+\d{5}(?:-\d{4})?\b"   # state abbreviation + ZIP, e.g. "IL 62706"
)
FEE_DEFERRAL_PATTERN = re.compile(
    r"deferral requirement|defer(?:s|red|ring)? (?:the )?(?:payment|collection) of "
    r"(?:all )?(?:initial )?fees",
    re.IGNORECASE,
)
NEGATION_LOOKBACK = 150  # characters checked before the keyword for a negation

WINDOW = 300  # characters of context checked around each case caption


def _context_window(text: str, start: int, end: int) -> str:
    lo = max(0, start - WINDOW)
    hi = min(len(text), end + WINDOW)
    return text[lo:hi]


def _any_keyword_in(text: str, keywords: List[str]) -> bool:
    lowered = text.lower()
    return any(kw in lowered for kw in keywords)


def code_item3_keywords(item3_text: str) -> Tuple[Item3Coding, List[str]]:
    """
    Code an Item 3 text block using keyword/pattern heuristics only — no API
    calls. Returns the coded fields plus a list of human-readable evidence
    snippets explaining what was matched, for manual verification.
    """
    evidence: List[str] = []
    lowered = item3_text.lower()

    # --- Case captions ("X v. Y") — computed first, since whether we found any
    # real cases determines how we interpret ambiguous "no litigation" phrasing. ---
    case_matches = list(CASE_CAPTION_PATTERN.finditer(item3_text))
    num_cases_total = len(case_matches)

    num_pending = 0
    num_resolved = 0
    num_franchisee_plaintiff = 0
    num_franchisor_plaintiff = 0
    num_regulatory = 0

    for m in case_matches:
        window = _context_window(item3_text, m.start(), m.end())
        caption = m.group(0)
        matched_any_category = False

        if _any_keyword_in(window, PENDING_KEYWORDS):
            num_pending += 1
            evidence.append(f"'{caption}' -> looks PENDING (nearby keyword match)")
            matched_any_category = True
        if _any_keyword_in(window, RESOLVED_KEYWORDS):
            num_resolved += 1
            evidence.append(f"'{caption}' -> looks RESOLVED (nearby keyword match)")
            matched_any_category = True
        if _any_keyword_in(window, FRANCHISEE_PLAINTIFF_KEYWORDS):
            num_franchisee_plaintiff += 1
            evidence.append(f"'{caption}' -> looks like FRANCHISEE is plaintiff (nearby keyword match)")
            matched_any_category = True
        if _any_keyword_in(window, FRANCHISOR_PLAINTIFF_KEYWORDS):
            num_franchisor_plaintiff += 1
            evidence.append(f"'{caption}' -> looks like FRANCHISOR is plaintiff (nearby keyword match)")
            matched_any_category = True
        if _any_keyword_in(window, REGULATORY_KEYWORDS):
            num_regulatory += 1
            evidence.append(f"'{caption}' -> looks like a REGULATORY action (nearby keyword match)")
            matched_any_category = True

        # A case caption was found, but none of the category keywords appeared
        # nearby — still a detected case, so it needs its own evidence line
        # rather than silently falling through to the generic "nothing found"
        # fallback below (which would contradict num_cases_total > 0).
        if not matched_any_category:
            evidence.append(f"'{caption}' -> case caption found, but no pending/resolved/plaintiff/regulatory keyword nearby to classify it further")

    # Independent regulatory check for actions that may not use "X v. Y" captions
    # (e.g., "In the Matter of..." administrative actions described in prose).
    # Two guards keep this from false-positiving on boilerplate:
    #   - skip if the keyword is actually part of a NEGATIVE statement
    #     ("...is NOT subject to any FTC order")
    #   - skip if it's sitting inside the standard state-regulator contact
    #     address block (detected by a phone number or ZIP code nearby)
    # A hit that survives both counts as one additional case/proceeding, since
    # the schema defines num_cases_total as covering administrative actions too.
    for kw in REGULATORY_KEYWORDS:
        stripped = kw.strip()
        if stripped not in lowered:
            continue
        idx = lowered.find(stripped)
        already_counted = any(stripped in e.lower() for e in evidence)
        if already_counted:
            continue

        preceding = item3_text[max(0, idx - NEGATION_LOOKBACK):idx]
        if REGULATORY_NEGATION_PATTERN.search(preceding):
            continue  # boilerplate negative disclosure, not a real action

        window = _context_window(item3_text, idx, idx + len(stripped))
        if ADDRESS_BLOCK_INDICATOR_PATTERN.search(window):
            continue  # looks like a state regulator contact address, not litigation
        if FEE_DEFERRAL_PATTERN.search(window):
            continue  # standard state addendum fee-deferral condition, not litigation

        snippet = window.strip()
        evidence.append(f"Regulatory keyword '{stripped}' found outside a case caption: ...{snippet}...")
        num_regulatory += 1
        num_cases_total += 1

    # --- No-litigation statement check ---
    # A standard no-litigation phrase only counts if it's NOT qualified by
    # "other than/except as [the actions above]", since that phrasing means
    # "nothing further" rather than "nothing at all". Computed here (after
    # case captions AND the independent regulatory pass) so a narrative-only
    # regulatory action correctly blocks a false "no litigation" reading too.
    no_litigation_phrase_found = False
    for p in NO_LITIGATION_PATTERNS:
        m = re.search(p, lowered)
        if m:
            preceding = lowered[:m.start()]
            if not QUALIFIER_PREFIX_PATTERN.search(preceding):
                no_litigation_phrase_found = True
                break

    no_such_party_count = len(NO_SUCH_PARTY_PATTERN.findall(item3_text))
    no_such_party_boilerplate = no_such_party_count >= NO_SUCH_PARTY_MIN_COUNT

    # Only treat this as "no litigation disclosed" if we also didn't find any
    # actual cases (caption-based or narrative-regulatory) — otherwise a
    # qualified phrase ("no litigation beyond what's described above") would
    # wrongly cancel out real cases.
    no_litigation = (num_cases_total == 0) and (no_litigation_phrase_found or no_such_party_boilerplate)

    if no_litigation_phrase_found:
        evidence.append("Matched a 'no litigation required to be disclosed' style statement.")
    if no_such_party_boilerplate:
        evidence.append(
            f"Found the standard 'No such party has/is...' template {no_such_party_count} times "
            "with no case captions elsewhere — likely the negative/boilerplate form of Item 3."
        )

    litigation_disclosed = 1 if num_cases_total > 0 else 0

    coding = Item3Coding(
        litigation_disclosed=litigation_disclosed,
        no_litigation_statement=1 if no_litigation else 0,
        num_cases_total=num_cases_total,
        num_cases_pending=num_pending,
        num_cases_resolved=num_resolved,
        num_cases_franchisee_plaintiff=num_franchisee_plaintiff,
        num_cases_franchisor_plaintiff=num_franchisor_plaintiff,
        num_cases_regulatory=num_regulatory,
    )

    if not evidence:
        evidence.append("No keyword matches found in this section — verify manually, especially if this seems wrong.")

    return coding, evidence
