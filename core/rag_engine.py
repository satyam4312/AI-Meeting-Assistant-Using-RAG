import os
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from core.vector_store import build_vector_store, load_vector_store, get_retriever

def get_llm():
    return ChatGroq(
        model = "openai/gpt-oss-120b",
        api_key = os.getenv("GROQ_API_KEY"),
        temperature = 0.2,
    )


def format_docs(docs):
    return "\n\n".join([doc.page_content for doc in docs])


def get_prompt():
    return ChatPromptTemplate.from_messages([
        ("system",
            """
            You are an expert meeting assistant.
            Answer the user's question based ONLY on the meeting
            transcript context provided below.

            If the answer is not found in the context, respond exactly :

            "I could not find this information in the meeting transcript."

            Rules:
            - Do not use outside knowledge.
            - Do not make up information.
            - Be concise and precise.
            - If quoting someone, clearly mention who said it.

            Meeting transcript context : {context}
            """
        ),
        ("human", "{question}"),
    ])


def build_rag_chain(transcript : str):

    if not transcript or not transcript.strip():
        raise ValueError("Transcript cannot be empty.")

    vector_store = build_vector_store(transcript)

    retriever = get_retriever(vector_store, k = 4)

    llm = get_llm()

    prompt = get_prompt()

    rag_chain = (
        {
            "context": retriever | RunnableLambda(format_docs),
            "question": RunnablePassthrough(),
        }
        | prompt | llm | StrOutputParser()
    )

    return rag_chain


def load_rag_chain():

    vector_store = load_vector_store()

    if vector_store is None:
        raise ValueError("Could not load the vector store.")

    retriever = get_retriever(vector_store, k = 4)

    llm = get_llm()

    prompt = get_prompt()

    rag_chain = (
        {
            "context" : retriever | RunnableLambda(format_docs),
            "question" : RunnablePassthrough(),
        }
        | prompt | llm | StrOutputParser()
    )

    return rag_chain


def ask_question(rag_chain, question: str) -> str:
    if not question or not question.strip():
        raise ValueError("Question cannot be empty.")

    print(f"\nQuestion: {question}")
    answer = rag_chain.invoke(question)
    print(f"Answer: {answer}")
    return answer
