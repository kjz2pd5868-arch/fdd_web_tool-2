"""
FDD Item 3 (Litigation) Extractor — Web App (Free / No-AI version)

A shareable tool: users upload FDD PDFs in their browser, the app extracts
the Item 3 section from each and codes it using keyword/pattern matching
(no API calls, no cost, no account needed), then they download a single
Excel spreadsheet with the results plus an Evidence column for manual
verification.

Run locally:
    streamlit run app.py

Deploy so others can use it (no install needed on their end):
    Push this repo to GitHub, then deploy free on share.streamlit.io
    (Streamlit Community Cloud) — see README for step-by-step.
"""

import io
from datetime import datetime

import pandas as pd
import streamlit as st

from engine import (
    SCHEMA_FIELDS,
    extract_pdf_text,
    isolate_item3,
    code_item3_keywords,
)

st.set_page_config(page_title="FDD Item 3 Extractor", page_icon="📄", layout="centered")

st.title("📄 FDD Item 3 (Litigation) Extractor")
st.write(
    "Upload one or more Franchise Disclosure Document PDFs. This tool finds the "
    "Item 3 (Litigation) section in each and codes it into a spreadsheet — "
    "completely free, no API key or account required."
)

st.info(
    "**How this works:** results are generated using keyword/pattern matching, "
    "not AI. This is reliable for detecting 'no litigation' statements and "
    "approximate case counts, but the more nuanced fields (pending vs. resolved, "
    "who's plaintiff, regulatory actions) are best-guess heuristics. Each result "
    "comes with an **Evidence** note explaining what triggered it — please spot-check "
    "results against the source PDFs before treating them as final.",
    icon="ℹ️",
)

uploaded_files = st.file_uploader(
    "Upload FDD PDFs",
    type=["pdf"],
    accept_multiple_files=True,
)

run_button = st.button("Extract Item 3 Data", type="primary", disabled=not uploaded_files)

# ---------------------------------------------------------------------------
# Processing
# ---------------------------------------------------------------------------

if run_button:
    if not uploaded_files:
        st.warning("Please upload at least one PDF.")
        st.stop()

    results_rows = []
    error_rows = []

    progress_bar = st.progress(0, text="Starting...")
    status_area = st.empty()

    total = len(uploaded_files)

    for i, uploaded_file in enumerate(uploaded_files, start=1):
        fname = uploaded_file.name
        progress_bar.progress(i / total, text=f"Processing {i}/{total}: {fname}")

        try:
            file_bytes = io.BytesIO(uploaded_file.getvalue())
            full_text = extract_pdf_text(file_bytes)
            item3_text = isolate_item3(full_text)

            if not item3_text:
                raise ValueError("Could not locate an Item 3 section in this PDF")

            coded, evidence = code_item3_keywords(item3_text)
            row = {"filename": fname, **coded.model_dump(), "evidence": " | ".join(evidence)}
            results_rows.append(row)

        except Exception as e:
            error_rows.append({"filename": fname, "error": str(e)})
            status_area.warning(f"⚠️ {fname}: {e}")

    progress_bar.progress(1.0, text="Done")

    # -----------------------------------------------------------------
    # Display + download
    # -----------------------------------------------------------------

    st.success(f"Processed {len(results_rows)} of {total} file(s) successfully.")

    result_columns = ["filename"] + SCHEMA_FIELDS + ["evidence"]

    if results_rows:
        results_df = pd.DataFrame(results_rows, columns=result_columns)
        st.subheader("Results")
        st.dataframe(results_df, use_container_width=True)
        st.caption(
            "Check the 'evidence' column for each row to see what text triggered "
            "each count — use it to quickly verify or correct results."
        )
    else:
        results_df = pd.DataFrame(columns=result_columns)

    if error_rows:
        errors_df = pd.DataFrame(error_rows, columns=["filename", "error"])
        with st.expander(f"⚠️ {len(error_rows)} file(s) had errors"):
            st.dataframe(errors_df, use_container_width=True)
    else:
        errors_df = pd.DataFrame(columns=["filename", "error"])

    # Build downloadable Excel file with both sheets
    output_buffer = io.BytesIO()
    with pd.ExcelWriter(output_buffer, engine="openpyxl") as writer:
        results_df.to_excel(writer, sheet_name="Results", index=False)
        errors_df.to_excel(writer, sheet_name="Errors", index=False)
    output_buffer.seek(0)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    st.download_button(
        label="⬇️ Download Excel spreadsheet",
        data=output_buffer,
        file_name=f"fdd_item3_results_{timestamp}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
