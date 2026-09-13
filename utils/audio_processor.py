import os
import yt_dlp
from pydub import AudioSegment

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def download_youtube_audio(url: str) -> str:
    """
    Download audio from a public YouTube URL and convert it to WAV.

    YouTube currently changes its download restrictions frequently,
    so we try a small set of supported yt-dlp client configurations.
    """

    output_template = os.path.join(
        DOWNLOAD_DIR,
        "%(id)s.%(ext)s",
    )

    base_opts = {
        "outtmpl": output_template,
        "quiet": False,
        "no_warnings": False,
        "noplaylist": True,

        # Prefer audio, but allow yt-dlp to choose a compatible format.
        "format": "bestaudio/best",

        # Convert downloaded audio to WAV.
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }
        ],

        # Avoid unnecessary parallel requests.
        "concurrent_fragment_downloads": 1,

        # Retry transient network failures.
        "retries": 3,
        "fragment_retries": 3,
    }

    # Try different clients because YouTube's restrictions vary by client.
    client_configs = [
        ["tv"],
        ["web_embedded"],
        ["android_vr"],
    ]

    last_error = None

    for clients in client_configs:
        try:
            ydl_opts = dict(base_opts)

            ydl_opts["extractor_args"] = {
                "youtube": {
                    "player_client": clients,
                }
            }

            print(
                f"Trying YouTube client configuration: {clients}"
            )

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(
                    url,
                    download=True,
                )

                if not info:
                    continue

                # yt-dlp's prepare_filename() gives us the original
                # downloaded filename. The FFmpeg postprocessor changes
                # its extension to .wav.
                prepared = ydl.prepare_filename(info)

                base, _ = os.path.splitext(prepared)
                wav_path = base + ".wav"

                if os.path.exists(wav_path):
                    print(
                        f"YouTube audio downloaded successfully: {wav_path}"
                    )
                    return wav_path

                # Fallback: find the generated WAV if yt-dlp changed
                # the filename unexpectedly.
                video_id = info.get("id")

                if video_id:
                    possible_wav = os.path.join(
                        DOWNLOAD_DIR,
                        f"{video_id}.wav",
                    )

                    if os.path.exists(possible_wav):
                        return possible_wav

        except Exception as e:
            last_error = e

            print(
                f"YouTube client {clients} failed: {type(e).__name__}: {e}"
            )

    raise RuntimeError(
        "Could not download the YouTube video. "
        "YouTube rejected all yt-dlp download attempts. "
        f"Last error: {last_error}"
    )


def convert_to_wav(input_path: str) -> str:
    """Convert any audio/video file to mono 16 kHz WAV."""

    output_path = (
        os.path.splitext(input_path)[0]
        + "_converted.wav"
    )

    audio = AudioSegment.from_file(input_path)

    audio = (
        audio
        .set_channels(1)
        .set_frame_rate(16000)
    )

    audio.export(
        output_path,
        format="wav",
    )

    return output_path


def chunk_audio(
    wav_path: str,
    chunk_minutes: int = 10,
) -> list:
    """Split WAV audio into fixed-size chunks."""

    audio = AudioSegment.from_wav(wav_path)

    chunk_ms = chunk_minutes * 60 * 1000

    chunks = []

    for i, start in enumerate(
        range(0, len(audio), chunk_ms)
    ):
        chunk = audio[start:start + chunk_ms]

        chunk_path = (
            f"{wav_path}_chunk_{i}.wav"
        )

        chunk.export(
            chunk_path,
            format="wav",
        )

        chunks.append(chunk_path)

    return chunks


def process_input(source: str) -> list:
    """Download/convert input and split it into chunks."""

    if source.startswith("http://") or source.startswith("https://"):

        print(
            "Detected YouTube URL. "
            "Downloading audio..."
        )

        wav_path = download_youtube_audio(source)

    else:

        print(
            "Detected local file. "
            "Converting to WAV..."
        )

        wav_path = convert_to_wav(source)

    print("Chunking audio...")

    chunks = chunk_audio(wav_path)

    print(
        f"Audio ready — {len(chunks)} chunk(s) created."
    )

    return chunks
