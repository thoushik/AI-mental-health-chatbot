# 🧠 DudeAI — Emotion-Based Mental Health Chatbot

### 🎯 Overview
**DudeAI** is an AI-powered empathetic chatbot designed to support mental health through emotional awareness.  
It combines **real-time facial emotion detection**, **local AI response generation (LLaMA3 via Ollama)**, and **voice-based interaction** (Tamil + English).

---

## ⚙️ Features
- 🎥 Real-time **facial emotion detection** using **DeepFace + OpenCV**
- 💬 Emotion-aware text replies using **LLaMA3 (Ollama local model)**
- 🔊 Voice output with **Microsoft Edge TTS** (Tamil & English)
- 📊 Live **emotion trend chart** and **mood summary**
- 🚨 Crisis detection (based on text + sustained emotion pattern)
- 🗂️ Automatic **session logs** with chat & emotion timeline

---

## 🧩 Folder Structure
```
DudeAI/
│
├── app.py
├── requirements.txt
├── README.md
│
├── templates/
│   └── index.html
│
├── static/
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   └── script.js
│   └── audio/              # created automatically for TTS output
│
└── session_logs/           # auto-created for chat/emotion logs
```

---

## 🧱 1️⃣ Environment Setup

### Create and activate virtual environment

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

---

## 📦 2️⃣ Install Dependencies
Install all required packages from `requirements.txt`:

```bash
pip install -r requirements.txt
```

If you face OpenCV or DeepFace errors, upgrade pip:
```bash
python -m pip install --upgrade pip
```

---

## 🤖 3️⃣ Ollama Setup (Local Chat Model)

**Step 1:** Download Ollama  
👉 [https://ollama.com/download](https://ollama.com/download)

**Step 2:** Pull the LLaMA3 model  
```bash
ollama pull llama3
```

**Step 3:** Test that Ollama works  
```bash
ollama run llama3
```
If it generates replies, Ollama is running correctly at `http://localhost:11434`.

---

## 🗣️ 4️⃣ Voice Setup (Edge TTS)
Check available voices:
```bash
python -m edge_tts --list-voices
```

Ensure these two voices are available:
- `en-IN-PrabhatNeural`  → English  
- `ta-IN-PallaviNeural`  → Tamil

These are automatically used by the chatbot for voice output.

---

## 🚀 5️⃣ Run the Application
Run the Flask backend:
```bash
python app.py
```

Once you see:
```
🚀 Server running: 
```

Open your browser and visit:  


Allow camera access when prompted.

---

## 💬 6️⃣ How It Works
1. **Webcam feed** → detects emotion using DeepFace  
2. **Chat messages** → sent to local **LLaMA3 (Ollama)** model  
3. **Emotion context** → influences chatbot tone (empathetic / supportive)  
4. **Edge TTS** → converts replies to speech  
5. **Logs** → stored in `/session_logs/` with timestamps

---

## 📈 7️⃣ Emotion & Crisis Detection
- Tracks emotion trends using a live **Chart.js graph**
- If user remains **sad/fear/angry** for ≥15 seconds → triggers **Crisis Modal**
- Crisis text detection for Tamil + English messages

---

## 🗂️ 8️⃣ Logs & Data
Each session creates a new log file under:
```
session_logs/session_<timestamp>.json
```
It stores:
- Detected emotions (with confidence)
- Chat messages (user + bot)
- UTC timestamps

---

## 🧾 9️⃣ Tech Stack
| Component | Technology |
|------------|-------------|
| Backend | Flask (Python) |
| Frontend | HTML, CSS, JS |
| AI Model | LLaMA3 (via Ollama) |
| Emotion Detection | DeepFace + OpenCV |
| Voice | Microsoft Edge TTS |
| Data Format | JSON Logs |

---

## 🧑‍💻 10️⃣ Developer Info
**Developers:**  
- S. Thoushik (21MIS1058)  

**Institution:**  
Vellore Institute of Technology, Chennai  
Integrated M.Tech Software Engineering  

---

## 🏁 11️⃣ Quick Summary Commands

```bash
# Step 1: Setup environment
python -m venv venv
venv\Scripts\activate

# Step 2: Install all libraries
pip install -r requirements.txt

# Step 3: Start Ollama (in a separate terminal)
ollama pull llama3

# Step 4: Run Flask app
python app.py

# Step 5: Visit in browser
http://127.0.0.1:5000/
```

---

### ✅ Output Example
- **Detected Emotion:** Happy (Confidence: 92%)  
- **Bot Reply (English):** “That’s great! Keep that smile on.”  
- **Bot Reply (Tamil):** “அது அருமை! உன் முகத்தில் அந்த புன்னகையை வைத்துக்கொள்.”  
- **Voice Output:** Generated using Edge TTS  
- **Log File:** `session_logs/session_1729638450.json`

---

### 💡 Notes
- Ensure your webcam is accessible and browser permissions are granted.
- Ollama must be running in the background before you start the Flask server.
- Voice generation may take a few seconds depending on system performance.

---

### ❤️ “I’ll be there for you…”
This project is built with empathy, for a better tomorrow.
