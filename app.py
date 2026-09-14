import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv


# ============================================================
# LOAD ENVIRONMENT VARIABLES FIRST
# ============================================================

load_dotenv(override=True)


# ============================================================
# PROJECT IMPORTS
# ============================================================

from utils.audio_processor import (
    process_input,
    YouTubeDownloadError,
)

from core.transcriber import transcribe_all
from core.summarizer import summarize, generate_title
from core.extractor import extract_all
from core.rag_engine import build_rag_chain, ask_question


# ============================================================
# STREAMLIT CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="AI Video Meeting Assistant",
    page_icon="🎥",
    layout="wide",
)


# ============================================================
# SESSION STATE
# ============================================================

if "processed" not in st.session_state:
    st.session_state.processed = False

if "transcript" not in st.session_state:
    st.session_state.transcript = ""

if "title" not in st.session_state:
    st.session_state.title = ""

if "summary" not in st.session_state:
    st.session_state.summary = ""

if "actions" not in st.session_state:
    st.session_state.actions = []

if "decisions" not in st.session_state:
    st.session_state.decisions = []

if "questions" not in st.session_state:
    st.session_state.questions = []

if "rag_chain" not in st.session_state:
    st.session_state.rag_chain = None

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


# ============================================================
# PAGE HEADER
# ============================================================

st.title("🎥 AI Video Meeting Assistant")

st.markdown(
    """
    **Turn meeting recordings into searchable, actionable knowledge.**

    🎙️ Transcribe &nbsp;&nbsp;→&nbsp;&nbsp;
    🧠 Summarize &nbsp;&nbsp;→&nbsp;&nbsp;
    ✅ Extract Actions &nbsp;&nbsp;→&nbsp;&nbsp;
    💬 Ask Questions
    """
)

st.divider()


# ============================================================
# INPUT SECTION
# ============================================================

st.subheader("🎬 Meeting Input")

st.markdown(
    """
    Provide a **YouTube URL** or upload an **audio/video file**.

    > ⚠️ YouTube may restrict automated access to some videos.
    > If a YouTube URL cannot be downloaded, upload the audio/video
    > file instead.
    """
)


youtube_url = st.text_input(
    "YouTube URL",
    placeholder="https://www.youtube.com/watch?v=...",
)


st.markdown("### OR")


uploaded_file = st.file_uploader(
    "Upload audio/video file",
    type=[
        "mp4",
        "mov",
        "mkv",
        "avi",
        "webm",
        "mp3",
        "wav",
        "m4a",
        "aac",
        "flac",
        "ogg",
    ],
)


# ============================================================
# PROCESSING BUTTON
# ============================================================

process_button = st.button(
    "🚀 Process Meeting",
    type="primary",
    use_container_width=True,
)


# ============================================================
# DETERMINE INPUT
# ============================================================

if process_button:

    source = None

    # --------------------------------------------------------
    # YouTube URL
    # --------------------------------------------------------

    if youtube_url.strip():

        source = youtube_url.strip()

    # --------------------------------------------------------
    # Uploaded file
    # --------------------------------------------------------

    elif uploaded_file is not None:

        upload_dir = Path("uploads")
        upload_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        uploaded_path = (
            upload_dir / uploaded_file.name
        )

        try:

            with open(
                uploaded_path,
                "wb",
            ) as f:

                f.write(
                    uploaded_file.getbuffer()
                )

            source = str(uploaded_path)

        except Exception as e:

            st.error(
                "❌ Could not save the uploaded file."
            )

            st.exception(e)

            st.stop()

    # --------------------------------------------------------
    # No input
    # --------------------------------------------------------

    else:

        st.warning(
            "Please enter a YouTube URL or upload "
            "an audio/video file."
        )

        st.stop()


    # ========================================================
    # STEP 1 — AUDIO PROCESSING
    # ========================================================

    try:

        with st.status(
            "🎧 Processing audio/video...",
            expanded=True,
        ) as status:

            st.write(
                "Extracting and preparing audio..."
            )

            chunks = process_input(source)

            st.write(
                f"Created **{len(chunks)} audio chunk(s)**."
            )

            status.update(
                label="✅ Audio processing complete",
                state="complete",
            )

    except YouTubeDownloadError:

        st.error(
            "🚫 YouTube is currently preventing "
            "automated access to this video."
        )

        st.info(
            """
            **Please upload the audio/video file instead.**

            Download the video or audio from YouTube using
            a method available to you, then upload the file
            in the section above.

            The rest of the AI Meeting Assistant pipeline
            will work normally.
            """
        )

        st.stop()

    except Exception as e:

        st.error(
            "❌ An unexpected error occurred while "
            "processing the audio/video."
        )

        st.exception(e)

        st.stop()


    # ========================================================
    # STEP 2 — TRANSCRIPTION
    # ========================================================

    try:

        with st.status(
            "🎙️ Transcribing meeting...",
            expanded=True,
        ) as status:

            st.write(
                "Running speech-to-text..."
            )

            transcript = transcribe_all(chunks)

            if not transcript:
                st.error(
                    "No transcript was generated."
                )

                st.stop()

            st.write(
                f"Transcript generated: "
                f"**{len(transcript.split()):,} words**"
            )

            status.update(
                label="✅ Transcription complete",
                state="complete",
            )

    except Exception as e:

        st.error(
            "❌ Transcription failed."
        )

        st.exception(e)

        st.stop()


    # ========================================================
    # STEP 3 — TITLE + SUMMARY
    # ========================================================

    try:

        with st.status(
            "🧠 Generating meeting summary...",
            expanded=True,
        ) as status:

            title = generate_title(
                transcript
            )

            summary = summarize(
                transcript
            )

            status.update(
                label="✅ Summary generated",
                state="complete",
            )

    except Exception as e:

        st.error(
            "❌ Summary generation failed."
        )

        st.exception(e)

        st.stop()


    # ========================================================
    # STEP 4 — ACTIONS / DECISIONS / QUESTIONS
    # ========================================================

    try:

        with st.status(
            "📋 Extracting meeting information...",
            expanded=True,
        ) as status:

            extracted = extract_all(
                transcript
            )

            # Support dictionary returned by extractor.py
            actions = extracted.get(
                "actions",
                []
            )

            decisions = extracted.get(
                "decisions",
                []
            )

            questions = extracted.get(
                "questions",
                []
            )

            status.update(
                label="✅ Meeting information extracted",
                state="complete",
            )

    except Exception as e:

        st.error(
            "❌ Information extraction failed."
        )

        st.exception(e)

        st.stop()


    # ========================================================
    # STEP 5 — BUILD RAG
    # ========================================================

    try:

        with st.status(
            "🔎 Building meeting knowledge base...",
            expanded=True,
        ) as status:

            rag_chain = build_rag_chain(
                transcript
            )

            status.update(
                label="✅ RAG knowledge base ready",
                state="complete",
            )

    except Exception as e:

        st.error(
            "❌ RAG initialization failed."
        )

        st.exception(e)

        st.stop()


    # ========================================================
    # SAVE RESULTS TO SESSION STATE
    # ========================================================

    st.session_state.title = title
    st.session_state.transcript = transcript
    st.session_state.summary = summary

    st.session_state.actions = actions
    st.session_state.decisions = decisions
    st.session_state.questions = questions

    st.session_state.rag_chain = rag_chain

    st.session_state.chat_history = []

    st.session_state.processed = True

    st.success(
        "🎉 Meeting processed successfully!"
    )

    st.rerun()


# ============================================================
# DISPLAY RESULTS
# ============================================================

if st.session_state.processed:

    # --------------------------------------------------------
    # TITLE
    # --------------------------------------------------------

    st.header(
        st.session_state.title
    )


    # --------------------------------------------------------
    # METRICS
    # --------------------------------------------------------

    transcript_words = len(
        st.session_state.transcript.split()
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Transcript Length",
            f"{transcript_words:,} words",
        )

    with col2:
        st.metric(
            "Action Items",
            len(st.session_state.actions),
        )

    with col3:
        st.metric(
            "Key Decisions",
            len(st.session_state.decisions),
        )

    with col4:
        st.metric(
            "Open Questions",
            len(st.session_state.questions),
        )


    st.divider()


    # ========================================================
    # TABS
    # ========================================================

    (
        summary_tab,
        actions_tab,
        decisions_tab,
        questions_tab,
        transcript_tab,
        chat_tab,
    ) = st.tabs(
        [
            "📝 Summary",
            "✅ Action Items",
            "🎯 Decisions",
            "❓ Questions",
            "📄 Transcript",
            "💬 Chat",
        ]
    )


    # ========================================================
    # SUMMARY TAB
    # ========================================================

    with summary_tab:

        st.subheader("Meeting Summary")

        st.markdown(
            st.session_state.summary
        )


    # ========================================================
    # ACTION ITEMS TAB
    # ========================================================

    with actions_tab:

        st.subheader("Action Items")

        actions = st.session_state.actions

        if not actions:

            st.info(
                "No action items were identified."
            )

        else:

            for i, action in enumerate(
                actions,
                start=1,
            ):

                if isinstance(action, dict):

                    st.markdown(
                        f"### {i}. "
                        f"{action.get('task', action.get('action', 'Action'))}"
                    )

                    owner = action.get(
                        "owner",
                        "Not specified",
                    )

                    deadline = action.get(
                        "deadline",
                        "Not specified",
                    )

                    st.write(
                        f"**Owner:** {owner}"
                    )

                    st.write(
                        f"**Deadline:** {deadline}"
                    )

                else:

                    st.markdown(
                        f"### {i}. {action}"
                    )

                st.divider()


    # ========================================================
    # DECISIONS TAB
    # ========================================================

    with decisions_tab:

        st.subheader("Key Decisions")

        decisions = (
            st.session_state.decisions
        )

        if not decisions:

            st.info(
                "No key decisions were identified."
            )

        else:

            for i, decision in enumerate(
                decisions,
                start=1,
            ):

                st.markdown(
                    f"### {i}. {decision}"
                )


    # ========================================================
    # QUESTIONS TAB
    # ========================================================

    with questions_tab:

        st.subheader(
            "Open Questions & Follow-ups"
        )

        questions = (
            st.session_state.questions
        )

        if not questions:

            st.info(
                "No unresolved questions were identified."
            )

        else:

            for i, question in enumerate(
                questions,
                start=1,
            ):

                st.markdown(
                    f"**{i}.** {question}"
                )


    # ========================================================
    # TRANSCRIPT TAB
    # ========================================================

    with transcript_tab:

        st.subheader(
            "Full Meeting Transcript"
        )

        st.text_area(
            "Transcript",
            value=st.session_state.transcript,
            height=600,
            label_visibility="collapsed",
        )


    # ========================================================
    # CHAT / RAG TAB
    # ========================================================

    with chat_tab:

        st.subheader(
            "💬 Chat with your meeting"
        )

        st.caption(
            "Ask questions about the meeting. "
            "Answers are generated from the meeting transcript."
        )


        # ----------------------------------------------------
        # Display previous chat
        # ----------------------------------------------------

        for message in st.session_state.chat_history:

            with st.chat_message(
                message["role"]
            ):

                st.markdown(
                    message["content"]
                )


        # ----------------------------------------------------
        # Chat input
        # ----------------------------------------------------

        question = st.chat_input(
            "Ask something about the meeting..."
        )


        if question:

            # ------------------------------------------------
            # User message
            # ------------------------------------------------

            st.session_state.chat_history.append(
                {
                    "role": "user",
                    "content": question,
                }
            )

            with st.chat_message("user"):

                st.markdown(question)


            # ------------------------------------------------
            # Generate answer
            # ------------------------------------------------

            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        answer = ask_question(
                            st.session_state.rag_chain,
                            question,
                        )
                        st.markdown(answer)
                        st.session_state.chat_history.append(
                            {
                                "role": "assistant",
                                "content": answer,
                            }
                        )
                    except Exception as e:
                        st.error("❌ Unable to answer the question.")
                        st.exception(e)