import os
import subprocess
import shutil

import yt_dlp
from pydub import AudioSegment


DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# BgUtils PO Token Provider
# ---------------------------------------------------------------------------

BGUTIL_DIR = "/tmp/bgutil-ytdlp-pot-provider"
BGUTIL_SERVER_DIR = os.path.join(BGUTIL_DIR, "server")
BGUTIL_BUILD_DIR = os.path.join(BGUTIL_SERVER_DIR, "build")


def setup_po_token_provider() -> bool:
    """
    Prepare the BgUtils PO Token provider.

    Returns True if the provider is available.
    Returns False if setup fails.

    The provider requires Node.js >= 20.
    """

    # Already compiled during this Streamlit process.
    generate_script = os.path.join(
        BGUTIL_BUILD_DIR,
        "generate_once.js",
    )

    if os.path.exists(generate_script):
        return True

    node_path = shutil.which("node")

    if not node_path:
        print(
            "Node.js is not installed. "
            "YouTube PO-token support is unavailable."
        )
        return False

    print("Setting up BgUtils PO Token provider...")

    try:

        # Remove incomplete previous installation.
        if os.path.exists(BGUTIL_DIR):
            shutil.rmtree(BGUTIL_DIR)

        subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "https://github.com/Brainicism/"
                "bgutil-ytdlp-pot-provider.git",
                BGUTIL_DIR,
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        subprocess.run(
            ["npm", "ci"],
            cwd=BGUTIL_SERVER_DIR,
            check=True,
            capture_output=True,
            text=True,
        )

        subprocess.run(
            ["npx", "tsc"],
            cwd=BGUTIL_SERVER_DIR,
            check=True,
            capture_output=True,
            text=True,
        )

        if not os.path.exists(generate_script):
            print(
                "BgUtils compiled, but generate_once.js "
                "was not found."
            )
            return False

        print("BgUtils PO Token provider ready.")

        return True

    except subprocess.CalledProcessError as e:

        print(
            "Failed to setup BgUtils PO Token provider."
        )

        if e.stdout:
            print(e.stdout)

        if e.stderr:
            print(e.stderr)

        return False

    except Exception as e:

        print(
            f"Unexpected PO Token provider error: {e}"
        )

        return False


# Initialize once when this module is imported.
PO_TOKEN_PROVIDER_AVAILABLE = setup_po_token_provider()


# ---------------------------------------------------------------------------
# YouTube downloader
# ---------------------------------------------------------------------------

def download_youtube_audio(url: str) -> str:
    """
    Download audio from YouTube and convert it to WAV.

    Uses the BgUtils PO Token provider when available.
    Falls back to normal yt-dlp if the provider cannot be initialized.
    """

    output_template = os.path.join(
        DOWNLOAD_DIR,
        "%(id)s.%(ext)s",
    )

    ydl_opts = {
        "format": "bestaudio/best",

        "outtmpl": output_template,

        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }
        ],

        "quiet": False,
        "no_warnings": False,

        "noplaylist": True,

        "retries": 3,
        "fragment_retries": 3,
    }


    # -----------------------------------------------------------------------
    # Enable BgUtils PO token provider
    # -----------------------------------------------------------------------

    if PO_TOKEN_PROVIDER_AVAILABLE:

        print(
            "Using BgUtils PO Token provider."
        )

        ydl_opts["extractor_args"] = {
            "youtube": {
                "player_client": ["mweb"],
            },

            "youtubepot-bgutilscript": {
                "server_home": BGUTIL_SERVER_DIR,
            },
        }

    else:

        print(
            "WARNING: PO Token provider unavailable. "
            "Trying standard yt-dlp."
        )


    # -----------------------------------------------------------------------
    # Download
    # -----------------------------------------------------------------------

    try:

        print("========================================")
        print("YouTube download started")
        print(f"URL: {url}")
        print("========================================")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            info = ydl.extract_info(
                url,
                download=True,
            )

            if not info:
                raise RuntimeError(
                    "yt-dlp returned no video information."
                )

            video_id = info.get("id")

            if not video_id:
                raise RuntimeError(
                    "yt-dlp did not return a video ID."
                )

        wav_path = os.path.join(
            DOWNLOAD_DIR,
            f"{video_id}.wav",
        )

        if not os.path.exists(wav_path):

            # Fallback search in case FFmpeg produced a
            # slightly different filename.

            candidates = [
                os.path.join(
                    DOWNLOAD_DIR,
                    filename,
                )
                for filename in os.listdir(
                    DOWNLOAD_DIR
                )
                if filename.lower().endswith(".wav")
            ]

            if candidates:
                wav_path = candidates[-1]

            else:
                raise FileNotFoundError(
                    "yt-dlp completed, but no WAV file "
                    "was created."
                )

        print(
            f"YouTube audio successfully downloaded: "
            f"{wav_path}"
        )

        return wav_path


    except yt_dlp.utils.DownloadError as e:

        print("========================================")
        print("YT-DLP DOWNLOAD ERROR")
        print(str(e))
        print("========================================")

        raise RuntimeError(
            "YouTube download failed.\n\n"
            f"yt-dlp error:\n{e}"
        ) from e


# ---------------------------------------------------------------------------
# Uploaded file conversion
# ---------------------------------------------------------------------------

def convert_to_wav(input_path: str) -> str:
    """
    Convert any supported audio/video file
    to mono 16-kHz WAV.
    """

    output_path = (
        os.path.splitext(input_path)[0]
        + "_converted.wav"
    )

    audio = AudioSegment.from_file(
        input_path
    )

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


# ---------------------------------------------------------------------------
# Audio chunking
# ---------------------------------------------------------------------------

def chunk_audio(
    wav_path: str,
    chunk_minutes: int = 10,
) -> list:
    """
    Split WAV audio into fixed-size chunks.
    """

    audio = AudioSegment.from_wav(
        wav_path
    )

    chunk_ms = (
        chunk_minutes
        * 60
        * 1000
    )

    chunks = []

    for i, start in enumerate(
        range(
            0,
            len(audio),
            chunk_ms,
        )
    ):

        chunk = audio[
            start:start + chunk_ms
        ]

        chunk_path = (
            f"{wav_path}_chunk_{i}.wav"
        )

        chunk.export(
            chunk_path,
            format="wav",
        )

        chunks.append(
            chunk_path
        )

    return chunks


# ---------------------------------------------------------------------------
# Main input processor
# ---------------------------------------------------------------------------

def process_input(source: str) -> list:
    """
    Process either:

    1. YouTube URL
    2. Uploaded local video/audio file
    """

    if source.startswith(
        ("http://", "https://")
    ):

        print(
            "Detected YouTube URL. "
            "Downloading audio..."
        )

        wav_path = (
            download_youtube_audio(
                source
            )
        )

    else:

        print(
            "Detected local file. "
            "Converting to WAV..."
        )

        wav_path = convert_to_wav(
            source
        )

    print("Chunking audio...")

    chunks = chunk_audio(
        wav_path
    )

    print(
        f"Audio ready — "
        f"{len(chunks)} chunk(s) created."
    )

    return chunks

