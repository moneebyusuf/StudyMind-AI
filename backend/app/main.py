from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Header, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import os
from app.rag import process_file, ask_question
from app.database import Base, engine, get_db
from app.models import User, Chat, Message
from app.auth import hash_password, verify_password, create_access_token, decode_access_token

Base.metadata.create_all(bind=engine)

app = FastAPI(title="StudyMind AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = os.path.dirname(BASE_DIR)
UPLOAD_DIR = os.path.join(PROJECT_DIR, "storage", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization token")

    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authorization scheme")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload.get("user_id")

    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


@app.get("/")
def home():
    return {"message": "StudyMind AI backend is running"}


@app.post("/signup")
def signup(data: dict, db: Session = Depends(get_db)):
    username = data.get("username", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not username or not email or not password:
        raise HTTPException(status_code=400, detail="Username, email, and password are required")

    existing_user = db.query(User).filter(
        (User.email == email) | (User.username == username)
    ).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="Username or email already exists")

    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(password)
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"user_id": user.id})

    return {
        "message": "Account created successfully",
        "token": token,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email
        }
    }


@app.post("/login")
def login(data: dict, db: Session = Depends(get_db)):
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")

    user = db.query(User).filter(User.email == email).first()

    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token({"user_id": user.id})

    return {
        "message": "Logged in successfully",
        "token": token,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email
        }
    }


@app.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email
    }


@app.post("/chats")
def create_chat(
    data: dict | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    data = data or {}
    title = data.get("title", "New Chat")

    chat = Chat(
        title=title,
        user_id=current_user.id
    )

    db.add(chat)
    db.commit()
    db.refresh(chat)

    return {
        "id": chat.id,
        "title": chat.title,
        "created_at": chat.created_at
    }


@app.get("/chats")
def get_chats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    chats = db.query(Chat).filter(
        Chat.user_id == current_user.id
    ).order_by(Chat.created_at.desc()).all()

    return [
        {
            "id": chat.id,
            "title": chat.title,
            "created_at": chat.created_at
        }
        for chat in chats
    ]


@app.get("/chats/{chat_id}/messages")
def get_chat_messages(
    chat_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    chat = db.query(Chat).filter(
        Chat.id == chat_id,
        Chat.user_id == current_user.id
    ).first()

    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    messages = db.query(Message).filter(
        Message.chat_id == chat.id
    ).order_by(Message.created_at.asc()).all()

    return [
        {
            "id": message.id,
            "role": message.role,
            "content": message.content,
            "created_at": message.created_at
        }
        for message in messages
    ]


@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    chat_id: int = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    allowed_extensions = [
        ".pdf", ".txt", ".md", ".docx", ".csv",
        ".py", ".js", ".jsx", ".html", ".css", ".json",
        ".xlsx", ".xls", ".pptx", ".ppt",
        ".png", ".jpg", ".jpeg"
    ]

    extension = os.path.splitext(file.filename)[1].lower()

    if extension not in allowed_extensions:
        return {
            "error": "Unsupported file type",
            "allowed": allowed_extensions
        }

    if not chat_id:
        chat = Chat(
            title=file.filename[:40],
            user_id=current_user.id
        )
        db.add(chat)
        db.commit()
        db.refresh(chat)
    else:
        chat = db.query(Chat).filter(
            Chat.id == chat_id,
            Chat.user_id == current_user.id
        ).first()

        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

    file_path = os.path.join(UPLOAD_DIR, file.filename)

    with open(file_path, "wb") as f:
        f.write(await file.read())

    result = process_file(file_path, chat.id)
    print("UPLOAD CHAT ID:", chat.id)
    print("UPLOADED FILE:", file.filename)
    print("UPLOAD RESULT:", result)

    return {
        "message": "File uploaded and processed successfully",
        "chat_id": chat.id,
        "file": file.filename,
        "result": result,
    }
@app.post("/ask")
async def ask(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    question = data.get("question", "").strip()
    chat_id = data.get("chat_id")
    mode = data.get("mode", "balanced")
    response_language = data.get("response_language", "English")

    if not question:
        raise HTTPException(status_code=400, detail="Question is required")

    if not chat_id:
        chat = Chat(
            title=question[:40],
            user_id=current_user.id
        )
        db.add(chat)
        db.commit()
        db.refresh(chat)
    else:
        chat = db.query(Chat).filter(
            Chat.id == chat_id,
            Chat.user_id == current_user.id
        ).first()

        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

    user_message = Message(
        chat_id=chat.id,
        role="user",
        content=question
    )

    db.add(user_message)
    db.commit()
    print("ASK CHAT ID:", chat.id)
    print("QUESTION:", question)

    answer = ask_question(
        question,
        chat_id=chat.id,
        mode=mode,
        response_language=response_language
    )
    ai_message = Message(
        chat_id=chat.id,
        role="ai",
        content=answer
    )

    db.add(ai_message)
    db.commit()

    return {
        "chat_id": chat.id,
        "answer": answer
    }


@app.delete("/chats/{chat_id}")
def delete_chat(
    chat_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    chat = db.query(Chat).filter(
        Chat.id == chat_id,
        Chat.user_id == current_user.id
    ).first()

    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    db.delete(chat)
    db.commit()

    return {"message": "Chat deleted successfully"}