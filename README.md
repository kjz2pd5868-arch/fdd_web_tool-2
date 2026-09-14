# FDD Item 3 (Litigation) Extractor — Free Version

A small web app: upload FDD PDFs in a browser, get back an Excel spreadsheet
coded according to the Item 3 litigation schema below. **No API key, no
account, and no cost for anyone who uses it** — results come from keyword
and pattern matching, not AI.

## Project structure

```
fdd_web_tool/
├── app.py                  # Streamlit web app (the UI)
├── engine/                 # Extraction + coding logic, separate from the UI
│   ├── schema.py           # Pydantic model — single source of truth for fields
│   ├── pdf_utils.py        # PDF text extraction + Item 3 isolation
│   └── keyword_coder.py    # Keyword/pattern-based coding (no API calls)
├── tests/
│   └── test_engine.py      # pytest tests for schema, isolation, and coding logic
├── requirements.txt
└── .gitignore
```

The `engine/` package has no Streamlit code in it, so if you ever want to
rebuild the UI differently later, the extraction logic doesn't change.

## Important: read this before relying on results

This version trades accuracy for being free and requiring nothing from
users. It's genuinely reliable for some fields and a rough approximation
for others:

- **Reliable**: `no_litigation_statement` — these tend to use standard
  legal boilerplate ("no litigation is required to be disclosed") that's
  easy to catch consistently.
- **Approximate**: `num_cases_total` — counts distinct "X v. Y" style case
  captions. Works well for standard formatting, but franchisors that
  describe cases without a formal caption (or use administrative/arbitration
  language only) may be undercounted.
- **Best-guess heuristic**: `num_cases_pending`, `num_cases_resolved`,
  `num_cases_franchisee_plaintiff`, `num_cases_franchisor_plaintiff`,
  `num_cases_regulatory` — these look for keywords near each case caption
  (e.g., "pending", "settled", "franchisee filed") but don't actually
  understand the sentence. Unusual phrasing will be missed or miscounted.

**Every row in the output includes an `evidence` column** listing exactly
which text triggered each count. Use it to quickly spot-check results
rather than trusting them blindly — especially before using this data in
anything you're publishing or relying on for decisions.

## Variables extracted

| Variable | What it captures |
|---|---|
| `litigation_disclosed` | 1 if Item 3 contains any litigation disclosure, 0 if none |
| `no_litigation_statement` | 1 if text explicitly says no litigation required to be disclosed |
| `num_cases_total` | Count of distinct "X v. Y" style case captions found |
| `num_cases_pending` | Cases with nearby pending/ongoing/unresolved language |
| `num_cases_resolved` | Cases with nearby settled/dismissed/resolved language |
| `num_cases_franchisee_plaintiff` | Cases with nearby language suggesting franchisee is plaintiff |
| `num_cases_franchisor_plaintiff` | Cases with nearby language suggesting franchisor is plaintiff |
| `num_cases_regulatory` | Cases/mentions with nearby FTC/AG/regulator language |
| `evidence` | The specific text snippets that triggered each count above |

## Running it locally in VS Code

1. Open the `fdd_web_tool` folder in VS Code (File → Open Folder).

2. Open a terminal (Terminal → New Terminal) and create a virtual
   environment:
   ```
   python3 -m venv .venv
   ```
   Then activate it:
   - macOS/Linux: `source .venv/bin/activate`
   - Windows: `.venv\Scripts\activate`

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Run the app:
   ```
   streamlit run app.py
   ```
   Opens in your browser at `http://localhost:8501`. This URL only works
   on your own machine — see below for making it usable by others.

5. Run the tests anytime:
   ```
   pytest tests/
   ```

### Reopening it later

Each new terminal session needs the virtual environment reactivated (not
reinstalled):
```
source .venv/bin/activate      # macOS/Linux
streamlit run app.py
```

## Making it usable by other people on other devices

Running it locally only works on your machine. To share it as a real link,
deploy it:

### Streamlit Community Cloud (free, recommended)

1. Push this folder to a new GitHub repo (Source Control panel in VS Code).
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with
   GitHub.
3. Click "New app", pick your repo and `app.py` as the entry point, and
   deploy.
4. You'll get a public URL like `yourapp.streamlit.app` — anyone can open
   it on any device and use it immediately. No API key, no sign-up, no
   cost to you or them.

## If you ever want more accuracy later

The judgment-heavy fields (pending vs. resolved, who's plaintiff) could be
made meaningfully more accurate by having an AI model read and interpret
each case, instead of keyword matching. That's a different tradeoff — it
would cost a small amount per document (typically a fraction of a cent to
a few cents each) and require each user to have their own API key. Worth
knowing this option exists if accuracy becomes more important than being
completely free — happy to help build that version if it's ever useful.
