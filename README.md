# FCT-D Analyst Workbench

**Fractal Credibility Transfer — Document Variant**  
A Streamlit prototype for structural credibility triage of textual narrative artifacts.

Author concept: **Kevin M. Hollenbeck**  
Status: **Working analytic construct / prototype — not formal IC doctrine**

---

## BLUF

FCT-D Analyst Workbench helps analysts evaluate whether a document's perceived credibility is earned through evidence or constructed through narrative structure.

The tool allows an analyst to:

- Paste text or upload `.txt`, `.docx`, or `.pdf` files
- Classify statements as Anchor, Event, Claim, or Inference
- Assess FCT-D mandatory conditions
- Generate a heuristic FCT risk score
- Classify anchor type and topology
- Produce topology-matched countermeasure guidance

This is **not a truth engine**. It does **not** determine whether claims are true or false. It assesses structure-driven credibility risk.

---

## Core Concepts

FCT-D evaluates three mandatory conditions:

1. **Anchor Presence** — a credible or salient entry point exists
2. **Structural Transfer** — credibility spreads through design rather than sourcing
3. **Fractal Recursion** — the same credibility-transfer pattern repeats across micro, meso, and macro levels

Operational node ladder:

| Code | Node | Meaning |
|---|---|---|
| A | Anchor | It is |
| E | Event | It happened |
| C | Claim | It means |
| I | Inference | It must be |

---

## Features

### Document Triage
Upload or paste a document and receive:

- FCT risk score
- Risk level: Low / Moderate / High / Critical
- Mandatory condition assessment
- Anchor type classification
- Topology classification
- Countermeasure recommendation
- Analyst note
- Node classification table

### Node Classifier
Classify a single statement as:

- Anchor
- Event
- Claim
- Inference

### Manual Scoring Layer
Use sliders to calculate:

```text
Score = (0.40 × UER) + (0.25 × Drop-off) + (0.20 × Connectivity) + (0.15 × Centrality)
```

### Field Reference
Built-in analyst reference for:

- Credibility ladder
- Mandatory conditions
- Topology countermeasures

---

## Installation

```bash
git clone https://github.com/YOUR-USERNAME/fct-d-analyst-workbench.git
cd fct-d-analyst-workbench
pip install -r requirements.txt
streamlit run app.py
```

Or run locally without Git:

```bash
pip install streamlit pandas python-docx pypdf
streamlit run app.py
```

---

## Accepted Inputs

- Paste text directly
- Upload `.txt`
- Upload `.docx`
- Upload `.pdf`

PDF extraction depends on whether the PDF contains selectable text. Scanned PDFs may not extract correctly.

---

## Important Limitation

This prototype uses a **rule-based heuristic engine**. It is intended for demonstration, training, and validation testing.

It does not replace analyst judgment. High-stakes use requires corroboration.

---

## Suggested Future Upgrades

- LLM-assisted node classification
- Exportable analyst report
- Graph visualization of anchor/claim topology
- Case study library
- Human-in-the-loop validation workflow
- Confidence calibration module
- Source quality scoring

---

## Repository Structure

```text
fct-d-analyst-workbench/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
└── samples/
    └── sample_artifact.txt
```

---

## License

Suggested: MIT License for code.  
Analytic framework attribution should remain credited to Kevin M. Hollenbeck.
