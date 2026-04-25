import re
from collections import Counter

# ---------------------------
# DOCTRINE CONSTANTS
# ---------------------------

# Node ladder per FCT-D Doctrine Section 5:
# A = "It is"   — verified, independently sourceable
# E = "It happened" — observable occurrence, no interpretation
# C = "It means"    — interpretation, assigns significance
# I = "It must be"  — stacked conclusion beyond direct evidence

ANCHOR_SIGNALS = [
    r"\b(confirmed|verified|established|documented|recorded|certified)\b",
    r"\baccording to [A-Z][a-z]+ (report|study|filing|data|statistics)\b",
    r"\b(published|released|filed|signed|enacted|ratified)\b",
    r"\b\d{4}\b.*\b(percent|billion|million|thousand)\b",
    r"\b(primary source|court filing|official record|government document)\b",
]

EVENT_SIGNALS = [
    r"\b(occurred|happened|took place|was arrested|was charged|launched|met with|voted|approved|denied|announced|stated|released|attacked|began|ended|created|formed|observed|reported|detected|identified)\b",
    r"\b(the (board|agency|official|department|committee|panel)) (released|issued|published|announced|submitted|reported)\b",
    r"\b(on [A-Z][a-z]+day|last (week|month|year)|on \w+ \d+)\b",
]

CLAIM_SIGNALS = [
    r"\b(suggests|indicates|shows|means|reveals|demonstrates|points to|signals|reflects|implies)\b",
    r"\b(evidence of|consistent with|this (confirms|proves|validates|demonstrates))\b",
    r"\b(therefore|thus|consequently|as a result|which (means|shows|proves|confirms|validates))\b",
    r"\b(because|since|given that|in light of)\b",
    r"\b(likely|appears to|seems to|is indicative of)\b",
    r"\b(asserts? that|concludes? that|determines? that|confirms? that)\b",
    r"\b(motive|agenda|intent|significance|implication)\b",
]

INFERENCE_SIGNALS = [
    r"\b(must (be|therefore|confirm|prove|validate|demonstrate))\b",
    r"\b(inferr?ing|infers? (therefore|that|from))\b",
    r"\b(it follows (that|therefore))\b",
    r"\b(no (other|alternative|independent) (explanation|source|review|validation))\b",
    r"\b(undeniable|inevitably|cannot be (coincidence|disputed|denied))\b",
    r"\b(only explanation|clearly proves|this must (mean|confirm|establish))\b",
    r"\b(validates? the (authority|mandate|role|process|conclusion) of)\b",
    r"\b(justif(ies|y) (continued|the|its))\b",
]

EMOTIONAL_TERMS = [
    "victim", "children", "trauma", "grief", "scandal", "atrocity",
    "fear", "outrage", "abuse", "death", "crisis", "tragedy", "suffering",
    "emergency", "catastrophe", "massacre",
]

INSTITUTIONAL_TERMS = [
    "board", "agency", "commission", "committee", "council", "department",
    "ministry", "official", "government", "court", "judiciary", "congress",
    "parliament", "university", "institute", "organization", "bureau",
    "authority", "administration", "secretariat", "oversight", "panel",
    "directorate", "coalition", "alliance", "federation",
    "fbi", "cia", "dhs", "odni", "doj", "gao", "who", "un", "nato",
    "treasury", "pentagon",
]

TECHNICAL_TERMS = [
    "algorithm", "dataset", "model", "patent", "peer-reviewed", "quantum",
    "machine learning", "neural", "statistical", "regression", "methodology",
    "calibration", "formula", "threshold", "metric", "coefficient",
    "parameter", "simulation", "protocol", "cve", "apt",
]

TOPOLOGY_GUIDANCE = {
    "Hub-Spoke":    "Single dominant anchor with multiple peripheral claims radiating outward.",
    "Hierarchical": "Anchor spawns mid-level sub-anchors, which then support additional claims (tree structure).",
    "Lattice":      "Multiple anchors cross-reference and mutually reinforce; no single root node dominates.",
}

COUNTERMEASURES = {
    "Hub-Spoke":    "Validate or refute the hub anchor first. Peripheral claims may collapse as a secondary effect.",
    "Hierarchical": "Map the full claim tree before engaging any node. Refute at the highest viable tier.",
    "Lattice":      "Require independent verification paths for each anchor. Internal cross-references do not qualify.",
}

TRIAGE_MATRIX = {
    ("Emotional",    "Hub-Spoke"):    "Fastest to collapse. Verify anchor event; spokes fall automatically.",
    ("Emotional",    "Hierarchical"): "Grief escalates into doctrine. Map emotional cascade path before engaging.",
    ("Emotional",    "Lattice"):      "Most manipulative variant. Multiple trauma anchors mutually reinforce. Per-anchor verification required.",
    ("Institutional","Hub-Spoke"):    "Classic disinfo playbook. Named agency as hub; check primary docs first.",
    ("Institutional","Hierarchical"): "Agency → program → claim tree. Refute at institutional tier first; subclaims may persist.",
    ("Institutional","Lattice"):      "Agencies cross-cited. Each lends the others halo. Verify each institution independently.",
    ("Technical",    "Hub-Spoke"):    "Jargon hub radiating pseudoscience. SME review of anchor term usually sufficient.",
    ("Technical",    "Hierarchical"): "Real paper → misread finding → theory tree. Engage at paper level.",
    ("Technical",    "Lattice"):      "Most durable variant. Escalate to SME triage.",
}

# ---------------------------
# NODE CLASSIFICATION
# Doctrine field tests:
#   A — "Can I prove this from a primary source outside this artifact?"
#   E — "Is this describing what occurred, not interpreting it?"
#   C — "Is this explaining meaning instead of stating fact?"
#   I — "Does this depend on prior claims rather than direct verification?"
# Primary failure point: Event → Claim transition (doctrine Section 5)
# ---------------------------

def _score(statement, patterns):
    return sum(1.0 for p in patterns if re.search(p, statement, re.I))

def classify_statement(s):
    scores = {
        "A": _score(s, ANCHOR_SIGNALS),
        "E": _score(s, EVENT_SIGNALS),
        "C": _score(s, CLAIM_SIGNALS),
        "I": _score(s, INFERENCE_SIGNALS),
    }
    # Doctrine primary failure point: boost Claim when co-occurring with Event
    if scores["E"] > 0 and scores["C"] > 0:
        scores["C"] += 0.5
    # Inference stacks on claims
    if scores["C"] > 0 and scores["I"] > 0:
        scores["I"] += 0.5

    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "E"  # default to Event, not Anchor


# ---------------------------
# TEXT SPLITTING (three-scale)
# Micro = sentences, Meso = paragraphs, Macro = first+last
# ---------------------------

def split_statements(text):
    cleaned = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    return [s.strip() for s in parts if len(s.strip()) > 25]

def split_paragraphs(text):
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paras) < 2:
        sents = split_statements(text)
        paras = [" ".join(sents[i:i+3]) for i in range(0, len(sents), 3)]
    return [p for p in paras if len(p) > 25]

def assign_scales(text):
    """Returns list of (scale, text) tuples for micro/meso/macro analysis."""
    sentences  = split_statements(text)
    paragraphs = split_paragraphs(text)
    units = []
    for s in sentences[:30]:
        units.append(("Micro", s))
    for para in paragraphs[:10]:
        para_sents = split_statements(para)
        if para_sents:
            units.append(("Meso", max(para_sents, key=len)))
    if len(sentences) >= 2:
        units.append(("Macro", sentences[0]))
        units.append(("Macro", sentences[-1]))
    elif sentences:
        units.append(("Macro", sentences[0]))
    return units


# ---------------------------
# CHAIN BUILDER
# ---------------------------

def build_chain(statements):
    return [{"text": s, "type": classify_statement(s)} for s in statements]


# ---------------------------
# EDGE SCORING
# Reflects doctrine risk hierarchy: A→E safe, E→C risky, C→I highest risk
# ---------------------------

def edge_score(n1, n2):
    table = {
        ("A","E"): 0.90, ("A","C"): 0.55, ("A","I"): 0.25,
        ("E","E"): 0.85, ("E","C"): 0.55, ("E","I"): 0.20,
        ("C","C"): 0.50, ("C","I"): 0.30,
        ("I","I"): 0.20, ("I","C"): 0.35,
    }
    return table.get((n1, n2), 0.50)

def build_transitions(chain):
    transitions, scores = [], []
    for i in range(len(chain) - 1):
        n1, n2 = chain[i]["type"], chain[i+1]["type"]
        score = edge_score(n1, n2)
        transitions.append({"from": n1, "to": n2, "transition": f"{n1}->{n2}", "score": score})
        scores.append(score)
    return transitions, scores


# ---------------------------
# ANCHOR SCORE
# ---------------------------

def anchor_score(chain):
    return 0.95 if any(n["type"] == "A" for n in chain) else 0.70


# ---------------------------
# DROP-OFF (doctrine: anchor score − avg edge score)
# ---------------------------

def calculate_dropoff(anchor, edge_scores):
    if not edge_scores:
        return 0.0
    return round(anchor - (sum(edge_scores) / len(edge_scores)), 3)


# ---------------------------
# ESCALATION DETECTION
# ---------------------------

def detect_escalation(transitions):
    return [t for t in transitions if t["transition"] in ("E->I", "C->I", "A->I")]


# ---------------------------
# KEY STATEMENTS (3–5)
# ---------------------------

def key_statements(chain):
    selected = []
    for priority in ("A", "I", "C", "E"):
        for node in chain:
            if node["type"] == priority and node not in selected:
                selected.append(node)
    return selected[:5]


# ---------------------------
# TOPOLOGY DETECTION
# Doctrine Axis 2:
#   Hub-Spoke    — single anchor, N peripheral claims
#   Hierarchical — 2 anchors (root + sub-anchor tier) + claims below
#   Lattice      — 3+ anchors cross-reinforcing
# ---------------------------

def detect_topology(chain):
    counts = Counter(n["type"] for n in chain)
    anchors = counts.get("A", 0)
    claims  = counts.get("C", 0)
    infer   = counts.get("I", 0)

    if anchors >= 3 and claims >= 2:
        return "Lattice"
    if anchors <= 1 and (claims + infer) >= 3:
        return "Hub-Spoke"
    if anchors == 2 and claims >= 2:
        return "Hierarchical"
    return "Hub-Spoke" if claims >= anchors else "Hierarchical"


# ---------------------------
# ANCHOR TYPE DETECTION
# Doctrine Axis 1: Emotional / Institutional / Technical
# Institutional terms weighted heavily — generic words like "data"
# should not override clear organizational language.
# ---------------------------

def detect_anchor_type(chain):
    text = " ".join(n["text"].lower() for n in chain)
    scores = {
        "Emotional":     sum(w in text for w in EMOTIONAL_TERMS),
        "Institutional": sum(w in text for w in INSTITUTIONAL_TERMS),
        "Technical":     sum(w in text for w in TECHNICAL_TERMS),
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "Institutional"


# ---------------------------
# SOURCE COUNTING
# ---------------------------

def count_sources(text):
    patterns = [
        r"https?://", r"www\.", r"doi\.org", r"\[[0-9]+\]",
        r"\([A-Z][A-Za-z]+,\s?\d{4}\)",
        r"\breported by\b", r"\bpublished by\b", r"\bdata from\b",
        r"\bsource:\b", r"\baccording to [A-Z]",
    ]
    return sum(len(re.findall(p, text, re.I)) for p in patterns)


# ---------------------------
# FCT METRICS
# ---------------------------

def calculate_metrics(chain, text):
    counts       = Counter(n["type"] for n in chain)
    total        = max(len(chain), 1)
    source_count = count_sources(text)
    interpretive = counts.get("C", 0) + counts.get("I", 0)

    unsupported  = max(0, interpretive - source_count)
    total_edges  = max(1, counts.get("E", 0) + interpretive)
    uer          = min(1.0, unsupported / total_edges)

    anchor_ratio      = counts.get("A", 0) / total
    interpretive_ratio = interpretive / total
    drop_off          = min(1.0, max(0.0, interpretive_ratio - anchor_ratio + 0.25))

    connectivity = min(1.0, counts.get("C", 0) * 0.07 + counts.get("I", 0) * 0.10)
    anchors      = max(counts.get("A", 0), 1)
    centrality   = min(1.0, interpretive / (anchors * 8))

    score = (0.40 * uer) + (0.25 * drop_off) + (0.20 * connectivity) + (0.15 * centrality)

    return {
        "UER":            round(uer, 2),
        "Drop-off":       round(drop_off, 2),
        "Connectivity":   round(connectivity, 2),
        "Centrality":     round(centrality, 2),
        "FCT Risk Score": round(min(1.0, score), 2),
        "Source Count":   source_count,
    }


# ---------------------------
# CONDITION ASSESSMENT (doctrine-faithful)
# ---------------------------

def check_anchor_presence(chain):
    """Doctrine 4.1: verifiable, semi-verifiable, or emotionally salient entry point."""
    anchor_count = sum(1 for n in chain if n["type"] == "A")
    if anchor_count >= 1:
        return True, f"Anchor node detected ({anchor_count} statement(s))."
    high_event = sum(1 for n in chain if n["type"] == "E")
    if high_event >= 1:
        return True, f"High-confidence Event serving as credibility anchor ({high_event} detected)."
    return False, "No verifiable or salient anchor detected."

def check_structural_transfer(chain, metrics):
    """Doctrine 4.2: credibility spreads through design rather than explicit evidence."""
    counts       = Counter(n["type"] for n in chain)
    interpretive = counts.get("C", 0) + counts.get("I", 0)
    anchors      = counts.get("A", 0)
    qualifies    = (
        interpretive >= 2 and
        (anchors == 0 or interpretive / max(anchors, 1) >= 2.0) and
        metrics["UER"] >= 0.40
    )
    if qualifies:
        return True, f"Structure substituting for sourcing: {interpretive} interpretive node(s) vs {anchors} anchor(s), UER={metrics['UER']}."
    return False, "Insufficient evidence that structure is substituting for sourcing."

def check_fractal_recursion_scaled(scale_units):
    """
    Doctrine 4.3 (LOAD-BEARING): pattern must repeat at micro, meso, AND macro
    scales simultaneously. Checks each scale independently.
    """
    by_scale = {"Micro": Counter(), "Meso": Counter(), "Macro": Counter()}
    for scale, text in scale_units:
        node = classify_statement(text)
        by_scale[scale][node] += 1

    results = {}
    for scale, counts in by_scale.items():
        has_interpretive = (counts.get("C", 0) + counts.get("I", 0)) >= 1
        has_sourcing     = (counts.get("A", 0) + counts.get("E", 0)) >= 1
        results[scale]   = has_interpretive and has_sourcing

    detail = " | ".join(f"{s}: {'✓' if v else '✗'}" for s, v in results.items())
    if all(results.values()):
        return True, f"Credibility transfer confirmed at all three scales. [{detail}]"
    failing = [s for s, v in results.items() if not v]
    if len(failing) == 1:
        return False, (
            f"Pattern at {' and '.join(s for s, v in results.items() if v)} scale only. "
            f"Insufficient for FCT-D. [{detail}] Consider Credibility Laundering or Narrative Cascade."
        )
    return False, f"Fractal Recursion not confirmed. [{detail}]"

def check_density_sourcing(metrics):
    """Doctrine Criterion 4: high claim volume vs. low external sourcing."""
    if metrics["UER"] >= 0.50:
        return True, f"High unsupported edge ratio ({metrics['UER']}): many interpretive nodes, few external sources."
    return False, f"Density imbalance not strongly confirmed (UER={metrics['UER']})."

def check_self_referential_closure(text, metrics):
    """
    Doctrine Criterion 5: claims loop internally without external validation.
    Internal cross-references serve as apparent corroboration.
    """
    self_val = [
        r"\b(validates?|confirms?|establishes?|certif(ies|y)) (the|its|their) (own|authority|mandate|process|methodology|role|conclusion|finding)\b",
        r"\bno (external|independent|outside) (review|source|validation|verification|audit) (is |was )?(required|needed|necessary)\b",
        r"\b(internal|own) (review|validation|assessment|analysis) (confirmed|validates?|establishes?)\b",
    ]
    circular = [
        r"\b(prior|earlier|previous) (warning|finding|assessment|report|bulletin).{0,60}(confirms?|validates?|proves?).{0,60}(current|this|present)\b",
        r"\b(this|the) (pattern|finding|conclusion|assessment).{0,80}(pattern|finding|conclusion|assessment)\b",
    ]
    s = text.lower()
    sv = sum(1 for p in self_val if re.search(p, s, re.I))
    cr = sum(1 for p in circular if re.search(p, s, re.I))

    if sv >= 1 or cr >= 1:
        return True, f"Self-referential closure confirmed (self-validation={sv}, circular={cr})."
    if metrics["Source Count"] <= 1 and metrics["UER"] >= 0.50:
        return True, f"Closure indicated: low external sourcing ({metrics['Source Count']}) with high interpretive load."
    return False, "No strong self-referential closure detected."


# ---------------------------
# TRIAGE MATRIX LOOKUP
# ---------------------------

def triage_matrix(anchor_type, topology):
    return TRIAGE_MATRIX.get((anchor_type, topology), "General analysis required — verify anchor independently.")


# ---------------------------
# MAIN ANALYSIS FUNCTION
# ---------------------------

def analyze_document(text):
    statements  = split_statements(text)
    chain       = build_chain(statements)
    scale_units = assign_scales(text)

    transitions, edge_scores = build_transitions(chain)
    anchor      = anchor_score(chain)
    dropoff     = calculate_dropoff(anchor, edge_scores)
    escalation  = detect_escalation(transitions)
    key_nodes   = key_statements(chain)
    topology    = detect_topology(chain)
    anchor_type = detect_anchor_type(chain)
    guidance    = triage_matrix(anchor_type, topology)
    metrics     = calculate_metrics(chain, text)

    # Condition assessment
    cond_anchor   = check_anchor_presence(chain)
    cond_transfer = check_structural_transfer(chain, metrics)
    cond_recursion = check_fractal_recursion_scaled(scale_units)
    cond_density  = check_density_sourcing(metrics)
    cond_closure  = check_self_referential_closure(text, metrics)

    conditions = {
        "Anchor Presence":              cond_anchor,
        "Structural Transfer":          cond_transfer,
        "Fractal Recursion":            cond_recursion,
        "Density-to-Sourcing Imbalance": cond_density,
        "Self-Referential Closure":     cond_closure,
    }

    mandatory_met = cond_anchor[0] and cond_transfer[0] and cond_recursion[0]

    return {
        "chain":        chain,
        "key_nodes":    key_nodes,
        "transitions":  transitions,
        "escalation":   escalation,
        "dropoff":      dropoff,
        "topology":     topology,
        "topology_note": TOPOLOGY_GUIDANCE[topology],
        "anchor_type":  anchor_type,
        "guidance":     guidance,
        "metrics":      metrics,
        "conditions":   conditions,
        "fct_confirmed": mandatory_met,
        "scale_units":  scale_units,
    }
