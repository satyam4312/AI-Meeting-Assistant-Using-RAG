from dotenv import load_dotenv

load_dotenv(override = True)

from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.audio_processor import process_input
from core.transcriber import transcribe_all
from core.summarizer import summarize, generate_title
from core.extractor import extract_all
from core.rag_engine import build_rag_chain, ask_question


def run_analysis(transcript: str) -> dict:
    """
    Run summary and structured extraction concurrently.
    Title generation is intentionally done after the summary so we avoid
    launching too many Groq requests at once. The title is generated from
    the shorter summary instead of the full transcript.
    """
    tasks = {
        "summary": summarize,
        "extraction": extract_all,
    }

    results = {}

    # Summary internally uses max_concurrency=5 and extraction uses 3 workers.
    # Running these two groups together keeps top-level concurrency predictable.
    with ThreadPoolExecutor(max_workers = 2) as executor:
        futures = {
            executor.submit(function, transcript): name
            for name, function in tasks.items()
        }

        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result()
                print(f"{name} completed")
            except Exception as exc:
                print(f"{name} failed: {exc}")
                raise

    summary = results["summary"]
    extraction = results["extraction"]

    # Use the compact summary for title generation.
    title = generate_title(summary)

    return {
        "title": title,
        "summary": summary,
        "action_items": extraction["action_items"],
        "key_decisions": extraction["key_decisions"],
        "open_questions": extraction["open_questions"],
    }


def run_pipeline(source: str, language: str = "english") -> dict:
    print("Starting AI Video Assistant")

    print("\n[1/4] Processing input...")
    chunks = process_input(source)

    print("\n[2/4] Transcribing...")
    transcript = transcribe_all(chunks, language)

    if not transcript.strip():
        raise ValueError("No transcript was produced from the input.")

    print(
        f"Raw transcription (first 300 characters): "
        f"{transcript[:300]}"
    )

    print("\n[3/4] Analyzing meeting...")
    analysis = run_analysis(transcript)

    print("\n[4/4] Building RAG index...")
    rag_chain = build_rag_chain(transcript)

    return {
        "title": analysis["title"],
        "transcript": transcript,
        "summary": analysis["summary"],
        "action_items": analysis["action_items"],
        "key_decisions": analysis["key_decisions"],
        "open_questions": analysis["open_questions"],
        "rag_chain": rag_chain,
    }


if __name__ == "__main__":
    source = input("Enter YouTube URL or local file path: ").strip()
    language = input("Language (english/hinglish): ").strip() or "english"

    result = run_pipeline(source, language)

    print("\n" + "=" * 60)
    print(f"📌 Title: {result['title']}")
    print(f"\n📋 Summary:\n{result['summary']}")
    print(f"\n✅ Action Items:\n{result['action_items']}")
    print(f"\n🔑 Key Decisions:\n{result['key_decisions']}")
    print(f"\n❓ Open Questions:\n{result['open_questions']}")
    print("=" * 60)

    print("\n💬 Chat with your meeting (type 'exit' to quit)\n")
    rag_chain = result["rag_chain"]

    while True:
        question = input("You: ").strip()

        if question.lower() in ["exit", "quit", "q"]:
            print("👋 Goodbye!")
            break

        if not question:
            continue

        try:
            answer = ask_question(rag_chain, question)
            print(f"\n🤖 Assistant: {answer}\n")
        except Exception as exc:
            print(f"\n❌ Error while answering: {exc}\n")
