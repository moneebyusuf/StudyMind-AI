import os
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    Docx2txtLoader,
    CSVLoader,
    UnstructuredExcelLoader,
    UnstructuredPowerPointLoader,
)
from langchain_core.documents import Document
from PIL import Image
import pytesseract
from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader, CSVLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings, OllamaLLM
from langchain_chroma import Chroma
from langdetect import detect
import easyocr


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_DIR = os.path.join(BASE_DIR, "storage", "chroma_db")
os.makedirs(DB_DIR, exist_ok=True)

embeddings = OllamaEmbeddings(model="nomic-embed-text")

def get_chat_db_dir(chat_id: int):
    return os.path.join(BASE_DIR, "storage", "chroma_db", f"chat_{chat_id}")


def process_file(file_path: str, chat_id: int):
    db_dir = get_chat_db_dir(chat_id)

    extension = os.path.splitext(file_path)[1].lower()

    if extension == ".pdf":
        loader = PyPDFLoader(file_path)
        documents = loader.load()

    elif extension == ".docx":
        loader = Docx2txtLoader(file_path)
        documents = loader.load()

    elif extension == ".csv":
        loader = CSVLoader(file_path)
        documents = loader.load()

    elif extension in [".xlsx", ".xls"]:
        loader = UnstructuredExcelLoader(file_path)
        documents = loader.load()

    elif extension in [".pptx", ".ppt"]:
        loader = UnstructuredPowerPointLoader(file_path)
        documents = loader.load()

    elif extension in [".png", ".jpg", ".jpeg"]:
        reader = easyocr.Reader(['ar', 'en'], gpu=False)

        result = reader.readtext(
            file_path,
            detail=0,
            paragraph=True
        )

        extracted_text = "\n".join(result)

        documents = [
            Document(
                page_content=f"""
This text was extracted from an uploaded image using OCR.
The OCR may contain broken word order, especially for Arabic handwriting or styled fonts.
If the user asks what is written in the image, reconstruct the most natural sentence from the OCR text.

OCR TEXT:
{extracted_text}
""",
                metadata={"source": file_path, "file_type": extension}
            )
        ]

    elif extension in [".txt", ".md", ".py", ".js", ".jsx", ".html", ".css", ".json"]:
        loader = TextLoader(file_path, encoding="utf-8")
        documents = loader.load()

    else:
        raise ValueError("Unsupported file type")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=80
    )

    chunks = splitter.split_documents(documents)

    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=db_dir
    )

    return {
        "file_type": extension,
        "documents": len(documents),
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


def ask_question(question: str, chat_id: int, mode: str = "balanced", response_language: str = "English"):
    db_dir = get_chat_db_dir(chat_id)

    vectorstore = Chroma(
        persist_directory=db_dir,
        embedding_function=embeddings
    )
    if mode == "fast":
        k = 1
        answer_style = "Give a very short, direct answer. Do not over-explain."
        model_name = "qwen2.5:1.5b"

    elif mode == "deep":
        k = 7
        answer_style = "Give a detailed step-by-step explanation with examples."
        model_name = "llama3.1"

    else:
        k = 3
        answer_style = "Give a clear balanced answer."
        model_name = "llama3.2:3b"

    llm = OllamaLLM(model=model_name)
    retriever = vectorstore.as_retriever(search_kwargs={"k": k})

    docs = retriever.invoke(question)
    print("DOCS FOUND:", len(docs))
    for i, doc in enumerate(docs):
        print("DOC", i, doc.page_content[:300])

    if not docs:
        context = "No relevant PDF context was found."
    else:
        context = "\n\n".join([
            f"Page {doc.metadata.get('page', 'unknown')}:\n{doc.page_content}"
            for doc in docs
        ])
        if not context.strip():
            return f"No file content was found for this chat. Please upload the file again in this chat."

    prompt = f"""
You are StudyMind AI, a smart educational tutor.

CRITICAL LANGUAGE RULE:
The selected response language is: {response_language}.
You MUST answer only in {response_language}.
If the uploaded file is in another language, translate and explain it in {response_language}.
Do not switch languages unless the selected response language is changed.

IMPORTANT FILE RULE:
The text below is the content extracted from the user's uploaded file.
You DO have access to the uploaded file through this extracted content.
Never say "I don't see an uploaded file".
Never ask the user to upload or paste the file again if UPLOADED FILE CONTENT is not empty.
Base your answer on the uploaded file content below.

ANSWER STYLE:
- {answer_style}
- If the uploaded file is an image and the OCR text is fragmented, reconstruct the most natural sentence.
- If the user asks "what is written in the image", answer with only the written text unless they ask for explanation.
- For Arabic OCR, fix word order when it is clearly reversed or fragmented.
- If the user asks to extract, copy, or read the text from an image or file, return the text directly as written.
- Do not summarize.
- Do not paraphrase.
- Do not explain unless the user asks for explanation.
- Do not claim something is missing if it appears in the uploaded file content.
- Do not invent numbers, percentages, metrics, GitHub links, or achievements.
- If no metric is provided in the file, suggest adding real measurable metrics, but do not create fake ones.
- When giving CV feedback, separate feedback into:
  1. Overall Assessment
  2. Strengths found in the CV
  3. Weaknesses or improvements
  4. Specific rewrite suggestions
- Base every point on the uploaded file content only.
- Be clear and direct.
- Explain like a teacher.
- Use simple words.
- Use short sections.
- If the user asks for feedback, give specific feedback based on the uploaded file.
- Mention strengths and weaknesses when evaluating a CV or document.
- If the topic is math, algorithms, or programming, explain step by step.
- When writing mathematical formulas, ALWAYS use LaTeX.
- For inline math, use \\( ... \\).
- For centered equations, use $$ ... $$.
- Do not start with greetings.
- Do not invent unrelated examples.

UPLOADED FILE CONTENT:
{context}

USER QUESTION:
{question}

Answer:
"""

    return llm.invoke(prompt)