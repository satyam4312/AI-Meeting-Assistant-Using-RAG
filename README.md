# 🎥 AI Meeting/Video Assistant — RAG

> An AI-powered meeting intelligence system that transforms YouTube videos, audio, and video recordings into structured meeting insights and enables conversational Q&A over the meeting content using Retrieval-Augmented Generation (RAG).

---

## 🚀 Overview

Meetings contain valuable information, but manually reviewing long recordings to find decisions, action items, deadlines, and unresolved questions is time-consuming.

**AI Meeting/Video Assistant** automates this entire workflow.

Simply provide a **YouTube URL or a local audio/video file**, and the system:

- 🎙️ Extracts and processes audio
- 📝 Transcribes the meeting
- 🌐 Supports English and Hindi/Hinglish workflows
- 📌 Generates a structured meeting summary
- ✅ Extracts actionable tasks with owners and deadlines
- 🎯 Identifies key decisions
- ❓ Finds unresolved questions and follow-ups
- 💬 Allows users to chat with the meeting using RAG
- 📄 Generates structured meeting reports

The goal is to turn unstructured meeting recordings into **searchable, actionable knowledge**.

---

## ✨ Key Features

### 🎬 Multi-Source Input

Accepts:

- YouTube URLs
- Local audio files
- Local video files

The audio processing pipeline automatically prepares the input for transcription.

---

### 🎙️ AI-Powered Transcription

The system supports different transcription workflows based on the selected language.

| Language | Transcription |
|----------|---------------|
| English | OpenAI Whisper |
| Hindi / Hinglish | Sarvam AI |

This makes the system suitable for both English meetings and Indian multilingual conversations.

---

### 🧠 Automated Meeting Intelligence

Instead of producing only a raw transcript, the system extracts useful information from the meeting.

#### 📋 Meeting Summary

Generates concise bullet-point summaries covering the important topics discussed.

#### ✅ Action Items

Identifies:

- Task
- Responsible person
- Deadline
- Relevant context

Example:

```text
1. Prepare the project report
   Owner: Rahul
   Deadline: Friday
