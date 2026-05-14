import os

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings, OllamaLLM
from langchain_chroma import Chroma

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_DIR = os.path.join(BASE_DIR, "storage", "chroma_db")

embeddings = OllamaEmbeddings(model="nomic-embed-text")
llm = OllamaLLM(model="llama3.1")


def process_pdf(file_path: str):
    loader = PyPDFLoader(file_path)
    documents = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=150
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


def ask_question(question: str):
    vectorstore = Chroma(
        persist_directory=DB_DIR,
        embedding_function=embeddings
    )

    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

    docs = retriever.invoke(question)

    context = "\n\n".join([
        f"Page {doc.metadata.get('page', 'unknown')}:\n{doc.page_content}"
        for doc in docs
    ])

    prompt = f"""
You are StudyMind AI, an educational AI tutor.

LANGUAGE RULES:
1. Answer in the same language used by the user.
2. If the user asks to translate, switch, or answer in another language, follow that requested language.
3. If the PDF is written in a different language, translate the relevant ideas into the user's requested language.
4. Do not mix languages unless the user asks for that.
5. If the user writes in Arabic, answer in clear Arabic.
6. If the user writes in English, answer in clear English.
7. If the user writes in Hebrew, answer in clear Hebrew.
8. If the user asks "حول للإنجليزي" or "answer in English", answer in English.

ANSWER RULES:
1. Use simple words and organize the answer.
2. If the question is general, give a short clear answer first, then explain.
3. If the topic is math, algorithms, or programming, explain step by step.
4. If the answer is not clearly found in the PDF, say that clearly in the same language as the user, then give a general explanation.

PDF Context:
{context}

User Question:
{question}

Answer:
"""

    return llm.invoke(prompt)