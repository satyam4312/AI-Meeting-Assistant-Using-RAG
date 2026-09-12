from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_text_splitters import RecursiveCharacterTextSplitter
import os

MAX_CONCURRENCY = 5

def get_llm():
    return ChatGroq(
        model = "openai/gpt-oss-120b",
        api_key = os.getenv("GROQ_API_KEY"),
        temperature = 0.2,
    )


def split_transcript(transcript: str) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size = 3000,
        chunk_overlap = 200,
    )

    return splitter.split_text(transcript)


def summarize(transcript: str) -> str:
    llm = get_llm()

    map_prompt = ChatPromptTemplate.from_messages([
        ("system",
        "Summarize this portion of a meeting transcript concisely.",
        ),
        ("human", "{text}"),
    ])

    map_chain = map_prompt | llm | StrOutputParser()

    chunks = split_transcript(transcript)

    print(f"[SUMMARY] Transcript split into {len(chunks)} chunks")

    chunk_summaries = map_chain.batch(
        [{"text": chunk} for chunk in chunks],
        config = {"max_concurrency" : MAX_CONCURRENCY},
    )

    combined = "\n\n".join(chunk_summaries)

    combined_prompt = ChatPromptTemplate.from_messages([
        ("system",
            "You are an expert meeting summarizer. Combine these partial summaries "
            "into one final professional meeting summary in bullet points.",
        ),
        ("human", "{text}"),
    ])

    combined_chain = combined_prompt | llm | StrOutputParser()

    return combined_chain.invoke({"text": combined})


def generate_title(transcript: str) -> str:
    llm = get_llm()

    title_chain = (
        ChatPromptTemplate.from_messages([
            ("system",
                "Based on the meeting transcript, generate a short professional meeting title "
                "(max 8 words). Only return the title, nothing else.",
            ),
            ("human", "{text}"),
        ]) 
        | llm | StrOutputParser()
    )

    return title_chain.invoke({"text": transcript[:2000]})

