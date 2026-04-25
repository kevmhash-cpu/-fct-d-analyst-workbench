"""
FCT-D Analyst Workbench — Streamlit App
Fractal Credibility Transfer | Document Triage Application
Author concept: Kevin M. Hollenbeck | April 2026
Engine: core_engine_v2.py (doctrine-aligned)
"""

import re
from collections import Counter
from typing import Tuple, Dict
import pandas as pd
import streamlit as st

from core_engine_v2 import (
    analyze_document,
    classify_statement,
    assign_scales,
    split_statements,
    TOPOLOGY_GUIDANCE,
    COUNTERMEASURES,
    TRIAGE_MATRIX,
)

try:
    from docx import Document as DocxDocument
except Exception:
    DocxDocument = None

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

st.set_page_config(page_title="FCT-D Analyst Workbench", page_icon="🧠", layout="wide")

# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------

NODE_DEFINITIONS = {
    "A": {"label": "Anchor",    "meaning": "It is",       "field_test": "Can I prove this right now from a primary source outside this artifact?"},
    "E": {"label": "Event",     "meaning": "It happened", "field_test": "Is this describing what occurred, not interpreting it?"},
    "C": {"label": "Claim",     "meaning": "It means",    "field_test": "Is this explaining meaning instead of stating fact?"},
    "I": {"label": "Inference", "meaning": "It must be",  "field_test": "Can this be independently verified, or does it depend on earlier steps?"},
}

ANCHOR_TYPE_GUIDANCE = {
    "Emotional":     "Trauma, scandal, grief, moral urgency, outrage, atrocity, fear, victims.",
    "Institutional": "Agencies, officials, courts, universities, documents, reports, named organizations.",
    "Technical":     "Scientific language, datasets, models, patents, technical jargon, statistics, charts.",
    "Unknown":       "No dominant anchor type detected.",
}

RISK_BANDS = [
    (0.00, 0.29, "Low",      "Evidence appears to scale with structure."),
    (0.30, 0.49, "Moderate", "Partial structural substitution for sourcing."),
    (0.50, 0.69, "High",     "Structure substantially exceeds evidence."),
    (0.70, 1.00, "Critical", "Structural coherence appears to drive all credibility."),
]

# ---------------------------------------------------------------------------
# FILE LOADING
# ---------------------------------------------------------------------------

def extract_text_from_docx(f) -> str:
    if DocxDocument is None:
        return ""
    doc = DocxDocument(f)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

def extract_text_from_pdf(f) -> str:
    if PdfReader is None:
        return ""
    reader = PdfReader(f)
    chunks = []
    for page in reader.pages:
        try:
            chunks.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n".join(chunks)

def load_uploaded_text(f) -> str:
    if f is None:
        return ""
    name = f.name.lower()
    if name.endswith(".txt"):
        return f.read().decode("utf-8", errors="ignore")
    if name.endswith(".docx"):
        return extract_text_from_docx(f)
    if name.endswith(".pdf"):
        return extract_text_from_pdf(f)
    return ""

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def get_risk_level(score: float) -> Tuple[str, str]:
    for low, high, label, explanation in RISK_BANDS:
        if low <= score <= high:
            return label, explanation
    return "Critical", "Structural coherence appears to drive all credibility."

def render_condition(name: str, result: Tuple[bool, str], is_mandatory: bool = True):
    passed, explanation = result
    icon = "✅" if passed else "❌"
    tag  = "[MANDATORY]" if is_mandatory else "[Confirmatory]"
    st.markdown(f"**{icon} {name}** *{tag}*")
    st.caption(explanation)

# ---------------------------------------------------------------------------
# REFERENCE TAB
# ---------------------------------------------------------------------------

def render_reference_tab():
    st.subheader("FCT-D Field Reference")
    st.info("FCT-D assesses structural credibility dynamics. It does not determine truth, intent, guilt, or deception.")

    st.markdown("### Credibility Ladder")
    ladder_df = pd.DataFrame([
        {"Code": code, "Node": v["label"], "Meaning": v["meaning"], "Field Test": v["field_test"]}
        for code, v in NODE_DEFINITIONS.items()
    ])
    st.dataframe(ladder_df, use_container_width=True, hide_index=True)
    st.caption("**Primary Failure Point:** Transition from Event → Claim. This is where credibility first transfers structurally rather than evidentially.")

    st.markdown("### Mandatory Conditions (all three required)")
    st.markdown("1. **Anchor Presence** — a verifiable, semi-verifiable, or emotionally salient entry point exists.")
    st.markdown("2. **Structural Transfer** — credibility spreads through design rather than explicit evidence.")
    st.markdown("3. **Fractal Recursion** *(load-bearing)* — the same transfer pattern repeats at micro, meso, and macro scales simultaneously.")

    st.markdown("### Scale Definitions")
    st.markdown("- **Micro:** Sentence or claim level")
    st.markdown("- **Meso:** Paragraph or section level")
    st.markdown("- **Macro:** Full narrative structure")

    st.markdown("### Topology Countermeasures")
    topo_df = pd.DataFrame([
        {"Topology": k, "Structure": TOPOLOGY_GUIDANCE[k], "Countermeasure": COUNTERMEASURES[k]}
        for k in TOPOLOGY_GUIDANCE
    ])
    st.dataframe(topo_df, use_container_width=True, hide_index=True)

    st.markdown("### Combined Triage Matrix (Anchor Type × Topology)")
    matrix_data = [
        {"Anchor Type": at, "Topology": topo, "Countermeasure": cm}
        for (at, topo), cm in TRIAGE_MATRIX.items()
    ]
    st.dataframe(pd.DataFrame(matrix_data), use_container_width=True, hide_index=True)

    st.markdown("### Adjacent Concepts — How FCT-D Differs")
    adjacent = pd.DataFrame([
        {"Concept": "Credibility Laundering", "How It Works": "Proximity to trusted source transfers legitimacy.",  "FCT-D Difference": "FCT-D is structure-based and recursively reinforced. Laundering lacks multi-scale repetition."},
        {"Concept": "Narrative Cascade",       "How It Works": "Sequential belief expansion over time.",             "FCT-D Difference": "Cascade is temporal. FCT-D is structural and simultaneous — within a single artifact."},
        {"Concept": "Cognitive Overload",      "How It Works": "Volume reduces analytic scrutiny.",                  "FCT-D Difference": "Overload is an outcome. FCT-D is the mechanism that engineers it."},
        {"Concept": "Apophenia",               "How It Works": "Observer perceives patterns in random data.",        "FCT-D Difference": "Apophenia is observer-side. FCT-D is artifact-side engineered structure."},
    ])
    st.dataframe(adjacent, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# STREAMLIT APP
# ---------------------------------------------------------------------------

st.title("FCT-D Analyst Workbench")
st.caption("Fractal Credibility Transfer | Document Variant | Structural Credibility Triage")
st.warning(
    "This prototype is a structural diagnostic tool. It does not determine whether "
    "claims are true or false, and does not assess intent or deception. "
    "High-stakes use requires corroboration."
)

mode = st.sidebar.radio("Analyst Mode", ["Experienced Analyst", "Junior / Trainee Analyst"])
st.sidebar.markdown("---")
st.sidebar.markdown("### Accepted Inputs")
st.sidebar.markdown("Paste text or upload `.txt`, `.docx`, or `.pdf`.")
st.sidebar.markdown("---")
st.sidebar.caption("Engine: core_engine_v2 | FCT-D Doctrine (Hollenbeck, April 2026)")

main_tab, node_tab, scoring_tab, reference_tab = st.tabs([
    "Document Triage", "Node Classifier", "Scoring Layer", "Field Reference"
])

# ── Document Triage ──────────────────────────────────────────────────────────
with main_tab:
    left, right = st.columns([1.15, 0.85])

    with left:
        st.subheader("Input Document")
        uploaded      = st.file_uploader("Upload document", type=["txt", "docx", "pdf"])
        uploaded_text = load_uploaded_text(uploaded) if uploaded else ""
        text_input    = st.text_area(
            "Paste text for FCT-D evaluation",
            value=uploaded_text,
            height=360,
            placeholder="Paste article, assessment, social thread, policy memo, or OSINT artifact here...",
        )
        run = st.button("Run FCT-D Analysis", type="primary", use_container_width=True)

    with right:
        st.subheader("Doctrine Reminder")
        st.markdown("**FCT-D asks:** Is perceived credibility earned through evidence, or constructed through structure?")
        st.markdown("**Mandatory Conditions (all three required):**")
        st.markdown("- Anchor Presence\n- Structural Transfer\n- Fractal Recursion *(load-bearing)*")
        st.markdown("**Primary Failure Point:** Event → Claim transition.")
        if mode == "Junior / Trainee Analyst":
            st.info("Trainee cue: Coherence is not evidence. Confidence is not proof.")

    if run:
        if not text_input.strip():
            st.error("Please paste or upload text before running analysis.")
        else:
            st.session_state["last_result"] = analyze_document(text_input)
            st.session_state["last_text"]   = text_input

    if "last_result" in st.session_state:
        result  = st.session_state["last_result"]
        metrics = result["metrics"]
        risk_level, risk_explanation = get_risk_level(metrics["FCT Risk Score"])

        st.markdown("---")
        st.subheader("FCT-D Assessment Output")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("FCT Risk Score",   metrics["FCT Risk Score"])
        m2.metric("Risk Level",       risk_level)
        m3.metric("FCT-D Confirmed",  "✅ YES" if result["fct_confirmed"] else "❌ NO")
        m4.metric("Sources detected", metrics["Source Count"])
        st.caption(risk_explanation)

        a1, a2 = st.columns(2)
        with a1:
            st.markdown(f"**Anchor Type:** {result['anchor_type']}")
            st.caption(ANCHOR_TYPE_GUIDANCE.get(result["anchor_type"], ""))
        with a2:
            st.markdown(f"**Topology:** {result['topology']}")
            st.caption(result["topology_note"])

        st.markdown("---")
        c1, c2 = st.columns(2)

        with c1:
            st.markdown("### Criteria Assessment")
            mandatory    = ["Anchor Presence", "Structural Transfer", "Fractal Recursion"]
            confirmatory = ["Density-to-Sourcing Imbalance", "Self-Referential Closure"]
            for name in mandatory:
                render_condition(name, result["conditions"][name], is_mandatory=True)
            for name in confirmatory:
                render_condition(name, result["conditions"][name], is_mandatory=False)

        with c2:
            st.markdown("### Classification")
            st.markdown(f"**Anchor Type:** {result['anchor_type']}")
            st.caption(ANCHOR_TYPE_GUIDANCE.get(result["anchor_type"], ""))
            st.markdown(f"**Topology:** {result['topology']}")
            st.caption(TOPOLOGY_GUIDANCE[result["topology"]])

            st.markdown("### Topology Countermeasure")
            st.info(COUNTERMEASURES[result["topology"]])

            combined_key = (result["anchor_type"], result["topology"])
            combined_cm  = TRIAGE_MATRIX.get(combined_key, COUNTERMEASURES[result["topology"]])
            st.markdown("### Combined Countermeasure (Anchor Type × Topology)")
            st.success(f"**{result['anchor_type']} + {result['topology']}:** {combined_cm}")

        st.markdown("### Analyst Note")
        if result["fct_confirmed"]:
            st.warning(result["guidance"])
        else:
            st.error(
                f"Full FCT-D classification is not supported — one or more mandatory conditions are unmet. "
                f"Anchor: {'✓' if result['conditions']['Anchor Presence'][0] else '✗'} | "
                f"Transfer: {'✓' if result['conditions']['Structural Transfer'][0] else '✗'} | "
                f"Recursion: {'✓' if result['conditions']['Fractal Recursion'][0] else '✗'}"
            )

        if mode == "Junior / Trainee Analyst":
            st.info("A high score does not mean the document is false. It means structure may be doing more credibility work than the evidence supports.")

        # Node classification table
        st.markdown("### Node Classification")
        scale_units = result.get("scale_units", [])
        rows = []
        for scale, text in scale_units:
            node = classify_statement(text)
            rows.append({
                "Scale":     scale,
                "Code":      node,
                "Type":      NODE_DEFINITIONS[node]["label"],
                "Statement": text[:120] + ("…" if len(text) > 120 else ""),
            })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # Node distribution by scale
        st.markdown("### Node Distribution by Scale")
        by_scale = {"Micro": Counter(), "Meso": Counter(), "Macro": Counter()}
        for row in rows:
            by_scale[row["Scale"]][row["Code"]] += 1
        dist_rows = []
        for scale in ["Micro", "Meso", "Macro"]:
            c = by_scale[scale]
            dist_rows.append({
                "Scale":          scale,
                "Anchors (A)":    c.get("A", 0),
                "Events (E)":     c.get("E", 0),
                "Claims (C)":     c.get("C", 0),
                "Inferences (I)": c.get("I", 0),
            })
        st.dataframe(pd.DataFrame(dist_rows), use_container_width=True, hide_index=True)

        # Metric breakdown
        with st.expander("⚡ Metric Breakdown"):
            b1, b2, b3, b4 = st.columns(4)
            b1.metric("UER (×0.40)",         metrics["UER"])
            b2.metric("Drop-off (×0.25)",     metrics["Drop-off"])
            b3.metric("Connectivity (×0.20)", metrics["Connectivity"])
            b4.metric("Centrality (×0.15)",   metrics["Centrality"])
            st.caption(
                f"Sources detected: {metrics['Source Count']} | "
                f"Formula: Score = (0.40 × UER) + (0.25 × Drop-off) + "
                f"(0.20 × Connectivity) + (0.15 × Centrality)"
            )

# ── Node Classifier ───────────────────────────────────────────────────────────
with node_tab:
    st.subheader("Single Statement Node Classifier")
    if mode == "Junior / Trainee Analyst":
        st.info("Enter one sentence. Returns its node type per the FCT-D Credibility Ladder.")
    statement = st.text_area("Enter one statement", height=140)
    if st.button("Classify Statement", use_container_width=True):
        if not statement.strip():
            st.error("Enter a statement first.")
        else:
            node = classify_statement(statement)
            defn = NODE_DEFINITIONS[node]
            st.metric("Node Type", f"{node} — {defn['label']}")
            st.metric("Meaning",   defn["meaning"])
            if mode == "Junior / Trainee Analyst":
                st.info(f"**Field Test:** {defn['field_test']}")

# ── Manual Scoring Layer ──────────────────────────────────────────────────────
with scoring_tab:
    st.subheader("Manual FCT Risk Score Calculator")
    st.caption("Score = (0.40 × UER) + (0.25 × Drop-off) + (0.20 × Connectivity) + (0.15 × Centrality)")
    uer  = st.slider("Unsupported Edge Ratio (UER)", 0.0, 1.0, 0.40, 0.01)
    drop = st.slider("Evidence Drop-off",             0.0, 1.0, 0.35, 0.01)
    conn = st.slider("Connectivity",                  0.0, 1.0, 0.40, 0.01)
    cent = st.slider("Centrality",                    0.0, 1.0, 0.35, 0.01)
    manual_score = round((0.40 * uer) + (0.25 * drop) + (0.20 * conn) + (0.15 * cent), 2)
    level, expl  = get_risk_level(manual_score)
    st.metric("Manual FCT Risk Score", manual_score)
    st.metric("Risk Level", level)
    st.caption(expl)

# ── Field Reference ───────────────────────────────────────────────────────────
with reference_tab:
    render_reference_tab()
