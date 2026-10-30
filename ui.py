import requests
import streamlit as st

API_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="HybridRAG Engine", page_icon="🔎", layout="wide")
st.title("🔎 HybridRAG Engine")
st.caption("Local document search with vector + keyword retrieval and source citations.")

with st.expander("How to use"):
    st.markdown(
        "1. Put PDF, text, Markdown, or code files in `data/uploads/`.\n"
        "2. Start the FastAPI server.\n"
        "3. Click **Re-index documents**.\n"
        "4. Ask a question below."
    )

if st.button("Re-index documents", type="primary"):
    try:
        with st.spinner("Extracting, embedding, and indexing documents..."):
            response = requests.post(f"{API_URL}/ingest", timeout=600)
        if response.ok:
            st.success(f"Indexed {response.json()['chunks_indexed']} chunks.")
        else:
            st.error(response.text)
    except requests.RequestException as exc:
        st.error(f"Could not reach API. Start it with `uvicorn app.main:app --reload`. Details: {exc}")

question = st.text_input("Ask a question about your documents")
top_k = st.slider("Number of source chunks", min_value=1, max_value=5, value=3)

if st.button("Search") and question.strip():
    try:
        with st.spinner("Searching documents..."):
            response = requests.post(
                f"{API_URL}/query",
                json={"question": question, "top_k": top_k},
                timeout=300,
            )
        if response.ok:
            result = response.json()
            st.subheader("Answer")
            st.write(result["answer"])
            st.caption(result["note"])
            st.subheader("Sources")
            for i, citation in enumerate(result["citations"], start=1):
                title = f"{i}. {citation['source']} — chunk {citation['chunk_id']}"
                if citation["page"] is not None:
                    title += f" — page {citation['page']}"
                with st.expander(title):
                    st.write(citation["text"])
        else:
            st.error(response.text)
    except requests.RequestException as exc:
        st.error(f"Could not reach API: {exc}")
