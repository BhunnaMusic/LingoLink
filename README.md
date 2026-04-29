# LingoLink

**AI-powered cross-cultural communication review for international business.**

LingoLink analyzes draft emails, proposals, and negotiation messages for cross-cultural tone risks before you send them. Paste your draft, select the sender and receiver countries and a business scenario, and the tool calls Claude to flag specific phrases that could cause misunderstandings — with explanations and rewrite suggestions for each one.

---

## Features

- **26 country pairings** — covers all major international business markets
- **8 business scenario types** — from cold outreach to contract discussions
- **6 risk categories** — FACE_RISK, DIRECTNESS_MISMATCH, RELATIONSHIP_BYPASS, HIERARCHY_VIOLATION, URGENCY_PRESSURE, NEGATIVE_FRAMING
- **Inline highlighting** — flagged phrases highlighted in the original text by severity (HIGH / MEDIUM / LOW)
- **Flag cards** — each issue shows the risk category, reasoning, and a concrete "Consider:" rewrite suggestion
- Powered by **Claude claude-sonnet-4-20250514** via the Anthropic API

---

## Project Structure

```
LingoLink/
├── app.py                   ← Main Streamlit application
├── .env                     ← Your API key (NOT tracked by git)
├── .gitignore
├── requirements.txt
└── .streamlit/
    └── config.toml          ← Dark theme + gold accent
```

---

## Prerequisites

- Python 3.9 or higher (Python 3.14 was used in development via `uv`)
- An [Anthropic API key](https://console.anthropic.com/)

---

## Setup & Running Locally

### 1. Clone or download the project

```powershell
cd C:\Users\Brayden\LingoLink
```

### 2. Create and activate a virtual environment

```powershell
uv venv .venv
```

Then activate it. Because PowerShell's execution policy may block `.ps1` scripts, use either:

```powershell
# Option A — change execution policy for this session only (recommended)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1

# Option B — use cmd.exe instead
cmd /k ".venv\Scripts\activate.bat"
```

### 3. Install dependencies

```powershell
uv pip install -r requirements.txt
```

> If you skipped the venv activation, the packages were already installed into `.venv` by the setup script. Just activate before running.

### 4. Add your Anthropic API key

Open the `.env` file in the project root and replace the placeholder:

```
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

Replace `your_anthropic_api_key_here` with your actual key from [console.anthropic.com](https://console.anthropic.com/). The file already exists — just edit it.

> `.env` is listed in `.gitignore` and will never be committed to git.

### 5. Run the app

```powershell
streamlit run app.py
```

Streamlit will open `http://localhost:8501` in your browser automatically.

---

## Deploying to Streamlit Cloud

1. Push the project to a GitHub repository (`.env` is gitignored — it won't be included).
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect your repo.
3. In the app settings, open **Secrets** and add:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```
4. Deploy. The app reads `st.secrets["ANTHROPIC_API_KEY"]` automatically on Streamlit Cloud.

---

## Usage

1. Select **Sender's Country** and **Receiver's Country** (must be different).
2. Choose a **Business Scenario** from the dropdown.
3. Paste your draft message into the left text panel.
4. Click **Analyze Message**.
5. Review the highlighted text on the left and the flag cards on the right.
6. Click **✏️ Edit Message** to revise and re-analyze.

---

## Risk Categories

| Category | Description |
|---|---|
| `FACE_RISK` | Phrasing that could cause the receiver to lose face or feel embarrassed |
| `DIRECTNESS_MISMATCH` | Tone too direct or too indirect for the receiver's cultural norms |
| `RELATIONSHIP_BYPASS` | Task-first framing that skips expected relationship-building |
| `HIERARCHY_VIOLATION` | Language that fails to respect seniority or formality norms |
| `URGENCY_PRESSURE` | Deadline/pressure language that conflicts with receiver's pace norms |
| `NEGATIVE_FRAMING` | Explicit refusal or disagreement where indirection is culturally expected |

---

## Tech Stack

| | |
|---|---|
| **Framework** | [Streamlit](https://streamlit.io) |
| **AI model** | Claude claude-sonnet-4-20250514 (Anthropic) |
| **API client** | [anthropic-sdk-python](https://github.com/anthropic/anthropic-sdk-python) |
| **Env vars** | [python-dotenv](https://github.com/theskumar/python-dotenv) |
| **Fonts** | DM Serif Display + DM Sans (Google Fonts) |
