# Action items, decisions, and questions extraction

import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


def get_llm():
    return ChatGroq(
        model = "openai/gpt-oss-120b",
        api_key = os.getenv("GROQ_API_KEY"),
        temperature = 0.2,
    )


def build_chain(system_prompt : str):
    """
    Build a LangChain pipeline for meeting analysis.
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{text}"),
    ])

    llm = get_llm()

    return prompt | llm | StrOutputParser()


def extract_action_items(transcript: str) -> str:
    """
    Extract action items with owner and deadline.
    """

    chain = build_chain(
        "You are an expert meeting analyst. From the meeting transcript, "
        "extract all action items. For each provide:\n"
        "- Task description\n"
        "- Owner (who is responsible)\n"
        "- Deadline (if mentioned, else write 'Not specified')\n\n"
        "Format as a numbered list. If none found say "
        "'No action items found.'"
    )

    return chain.invoke({"text": transcript})


def extract_key_decisions(transcript: str) -> str:
    """
    Extract key decisions from the meeting.
    """

    chain = build_chain(
        "You are an expert meeting analyst. From the meeting transcript, "
        "extract all key decisions made. Format as a numbered list. "
        "If none found say 'No key decisions found.'"
    )

    return chain.invoke({"text": transcript})


def extract_questions(transcript: str) -> str:
    """
    Extract unresolved questions and follow-ups.
    """

    chain = build_chain(
        "From the meeting transcript, extract all unresolved questions "
        "or topics needing follow-up. Format as a numbered list. "
        "If none found say 'No open questions found.'"
    )

    return chain.invoke({"text": transcript})


def extract_all(transcript: str) -> dict:
    """
    Run action-item, decision, and question extraction concurrently.
    This function is optional for now. Your existing main.py can continue
    using the three individual functions until we update it in the next step.
    """

    tasks = {
        "action_items": extract_action_items,
        "key_decisions": extract_key_decisions,
        "open_questions": extract_questions,
    }

    results = {}

    # Controlled concurrency:
    # 3 workers = one request for each independent task.
    with ThreadPoolExecutor(max_workers=3) as executor:

        future_map = {
            executor.submit(function, transcript): name
            for name, function in tasks.items()
        }

        for future in as_completed(future_map):
            name = future_map[future]

            try:
                results[name] = future.result()
                print(f"{name} extraction completed")

            except Exception as e:
                print(f"{name} extraction failed: {e}")
                results[name] = f"Error: {e}"

    return results
