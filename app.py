from dotenv import load_dotenv
load_dotenv()

import streamlit as st
from utils.audio_processor import process_input
from core.transcriber import transcribe_all
from core.summarizer import summarize, generate_title
from core.extractor import extract_action_items, extract_key_decisions, extract_questions
from core.rag_engine import build_rag_chain, ask_question


# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Video Assistant",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# STYLE
# Kept intentionally light — most of the UI now leans on native Streamlit
# components (tabs, chat_message, status, metrics) instead of custom HTML,
# which makes it more robust, more accessible, and easier to maintain.
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&display=swap');

:root {
    --bg: #0b0c10;
    --surface: #14151c;
    --border: #24252f;
    --accent: #8b5cf6;
    --accent-2: #22d3ee;
    --text-muted: #8a8aa3;
}

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
h1, h2, h3, h4 { font-family: 'Space Grotesk', sans-serif !important; }

.stApp { background: var(--bg); }

/* Hero */
.hero {
    padding: 0.25rem 0 1rem 0;
}
.hero h1 {
    font-size: 2.1rem;
    margin: 0;
    background: linear-gradient(135deg, #ffffff 0%, var(--accent) 60%, var(--accent-2) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.hero p {
    color: var(--text-muted);
    margin-top: 0.25rem;
    font-size: 0.95rem;
}

/* Metric-style summary chips */
[data-testid="stMetric"] {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 0.9rem 1rem;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] { gap: 4px; }
.stTabs [data-baseweb="tab"] {
    border-radius: 8px 8px 0 0;
    padding: 0.5rem 1.1rem;
}

/* Buttons */
.stButton > button, .stDownloadButton > button {
    border-radius: 8px !important;
    font-weight: 600 !important;
}

/* Sidebar */
[data-testid="stSidebar"] { border-right: 1px solid var(--border); }

/* Empty state */
.empty-state {
    text-align: center;
    padding: 4rem 1rem;
    color: var(--text-muted);
}
.empty-state .emoji { font-size: 3rem; margin-bottom: 0.75rem; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────
for key, default in {
    "result": None,
    "chat_history": [],
    "pipeline_steps": {},
    "pipeline_done": False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

PIPELINE_STEPS = [
    ("audio", "Processing audio"),
    ("transcript", "Transcribing"),
    ("title", "Generating title"),
    ("summary", "Summarising"),
    ("extract", "Extracting insights"),
    ("rag", "Building chat engine"),
]

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR — inputs live here, kept minimal
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🎬 AI Video Assistant")
    st.caption("Meeting intelligence, end to end.")
    st.divider()

    source = st.text_input(
        "YouTube URL or file path",
        placeholder="https://youtube.com/watch?v=... or /path/to/file.mp4",
    )
    language = st.selectbox("Language", ["english", "hinglish"], index=0)
    run_btn = st.button("⚡ Analyse", use_container_width=True, type="primary")

    if st.session_state.result:
        st.divider()
        if st.button("🗂️ New session", use_container_width=True):
            st.session_state.result = None
            st.session_state.chat_history = []
            st.session_state.pipeline_done = False
            st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="hero"><h1>AI Video Assistant</h1>'
    '<p>Transcribe · Summarise · Chat with your meetings</p></div>',
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────────────────────
# RUN PIPELINE
# Uses st.status as a single live, collapsible progress panel instead of a
# custom sidebar dot-tracker — clearer feedback and built-in error styling.
# ─────────────────────────────────────────────────────────────────────────────
if run_btn:
    if not source.strip():
        st.error("Please enter a YouTube URL or file path.")
    else:
        st.session_state.result = None
        st.session_state.chat_history = []
        st.session_state.pipeline_done = False

        with st.status("Running pipeline…", expanded=True) as status:
            try:
                st.write("🔊 Processing audio…")
                chunks = process_input(source)

                st.write("📝 Transcribing…")
                transcript = transcribe_all(chunks, language)

                st.write("🏷️ Generating title…")
                title = generate_title(transcript)

                st.write("📋 Summarising…")
                summary = summarize(transcript)

                st.write("🔍 Extracting action items, decisions & questions…")
                action_items = extract_action_items(transcript)
                decisions = extract_key_decisions(transcript)
                questions = extract_questions(transcript)

                st.write("🧠 Building chat engine…")
                rag_chain = build_rag_chain(transcript)

                st.session_state.result = {
                    "title": title,
                    "transcript": transcript,
                    "summary": summary,
                    "action_items": action_items,
                    "key_decisions": decisions,
                    "open_questions": questions,
                    "rag_chain": rag_chain,
                }
                st.session_state.pipeline_done = True
                status.update(label="✅ Analysis complete", state="complete", expanded=False)

            except Exception as e:
                status.update(label="❌ Pipeline failed", state="error", expanded=True)
                st.exception(e)
                st.stop()

        st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# RESULTS
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.result:
    r = st.session_state.result

    st.subheader(r["title"])

    def _word_count(text: str) -> int:
        return len((text or "").split())

    m1, m2, m3, m4 = st.columns(4)
    def _line_count(text: str) -> int:
        return len([l for l in (text or "").split("\n") if l.strip()])

    m1.metric("Transcript length", f"{_word_count(r['transcript']):,} words")
    m2.metric("Action items", _line_count(r["action_items"]))
    m3.metric("Key decisions", _line_count(r["key_decisions"]))
    m4.metric("Open questions", _line_count(r["open_questions"]))

    st.divider()

    tab_summary, tab_actions, tab_decisions, tab_questions, tab_transcript, tab_chat = st.tabs(
        ["📋 Summary", "✅ Action Items", "🔑 Decisions", "❓ Questions", "📝 Transcript", "💬 Chat"]
    )

    with tab_summary:
        st.markdown(r["summary"])

    with tab_actions:
        st.markdown(r["action_items"])

    with tab_decisions:
        st.markdown(r["key_decisions"])

    with tab_questions:
        st.markdown(r["open_questions"])

    with tab_transcript:
        st.text_area("Full transcript", r["transcript"], height=400, label_visibility="collapsed")
        st.download_button(
            "⬇️ Download transcript (.txt)",
            data=r["transcript"],
            file_name="transcript.txt",
            mime="text/plain",
        )

    with tab_chat:
        st.caption("Ask anything about this meeting — grounded in the transcript.")

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if prompt := st.chat_input("What were the main decisions made?"):
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Thinking…"):
                    answer = ask_question(r["rag_chain"], prompt)
                st.markdown(answer)
            st.session_state.chat_history.append({"role": "assistant", "content": answer})

        if st.session_state.chat_history:
            if st.button("🗑️ Clear chat"):
                st.session_state.chat_history = []
                st.rerun()

else:
    st.markdown("""
    <div class="empty-state">
        <div class="emoji">🎬</div>
        <h3>Ready to analyse</h3>
        <p>Paste a YouTube URL or local file path in the sidebar, choose your language,
        and hit <strong>Analyse</strong> to get started.</p>
    </div>
    """, unsafe_allow_html=True)

