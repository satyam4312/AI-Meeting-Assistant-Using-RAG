import os
import re
from html import escape
from pathlib import Path
import streamlit as st

from dotenv import load_dotenv
load_dotenv(override = True)

# Streamlit Community Cloud exposes configured keys through st.secrets rather
# than automatically exporting them as environment variables.
for secret_name in ("GROQ_API_KEY", "SARVAM_API_KEY"):
    if not os.getenv(secret_name):
        try:
            secret_value = st.secrets.get(secret_name)
        except Exception:
            secret_value = None
        if secret_value:
            os.environ[secret_name] = str(secret_value)

from utils.audio_processor import process_input, YouTubeDownloadError
from core.transcriber import transcribe_all
from core.summarizer import summarize, generate_title
from core.extractor import extract_all
from core.rag_engine import build_rag_chain, ask_question

st.set_page_config(
    page_title = "AI Video Meeting Assistant",
    page_icon = "🎬",
    layout = "wide",
    initial_sidebar_state = "expanded",
)

st.markdown(
    """
    <style>
        :root { --ink:#f3f2f8; --muted:#9b9ca8; --line:#2d303a; --accent:#ff4d57; }
        [data-testid="stAppViewContainer"] { background:#0c0d12; color:var(--ink); }
        [data-testid="stHeader"] { background:#0c0d12; }
        [data-testid="stSidebar"] { background:#23252e; border-right:1px solid #343641; }
        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap:.65rem; }
        [data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] .stMarkdown { color:#d8d8e0; }
        .block-container { max-width:1480px; padding:1.35rem clamp(1.25rem,4vw,3.6rem) 3.5rem; }
        h1, h2, h3, h4 { color:var(--ink); letter-spacing:-.035em; }
        p, .stCaption { color:#a5a6b2; }
        [data-testid="stSidebar"] input, [data-testid="stSidebar"] [data-baseweb="select"] > div { background:#11131a; border-color:#383a45; color:#f3f2f8; border-radius:10px; }
        [data-testid="stSidebar"] [data-testid="stFileUploader"] section { background:#1a1c24; border:1px dashed #555762; border-radius:12px; }
        [data-testid="stSidebar"] [data-testid="stFileUploader"] small, [data-testid="stSidebar"] [data-testid="stFileUploader"] span { color:#b5b5c0; }
        .side-brand { color:#f7f6fb; font-size:1.05rem; font-weight:760; letter-spacing:-.02em; }
        .side-brand span { display:inline-grid; place-items:center; width:30px; height:30px; margin-right:.5rem; border-radius:9px; background:#393746; }
        .side-tagline { color:#a1a2ad; font-size:.85rem; margin-top:.35rem; }
        .app-heading { margin:0; color:#f4f2fa; font-size:clamp(2rem,3vw,2.65rem); line-height:1.12; font-weight:780; letter-spacing:-.045em; }
        .app-subtitle { margin:.55rem 0 2.35rem; color:#a6a7b5; font-size:1rem; }
        .report-title { color:#f4f2fa; font-size:clamp(1.55rem,2.4vw,2rem); font-weight:770; line-height:1.2; letter-spacing:-.035em; margin:.25rem 0 1.15rem; }
        [data-testid="stMetric"] { min-height:100px; background:#14161d; border:1px solid #292c36; border-radius:13px; padding:1rem 1.1rem; }
        [data-testid="stMetricLabel"] { color:#c2c2cc; font-weight:550; font-size:.88rem; }
        [data-testid="stMetricValue"] { color:#f5f4f9; font-weight:650; font-size:clamp(1.7rem,2.4vw,2.5rem); }
        [data-testid="stTabs"] [data-baseweb="tab-list"] { gap:.7rem; border-bottom:1px solid #333640; margin-top:1.8rem; }
        [data-testid="stTabs"] button[data-baseweb="tab"] { color:#c6c6cf; font-weight:600; }
        [data-testid="stTabs"] button[aria-selected="true"] { color:#ff6670; }
        [data-testid="stTabs"] [data-baseweb="tab-highlight"] { background:#ff4d57; height:2px; }
        div.stButton > button[kind="primary"] { background:#ff4d57; color:white; border:0; border-radius:10px; min-height:2.8rem; font-weight:680; }
        div.stButton > button[kind="primary"]:hover { background:#e83e49; color:#fff; border:0; }
        [data-testid="stSidebar"] div.stButton > button[kind="primary"] { background:#ff4d57; }
        [data-testid="stSidebar"] div.stButton > button:not([kind="primary"]) { background:transparent; color:#f1f0f5; border:1px solid #50525d; border-radius:10px; min-height:2.65rem; }
        [data-testid="stVerticalBlockBorderWrapper"] { background:#14161d; border:1px solid #292c36; border-radius:14px; }
        [data-testid="stChatMessage"] { background:#14161d; border:1px solid #292c36; border-radius:13px; }
        [data-testid="stTextArea"] textarea { border-radius:10px; background:#11131a; color:#f3f2f8; line-height:1.65; }
        .eyebrow { color:#a8a9b5; font-size:.72rem; font-weight:700; letter-spacing:.11em; text-transform:uppercase; }
        .report-subtitle { color:#a4a5b1; margin:0; }
        @media (max-width:850px) { .block-container { padding:1.3rem 1.15rem 3rem; } [data-testid="stTabs"] [data-baseweb="tab-list"] { gap:.15rem; } [data-testid="stTabs"] button[data-baseweb="tab"] { padding-left:.55rem; padding-right:.55rem; font-size:.82rem; } }
    </style>
    """,
    unsafe_allow_html = True,
)

defaults = {
    "processed": False,
    "transcript": "",
    "title": "",
    "summary": "",
    "actions": [],
    "decisions": [],
    "questions": [],
    "rag_chain": None,
    "chat_history": [],
}


def result_count(value):
    """Count structured items returned by the extraction prompts."""
    if isinstance(value, (list, tuple)):
        return len(value)
    text = str(value or "").strip()
    if not text or text.lower().startswith(("no ", "error:")):
        return 0
    numbered_items = re.findall(r"(?m)^\s*(?:\d+[.)]|[-*•])\s+", text)
    return len(numbered_items) if numbered_items else 1


for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

st.sidebar.markdown(
    '<div class="side-brand"><span>🎬</span> AI Video Assistant</div>'
    '<div class="side-tagline">Meeting intelligence, end to end.</div>',
    unsafe_allow_html=True,
)
st.sidebar.markdown("---")
st.sidebar.markdown("**YouTube URL or file**")
youtube_url = st.sidebar.text_input(
    "YouTube URL",
    placeholder="Paste a YouTube link...",
    label_visibility="collapsed",
    key="youtube_url_input",
)
uploaded_file = st.sidebar.file_uploader(
    label="Upload meeting audio/video",
    type=["mp4", "mov", "mkv", "avi", "webm", "mp3", "wav", "m4a", "aac", "flac", "ogg"],
    help="Choose an audio or video file.",
    key="meeting_file_input",
)
language = st.sidebar.selectbox(
    "Language",
    options=["English", "Hinglish"],
    index=0,
    help="Hinglish uses Sarvam AI; English uses Whisper.",
)
process_button = st.sidebar.button("⚡  Analyse meeting", type="primary", use_container_width=True)
st.sidebar.markdown("---")
if st.sidebar.button("📁  New session", use_container_width=True):
    st.session_state.clear()
    st.rerun()

st.markdown(
    '<h1 class="app-heading">AI Video Assistant</h1>'
    '<p class="app-subtitle">Transcribe · Summarise · Chat with your meetings</p>',
    unsafe_allow_html=True,
)

if not st.session_state.processed:
    with st.container(border=True):
        st.markdown('<div class="eyebrow">Your workspace</div>', unsafe_allow_html=True)
        st.subheader("Your meeting brief will appear here")
        st.caption("Add a YouTube link or upload a recording from the sidebar to get started.")
        st.markdown("**Transcript**  ·  **Summary**  ·  **Action items**  ·  **Decisions**  ·  **Meeting chat**")

if process_button:
    if not os.getenv("GROQ_API_KEY"):
        st.error(
            "GROQ_API_KEY is missing. Add it in Streamlit Cloud under "
            "App settings → Secrets, then restart the app."
        )
        st.stop()

    source = None

    if youtube_url.strip():
        source = youtube_url.strip()

    elif uploaded_file is not None:
        upload_dir = Path("uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        uploaded_path = upload_dir / uploaded_file.name
        try:
            with open(uploaded_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            source = str(uploaded_path)
        except Exception as e:
            st.error("❌ Could not save the uploaded file.")
            st.exception(e)
            st.stop()

    else:
        st.warning("Please enter a YouTube URL or upload an audio/video file.")
        st.stop()

    try:
        with st.status("🎧 Processing audio/video...", expanded=True) as status:
            st.write("Extracting and preparing audio...")
            chunks = process_input(source)
            st.write(f"Created **{len(chunks)} audio chunk(s)**.")
            status.update(label = "✅ Audio processing complete", state = "complete")
    except YouTubeDownloadError:
        st.error("🚫 YouTube is currently preventing automated access to this video.")
        st.info(
            "**Please upload the audio/video file instead.**\n\n"
            "Download the video or audio from YouTube using a method available to you, "
            "then upload the file in the section above.\n\n"
            "The rest of the AI Meeting Assistant pipeline will work normally."
        )
        st.stop()
    except Exception as e:
        st.error("❌ An unexpected error occurred while processing the audio/video.")
        st.exception(e)
        st.stop()

    try:
        with st.status("🎙️ Transcribing meeting...", expanded=True) as status:
            st.write("Running speech-to-text...")
            transcript = transcribe_all(chunks, language=language.lower())
            if not transcript:
                st.error("No transcript was generated.")
                st.stop()
            st.write(f"Transcript generated: **{len(transcript.split()):,} words**")
            status.update(label = "✅ Transcription complete", state = "complete")
    except Exception as e:
        st.error("❌ Transcription failed.")
        st.exception(e)
        st.stop()

    try:
        with st.status("🧠 Generating meeting summary...", expanded=True) as status:
            title = generate_title(transcript)
            summary = summarize(transcript)
            status.update(label = "✅ Summary generated", state = "complete")
    except Exception as e:
        st.error("❌ Summary generation failed.")
        st.exception(e)
        st.stop()

    try:
        with st.status("📋 Extracting meeting information...", expanded=True) as status:
            extracted = extract_all(transcript)
            actions = extracted.get("action_items", extracted.get("actions", []))
            decisions = extracted.get("key_decisions", extracted.get("decisions", []))
            questions = extracted.get("open_questions", extracted.get("questions", []))
            status.update(label = "✅ Meeting information extracted", state = "complete")
    except Exception as e:
        st.error("❌ Information extraction failed.")
        st.exception(e)
        st.stop()

    try:
        with st.status("🔎 Building meeting knowledge base...", expanded=True) as status:
            rag_chain = build_rag_chain(transcript)
            status.update(label = "✅ RAG knowledge base ready", state = "complete")
    except Exception as e:
        st.error("❌ RAG initialization failed.")
        st.exception(e)
        st.stop()

    st.session_state.title = title
    st.session_state.transcript = transcript
    st.session_state.summary = summary
    st.session_state.actions = actions
    st.session_state.decisions = decisions
    st.session_state.questions = questions
    st.session_state.rag_chain = rag_chain
    st.session_state.chat_history = []
    st.session_state.processed = True

    st.success("Meeting brief is ready.")
    st.rerun()

if st.session_state.processed:
    st.write("")

    with st.container(border=True):
        st.markdown('<div class="eyebrow">Your meeting brief</div>', unsafe_allow_html=True)
        report_title = escape(st.session_state.title or "Meeting notes")
        st.markdown(f'<div class="report-title">{report_title}</div>', unsafe_allow_html=True)
        st.markdown('<p class="report-subtitle">A searchable record of what was discussed and what happens next.</p>', unsafe_allow_html=True)

    transcript_words = len(st.session_state.transcript.split())
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Transcript", f"{transcript_words:,} words")
    with col2:
        st.metric("Action items", result_count(st.session_state.actions))
    with col3:
        st.metric("Decisions", result_count(st.session_state.decisions))
    with col4:
        st.metric("Open questions", result_count(st.session_state.questions))

    st.write("")

    summary_tab, actions_tab, decisions_tab, questions_tab, transcript_tab, chat_tab = st.tabs(
        ["Summary", "Action items", "Decisions", "Open questions", "Transcript", "Ask the meeting"]
    )

    with summary_tab:
        with st.container(border = True):
            st.subheader("Meeting summary")
            st.markdown(st.session_state.summary)

    with actions_tab:
        with st.container(border = True):
            st.subheader("Action items")
            actions = st.session_state.actions
            if result_count(actions) == 0:
                st.info("No action items were identified.")
            else:
                st.markdown(str(actions))

    with decisions_tab:
        with st.container(border = True):
            st.subheader("Key decisions")
            decisions = st.session_state.decisions
            if result_count(decisions) == 0:
                st.info("No key decisions were identified.")
            else:
                st.markdown(str(decisions))

    with questions_tab:
        with st.container(border = True):
            st.subheader("Open questions & follow-ups")
            questions = st.session_state.questions
            if result_count(questions) == 0:
                st.info("No unresolved questions were identified.")
            else:
                st.markdown(str(questions))

    with transcript_tab:
        with st.container(border = True):
            st.subheader("Full transcript")
            st.download_button(
                "Download transcript",
                data = st.session_state.transcript,
                file_name = f"{st.session_state.title or 'transcript'}.txt",
                mime = "text/plain",
            )
            st.text_area("Transcript", value = st.session_state.transcript, height = 560, label_visibility = "collapsed")

    with chat_tab:
        with st.container(border = True):
            st.subheader("Ask the meeting")
            st.caption("Ask about a decision, a person’s next step, or anything discussed in the recording.")

            for message in st.session_state.chat_history:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            question = st.chat_input("Ask something about the meeting...")
            if question:
                st.session_state.chat_history.append({"role": "user", "content": question})
                with st.chat_message("user"):
                    st.markdown(question)

                with st.chat_message("assistant"):
                    with st.spinner("Thinking..."):
                        try:
                            answer = ask_question(st.session_state.rag_chain, question)
                            st.markdown(answer)
                            st.session_state.chat_history.append({"role": "assistant", "content": answer})
                        except Exception as e:
                            st.error("❌ Unable to answer the question.")
                            st.exception(e) 
