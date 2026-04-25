import streamlit as st
import pandas as pd
from core_engine_v2 import analyze_document

st.set_page_config(page_title="FCT-D Analyst Workbench", page_icon="🧠", layout="wide")

st.title("FCT-D Analyst Workbench")
st.caption("Fractal Credibility Transfer — Document Variant")
st.warning("This tool evaluates structural credibility, not truth, intent, or deception.")

# -----------------------
# INPUT
# -----------------------
text = st.text_area("Paste document text", height=300)

# -----------------------
# RUN ANALYSIS
# -----------------------
if st.button("Run FCT-D Analysis"):

    if not text.strip():
        st.error("Please enter text.")
    else:
        result = analyze_document(text)

        st.markdown("---")
        st.subheader("FCT-D Output")

        # -----------------------
        # KEY METRICS
        # -----------------------
        col1, col2, col3 = st.columns(3)

        col1.metric("Drop-off", result["dropoff"])
        col2.metric("Topology", result["topology"])
        col3.metric("Anchor Type", result["anchor_type"])

        # -----------------------
        # TRIAGE GUIDANCE
        # -----------------------
        st.markdown("### Analyst Guidance")
        st.success(result["guidance"])

        # -----------------------
        # ESCALATION POINTS
        # -----------------------
        st.markdown("### Escalation Points")

        if result["escalation"]:
            df = pd.DataFrame(result["escalation"])
            st.dataframe(df, use_container_width=True)
        else:
            st.write("No high-risk escalation detected.")

        # -----------------------
        # KEY STATEMENTS
        # -----------------------
        st.markdown("### Key Statements (A / C / I focus)")

        key_nodes = result["key_nodes"]

        if key_nodes:
            df = pd.DataFrame(key_nodes)
            st.dataframe(df, use_container_width=True)
        else:
            st.write("No key statements identified.")

        # -----------------------
        # FULL CHAIN (OPTIONAL)
        # -----------------------
        with st.expander("Show Full Chain"):
            df_chain = pd.DataFrame(result["chain"])
            st.dataframe(df_chain, use_container_width=True)
