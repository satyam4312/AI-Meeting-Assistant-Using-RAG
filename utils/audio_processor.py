import os
import shutil
import subprocess
from pathlib import Path

import yt_dlp
from pydub import AudioSegment


# ============================================================
# DIRECTORIES
# ============================================================

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

BGUTIL_DIR = Path("/tmp/bgutil-ytdlp-pot-provider")
BGUTIL_SERVER_DIR = BGUTIL_DIR / "server"

# Pin the provider version so Streamlit does not unexpectedly
# pull a different server/plugin combination.
BGUTIL_VERSION = "2.0.0"


# ============================================================
# BGUTIL PO TOKEN PROVIDER
# ============================================================

def _command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def setup_po_token_provider() -> bool:
    """
    Prepare bgutil-ytdlp-pot-provider on Streamlit Cloud.

    The provider uses Node.js to generate YouTube proof-of-origin
    tokens. This helps with YouTube's current 403 / bot protection.

    Returns:
        True if the provider is available.
        False if it could not be installed.
    """

    # Already compiled during this app/container lifetime
    generate_script = (
        BGUTIL_SERVER_DIR
        / "build"
        / "generate_once.js"
    )

    if generate_script.exists():
        return True

    # Node is required by the provider.
    if not _command_exists("node"):
        print("WARNING: Node.js is not available.")
        print("PO-token provider cannot be initialized.")
        return False

    # npm is required to build the provider.
    if not _command_exists("npm"):
        print("WARNING: npm is not available.")
        print("PO-token provider cannot be initialized.")
        return False

    try:
        # Clone only if it doesn't already exist.
        if not BGUTIL_DIR.exists():
            print("Installing YouTube PO-token provider...")

            subprocess.run(
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    "--branch",
                    BGUTIL_VERSION,
                    "https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git",
                    str(BGUTIL_DIR),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

        package_json = BGUTIL_SERVER_DIR / "package.json"

        if not package_json.exists():
            print("WARNING: bgutil server files were not found.")
            return False

        # Install Node dependencies.
        print("Installing PO-token provider dependencies...")

        subprocess.run(
            ["npm", "ci", "--no-audit", "--no-fund"],
            cwd=str(BGUTIL_SERVER_DIR),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        # Compile TypeScript -> JavaScript.
        print("Compiling PO-token provider...")

        subprocess.run(
            ["npx", "tsc"],
            cwd=str(BGUTIL_SERVER_DIR),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        if not generate_script.exists():
            print(
                "WARNING: PO-token provider compilation completed "
                "but generate_once.js was not found."
            )
            return False

        print("PO-token provider is ready.")
        return True

    except subprocess.CalledProcessError as e:
        print("PO-token provider setup failed.")

        if e.stdout:
            print(e.stdout)

        return False

    except Exception as e:
        print(f"Unexpected PO-token provider setup error: {e}")
        return False


# ============================================================
# YOUTUBE DOWNLOAD
# ============================================================

def download_youtube_audio(url: str) -> str:
    """
    Download YouTube audio and convert it to WAV.

    Uses:
      - yt-dlp
      - mweb YouTube client
      - bgutil PO-token provider when available
    """

    print("Starting YouTube download...")
    print(f"URL: {url}")

    provider_available = setup_po_token_provider()

    # Use video ID as filename rather than the title.
    output_template = str(
        DOWNLOAD_DIR / "%(id)s.%(ext)s"
    )

    ydl_opts = {
        # Prefer audio.
        "format": "bestaudio/best",

        "outtmpl": output_template,

        "noplaylist": True,

        # Retry transient failures.
        "retries": 5,
        "fragment_retries": 5,

        # Avoid noisy output in normal Streamlit operation.
        "quiet": True,
        "no_warnings": False,

        # FFmpeg converts downloaded audio to WAV.
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }
        ],

        # Don't retain the original webm/m4a after conversion.
        "keepvideo": False,
    }

    # --------------------------------------------------------
    # YouTube PO token configuration
    # --------------------------------------------------------

    if provider_available:
        generate_script = (
            BGUTIL_SERVER_DIR
            / "build"
            / "generate_once.js"
        )

        ydl_opts["extractor_args"] = {
            "youtube": {
                # Current PO-token configuration works with mweb.
                "player_client": ["mweb"],
            },
            "youtubepot-bgutilscript": {
                "script_path": str(generate_script),
            },
        }

        # Explicitly tell the provider to use Node.
        ydl_opts["js_runtimes"] = {
            "node": None
        }

        print("Using bgutil PO-token provider.")

    else:
        # Still try normal yt-dlp if the provider cannot initialize.
        ydl_opts["extractor_args"] = {
            "youtube": {
                "player_client": ["mweb"],
            }
        }

        print(
            "PO-token provider unavailable. "
            "Attempting normal yt-dlp download."
        )

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            info = ydl.extract_info(
                url,
                download=True,
            )

            video_id = info.get("id")

            if not video_id:
                raise RuntimeError(
                    "yt-dlp did not return a YouTube video ID."
                )

        wav_path = DOWNLOAD_DIR / f"{video_id}.wav"

        if not wav_path.exists():

            # Sometimes yt-dlp/FFmpeg may produce a slightly
            # different filename. Search for it.
            candidates = list(
                DOWNLOAD_DIR.glob(f"{video_id}*.wav")
            )

            if candidates:
                wav_path = candidates[0]

            else:
                raise FileNotFoundError(
                    "yt-dlp completed, but the WAV file was not found."
                )

        print(f"YouTube audio ready: {wav_path}")

        return str(wav_path)

    except yt_dlp.utils.DownloadError as e:

        error_text = str(e)

        print("=" * 70)
        print("YT-DLP DOWNLOAD ERROR")
        print(error_text)
        print("=" * 70)

        # IMPORTANT:
        # Do NOT hide the real yt-dlp error behind the old
        # generic "YouTube refused..." message.
        raise RuntimeError(
            "YouTube download failed.\n\n"
            f"{error_text}"
        ) from e

    except Exception as e:

        print("=" * 70)
        print("YOUTUBE PROCESSING ERROR")
        print(repr(e))
        print("=" * 70)

        raise


# ============================================================
# LOCAL FILE -> WAV
# ============================================================

def convert_to_wav(input_path: str) -> str:
    """
    Convert uploaded/local audio or video to mono 16 kHz WAV.
    """

    input_path = str(input_path)

    if not os.path.exists(input_path):
        raise FileNotFoundError(
            f"Input file does not exist: {input_path}"
        )

    output_path = (
        os.path.splitext(input_path)[0]
        + "_converted.wav"
    )

    print(f"Converting local file: {input_path}")

    try:
        audio = AudioSegment.from_file(input_path)

        # Whisper works well with mono 16 kHz audio.
        audio = (
            audio
            .set_channels(1)
            .set_frame_rate(16000)
        )

        audio.export(
            output_path,
            format="wav",
        )

    except Exception as e:
        raise RuntimeError(
            f"Could not convert the uploaded file to WAV: {e}"
        ) from e

    return output_path


# ============================================================
# AUDIO CHUNKING
# ============================================================

def chunk_audio(
    wav_path: str,
    chunk_minutes: int = 10,
) -> list:
    """
    Split WAV into manageable chunks.

    Default:
        10 minutes per chunk
    """

    if not os.path.exists(wav_path):
        raise FileNotFoundError(
            f"WAV file not found: {wav_path}"
        )

    if chunk_minutes <= 0:
        raise ValueError(
            "chunk_minutes must be greater than zero."
        )

    print("Loading audio for chunking...")

    audio = AudioSegment.from_wav(wav_path)

    chunk_ms = chunk_minutes * 60 * 1000

    chunks = []

    for i, start in enumerate(
        range(0, len(audio), chunk_ms)
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

        chunks.append(chunk_path)

    return chunks


# ============================================================
# MAIN INPUT PROCESSOR
# ============================================================

def process_input(source: str) -> list:
    """
    Process either:

        1. YouTube URL
        2. Local/uploaded audio/video file

    Returns:
        List of WAV chunk paths.
    """

    if not source:
        raise ValueError(
            "No input source was provided."
        )

    source = str(source).strip()

    if source.startswith(
        ("http://", "https://")
    ):

        print(
            "Detected YouTube URL. "
            "Downloading audio..."
        )

        wav_path = download_youtube_audio(
            source
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
        wav_path,
        chunk_minutes=10,
    )

    print(
        f"Audio ready — "
        f"{len(chunks)} chunk(s) created."
    )

    return chunks