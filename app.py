"""
LingoLink — Cross-cultural communication review for international business."""

import html
import json
import os

import anthropic
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# Page configuration  (must be the first Streamlit call)
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="LingoLink",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
COUNTRIES = [
    "United States", "China", "Japan", "Germany", "United Kingdom",
    "France", "India", "Brazil", "South Korea", "Saudi Arabia",
    "United Arab Emirates", "Mexico", "Canada", "Australia", "Singapore",
    "Nigeria", "South Africa", "Netherlands", "Italy", "Spain",
    "Russia", "Indonesia", "Turkey", "Argentina", "Sweden", "Switzerland",
]

SCENARIOS = [
    "Proposal / Pitch",
    "Negotiation Email",
    "Follow-Up Message",
    "Rejection or Decline",
    "Partnership Request",
    "Contract Discussion",
    "Complaint or Escalation",
    "Introduction / Cold Outreach",
]

# Severity colour palette
SEV_BORDER = {"HIGH": "#e2b04a", "MEDIUM": "#c47c2b", "LOW": "#4a90b8"}
SEV_BG     = {
    "HIGH":   "rgba(226,176,74,0.22)",
    "MEDIUM": "rgba(196,124,43,0.22)",
    "LOW":    "rgba(74,144,184,0.22)",
}
SEV_CARD_BG = {
    "HIGH":   "rgba(226,176,74,0.07)",
    "MEDIUM": "rgba(196,124,43,0.07)",
    "LOW":    "rgba(74,144,184,0.07)",
}

# ─────────────────────────────────────────────────────────────────────────────
# System prompt  (verbatim as specified)
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
You are an expert in international business communication and cross-cultural communication theory. 
You analyze draft business communications written by professionals from one country and intended 
for recipients in another country.

Your job is to identify specific phrases or sentences that carry cross-cultural communication risk 
given the sender's cultural background and the receiver's cultural background. You understand 
cultural communication norms across all major international business markets including but not 
limited to: the United States, China, Japan, Germany, the UK, France, India, Brazil, South Korea, 
the Middle East, and Southeast Asia.

You will be given:
- Sender's country
- Receiver's country  
- Business scenario type
- The draft message text

Analyze the message and flag specific phrases that create risk based on the cultural gap between 
the sender and receiver. Only flag genuine mismatches — do not flag phrases that are appropriate 
for the given pairing. Consider the business scenario type when assessing severity and context.

Use these six risk categories:
1. FACE_RISK: Phrasing that could cause the receiver to lose face or feel publicly embarrassed
2. DIRECTNESS_MISMATCH: Tone that is too direct or too indirect for the receiver's cultural norms
3. RELATIONSHIP_BYPASS: Task-first framing that skips relationship-building expectations
4. HIERARCHY_VIOLATION: Language that fails to respect seniority or formality norms
5. URGENCY_PRESSURE: Deadline or pressure language that conflicts with the receiver's pace norms
6. NEGATIVE_FRAMING: Explicit refusal or disagreement where indirection is culturally expected

For each flag provide:
- The exact phrase from the text
- The risk category
- A severity level: LOW, MEDIUM, or HIGH
- A reasoning explanation: 2-3 sentences explaining specifically why this phrase creates risk 
  given this sender-receiver cultural pairing and business scenario
- A recommendation: a concrete suggested alternative phrasing, framed as 
  "Consider: [alternative]" that addresses the cultural risk while preserving the intent

Return ONLY a valid JSON object. No preamble, no explanation, no markdown formatting.

{
  "flags": [
    {
      "phrase": "exact phrase from the text",
      "category": "FACE_RISK | DIRECTNESS_MISMATCH | RELATIONSHIP_BYPASS | HIERARCHY_VIOLATION | URGENCY_PRESSURE | NEGATIVE_FRAMING",
      "severity": "LOW | MEDIUM | HIGH",
      "reasoning": "2-3 sentences explaining the specific cultural risk for this pairing and scenario.",
      "recommendation": "Consider: [alternative phrasing that preserves intent while reducing cultural risk]"
    }
  ],
  "overall_summary": "2-3 sentence overall assessment of the message's cross-cultural risk level and the most important adjustments to make."
}

If no flags are found, return: {"flags": [], "overall_summary": "This message appears well-calibrated for the given cultural pairing and scenario."}\
"""


# ─────────────────────────────────────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────────────────────────────────────

def get_api_key():
    """Return the Anthropic API key from Streamlit secrets or environment."""
    try:
        return st.secrets["ANTHROPIC_API_KEY"]
    except (KeyError, FileNotFoundError):
        pass
    return os.getenv("ANTHROPIC_API_KEY")


def analyze_message(sender, receiver, scenario, message):
    """Send the draft message to Claude and return the raw response text."""
    api_key = get_api_key()
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY not found. "
            "Add it to your .env file or Streamlit secrets."
        )
    client = anthropic.Anthropic(api_key=api_key)
    user_content = (
        f"Sender's Country: {sender}\n"
        f"Receiver's Country: {receiver}\n"
        f"Business Scenario: {scenario}\n\n"
        f"Draft Message:\n{message}"
    )
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    return response.content[0].text


def strip_code_fence(text):
    """Strip optional markdown code fences that Claude may wrap JSON in."""
    t = text.strip()
    if t.startswith("```"):
        # Drop the opening fence line (e.g. ```json)
        t = t.split("\n", 1)[1] if "\n" in t else ""
        # Drop the closing fence
        if t.endswith("```"):
            t = t[:-3]
        elif "\n```" in t:
            t = t.rsplit("\n```", 1)[0]
    return t.strip()


def highlight_text(original, flags):
    """
    Return an HTML string with flagged phrases highlighted by severity.
    The original text is HTML-escaped before processing; highlights are
    injected via <mark> tags using position-based intervals.
    """
    if not flags:
        return html.escape(original).replace("\n", "<br>")

    # Build (start, end, severity) intervals from phrase positions
    intervals = []
    for flag in flags:
        phrase = flag.get("phrase", "").strip()
        severity = flag.get("severity", "LOW")
        if not phrase:
            continue
        idx = original.find(phrase)
        if idx >= 0:
            intervals.append((idx, idx + len(phrase), severity))

    if not intervals:
        return html.escape(original).replace("\n", "<br>")

    # Sort by start position; merge overlapping intervals (keep higher severity)
    intervals.sort(key=lambda x: x[0])
    sev_rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    merged = []
    for start, end, sev in intervals:
        if merged and start < merged[-1][1]:
            ps, pe, psev = merged[-1]
            keep = sev if sev_rank.get(sev, 0) > sev_rank.get(psev, 0) else psev
            merged[-1] = (ps, max(pe, end), keep)
        else:
            merged.append((start, end, sev))

    # Build HTML by iterating through the original text character-by-character
    parts = []
    cursor = 0
    for start, end, sev in merged:
        parts.append(html.escape(original[cursor:start]))
        bg     = SEV_BG.get(sev, SEV_BG["LOW"])
        border = SEV_BORDER.get(sev, SEV_BORDER["LOW"])
        inner  = html.escape(original[start:end])
        parts.append(
            f'<mark style="background:{bg};border-bottom:2px solid {border};'
            f'padding:1px 3px;border-radius:3px;color:inherit;font-weight:500;">'
            f"{inner}</mark>"
        )
        cursor = end
    parts.append(html.escape(original[cursor:]))
    return "".join(parts).replace("\n", "<br>")


def render_flag_card(flag):
    """Return an HTML string for a single flag card."""
    sev     = flag.get("severity", "LOW")
    cat     = flag.get("category", "")
    phrase  = html.escape(flag.get("phrase", ""))
    reason  = html.escape(flag.get("reasoning", ""))
    rec     = html.escape(flag.get("recommendation", ""))
    border  = SEV_BORDER.get(sev, SEV_BORDER["LOW"])
    card_bg = SEV_CARD_BG.get(sev, SEV_CARD_BG["LOW"])

    return f"""
<div style="background:{card_bg};border-left:3px solid {border};border-radius:6px;
     padding:14px 16px;margin-bottom:12px;box-shadow:0 2px 10px rgba(0,0,0,0.2);">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
    <span style="background:{border};color:#1a1a2e;font-size:10px;font-weight:700;
          padding:2px 8px;border-radius:10px;letter-spacing:0.5px;
          font-family:'DM Sans',sans-serif;">{sev}</span>
    <span style="color:{border};font-size:11px;font-weight:600;letter-spacing:0.7px;
          font-family:'DM Sans',sans-serif;">{cat}</span>
  </div>
  <p style="color:#a8b4d0;font-style:italic;font-size:13px;margin:0 0 8px;
     font-family:'DM Sans',sans-serif;">"{phrase}"</p>
  <p style="color:#c8d4e8;font-size:13px;line-height:1.6;margin:0 0 10px;
     font-family:'DM Sans',sans-serif;">{reason}</p>
  <div style="background:rgba(255,255,255,0.05);border-radius:4px;padding:8px 12px;
       border-left:2px solid rgba(255,255,255,0.12);">
    <p style="color:#8eb8d4;font-size:12px;margin:0;line-height:1.5;
       font-family:'DM Sans',sans-serif;">{rec}</p>
  </div>
</div>"""


# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────

def inject_css():
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600;9..40,700&display=swap');

/* ── Global */
html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

/* ── Hide default Streamlit chrome */
#MainMenu      { visibility: hidden; }
footer         { visibility: hidden; }
header         { visibility: hidden; }
.stDeployButton { display: none; }

/* ── Brand name */
.brand-name {
    font-family: 'DM Serif Display', serif !important;
    font-size: 2.5rem;
    color: #e2b04a;
    margin: 0 0 2px 0;
    line-height: 1.1;
    letter-spacing: -0.5px;
}

/* ── Tagline */
.brand-tagline {
    font-size: 0.95rem;
    color: #6a7a98;
    margin: 0 0 22px 0;
    font-weight: 400;
}

/* ── Arrow separator in controls row */
.arrow-sep {
    font-size: 1.3rem;
    color: #e2b04a;
    text-align: center;
    padding-top: 30px;
    opacity: 0.7;
}

/* ── Annotated text display panel */
.text-panel {
    background: #16213e;
    border-radius: 8px;
    padding: 20px 22px;
    border: 1px solid rgba(255,255,255,0.07);
    min-height: 400px;
    font-size: 14px;
    line-height: 1.8;
    color: #c8d4e8;
    word-wrap: break-word;
}

/* ── Column panel label */
.panel-label {
    font-size: 10px;
    font-weight: 700;
    color: #4a5a78;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    margin-bottom: 10px;
}

/* ── Analyze button (gold, prominent) */
div[data-testid="stButton"] > button {
    background-color: #e2b04a !important;
    color: #1a1a2e !important;
    font-weight: 700 !important;
    font-family: 'DM Sans', sans-serif !important;
    border: none !important;
    border-radius: 6px !important;
    transition: background-color 0.2s ease, transform 0.15s ease,
                box-shadow 0.2s ease !important;
    font-size: 13px !important;
    letter-spacing: 0.3px !important;
}

div[data-testid="stButton"] > button:hover {
    background-color: #f0c060 !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 14px rgba(226,176,74,0.35) !important;
}

/* ── Edit Message button (subtle, secondary) */
div[data-testid="stButton"]:has(button[kind="secondary"]) > button {
    background-color: transparent !important;
    color: #7a8aaa !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    box-shadow: none !important;
}

/* ── Text area */
.stTextArea textarea {
    background-color: #16213e !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 8px !important;
    color: #c8d4e8 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 14px !important;
    line-height: 1.75 !important;
    caret-color: #e2b04a;
}

.stTextArea textarea:focus {
    border-color: rgba(226,176,74,0.4) !important;
    box-shadow: 0 0 0 2px rgba(226,176,74,0.08) !important;
}

/* ── Selectboxes */
.stSelectbox [data-baseweb="select"] > div {
    background-color: #16213e !important;
    border-color: rgba(255,255,255,0.1) !important;
}

/* ── Divider */
hr { border-color: rgba(255,255,255,0.07) !important; }

/* ── Custom scrollbar */
::-webkit-scrollbar       { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #16213e; }
::-webkit-scrollbar-thumb { background: #3a4a68; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #4a5a78; }
</style>
""",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Main application
# ─────────────────────────────────────────────────────────────────────────────

def main():
    inject_css()

    # Session state initialisation
    if "result"         not in st.session_state:
        st.session_state.result         = None
    if "analyzed_text"  not in st.session_state:
        st.session_state.analyzed_text  = ""
    if "draft_message"  not in st.session_state:
        st.session_state.draft_message  = ""

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown('<h1 class="brand-name">LingoLink</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="brand-tagline">'
        "AI-powered cross-cultural communication review for international business."
        "</p>",
        unsafe_allow_html=True,
    )

    # ── Controls row ──────────────────────────────────────────────────────────
    c1, c_arr, c2, c3, c4 = st.columns([3, 0.45, 3, 3, 2])

    with c1:
        sender = st.selectbox("Sender's Country", COUNTRIES, key="sender_sel")

    with c_arr:
        st.markdown('<div class="arrow-sep">→</div>', unsafe_allow_html=True)

    with c2:
        # Default receiver index: skip the first entry if it matches sender
        default_rcv_idx = 1 if sender == COUNTRIES[0] else 0
        receiver = st.selectbox(
            "Receiver's Country",
            COUNTRIES,
            index=default_rcv_idx,
            key="receiver_sel",
        )

    with c3:
        scenario = st.selectbox("Business Scenario", SCENARIOS, key="scenario_sel")

    with c4:
        # Small spacer so the button aligns with the selectbox baselines
        st.markdown("&nbsp;", unsafe_allow_html=True)
        analyze_clicked = st.button(
            "Analyze Message",
            use_container_width=True,
            key="analyze_btn",
        )

    # Same-country validation banner
    same_country = sender == receiver
    if same_country:
        st.warning(
            "⚠️  Sender and receiver countries must be different "
            "to perform cross-cultural analysis."
        )

    # ── Severity legend ───────────────────────────────────────────────────────
    st.markdown(
        """
<div style="display:flex;gap:18px;align-items:center;padding:8px 14px;
     background:rgba(255,255,255,0.025);border-radius:6px;
     border:1px solid rgba(255,255,255,0.05);margin:10px 0 18px 0;">
  <span style="font-size:10px;font-weight:700;color:#3a4a68;letter-spacing:1px;
        text-transform:uppercase;font-family:'DM Sans',sans-serif;">Severity</span>
  <span style="display:flex;align-items:center;gap:5px;font-size:12px;
        color:#8a9ab8;font-family:'DM Sans',sans-serif;">
    <span style="width:10px;height:10px;border-radius:2px;background:#e2b04a;
          display:inline-block;flex-shrink:0;"></span>HIGH
  </span>
  <span style="display:flex;align-items:center;gap:5px;font-size:12px;
        color:#8a9ab8;font-family:'DM Sans',sans-serif;">
    <span style="width:10px;height:10px;border-radius:2px;background:#c47c2b;
          display:inline-block;flex-shrink:0;"></span>MEDIUM
  </span>
  <span style="display:flex;align-items:center;gap:5px;font-size:12px;
        color:#8a9ab8;font-family:'DM Sans',sans-serif;">
    <span style="width:10px;height:10px;border-radius:2px;background:#4a90b8;
          display:inline-block;flex-shrink:0;"></span>LOW
  </span>
</div>
""",
        unsafe_allow_html=True,
    )

    # ── Body: two-column layout ───────────────────────────────────────────────
    left_col, right_col = st.columns([58, 42], gap="medium")

    # ── Left column: draft message / annotated output ─────────────────────────
    with left_col:
        st.markdown('<p class="panel-label">Draft Message</p>', unsafe_allow_html=True)

        has_result = st.session_state.result is not None

        if has_result:
            # Show annotated (highlighted) version of the analysed text
            flags = st.session_state.result.get("flags", [])
            annotated_html = highlight_text(st.session_state.analyzed_text, flags)
            st.markdown(
                f'<div class="text-panel">{annotated_html}</div>',
                unsafe_allow_html=True,
            )
            if st.button("✏️  Edit Message", key="edit_btn"):
                st.session_state.result = None
                st.rerun()
        else:
            # Show editable text area; key syncs value into session state
            st.text_area(
                label="draft",
                height=420,
                placeholder=(
                    "Paste your draft email, proposal, or business "
                    "communication here…"
                ),
                label_visibility="collapsed",
                key="draft_message",
            )

    # ── Right column: results panel ───────────────────────────────────────────
    with right_col:
        st.markdown(
            '<p class="panel-label">Analysis Results</p>', unsafe_allow_html=True
        )

        if st.session_state.result:
            flags   = st.session_state.result.get("flags", [])
            summary = html.escape(
                st.session_state.result.get("overall_summary", "")
            )

            # Overall summary card
            st.markdown(
                f"""
<div style="background:rgba(226,176,74,0.08);border-left:3px solid #e2b04a;
     border-radius:6px;padding:14px 18px;margin-bottom:18px;">
  <div style="font-size:10px;font-weight:700;color:#e2b04a;letter-spacing:1px;
       text-transform:uppercase;margin-bottom:6px;
       font-family:'DM Sans',sans-serif;">Overall Assessment</div>
  <p style="color:#c8d4e8;font-size:13px;line-height:1.65;margin:0;
     font-family:'DM Sans',sans-serif;">{summary}</p>
</div>
""",
                unsafe_allow_html=True,
            )

            if flags:
                count = len(flags)
                st.markdown(
                    f'<p style="font-size:11px;color:#4a5a78;margin:0 0 10px;'
                    f'letter-spacing:0.3px;font-family:\'DM Sans\',sans-serif;">'
                    f'{count} issue{"s" if count != 1 else ""} identified</p>',
                    unsafe_allow_html=True,
                )
                for flag in flags:
                    st.markdown(render_flag_card(flag), unsafe_allow_html=True)
            else:
                st.markdown(
                    """
<div style="background:rgba(74,160,100,0.07);border-left:3px solid #4aa064;
     border-radius:6px;padding:14px 16px;">
  <p style="color:#7ab894;font-size:13px;margin:0;line-height:1.6;
     font-family:'DM Sans',sans-serif;">
    ✓ No cross-cultural risk flags identified for this pairing and scenario.
  </p>
</div>""",
                    unsafe_allow_html=True,
                )
        else:
            # Empty-state placeholder
            st.markdown(
                """
<div style="text-align:center;padding:64px 20px 40px;">
  <div style="font-size:2.4rem;opacity:0.13;margin-bottom:14px;">🌐</div>
  <p style="font-size:13px;color:#3a4a68;line-height:1.8;margin:0;
     font-family:'DM Sans',sans-serif;">
    Select countries and a scenario,<br>
    paste your draft in the left panel,<br>
    then click <strong style="color:#e2b04a;">Analyze&nbsp;Message</strong>.
  </p>
</div>""",
                unsafe_allow_html=True,
            )

    # ── Handle Analyze button ─────────────────────────────────────────────────
    if analyze_clicked:
        if same_country:
            st.error("Please select different countries for sender and receiver.")
            st.stop()

        message = st.session_state.get("draft_message", "")
        if not message or not message.strip():
            st.error("Please paste a draft message before analyzing.")
            st.stop()

        with st.spinner("Analyzing cross-cultural communication risks…"):
            try:
                raw    = analyze_message(sender, receiver, scenario, message)
                clean  = strip_code_fence(raw)
                result = json.loads(clean)
                st.session_state.result        = result
                st.session_state.analyzed_text = message
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
            except json.JSONDecodeError as exc:
                st.error(
                    "The analysis response could not be parsed. "
                    f"Please try again. (JSON error: {exc})"
                )
            except anthropic.APIError as exc:
                st.error(f"Anthropic API error: {exc}")
            except Exception as exc:
                st.error(f"An unexpected error occurred: {exc}")


if __name__ == "__main__":
    main()
