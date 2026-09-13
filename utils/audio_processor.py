import os
import shutil
import subprocess
from pathlib import Path

import yt_dlp
from pydub import AudioSegment


# ============================================================
# Configuration
# ============================================================

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# BgUtils PO-token provider
BGUTIL_DIR = Path.home() / "bgutil-ytdlp-pot-provider"
BGUTIL_SERVER_DIR = BGUTIL_DIR / "server"

BGUTIL_REPO = (
    "https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git"
)

BGUTIL_VERSION = "2.0.0"


# ============================================================
# BgUtils / Deno Setup
# ============================================================

def setup_bgutil_provider() -> str:
    """
    Prepare the BgUtils PO-token provider.

    Deno is installed through requirements.txt.
    BgUtils provider source is cloned when required.

    Returns:
        Path to the BgUtils server directory.
    """

    # --------------------------------------------------------
    # 1. Check Deno
    # --------------------------------------------------------

    try:
        deno_result = subprocess.run(
            ["deno", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )

        print("Deno detected:")
        print(deno_result.stdout.strip())

    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(
            "Deno is not available. "
            "Make sure `deno>=2.9.0` is present in requirements.txt."
        ) from exc

    # --------------------------------------------------------
    # 2. Clone BgUtils provider
    # --------------------------------------------------------

    if not BGUTIL_SERVER_DIR.exists():

        print("Installing BgUtils PO-token provider...")

        # Remove incomplete installation if it exists
        if BGUTIL_DIR.exists():
            shutil.rmtree(BGUTIL_DIR)

        subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--branch",
                BGUTIL_VERSION,
                BGUTIL_REPO,
                str(BGUTIL_DIR),
            ],
            check=True,
        )

    # --------------------------------------------------------
    # 3. Install BgUtils dependencies
    # --------------------------------------------------------

    node_modules = BGUTIL_SERVER_DIR / "node_modules"

    if not node_modules.exists():

        print(
            "Installing BgUtils JavaScript dependencies..."
        )

        subprocess.run(
            [
                "deno",
                "install",
                "--allow-scripts=npm:canvas",
                "--frozen",
            ],
            cwd=str(BGUTIL_SERVER_DIR),
            check=True,
        )

    return str(BGUTIL_SERVER_DIR)


# ============================================================
# YouTube Audio Downloader
# ============================================================

def download_youtube_audio(url: str) -> str:
    """
    Download audio from YouTube using:

        yt-dlp
        yt-dlp-ejs
        Deno
        BgUtils PO-token provider
        FFmpeg

    The YouTube player client is intentionally NOT forced.
    """

    # --------------------------------------------------------
    # Prepare PO-token provider
    # --------------------------------------------------------

    bgutil_server = setup_bgutil_provider()

    # --------------------------------------------------------
    # Output path
    # --------------------------------------------------------

    output_path = os.path.join(
        DOWNLOAD_DIR,
        "%(title)s.%(ext)s",
    )

    # --------------------------------------------------------
    # yt-dlp configuration
    # --------------------------------------------------------

    ydl_opts = {

        # Audio only when available,
        # otherwise use best available format.
        "format": "ba/b",

        # Output filename
        "outtmpl": output_path,

        # Never download playlists
        "noplaylist": True,

        # ----------------------------------------------------
        # Modern YouTube JavaScript support
        # ----------------------------------------------------

        "js_runtimes": {
            "deno": {},
        },
        # ----------------------------------------------------
        # BgUtils PO-token provider
        # ----------------------------------------------------

        "extractor_args": {
            "youtubepot-bgutilscript": {
                "server_home": bgutil_server,
            }
        },

        # ----------------------------------------------------
        # Convert downloaded audio to WAV
        # ----------------------------------------------------

        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }
        ],

        # ----------------------------------------------------
        # Diagnostics
        # ----------------------------------------------------

        "quiet": False,
        "no_warnings": False,
        "verbose": True,

        # ----------------------------------------------------
        # Network reliability
        # ----------------------------------------------------

        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 30,
    }

    print("=" * 60)
    print("Starting YouTube download")
    print("=" * 60)
    print("URL:", url)
    print("PO-token provider:", bgutil_server)

    # --------------------------------------------------------
    # Download
    # --------------------------------------------------------

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:

        info = ydl.extract_info(
            url,
            download=True,
        )

        filename = ydl.prepare_filename(info)

    # --------------------------------------------------------
    # FFmpegExtractAudio changes extension to WAV
    # --------------------------------------------------------

    filename = (
        os.path.splitext(filename)[0]
        + ".wav"
    )

    # --------------------------------------------------------
    # Verify file
    # --------------------------------------------------------

    if not os.path.exists(filename):

        raise FileNotFoundError(
            "YouTube download completed, "
            "but the WAV file was not found:\n"
            f"{filename}"
        )

    print("=" * 60)
    print("YouTube audio downloaded successfully")
    print("File:", filename)
    print("=" * 60)

    return filename


# ============================================================
# Local Audio / Video → WAV
# ============================================================

def convert_to_wav(input_path: str) -> str:
    """
    Convert any supported audio/video file to:

        - WAV
        - Mono
        - 16 kHz

    This format is suitable for Whisper.
    """

    output_path = (
        os.path.splitext(input_path)[0]
        + "_converted.wav"
    )

    print("Converting file to WAV...")

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

    print(
        "Conversion completed:",
        output_path,
    )

    return output_path


# ============================================================
# Audio Chunking
# ============================================================

def chunk_audio(
    wav_path: str,
    chunk_minutes: int = 10,
) -> list:
    """
    Split WAV audio into chunks.

    Default chunk size:
        10 minutes

    Returns:
        List of WAV chunk paths.
    """

    print("Loading audio for chunking...")

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


# ============================================================
# Environment Diagnostic
# ============================================================

def check_youtube_environment():
    """
    Print useful diagnostics for Streamlit Cloud
    and local debugging.
    """

    print("=" * 60)
    print("YouTube Environment Check")
    print("=" * 60)

    # --------------------------------------------------------
    # yt-dlp
    # --------------------------------------------------------

    try:
        print(
            "yt-dlp:",
            yt_dlp.version.__version__,
        )
    except Exception as exc:
        print(
            "yt-dlp version error:",
            exc,
        )

    # --------------------------------------------------------
    # Deno
    # --------------------------------------------------------

    try:

        result = subprocess.run(
            ["deno", "--version"],
            capture_output=True,
            text=True,
        )

        print("Deno:")
        print(result.stdout.strip())

    except Exception as exc:

        print(
            "Deno ERROR:",
            exc,
        )

    # --------------------------------------------------------
    # BgUtils
    # --------------------------------------------------------

    print(
        "BgUtils directory:",
        BGUTIL_SERVER_DIR,
    )

    print(
        "BgUtils exists:",
        BGUTIL_SERVER_DIR.exists(),
    )

    # --------------------------------------------------------
    # FFmpeg
    # --------------------------------------------------------

    try:

        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
        )

        first_line = (
            result.stdout.splitlines()[0]
            if result.stdout
            else "Unknown"
        )

        print(
            "FFmpeg:",
            first_line,
        )

    except Exception as exc:

        print(
            "FFmpeg ERROR:",
            exc,
        )

    print("=" * 60)


# ============================================================
# Main Input Processor
# ============================================================

def process_input(source: str) -> list:
    """
    Process either:

        1. YouTube URL
        2. Local audio/video file

    Returns:
        List of WAV chunk paths.
    """

    # --------------------------------------------------------
    # YouTube
    # --------------------------------------------------------

    if (
        source.startswith("http://")
        or source.startswith("https://")
    ):

        print(
            "Detected YouTube URL."
        )

        wav_path = (
            download_youtube_audio(
                source
            )
        )

    # --------------------------------------------------------
    # Local file
    # --------------------------------------------------------

    else:

        print(
            "Detected local audio/video file."
        )

        wav_path = (
            convert_to_wav(
                source
            )
        )

    # --------------------------------------------------------
    # Chunk audio
    # --------------------------------------------------------

    print(
        "Chunking audio..."
    )

    chunks = chunk_audio(
        wav_path
    )

    print(
        f"Audio ready — "
        f"{len(chunks)} chunk(s) created."
    )

    return chunks
