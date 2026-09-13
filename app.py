from dotenv import load_dotenv
load_dotenv()

import os
import uuid
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
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
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

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    h1, h2, h3, h4 {
        font-family: 'Space Grotesk', sans-serif !important;
    }

    .stApp {
        background: var(--bg);
    }

    /* Hero */
    .hero {
        padding: 0.25rem 0 1rem 0;
    }

    .hero h1 {
        font-size: 2.1rem;
        margin: 0;
        background: linear-gradient(
            135deg,
            #ffffff 0%,
            var(--accent) 60%,
            var(--accent-2) 100%
        );
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
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 0.5rem 1.1rem;
    }

    /* Buttons */
    .stButton > button,
    .stDownloadButton > button {
        border-radius: 8px !important;
        font-weight: 600 !important;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        border-right: 1px solid var(--border);
    }

    /* Empty state */
    .empty-state {
        text-align: center;
        padding: 4rem 1rem;
        color: var(--text-muted);
    }

    .empty-state .emoji {
        font-size: 3rem;
        margin-bottom: 0.75rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


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


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

PIPELINE_STEPS = [
    ("audio", "Processing audio"),
    ("transcript", "Transcribing"),
    ("title", "Generating title"),
    ("summary", "Summarising"),
    ("extract", "Extracting insights"),
    ("rag", "Building chat engine"),
]

SUPPORTED_VIDEO_TYPES = [
    "mp4",
    "mov",
    "mkv",
    "avi",
    "webm",
    "mpeg",
    "mpg",
    "m4v",
]

SUPPORTED_AUDIO_TYPES = [
    "mp3",
    "wav",
    "m4a",
    "aac",
    "flac",
    "ogg",
]


# ─────────────────────────────────────────────────────────────────────────────
# HELPER — SAVE UPLOADED FILE
# ─────────────────────────────────────────────────────────────────────────────
def save_uploaded_file(uploaded_file) -> str:
    """
    Save a Streamlit UploadedFile to the downloads directory.

    A UUID is added to the filename so multiple users/files do not
    accidentally overwrite each other.
    """

    original_name = uploaded_file.name
    extension = os.path.splitext(original_name)[1].lower()

    unique_name = f"{uuid.uuid4().hex}{extension}"
    output_path = os.path.join(DOWNLOAD_DIR, unique_name)

    with open(output_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    return output_path


# ─────────────────────────────────────────────────────────────────────────────
# HELPER — CLEAN UP TEMPORARY FILE
# ─────────────────────────────────────────────────────────────────────────────
def cleanup_file(file_path: str | None) -> None:
    """Remove a temporary uploaded file if it exists."""

    if not file_path:
        return

    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except OSError:
        # Cleanup failure should never crash the application.
        pass


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR — INPUTS
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🎬 AI Video Assistant")
    st.caption("Meeting intelligence, end to end.")
    st.divider()

    # Input mode
    input_mode = st.radio(
        "Input source",
        ["YouTube URL", "Upload video/audio"],
        horizontal=False,
    )

    source = None
    uploaded_file = None

    # ─────────────────────────────────────────────────────────────────────────
    # YOUTUBE INPUT
    # ─────────────────────────────────────────────────────────────────────────
    if input_mode == "YouTube URL":
        source = st.text_input(
            "YouTube URL",
            placeholder="https://youtube.com/watch?v=...",
        )

        st.caption(
            "Paste a public YouTube video URL."
        )

    # ─────────────────────────────────────────────────────────────────────────
    # FILE UPLOAD INPUT
    # ─────────────────────────────────────────────────────────────────────────
    else:
        uploaded_file = st.file_uploader(
            "Upload your meeting video/audio",
            type=SUPPORTED_VIDEO_TYPES + SUPPORTED_AUDIO_TYPES,
            help=(
                "Supported video formats: MP4, MOV, MKV, AVI, WEBM, MPEG, MPG, M4V. "
                "Supported audio formats: MP3, WAV, M4A, AAC, FLAC, OGG."
            ),
        )

        if uploaded_file is not None:
            file_size_mb = uploaded_file.size / (1024 * 1024)

            st.success(f"✓ {uploaded_file.name}")
            st.caption(f"File size: {file_size_mb:.1f} MB")

    st.divider()

    # Language
    language = st.selectbox(
        "Language",
        ["english", "hinglish"],
        index=0,
    )

    # Analyse button
    run_btn = st.button(
        "⚡ Analyse",
        use_container_width=True,
        type="primary",
    )

    # New session
    if st.session_state.result:
        st.divider()

        if st.button(
            "🗂️ New session",
            use_container_width=True,
        ):
            st.session_state.result = None
            st.session_state.chat_history = []
            st.session_state.pipeline_done = False
            st.session_state.pipeline_steps = {}
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="hero">'
    '<h1>AI Video Assistant</h1>'
    '<p>Transcribe · Summarise · Chat with your meetings</p>'
    '</div>',
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────────────────────────────────────
# RUN PIPELINE
# ─────────────────────────────────────────────────────────────────────────────
if run_btn:

    # ─────────────────────────────────────────────────────────────────────────
    # VALIDATE INPUT
    # ─────────────────────────────────────────────────────────────────────────

    if input_mode == "YouTube URL":

        if not source or not source.strip():
            st.error("Please enter a YouTube URL.")

            st.stop()

        source = source.strip()

        if not (
            source.startswith("http://")
            or source.startswith("https://")
        ):
            st.error(
                "Please enter a valid YouTube URL starting with "
                "`https://`."
            )
            st.stop()

        uploaded_source_path = None

    else:

        if uploaded_file is None:
            st.error("Please upload a video or audio file.")

            st.stop()

        # Save uploaded file temporarily
        uploaded_source_path = save_uploaded_file(uploaded_file)
        source = uploaded_source_path

    # Reset previous results
    st.session_state.result = None
    st.session_state.chat_history = []
    st.session_state.pipeline_done = False

    # ─────────────────────────────────────────────────────────────────────────
    # PIPELINE
    # ─────────────────────────────────────────────────────────────────────────

    with st.status("Running pipeline…", expanded=True,) as status:
        try:
            # ─────────────────────────────────────────────────────────────────
            # STEP 1 — AUDIO PROCESSING
            # ─────────────────────────────────────────────────────────────────
            st.write("🔊 Processing audio…")

            chunks = process_input(source)

            if not chunks:
                raise RuntimeError(
                    "No audio chunks were created from the input."
                )

            # ─────────────────────────────────────────────────────────────────
            # STEP 2 — TRANSCRIPTION
            # ─────────────────────────────────────────────────────────────────
            st.write("📝 Transcribing…")

            transcript = transcribe_all(
                chunks,
                language,
            )

            if not transcript or not transcript.strip():
                raise RuntimeError(
                    "The transcription was empty. "
                    "Please check that the uploaded file contains speech."
                )

            # ─────────────────────────────────────────────────────────────────
            # STEP 3 — TITLE
            # ─────────────────────────────────────────────────────────────────
            st.write("🏷️ Generating title…")

            title = generate_title(transcript)

            # ─────────────────────────────────────────────────────────────────
            # STEP 4 — SUMMARY
            # ─────────────────────────────────────────────────────────────────
            st.write("📋 Summarising…")

            summary = summarize(transcript)

            # ─────────────────────────────────────────────────────────────────
            # STEP 5 — EXTRACT INSIGHTS
            # ─────────────────────────────────────────────────────────────────
            st.write("🔍 Extracting action items, decisions & questions…")

            action_items = extract_action_items(transcript)
            decisions = extract_key_decisions(transcript)
            questions = extract_questions(transcript)

            # ─────────────────────────────────────────────────────────────────
            # STEP 6 — RAG
            # ─────────────────────────────────────────────────────────────────
            st.write("🧠 Building chat engine…")

            rag_chain = build_rag_chain(transcript)

            # ─────────────────────────────────────────────────────────────────
            # STORE RESULT
            # ─────────────────────────────────────────────────────────────────
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

            status.update(
                label="✅ Analysis complete",
                state="complete",
                expanded=False,
            )

        except Exception as e:

            status.update(
                label="❌ Pipeline failed",
                state="error",
                expanded=True,
            )

            # More useful error messages for users
            if input_mode == "YouTube URL":
                error_text = str(e)

                if (
                    "403" in error_text
                    or "Forbidden" in error_text
                    or "DownloadError" in error_text
                ):
                    st.error(
                        "YouTube refused the download request (HTTP 403). "
                        "Please try another public YouTube video. "
                        "If this happens for every public video, "
                        "the YouTube/yt-dlp configuration needs to be updated."
                    )
                    st.caption("The rest of the AI pipeline was not started.")

                else:
                    st.error("Could not process the YouTube video.")
                    st.exception(e)

            else:

                st.error(
                    "Could not process the uploaded file. "
                    "Please make sure the file is a supported video/audio "
                    "format and contains playable audio."
                )

                st.exception(e)

            # Cleanup uploaded file if processing failed
            if uploaded_source_path:
                cleanup_file(uploaded_source_path)

            st.stop()

        finally:
            if uploaded_source_path:
                cleanup_file(uploaded_source_path)

    st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# RESULTS
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.result:

    r = st.session_state.result

    # ─────────────────────────────────────────────────────────────────────────
    # TITLE
    # ─────────────────────────────────────────────────────────────────────────
    st.subheader(r["title"])

    # ─────────────────────────────────────────────────────────────────────────
    # METRICS
    # ─────────────────────────────────────────────────────────────────────────
    def _word_count(text: str) -> int:
        return len((text or "").split())


    def _line_count(text: str) -> int:
        return len(
            [
                line
                for line in (text or "").split("\n")
                if line.strip()
            ]
        )


    m1, m2, m3, m4 = st.columns(4)

    m1.metric(
        "Transcript length",
        f"{_word_count(r['transcript']):,} words",
    )

    m2.metric(
        "Action items",
        _line_count(r["action_items"]),
    )

    m3.metric(
        "Key decisions",
        _line_count(r["key_decisions"]),
    )

    m4.metric(
        "Open questions",
        _line_count(r["open_questions"]),
    )

    st.divider()

    # ─────────────────────────────────────────────────────────────────────────
    # TABS
    # ─────────────────────────────────────────────────────────────────────────
    (
        tab_summary,
        tab_actions,
        tab_decisions,
        tab_questions,
        tab_transcript,
        tab_chat,
    ) = st.tabs(
        [
            "📋 Summary",
            "✅ Action Items",
            "🔑 Decisions",
            "❓ Questions",
            "📝 Transcript",
            "💬 Chat",
        ]
    )

    # ─────────────────────────────────────────────────────────────────────────
    # SUMMARY
    # ─────────────────────────────────────────────────────────────────────────
    with tab_summary:
        st.markdown(r["summary"])

    # ─────────────────────────────────────────────────────────────────────────
    # ACTION ITEMS
    # ─────────────────────────────────────────────────────────────────────────
    with tab_actions:
        st.markdown(r["action_items"])

    # ─────────────────────────────────────────────────────────────────────────
    # DECISIONS
    # ─────────────────────────────────────────────────────────────────────────
    with tab_decisions:
        st.markdown(r["key_decisions"])

    # ─────────────────────────────────────────────────────────────────────────
    # QUESTIONS
    # ─────────────────────────────────────────────────────────────────────────
    with tab_questions:
        st.markdown(r["open_questions"])

    # ─────────────────────────────────────────────────────────────────────────
    # TRANSCRIPT
    # ─────────────────────────────────────────────────────────────────────────
    with tab_transcript:

        st.text_area(
            "Full transcript",
            r["transcript"],
            height=400,
            label_visibility="collapsed",
        )

        st.download_button(
            "⬇️ Download transcript (.txt)",
            data=r["transcript"],
            file_name="transcript.txt",
            mime="text/plain",
        )

    # ─────────────────────────────────────────────────────────────────────────
    # RAG CHAT
    # ─────────────────────────────────────────────────────────────────────────
    with tab_chat:

        st.caption(
            "Ask anything about this meeting — grounded in the transcript."
        )

        # Existing chat history
        for msg in st.session_state.chat_history:

            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # New question
        if prompt := st.chat_input(
            "What were the main decisions made?"
        ):

            # User message
            st.session_state.chat_history.append(
                {
                    "role": "user",
                    "content": prompt,
                }
            )
            with st.chat_message("user"):
                st.markdown(prompt)

            # Assistant response
            with st.chat_message("assistant"):
                with st.spinner("Thinking…"):

                    try:
                        answer = ask_question(
                            r["rag_chain"],
                            prompt,
                        )

                    except Exception as e:
                        answer = (
                            "Sorry, I couldn't answer that question. "
                            "Please try again."
                        )

                        st.error(str(e))

                st.markdown(answer)

            st.session_state.chat_history.append(
                {
                    "role": "assistant",
                    "content": answer,
                }
            )

        # Clear chat
        if st.session_state.chat_history:
            if st.button("🗑️ Clear chat"):
                st.session_state.chat_history = []
                st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# EMPTY STATE
# ─────────────────────────────────────────────────────────────────────────────
else:

    st.markdown(
        """
        <div class="empty-state">
            <div class="emoji">🎬</div>
            <h3>Ready to analyse</h3>
            <p>
                Choose a YouTube URL or upload a meeting video/audio file,
                select your language, and hit <strong>Analyse</strong>
                to get started.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
