import os
import yt_dlp
from pydub import AudioSegment

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok = True)


def download_youtube_audio(url: str) -> str:
    """
    Download audio from a YouTube URL and convert it to WAV.
    Note:
    YouTube may reject automated/cloud requests with HTTP 403.
    This function gives yt-dlp a few more robust options and
    produces a predictable output filename.
    """

    output_template = os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s")

    ydl_opts = {
        # Prefer audio-only formats
        "format": "bestaudio/best",
        "outtmpl": output_template,

        # Convert downloaded audio to WAV
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }
        ],

        # Avoid unnecessary console output
        "quiet": True,
        # Retry temporary network failures
        "retries": 3,
        # Don't download playlists accidentally
        "noplaylist": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            # After FFmpegExtractAudio, the final file is WAV.
            video_id = info["id"]
            wav_path = os.path.join(
                DOWNLOAD_DIR,
                f"{video_id}.wav"
            )

        if not os.path.exists(wav_path):
            raise FileNotFoundError(
                f"yt-dlp completed, but WAV file was not found: {wav_path}"
            )
        
        return wav_path

    except yt_dlp.utils.DownloadError as e:
        raise RuntimeError(
            "Could not download the YouTube video. "
            "YouTube may be blocking the Streamlit Cloud request "
            "or the video may require authentication."
        ) from e


def convert_to_wav(input_path: str) -> str:
    """Convert any audio/video file to mono 16-kHz WAV."""

    output_path = os.path.splitext(input_path)[0] + "_converted.wav"
    audio = AudioSegment.from_file(input_path)
    audio = (audio.set_channels(1).set_frame_rate(16000))
    audio.export(output_path, format="wav")

    return output_path


def chunk_audio(wav_path: str, chunk_minutes: int = 10) -> list:
    """Split WAV audio into chunks."""

    audio = AudioSegment.from_wav(wav_path)
    chunk_ms = chunk_minutes * 60 * 1000

    chunks = []

    for i, start in enumerate(range(0, len(audio), chunk_ms)):
        chunk = audio[start:start + chunk_ms]
        chunk_path = f"{wav_path}_chunk_{i}.wav"
        chunk.export(chunk_path, format="wav")
        chunks.append(chunk_path)

    return chunks


def process_input(source: str) -> list:
    """Process either a YouTube URL or a local uploaded file."""

    if source.startswith(("http://", "https://")):
        print("Detected YouTube URL. Downloading audio...")
        wav_path = download_youtube_audio(source)

    else:
        print("Detected local file. Converting to WAV...")
        wav_path = convert_to_wav(source)

    print("Chunking audio...")
    chunks = chunk_audio(wav_path)
    print(f"Audio ready — {len(chunks)} chunk(s) created.")

    return chunks

