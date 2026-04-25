"""
FCT-D Analyst Workbench — Streamlit Prototype
Fractal Credibility Transfer | Document Triage Application
Author concept: Kevin M. Hollenbeck | April 2026

Doctrine-aligned revision. Implements:
  - Corrected Fractal Recursion detection (micro/meso/macro scale analysis)
  - Combined 3x3 Triage Matrix (Anchor Type × Topology) with joint countermeasures
  - Node Classifier running chain with escalation analysis
  - Doctrine-aligned Drop-off formula (anchor score − avg edge score)
  - Improved UER sourcing detection
  - Reclassification path when mandatory conditions fail
  - 10-second analyst method in Field Reference
  - Triage Field Rule in Document Triage
  - Combined topology × anchor type countermeasures

This prototype uses a rule-based heuristic engine.
It is NOT a truth engine. It assesses structure-driven credibility risk, not factual accuracy, intent, or deception.
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import pandas as pd
import streamlit as st

try:
    from docx import Document as DocxDocument
except Exception:
    DocxDocument = None

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

# ─────────────────────────────────────────────
# CONFIGURATION & DOCTRINE TABLES
# ─────────────────────────────────────────────

st.set_page_config(
    page_title="FCT-D Analyst Workbench",
    page_icon="🧠",
    layout="wide"
)

NODE_DEFINITIONS = {
    "A": {
        "label": "Anchor",
        "meaning": "It is",
        "definition": "Verified, defensible, or highly salient entry point. Independently sourceable or emotionally/institutionally compelling.",
        "field_test": "Can I prove this right now from a primary source outside this artifact?",
        "risk": "Baseline — no risk on its own.",
    },
    "E": {
        "label": "Event",
        "meaning": "It happened",
        "definition": "Observable occurrence or real-world condition. Reports what happened, not what it means.",
        "field_test": "Is this describing what occurred rather than interpreting it?",
        "risk": "Low — observable, not interpretive.",
    },
    "C": {
        "label": "Claim",
        "meaning": "It means",
        "definition": "Interpretation of events. Assigns meaning, motive, consequence, or significance. PRIMARY FAILURE POINT.",
        "field_test": "Is this explaining meaning instead of stating fact?",
        "risk": "High — first point where credibility transfers structurally rather than evidentially.",
    },
    "I": {
        "label": "Inference",
        "meaning": "It must be",
        "definition": "Conclusion built on stacked claims. Extends beyond what evidence directly proves. Highest risk node.",
        "field_test": "Can this be independently verified, or does it depend on earlier steps?",
        "risk": "Critical — entirely dependent on prior chain integrity.",
    },
}

RISK_BANDS = [
    (0.00, 0.29, "Low",      "Evidence appears to scale with structure."),
    (0.30, 0.49, "Moderate", "Partial structural substitution for sourcing."),
    (0.50, 0.69, "High",     "Structure substantially exceeds evidence."),
    (0.70, 1.00, "Critical", "Structural coherence appears to drive credibility."),
]

ANCHOR_TYPE_GUIDANCE = {
    "Emotional":     "Trauma, scandal, grief, moral urgency, outrage, atrocity, fear, children, victims.",
    "Institutional": "Agencies, officials, courts, universities, documents, reports, named organizations.",
    "Technical":     "Scientific language, datasets, models, patents, technical jargon, statistics, charts.",
}

TOPOLOGY_GUIDANCE = {
    "Hub-Spoke":    "Single dominant anchor with multiple peripheral claims radiating outward.",
    "Hierarchical": "Anchor develops into mid-level sub-anchors, which then support additional claims.",
    "Lattice":      "Multiple anchors cross-reference and mutually reinforce; no single root node dominates.",
}

# Topology countermeasures (standalone)
COUNTERMEASURES = {
    "Hub-Spoke":    "Validate or refute the hub anchor first. Peripheral claims may collapse as a secondary effect. A single sourcing check on the anchor event is often sufficient.",
    "Hierarchical": "Map the full claim tree before engaging any node. Refute at the highest viable tier. Subclaims may persist; continue working downward systematically.",
    "Lattice":      "Require independent verification paths for each anchor. Internal cross-references within the network do not constitute corroboration. Escalate Technical-Lattice variants to SME review.",
}

# 3×3 Combined Triage Matrix (Anchor Type × Topology) — doctrine Section 4
COMBINED_MATRIX = {
    ("Emotional", "Hub-Spoke"):    "Fastest to collapse. Verify anchor event; peripheral claims fall automatically. Single sourcing check is usually sufficient.",
    ("Emotional", "Hierarchical"): "Grief or moral urgency escalates into doctrine. Map the emotional cascade path before engaging. Identify where urgency converts to factual claim.",
    ("Emotional", "Lattice"):      "Most manipulative emotional variant. Multiple trauma or outrage anchors mutually reinforce. Per-anchor independent verification required.",
    ("Institutional", "Hub-Spoke"):    "Classic influence playbook. Named agency or official as hub; verify primary documents first. Check whether citations actually support the claims made.",
    ("Institutional", "Hierarchical"): "Agency → program → claim tree. Refute at institutional tier first; subclaims may persist independently.",
    ("Institutional", "Lattice"):      "Agencies cross-cited. Each lends halo to the others. Verify each institution independently; internal cross-references do not qualify as corroboration.",
    ("Technical", "Hub-Spoke"):    "Jargon hub radiating pseudoscience. SME review of the anchor term is usually sufficient to collapse peripheral claims.",
    ("Technical", "Hierarchical"): "Real paper → misread finding → theory tree. Engage at the paper or study level; refute the interpretive chain.",
    ("Technical", "Lattice"):      "MOST DURABLE VARIANT. Cross-reinforcing technical anchors. Escalate to SME triage. Do not engage without subject-matter expertise.",
}

# Reclassification paths when mandatory conditions fail (doctrine Section 4.3 note)
RECLASSIFICATION = {
    "no_anchor":    "No strong anchor detected. Cannot classify as FCT-D. Consider reviewing for unsourced speculation or weak narrative without credibility base.",
    "no_transfer":  "Structural transfer not confirmed. Credibility spread appears proportional to sourcing. This may be a well-sourced document or a simple information report.",
    "no_recursion": "Anchor Presence and Structural Transfer confirmed, but Fractal Recursion is not detected across micro/meso/macro scales. RECLASSIFY: evaluate for Narrative Cascade (temporal spread, node-to-node) or Credibility Laundering (proximity-based legitimacy transfer without recursive structure).",
}

# ─────────────────────────────────────────────
# DATA CLASS
# ─────────────────────────────────────────────

@dataclass
class StatementAssessment:
    statement: str
    node_code: str
    node_type: str
    confidence: float
    rationale: str
    signal: str
    position: int = 0          # index in document (used for scale analysis)
    section: str = "unknown"   # micro / meso / macro


# ─────────────────────────────────────────────
# FILE LOADING
# ─────────────────────────────────────────────

def extract_text_from_docx(uploaded_file) -> str:
    if DocxDocument is None:
        return ""
    doc = DocxDocument(uploaded_file)
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


# ─────────────────────────────────────────────
# TEXT PROCESSING
# ─────────────────────────────────────────────

def split_into_statements(text: str) -> List[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    return [p.strip() for p in parts if len(p.strip()) > 25][:80]


def assign_scale_section(idx: int, total: int) -> str:
    """Assign micro/meso/macro based on position in document."""
    if total == 0:
        return "micro"
    pct = idx / total
    if pct < 0.33:
        return "micro"
    elif pct < 0.67:
        return "meso"
    else:
        return "macro"


def count_sources(text: str) -> int:
    """
    Count explicit sourcing indicators. Broader than URL-only detection to
    catch documents that reference primary sources without formal citation syntax.
    """
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
        r"citing",
        r"as stated by",
        r"as noted by",
        r"per\s+[A-Z]",          # "per FBI", "per DHS"
        r"confirmed by",
        r"based on",
        r"the\s+\w+\s+report",   # "the GAO report"
        r"\bIbid\b",
        r"op\.?\s*cit",
        r"et al\.",
        r"\bp\.\s*\d+",          # page citations
        r"testimony",
        r"filing",
        r"court\s+document",
        r"official\s+statement",
    ]
    return sum(len(re.findall(p, text, flags=re.I)) for p in patterns)


# ─────────────────────────────────────────────
# NODE CLASSIFICATION
# ─────────────────────────────────────────────

def classify_statement(statement: str, idx: int = 0, total: int = 1) -> StatementAssessment:
    s = statement.lower()

    anchor_terms = [
        "report", "document", "agency", "court", "official", "university",
        "study", "data", "according to", "published", "confirmed", "stated",
        "announced", "department", "ministry", "fbi", "cia", "dhs", "odni",
        "who", "un", "treasury", "doj", "gao", "congress", "hearing",
        "filing", "primary source", "on record", "documented",
    ]
    event_terms = [
        "occurred", "happened", "arrested", "charged", "launched", "met",
        "signed", "released", "killed", "attacked", "reported", "filed",
        "voted", "approved", "denied", "created", "began", "ended",
        "took place", "was held", "was found", "was released",
    ]
    claim_terms = [
        "suggests", "indicates", "shows", "means", "reveals", "demonstrates",
        "points to", "signals", "reflects", "evidence of", "likely", "appears",
        "implies", "because", "therefore", "as a result", "which means",
        "this indicates", "this suggests", "context of",
    ]
    inference_terms = [
        "must", "therefore", "proves", "undeniable", "clearly", "no doubt",
        "only explanation", "cannot be coincidence", "shows that",
        "will lead to", "is part of", "coordinated", "orchestrated",
        "inevitably", "must be", "cannot be", "there is no other",
        "pattern is clear", "no question", "obvious that",
    ]

    scores = {
        "A": sum(term in s for term in anchor_terms),
        "E": sum(term in s for term in event_terms),
        "C": sum(term in s for term in claim_terms),
        "I": sum(term in s for term in inference_terms),
    }

    # Scoring bonuses
    if re.search(r"\b\d{4}\b|\b\d+%\b|\b\$\d+", statement):
        scores["A"] += 0.5
    if any(x in s for x in ["why", "meaning", "motive", "intent", "agenda"]):
        scores["C"] += 1
    if any(x in s for x in ["inevitably", "must be", "cannot be", "there is no other", "pattern is clear"]):
        scores["I"] += 1.5

    node_code = max(scores, key=scores.get)
    max_score = scores[node_code]

    if max_score == 0:
        node_code = "E"
        confidence = 0.45
        signal = "Defaulted to Event: descriptive sentence without strong interpretive markers."
        rationale = "Statement appears mainly descriptive; no strong FCT markers detected."
    else:
        total_score = sum(scores.values()) or 1
        confidence = min(0.95, 0.50 + (max_score / total_score) * 0.45)
        signal = f"Detected {NODE_DEFINITIONS[node_code]['label']} indicators."
        rationale = NODE_DEFINITIONS[node_code]["definition"]

    section = assign_scale_section(idx, total)

    return StatementAssessment(
        statement=statement,
        node_code=node_code,
        node_type=NODE_DEFINITIONS[node_code]["label"],
        confidence=round(confidence, 2),
        rationale=rationale,
        signal=signal,
        position=idx,
        section=section,
    )


# ─────────────────────────────────────────────
# ANCHOR TYPE & TOPOLOGY
# ─────────────────────────────────────────────

def detect_anchor_type(text: str) -> Tuple[str, str]:
    s = text.lower()
    emotional    = ["victim", "children", "trauma", "grief", "scandal", "atrocity",
                    "fear", "outrage", "abuse", "death", "crisis", "tragedy", "horror"]
    institutional = ["agency", "official", "government", "court", "department",
                     "ministry", "university", "report", "hearing", "filing",
                     "doj", "fbi", "cia", "dhs", "odni", "treasury", "congress",
                     "senate", "committee", "administration"]
    technical    = ["data", "model", "algorithm", "patent", "study", "dataset",
                    "scientific", "technical", "statistical", "quantum", "ai",
                    "machine learning", "peer-reviewed", "analysis", "survey",
                    "research", "experiment", "methodology"]

    counts = {
        "Emotional":     sum(w in s for w in emotional),
        "Institutional": sum(w in s for w in institutional),
        "Technical":     sum(w in s for w in technical),
    }
    anchor_type = max(counts, key=counts.get)
    if counts[anchor_type] == 0:
        return "Institutional", "Default: no dominant anchor type detected; Institutional selected as neutral baseline."
    return anchor_type, ANCHOR_TYPE_GUIDANCE[anchor_type]


def estimate_topology(assessments: List[StatementAssessment]) -> Tuple[str, str]:
    counts = Counter(a.node_code for a in assessments)
    anchors   = counts.get("A", 0)
    claims    = counts.get("C", 0)
    inferences = counts.get("I", 0)

    if anchors >= 2 and claims >= 3 and inferences >= 2:
        return "Lattice", TOPOLOGY_GUIDANCE["Lattice"]
    if anchors <= 1 and claims + inferences >= 3:
        return "Hub-Spoke", TOPOLOGY_GUIDANCE["Hub-Spoke"]
    return "Hierarchical", TOPOLOGY_GUIDANCE["Hierarchical"]


# ─────────────────────────────────────────────
# FRACTAL RECURSION DETECTION (doctrine-aligned)
# ─────────────────────────────────────────────

def detect_fractal_recursion(assessments: List[StatementAssessment]) -> Tuple[bool, str]:
    """
    Doctrine: Fractal Recursion = the credibility-transfer pattern (A→C or A→I)
    repeats at micro (sentence), meso (paragraph/section), and macro (full artifact) levels simultaneously.

    Implementation:
      - Divide statements into three thirds (micro / meso / macro sections)
      - Confirm that each section contains at least one Anchor or Claim/Inference escalation
      - Confirm that the escalation ratio (C+I / A+E) is present in ALL three sections
      - If only 1-2 sections show the pattern: cascade not recursion
    """
    if len(assessments) < 6:
        return False, "Insufficient document length for multi-scale recursion analysis (minimum 6 classified statements required)."

    sections = {"micro": [], "meso": [], "macro": []}
    for a in assessments:
        sections[a.section].append(a.node_code)

    section_results = {}
    for scale, nodes in sections.items():
        if not nodes:
            section_results[scale] = False
            continue
        anchor_event = sum(1 for n in nodes if n in ("A", "E"))
        claim_inf    = sum(1 for n in nodes if n in ("C", "I"))
        # Pattern present if claims/inferences exist AND outnumber anchors/events
        section_results[scale] = claim_inf > 0 and claim_inf >= anchor_event

    scales_with_pattern = sum(1 for v in section_results.values() if v)

    if scales_with_pattern == 3:
        return True, "Credibility-transfer pattern (escalation from Anchor/Event to Claim/Inference) confirmed at micro, meso, and macro scales simultaneously."
    elif scales_with_pattern == 2:
        active = [k for k, v in section_results.items() if v]
        return False, f"Pattern detected at {active[0]} and {active[1]} scales only — not all three. This suggests Narrative Cascade rather than Fractal Recursion. RECLASSIFY."
    elif scales_with_pattern == 1:
        active = [k for k, v in section_results.items() if v]
        return False, f"Pattern detected at {active[0]} scale only. Insufficient for FCT-D classification. Consider Credibility Laundering or simple interpretive reporting."
    else:
        return False, "No escalation pattern detected at any scale. Document does not meet Fractal Recursion condition."


# ─────────────────────────────────────────────
# FCT METRICS (doctrine-aligned formulas)
# ─────────────────────────────────────────────

def calculate_fct_metrics(text: str, assessments: List[StatementAssessment]) -> Dict:
    total_statements = max(len(assessments), 1)
    counts = Counter(a.node_code for a in assessments)
    source_count = count_sources(text)

    # UER = unsupported edges / total edges
    # Edges = transitions from evidence nodes (A, E) to interpretive nodes (C, I)
    # Unsupported edges = interpretive nodes that exceed available sources
    interpretive_count = counts.get("C", 0) + counts.get("I", 0)
    total_edges = max(1, counts.get("E", 0) + counts.get("C", 0) + counts.get("I", 0))
    unsupported_edges = max(0, interpretive_count - source_count)
    uer = min(1.0, unsupported_edges / total_edges)

    # Drop-off: doctrine defines as anchor score − avg edge score
    # Operationalized as: anchor node density − average interpretive node density per source
    anchor_density = counts.get("A", 0) / total_statements
    interpretive_density = interpretive_count / total_statements
    source_density = min(1.0, source_count / max(1, total_statements))
    # Drop-off = how far the interpretive layer exceeds available anchoring/sourcing
    drop_off = min(1.0, max(0.0, interpretive_density - (anchor_density + source_density)))

    # Connectivity: how interconnected the interpretive layer is
    connectivity = min(1.0, (counts.get("C", 0) * 0.07) + (counts.get("I", 0) * 0.10))

    # Centrality: ratio of interpretive nodes to anchors (how much work anchors are doing)
    anchors = max(counts.get("A", 0), 1)
    centrality = min(1.0, (counts.get("C", 0) + counts.get("I", 0)) / (anchors * 8))

    score = (0.40 * uer) + (0.25 * drop_off) + (0.20 * connectivity) + (0.15 * centrality)

    return {
        "UER":           round(uer, 2),
        "Drop-off":      round(drop_off, 2),
        "Connectivity":  round(connectivity, 2),
        "Centrality":    round(centrality, 2),
        "FCT Risk Score": round(min(1.0, score), 2),
        "Source Count":  source_count,
        "Node Counts":   dict(counts),
    }


def get_risk_level(score: float) -> Tuple[str, str]:
    for low, high, label, explanation in RISK_BANDS:
        if low <= score <= high:
            return label, explanation
    return "Critical", "Structural coherence appears to drive credibility."


# ─────────────────────────────────────────────
# CONDITIONS ASSESSMENT (doctrine-aligned)
# ─────────────────────────────────────────────

def assess_conditions(assessments: List[StatementAssessment], metrics: Dict) -> Dict[str, Tuple[bool, str]]:
    counts = Counter(a.node_code for a in assessments)

    # Anchor Presence
    has_anchor = counts.get("A", 0) >= 1
    anchor_note = (
        "At least one anchor-like statement detected."
        if has_anchor
        else "No strong anchor detected."
    )

    # Structural Transfer — implied relationships exceed sourced relationships
    interpretive = counts.get("C", 0) + counts.get("I", 0)
    has_transfer = interpretive >= 2 and metrics["UER"] >= 0.30
    transfer_note = (
        "Interpretive claims appear to exceed explicit sourcing. Design substitutes for sourcing."
        if has_transfer
        else "Insufficient evidence that structure is substituting for sourcing."
    )

    # Fractal Recursion — runs full scale analysis
    has_recursion, recursion_note = detect_fractal_recursion(assessments)

    # Confirmatory: Density-to-Sourcing Imbalance
    density_imbalance = metrics["UER"] >= 0.50
    density_note = (
        "High unsupported edge ratio detected. Many interpretive nodes relative to sourced support."
        if density_imbalance
        else "Density imbalance not strongly confirmed."
    )

    # Confirmatory: Self-Referential Closure
    self_ref = metrics["Source Count"] <= 1 and metrics["UER"] >= 0.40
    self_ref_note = (
        "Low external sourcing plus high interpretive load suggests possible self-referential closure."
        if self_ref
        else "No strong self-referential closure detected."
    )

    return {
        "Anchor Presence":               (has_anchor,        anchor_note),
        "Structural Transfer":           (has_transfer,       transfer_note),
        "Fractal Recursion":             (has_recursion,      recursion_note),
        "Density-to-Sourcing Imbalance": (density_imbalance,  density_note),
        "Self-Referential Closure":      (self_ref,           self_ref_note),
    }


# ─────────────────────────────────────────────
# RECLASSIFICATION LOGIC
# ─────────────────────────────────────────────

def get_reclassification_note(conditions: Dict[str, Tuple[bool, str]]) -> Optional[str]:
    """
    Doctrine: when mandatory conditions fail, reclassify rather than simply
    flagging 'not FCT-D'. Returns the appropriate reclassification guidance.
    """
    has_anchor   = conditions["Anchor Presence"][0]
    has_transfer = conditions["Structural Transfer"][0]
    has_recursion = conditions["Fractal Recursion"][0]

    if not has_anchor:
        return RECLASSIFICATION["no_anchor"]
    if has_anchor and not has_transfer:
        return RECLASSIFICATION["no_transfer"]
    if has_anchor and has_transfer and not has_recursion:
        return RECLASSIFICATION["no_recursion"]
    return None


# ─────────────────────────────────────────────
# FULL DOCUMENT ANALYSIS
# ─────────────────────────────────────────────

def analyze_document(text: str) -> Dict:
    statements  = split_into_statements(text)
    total       = len(statements)
    assessments = [classify_statement(s, i, total) for i, s in enumerate(statements)]
    metrics     = calculate_fct_metrics(text, assessments)
    risk_level, risk_explanation = get_risk_level(metrics["FCT Risk Score"])
    anchor_type, anchor_type_note = detect_anchor_type(text)
    topology, topology_note       = estimate_topology(assessments)
    conditions  = assess_conditions(assessments, metrics)

    mandatory_met = all(conditions[k][0] for k in ["Anchor Presence", "Structural Transfer", "Fractal Recursion"])
    reclassification = None if mandatory_met else get_reclassification_note(conditions)

    # Combined triage matrix lookup
    combined_key = (anchor_type, topology)
    combined_countermeasure = COMBINED_MATRIX.get(combined_key, COUNTERMEASURES[topology])

    if mandatory_met:
        analyst_note = (
            f"FCT-D conditions are present. The artifact exhibits {anchor_type.lower()} anchor "
            f"characteristics within a {topology.lower()} structure. "
            f"Credibility transfer is confirmed across micro, meso, and macro scales. "
            f"Primary structural concern: narrative coherence may exceed evidentiary support. "
            f"Topology-matched countermeasure: {combined_countermeasure}"
        )
    else:
        analyst_note = (
            f"Full FCT-D classification is not supported — one or more mandatory conditions are unmet. "
            f"{reclassification or 'Treat as structural concern requiring further analyst review.'}"
        )

    return {
        "statements":            assessments,
        "metrics":               metrics,
        "risk_level":            risk_level,
        "risk_explanation":      risk_explanation,
        "anchor_type":           anchor_type,
        "anchor_type_note":      anchor_type_note,
        "topology":              topology,
        "topology_note":         topology_note,
        "conditions":            conditions,
        "mandatory_met":         mandatory_met,
        "reclassification":      reclassification,
        "countermeasure":        COUNTERMEASURES[topology],
        "combined_countermeasure": combined_countermeasure,
        "analyst_note":          analyst_note,
    }


# ─────────────────────────────────────────────
# ESCALATION ANALYSIS (Node Chain)
# ─────────────────────────────────────────────

def run_escalation_analysis(chain: List[StatementAssessment]) -> Dict:
    """Analyze a manually-built node chain for FCT patterns."""
    counts = Counter(a.node_code for a in chain)
    total  = len(chain)

    # Check for A→C or A→I transitions
    transitions = []
    for i in range(len(chain) - 1):
        pair = (chain[i].node_code, chain[i + 1].node_code)
        transitions.append(pair)

    structural_transitions = [t for t in transitions if t[0] in ("A", "E") and t[1] in ("C", "I")]
    escalation_ratio = len(structural_transitions) / max(len(transitions), 1)

    risk_flags = []
    if counts.get("I", 0) > counts.get("A", 0):
        risk_flags.append("Inferences outnumber Anchors — high structural risk.")
    if counts.get("C", 0) + counts.get("I", 0) > counts.get("A", 0) + counts.get("E", 0):
        risk_flags.append("Interpretive nodes outnumber evidence nodes — credibility likely structural.")
    if escalation_ratio > 0.5:
        risk_flags.append(f"High escalation rate ({escalation_ratio:.0%}) — majority of transitions move from evidence to interpretation.")

    dominant = max(counts, key=counts.get) if counts else "E"

    return {
        "counts":          dict(counts),
        "transitions":     transitions,
        "structural_transitions": structural_transitions,
        "escalation_ratio": round(escalation_ratio, 2),
        "risk_flags":      risk_flags,
        "dominant_node":   dominant,
        "chain_length":    total,
    }


# ─────────────────────────────────────────────
# UI HELPERS
# ─────────────────────────────────────────────

RISK_COLORS = {
    "Low":      "#2ecc71",
    "Moderate": "#f39c12",
    "High":     "#e67e22",
    "Critical": "#e74c3c",
}

NODE_COLORS = {
    "A": "#2980b9",
    "E": "#27ae60",
    "C": "#e67e22",
    "I": "#c0392b",
}

def render_condition(name: str, result: Tuple[bool, str], mode: str):
    passed, explanation = result
    is_mandatory = name in ("Anchor Presence", "Structural Transfer", "Fractal Recursion")
    icon = "✅" if passed else ("❌" if is_mandatory else "⚠️")
    badge = "**[MANDATORY]**" if is_mandatory else "*[Confirmatory]*"
    st.markdown(f"{icon} **{name}** {badge}")
    if mode == "Junior / Trainee Analyst":
        st.caption(explanation)
    else:
        if not passed:
            st.caption(explanation)


def render_reference_tab(mode: str):
    st.subheader("FCT-D Field Reference")
    st.info("FCT-D assesses structural credibility dynamics. It does not determine truth, intent, guilt, or deception.")

    st.markdown("---")
    st.markdown("### ⚡ 10-Second Analyst Method")
    st.markdown("""
> **Step 1 — Find the anchor.** What is the single most credible or emotionally salient claim in this document? Can you verify it independently right now?

> **Step 2 — Check the transition.** Does the document move from that anchor into interpretation without sourcing? Look for the Event→Claim transition.

> **Step 3 — Test the bottom.** Does the conclusion (the inference) depend on what came before, or could it stand alone? If it collapses without the anchor, the credibility is structural.

> **Field Rule:** *If the top of the narrative feels stronger than the bottom supports — likely FCT. Coherence is not evidence. Confidence is not proof.*
""")

    st.markdown("---")
    st.markdown("### Credibility Ladder")
    ladder_data = []
    for code, v in NODE_DEFINITIONS.items():
        ladder_data.append({
            "Code": code,
            "Node": v["label"],
            "Meaning": v["meaning"],
            "Risk": v["risk"],
            "Field Test": v["field_test"],
        })
    st.dataframe(pd.DataFrame(ladder_data), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("### Mandatory Conditions")
    st.markdown("""
| Condition | Definition | Notes |
|---|---|---|
| **Anchor Presence** | A verifiable, semi-verifiable, or emotionally salient entry point exists. | May be factual, partially factual, or affective. |
| **Structural Transfer** | Credibility spreads through narrative design rather than explicit evidence. | Implied relationships exceed sourced relationships. |
| **Fractal Recursion** | The credibility-transfer pattern repeats across micro, meso, and macro levels. | **LOAD-BEARING CONDITION.** Absence → reclassify as Narrative Cascade or Credibility Laundering. |
""")

    st.markdown("---")
    st.markdown("### Detection Criteria")
    st.markdown("""
| # | Criterion | Type |
|---|---|---|
| 1 | Anchor Identification | **MANDATORY** |
| 2 | Structural Transfer Detection | **MANDATORY** |
| 3 | Fractal Recursion Confirmation | **MANDATORY** |
| 4 | Density-to-Sourcing Imbalance | Confirmatory |
| 5 | Self-Referential Closure | Confirmatory |
""")

    st.markdown("---")
    st.markdown("### Reclassification Paths")
    st.markdown("""
| Condition Absent | Reclassify As |
|---|---|
| Anchor Presence | Unsourced speculation / weak narrative |
| Structural Transfer (anchor present) | Well-sourced reporting / simple information |
| Fractal Recursion (anchor + transfer present) | **Narrative Cascade** (temporal) or **Credibility Laundering** (proximity-based) |
""")

    st.markdown("---")
    st.markdown("### Combined Triage Matrix (Anchor Type × Topology)")
    matrix_data = []
    for (atype, topo), guidance in COMBINED_MATRIX.items():
        matrix_data.append({"Anchor Type": atype, "Topology": topo, "Countermeasure": guidance})
    st.dataframe(pd.DataFrame(matrix_data), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("### Topology Countermeasures (Standalone)")
    topo_df = pd.DataFrame([
        {"Topology": k, "Description": TOPOLOGY_GUIDANCE[k], "Countermeasure": COUNTERMEASURES[k]}
        for k in TOPOLOGY_GUIDANCE
    ])
    st.dataframe(topo_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("### Distinction from Adjacent Concepts")
    st.markdown("""
| Adjacent Concept | How It Works | How FCT-D Differs |
|---|---|---|
| **Credibility Laundering** | Association-based legitimacy transfer via proximity to trusted source. | FCT-D is structure-based and recursively reinforced. Laundering lacks multi-scale repetition. |
| **Narrative Cascade** | Sequential belief expansion over time. Story spreads node to node. | Cascade is temporal. FCT-D is structural and simultaneous — operates within a single artifact. |
| **Cognitive Overload** | Volume-driven reduction in analytic scrutiny. | Overload is an outcome. FCT-D is the mechanism that engineers that overload. |
| **Apophenia** | Observer-side cognitive bias to perceive patterns in random data. | Apophenia is observer-side. FCT-D is artifact-side engineered structure that exploits that bias. |
""")


# ─────────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────────

st.title("FCT-D Analyst Workbench")
st.caption("Fractal Credibility Transfer | Document Variant | Structural Credibility Triage | Kevin M. Hollenbeck, April 2026")

st.warning(
    "**Scope Limitation:** This tool is a structural diagnostic instrument. It does not determine whether individual "
    "claims are true or false, and it does not assess intent or deception. FCT conditions can be present in "
    "documents that are factually accurate. A finding of FCT risk is an assessment of structural mechanics, "
    "not a judgment of veracity. High-stakes use requires corroboration."
)

# Sidebar
mode = st.sidebar.radio("Analyst Mode", ["Experienced Analyst", "Junior / Trainee Analyst"])
st.sidebar.markdown("---")
st.sidebar.markdown("### Accepted Inputs")
st.sidebar.markdown("Paste text or upload `.txt`, `.docx`, or `.pdf`.")
st.sidebar.markdown("---")
st.sidebar.markdown("### Node Quick Reference")
for code, v in NODE_DEFINITIONS.items():
    color = NODE_COLORS[code]
    st.sidebar.markdown(
        f"<span style='color:{color};font-weight:bold'>{code} — {v['label']}</span>: {v['meaning']}",
        unsafe_allow_html=True
    )
st.sidebar.markdown("---")
st.sidebar.caption("Rule-based heuristic engine. Designed for demonstration, OSINT triage, and analytic training. Not formal IC doctrine.")

# Tabs
main_tab, node_tab, scoring_tab, reference_tab = st.tabs([
    "📄 Document Triage", "🔬 Node Classifier", "📊 Scoring Layer", "📚 Field Reference"
])

# ──────────────────────────────────────────────────────
# TAB 1: DOCUMENT TRIAGE
# ──────────────────────────────────────────────────────
with main_tab:
    left, right = st.columns([1.2, 0.8])

    with left:
        st.subheader("Input Document")
        uploaded = st.file_uploader("Upload document", type=["txt", "docx", "pdf"])
        uploaded_text = load_uploaded_text(uploaded) if uploaded else ""
        text_input = st.text_area(
            "Paste text for FCT-D evaluation",
            value=uploaded_text,
            height=360,
            placeholder="Paste article, assessment, social thread, policy memo, or OSINT artifact here...",
        )
        run = st.button("▶ Run FCT-D Analysis", type="primary", use_container_width=True)

    with right:
        st.subheader("Doctrine Reminder")
        st.markdown("**FCT-D asks:** Is this document's perceived credibility earned through evidence, or constructed through structure?")
        st.markdown("**Three Mandatory Conditions (ALL required):**")
        st.markdown("- ⚓ Anchor Presence\n- 🔀 Structural Transfer\n- 🔁 Fractal Recursion (load-bearing)")
        st.markdown("**Primary Failure Point:**")
        st.info("The transition from **Event → Claim**. This is where credibility first transfers structurally rather than evidentially.")
        if mode == "Junior / Trainee Analyst":
            st.markdown("**Triage Field Rule:**")
            st.success("*If the top of the narrative feels stronger than the bottom supports — likely FCT. Coherence is not evidence. Confidence is not proof.*")

    if run:
        if not text_input.strip():
            st.error("Please paste or upload text before running analysis.")
        else:
            st.session_state["last_result"] = analyze_document(text_input)
            st.session_state["last_text"]   = text_input

    if "last_result" in st.session_state:
        result = st.session_state["last_result"]

        st.markdown("---")
        st.subheader("FCT-D Assessment Output")

        # Top metrics
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("FCT Risk Score", result["metrics"]["FCT Risk Score"])
        m2.metric("Risk Level", result["risk_level"])
        m3.metric("FCT-D Confirmed", "✅ YES" if result["mandatory_met"] else "❌ NO")
        m4.metric("Anchor Type", result["anchor_type"])
        m5.metric("Topology", result["topology"])
        st.caption(result["risk_explanation"])

        # Conditions + Classification
        c1, c2 = st.columns([1.1, 0.9])

        with c1:
            st.markdown("### Criteria Assessment")
            for name, condition in result["conditions"].items():
                render_condition(name, condition, mode)

        with c2:
            st.markdown("### Classification")
            st.markdown(f"**Anchor Type:** {result['anchor_type']}")
            st.caption(result["anchor_type_note"])
            st.markdown(f"**Topology:** {result['topology']}")
            st.caption(result["topology_note"])

            st.markdown("### Topology Countermeasure")
            st.info(result["countermeasure"])

        # Combined triage matrix result
        st.markdown("### Combined Countermeasure (Anchor Type × Topology)")
        combined_key = (result["anchor_type"], result["topology"])
        st.success(f"**{result['anchor_type']} + {result['topology']}:** {result['combined_countermeasure']}")

        # Analyst note / reclassification
        st.markdown("### Analyst Note")
        if result["mandatory_met"]:
            st.warning(result["analyst_note"])
        else:
            st.error(result["analyst_note"])
            if result["reclassification"]:
                st.markdown("**Reclassification Guidance:**")
                st.info(result["reclassification"])

        if mode == "Junior / Trainee Analyst":
            st.markdown("---")
            st.info(
                "**Trainee Reminder:** A high FCT Risk Score does not mean the document is false. "
                "It means the structure may be doing more credibility work than the evidence supports. "
                "FCT conditions can be present in factually accurate material."
            )

        # Node classification table
        st.markdown("### Node Classification")
        rows = []
        for a in result["statements"]:
            rows.append({
                "Scale":      a.section.capitalize(),
                "Code":       a.node_code,
                "Type":       a.node_type,
                "Confidence": a.confidence,
                "Statement":  a.statement[:120] + ("…" if len(a.statement) > 120 else ""),
                "Signal":     a.signal,
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # Node distribution
        st.markdown("### Node Distribution by Scale")
        scale_data = []
        for scale in ["micro", "meso", "macro"]:
            scale_nodes = [a.node_code for a in result["statements"] if a.section == scale]
            sc = Counter(scale_nodes)
            scale_data.append({
                "Scale":       scale.capitalize(),
                "Anchors (A)": sc.get("A", 0),
                "Events (E)":  sc.get("E", 0),
                "Claims (C)":  sc.get("C", 0),
                "Inferences (I)": sc.get("I", 0),
                "Escalation Pattern": "✅ Present" if (sc.get("C", 0) + sc.get("I", 0)) >= (sc.get("A", 0) + sc.get("E", 0)) else "—",
            })
        st.dataframe(pd.DataFrame(scale_data), use_container_width=True, hide_index=True)
        if mode == "Junior / Trainee Analyst":
            st.caption("Fractal Recursion requires the escalation pattern to be present in ALL three scales simultaneously.")

        # Metric breakdown
        with st.expander("📐 Metric Breakdown"):
            metrics = result["metrics"]
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("UER (×0.40)", metrics["UER"], help="Unsupported Edge Ratio: interpretive nodes relative to sourced support.")
            col2.metric("Drop-off (×0.25)", metrics["Drop-off"], help="How far interpretive density exceeds anchor + source density.")
            col3.metric("Connectivity (×0.20)", metrics["Connectivity"], help="Density of the interpretive claim network.")
            col4.metric("Centrality (×0.15)", metrics["Centrality"], help="Interpretive load per anchor node.")
            st.caption(f"Sources detected: {metrics['Source Count']} | Formula: Score = (0.40 × UER) + (0.25 × Drop-off) + (0.20 × Connectivity) + (0.15 × Centrality)")


# ──────────────────────────────────────────────────────
# TAB 2: NODE CLASSIFIER (with running chain)
# ──────────────────────────────────────────────────────
with node_tab:
    st.subheader("Node Classifier")
    st.markdown("Classify individual statements and build a chain for escalation analysis.")

    # Initialize chain in session state
    if "node_chain" not in st.session_state:
        st.session_state["node_chain"] = []

    col_input, col_result = st.columns([1.2, 0.8])

    with col_input:
        statement = st.text_area("Enter one statement", height=140, key="node_input")
        btn_col1, btn_col2 = st.columns(2)
        classify_btn = btn_col1.button("🔬 Classify Statement", use_container_width=True)
        add_to_chain = btn_col2.button("➕ Classify & Add to Chain", use_container_width=True)

    with col_result:
        if classify_btn or add_to_chain:
            if not statement.strip():
                st.error("Enter a statement first.")
            else:
                a = classify_statement(statement.strip())
                st.metric("Node Type", f"{a.node_code} — {a.node_type}")
                st.metric("Confidence", a.confidence)
                st.markdown(f"**Rationale:** {a.rationale}")
                st.markdown(f"**Signal:** {a.signal}")

                if mode == "Junior / Trainee Analyst":
                    st.info(f"**Field Test:** {NODE_DEFINITIONS[a.node_code]['field_test']}")
                    st.caption(f"**Risk Level:** {NODE_DEFINITIONS[a.node_code]['risk']}")

                if add_to_chain:
                    st.session_state["node_chain"].append(a)
                    st.success(f"Added to chain. Chain length: {len(st.session_state['node_chain'])}")

    # Running chain display
    st.markdown("---")
    st.markdown("### Running Node Chain")

    if st.session_state["node_chain"]:
        chain = st.session_state["node_chain"]

        # Visual chain
        chain_display = " → ".join([
            f"**:{('blue' if a.node_code == 'A' else 'green' if a.node_code == 'E' else 'orange' if a.node_code == 'C' else 'red')}[{a.node_code}]**"
            for a in chain
        ])
        st.markdown(chain_display)

        # Chain table
        chain_rows = [{
            "#":          i + 1,
            "Code":       a.node_code,
            "Type":       a.node_type,
            "Confidence": a.confidence,
            "Statement":  a.statement[:100] + ("…" if len(a.statement) > 100 else ""),
        } for i, a in enumerate(chain)]
        st.dataframe(pd.DataFrame(chain_rows), use_container_width=True, hide_index=True)

        btn_c1, btn_c2 = st.columns(2)

        with btn_c1:
            if st.button("🔍 Run Escalation Analysis", use_container_width=True):
                if len(chain) < 2:
                    st.warning("Add at least 2 statements to run escalation analysis.")
                else:
                    esc = run_escalation_analysis(chain)
                    st.markdown("#### Escalation Analysis Results")

                    e1, e2, e3 = st.columns(3)
                    e1.metric("Chain Length", esc["chain_length"])
                    e2.metric("Escalation Rate", f"{esc['escalation_ratio']:.0%}")
                    e3.metric("Dominant Node", esc["dominant_node"])

                    if esc["risk_flags"]:
                        st.markdown("**Risk Flags:**")
                        for flag in esc["risk_flags"]:
                            st.warning(f"⚠️ {flag}")
                    else:
                        st.success("No significant escalation risk flags detected in this chain.")

                    if esc["structural_transitions"]:
                        st.markdown(f"**Structural Transitions (Evidence → Interpretation):** {len(esc['structural_transitions'])} detected")
                        for t in esc["structural_transitions"]:
                            st.caption(f"  {t[0]} → {t[1]}: {NODE_DEFINITIONS[t[0]]['label']} → {NODE_DEFINITIONS[t[1]]['label']}")

                    if mode == "Junior / Trainee Analyst":
                        st.info("Escalation analysis shows how credibility moves through your chain. A high rate of Evidence→Interpretation transitions suggests structural credibility risk.")

        with btn_c2:
            if st.button("🗑️ Clear Chain", use_container_width=True):
                st.session_state["node_chain"] = []
                st.rerun()
    else:
        st.caption("No statements in chain yet. Classify statements and click 'Classify & Add to Chain' to build.")


# ──────────────────────────────────────────────────────
# TAB 3: MANUAL SCORING LAYER
# ──────────────────────────────────────────────────────
with scoring_tab:
    st.subheader("Manual FCT Risk Score Calculator")
    st.caption("Formula: **Score = (0.40 × UER) + (0.25 × Drop-off) + (0.20 × Connectivity) + (0.15 × Centrality)**")

    if mode == "Junior / Trainee Analyst":
        with st.expander("ℹ️ What do these inputs mean?"):
            st.markdown("""
- **UER (Unsupported Edge Ratio):** How many of the document's interpretive moves (claims, inferences) lack explicit sourcing? 0 = all sourced, 1 = none sourced.
- **Drop-off:** How far does the interpretive density exceed the anchor and source density? High drop-off means the bottom of the document rests on much thinner evidence than the top suggests.
- **Connectivity:** How interconnected is the interpretive claim network? More interconnected = more structural reinforcement = higher risk.
- **Centrality:** How much interpretive work are the anchors doing? High centrality = few anchors carrying many claims = structural risk.
""")

    c1, c2 = st.columns(2)
    with c1:
        uer  = st.slider("Unsupported Edge Ratio (UER)", 0.0, 1.0, 0.40, 0.01, help="Unsupported interpretive edges / total edges")
        drop = st.slider("Drop-off", 0.0, 1.0, 0.35, 0.01, help="Interpretive density minus anchor+source density")
    with c2:
        conn = st.slider("Connectivity", 0.0, 1.0, 0.40, 0.01, help="Claim network density")
        cent = st.slider("Centrality", 0.0, 1.0, 0.35, 0.01, help="Interpretive load per anchor")

    manual_score = round((0.40 * uer) + (0.25 * drop) + (0.20 * conn) + (0.15 * cent), 2)
    level, expl  = get_risk_level(manual_score)

    r1, r2 = st.columns(2)
    r1.metric("Manual FCT Risk Score", manual_score)
    r2.metric("Risk Level", level)
    st.caption(expl)

    # Breakdown bar
    st.markdown("#### Score Contribution Breakdown")
    contrib_data = {
        "Component":    ["UER (×0.40)", "Drop-off (×0.25)", "Connectivity (×0.20)", "Centrality (×0.15)"],
        "Raw Value":    [uer, drop, conn, cent],
        "Contribution": [round(0.40*uer, 3), round(0.25*drop, 3), round(0.20*conn, 3), round(0.15*cent, 3)],
    }
    st.dataframe(pd.DataFrame(contrib_data), use_container_width=True, hide_index=True)

    if mode == "Junior / Trainee Analyst":
        st.info(
            "The FCT Risk Score formalizes analyst observations. Treat scores as calibrated assessments "
            "— one input in the triage process, not a definitive finding. High-stakes applications require corroboration."
        )


# ──────────────────────────────────────────────────────
# TAB 4: FIELD REFERENCE
# ──────────────────────────────────────────────────────
with reference_tab:
    render_reference_tab(mode)
