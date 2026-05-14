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

embeddings = OllamaEmbeddings(
    model="nomic-embed-text",
    base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
)

def has_bad_math_format(answer: str) -> bool:
    bad_patterns = [
        "1/",
        "^",
        "∫",
        "sqrt",
        "ln(",
        "dx",
        "u'",
        "f'",
    ]

    has_math_symbols = any(pattern in answer for pattern in bad_patterns)
    has_latex = "$$" in answer or "\\(" in answer or "\\[" in answer

    return has_math_symbols and not has_latex

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
        k = 6
        answer_style = "Give a detailed step-by-step explanation with clear examples."
        model_name = "llama3.1"
    else:
        k = 3
        answer_style = "Give a clear balanced answer."
        model_name = "llama3.2:3b"

    llm = OllamaLLM(
        model=model_name,
        base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    )
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

========================
LANGUAGE RULES
========================
- The selected response language is: {response_language}.
- You MUST answer only in {response_language}.
- If the uploaded file is in another language, translate and explain the relevant content in {response_language}.
- Do not switch languages unless the selected response language is changed by the user.
- Do not mix languages unless the user asks for mixed languages.

========================
FILE ACCESS RULES
========================
- The text below is extracted from the user's uploaded file.
- You DO have access to the uploaded file through this extracted content.
- Never say "I don't see an uploaded file" if UPLOADED FILE CONTENT is not empty.
- Never ask the user to upload or paste the file again if UPLOADED FILE CONTENT is not empty.
- Base your answer only on the uploaded file content below.
- If the uploaded file content is partial, say that your answer is based on the retrieved parts of the file.

========================
ACCURACY RULES
========================
- Do not invent information.
- Do not invent numbers, percentages, metrics, GitHub links, sources, or achievements.
- Do not claim something is missing if it appears in the uploaded file content.
- If no metric is provided in the file, suggest adding real measurable metrics, but do not create fake ones.
- Do not add unrelated examples unless they help explain the uploaded content clearly.
- If the answer is not clearly supported by the uploaded content, say that clearly in {response_language}.

========================
ANSWER STYLE
========================
- {answer_style}
- Be clear, direct, and organized.
- Explain like a helpful teacher.
- Use simple words.
- Use short sections and bullet points when helpful.
- If the user asks for a simple answer, keep it short.
- If the user asks for explanation, explain step by step.
- If the topic is math, algorithms, or programming, explain step by step.
- Do not start with greetings like "hello", "hi", or "sure".

========================
IMAGE / OCR RULES
========================
- If the uploaded file is an image and the OCR text is fragmented, reconstruct the most natural sentence.
- For Arabic OCR, fix word order only when it is clearly reversed or fragmented.
- Do not change the meaning of the text.
- Do not change singular/plural words, such as changing "أنت" to "أنتم".
- If the user asks what is written in an image, answer with only the written text unless they ask for explanation.
- If the user asks to extract, copy, or read text from an image or file, return the text directly as written.
- Do not summarize or paraphrase extracted text unless the user asks.

========================
CV / DOCUMENT FEEDBACK RULES
========================
- If the user asks for feedback on a CV or document, give specific feedback based on the uploaded file.
- Mention strengths and weaknesses.
- Structure CV feedback like this:
  1. Overall Assessment
  2. Strengths found in the CV
  3. Weaknesses or improvements
  4. Specific rewrite suggestions
- Do not invent missing sections or fake achievements.

========================
MATH FORMATTING RULES
========================
- All mathematical formulas MUST be written in valid LaTeX.
- Use $$ ... $$ for every important formula.
- Do NOT write formulas as plain text.
- Do NOT write powers like u^2(x). Write them as:
  $$
  u^{{2}}(x)
  $$
- Do NOT write fractions like 1/2. Write them as:
  $$
  \\frac{{1}}{{2}}
  $$
- Do NOT write derivatives like u^2(x)'. Write them as:
  $$
  \\left(u^{{2}}(x)\\right)'
  $$
- Do NOT write integrals like ∫ 1/2 u(x)^2 dx. Write them as:
  $$
  \\int \\frac{{1}}{{2}}u^{{2}}(x)\\,dx
  $$
- Use proper LaTeX commands:
  \\frac{{}}{{}}, \\int, \\ln, \\sqrt{{}}, ^{{}}, _{{}}, \\cdot, \\,dx, \\left( \\right)
- If the uploaded file has broken math text, reconstruct it into clean LaTeX.

Examples of correct math formatting:

$$
\\left(u^{{2}}(x)\\right)' = 2u(x)u'(x)
$$

$$
\\int u(x)u'(x)\\,dx = \\frac{{1}}{{2}}u^{{2}}(x)+C
$$

$$
\\int x^{{t}}\\,dx = \\frac{{1}}{{t+1}}x^{{t+1}}+C
$$
========================
UPLOADED FILE CONTENT
========================
{context}

========================
USER QUESTION
========================
{question}

Answer:
"""

    try:
        answer = llm.invoke(prompt)

        if has_bad_math_format(answer):
            fix_prompt = f"""
You made a formatting mistake.

Rewrite the answer below, but keep the same meaning.

STRICT RULES:
- Convert EVERY mathematical expression to proper LaTeX.
- Use $$ ... $$ for displayed formulas.
- Use \\( ... \\) for short inline symbols.
- Do NOT write formulas using plain text like 1/2, x^2, u'(x), or ∫.
- Use \\frac{{}}{{}}, ^{{}}, \\int, \\ln, \\sqrt{{}}, \\cdot, \\,dx.
- Keep the response language as {response_language}.
- Do not add new information.

Bad answer:
{answer}

Corrected answer:
"""
            answer = llm.invoke(fix_prompt)

        return answer

    except Exception as e:
        print("PRIMARY MODEL ERROR:", e)

        if mode == "deep":
            fallback_llm = OllamaLLM(
                model="llama3.2:3b",
                base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
            )

            try:
                return fallback_llm.invoke(prompt)
            except Exception as fallback_error:
                print("FALLBACK MODEL ERROR:", fallback_error)
                return "Sorry, the AI model failed to respond. Please try again using Balanced mode."

        return "Sorry, the AI model failed to respond. Please try again."