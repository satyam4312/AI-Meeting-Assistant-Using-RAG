import os
import shutil
import subprocess
from pathlib import Path

import yt_dlp
from pydub import AudioSegment


DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok = True)

BGUTIL_DIR = Path.home() / "bgutil-ytdlp-pot-provider"
BGUTIL_SERVER_DIR = BGUTIL_DIR / "server"

BGUTIL_REPO = (
    "https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git"
)

BGUTIL_VERSION = "2.0.0"


class YouTubeDownloadError(Exception):
    """
    Raised when YouTube prevents yt-dlp from downloading
    the requested video.
    """
    pass


# BgUtils PO Token Provider

def setup_bgutil_provider():
    """
    Set up the BgUtils PO Token Provider if it is not already
    installed.
    """
    deno_path = shutil.which("deno")

    if not deno_path:
        print("Warning: Deno was not found.")
        print("YouTube extraction may fail.")
        return None

    print(f"Deno found: {deno_path}")

    # Clone BgUtils provider if necessary
    if not BGUTIL_SERVER_DIR.exists():
        print("Installing BgUtils PO Token Provider...")

        if BGUTIL_DIR.exists():
            shutil.rmtree(BGUTIL_DIR)
        try:
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
                check = True,
                capture_output = True,
                text = True,
            )
        except subprocess.CalledProcessError as e:
            print("Failed to clone BgUtils provider.")
            print(e.stderr)
            return None

    # Install provider dependencies
    node_modules = BGUTIL_SERVER_DIR / "node_modules"
    if not node_modules.exists():
        print("Installing BgUtils dependencies...")
        try:
            subprocess.run(
                [
                    "deno",
                    "install",
                    "--allow-scripts=npm:canvas",
                    "--frozen",
                ],
                cwd = str(BGUTIL_SERVER_DIR),
                check = True,
            )
        except subprocess.CalledProcessError as e:
            print("Failed to install BgUtils dependencies.")
            print(e)
            return None

    print(f"BgUtils provider ready: {BGUTIL_SERVER_DIR}")
    return str(BGUTIL_SERVER_DIR)


# YouTube downloader
def download_youtube_audio(url: str) -> str:
    print("Preparing YouTube downloader...")
    bgutil_server = setup_bgutil_provider()
    output_path = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")

    ydl_opts = {
        # Let yt-dlp select an available best audio/video format.
        "format": "ba/b",
        "outtmpl": output_path,
        "noplaylist": True,

        # JavaScript runtime
        "js_runtimes": {
            "deno": {},
        },

        # PO Token provider
        "extractor_args": {},

        # FFmpeg conversion
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }
        ],

        # Network settings
        "retries": 5,
        "fragment_retries": 5,
        "socket_timeout": 30,

        # Logging
        "quiet": False,
        "no_warnings": False,
        "verbose": True,
    }

    # Configure BgUtils provider
    if bgutil_server:
        ydl_opts["extractor_args"] = {
            "youtubepot-bgutilscript": {
                "server_home": bgutil_server,
            }
        }

    # Download
    try:
        print(f"Downloading YouTube video: {url}")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        # yt-dlp changes the extension after FFmpeg processing.
        wav_path = os.path.splitext(filename)[0] + ".wav"

        if not os.path.exists(wav_path):
            base_name = os.path.splitext(filename)[0]

            possible_files = [
                base_name + ".wav",
                base_name + ".webm.wav",
                base_name + ".m4a.wav",
            ]

            for candidate in possible_files:

                if os.path.exists(candidate):
                    wav_path = candidate
                    break

        if not os.path.exists(wav_path):
            raise YouTubeDownloadError(
                "YouTube download completed, but the audio file "
                "could not be found after FFmpeg conversion."
            )

        print(f"YouTube audio ready: {wav_path}")
        return wav_path

    except yt_dlp.utils.DownloadError as e:

        error_message = str(e)

        print("YouTube download failed:")
        print(error_message)


        # Detect YouTube access restrictions
        if (
            "403" in error_message
            or "Forbidden" in error_message
            or "unable to download video data" in error_message
            or "Sign in to confirm" in error_message
            or "reloaded" in error_message
            or "not a bot" in error_message
        ):

            raise YouTubeDownloadError(
                "YouTube is currently preventing this video "
                "from being downloaded automatically."
            ) from e
        
        # Other yt-dlp errors
        raise YouTubeDownloadError(
            "YouTube could not be downloaded. "
            "Please try uploading the audio/video file instead."
        ) from e

    except Exception as e:

        print("Unexpected YouTube download error:")
        print(e)

        raise YouTubeDownloadError(
            "An error occurred while processing the YouTube URL. "
            "Please upload the audio/video file instead."
        ) from e


# Convert local file to WAV
def convert_to_wav(input_path: str) -> str:
    """
    Convert any audio/video file to mono 16 kHz WAV.
    """
    output_path = (os.path.splitext(input_path)[0] + "_converted.wav")

    print("Converting input file to WAV...")
    audio = AudioSegment.from_file(input_path)
    audio = (audio.set_channels(1).set_frame_rate(16000))
    audio.export(output_path, format="wav")
    print(f"Converted audio: {output_path}")

    return output_path


# Split audio into chunks
def chunk_audio(wav_path: str, chunk_minutes: int = 10) -> list:
    print("Chunking audio...")
    audio = AudioSegment.from_wav(wav_path)
    chunk_ms = chunk_minutes * 60 * 1000

    chunks = []

    for i, start in enumerate(range(0, len(audio), chunk_ms)):
        chunk = audio[start:start + chunk_ms]
        chunk_path = (f"{wav_path}_chunk_{i}.wav")
        chunk.export(chunk_path, format="wav")
        chunks.append(chunk_path)

    print(f"Audio ready — {len(chunks)} chunk(s) created.")
    return chunks


# Main input processor
def process_input(source: str) -> list:
    if (source.startswith("http://") or source.startswith("https://")):
        print(
            "Detected YouTube URL. "
            "Attempting to download audio..."
        )
        wav_path = download_youtube_audio(source)
    else:
        print(
            "Detected local file. "
            "Converting to WAV..."
        )
        wav_path = convert_to_wav(source)

    return chunk_audio(wav_path) 