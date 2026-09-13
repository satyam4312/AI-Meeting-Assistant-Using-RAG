import os
import uuid
from pathlib import Path

import streamlit as st

from utils.audio_processor import process_input


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="AI Meeting Assistant",
    page_icon="🎙️",
    layout="wide",
)


# ============================================================
# DIRECTORIES
# ============================================================

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# SESSION STATE
# ============================================================

if "transcript" not in st.session_state:
    st.session_state.transcript = ""

if "title" not in st.session_state:
    st.session_state.title = ""

if "summary" not in st.session_state:
    st.session_state.summary = ""

if "actions" not in st.session_state:
    st.session_state.actions = ""

if "decisions" not in st.session_state:
    st.session_state.decisions = ""

if "questions" not in st.session_state:
    st.session_state.questions = ""

if "messages" not in st.session_state:
    st.session_state.messages = []


# ============================================================
# WHISPER
# ============================================================

@st.cache_resource
def load_whisper_model():

    import whisper

    # "base" is a reasonable Streamlit Cloud starting point.
    # Change to "small" if your deployment has enough RAM.
    return whisper.load_model("base")


def transcribe_chunks(chunk_paths):

    model = load_whisper_model()

    transcript_parts = []

    total = len(chunk_paths)

    progress = st.progress(0)

    for i, chunk_path in enumerate(chunk_paths):

        st.write(
            f"Transcribing chunk {i + 1} "
            f"of {total}..."
        )

        result = model.transcribe(
            chunk_path,
            fp16=False,
        )

        text = result.get(
            "text",
            "",
        ).strip()

        if text:
            transcript_parts.append(text)

        progress.progress(
            (i + 1) / total
        )

    progress.empty()

    return "\n\n".join(
        transcript_parts
    )


# ============================================================
# GROQ / AI
# ============================================================

def get_groq_model():

    api_key = os.getenv(
        "GROQ_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not configured. "
            "Add it to Streamlit Cloud Secrets."
        )

    from langchain_groq import ChatGroq

    return ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.2,
        groq_api_key=api_key,
    )


def ask_ai(prompt: str) -> str:

    llm = get_groq_model()

    response = llm.invoke(prompt)

    return response.content


# ============================================================
# TEXT HELPERS
# ============================================================

def limit_text(text, max_chars=30000):

    if not text:
        return ""

    if len(text) <= max_chars:
        return text

    return (
        text[:max_chars]
        + "\n\n[Transcript truncated for AI processing.]"
    )


# ============================================================
# AI EXTRACTION
# ============================================================

def generate_meeting_outputs(transcript):

    ai_text = limit_text(
        transcript,
        30000,
    )

    with st.spinner(
        "Generating meeting insights..."
    ):

        title = ask_ai(
            f"""
Create a short professional title for this meeting.

Transcript:
{ai_text}

Return only the title.
"""
        )

        summary = ask_ai(
            f"""
Summarize the following meeting transcript.

Requirements:
- Give a concise executive summary.
- Identify the main topics discussed.
- Mention important conclusions.
- Do not invent information.

Transcript:
{ai_text}
"""
        )

        actions = ask_ai(
            f"""
Extract all action items from this meeting.

For each action item include:
- Task
- Person responsible, if explicitly mentioned
- Deadline, if explicitly mentioned

If no owner or deadline is stated, write "Not specified".

Do not invent names or deadlines.

Transcript:
{ai_text}
"""
        )

        decisions = ask_ai(
            f"""
Extract the important decisions made during this meeting.

Use bullet points.

If no clear decisions were made, say:
"No explicit decisions identified."

Transcript:
{ai_text}
"""
        )

        questions = ask_ai(
            f"""
Extract unresolved questions, concerns, or follow-up questions
from this meeting.

Use bullet points.

If there are none, say:
"No unresolved questions identified."

Transcript:
{ai_text}
"""
        )

    return (
        title.strip(),
        summary.strip(),
        actions.strip(),
        decisions.strip(),
        questions.strip(),
    )


# ============================================================
# CHAT
# ============================================================

def answer_question(
    question,
    transcript,
):

    context = limit_text(
        transcript,
        40000,
    )

    prompt = f"""
You are an AI meeting assistant.

Answer the user's question using ONLY the meeting transcript
provided below.

Rules:
- Do not invent information.
- If the answer is not present, clearly say that it is not stated
  in the transcript.
- Be concise but useful.
- Mention relevant details when available.

MEETING TRANSCRIPT:
{context}

USER QUESTION:
{question}
"""

    return ask_ai(prompt)


# ============================================================
# HEADER
# ============================================================

st.title(
    "🎙️ AI Meeting / Video Assistant"
)

st.caption(
    "Upload a meeting recording or process a public YouTube video."
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("Input")

    input_mode = st.radio(
        "Choose input type",
        [
            "YouTube URL",
            "Upload video/audio",
        ],
    )

    youtube_url = None
    uploaded_file = None

    if input_mode == "YouTube URL":

        youtube_url = st.text_input(
            "YouTube URL",
            placeholder=(
                "https://www.youtube.com/watch?v=..."
            ),
        )

    else:

        uploaded_file = st.file_uploader(
            "Upload meeting video/audio",
            type=[
                "mp4",
                "mov",
                "mkv",
                "avi",
                "webm",
                "mpeg",
                "mpg",
                "m4v",
                "mp3",
                "wav",
                "m4a",
                "aac",
                "flac",
                "ogg",
            ],
        )

    process_button = st.button(
        "🚀 Process Meeting",
        type="primary",
        use_container_width=True,
    )


# ============================================================
# INPUT PROCESSING
# ============================================================

if process_button:

    source_path = None

    try:

        # ----------------------------------------------------
        # YOUTUBE
        # ----------------------------------------------------

        if input_mode == "YouTube URL":

            if not youtube_url:
                st.warning(
                    "Please enter a YouTube URL."
                )
                st.stop()

            source = youtube_url.strip()

            st.info(
                "Downloading YouTube audio..."
            )

        # ----------------------------------------------------
        # UPLOAD
        # ----------------------------------------------------

        else:

            if uploaded_file is None:
                st.warning(
                    "Please upload a video or audio file."
                )
                st.stop()

            extension = Path(
                uploaded_file.name
            ).suffix.lower()

            unique_name = (
                f"{uuid.uuid4().hex}"
                f"{extension}"
            )

            source_path = (
                DOWNLOAD_DIR / unique_name
            )

            with open(
                source_path,
                "wb",
            ) as f:

                f.write(
                    uploaded_file.getbuffer()
                )

            source = str(source_path)

            st.info(
                "Uploaded file received. "
                "Converting audio..."
            )

        # ----------------------------------------------------
        # AUDIO PROCESSING
        # ----------------------------------------------------

        with st.spinner(
            "Preparing audio..."
        ):

            chunk_paths = process_input(
                source
            )

        st.success(
            f"Audio prepared: "
            f"{len(chunk_paths)} chunk(s)."
        )

        # ----------------------------------------------------
        # TRANSCRIPTION
        # ----------------------------------------------------

        with st.spinner(
            "Transcribing with Whisper..."
        ):

            transcript = transcribe_chunks(
                chunk_paths
            )

        if not transcript.strip():

            st.error(
                "Whisper returned an empty transcript."
            )

            st.stop()

        st.session_state.transcript = transcript

        # ----------------------------------------------------
        # AI ANALYSIS
        # ----------------------------------------------------

        (
            title,
            summary,
            actions,
            decisions,
            questions,
        ) = generate_meeting_outputs(
            transcript
        )

        st.session_state.title = title
        st.session_state.summary = summary
        st.session_state.actions = actions
        st.session_state.decisions = decisions
        st.session_state.questions = questions

        # Reset chat for new meeting.
        st.session_state.messages = []

        st.success(
            "Meeting processing completed successfully."
        )

    except Exception as e:

        error_text = str(e)

        # ----------------------------------------------------
        # IMPORTANT YOUTUBE ERROR HANDLING
        # ----------------------------------------------------

        if (
            "403" in error_text
            or "Forbidden" in error_text
            or "YouTube download failed" in error_text
        ):

            st.error(
                "YouTube blocked the automated download request."
            )

            st.warning(
                "The AI pipeline did not start because "
                "the audio could not be downloaded."
            )

            with st.expander(
                "🔍 Technical YouTube error"
            ):

                st.code(
                    error_text,
                    language="text",
                )

            st.info(
                "If this happens for every public YouTube "
                "video, check the yt-dlp / PO-token provider "
                "installation in the Streamlit deployment."
            )

        else:

            st.error(
                "Could not process the meeting."
            )

            with st.expander(
                "Technical error"
            ):

                st.exception(e)

    finally:

        # ----------------------------------------------------
        # REMOVE UPLOADED ORIGINAL
        # ----------------------------------------------------

        if source_path:

            try:

                if os.path.exists(
                    source_path
                ):

                    os.remove(
                        source_path
                    )

            except Exception:
                pass


# ============================================================
# RESULTS
# ============================================================

if st.session_state.transcript:

    st.divider()

    st.header(
        st.session_state.title
        or "Meeting Results"
    )

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        [
            "📋 Summary",
            "✅ Action Items",
            "🎯 Decisions",
            "❓ Questions",
            "📝 Transcript",
            "💬 Ask AI",
        ]
    )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    with tab1:

        st.subheader(
            "Meeting Summary"
        )

        st.write(
            st.session_state.summary
        )

    # --------------------------------------------------------
    # ACTION ITEMS
    # --------------------------------------------------------

    with tab2:

        st.subheader(
            "Action Items"
        )

        st.write(
            st.session_state.actions
        )

    # --------------------------------------------------------
    # DECISIONS
    # --------------------------------------------------------

    with tab3:

        st.subheader(
            "Decisions"
        )

        st.write(
            st.session_state.decisions
        )

    # --------------------------------------------------------
    # QUESTIONS
    # --------------------------------------------------------

    with tab4:

        st.subheader(
            "Unresolved Questions"
        )

        st.write(
            st.session_state.questions
        )

    # --------------------------------------------------------
    # TRANSCRIPT
    # --------------------------------------------------------

    with tab5:

        st.subheader(
            "Full Transcript"
        )

        st.text_area(
            "Transcript",
            st.session_state.transcript,
            height=500,
        )

        st.download_button(
            "⬇️ Download Transcript",
            data=st.session_state.transcript,
            file_name="meeting_transcript.txt",
            mime="text/plain",
            use_container_width=True,
        )

    # --------------------------------------------------------
    # AI CHAT
    # --------------------------------------------------------

    with tab6:

        st.subheader(
            "Ask questions about the meeting"
        )

        for message in st.session_state.messages:

            with st.chat_message(
                message["role"]
            ):

                st.markdown(
                    message["content"]
                )

        user_question = st.chat_input(
            "Ask something about the meeting..."
        )

        if user_question:

            st.session_state.messages.append(
                {
                    "role": "user",
                    "content": user_question,
                }
            )

            with st.chat_message("user"):

                st.markdown(
                    user_question
                )

            try:

                with st.chat_message(
                    "assistant"
                ):

                    with st.spinner(
                        "Thinking..."
                    ):

                        answer = answer_question(
                            user_question,
                            st.session_state.transcript,
                        )

                    st.markdown(
                        answer
                    )

                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": answer,
                    }
                )

            except Exception as e:

                st.error(
                    f"AI chat failed: {e}"
                )