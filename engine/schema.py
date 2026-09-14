"""
Data models and constants for the FDD Item 3 coding scheme.

Kept separate from extraction/API logic so the schema is the single
source of truth — the app, the API prompt, and the spreadsheet columns
all derive from this file.
"""

from pydantic import BaseModel, Field


class Item3Coding(BaseModel):
    """One coded record for a single FDD's Item 3 (Litigation) section."""

    litigation_disclosed: int = Field(
        description="1 if Item 3 contains at least one litigation disclosure; 0 if Item 3 "
                     "states no litigation or an equivalent statement."
    )
    no_litigation_statement: int = Field(
        description="1 if the text explicitly says no litigation is required to be disclosed; "
                     "0 otherwise."
    )
    num_cases_total: int = Field(
        description="Count of each distinct lawsuit, arbitration, administrative action, or "
                     "proceeding disclosed."
    )
    num_cases_pending: int = Field(
        description="Count of cases described as pending, ongoing, unresolved, filed, or active."
    )
    num_cases_resolved: int = Field(
        description="Count of cases described as settled, dismissed, resolved, judgment "
                     "entered, closed, or completed."
    )
    num_cases_franchisee_plaintiff: int = Field(
        description="Count of cases where the franchisee/former franchisee is the plaintiff, "
                     "claimant, or initiating party."
    )
    num_cases_franchisor_plaintiff: int = Field(
        description="Count of cases where the franchisor is the plaintiff or the initiating party."
    )
    num_cases_regulatory: int = Field(
        description="Count of FTC, state attorney general, state franchise regulator, or other "
                     "government actions."
    )


# Column order used in the output spreadsheet
SCHEMA_FIELDS = list(Item3Coding.model_fields.keys())


def build_coding_prompt(item3_text: str) -> str:
    """Build the instruction + data prompt sent to Claude for one FDD."""
    field_descriptions = "\n".join(
        f"- {name}: {field.description}"
        for name, field in Item3Coding.model_fields.items()
    )

    return f"""You are coding Item 3 ("Litigation") sections from Franchise Disclosure
Documents (FDDs) according to a fixed coding scheme. Read the Item 3 text provided and
return ONLY a JSON object (no markdown fences, no commentary) with exactly these fields:

{field_descriptions}

Rules:
- All fields are integers (use 0 if none apply).
- num_cases_total should generally equal or exceed the sum of the more specific categories,
  since a single case can fall into multiple categories (e.g., pending AND franchisor-plaintiff).
- If a field can't be confidently determined, use your best reasonable judgment based on what's
  given rather than omitting it. Every field must be present in your JSON output.
- Return ONLY the JSON object. No preamble, no explanation, no markdown code fences.

Item 3 text to code:

{item3_text}
"""
