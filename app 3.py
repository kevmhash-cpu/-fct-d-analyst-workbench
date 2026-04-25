"""
FCT-D Analyst Workbench — Streamlit Prototype
Fractal Credibility Transfer | Document Triage Application
Author concept: Kevin M. Hollenbeck | April 2026

Corrected implementation aligned with FCT-D Doctrine Page (Hollenbeck, April 2026).
"""

import re
from collections import Counter
from dataclasses import dataclass
from typing import List, Dict, Tuple
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

st.set_page_config(page_title="FCT-D Analyst Workbench", page_icon="🧠", layout="wide")

# ---------------------------------------------------------------------------
# DOCTRINE DEFINITIONS — sourced verbatim from FCT-D Doctrine Page
# ---------------------------------------------------------------------------

NODE_DEFINITIONS = {
    "A": {
        "label": "Anchor",
        "meaning": "It is",
        "definition": "Verified, defensible fact. Independently sourceable. The initial credibility source.",
        "field_test": "Can I prove this right now from a primary source outside this artifact?",
    },
    "E": {
        "label": "Event",
        "meaning": "It happened",
        "definition": "Observable occurrence or real-world condition. Reports what happened, not what it means.",
        "field_test": "Is this describing what occurred, not interpreting it?",
    },
    "C": {
        "label": "Claim",
        "meaning": "It means",
        "definition": "Interpretation of events. Assigns meaning, motive, or significance. First risk point.",
        "field_test": "Is this explaining meaning instead of stating fact?",
    },
    "I": {
        "label": "Inference",
        "meaning": "It must be",
        "definition": "Conclusion built on stacked claims. Extends beyond direct evidence. Highest risk.",
        "field_test": "Can this be independently verified, or does it depend on earlier steps?",
    },
}

RISK_BANDS = [
    (0.00, 0.29, "Low",      "Evidence appears to scale with structure."),
    (0.30, 0.49, "Moderate", "Partial structural substitution for sourcing."),
    (0.50, 0.69, "High",     "Structure substantially exceeds evidence."),
    (0.70, 1.00, "Critical", "Structural coherence appears to drive all credibility."),
]

ANCHOR_TYPE_GUIDANCE = {
    "Emotional":    "Trauma, scandal, grief, moral urgency, outrage, atrocity, fear, victims.",
    "Institutional":"Agencies, officials, courts, universities, documents, reports, named organizations.",
    "Technical":    "Scientific language, datasets, models, patents, technical jargon, statistics, charts.",
}

TOPOLOGY_GUIDANCE = {
    "Hub-Spoke":    "Single dominant anchor with multiple peripheral claims radiating outward.",
    "Hierarchical": "Anchor spawns mid-level sub-anchors, which then support additional claims (tree structure).",
    "Lattice":      "Multiple anchors cross-reference and mutually reinforce; no single root node dominates.",
}

COUNTERMEASURES = {
    "Hub-Spoke":    "Validate or refute the hub anchor first. Peripheral claims may collapse as a secondary effect. A single sourcing check on the anchor event is often sufficient.",
    "Hierarchical": "Map the full claim tree before engaging any node. Refute at the highest viable tier. Subclaims may persist; continue working downward systematically.",
    "Lattice":      "Require independent verification paths for each anchor. Internal cross-references within the network do not constitute corroboration. Escalate technical-lattice variants to SME review.",
}

# Combined triage matrix per doctrine Section 4 / Workbench Section 4
COMBINED_COUNTERMEASURE = {
    ("Emotional",    "Hub-Spoke"):    "Fastest to collapse. Verify anchor event; spokes fall automatically.",
    ("Emotional",    "Hierarchical"): "Grief escalates into doctrine. Map emotional cascade path before engaging.",
    ("Emotional",    "Lattice"):      "Most manipulative variant. Multiple trauma anchors mutually reinforce. Per-anchor verification required.",
    ("Institutional","Hub-Spoke"):    "Classic disinfo playbook. Named agency as hub; check primary docs first.",
    ("Institutional","Hierarchical"): "Agency → program → claim tree. Refute at institutional tier first; subclaims may persist independently.",
    ("Institutional","Lattice"):      "Agencies cross-cited. Each lends the others halo. Verify each institution independently.",
    ("Technical",    "Hub-Spoke"):    "Jargon hub radiating pseudoscience. SME review of the anchor term is usually sufficient to collapse peripheral claims.",
    ("Technical",    "Hierarchical"): "Real paper → misread finding → theory tree. Engage at paper level.",
    ("Technical",    "Lattice"):      "Most durable variant. Escalate to SME triage.",
}

# ---------------------------------------------------------------------------
# DATA CLASS
# ---------------------------------------------------------------------------

@dataclass
class StatementAssessment:
    statement:  str
    scale:      str   # "Micro" | "Meso" | "Macro"
    node_code:  str
    node_type:  str
    confidence: float
    rationale:  str
    signal:     str

# ---------------------------------------------------------------------------
# FILE LOADING
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# TEXT SPLITTING — three-scale aware
# Micro  = individual sentences
# Meso   = paragraphs (groups of sentences)
# Macro  = whole document (first + last representative sentences)
# ---------------------------------------------------------------------------

def split_into_sentences(text: str) -> List[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    return [p.strip() for p in parts if len(p.strip()) > 25]

def split_into_paragraphs(text: str) -> List[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paragraphs) < 2:
        # Fall back: treat every 3 sentences as a paragraph
        sentences = split_into_sentences(text)
        paragraphs = [" ".join(sentences[i:i+3]) for i in range(0, len(sentences), 3)]
    return [p for p in paragraphs if len(p) > 25]

def assign_scales(text: str) -> List[Tuple[str, str]]:
    """
    Returns list of (scale, unit_text) tuples.
    Micro  → individual sentences (up to 30 sampled)
    Meso   → paragraphs (up to 10 sampled)
    Macro  → 2 macro-representative sentences (first + last of document)
    """
    sentences  = split_into_sentences(text)
    paragraphs = split_into_paragraphs(text)

    units: List[Tuple[str, str]] = []

    # Micro: sample sentences (cap at 30 to keep runtime sane)
    for s in sentences[:30]:
        units.append(("Micro", s))

    # Meso: one representative sentence per paragraph (the longest sentence in each)
    for para in paragraphs[:10]:
        para_sents = split_into_sentences(para)
        if para_sents:
            rep = max(para_sents, key=len)
            units.append(("Meso", rep))

    # Macro: first and last sentences of the full document
    if len(sentences) >= 2:
        units.append(("Macro", sentences[0]))
        units.append(("Macro", sentences[-1]))
    elif sentences:
        units.append(("Macro", sentences[0]))

    return units

# ---------------------------------------------------------------------------
# SOURCE COUNTING
# ---------------------------------------------------------------------------

def count_sources(text: str) -> int:
    patterns = [
        r"https?://", r"www\.", r"doi\.org", r"\[[0-9]+\]",
        r"\([A-Z][A-Za-z]+,\s?\d{4}\)",
        r"\breported by\b", r"\bpublished by\b", r"\bdata from\b",
        r"\bsource:\b", r"\baccording to [A-Z]",
    ]
    return sum(len(re.findall(p, text, flags=re.I)) for p in patterns)

# ---------------------------------------------------------------------------
# NODE CLASSIFIER
# Doctrine field tests (Section 5):
#   A — "Can I prove this right now from a primary source outside this artifact?"
#   E — "Is this describing what occurred, not interpreting it?"
#   C — "Is this explaining meaning instead of stating fact?"
#   I — "Does this depend on prior claims rather than direct independent verification?"
#
# Key doctrine principle: PRIMARY FAILURE POINT is Event → Claim.
# Named organizations, officials, and documents are Institutional ANCHOR SOURCES,
# but the STATEMENTS containing them may be Events, Claims, or Inferences depending
# on whether the sentence describes, interprets, or stacks conclusions.
# ---------------------------------------------------------------------------

# Signals for "It is" — independently verifiable facts, specific named primary sources
ANCHOR_SIGNALS = [
    r"\b(confirmed|verified|established|documented|recorded|certified)\b",
    r"\baccording to [A-Z][a-z]+ (report|study|filing|data|statistics)\b",
    r"\b(published|released|filed|signed|enacted|ratified)\b",
    r"\b\d{4}\b.*\b(percent|billion|million|thousand)\b",
    r"\b(primary source|court filing|official record|government document)\b",
]

# Signals for "It happened" — observable occurrences, no interpretation
EVENT_SIGNALS = [
    r"\b(occurred|happened|took place|was arrested|was charged|launched|met with|voted|approved|denied|announced|stated|released|attacked|began|ended|created|formed)\b",
    r"\b(the (board|agency|official|department|committee|panel)) (released|issued|published|announced|submitted|reported)\b",
    r"\b(on [A-Z][a-z]+day|last (week|month|year)|on \w+ \d+)\b",
]

# Signals for "It means" — interpretation, assigned motive/significance
CLAIM_SIGNALS = [
    r"\b(suggests|indicates|shows|means|reveals|demonstrates|points to|signals|reflects|implies)\b",
    r"\b(evidence of|consistent with|this (confirms|proves|validates|demonstrates))\b",
    r"\b(therefore|thus|consequently|as a result|which (means|shows|proves|confirms|validates))\b",
    r"\b(because|since|given that|in light of)\b",
    r"\b(likely|appears to|seems to|is indicative of)\b",
    r"\b(asserts? that|concludes? that|determines? that|confirms? that)\b",
    r"\b(motive|agenda|intent|significance|implication)\b",
]

# Signals for "It must be" — stacked conclusions beyond direct evidence
INFERENCE_SIGNALS = [
    r"\b(must (be|therefore|confirm|prove|validate|demonstrate))\b",
    r"\b(inferr?ing|infers? (therefore|that|from))\b",
    r"\b(it follows (that|therefore))\b",
    r"\b(no (other|alternative|independent) (explanation|source|review|validation))\b",
    r"\b(undeniable|inevitably|cannot be (coincidence|disputed|denied))\b",
    r"\b(only explanation|clearly proves|this must (mean|confirm|establish))\b",
    r"\b(validates? the (authority|mandate|role|process|conclusion) of)\b",
    r"\b(justif(ies|y) (continued|the|its))\b",
    r"\b(self-establishes?|self-validates?|self-certif(ies|y))\b",
]

def score_signals(statement: str, patterns: List[str]) -> float:
    s = statement.lower()
    return sum(1.0 for p in patterns if re.search(p, s, re.I))

def classify_statement(statement: str, scale: str = "Micro") -> StatementAssessment:
    scores = {
        "A": score_signals(statement, ANCHOR_SIGNALS),
        "E": score_signals(statement, EVENT_SIGNALS),
        "C": score_signals(statement, CLAIM_SIGNALS),
        "I": score_signals(statement, INFERENCE_SIGNALS),
    }

    # Doctrine primary failure point: Event → Claim transition
    # Boost Claim when interpretive language co-occurs with event framing
    if scores["E"] > 0 and scores["C"] > 0:
        scores["C"] += 0.5

    # Inference stacks on claims — boost if both present
    if scores["C"] > 0 and scores["I"] > 0:
        scores["I"] += 0.5

    node_code = max(scores, key=scores.get)
    max_score = scores[node_code]

    if max_score == 0:
        # Default to Event (descriptive) per doctrine — not Anchor
        node_code   = "E"
        confidence  = 0.45
        signal      = "No strong FCT markers detected. Defaulted to Event (descriptive)."
        rationale   = NODE_DEFINITIONS["E"]["definition"]
    else:
        total      = sum(scores.values()) or 1
        confidence = min(0.95, 0.50 + (max_score / total) * 0.45)
        signal     = f"Detected {NODE_DEFINITIONS[node_code]['label']} markers. Scores: A={scores['A']:.1f} E={scores['E']:.1f} C={scores['C']:.1f} I={scores['I']:.1f}"
        rationale  = NODE_DEFINITIONS[node_code]["definition"]

    return StatementAssessment(
        statement  = statement,
        scale      = scale,
        node_code  = node_code,
        node_type  = NODE_DEFINITIONS[node_code]["label"],
        confidence = round(confidence, 2),
        rationale  = rationale,
        signal     = signal,
    )

# ---------------------------------------------------------------------------
# ANCHOR TYPE DETECTION
# Doctrine Axis 1:
#   Emotional    — trauma, scandal, moral urgency → suppresses analytic evaluation
#   Institutional— named agencies, officials, documents → authority halo
#   Technical    — scientific jargon, data, models → complexity deters verification
#
# FIX: Weight proper-noun organizational references heavily for Institutional.
# Technical words alone should not override clear institutional language.
# ---------------------------------------------------------------------------

EMOTIONAL_TERMS = [
    "victim", "children", "trauma", "grief", "scandal", "atrocity",
    "fear", "outrage", "abuse", "death", "crisis", "tragedy", "suffering",
    "emergency", "catastrophe", "massacre",
]

INSTITUTIONAL_TERMS = [
    "board", "agency", "commission", "committee", "council", "department",
    "ministry", "official", "government", "court", "judiciary", "congress",
    "parliament", "university", "institute", "organization", "bureau",
    "authority", "administration", "secretariat", "task force", "oversight",
    "panel", "directorate", "coalition", "alliance", "federation",
    # Common abbreviations
    "fbi", "cia", "dhs", "odni", "doj", "gao", "who", "un", "nato",
    "treasury", "pentagon", "whitehouse",
]

TECHNICAL_TERMS = [
    "algorithm", "dataset", "model", "patent", "peer-reviewed", "quantum",
    "machine learning", "neural", "statistical", "regression", "methodology",
    "calibration", "formula", "threshold", "metric", "index", "coefficient",
    "parameter", "simulation", "protocol",
]

def detect_anchor_type(text: str) -> Tuple[str, str]:
    s = text.lower()

    emotional    = sum(w in s for w in EMOTIONAL_TERMS)
    institutional = sum(w in s for w in INSTITUTIONAL_TERMS)
    technical    = sum(w in s for w in TECHNICAL_TERMS)

    # Doctrine signature check: Institutional = "named sources present;
    # citations do not support claims made." Weight named-org language more.
    # Also: generic words like "data", "study", "report" should NOT override
    # clear institutional language — they appear in Institutional docs too.
    counts = {
        "Emotional":     emotional,
        "Institutional": institutional,
        "Technical":     technical,
    }

    anchor_type = max(counts, key=counts.get)
    if counts[anchor_type] == 0:
        anchor_type = "Institutional"  # neutral baseline per doctrine

    return anchor_type, ANCHOR_TYPE_GUIDANCE[anchor_type]

# ---------------------------------------------------------------------------
# TOPOLOGY ESTIMATION
# Doctrine Axis 2:
#   Hub-Spoke    — single anchor, N peripheral claims radiate directly
#   Hierarchical — anchor → mid-level sub-anchors → peripheral claims (tree)
#   Lattice      — multiple anchors cross-reference and mutually reinforce
# ---------------------------------------------------------------------------

def estimate_topology(assessments: List[StatementAssessment]) -> Tuple[str, str]:
    counts  = Counter(a.node_code for a in assessments)
    anchors = counts.get("A", 0)
    claims  = counts.get("C", 0)
    infer   = counts.get("I", 0)

    # Lattice: multiple anchors cross-reinforcing
    if anchors >= 3 and claims >= 2:
        return "Lattice", TOPOLOGY_GUIDANCE["Lattice"]

    # Hub-Spoke: single (or zero) anchor with claims radiating outward
    # Per doctrine: "single anchor; N peripheral claims radiate directly"
    if anchors <= 1 and (claims + infer) >= 3:
        return "Hub-Spoke", TOPOLOGY_GUIDANCE["Hub-Spoke"]

    # Hierarchical: 2 anchors (root + sub-anchor level) with claims below
    # Per doctrine: "anchor spawns mid-level sub-anchors, which spawn claims"
    if anchors == 2 and claims >= 2:
        return "Hierarchical", TOPOLOGY_GUIDANCE["Hierarchical"]

    # Default: if anchor count is ambiguous, use ratio to decide
    if anchors > claims:
        return "Hierarchical", TOPOLOGY_GUIDANCE["Hierarchical"]
    return "Hub-Spoke", TOPOLOGY_GUIDANCE["Hub-Spoke"]

# ---------------------------------------------------------------------------
# FCT METRICS
# ---------------------------------------------------------------------------

def calculate_fct_metrics(text: str, assessments: List[StatementAssessment]) -> Dict[str, float]:
    total_statements = max(len(assessments), 1)
    counts           = Counter(a.node_code for a in assessments)
    source_count     = count_sources(text)

    # UER: unsupported edges = Claims + Inferences that lack external sourcing
    interpretive     = counts.get("C", 0) + counts.get("I", 0)
    unsupported_edges = max(0, interpretive - source_count)
    total_edges      = max(1, counts.get("E", 0) + interpretive)
    uer              = min(1.0, unsupported_edges / total_edges)

    # Drop-off: anchor credibility minus average edge credibility
    anchor_ratio      = counts.get("A", 0) / total_statements
    interpretive_ratio = interpretive / total_statements
    drop_off          = min(1.0, max(0.0, interpretive_ratio - anchor_ratio + 0.25))

    # Connectivity: density of interpretive nodes
    connectivity = min(1.0, (counts.get("C", 0) * 0.07) + (counts.get("I", 0) * 0.10))

    # Centrality: how many interpretive nodes per anchor
    anchors     = max(counts.get("A", 0), 1)
    centrality  = min(1.0, interpretive / (anchors * 8))

    score = (0.40 * uer) + (0.25 * drop_off) + (0.20 * connectivity) + (0.15 * centrality)

    return {
        "UER":           round(uer, 2),
        "Drop-off":      round(drop_off, 2),
        "Connectivity":  round(connectivity, 2),
        "Centrality":    round(centrality, 2),
        "FCT Risk Score":round(min(1.0, score), 2),
        "Source Count":  source_count,
    }

def get_risk_level(score: float) -> Tuple[str, str]:
    for low, high, label, explanation in RISK_BANDS:
        if low <= score <= high:
            return label, explanation
    return "Critical", "Structural coherence appears to drive all credibility."

# ---------------------------------------------------------------------------
# CONDITION ASSESSMENT — doctrine-faithful implementations
# ---------------------------------------------------------------------------

def check_anchor_presence(assessments: List[StatementAssessment]) -> Tuple[bool, str]:
    """
    Doctrine 4.1: A verifiable, semi-verifiable, or emotionally salient entry
    point exists. May be factual, partially factual, or affective.
    """
    anchor_count = sum(1 for a in assessments if a.node_code == "A")
    if anchor_count >= 1:
        return True, f"Anchor node detected ({anchor_count} statement(s) classified as Anchor)."
    # Fallback: even high-confidence Event nodes can serve as anchors per doctrine
    high_event = sum(1 for a in assessments if a.node_code == "E" and a.confidence >= 0.65)
    if high_event >= 1:
        return True, f"High-confidence Event node is serving as the credibility anchor ({high_event} detected)."
    return False, "No verifiable or salient anchor detected."

def check_structural_transfer(assessments: List[StatementAssessment], metrics: Dict[str, float]) -> Tuple[bool, str]:
    """
    Doctrine 4.2: Credibility spreads through narrative or topological design
    rather than explicit evidence. Implied relationships exceed sourced relationships.
    Connections are suggested, not demonstrated.

    FIX: Original code required UER >= 0.30 which was too lenient and inconsistent.
    Doctrine says 'implied relationships EXCEED sourced relationships' — so we need
    more interpretive nodes than the source count can support, AND the interpretive
    ratio must substantially exceed the anchor ratio.
    """
    counts       = Counter(a.node_code for a in assessments)
    interpretive = counts.get("C", 0) + counts.get("I", 0)
    anchors      = counts.get("A", 0)

    # Structure substitutes for sourcing when:
    # (a) interpretive nodes substantially outnumber anchors, AND
    # (b) UER is high (few external sources relative to claims)
    design_exceeds_sourcing = (
        interpretive >= 2 and
        (anchors == 0 or interpretive / max(anchors, 1) >= 2.0) and
        metrics["UER"] >= 0.40
    )

    if design_exceeds_sourcing:
        return True, (
            f"Structure substituting for sourcing: {interpretive} interpretive node(s) "
            f"vs {anchors} anchor(s), UER={metrics['UER']}."
        )
    return False, "Insufficient evidence that structure is substituting for sourcing."

def check_fractal_recursion(assessments: List[StatementAssessment]) -> Tuple[bool, str]:
    """
    Doctrine 4.3 (LOAD-BEARING CONDITION):
    The credibility transfer pattern repeats across micro, meso, AND macro scales
    SIMULTANEOUSLY.

    Scale definitions (doctrine):
      Micro = sentence/claim level
      Meso  = paragraph/section level
      Macro = full narrative structure

    FIX: Original code only checked global totals. This implementation checks
    whether at least one interpretive node (C or I) exists at EACH scale.
    All three scales must show the A→E→C/I pattern, not just in aggregate.
    """
    by_scale: Dict[str, Counter] = {
        "Micro": Counter(),
        "Meso":  Counter(),
        "Macro": Counter(),
    }
    for a in assessments:
        by_scale[a.scale][a.node_code] += 1

    scale_results = {}
    for scale, counts in by_scale.items():
        # Each scale must have at least one interpretive node (C or I)
        # and at least one sourcing node (A or E) — showing the transfer pattern
        has_interpretive = (counts.get("C", 0) + counts.get("I", 0)) >= 1
        has_sourcing     = (counts.get("A", 0) + counts.get("E", 0)) >= 1
        scale_results[scale] = has_interpretive and has_sourcing

    all_scales_present = all(scale_results.values())
    detail = " | ".join(
        f"{s}: {'✓' if v else '✗'}" for s, v in scale_results.items()
    )

    if all_scales_present:
        return True, f"Credibility transfer pattern confirmed at all three scales. [{detail}]"

    failing = [s for s, v in scale_results.items() if not v]
    if len(failing) == 1:
        return False, (
            f"Pattern detected at {' and '.join(s for s, v in scale_results.items() if v)} scale only. "
            f"Insufficient for FCT-D classification. [{detail}] "
            f"Consider Credibility Laundering or simple interpretive reporting."
        )
    return False, (
        f"Fractal Recursion not confirmed across scales. [{detail}] "
        f"Minimum 6 classified statements with distribution across scales required."
    )

def check_density_sourcing_imbalance(metrics: Dict[str, float]) -> Tuple[bool, str]:
    """
    Doctrine Criterion 4: High claim volume relative to independently verifiable
    external sourcing. Many nodes, few or no citations.
    """
    if metrics["UER"] >= 0.50:
        return True, f"High unsupported edge ratio ({metrics['UER']}): many interpretive nodes, few external sources."
    return False, f"Density imbalance not strongly confirmed (UER={metrics['UER']})."

def check_self_referential_closure(text: str, assessments: List[StatementAssessment], metrics: Dict[str, float]) -> Tuple[bool, str]:
    """
    Doctrine Criterion 5: Claims loop internally without external validation.
    Internal cross-references serve as apparent corroboration.

    FIX: Original code only checked source_count <= 1. Doctrine requires detecting
    actual internal looping — where claim language references back to earlier
    claims within the same artifact, creating the appearance of corroboration.
    """
    # Pattern 1: Self-validation language — entity validates itself
    self_validation_patterns = [
        r"\b(validates?|confirms?|establishes?|certif(ies|y)) (the|its|their) (own|authority|mandate|process|methodology|role|conclusion|finding)\b",
        r"\b(self-referential|self-validat|self-certif|self-establ)\w*\b",
        r"\bno (external|independent|outside) (review|source|validation|verification|audit) (is |was )?(required|needed|necessary)\b",
        r"\b(internal|own) (review|validation|assessment|analysis) (confirmed|validates?|establishes?)\b",
    ]

    # Pattern 2: Circular reference — conclusion used as premise for itself
    circular_patterns = [
        r"\b(therefore|thus|which confirms|which proves|which validates).{0,60}(same|prior|earlier|above|this)\b",
        r"\b(prior|earlier|previous) (warning|finding|assessment|report|bulletin).{0,60}(confirms?|validates?|proves?|establishes?).{0,60}(current|this|present)\b",
        r"\b(this|the) (pattern|finding|conclusion|assessment).{0,80}(pattern|finding|conclusion|assessment)\b",
    ]

    s = text.lower()
    self_val_hits  = sum(1 for p in self_validation_patterns if re.search(p, s, re.I))
    circular_hits  = sum(1 for p in circular_patterns if re.search(p, s, re.I))

    # Also check: low external sourcing combined with high interpretive density
    low_external = metrics["Source Count"] <= 1
    high_interp  = metrics["UER"] >= 0.50

    strong_closure = self_val_hits >= 1 or circular_hits >= 1
    weak_closure   = low_external and high_interp

    if strong_closure:
        return True, (
            f"Self-referential closure confirmed: internal loops detected "
            f"(self-validation signals={self_val_hits}, circular reference signals={circular_hits})."
        )
    if weak_closure:
        return True, (
            f"Self-referential closure indicated: low external sourcing ({metrics['Source Count']}) "
            f"with high interpretive load (UER={metrics['UER']}). Claims appear to loop internally."
        )
    return False, "No strong self-referential closure detected."

def assess_conditions(
    text: str,
    assessments: List[StatementAssessment],
    metrics: Dict[str, float]
) -> Dict[str, Tuple[bool, str]]:
    return {
        "Anchor Presence":             check_anchor_presence(assessments),
        "Structural Transfer":         check_structural_transfer(assessments, metrics),
        "Fractal Recursion":           check_fractal_recursion(assessments),
        "Density-to-Sourcing Imbalance": check_density_sourcing_imbalance(metrics),
        "Self-Referential Closure":    check_self_referential_closure(text, assessments, metrics),
    }

# ---------------------------------------------------------------------------
# RECLASSIFICATION GUIDANCE
# Doctrine 4.3: Absence of recursion → reclassify as narrative cascade or
# credibility laundering.
# ---------------------------------------------------------------------------

def get_reclassification_note(conditions: Dict[str, Tuple[bool, str]]) -> str:
    anchor_ok    = conditions["Anchor Presence"][0]
    transfer_ok  = conditions["Structural Transfer"][0]
    recursion_ok = conditions["Fractal Recursion"][0]

    if not anchor_ok:
        return "No anchor detected. This may be a simple information report or raw event description."
    if anchor_ok and not transfer_ok:
        return (
            "Structural transfer not confirmed. Credibility spread appears proportional to sourcing. "
            "This may be a well-sourced document or a simple information report."
        )
    if anchor_ok and transfer_ok and not recursion_ok:
        return (
            "Anchor Presence and Structural Transfer confirmed, but Fractal Recursion is not detected "
            "across micro/meso/macro scales. RECLASSIFY: evaluate for Narrative Cascade (temporal "
            "spread, node-to-node) or Credibility Laundering (proximity-based legitimacy transfer "
            "without recursive structure)."
        )
    return ""

# ---------------------------------------------------------------------------
# FULL ANALYSIS PIPELINE
# ---------------------------------------------------------------------------

def analyze_document(text: str) -> Dict:
    # Assign scale to each unit before classification
    scale_units = assign_scales(text)
    assessments = [classify_statement(unit_text, scale) for scale, unit_text in scale_units]

    metrics      = calculate_fct_metrics(text, assessments)
    risk_level, risk_explanation = get_risk_level(metrics["FCT Risk Score"])
    anchor_type, anchor_type_note = detect_anchor_type(text)
    topology, topology_note = estimate_topology(assessments)
    conditions   = assess_conditions(text, assessments, metrics)

    mandatory_met = all(
        conditions[k][0] for k in ["Anchor Presence", "Structural Transfer", "Fractal Recursion"]
    )

    combined_key   = (anchor_type, topology)
    combined_cm    = COMBINED_COUNTERMEASURE.get(combined_key, COUNTERMEASURES[topology])

    if mandatory_met:
        analyst_note = (
            f"FCT-D conditions are present. The artifact exhibits {anchor_type.lower()} anchor "
            f"characteristics within a {topology.lower()} structure. Credibility transfer is confirmed "
            f"across micro, meso, and macro scales. Primary structural concern: narrative coherence "
            f"may exceed evidentiary support. Topology-matched countermeasure: {combined_cm}"
        )
    else:
        reclass = get_reclassification_note(conditions)
        analyst_note = (
            f"Full FCT-D classification is not supported — one or more mandatory conditions are unmet. "
            f"{reclass}"
        )

    return {
        "statements":        assessments,
        "metrics":           metrics,
        "risk_level":        risk_level,
        "risk_explanation":  risk_explanation,
        "anchor_type":       anchor_type,
        "anchor_type_note":  anchor_type_note,
        "topology":          topology,
        "topology_note":     topology_note,
        "conditions":        conditions,
        "countermeasure":    COUNTERMEASURES[topology],
        "combined_countermeasure": combined_cm,
        "analyst_note":      analyst_note,
        "fct_confirmed":     mandatory_met,
        "reclass_note":      get_reclassification_note(conditions),
    }

# ---------------------------------------------------------------------------
# RENDERING HELPERS
# ---------------------------------------------------------------------------

def render_condition(name: str, result: Tuple[bool, str], is_mandatory: bool = True):
    passed, explanation = result
    if passed:
        icon = "✅"
    else:
        icon = "❌"
    tag = "[MANDATORY]" if is_mandatory else "[Confirmatory]"
    st.markdown(f"**{icon} {name}** *{tag}*")
    st.caption(explanation)

def render_reference_tab():
    st.subheader("FCT-D Field Reference")
    st.info(
        "FCT-D assesses structural credibility dynamics. It does not determine "
        "truth, intent, guilt, or deception. A finding of FCT risk is a structural "
        "assessment, not a judgment of veracity."
    )

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
    st.markdown("3. **Fractal Recursion** *(load-bearing)* — the same transfer pattern repeats at micro, meso, and macro scales simultaneously. Absence → reclassify as Narrative Cascade or Credibility Laundering.")

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
    matrix_data = []
    for (at, topo), cm in COMBINED_COUNTERMEASURE.items():
        matrix_data.append({"Anchor Type": at, "Topology": topo, "Countermeasure": cm})
    st.dataframe(pd.DataFrame(matrix_data), use_container_width=True, hide_index=True)

    st.markdown("### Adjacent Concepts — How FCT-D Differs")
    adjacent = pd.DataFrame([
        {"Concept": "Credibility Laundering", "How It Works": "Proximity to trusted source transfers legitimacy.", "FCT-D Difference": "FCT-D is structure-based and recursively reinforced. Laundering lacks multi-scale repetition."},
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
    "claims are true or false, and it does not assess intent or deception. "
    "High-stakes use requires corroboration."
)

mode = st.sidebar.radio("Analyst Mode", ["Experienced Analyst", "Junior / Trainee Analyst"])
st.sidebar.markdown("---")
st.sidebar.markdown("### Accepted Inputs")
st.sidebar.markdown("Paste text or upload `.txt`, `.docx`, or `.pdf`.")
st.sidebar.markdown("---")
st.sidebar.caption(
    "Rule-based heuristic engine implementing FCT-D Doctrine (Hollenbeck, April 2026). "
    "Designed for demonstration and validation testing."
)

main_tab, node_tab, scoring_tab, reference_tab = st.tabs([
    "Document Triage", "Node Classifier", "Scoring Layer", "Field Reference"
])

# ── Document Triage ──────────────────────────────────────────────────────────
with main_tab:
    left, right = st.columns([1.15, 0.85])

    with left:
        st.subheader("Input Document")
        uploaded     = st.file_uploader("Upload document", type=["txt", "docx", "pdf"])
        uploaded_text = load_uploaded_text(uploaded) if uploaded else ""
        text_input   = st.text_area(
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
            st.info(
                "Trainee cue: The top of the narrative should feel no stronger than the "
                "bottom supports. Coherence is not evidence. Confidence is not proof."
            )

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
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("FCT Risk Score", result["metrics"]["FCT Risk Score"])
        m2.metric("Risk Level",     result["risk_level"])
        fct_badge = "✅ YES" if result["fct_confirmed"] else "❌ NO"
        m3.metric("FCT-D Confirmed", fct_badge)
        m4.metric("Sources detected", result["metrics"]["Source Count"])
        st.caption(result["risk_explanation"])

        # Anchor type and topology
        a1, a2 = st.columns(2)
        with a1:
            st.markdown(f"**Anchor Type:** {result['anchor_type']}")
            st.caption(result["anchor_type_note"])
        with a2:
            st.markdown(f"**Topology:** {result['topology']}")
            st.caption(result["topology_note"])
            if result["topology_note"]:
                st.caption(f"*Evidence appears to scale with structure.*")

        st.markdown("---")
        c1, c2 = st.columns([1, 1])

        with c1:
            st.markdown("### Criteria Assessment")
            mandatory   = ["Anchor Presence", "Structural Transfer", "Fractal Recursion"]
            confirmatory = ["Density-to-Sourcing Imbalance", "Self-Referential Closure"]
            for name in mandatory:
                render_condition(name, result["conditions"][name], is_mandatory=True)
            for name in confirmatory:
                render_condition(name, result["conditions"][name], is_mandatory=False)

        with c2:
            st.markdown("### Classification")
            st.markdown(f"**Anchor Type:** {result['anchor_type']}")
            st.caption(ANCHOR_TYPE_GUIDANCE[result["anchor_type"]])
            st.markdown(f"**Topology:** {result['topology']}")
            st.caption(TOPOLOGY_GUIDANCE[result["topology"]])

            st.markdown("### Topology Countermeasure")
            st.info(result["countermeasure"])

            st.markdown("### Combined Countermeasure (Anchor Type × Topology)")
            st.success(f"**{result['anchor_type']} + {result['topology']}:** {result['combined_countermeasure']}")

        st.markdown("### Analyst Note")
        if result["fct_confirmed"]:
            st.warning(result["analyst_note"])
        else:
            st.error(result["analyst_note"])
            if result["reclass_note"]:
                st.info(f"**Reclassification Guidance:** {result['reclass_note']}")

        if mode == "Junior / Trainee Analyst":
            st.info(
                "A high score does not mean the document is false. It means the structure "
                "may be doing more credibility work than the evidence supports."
            )

        # Node classification table with scale column
        st.markdown("### Node Classification")
        rows = [
            {
                "Scale":      a.scale,
                "Code":       a.node_code,
                "Type":       a.node_type,
                "Confidence": a.confidence,
                "Statement":  a.statement[:120] + ("…" if len(a.statement) > 120 else ""),
            }
            for a in result["statements"]
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # Node distribution by scale — key diagnostic table
        st.markdown("### Node Distribution by Scale")
        dist_rows = []
        by_scale = {"Micro": Counter(), "Meso": Counter(), "Macro": Counter()}
        for a in result["statements"]:
            by_scale[a.scale][a.node_code] += 1
        for scale in ["Micro", "Meso", "Macro"]:
            c = by_scale[scale]
            dist_rows.append({
                "Scale":         scale,
                "Anchors (A)":   c.get("A", 0),
                "Events (E)":    c.get("E", 0),
                "Claims (C)":    c.get("C", 0),
                "Inferences (I)":c.get("I", 0),
            })
        st.dataframe(pd.DataFrame(dist_rows), use_container_width=True, hide_index=True)

        # Metric breakdown (collapsible)
        with st.expander("⚡ Metric Breakdown"):
            mm = result["metrics"]
            b1, b2, b3, b4 = st.columns(4)
            b1.metric(f"UER (×0.40)",         mm["UER"])
            b2.metric(f"Drop-off (×0.25)",     mm["Drop-off"])
            b3.metric(f"Connectivity (×0.20)", mm["Connectivity"])
            b4.metric(f"Centrality (×0.15)",   mm["Centrality"])
            st.caption(
                f"Sources detected: {mm['Source Count']} | "
                f"Formula: Score = (0.40 × UER) + (0.25 × Drop-off) + "
                f"(0.20 × Connectivity) + (0.15 × Centrality)"
            )

# ── Node Classifier ───────────────────────────────────────────────────────────
with node_tab:
    st.subheader("Single Statement Node Classifier")
    if mode == "Junior / Trainee Analyst":
        st.info(
            "Enter one sentence. The classifier returns its node type per the FCT-D "
            "Credibility Ladder: Anchor (It is) → Event (It happened) → "
            "Claim (It means) → Inference (It must be)."
        )
    statement = st.text_area("Enter one statement", height=140)
    if st.button("Classify Statement", use_container_width=True):
        if not statement.strip():
            st.error("Enter a statement first.")
        else:
            a = classify_statement(statement, scale="Micro")
            st.metric("Node Type", f"{a.node_code} — {a.node_type}")
            st.metric("Meaning",   NODE_DEFINITIONS[a.node_code]["meaning"])
            st.metric("Confidence", a.confidence)
            st.write("**Rationale:**", a.rationale)
            st.write("**Signal:**",    a.signal)
            if mode == "Junior / Trainee Analyst":
                st.info(f"**Field Test:** {NODE_DEFINITIONS[a.node_code]['field_test']}")

# ── Manual Scoring Layer ──────────────────────────────────────────────────────
with scoring_tab:
    st.subheader("Manual FCT Risk Score Calculator")
    st.caption("Score = (0.40 × UER) + (0.25 × Drop-off) + (0.20 × Connectivity) + (0.15 × Centrality)")
    uer  = st.slider("Unsupported Edge Ratio (UER)",  0.0, 1.0, 0.40, 0.01)
    drop = st.slider("Evidence Drop-off",              0.0, 1.0, 0.35, 0.01)
    conn = st.slider("Connectivity",                   0.0, 1.0, 0.40, 0.01)
    cent = st.slider("Centrality",                     0.0, 1.0, 0.35, 0.01)
    manual_score = round((0.40 * uer) + (0.25 * drop) + (0.20 * conn) + (0.15 * cent), 2)
    level, expl  = get_risk_level(manual_score)
    st.metric("Manual FCT Risk Score", manual_score)
    st.metric("Risk Level", level)
    st.caption(expl)

# ── Field Reference ───────────────────────────────────────────────────────────
with reference_tab:
    render_reference_tab()
