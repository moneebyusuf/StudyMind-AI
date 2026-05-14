import { useEffect, useState } from "react";
import axios from "axios";
import "./App.css";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

const API = "http://127.0.0.1:8000";


function App() {
  const [token, setToken] = useState(localStorage.getItem("token") || "");
  const [user, setUser] = useState(null);

  const [authMode, setAuthMode] = useState("login");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [file, setFile] = useState(null);
  const [uploadMessage, setUploadMessage] = useState("");

  const [chats, setChats] = useState([]);
  const [activeChatId, setActiveChatId] = useState(null);
  const [messages, setMessages] = useState([]);

  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState("balanced");
  const [responseLanguage, setResponseLanguage] = useState("English");

  const authHeaders = {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  };

  useEffect(() => {
    if (token) {
      loadUser();
      loadChats();
    }
  }, [token]);

  async function loadUser() {
    try {
      const res = await axios.get(`${API}/me`, authHeaders);
      setUser(res.data);
    } catch {
      logout();
    }
  }

  async function login() {
    try {
      const res = await axios.post(`${API}/login`, {
        email,
        password,
      });

      localStorage.setItem("token", res.data.token);
      setToken(res.data.token);
      setUser(res.data.user);
    } catch (error) {
      alert(error.response?.data?.detail || "Login failed");
    }
  }

  async function signup() {
    try {
      const res = await axios.post(`${API}/signup`, {
        username,
        email,
        password,
      });

      localStorage.setItem("token", res.data.token);
      setToken(res.data.token);
      setUser(res.data.user);
    } catch (error) {
      alert(error.response?.data?.detail || "Signup failed");
    }
  }

  function logout() {
    localStorage.removeItem("token");
    setToken("");
    setUser(null);
    setChats([]);
    setMessages([]);
    setActiveChatId(null);
  }

  async function loadChats() {
    try {
      const res = await axios.get(`${API}/chats`, authHeaders);
      setChats(res.data);
    } catch (error) {
      console.error(error);
    }
  }

  async function createNewChat() {
    try {
      const res = await axios.post(
        `${API}/chats`,
        { title: "New Chat" },
        authHeaders
      );

      setActiveChatId(res.data.id);
      setMessages([]);
      await loadChats();
    } catch (error) {
      console.error(error);
    }
  }

  async function openChat(chatId) {
    setActiveChatId(chatId);

    try {
      const res = await axios.get(
        `${API}/chats/${chatId}/messages`,
        authHeaders
      );

      setMessages(
        res.data.map((msg) => ({
          role: msg.role === "ai" ? "ai" : "user",
          text: msg.content,
        }))
      );
    } catch (error) {
      console.error(error);
    }
  }

  async function deleteChat(chatId) {
  const confirmDelete = window.confirm("Delete this chat?");
  if (!confirmDelete) return;

  try {
    await axios.delete(`${API}/chats/${chatId}`, authHeaders);

    if (activeChatId === chatId) {
      setActiveChatId(null);
      setMessages([]);
    }

    await loadChats();
  } catch (error) {
    console.error(error);
    alert("Failed to delete chat.");
  }
}

  async function uploadPDF() {
  if (!file) {
    setUploadMessage("Please choose a file first.");
    return;
  }

  const formData = new FormData();
  formData.append("file", file);

  if (activeChatId) {
    formData.append("chat_id", activeChatId);
  }

  try {
    setUploadMessage("Uploading and processing file...");

    const res = await axios.post(`${API}/upload`, formData, {
      headers: {
        "Content-Type": "multipart/form-data",
        Authorization: `Bearer ${token}`,
      },
    });

    setActiveChatId(res.data.chat_id);
    await loadChats();
    setMessages([
    {
      role: "ai",
      text: `I finished reading "${file.name}". You can now ask me about it.`,
    },
  ]);

    setUploadMessage(
      `File ready: ${file.name} | Type: ${res.data.result.file_type} | Chunks: ${res.data.result.chunks}`
    );
  } catch (error) {
    setUploadMessage("Error uploading file.");
    console.error(error);
  }
}

  async function askAI() {
    if (!question.trim()) return;
    if (!activeChatId) {
      alert("Please upload a file or create a chat first.");
      return;
    }

    const userQuestion = question;
    setQuestion("");

    setMessages((prev) => [
      ...prev,
      { role: "user", text: userQuestion },
      { role: "ai", text: "Thinking..." },
    ]);

    try {
      const res = await axios.post(
        `${API}/ask`,
        {
          question: userQuestion,
          chat_id: activeChatId,
          mode,
          response_language: responseLanguage,
        },  
        authHeaders
      );

      setActiveChatId(res.data.chat_id);

      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          role: "ai",
          text: res.data.answer,
        };
        return updated;
      });

      await loadChats();
    } catch (error) {
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          role: "ai",
          text: error.response?.data?.detail || "Error getting answer.",
        };
        return updated;
      });
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      askAI();
    }
  }

  if (!token) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <h1>StudyMind AI</h1>
          <p>Sign in to save your PDFs, chats, and learning history.</p>

          <div className="auth-tabs">
            <button
              className={authMode === "login" ? "active" : ""}
              onClick={() => setAuthMode("login")}
            >
              Login
            </button>
            <button
              className={authMode === "signup" ? "active" : ""}
              onClick={() => setAuthMode("signup")}
            >
              Sign Up
            </button>
          </div>

          {authMode === "signup" && (
            <input
              placeholder="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          )}

          <input
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />

          <input
            placeholder="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          <button
            className="auth-submit"
            onClick={authMode === "login" ? login : signup}
          >
            {authMode === "login" ? "Login" : "Create Account"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <h2>StudyMind AI</h2>

        <div className="user-box">
          <p>{user?.username}</p>
          <button onClick={logout}>Logout</button>
        </div>

        <button className="new-chat-btn" onClick={createNewChat}>
          + New Chat
        </button>

        <div className="history">
          <h3>Chat History</h3>

          {chats.length === 0 ? (
            <p className="empty-history">No chats yet.</p>
          ) : (
            chats.map((chat) => (
              <div
                className={`history-item ${
                  activeChatId === chat.id ? "selected" : ""
                }`}
                key={chat.id}
              >
                <span onClick={() => openChat(chat.id)}>
                  {chat.title}
                </span>

                <button
                  className="delete-chat-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteChat(chat.id);
                  }}
                >
                  ×
                </button>
              </div>
            ))
          )}
        </div>
      </aside>

      <main className="main">
        <header className="top-bar">
          <div>
            <h1>StudyMind AI</h1>
            <p>Upload any supported file and ask anything about it.</p>
          </div>
        </header>

        <section className="pdf-box">
          <div>
            <h2>Upload File</h2>
            <p>Choose a file to teach StudyMind AI.</p>
          </div>

          <div className="upload-row">
            <input
              type="file"
              accept=".pdf,.txt,.md,.docx,.csv,.py,.js,.jsx,.html,.css,.json,.xlsx,.xls,.pptx,.ppt,.png,.jpg,.jpeg"
              onChange={(e) => setFile(e.target.files[0])}
            />

            <button onClick={uploadPDF}>Upload</button>
          </div>
          

          {uploadMessage && <p className="upload-message">{uploadMessage}</p>}
          <div className="language-row">
            <label>Response Language</label>

            <select
              value={responseLanguage}
              onChange={(e) => setResponseLanguage(e.target.value)}
            >
              <option value="Arabic">Arabic</option>
              <option value="English">English</option>
              <option value="Hebrew">Hebrew</option>
              <option value="French">French</option>
              <option value="Spanish">Spanish</option>
              <option value="German">German</option>
              <option value="Turkish">Turkish</option>
              <option value="Italian">Italian</option>
              <option value="Portuguese">Portuguese</option>
              <option value="Russian">Russian</option>
              <option value="Chinese">Chinese</option>
              <option value="Japanese">Japanese</option>
              <option value="Korean">Korean</option>
            </select>
          </div>
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
                  <ReactMarkdown
                    remarkPlugins={[remarkMath]}
                    rehypePlugins={[rehypeKatex]}
                  >
                    {msg.text}
                  </ReactMarkdown>
                </div>
              </div>
            ))
          )}
        </section>

        <footer className="input-area">
          <select value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="fast">Fast</option>
            <option value="balanced">Balanced</option>
            <option value="deep">Deep</option>
          </select>

          <textarea
            placeholder="Ask a question about your file..."
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