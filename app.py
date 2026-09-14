import os
from pathlib import Path
import streamlit as st

from dotenv import load_dotenv
load_dotenv(override = True)

from utils.audio_processor import process_input, YouTubeDownloadError
from core.transcriber import transcribe_all
from core.summarizer import summarize, generate_title
from core.extractor import extract_all
from core.rag_engine import build_rag_chain, ask_question

st.set_page_config(
    page_title = "AI Video Meeting Assistant",
    page_icon = "🎥",
    layout = "wide",
    initial_sidebar_state = "collapsed",
)

st.markdown(
    """
    <style>
        .block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1100px; }
        .hero {
            background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 50%, #EC4899 100%);
            border-radius: 18px;
            padding: 2.2rem 2.5rem;
            margin-bottom: 1.6rem;
            color: white;
            box-shadow: 0 10px 28px rgba(99, 102, 241, 0.3);
        }
        .hero h1 { margin: 0 0 0.4rem 0; font-size: 2.1rem; font-weight: 800; color: white; }
        .hero p { margin: 0; font-size: 1.02rem; opacity: 0.92; }
        .pipeline { margin-top: 1.1rem; display: flex; flex-wrap: wrap; gap: 0.5rem; font-size: 0.9rem; }
        .pipeline span { background: rgba(255, 255, 255, 0.18); padding: 0.3rem 0.85rem; border-radius: 999px; font-weight: 600; }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 16px !important;
        }
        div[data-testid="column"] div[data-testid="stVerticalBlockBorderWrapper"] {
            height: 100%;
        }

        .card-title {
            font-size: 1.08rem;
            font-weight: 700;
            margin-bottom: 0.8rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        div[data-testid="stMetric"] {
            background: var(--secondary-background-color);
            border: 1px solid rgba(128, 128, 128, 0.2);
            border-radius: 14px;
            padding: 1rem 1.1rem;
        }

        div.stButton > button[kind="primary"] {
            border-radius: 12px;
            font-weight: 700;
            padding: 0.75rem 1.2rem;
            font-size: 1.02rem;
            box-shadow: 0 4px 14px rgba(99, 102, 241, 0.35);
            border: none;
        }

        .item-card {
            border: 1px solid rgba(128, 128, 128, 0.2);
            border-radius: 12px;
            padding: 0.95rem 1.2rem;
            margin-bottom: 0.7rem;
            background: var(--secondary-background-color);
        }
        .item-card:last-child { margin-bottom: 0; }
        .item-card h4 { margin: 0 0 0.4rem 0; font-size: 1.02rem; }
        .item-meta { display: flex; gap: 1.5rem; font-size: 0.87rem; opacity: 0.8; margin-top: 0.35rem; }
        .badge { display: inline-block; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.03em; padding: 0.15rem 0.6rem; border-radius: 999px; }
        .badge-decision { background: rgba(16, 185, 129, 0.18); color: #10B981; }
        .badge-question { background: rgba(245, 158, 11, 0.18); color: #F59E0B; }

        button[data-baseweb="tab"] { font-weight: 600; }
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
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

st.markdown(
    """
    <div class="hero">
        <h1>🎥 AI Video Meeting Assistant</h1>
        <p>Turn meeting recordings into searchable, actionable knowledge.</p>
        <div class="pipeline">
            <span>🎙️ Transcribe</span>
            <span>🧠 Summarize</span>
            <span>✅ Extract Actions</span>
            <span>💬 Ask Questions</span>
        </div>
    </div>
    """,
    unsafe_allow_html = True,
)

with st.container(border = True):
    st.markdown('<div class="card-title">🎬 Meeting Input</div>', unsafe_allow_html = True)
    st.caption("Provide a **YouTube URL** or upload an **audio/video file**.")

    input_col1, input_col2 = st.columns(2, gap = "large")
    with input_col1:
        st.markdown("**🔗 YouTube URL**")
        youtube_url = st.text_input(
            "YouTube URL", placeholder="https://www.youtube.com/watch?v=...", label_visibility = "collapsed"
        )
    with input_col2:
        st.markdown("**📁 Audio/video file**")
        uploaded_file = st.file_uploader(
            "Upload audio/video file",
            type = ["mp4", "mov", "mkv", "avi", "webm", "mp3", "wav", "m4a", "aac", "flac", "ogg"],
            label_visibility = "collapsed",
        )

    st.write("")
    process_button = st.button("🚀 Process Meeting", type = "primary", use_container_width = True)

if process_button:
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
            actions = extracted.get("actions", [])
            decisions = extracted.get("decisions", [])
            questions = extracted.get("questions", [])
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

    st.success("🎉 Meeting processed successfully!")
    st.balloons()
    st.rerun()

if st.session_state.processed:
    st.write("")

    with st.container(border=True):
        st.markdown(
            f"""
            <div style="text-align:center;">
                <div style="font-size:0.82rem; font-weight:700; letter-spacing:0.06em;
                            text-transform:uppercase; opacity:0.55; margin-bottom:0.3rem;">
                    Meeting Report
                </div>
                <div style="font-size:1.7rem; font-weight:800;">
                    {st.session_state.title}
                </div>
            </div>
            """,
            unsafe_allow_html = True,
        )

    transcript_words = len(st.session_state.transcript.split())
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📄 Transcript Length", f"{transcript_words:,} words")
    with col2:
        st.metric("✅ Action Items", len(st.session_state.actions))
    with col3:
        st.metric("🎯 Key Decisions", len(st.session_state.decisions))
    with col4:
        st.metric("❓ Open Questions", len(st.session_state.questions))

    st.write("")

    summary_tab, actions_tab, decisions_tab, questions_tab, transcript_tab, chat_tab = st.tabs(
        ["📝 Summary", "✅ Action Items", "🎯 Decisions", "❓ Questions", "📄 Transcript", "💬 Chat"]
    )

    with summary_tab:
        with st.container(border = True):
            st.markdown('<div class = "card-title">📝 Meeting Summary</div>', unsafe_allow_html = True)
            st.markdown(st.session_state.summary)

    with actions_tab:
        with st.container(border = True):
            st.markdown('<div class="card-title">✅ Action Items</div>', unsafe_allow_html = True)
            actions = st.session_state.actions
            if not actions:
                st.info("No action items were identified.")
            else:
                for i, action in enumerate(actions, start=1):
                    if isinstance(action, dict):
                        task = action.get("task", action.get("action", "Action"))
                        owner = action.get("owner", "Not specified")
                        deadline = action.get("deadline", "Not specified")
                        st.markdown(
                            f"""
                            <div class="item-card">
                                <h4>{i}. {task}</h4>
                                <div class="item-meta">
                                    <span>👤 <b>Owner:</b> {owner}</span>
                                    <span>📅 <b>Deadline:</b> {deadline}</span>
                                </div>
                            </div>
                            """,
                            unsafe_allow_html = True,
                        )
                    else:
                        st.markdown(f'<div class="item-card"><h4>{i}. {action}</h4></div>', unsafe_allow_html = True)

    with decisions_tab:
        with st.container(border = True):
            st.markdown('<div class = "card-title">🎯 Key Decisions</div>', unsafe_allow_html = True)
            decisions = st.session_state.decisions
            if not decisions:
                st.info("No key decisions were identified.")
            else:
                for i, decision in enumerate(decisions, start = 1):
                    st.markdown(
                        f"""
                        <div class = "item-card">
                            <span class = "badge badge-decision">DECISION {i}</span>
                            <p style = "margin-top:0.5rem; margin-bottom:0;">{decision}</p>
                        </div>
                        """,
                        unsafe_allow_html = True,
                    )

    with questions_tab:
        with st.container(border = True):
            st.markdown('<div class = "card-title">❓ Open Questions & Follow-ups</div>', unsafe_allow_html = True)
            questions = st.session_state.questions
            if not questions:
                st.info("No unresolved questions were identified.")
            else:
                for i, question in enumerate(questions, start = 1):
                    st.markdown(
                        f"""
                        <div class = "item-card">
                            <span class = "badge badge-question">Q{i}</span>
                            <p style = "margin-top:0.5rem; margin-bottom:0;">{question}</p>
                        </div>
                        """,
                        unsafe_allow_html = True,
                    )

    with transcript_tab:
        with st.container(border = True):
            st.markdown('<div class="card-title">📄 Full Meeting Transcript</div>', unsafe_allow_html = True)
            st.download_button(
                "⬇️ Download transcript (.txt)",
                data = st.session_state.transcript,
                file_name = f"{st.session_state.title or 'transcript'}.txt",
                mime = "text/plain",
            )
            st.text_area("Transcript", value = st.session_state.transcript, height = 560, label_visibility = "collapsed")

    with chat_tab:
        with st.container(border = True):
            st.markdown('<div class="card-title">💬 Chat with your meeting</div>', unsafe_allow_html = True)
            st.caption("Ask questions about the meeting. Answers are generated from the meeting transcript.")

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
