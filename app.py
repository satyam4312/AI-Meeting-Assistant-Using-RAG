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
    page_icon = "✳️",
    layout = "wide",
    initial_sidebar_state = "collapsed",
)

st.markdown(
    """
    <style>
        :root { --ink: #18332f; --muted: #71817d; --line: #e4e9e5; }
        [data-testid="stAppViewContainer"] { background: #f5f7f3; }
        [data-testid="stHeader"] { background: transparent; }
        .block-container { max-width: 1160px; padding: 2.25rem 2rem 4rem; }
        h1, h2, h3 { color: var(--ink); letter-spacing: -.035em; }
        p, label, .stCaption { color: #52635f; }
        .hero { position:relative; overflow:hidden; color:#f8fbf5; padding:2.2rem 2.5rem; margin:0 0 1.4rem; border:1px solid rgba(255,255,255,.1); border-radius:24px; background:radial-gradient(circle at 88% 5%, rgba(197,239,120,.25), transparent 26%), linear-gradient(120deg,#163632 0%,#244b43 58%,#315d50 100%); box-shadow:0 18px 45px rgba(25,55,48,.13); }
        .hero-kicker { color:#c5ef78; font-size:.72rem; font-weight:800; letter-spacing:.16em; text-transform:uppercase; }
        .hero h1 { color:#fff; font-size:clamp(2rem,4vw,3.15rem); line-height:1.08; margin:.55rem 0 .65rem; }
        .hero p { color:#d2e1d9; max-width:610px; font-size:1.02rem; margin:0; }
        .hero-steps { display:flex; flex-wrap:wrap; gap:.55rem; margin-top:1.45rem; }
        .hero-steps span { color:#eaf2e9; border:1px solid rgba(255,255,255,.18); background:rgba(255,255,255,.07); border-radius:999px; padding:.36rem .75rem; font-size:.79rem; }
        [data-testid="stVerticalBlockBorderWrapper"] { background:#fff; border:1px solid var(--line); border-radius:18px; box-shadow:0 6px 20px rgba(30,55,46,.035); }
        [data-testid="stMetric"] { background:#fff; border:1px solid var(--line); border-radius:16px; padding:1rem 1.15rem; }
        [data-testid="stMetricLabel"] { color:var(--muted); font-weight:650; }
        [data-testid="stMetricValue"] { color:var(--ink); font-weight:780; }
        [data-testid="stTabs"] [data-baseweb="tab-list"] { gap:.45rem; border-bottom:1px solid var(--line); }
        [data-testid="stTabs"] button[data-baseweb="tab"] { color:#657570; font-weight:650; border-radius:10px 10px 0 0; }
        [data-testid="stTabs"] button[aria-selected="true"] { color:var(--ink); }
        div.stButton > button[kind="primary"] { background:#244b43; color:#fff; border:0; border-radius:12px; min-height:3rem; font-weight:750; box-shadow:0 7px 18px rgba(36,75,67,.18); }
        div.stButton > button[kind="primary"]:hover { background:#183c35; color:#fff; border:0; }
        [data-testid="stFileUploader"] section { background:#f8faf7; border:1px dashed #bccac1; border-radius:14px; }
        [data-testid="stChatMessage"] { border:1px solid var(--line); border-radius:16px; }
        [data-testid="stTextArea"] textarea { border-radius:12px; background:#fbfcfa; line-height:1.65; }
        .eyebrow { color:#7c8b85; font-size:.72rem; font-weight:800; letter-spacing:.13em; text-transform:uppercase; }
        .report-title { color:#18332f; font-size:clamp(1.65rem,3vw,2.25rem); font-weight:800; line-height:1.15; letter-spacing:-.04em; margin:.35rem 0 .45rem; }
        .report-subtitle { color:#71817d; margin:0; }
        @media (max-width:700px) { .block-container { padding:1.2rem 1rem 3rem; } .hero { padding:1.6rem 1.35rem; border-radius:19px; } }
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

st.markdown(
    """
    <div class="hero">
        <div class="hero-kicker">Meeting intelligence, made simple</div>
        <h1>Make every meeting<br>easier to remember.</h1>
        <p>Turn a recording into clear notes, decisions, action items, and answers you can find later.</p>
        <div class="hero-steps">
            <span>01 &nbsp; Transcribe</span><span>02 &nbsp; Summarize</span>
            <span>03 &nbsp; Find next steps</span><span>04 &nbsp; Ask anything</span>
        </div>
    </div>
    """,
    unsafe_allow_html = True,
)

with st.container(border=True):
    st.markdown('<div class="eyebrow">Start with a recording</div>', unsafe_allow_html=True)
    st.subheader("Bring your meeting in")
    st.caption("Paste a YouTube link or choose an audio/video file. We’ll turn it into a searchable meeting brief.")
    youtube_url = ""
    uploaded_file = None
    source_tab_url, source_tab_upload = st.tabs(["YouTube link", "Upload a file"])
    with source_tab_url:
        youtube_url = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=...", label_visibility="collapsed")
    with source_tab_upload:
        uploaded_file = st.file_uploader(
            "Choose an audio or video file",
            type=["mp4", "mov", "mkv", "avi", "webm", "mp3", "wav", "m4a", "aac", "flac", "ogg"],
            label="Recording file",
        )
    st.write("")
    process_button = st.button("Create meeting brief", type="primary", use_container_width=True)
    st.caption("Your transcript, summary, and action items will appear here after processing.")

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
            transcript = transcribe_all(chunks)
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
