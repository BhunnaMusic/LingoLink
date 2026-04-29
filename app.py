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


def render_flag_card(flag, index=0):
    """Return an HTML string for a single flag card."""
    sev     = flag.get("severity", "LOW")
    cat     = flag.get("category", "")
    phrase  = html.escape(flag.get("phrase", ""))
    reason  = html.escape(flag.get("reasoning", ""))
    rec     = html.escape(flag.get("recommendation", ""))
    border  = SEV_BORDER.get(sev, SEV_BORDER["LOW"])
    card_bg = SEV_CARD_BG.get(sev, SEV_CARD_BG["LOW"])
    delay   = f"{index * 0.05:.2f}s"

    # Category icon mapping
    cat_icons = {
        "FACE_RISK":            "◈",
        "DIRECTNESS_MISMATCH":  "⇄",
        "RELATIONSHIP_BYPASS":  "◎",
        "HIERARCHY_VIOLATION":  "△",
        "URGENCY_PRESSURE":     "◷",
        "NEGATIVE_FRAMING":     "⊘",
    }
    icon = cat_icons.get(cat, "◆")

    return f"""
<div class="flag-card-animate" style="background:{card_bg};border-left:3px solid {border};
     border-radius:8px;padding:14px 16px;margin-bottom:10px;
     box-shadow:0 2px 12px rgba(0,0,0,0.25),0 0 0 1px rgba(255,255,255,0.03);
     animation-delay:{delay};cursor:default;
     transition:box-shadow 0.2s ease,transform 0.2s ease;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:9px;">
    <div style="display:flex;align-items:center;gap:7px;">
      <span style="color:{border};font-size:14px;line-height:1;opacity:0.9;">{icon}</span>
      <span style="color:{border};font-size:10px;font-weight:700;letter-spacing:0.8px;
            text-transform:uppercase;font-family:'DM Sans',sans-serif;">{cat.replace("_", " ")}</span>
    </div>
    <span style="background:{border};color:#1a1a2e;font-size:9px;font-weight:800;
          padding:2px 7px;border-radius:8px;letter-spacing:0.6px;
          font-family:'DM Sans',sans-serif;">{sev}</span>
  </div>
  <p style="color:#8090b0;font-style:italic;font-size:12.5px;margin:0 0 9px;
     line-height:1.55;font-family:'DM Sans',sans-serif;border-left:1px solid rgba(255,255,255,0.06);
     padding-left:8px;">"{phrase}"</p>
  <p style="color:#9aaac0;font-size:12.5px;line-height:1.65;margin:0 0 10px;
     font-family:'DM Sans',sans-serif;">{reason}</p>
  <div style="background:rgba(255,255,255,0.03);border-radius:5px;padding:9px 12px;
       border:1px solid rgba(255,255,255,0.06);">
    <span style="font-size:9px;font-weight:700;color:#3a5070;letter-spacing:0.8px;
          text-transform:uppercase;display:block;margin-bottom:4px;
          font-family:'DM Sans',sans-serif;">Suggestion</span>
    <p style="color:#7aaccc;font-size:12.5px;margin:0;line-height:1.55;
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

/* ── Motion preference ── */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
}

/* ── Card entrance animation ── */
@keyframes fadeSlideUp {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}
.flag-card-animate { animation: fadeSlideUp 0.25s ease forwards; }

/* ── Global ── */
html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
    background-color: #1a1a2e;
}

/* ── Hide default Streamlit chrome ── */
#MainMenu      { visibility: hidden; }
footer         { visibility: hidden; }
header         { visibility: hidden; }
.stDeployButton { display: none; }
[data-testid="stAppViewBlockContainer"] { padding-top: 1.5rem !important; }
[data-testid="stMainBlockContainer"]   { padding-top: 0 !important; }

/* ── Top nav bar ── */
.top-nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 0 20px 0;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    margin-bottom: 24px;
}
.brand-lockup { display: flex; align-items: baseline; gap: 12px; }
.brand-name {
    font-family: 'DM Serif Display', serif !important;
    font-size: 2rem;
    background: linear-gradient(135deg, #e2b04a 0%, #f5d07a 60%, #c8922a 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0;
    line-height: 1;
    letter-spacing: -0.5px;
}
.brand-badge {
    font-size: 9px;
    font-weight: 700;
    color: #1a1a2e;
    background: #e2b04a;
    padding: 2px 7px;
    border-radius: 10px;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    font-family: 'DM Sans', sans-serif;
    align-self: center;
}
.brand-tagline {
    font-size: 0.82rem;
    color: #4a5a78;
    margin: 0;
    font-weight: 400;
    letter-spacing: 0.1px;
}
.nav-right {
    display: flex;
    gap: 6px;
    align-items: center;
}
.nav-pill {
    font-size: 10px;
    font-weight: 600;
    color: #4a5a78;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    padding: 4px 10px;
    border-radius: 20px;
    letter-spacing: 0.3px;
    font-family: 'DM Sans', sans-serif;
}

/* ── Controls card ── */
.controls-card {
    background: rgba(22, 33, 62, 0.8);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 10px;
    padding: 16px 20px 14px;
    margin-bottom: 16px;
    backdrop-filter: blur(4px);
    box-shadow: 0 4px 24px rgba(0,0,0,0.25);
}
.controls-label {
    font-size: 9px;
    font-weight: 700;
    color: #2e3e5c;
    letter-spacing: 1.3px;
    text-transform: uppercase;
    margin-bottom: 12px;
    font-family: 'DM Sans', sans-serif;
}

/* ── Country pair badge ── */
.pair-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(226,176,74,0.07);
    border: 1px solid rgba(226,176,74,0.15);
    border-radius: 20px;
    padding: 4px 12px 4px 8px;
    font-size: 11px;
    color: #a89060;
    font-family: 'DM Sans', sans-serif;
    font-weight: 500;
    letter-spacing: 0.2px;
}
.pair-arrow { color: #e2b04a; font-size: 10px; opacity: 0.8; }

/* ── Arrow separator in controls row ── */
.arrow-sep {
    font-size: 1.1rem;
    color: #e2b04a;
    text-align: center;
    padding-top: 28px;
    opacity: 0.5;
    user-select: none;
}

/* ── Severity legend ── */
.legend-bar {
    display: flex;
    gap: 16px;
    align-items: center;
    padding: 7px 14px;
    background: rgba(255,255,255,0.02);
    border-radius: 6px;
    border: 1px solid rgba(255,255,255,0.04);
    margin: 0 0 20px 0;
}
.legend-item {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 11px;
    color: #4a5a78;
    font-family: 'DM Sans', sans-serif;
    font-weight: 500;
}
.legend-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
}

/* ── Panel label ── */
.panel-label {
    font-size: 9px;
    font-weight: 700;
    color: #2e3e5c;
    letter-spacing: 1.3px;
    text-transform: uppercase;
    margin-bottom: 10px;
    font-family: 'DM Sans', sans-serif;
}

/* ── Annotated text display panel ── */
.text-panel {
    background: #111827;
    border-radius: 8px;
    padding: 20px 24px;
    border: 1px solid rgba(255,255,255,0.06);
    min-height: 420px;
    font-size: 14px;
    line-height: 1.85;
    color: #b8c8e0;
    word-wrap: break-word;
    font-family: 'DM Sans', sans-serif;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
}

/* ── Analyze button (gold, prominent) ── */
div[data-testid="stButton"] > button {
    background: linear-gradient(135deg, #e2b04a 0%, #d4a040 100%) !important;
    color: #1a1a2e !important;
    font-weight: 700 !important;
    font-family: 'DM Sans', sans-serif !important;
    border: none !important;
    border-radius: 7px !important;
    transition: all 0.2s ease !important;
    font-size: 13px !important;
    letter-spacing: 0.4px !important;
    box-shadow: 0 2px 8px rgba(226,176,74,0.2) !important;
    cursor: pointer !important;
}
div[data-testid="stButton"] > button:hover {
    background: linear-gradient(135deg, #f0c060 0%, #e2b04a 100%) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 18px rgba(226,176,74,0.4) !important;
}
div[data-testid="stButton"] > button:active {
    transform: translateY(0) !important;
    box-shadow: 0 2px 6px rgba(226,176,74,0.25) !important;
}

/* ── Edit Message button ── */
div[data-testid="stButton"]:has(button[kind="secondary"]) > button {
    background: transparent !important;
    color: #4a5a78 !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    font-size: 11px !important;
    font-weight: 500 !important;
    box-shadow: none !important;
}
div[data-testid="stButton"]:has(button[kind="secondary"]) > button:hover {
    color: #8a9ab8 !important;
    border-color: rgba(255,255,255,0.15) !important;
    transform: none !important;
    box-shadow: none !important;
}

/* ── Text area ── */
.stTextArea textarea {
    background-color: #111827 !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 8px !important;
    color: #b8c8e0 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 14px !important;
    line-height: 1.8 !important;
    caret-color: #e2b04a;
    transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}
.stTextArea textarea:focus {
    border-color: rgba(226,176,74,0.35) !important;
    box-shadow: 0 0 0 3px rgba(226,176,74,0.06) !important;
}
.stTextArea textarea::placeholder { color: #2e3e5c !important; }

/* ── Selectboxes ── */
.stSelectbox [data-baseweb="select"] > div {
    background-color: #111827 !important;
    border-color: rgba(255,255,255,0.07) !important;
    border-radius: 7px !important;
    transition: border-color 0.2s ease !important;
}
.stSelectbox [data-baseweb="select"] > div:focus-within {
    border-color: rgba(226,176,74,0.35) !important;
    box-shadow: 0 0 0 3px rgba(226,176,74,0.06) !important;
}
.stSelectbox label {
    color: #4a5a78 !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    letter-spacing: 0.5px !important;
    text-transform: uppercase !important;
}

/* ── Risk score chips row ── */
.risk-chips {
    display: flex;
    gap: 8px;
    margin-bottom: 14px;
    flex-wrap: wrap;
}
.risk-chip {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 4px 10px;
    border-radius: 5px;
    font-size: 11px;
    font-weight: 700;
    font-family: 'DM Sans', sans-serif;
    letter-spacing: 0.3px;
}

/* ── Divider ── */
hr { border-color: rgba(255,255,255,0.05) !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar       { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #2e3e5c; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #3a4e70; }

/* ── Warning / error ── */
[data-testid="stAlert"] {
    border-radius: 8px !important;
    font-size: 13px !important;
    font-family: 'DM Sans', sans-serif !important;
}
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

    # ── Top nav bar ───────────────────────────────────────────────────────────
    st.markdown(
        """
<div class="top-nav">
  <div class="brand-lockup">
    <h1 class="brand-name">LingoLink</h1>
    <span class="brand-badge">AI</span>
    <p class="brand-tagline">Cross-cultural communication review for international business.</p>
  </div>
  <div class="nav-right">
    <span class="nav-pill">26 Markets</span>
    <span class="nav-pill">6 Risk Types</span>
    <span class="nav-pill">Claude claude-sonnet-4-20250514</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    # ── Controls card ─────────────────────────────────────────────────────────
    st.markdown('<div class="controls-card">', unsafe_allow_html=True)
    st.markdown('<p class="controls-label">Configure Analysis</p>', unsafe_allow_html=True)

    c1, c_arr, c2, c3, c4 = st.columns([3, 0.4, 3, 3, 2])

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

    # Same-country validation
    same_country = sender == receiver
    if not same_country:
        st.markdown(
            f'<div style="margin-top:10px;">'
            f'<span class="pair-badge">'
            f'{sender} <span class="pair-arrow">→</span> {receiver}'
            f'  ·  {scenario}'
            f'</span></div>',
            unsafe_allow_html=True,
        )
    else:
        st.warning("⚠️  Sender and receiver countries must be different.")

    st.markdown('</div>', unsafe_allow_html=True)  # close controls-card

    # ── Severity legend ───────────────────────────────────────────────────────
    st.markdown(
        """
<div class="legend-bar">
  <span style="font-size:9px;font-weight:700;color:#2e3e5c;letter-spacing:1px;
        text-transform:uppercase;font-family:'DM Sans',sans-serif;">Severity</span>
  <span class="legend-item"><span class="legend-dot" style="background:#e2b04a;"></span>HIGH</span>
  <span class="legend-item"><span class="legend-dot" style="background:#c47c2b;"></span>MEDIUM</span>
  <span class="legend-item"><span class="legend-dot" style="background:#4a90b8;"></span>LOW</span>
  <span style="margin-left:auto;font-size:10px;color:#2e3e5c;font-family:'DM Sans',sans-serif;">
    Highlights appear inline in your draft text
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
            flags = st.session_state.result.get("flags", [])
            annotated_html = highlight_text(st.session_state.analyzed_text, flags)
            st.markdown(
                f'<div class="text-panel">{annotated_html}</div>',
                unsafe_allow_html=True,
            )
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("✏️  Edit Message", key="edit_btn"):
                st.session_state.result = None
                st.rerun()
        else:
            st.text_area(
                label="draft",
                height=440,
                placeholder="Paste your draft email, proposal, or business communication here…",
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

            # Risk score chips
            if flags:
                counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
                for f in flags:
                    sev = f.get("severity", "LOW")
                    if sev in counts:
                        counts[sev] += 1
                chip_styles = {
                    "HIGH":   "background:rgba(226,176,74,0.12);color:#e2b04a;border:1px solid rgba(226,176,74,0.2);",
                    "MEDIUM": "background:rgba(196,124,43,0.12);color:#c47c2b;border:1px solid rgba(196,124,43,0.2);",
                    "LOW":    "background:rgba(74,144,184,0.12);color:#4a90b8;border:1px solid rgba(74,144,184,0.2);",
                }
                chips_html = '<div class="risk-chips">'
                for sev, cnt in counts.items():
                    if cnt:
                        chips_html += (
                            f'<span class="risk-chip" style="{chip_styles[sev]}">'
                            f'{cnt} {sev}</span>'
                        )
                chips_html += "</div>"
                st.markdown(chips_html, unsafe_allow_html=True)

            # Overall summary card
            st.markdown(
                f"""
<div style="background:rgba(226,176,74,0.06);border:1px solid rgba(226,176,74,0.12);
     border-left:3px solid #e2b04a;border-radius:8px;padding:14px 16px;margin-bottom:16px;">
  <div style="font-size:9px;font-weight:700;color:#8a6a20;letter-spacing:1px;
       text-transform:uppercase;margin-bottom:7px;font-family:'DM Sans',sans-serif;">
       Overall Assessment</div>
  <p style="color:#b0a080;font-size:13px;line-height:1.7;margin:0;
     font-family:'DM Sans',sans-serif;">{summary}</p>
</div>
""",
                unsafe_allow_html=True,
            )

            if flags:
                count = len(flags)
                st.markdown(
                    f'<p style="font-size:10px;color:#2e3e5c;margin:0 0 12px;'
                    f'letter-spacing:0.3px;font-family:\'DM Sans\',sans-serif;">'
                    f'{count} issue{"s" if count != 1 else ""} identified — review each before sending</p>',
                    unsafe_allow_html=True,
                )
                for i, flag in enumerate(flags):
                    st.markdown(render_flag_card(flag, i), unsafe_allow_html=True)
            else:
                st.markdown(
                    """
<div style="background:rgba(74,160,100,0.06);border-left:3px solid #4aa064;
     border-radius:8px;padding:14px 16px;border:1px solid rgba(74,160,100,0.1);">
  <p style="color:#5a9a74;font-size:13px;margin:0;line-height:1.65;
     font-family:'DM Sans',sans-serif;">
    ✓ No cross-cultural risk flags identified for this pairing and scenario.
  </p>
</div>""",
                    unsafe_allow_html=True,
                )
        else:
            # Empty state
            st.markdown(
                """
<div style="text-align:center;padding:56px 20px 40px;">
  <div style="width:48px;height:48px;border-radius:50%;background:rgba(226,176,74,0.06);
       border:1px solid rgba(226,176,74,0.1);display:inline-flex;align-items:center;
       justify-content:center;font-size:1.5rem;margin-bottom:18px;opacity:0.6;">🌐</div>
  <p style="font-size:13px;color:#2e3e5c;line-height:1.9;margin:0 0 20px;
     font-family:'DM Sans',sans-serif;">
    Select sender &amp; receiver countries,<br>
    choose a scenario, paste your draft,<br>
    then click <strong style="color:#4a5a78;font-weight:600;">Analyze Message</strong>.
  </p>
  <div style="display:inline-flex;flex-direction:column;gap:6px;text-align:left;">
    <div style="font-size:11px;color:#2a3a58;font-family:'DM Sans',sans-serif;
         display:flex;align-items:center;gap:7px;">
      <span style="color:#e2b04a;opacity:0.4;">◈</span> Face &amp; status risk detection
    </div>
    <div style="font-size:11px;color:#2a3a58;font-family:'DM Sans',sans-serif;
         display:flex;align-items:center;gap:7px;">
      <span style="color:#e2b04a;opacity:0.4;">⇄</span> Directness calibration
    </div>
    <div style="font-size:11px;color:#2a3a58;font-family:'DM Sans',sans-serif;
         display:flex;align-items:center;gap:7px;">
      <span style="color:#e2b04a;opacity:0.4;">△</span> Hierarchy &amp; formality checks
    </div>
    <div style="font-size:11px;color:#2a3a58;font-family:'DM Sans',sans-serif;
         display:flex;align-items:center;gap:7px;">
      <span style="color:#e2b04a;opacity:0.4;">◷</span> Urgency pressure flags
    </div>
  </div>
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
