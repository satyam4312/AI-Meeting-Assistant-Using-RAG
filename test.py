from dotenv import load_dotenv
load_dotenv()

from utils.audio_processor import process_input
from core.transcriber import transcribe_all
import os

print("KEY LOADED:", bool(os.getenv("SARVAM_API_KEY")))
print("CWD:", os.getcwd())

source = "https://youtu.be/KlfuFFGWw64?si=RbO8m5TrpGR_Il9Y"
language = "hinglish"

chunks = process_input(source)
transcript = transcribe_all(chunks, language = language)

print("\n============ TRANSCRIPT ============\n")
print(transcript)
