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
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st

try:
    from docx import Document
except Exception:
    Document = None

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None


# -----------------------------
# PAGE CONFIG
# -----------------------------

st.set_page_config(
    page_title="FCT-D Analyst Workbench",
    page_icon="🧠",
    layout="wide"
)


# -----------------------------
# DOCTRINE CONSTANTS
# -----------------------------

MAX_STATEMENTS = 80

NODE_DEFINITIONS = {
    "A": {
        "label": "Anchor",
        "meaning": "It is",
        "definition": "Verified, defensible, or highly salient entry point. Independently sourceable or emotionally/institutionally compelling.",
        "field_test": "Can I prove this right now from a primary source outside this artifact, or is it being used as the credibility base?"
    },
    "E": {
        "label": "Event",
        "meaning": "It happened",
        "definition": "Observable occurrence or real-world condition. Reports what happened, not what it means.",
        "field_test": "Is this describing what occurred rather than interpreting it?"
    },
    "C": {
        "label": "Claim",
        "meaning": "It means",
        "definition": "Interpretation of events. Assigns meaning, motive, consequence, or significance.",
        "field_test": "Is this explaining meaning instead of stating fact?"
    },
    "I": {
        "label": "Inference",
        "meaning": "It must be",
        "definition": "Conclusion built on stacked claims. Extends beyond what evidence directly proves.",
        "field_test": "Can this be independently verified, or does it depend on earlier steps?"
    },
}

RISK_BANDS = [
    (0.00, 0.29, "Low", "Evidence appears to scale with structure."),
    (0.30, 0.49, "Moderate", "Partial structural substitution for sourcing."),
    (0.50, 0.69, "High", "Structure substantially exceeds evidence."),
    (0.70, 1.00, "Critical", "Structural coherence appears to drive credibility."),
]

ANCHOR_TYPE_GUIDANCE = {
    "Emotional": "Trauma, scandal, moral urgency, outrage, fear, children, victims, abuse, death, crisis.",
    "Institutional": "Agencies, officials, courts, universities, documents, reports, named organizations.",
    "Technical": "Scientific language, datasets, models, patents, jargon, statistics, charts, CVEs, MITRE IDs.",
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

COMBINED_TRIAGE_MATRIX = {
    ("Emotional", "Hub-Spoke"): "Fastest to collapse. Verify anchor event; spokes fall automatically.",
    ("Emotional", "Hierarchical"): "Grief or moral urgency escalates into doctrine. Map emotional cascade path before engaging.",
    ("Emotional", "Lattice"): "Most manipulative variant. Multiple trauma anchors mutually reinforce. Per-anchor verification required.",
    ("Institutional", "Hub-Spoke"): "Classic authority-halo pattern. Named agency as hub; check primary documents first.",
    ("Institutional", "Hierarchical"): "Agency > program > claim tree. Refute at institutional tier; subclaims may persist.",
    ("Institutional", "Lattice"): "Agencies cross-cited. Each lends the others halo. Verify each institution independently.",
    ("Technical", "Hub-Spoke"): "Jargon hub radiating unsupported conclusions. SME review of anchor term may be sufficient.",
    ("Technical", "Hierarchical"): "Real paper > misread finding > theory tree. Engage at paper or method level.",
    ("Technical", "Lattice"): "Most durable variant. Multiple technical anchors cross-reinforce. Escalate to SME triage.",
}

ADJACENT_CONCEPTS = [
    {
        "Concept": "Credibility Laundering",
        "How It Works": "Association-based legitimacy transfer via proximity to trusted source.",
        "How FCT-D Differs": "FCT-D is structure-based and recursively reinforced; laundering lacks multi-scale repetition."
    },
    {
        "Concept": "Narrative Cascade",
        "How It Works": "Sequential belief expansion over time.",
        "How FCT-D Differs": "Cascade is temporal. FCT-D is structural and simultaneous within one artifact."
    },
    {
        "Concept": "Cognitive Overload",
        "How It Works": "Volume-driven reduction in analytic scrutiny.",
        "How FCT-D Differs": "Overload is an outcome. FCT-D is the mechanism that engineers the overload."
    },
    {
        "Concept": "Apophenia",
        "How It Works": "Observer-side tendency to perceive patterns in random data.",
        "How FCT-D Differs": "FCT-D is artifact-side engineered structure exploiting that bias."
    },
]


# -----------------------------
# DATA STRUCTURE
# -----------------------------

@dataclass
class StatementAssessment:
    statement: str
    node_code: str
    node_type: str
    confidence: float
    rationale: str
    signal: str
    edge_score_to_next: float = 0.0


# -----------------------------
# FILE HELPERS
# -----------------------------

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


# -----------------------------
# TEXT PROCESSING
# -----------------------------

def split_into_statements(text: str) -> Tuple[List[str], int, bool]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return [], 0, False

    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    statements = [p.strip() for p in parts if len(p.strip()) > 25]
    total = len(statements)
    truncated = total > MAX_STATEMENTS

    return statements[:MAX_STATEMENTS], total, truncated


def split_into_paragraphs(text: str) -> List[str]:
    raw = re.split(r"\n\s*\n", text.strip())
    return [p.strip() for p in raw if len(p.strip()) > 40]


def count_sources(text: str) -> int:
    patterns = [
        r"https?://",
        r"www\.",
        r"doi\.org",
        r"\[[0-9]+\]",
        r"\([A-Z][A-Za-z]+,\s?\d{4}\)",
        r"according to",
        r"reported by",
        r"published by",
        r"data from",
        r"source:",
        r"CVE-\d{4}-\d+",
        r"\bT\d{4}(?:\.\d{3})?\b",
        r"\bAPT\d+\b",
        r"\bFIN\d+\b",
        r"\bUNC\d+\b",
        r"\bSHA256\b",
        r"\bMD5\b",
        r"\bIOC\b",
        r"\bMITRE\b",
        r"\bATT&CK\b",
        r"\bCISA\b",
        r"\bDOJ\b",
        r"\bODNI\b",
        r"\bGAO\b",
    ]
    return sum(len(re.findall(p, text, flags=re.I)) for p in patterns)


# -----------------------------
# NODE CLASSIFIER
# -----------------------------

def classify_statement(statement: str) -> StatementAssessment:
    s = statement.lower()

    anchor_terms = [
        "according to", "published by", "confirmed", "official", "court", "filing",
        "hearing", "report", "document", "data", "study", "cve-", "mitre",
        "attack technique", "cisa", "odni", "gao", "doj", "fbi", "cia", "treasury",
        "who", "university", "peer-reviewed"
    ]

    event_terms = [
        "occurred", "happened", "observed", "detected", "identified", "reported",
        "released", "launched", "filed", "charged", "arrested", "approved",
        "denied", "voted", "signed", "began", "ended", "published"
    ]

    claim_terms = [
        "suggests", "indicates", "appears", "likely", "reflects", "signals",
        "points to", "consistent with", "because", "may indicate", "could indicate",
        "assess", "we assess", "believed", "linked to", "associated with"
    ]

    inference_terms = [
        "therefore", "must", "proves", "clearly", "undeniable", "no doubt",
        "only explanation", "cannot be coincidence", "shows that", "will lead to",
        "is part of", "coordinated plot", "orchestrated", "inevitably"
    ]

    scores = {
        "A": sum(term in s for term in anchor_terms),
        "E": sum(term in s for term in event_terms),
        "C": sum(term in s for term in claim_terms),
        "I": sum(term in s for term in inference_terms),
    }

    if re.search(r"\b\d{4}\b|\b\d+%\b|\b\$\d+|CVE-\d{4}-\d+", statement, flags=re.I):
        scores["A"] += 0.5

    if any(x in s for x in ["meaning", "motive", "intent", "agenda", "strategy"]):
        scores["C"] += 1

    if any(x in s for x in ["must be", "cannot be", "there is no other"]):
        scores["I"] += 1.5

    node_code = max(scores, key=scores.get)
    max_score = scores[node_code]

    if max_score == 0:
        node_code = "E"
        confidence = 0.45
        signal = "Defaulted to Event: descriptive sentence without strong interpretive markers."
        rationale = "Statement appears mainly descriptive, but confidence is limited because no strong FCT-D markers were detected."
    else:
        total = sum(scores.values()) or 1
        confidence = min(0.95, 0.50 + (max_score / total) * 0.45)
        signal = f"Detected {NODE_DEFINITIONS[node_code]['label']} indicators."
        rationale = NODE_DEFINITIONS[node_code]["definition"]

    return StatementAssessment(
        statement=statement,
        node_code=node_code,
        node_type=NODE_DEFINITIONS[node_code]["label"],
        confidence=round(confidence, 2),
        rationale=rationale,
        signal=signal
    )


# -----------------------------
# EDGE / CHAIN LOGIC
# -----------------------------

def edge_score(from_code: str, to_code: str) -> float:
    transition = f"{from_code}->{to_code}"

    table = {
        "A->E": 0.90,
        "E->E": 0.85,
        "A->C": 0.55,
        "E->C": 0.60,
        "C->C": 0.45,
        "C->I": 0.30,
        "E->I": 0.25,
        "A->I": 0.20,
        "I->I": 0.20,
        "I->C": 0.25,
    }

    return table.get(transition, 0.50)


def build_transitions(assessments: List[StatementAssessment]) -> List[Dict]:
    transitions = []
    for i in range(len(assessments) - 1):
        current = assessments[i]
        nxt = assessments[i + 1]
        score = edge_score(current.node_code, nxt.node_code)
        current.edge_score_to_next = score

        transitions.append({
            "From": current.node_code,
            "To": nxt.node_code,
            "Transition": f"{current.node_code}->{nxt.node_code}",
            "Edge Score": score,
            "Risk Signal": "High-risk escalation" if f"{current.node_code}->{nxt.node_code}" in ["A->I", "E->I", "C->I"] else "Normal / moderate transition",
            "From Statement": current.statement,
            "To Statement": nxt.statement,
        })

    return transitions


def detect_escalations(transitions: List[Dict]) -> List[Dict]:
    return [t for t in transitions if t["Transition"] in ["A->I", "E->I", "C->I"]]


def select_key_statements(assessments: List[StatementAssessment]) -> List[StatementAssessment]:
    selected = []

    for code in ["A", "E", "C", "I"]:
        for a in assessments:
            if a.node_code == code and a not in selected:
                selected.append(a)
                break

    for a in sorted(assessments, key=lambda x: x.confidence, reverse=True):
        if len(selected) >= 5:
            break
        if a not in selected:
            selected.append(a)

    return selected[:5]


# -----------------------------
# TYPOLOGY
# -----------------------------

def detect_anchor_type(text: str) -> Tuple[str, str]:
    s = text.lower()

    emotional = [
        "victim", "children", "trauma", "grief", "scandal", "atrocity", "fear",
        "outrage", "abuse", "death", "crisis", "moral", "harm"
    ]

    institutional = [
        "agency", "official", "government", "court", "department", "ministry",
        "university", "report", "hearing", "filing", "doj", "fbi", "cia",
        "dhs", "odni", "treasury", "congress", "gao"
    ]

    technical = [
        "data", "model", "algorithm", "patent", "study", "dataset", "scientific",
        "technical", "statistical", "quantum", "ai", "machine learning",
        "peer-reviewed", "cve", "mitre", "malware", "ioc"
    ]

    counts = {
        "Emotional": sum(w in s for w in emotional),
        "Institutional": sum(w in s for w in institutional),
        "Technical": sum(w in s for w in technical),
    }

    anchor_type = max(counts, key=counts.get)

    if counts[anchor_type] == 0:
        return "Institutional", "Default baseline: no dominant anchor type detected."

    return anchor_type, ANCHOR_TYPE_GUIDANCE[anchor_type]


def estimate_topology(assessments: List[StatementAssessment]) -> Tuple[str, str]:
    counts = Counter(a.node_code for a in assessments)
    anchors = counts.get("A", 0)
    claims = counts.get("C", 0)
    inferences = counts.get("I", 0)

    if anchors <= 1 and claims + inferences >= 3:
        return "Hub-Spoke", TOPOLOGY_GUIDANCE["Hub-Spoke"]

    if anchors >= 2 and claims >= 3 and inferences >= 2:
        return "Lattice", TOPOLOGY_GUIDANCE["Lattice"]

    return "Hierarchical", TOPOLOGY_GUIDANCE["Hierarchical"]


def get_combined_guidance(anchor_type: str, topology: str) -> str:
    return COMBINED_TRIAGE_MATRIX.get(
        (anchor_type, topology),
        "General structural review required. Validate anchors and inspect unsupported transitions."
    )


# -----------------------------
# RECURSION CHECK
# -----------------------------

def check_micro_recursion(transitions: List[Dict]) -> Tuple[bool, str]:
    high_risk = detect_escalations(transitions)
    if high_risk:
        return True, "Micro recursion indicator: sentence-level transition shows escalation into inference."
    return False, "No strong sentence-level escalation detected."


def check_meso_recursion(text: str) -> Tuple[bool, str]:
    paragraphs = split_into_paragraphs(text)
    if len(paragraphs) < 2:
        return False, "Insufficient paragraph structure for meso-level recursion."

    escalatory_paragraphs = 0

    for p in paragraphs[:8]:
        statements, _, _ = split_into_statements(p)
        assessments = [classify_statement(s) for s in statements]
        counts = Counter(a.node_code for a in assessments)
        if counts.get("C", 0) + counts.get("I", 0) >= 2:
            escalatory_paragraphs += 1

    if escalatory_paragraphs >= 2:
        return True, "Meso recursion indicator: multiple paragraphs contain claim/inference expansion."

    return False, "Meso recursion not strongly demonstrated across paragraphs."


def check_macro_recursion(assessments: List[StatementAssessment]) -> Tuple[bool, str]:
    if len(assessments) < 4:
        return False, "Insufficient document length for macro-level structure."

    first_third = assessments[:max(1, len(assessments)//3)]
    last_third = assessments[-max(1, len(assessments)//3):]

    early_anchors = sum(1 for a in first_third if a.node_code == "A")
    late_interpretive = sum(1 for a in last_third if a.node_code in ["C", "I"])

    if early_anchors >= 1 and late_interpretive >= 2:
        return True, "Macro recursion indicator: early anchor base expands toward later claims/inferences."

    return False, "Macro recursion not strongly demonstrated."


def assess_recursion(text: str, assessments: List[StatementAssessment], transitions: List[Dict]) -> Tuple[bool, str, Dict]:
    micro, micro_note = check_micro_recursion(transitions)
    meso, meso_note = check_meso_recursion(text)
    macro, macro_note = check_macro_recursion(assessments)

    details = {
        "Micro": (micro, micro_note),
        "Meso": (meso, meso_note),
        "Macro": (macro, macro_note),
    }

    confirmed = micro and meso and macro

    if confirmed:
        return True, "Fractal recursion confirmed across micro, meso, and macro levels.", details

    return False, "Fractal recursion not fully confirmed across all three required scales.", details


# -----------------------------
# METRICS
# -----------------------------

def calculate_fct_metrics(text: str, assessments: List[StatementAssessment], transitions: List[Dict]) -> Dict[str, float]:
    counts = Counter(a.node_code for a in assessments)
    source_count = count_sources(text)

    total_edges = max(len(transitions), 1)
    unsupported_edges = sum(1 for t in transitions if t["Edge Score"] < 0.50)
    uer = min(1.0, unsupported_edges / total_edges)

    anchor_scores = [a.confidence for a in assessments if a.node_code == "A"]
    anchor_score = max(anchor_scores) if anchor_scores else 0.70

    edge_scores = [t["Edge Score"] for t in transitions]
    avg_edge_score = sum(edge_scores) / len(edge_scores) if edge_scores else 0.70

    # Doctrine-correct definition:
    # Drop-off = anchor score − average edge score
    drop_off = max(0.0, min(1.0, anchor_score - avg_edge_score))

    connectivity = min(1.0, (counts.get("C", 0) * 0.07) + (counts.get("I", 0) * 0.10))

    anchors = max(counts.get("A", 0), 1)
    centrality = min(1.0, (counts.get("C", 0) + counts.get("I", 0)) / (anchors * 8))

    score = (0.40 * uer) + (0.25 * drop_off) + (0.20 * connectivity) + (0.15 * centrality)

    return {
        "UER": round(uer, 2),
        "Drop-off": round(drop_off, 2),
        "Connectivity": round(connectivity, 2),
        "Centrality": round(centrality, 2),
        "FCT Risk Score": round(min(1.0, score), 2),
        "Source Count": source_count,
        "Anchor Score": round(anchor_score, 2),
        "Average Edge Score": round(avg_edge_score, 2),
        "Unsupported Edges": unsupported_edges,
        "Total Edges": total_edges,
    }


def get_risk_level(score: float) -> Tuple[str, str]:
    for low, high, label, explanation in RISK_BANDS:
        if low <= score <= high:
            return label, explanation
    return "Critical", "Structural coherence appears to drive credibility."


def assess_conditions(text: str, assessments: List[StatementAssessment], transitions: List[Dict], metrics: Dict[str, float]) -> Tuple[Dict[str, Tuple[bool, str]], Dict]:
    counts = Counter(a.node_code for a in assessments)

    has_anchor = counts.get("A", 0) >= 1
    has_transfer = metrics["UER"] >= 0.30 and (counts.get("C", 0) + counts.get("I", 0)) >= 2
    has_recursion, recursion_note, recursion_details = assess_recursion(text, assessments, transitions)

    conditions = {
        "Anchor Presence": (
            has_anchor,
            "At least one anchor-like statement detected." if has_anchor else "No strong anchor detected."
        ),
        "Structural Transfer": (
            has_transfer,
            "Interpretive claims appear to exceed explicit sourcing." if has_transfer else "Insufficient evidence that structure is substituting for sourcing."
        ),
        "Fractal Recursion": (
            has_recursion,
            recursion_note
        ),
        "Density-to-Sourcing Imbalance": (
            metrics["UER"] >= 0.50,
            "High unsupported edge ratio detected." if metrics["UER"] >= 0.50 else "Density imbalance not strongly confirmed."
        ),
        "Self-Referential Closure": (
            metrics["Source Count"] <= 1 and metrics["UER"] >= 0.40,
            "Low external sourcing plus high interpretive load suggests possible internal closure." if metrics["Source Count"] <= 1 and metrics["UER"] >= 0.40 else "No strong self-referential closure detected."
        ),
    }

    return conditions, recursion_details


# -----------------------------
# MAIN ANALYSIS
# -----------------------------

def analyze_document(text: str) -> Dict:
    statements, total_statements, truncated = split_into_statements(text)
    assessments = [classify_statement(s) for s in statements]
    transitions = build_transitions(assessments)
    metrics = calculate_fct_metrics(text, assessments, transitions)

    risk_level, risk_explanation = get_risk_level(metrics["FCT Risk Score"])
    anchor_type, anchor_type_note = detect_anchor_type(text)
    topology, topology_note = estimate_topology(assessments)
    combined_guidance = get_combined_guidance(anchor_type, topology)

    conditions, recursion_details = assess_conditions(text, assessments, transitions, metrics)

    mandatory_met = all(
        conditions[k][0]
        for k in ["Anchor Presence", "Structural Transfer", "Fractal Recursion"]
    )

    confirmatory_met = any(
        conditions[k][0]
        for k in ["Density-to-Sourcing Imbalance", "Self-Referential Closure"]
    )

    fct_classification = mandatory_met and confirmatory_met

    analyst_note = (
        f"FCT-D conditions are present. The artifact shows {anchor_type.lower()} anchor characteristics with a {topology.lower()} structure. Primary concern: perceived coherence may be generated by narrative architecture rather than proportional evidentiary support. Recommended action: {combined_guidance}"
        if fct_classification else
        "Full FCT-D classification is not supported because one or more mandatory/confirmatory conditions are not met. Treat this as a structural concern requiring further analyst review, not confirmed FCT-D."
    )

    return {
        "statements": assessments,
        "key_statements": select_key_statements(assessments),
        "transitions": transitions,
        "escalations": detect_escalations(transitions),
        "metrics": metrics,
        "risk_level": risk_level,
        "risk_explanation": risk_explanation,
        "anchor_type": anchor_type,
        "anchor_type_note": anchor_type_note,
        "topology": topology,
        "topology_note": topology_note,
        "combined_guidance": combined_guidance,
        "conditions": conditions,
        "recursion_details": recursion_details,
        "countermeasure": COUNTERMEASURES[topology],
        "analyst_note": analyst_note,
        "truncated": truncated,
        "total_statements": total_statements,
        "analyzed_statements": len(statements),
        "fct_classification": fct_classification,
    }


# -----------------------------
# RENDER HELPERS
# -----------------------------

def render_condition(name: str, result: Tuple[bool, str]):
    passed, explanation = result
    icon = "✅" if passed else "⚠️"
    st.markdown(f"**{icon} {name}**")
    st.caption(explanation)


def assessment_to_row(a: StatementAssessment) -> Dict:
    return {
        "Code": a.node_code,
        "Type": a.node_type,
        "Confidence": a.confidence,
        "Statement": a.statement,
        "Signal": a.signal,
    }


def render_reference_tab():
    st.subheader("FCT-D Field Reference")
    st.info("FCT-D assesses structural credibility dynamics. It does not determine truth, intent, guilt, or deception.")

    st.markdown("### 10-Second Analyst Method")
    st.markdown("**Circle Anchors → Underline Events → Box Claims → Star Inferences**")
    st.markdown("Then ask: **Are conclusions supported by new evidence or just earlier statements?**")

    st.markdown("### Credibility Ladder")
    ladder_df = pd.DataFrame([
        {
            "Code": code,
            "Node": v["label"],
            "Meaning": v["meaning"],
            "Field Test": v["field_test"]
        }
        for code, v in NODE_DEFINITIONS.items()
    ])
    st.dataframe(ladder_df, use_container_width=True, hide_index=True)

    st.markdown("### Mandatory Conditions")
    st.markdown("1. **Anchor Presence** — credible or salient entry point exists.")
    st.markdown("2. **Structural Transfer** — linguistic or structural design substitutes for sourcing.")
    st.markdown("3. **Fractal Recursion** — same transfer pattern repeats at micro, meso, and macro levels.")

    st.markdown("### Combined Triage Matrix")
    matrix_df = pd.DataFrame([
        {
            "Anchor Type": a,
            "Topology": t,
            "Guidance": g
        }
        for (a, t), g in COMBINED_TRIAGE_MATRIX.items()
    ])
    st.dataframe(matrix_df, use_container_width=True, hide_index=True)

    st.markdown("### Topology Countermeasures")
    topo_df = pd.DataFrame([
        {
            "Topology": k,
            "Description": TOPOLOGY_GUIDANCE[k],
            "Countermeasure": COUNTERMEASURES[k]
        }
        for k in TOPOLOGY_GUIDANCE
    ])
    st.dataframe(topo_df, use_container_width=True, hide_index=True)

    st.markdown("### Adjacent Concept Distinctions")
    st.dataframe(pd.DataFrame(ADJACENT_CONCEPTS), use_container_width=True, hide_index=True)

    st.markdown("### Critical Distinctions")
    st.markdown("- **FCT-D ≠ false**")
    st.markdown("- **FCT-D ≠ deception**")
    st.markdown("- **FCT-D ≠ intent assessment**")
    st.markdown("- **FCT-D = structure-driven credibility transfer**")


# -----------------------------
# APP UI
# -----------------------------

st.title("FCT-D Analyst Workbench")
st.caption("Fractal Credibility Transfer | Document Variant | Structural Credibility Triage")
st.warning(
    "This prototype is a structural diagnostic tool. It does not determine whether claims are true or false, "
    "and it does not assess intent or deception. High-stakes use requires corroboration."
)

mode = st.sidebar.radio("Analyst Mode", ["Experienced Analyst", "Junior / Trainee Analyst"])
st.sidebar.markdown("---")
st.sidebar.markdown("### Accepted Inputs")
st.sidebar.markdown("Paste text or upload `.txt`, `.docx`, or `.pdf`.")
st.sidebar.markdown("---")
st.sidebar.caption("Rule-based heuristic engine. Designed for demonstration and validation testing.")

main_tab, node_tab, scoring_tab, reference_tab = st.tabs(
    ["Document Triage", "Node Classifier", "Scoring Layer", "Field Reference"]
)


# -----------------------------
# DOCUMENT TRIAGE
# -----------------------------

with main_tab:
    left, right = st.columns([1.15, 0.85])

    with left:
        st.subheader("Input Document")
        uploaded = st.file_uploader("Upload document", type=["txt", "docx", "pdf"])
        uploaded_text = load_uploaded_text(uploaded) if uploaded else ""

        text_input = st.text_area(
            "Paste text for FCT-D evaluation",
            value=uploaded_text,
            height=360,
            placeholder="Paste article, assessment, social thread, policy memo, or OSINT artifact here..."
        )

        run = st.button("Run FCT-D Analysis", type="primary", use_container_width=True)

    with right:
        st.subheader("Doctrine Reminder")
        st.markdown("**FCT-D asks:** Is the document’s perceived credibility earned through evidence, or constructed through structure?")
        st.markdown("**Mandatory Conditions:**")
        st.markdown("- Anchor Presence\n- Structural Transfer\n- Fractal Recursion")
        st.markdown("**Confirmatory Conditions:**")
        st.markdown("- Density-to-Sourcing Imbalance\n- Self-Referential Closure")

        if mode == "Junior / Trainee Analyst":
            st.info("Trainee cue: The primary failure point is the transition from Event → Claim.")

    if run:
        if not text_input.strip():
            st.error("Please paste or upload text before running analysis.")
        else:
            st.session_state["last_result"] = analyze_document(text_input)
            st.session_state["last_text"] = text_input

    if "last_result" in st.session_state:
        result = st.session_state["last_result"]

        st.markdown("---")
        st.subheader("FCT-D Assessment Output")

        if result["truncated"]:
            st.warning(
                f"Only first {result['analyzed_statements']} of {result['total_statements']} statements analyzed. "
                "Long documents may require chunked review."
            )

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("FCT Risk Score", result["metrics"]["FCT Risk Score"])
        m2.metric("Risk Level", result["risk_level"])
        m3.metric("Anchor Type", result["anchor_type"])
        m4.metric("Topology", result["topology"])

        st.caption(result["risk_explanation"])

        if result["fct_classification"]:
            st.success("FCT-D classification supported: mandatory criteria met and at least one confirmatory condition present.")
        else:
            st.info("FCT-D classification not fully supported. Treat as structural triage, not confirmed FCT-D.")

        c1, c2 = st.columns([1, 1])

        with c1:
            st.markdown("### Criteria Assessment")
            for name, condition in result["conditions"].items():
                render_condition(name, condition)

            st.markdown("### Recursion Details")
            for scale, detail in result["recursion_details"].items():
                render_condition(scale, detail)

        with c2:
            st.markdown("### Combined Triage Matrix Guidance")
            st.success(result["combined_guidance"])

            st.markdown("### Topology Countermeasure")
            st.write(result["countermeasure"])

            st.markdown("### Analyst Note")
            st.write(result["analyst_note"])

            if mode == "Junior / Trainee Analyst":
                st.info("A high score does not mean the document is false. It means the structure may be doing more credibility work than the evidence supports.")

        st.markdown("### Key Statement Classification — 3–5 Nodes")
        key_rows = [assessment_to_row(a) for a in result["key_statements"]]
        st.dataframe(pd.DataFrame(key_rows), use_container_width=True, hide_index=True)

        st.markdown("### Escalation Analysis")
        if result["escalations"]:
            st.dataframe(pd.DataFrame(result["escalations"]), use_container_width=True, hide_index=True)
        else:
            st.write("No A→I, E→I, or C→I escalation transitions detected.")

        with st.expander("Show Full Node Table"):
            rows = [assessment_to_row(a) for a in result["statements"]]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        with st.expander("Show Scoring Components"):
            st.dataframe(
                pd.DataFrame(
                    [{"Metric": k, "Value": v} for k, v in result["metrics"].items()]
                ),
                use_container_width=True,
                hide_index=True
            )


# -----------------------------
# NODE CLASSIFIER + CHAIN BUILDER
# -----------------------------

with node_tab:
    st.subheader("Single Statement Node Classifier + Chain Builder")

    if "node_chain" not in st.session_state:
        st.session_state["node_chain"] = []

    statement = st.text_area("Enter one statement", height=140)

    col_a, col_b, col_c = st.columns(3)

    with col_a:
        classify_btn = st.button("Classify Statement", use_container_width=True)

    with col_b:
        add_btn = st.button("Add to Chain", use_container_width=True)

    with col_c:
        clear_btn = st.button("Clear Chain", use_container_width=True)

    if classify_btn:
        if not statement.strip():
            st.error("Enter a statement first.")
        else:
            a = classify_statement(statement)
            st.metric("Node Type", f"{a.node_code} — {a.node_type}")
            st.metric("Confidence", a.confidence)
            st.write("**Rationale:**", a.rationale)
            st.write("**Signal:**", a.signal)

            if mode == "Junior / Trainee Analyst":
                st.info(NODE_DEFINITIONS[a.node_code]["field_test"])

    if add_btn:
        if not statement.strip():
            st.error("Enter a statement first.")
        else:
            a = classify_statement(statement)
            st.session_state["node_chain"].append(a)
            st.success(f"Added to chain: {a.node_code} — {a.node_type}")

    if clear_btn:
        st.session_state["node_chain"] = []
        st.success("Chain cleared.")

    st.markdown("### Running Chain")

    if st.session_state["node_chain"]:
        chain_rows = [assessment_to_row(a) for a in st.session_state["node_chain"]]
        st.dataframe(pd.DataFrame(chain_rows), use_container_width=True, hide_index=True)

        transitions = build_transitions(st.session_state["node_chain"])
        escalations = detect_escalations(transitions)

        st.markdown("### Chain Escalation Analysis")
        if transitions:
            st.dataframe(pd.DataFrame(transitions), use_container_width=True, hide_index=True)
        else:
            st.write("Add at least two statements to analyze transitions.")

        if escalations:
            st.warning("High-risk escalation transition detected.")
            st.dataframe(pd.DataFrame(escalations), use_container_width=True, hide_index=True)
        else:
            st.info("No high-risk A→I, E→I, or C→I transition detected yet.")
    else:
        st.caption("No statements in chain yet.")


# -----------------------------
# SCORING LAYER
# -----------------------------

with scoring_tab:
    st.subheader("Manual FCT Risk Score Calculator")
    st.caption("Score = (0.40 × UER) + (0.25 × Drop-off) + (0.20 × Connectivity) + (0.15 × Centrality)")
    st.caption("Doctrine note: Drop-off = anchor score − average edge score.")

    uer = st.slider("Unsupported Edge Ratio", 0.0, 1.0, 0.40, 0.01)
    anchor_score = st.slider("Anchor Score", 0.0, 1.0, 0.90, 0.01)
    avg_edge_score = st.slider("Average Edge Score", 0.0, 1.0, 0.55, 0.01)
    drop = max(0.0, min(1.0, anchor_score - avg_edge_score))
    conn = st.slider("Connectivity", 0.0, 1.0, 0.40, 0.01)
    cent = st.slider("Centrality", 0.0, 1.0, 0.35, 0.01)

    manual_score = round((0.40 * uer) + (0.25 * drop) + (0.20 * conn) + (0.15 * cent), 2)
    level, expl = get_risk_level(manual_score)

    st.metric("Calculated Drop-off", round(drop, 2))
    st.metric("Manual FCT Risk Score", manual_score)
    st.metric("Risk Level", level)
    st.caption(expl)


# -----------------------------
# FIELD REFERENCE
# -----------------------------

with reference_tab:
    render_reference_tab()
