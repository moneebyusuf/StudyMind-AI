from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import os

from app.rag import process_pdf, ask_question

app = FastAPI(title="StudyMind AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UPLOAD_DIR = os.path.join(BASE_DIR, "storage", "uploads")

os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.get("/")
def home():
    return {"message": "StudyMind AI backend is running"}


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        return {"error": "Please upload a PDF file only"}

    file_path = os.path.join(UPLOAD_DIR, file.filename)

    with open(file_path, "wb") as f:
        f.write(await file.read())

    result = process_pdf(file_path)

    return {
        "message": "PDF uploaded and processed successfully",
        "file": file.filename,
        "result": result,
    }


@app.post("/ask")
async def ask(data: dict):
    question = data.get("question", "")

    if not question.strip():
        return {"error": "Question is required"}

    answer = ask_question(question)

    return {"answer": answer}