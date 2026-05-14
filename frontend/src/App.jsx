import { useState } from "react";
import axios from "axios";
import "./App.css";

function App() {
  const [file, setFile] = useState(null);
  const [uploadMessage, setUploadMessage] = useState("");
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);

  async function uploadPDF() {
    if (!file) {
      setUploadMessage("Please choose a PDF file first.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    try {
      setUploadMessage("Uploading and processing PDF...");

      const res = await axios.post("http://127.0.0.1:8000/upload", formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      });

      setUploadMessage(
        `PDF ready: ${file.name} | Pages: ${res.data.result.pages} | Chunks: ${res.data.result.chunks}`
      );

      setMessages([
        {
          role: "ai",
          text: `I finished reading "${file.name}". You can now ask me questions about it.`,
        },
      ]);
    } catch (error) {
      setUploadMessage("Error uploading PDF. Make sure the backend is running.");
      console.error(error);
    }
  }

  async function askAI() {
    if (!question.trim()) return;

    const userQuestion = question;

    setMessages((prev) => [
      ...prev,
      { role: "user", text: userQuestion },
      { role: "ai", text: "Thinking..." },
    ]);

    setQuestion("");

    try {
      const res = await axios.post("http://127.0.0.1:8000/ask", {
        question: userQuestion,
      });

      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          role: "ai",
          text: res.data.answer,
        };
        return updated;
      });
    } catch (error) {
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          role: "ai",
          text: "Error getting answer. Make sure the PDF was uploaded, backend is running, and Ollama is working.",
        };
        return updated;
      });

      console.error(error);
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      askAI();
    }
  }

  function clearChat() {
    setMessages([]);
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <h2>StudyMind AI</h2>

        <button className="new-chat-btn" onClick={clearChat}>
          + New Chat
        </button>

        <div className="history">
          <h3>Chat History</h3>

          {messages.length === 0 ? (
            <p className="empty-history">No messages yet.</p>
          ) : (
            messages
              .filter((msg) => msg.role === "user")
              .map((msg, index) => (
                <div className="history-item" key={index}>
                  {msg.text.slice(0, 35)}
                  {msg.text.length > 35 ? "..." : ""}
                </div>
              ))
          )}
        </div>
      </aside>

      <main className="main">
        <header className="top-bar">
          <div>
            <h1>StudyMind AI</h1>
            <p>Upload a PDF and ask anything about it.</p>
          </div>
        </header>

        <section className="pdf-box">
          <div>
            <h2>Upload PDF</h2>
            <p>Choose a PDF file to teach StudyMind AI.</p>
          </div>

          <div className="upload-row">
            <input
              type="file"
              accept="application/pdf"
              onChange={(e) => setFile(e.target.files[0])}
            />

            <button onClick={uploadPDF}>Upload</button>
          </div>

          {uploadMessage && <p className="upload-message">{uploadMessage}</p>}
        </section>

        <section className="chat-area">
          {messages.length === 0 ? (
            <div className="welcome">
              <h2>Start learning with your PDF</h2>
              <p>
                Upload a PDF above, then ask questions like:
                “Explain this topic simply” or “Give me examples.”
              </p>
            </div>
          ) : (
            messages.map((msg, index) => (
              <div
                className={`message-row ${
                  msg.role === "user" ? "user-row" : "ai-row"
                }`}
                key={index}
              >
                <div className={`bubble ${msg.role === "user" ? "user" : "ai"}`}>
                  <span className="label">
                    {msg.role === "user" ? "You" : "StudyMind AI"}
                  </span>
                  <p>{msg.text}</p>
                </div>
              </div>
            ))
          )}
        </section>

        <footer className="input-area">
          <textarea
            placeholder="Ask a question about your PDF..."
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
          />

          <button onClick={askAI}>Send</button>
        </footer>
      </main>
    </div>
  );
}

export default App;