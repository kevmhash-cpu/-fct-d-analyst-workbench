"""
FCT-D Analyst Workbench — Streamlit Prototype
Fractal Credibility Transfer | Document Triage Application
Author concept: Kevin M. Hollenbeck | April 2026

This prototype allows an analyst to paste or upload a document and run a structured FCT-D triage.
It is NOT a truth engine. It assesses structure-driven credibility risk, not factual accuracy, intent, or deception.
"""

import re
from collections import Counter
from dataclasses import dataclass
from typing import List, Dict, Tuple

import pandas as pd
import streamlit as st
from core_engine_v2 import analyze_document as analyze_document_v2
try:
from docx import Document
except Exception:
    Document = None

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

st.set_page_config(page_title="FCT-D Analyst Workbench", page_icon="🧠", layout="wide")

NODE_DEFINITIONS = {
    "A": {"label": "Anchor", "meaning": "It is", "definition": "Verified, defensible, or highly salient entry point. Independently sourceable or emotionally/institutionally compelling.", "field_test": "Can I prove this from a primary source outside this artifact, or is it being used as the credibility base?"},
    "E": {"label": "Event", "meaning": "It happened", "definition": "Observable occurrence or real-world condition. Reports what happened, not what it means.", "field_test": "Is this describing what occurred rather than interpreting it?"},
    "C": {"label": "Claim", "meaning": "It means", "definition": "Interpretation of events. Assigns meaning, motive, consequence, or significance.", "field_test": "Is this explaining meaning rather than stating fact?"},
    "I": {"label": "Inference", "meaning": "It must be", "definition": "Conclusion built on stacked claims. Extends beyond what evidence directly proves.", "field_test": "Does this depend on prior claims rather than direct independent verification?"},
}

RISK_BANDS = [
    (0.00, 0.29, "Low", "Evidence appears to scale with structure."),
    (0.30, 0.49, "Moderate", "Partial structural substitution for sourcing."),
    (0.50, 0.69, "High", "Structure substantially exceeds evidence."),
    (0.70, 1.00, "Critical", "Structural coherence appears to drive credibility."),
]

ANCHOR_TYPE_GUIDANCE = {
    "Emotional": "Trauma, scandal, grief, moral urgency, outrage, atrocity, fear, children, victims.",
    "Institutional": "Agencies, officials, courts, universities, documents, reports, named organizations.",
    "Technical": "Scientific language, datasets, models, patents, technical jargon, statistics, charts.",
}

TOPOLOGY_GUIDANCE = {
    "Hub-Spoke": "Single dominant anchor with multiple peripheral claims radiating outward.",
    "Hierarchical": "Anchor develops into mid-level sub-anchors, which then support additional claims.",
    "Lattice": "Multiple anchors cross-reference and mutually reinforce; no single root node dominates.",
}

COUNTERMEASURES = {
    "Hub-Spoke": "Validate or refute the hub anchor first. Peripheral claims may collapse as a secondary effect.",
    "Hierarchical": "Map the full claim tree. Refute at the highest viable tier, then work downward.",
    "Lattice": "Require independent verification for each anchor. Internal cross-references do not qualify as corroboration.",
}

@dataclass
class StatementAssessment:
    statement: str
    node_code: str
    node_type: str
    confidence: float
    rationale: str
    signal: str

def extract_text_from_docx(uploaded_file) -> str:
    if Document is None:
        return ""
    doc = Document(uploaded_file)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

def extract_text_from_pdf(uploaded_file) -> str:
    if PdfReader is None:
        return ""
    reader = PdfReader(uploaded_file)
    chunks = []
    for page in reader.pages:
        try:
            chunks.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n".join(chunks)

def load_uploaded_text(uploaded_file) -> str:
    if uploaded_file is None:
        return ""
    name = uploaded_file.name.lower()
    if name.endswith(".txt"):
        return uploaded_file.read().decode("utf-8", errors="ignore")
    if name.endswith(".docx"):
        return extract_text_from_docx(uploaded_file)
    if name.endswith(".pdf"):
        return extract_text_from_pdf(uploaded_file)
    return ""

def split_into_statements(text: str) -> List[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    return [p.strip() for p in parts if len(p.strip()) > 25][:80]

def count_sources(text: str) -> int:
    patterns = [r"https?://", r"www\.", r"doi\.org", r"\[[0-9]+\]", r"\([A-Z][A-Za-z]+,\s?\d{4}\)", r"according to", r"reported by", r"published by", r"data from", r"source:"]
    return sum(len(re.findall(p, text, flags=re.I)) for p in patterns)

def classify_statement(statement: str) -> StatementAssessment:
    s = statement.lower()
    anchor_terms = ["report", "document", "agency", "court", "official", "university", "study", "data", "according to", "published", "confirmed", "stated", "announced", "department", "ministry", "fbi", "cia", "dhs", "odni", "who", "un", "treasury", "doj", "gao", "congress", "hearing", "filing"]
    event_terms = ["occurred", "happened", "arrested", "charged", "launched", "met", "signed", "released", "killed", "attacked", "reported", "filed", "voted", "approved", "denied", "created", "began", "ended"]
    claim_terms = ["suggests", "indicates", "shows", "means", "reveals", "demonstrates", "points to", "signals", "reflects", "evidence of", "likely", "appears", "implies", "because", "therefore"]
    inference_terms = ["must", "therefore", "proves", "undeniable", "clearly", "no doubt", "only explanation", "cannot be coincidence", "shows that", "will lead to", "is part of", "coordinated plot", "orchestrated"]
    scores = {"A": sum(term in s for term in anchor_terms), "E": sum(term in s for term in event_terms), "C": sum(term in s for term in claim_terms), "I": sum(term in s for term in inference_terms)}
    if re.search(r"\b\d{4}\b|\b\d+%\b|\b\$\d+", statement): scores["A"] += 0.5
    if any(x in s for x in ["why", "meaning", "motive", "intent", "agenda"]): scores["C"] += 1
    if any(x in s for x in ["inevitably", "must be", "cannot be", "there is no other"]): scores["I"] += 1.5
    node_code = max(scores, key=scores.get)
    max_score = scores[node_code]
    if max_score == 0:
        node_code = "E"; confidence = 0.45; signal = "Defaulted to Event: descriptive sentence without strong interpretive markers."; rationale = "Statement appears mainly descriptive, but confidence is limited because no strong FCT markers were detected."
    else:
        total = sum(scores.values()) or 1
        confidence = min(0.95, 0.50 + (max_score / total) * 0.45)
        signal = f"Detected {NODE_DEFINITIONS[node_code]['label']} indicators."
        rationale = NODE_DEFINITIONS[node_code]["definition"]
    return StatementAssessment(statement, node_code, NODE_DEFINITIONS[node_code]["label"], round(confidence, 2), rationale, signal)

def detect_anchor_type(text: str) -> Tuple[str, str]:
    s = text.lower()
    emotional = ["victim", "children", "trauma", "grief", "scandal", "atrocity", "fear", "outrage", "abuse", "death", "crisis"]
    institutional = ["agency", "official", "government", "court", "department", "ministry", "university", "report", "hearing", "filing", "doj", "fbi", "cia", "dhs", "odni", "treasury"]
    technical = ["data", "model", "algorithm", "patent", "study", "dataset", "scientific", "technical", "statistical", "quantum", "ai", "machine learning", "peer-reviewed"]
    counts = {"Emotional": sum(w in s for w in emotional), "Institutional": sum(w in s for w in institutional), "Technical": sum(w in s for w in technical)}
    anchor_type = max(counts, key=counts.get)
    if counts[anchor_type] == 0:
        return "Institutional", "Default: no dominant anchor type detected; institutional selected as neutral baseline."
    return anchor_type, ANCHOR_TYPE_GUIDANCE[anchor_type]

def estimate_topology(assessments: List[StatementAssessment]) -> Tuple[str, str]:
    counts = Counter(a.node_code for a in assessments)
    anchors, claims, inferences = counts.get("A", 0), counts.get("C", 0), counts.get("I", 0)
    if anchors <= 1 and claims + inferences >= 3: return "Hub-Spoke", TOPOLOGY_GUIDANCE["Hub-Spoke"]
    if anchors >= 2 and claims >= 3 and inferences >= 2: return "Lattice", TOPOLOGY_GUIDANCE["Lattice"]
    return "Hierarchical", TOPOLOGY_GUIDANCE["Hierarchical"]

def calculate_fct_metrics(text: str, assessments: List[StatementAssessment]) -> Dict[str, float]:
    total_statements = max(len(assessments), 1)
    counts = Counter(a.node_code for a in assessments)
    source_count = count_sources(text)
    unsupported_edges = max(0, counts.get("C", 0) + counts.get("I", 0) - source_count)
    total_edges = max(1, counts.get("E", 0) + counts.get("C", 0) + counts.get("I", 0))
    uer = min(1.0, unsupported_edges / total_edges)
    anchor_ratio = counts.get("A", 0) / total_statements
    interpretive_ratio = (counts.get("C", 0) + counts.get("I", 0)) / total_statements
    drop_off = min(1.0, max(0.0, interpretive_ratio - anchor_ratio + 0.25))
    connectivity = min(1.0, (counts.get("C", 0) * 0.07) + (counts.get("I", 0) * 0.10))
    anchors = max(counts.get("A", 0), 1)
    centrality = min(1.0, (counts.get("C", 0) + counts.get("I", 0)) / (anchors * 8))
    score = (0.40 * uer) + (0.25 * drop_off) + (0.20 * connectivity) + (0.15 * centrality)
    return {"UER": round(uer, 2), "Drop-off": round(drop_off, 2), "Connectivity": round(connectivity, 2), "Centrality": round(centrality, 2), "FCT Risk Score": round(min(1.0, score), 2), "Source Count": source_count}

def get_risk_level(score: float) -> Tuple[str, str]:
    for low, high, label, explanation in RISK_BANDS:
        if low <= score <= high:
            return label, explanation
    return "Critical", "Structural coherence appears to drive credibility."

def assess_conditions(assessments: List[StatementAssessment], metrics: Dict[str, float]) -> Dict[str, Tuple[bool, str]]:
    counts = Counter(a.node_code for a in assessments)
    has_anchor = counts.get("A", 0) >= 1
    has_transfer = (counts.get("C", 0) + counts.get("I", 0)) >= 2 and metrics["UER"] >= 0.30
    has_recursion = len(assessments) >= 6 and counts.get("A", 0) >= 1 and counts.get("C", 0) >= 2 and counts.get("I", 0) >= 1
    return {
        "Anchor Presence": (has_anchor, "At least one anchor-like statement detected." if has_anchor else "No strong anchor detected."),
        "Structural Transfer": (has_transfer, "Interpretive claims appear to exceed explicit sourcing." if has_transfer else "Insufficient evidence that structure is substituting for sourcing."),
        "Fractal Recursion": (has_recursion, "Anchor-to-claim escalation appears across multiple levels." if has_recursion else "Recursion not sufficiently demonstrated; consider narrative cascade or credibility laundering."),
        "Density-to-Sourcing Imbalance": (metrics["UER"] >= 0.50, "High unsupported edge ratio detected." if metrics["UER"] >= 0.50 else "Density imbalance not strongly confirmed."),
        "Self-Referential Closure": (metrics["Source Count"] <= 1 and metrics["UER"] >= 0.40, "Low external sourcing plus high interpretive load suggests possible internal closure." if metrics["Source Count"] <= 1 and metrics["UER"] >= 0.40 else "No strong self-referential closure detected."),
    }

def analyze_document(text: str) -> Dict:
    statements = split_into_statements(text)
    assessments = [classify_statement(s) for s in statements]
    metrics = calculate_fct_metrics(text, assessments)
    risk_level, risk_explanation = get_risk_level(metrics["FCT Risk Score"])
    anchor_type, anchor_type_note = detect_anchor_type(text)
    topology, topology_note = estimate_topology(assessments)
    conditions = assess_conditions(assessments, metrics)
    mandatory_met = all(conditions[k][0] for k in ["Anchor Presence", "Structural Transfer", "Fractal Recursion"])
    analyst_note = (
        f"FCT-D conditions are present. The artifact shows {anchor_type.lower()} anchor characteristics with a {topology.lower()} structure. Primary concern: perceived coherence may be generated by narrative architecture rather than proportional evidentiary support. Recommended action: {COUNTERMEASURES[topology]}"
        if mandatory_met else
        "Full FCT-D classification is not supported because one or more mandatory conditions are not met. Treat this as a structural concern requiring further analyst review, not confirmed FCT-D."
    )
    return {"statements": assessments, "metrics": metrics, "risk_level": risk_level, "risk_explanation": risk_explanation, "anchor_type": anchor_type, "anchor_type_note": anchor_type_note, "topology": topology, "topology_note": topology_note, "conditions": conditions, "countermeasure": COUNTERMEASURES[topology], "analyst_note": analyst_note}

def render_condition(name: str, result: Tuple[bool, str]):
    passed, explanation = result
    icon = "✅" if passed else "⚠️"
    st.markdown(f"**{icon} {name}**")
    st.caption(explanation)

def render_reference_tab():
    st.subheader("FCT-D Field Reference")
    st.info("FCT-D assesses structural credibility dynamics. It does not determine truth, intent, guilt, or deception.")
    st.markdown("### Credibility Ladder")
    ladder_df = pd.DataFrame([{"Code": code, "Node": v["label"], "Meaning": v["meaning"], "Field Test": v["field_test"]} for code, v in NODE_DEFINITIONS.items()])
    st.dataframe(ladder_df, use_container_width=True, hide_index=True)
    st.markdown("### Mandatory Conditions")
    st.markdown("1. **Anchor Presence** — credible or salient entry point exists.")
    st.markdown("2. **Structural Transfer** — design substitutes for sourcing.")
    st.markdown("3. **Fractal Recursion** — same transfer pattern repeats at micro, meso, and macro levels.")
    st.markdown("### Topology Countermeasures")
    topo_df = pd.DataFrame([{"Topology": k, "Description": TOPOLOGY_GUIDANCE[k], "Countermeasure": COUNTERMEASURES[k]} for k in TOPOLOGY_GUIDANCE])
    st.dataframe(topo_df, use_container_width=True, hide_index=True)

st.title("FCT-D Analyst Workbench")
st.caption("Fractal Credibility Transfer | Document Variant | Structural Credibility Triage")
st.warning("This prototype is a structural diagnostic tool. It does not determine whether claims are true or false, and it does not assess intent or deception. High-stakes use requires corroboration.")

mode = st.sidebar.radio("Analyst Mode", ["Experienced Analyst", "Junior / Trainee Analyst"])
st.sidebar.markdown("---")
st.sidebar.markdown("### Accepted Inputs")
st.sidebar.markdown("Paste text or upload `.txt`, `.docx`, or `.pdf`.")
st.sidebar.markdown("---")
st.sidebar.caption("Rule-based heuristic engine. Designed for demonstration and validation testing.")

main_tab, node_tab, scoring_tab, reference_tab = st.tabs(["Document Triage", "Node Classifier", "Scoring Layer", "Field Reference"])

with main_tab:
    left, right = st.columns([1.15, 0.85])
    with left:
        st.subheader("Input Document")
        uploaded = st.file_uploader("Upload document", type=["txt", "docx", "pdf"])
        uploaded_text = load_uploaded_text(uploaded) if uploaded else ""
        text_input = st.text_area("Paste text for FCT-D evaluation", value=uploaded_text, height=360, placeholder="Paste article, assessment, social thread, policy memo, or OSINT artifact here...")
        run = st.button("Run FCT-D Analysis", type="primary", use_container_width=True)
    with right:
        st.subheader("Doctrine Reminder")
        st.markdown("**FCT-D asks:** Is the document’s perceived credibility earned through evidence, or constructed through structure?")
        st.markdown("**Mandatory Conditions:**")
        st.markdown("- Anchor Presence\n- Structural Transfer\n- Fractal Recursion")
        if mode == "Junior / Trainee Analyst":
            st.info("Trainee cue: The primary failure point is the transition from Event → Claim.")
    if run:
        if not text_input.strip():
            st.error("Please paste or upload text before running analysis.")
        else:
            st.session_state["last_result"] = analyze_document_v2(text_input)
            st.session_state["last_text"] = text_input
    if "last_result" in st.session_state:
        result = st.session_state["last_result"]
        st.markdown("---")
        st.subheader("FCT-D Assessment Output")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("FCT Risk Score", result["metrics"]["FCT Risk Score"])
        m2.metric("Risk Level", result["risk_level"])
        m3.metric("Anchor Type", result["anchor_type"])
        m4.metric("Topology", result["topology"])
        st.caption(result["risk_explanation"])
        c1, c2 = st.columns([1, 1])
        with c1:
            st.markdown("### Criteria Assessment")
            for name, condition in result["conditions"].items(): render_condition(name, condition)
        with c2:
            st.markdown("### Countermeasure")
            st.success(result["countermeasure"])
            st.markdown("### Analyst Note")
            st.write(result["analyst_note"])
            if mode == "Junior / Trainee Analyst":
                st.info("A high score does not mean the document is false. It means the structure may be doing more credibility work than the evidence supports.")
        st.markdown("### Node Classification")
        rows = [{"Code": a.node_code, "Type": a.node_type, "Confidence": a.confidence, "Statement": a.statement, "Signal": a.signal} for a in result["statements"]]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

with node_tab:
    st.subheader("Single Statement Node Classifier")
    statement = st.text_area("Enter one statement", height=140)
    if st.button("Classify Statement", use_container_width=True):
        if not statement.strip(): st.error("Enter a statement first.")
        else:
            a = classify_statement(statement)
            st.metric("Node Type", f"{a.node_code} — {a.node_type}")
            st.metric("Confidence", a.confidence)
            st.write("**Rationale:**", a.rationale)
            st.write("**Signal:**", a.signal)
            if mode == "Junior / Trainee Analyst": st.info(NODE_DEFINITIONS[a.node_code]["field_test"])

with scoring_tab:
    st.subheader("Manual FCT Risk Score Calculator")
    st.caption("Score = (0.40 × UER) + (0.25 × Drop-off) + (0.20 × Connectivity) + (0.15 × Centrality)")
    uer = st.slider("Unsupported Edge Ratio", 0.0, 1.0, 0.40, 0.01)
    drop = st.slider("Evidence Drop-off", 0.0, 1.0, 0.35, 0.01)
    conn = st.slider("Connectivity", 0.0, 1.0, 0.40, 0.01)
    cent = st.slider("Centrality", 0.0, 1.0, 0.35, 0.01)
    manual_score = round((0.40 * uer) + (0.25 * drop) + (0.20 * conn) + (0.15 * cent), 2)
    level, expl = get_risk_level(manual_score)
    st.metric("Manual FCT Risk Score", manual_score)
    st.metric("Risk Level", level)
    st.caption(expl)

with reference_tab:
    render_reference_tab()
