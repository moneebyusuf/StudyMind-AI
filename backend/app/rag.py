import os

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings, OllamaLLM
from langchain_chroma import Chroma
from langdetect import detect

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_DIR = os.path.join(BASE_DIR, "storage", "chroma_db")

embeddings = OllamaEmbeddings(model="nomic-embed-text")
llm = OllamaLLM(model="llama3.1")


def process_pdf(file_path: str):
    loader = PyPDFLoader(file_path)
    documents = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=80
    )

    chunks = splitter.split_documents(documents)

    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=DB_DIR
    )

    return {
        "pages": len(documents),
        "chunks": len(chunks)
    }

def detect_user_language(question: str):
    try:
        lang_code = detect(question)

        language_names = {
            "ar": "Arabic",
            "en": "English",
            "he": "Hebrew",
            "iw": "Hebrew",
            "fr": "French",
            "es": "Spanish",
            "de": "German",
            "it": "Italian",
            "pt": "Portuguese",
            "ru": "Russian",
            "tr": "Turkish",
            "zh-cn": "Chinese",
            "zh-tw": "Chinese",
            "ja": "Japanese",
            "ko": "Korean",
            "hi": "Hindi",
            "ur": "Urdu",
            "fa": "Persian",
        }

        return language_names.get(lang_code, lang_code)
    except:
        return "the same language as the user's question"


def ask_question(question: str):
    user_language = detect_user_language(question)
    vectorstore = Chroma(
        persist_directory=DB_DIR,
        embedding_function=embeddings
    )

    retriever = vectorstore.as_retriever(search_kwargs={"k": 2})

    docs = retriever.invoke(question)

    context = "\n\n".join([
        f"Page {doc.metadata.get('page', 'unknown')}:\n{doc.page_content}"
        for doc in docs
    ])

    prompt = f"""
You are StudyMind AI, a smart educational tutor.

CRITICAL LANGUAGE RULE:
The detected user language is: {user_language}.
You MUST answer in the user's language.
Do NOT answer in English unless the user wrote in English or specifically asked for English.
If the PDF context is written in another language, translate the relevant ideas into the user's language.
Symbols, formulas, code, or terms like A*, f(n), g(n), Python, React, or integral do NOT determine the answer language.
The natural language of the user's question determines the answer language.
If the user asks to switch language, use the requested language.
Do not mix languages unless the user asks.

ANSWER STYLE:
- Be clear and direct.
- Explain like a teacher.
- Use simple words.
- Use short sections.
- If the topic is an algorithm, math, or programming, explain step by step.
- Give a small example when useful.
- Do not start with greetings.
- Do not invent unrelated examples.

PDF CONTEXT:
{context}

USER QUESTION:
{question}

Answer:
"""

    return llm.invoke(prompt)