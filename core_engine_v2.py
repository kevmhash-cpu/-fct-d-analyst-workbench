import re

# ---------------------------
# NODE CLASSIFICATION
# ---------------------------

def classify_statement(s):
    s_lower = s.lower()

    if any(x in s_lower for x in ["according to", "confirmed", "cve-", "apt", "official"]):
        return "A"
    if any(x in s_lower for x in ["observed", "reported", "detected", "identified"]):
        return "E"
    if any(x in s_lower for x in ["suggests", "likely", "indicates", "appears"]):
        return "C"
    if any(x in s_lower for x in ["therefore", "must", "proves", "confirms that"]):
        return "I"

    return "E"


# ---------------------------
# SPLIT TEXT
# ---------------------------

def split_statements(text):
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s for s in sentences if s.strip()]


# ---------------------------
# BUILD CHAIN
# ---------------------------

def build_chain(statements):
    chain = []
    for s in statements:
        node_type = classify_statement(s)
        chain.append({"text": s, "type": node_type})
    return chain


# ---------------------------
# EDGE SCORING (simple)
# ---------------------------

def edge_score(n1, n2):
    if n1 == "A" and n2 == "E":
        return 0.9
    if n1 == "E" and n2 == "E":
        return 0.85
    if n1 == "E" and n2 == "C":
        return 0.6
    if n1 == "C" and n2 == "I":
        return 0.3
    if n2 == "I":
        return 0.2
    return 0.5


# ---------------------------
# BUILD TRANSITIONS
# ---------------------------

def build_transitions(chain):
    transitions = []
    scores = []

    for i in range(len(chain) - 1):
        n1 = chain[i]["type"]
        n2 = chain[i + 1]["type"]

        score = edge_score(n1, n2)

        transitions.append({
            "from": n1,
            "to": n2,
            "transition": f"{n1}->{n2}",
            "score": score
        })

        scores.append(score)

    return transitions, scores


# ---------------------------
# FIND ANCHOR SCORE
# ---------------------------

def anchor_score(chain):
    for node in chain:
        if node["type"] == "A":
            return 0.95
    return 0.7


# ---------------------------
# DROP-OFF (FIXED — DOCTRINE CORRECT)
# ---------------------------

def calculate_dropoff(anchor, edge_scores):
    if not edge_scores:
        return 0
    avg_edge = sum(edge_scores) / len(edge_scores)
    return round(anchor - avg_edge, 3)


# ---------------------------
# ESCALATION DETECTION
# ---------------------------

def detect_escalation(transitions):
    escalation = []

    for t in transitions:
        if t["transition"] in ["E->I", "C->I", "A->I"]:
            escalation.append(t)

    return escalation


# ---------------------------
# KEY STATEMENTS (3–5 ONLY)
# ---------------------------

def key_statements(chain):
    priority = ["A", "I", "C"]
    selected = []

    for p in priority:
        for node in chain:
            if node["type"] == p and node not in selected:
                selected.append(node)

    return selected[:5]


# ---------------------------
# TOPOLOGY (simple heuristic)
# ---------------------------

def detect_topology(chain):
    counts = {"A":0, "E":0, "C":0, "I":0}

    for n in chain:
        counts[n["type"]] += 1

    if counts["A"] == 1:
        return "Hub-Spoke"
    elif counts["A"] > 1:
        return "Lattice"
    else:
        return "Hierarchical"


# ---------------------------
# ANCHOR TYPE (simple)
# ---------------------------

def detect_anchor_type(chain):
    text = " ".join([n["text"].lower() for n in chain])

    if any(x in text for x in ["death", "trafficking", "abuse"]):
        return "Emotional"
    if any(x in text for x in ["cia", "nasa", "government", "agency"]):
        return "Institutional"
    if any(x in text for x in ["data", "study", "analysis", "cve"]):
        return "Technical"

    return "Unknown"


# ---------------------------
# TRIAGE MATRIX (CRITICAL ADD)
# ---------------------------

def triage_matrix(anchor_type, topology):

    matrix = {
        ("Emotional","Hub-Spoke"): "Fast collapse — verify anchor",
        ("Emotional","Lattice"): "Most manipulative — verify each anchor",
        ("Technical","Lattice"): "Most durable — escalate to SME",
        ("Technical","Hierarchical"): "Refute at study level",
        ("Institutional","Hub-Spoke"): "Verify institution first",
        ("Institutional","Hierarchical"): "Engage mid-tier claims"
    }

    return matrix.get((anchor_type, topology), "General analysis required")


# ---------------------------
# MAIN ANALYSIS FUNCTION
# ---------------------------

def analyze_document(text):

    statements = split_statements(text)

    chain = build_chain(statements)

    transitions, edge_scores = build_transitions(chain)

    anchor = anchor_score(chain)

    dropoff = calculate_dropoff(anchor, edge_scores)

    escalation = detect_escalation(transitions)

    key_nodes = key_statements(chain)

    topology = detect_topology(chain)

    anchor_type = detect_anchor_type(chain)

    guidance = triage_matrix(anchor_type, topology)

    return {
        "chain": chain,
        "key_nodes": key_nodes,
        "transitions": transitions,
        "escalation": escalation,
        "dropoff": dropoff,
        "topology": topology,
        "anchor_type": anchor_type,
        "guidance": guidance
    }
