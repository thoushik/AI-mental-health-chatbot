<<<<<<< HEAD
import os
import json
import time
import base64
import cv2
import numpy as np
from flask import Flask, jsonify, render_template, request, send_from_directory
from deepface import DeepFace
import requests
import asyncio
import edge_tts
from collections import deque
from datetime import datetime

# ----- CONFIG -----
AUDIO_DIR = "static/audio"
LOG_DIR = "session_logs"
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

app = Flask(__name__, static_folder="static", template_folder="templates")

# In-memory sliding window of last 50 emotion entries (timestamp, emotion, confidence)
last_emotions = deque(maxlen=50)

# Create a session log file (one per run) to store chat & emotion timeline
session_filename = os.path.join(LOG_DIR, f"session_{int(time.time())}.json")
session_log = {"start": datetime.utcnow().isoformat(), "chats": [], "emotions": []}
with open(session_filename, "w", encoding="utf-8") as f:
    json.dump(session_log, f, ensure_ascii=False, indent=2)


# ---------- FACE + EMOTION DETECTION ----------
def face_exists(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    fc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = fc.detectMultiScale(gray, 1.1, 5)
    return len(faces) > 0


def detect_emotion(frame):
    if not face_exists(frame):
        return "no face detected", 0.0
    try:
        # DeepFace analyze - enforce_detection False to avoid exceptions
        res = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False)
        if isinstance(res, list):
            res = res[0]
        emo = res.get("dominant_emotion", "unknown")
        # emotion dict may contain raw values that sum >100; we will normalize later
        conf = res.get("emotion", {}).get(emo, 0)
        # Clamp confidence to sensible range for chart display
        try:
            conf = float(conf)
        except Exception:
            conf = 0.0
        # Clip to 0-100
        if conf < 0:
            conf = 0.0
        if conf > 1000:  # sometimes DeepFace returns huge numbers; clamp
            conf = conf % 100
        if conf > 100:
            conf = conf / (conf / 100.0)
        return emo, round(conf, 2)
    except Exception as e:
        print("DeepFace error:", e)
        return "error", 0.0


# ---------- CHAT (Ollama local) ----------
def ollama_chat(prompt, lang="en", emotion_context=None):
    # We embed the emotion context into the system prompt so replies are empathetic
    tone_hint = ""
    if emotion_context in ("sad", "fear", "angry"):
        tone_hint = "The user seems distressed. Reply in a calm, comforting, and empathetic tone. Keep sentences short."
    elif emotion_context == "neutral":
        tone_hint = "The user seems neutral. Reply normally and concisely."
    elif emotion_context == "happy":
        tone_hint = "The user seems positive; reply with encouraging, supportive tone."

    system_prompt = (
        "You are a kind and empathetic mental-health assistant. "
        "If the user speaks Tamil, reply fully in Tamil; otherwise, reply in English. "
        "Keep answers brief, calm, and supportive. " + tone_hint
    )

    payload = {
        "model": "llama3",
        "prompt": f"{system_prompt}\n\nUser ({lang}): {prompt}\nAssistant ({lang}):",
        "stream": False,
    }
    try:
        r = requests.post("http://localhost:11434/api/generate", json=payload, timeout=60)
        r.raise_for_status()
        return r.json().get("response", "").strip()
    except Exception as e:
        print("Ollama error:", e)
        # fallback minimal responses
        if lang == "ta":
            return "நான் இப்போ என்ன சொல்வது என்று தெரியவில்லை. நிச்சயமாக நான் உன்னுடன் இருக்கிறேன்."
        return "Sorry, I am having trouble thinking right now. I'm here for you."


# ---------- Edge TTS (async wrapper) ----------
async def generate_edge_audio_async(text, voice, path):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(path)
    return path


def make_audio(text, lang="en", emotion=None):
    """
    Create TTS audio file and return URL path.
    Use different voice or slower rate for distressed emotions.
    """
    # Choose voice and (optionally) style/rate note: edge-tts API doesn't accept rate param in Communicate()
    # We keep voice selection simple: Tamil voice for ta, English for en
    voice = "ta-IN-PallaviNeural" if lang == "ta" else "en-IN-PrabhatNeural"

    # For distressed emotions, prepend a small calming instruction (Edge TTS will speak it too).
    # Alternatively we could use SSML to adjust prosody but keep it simple to avoid compatibility issues.
    if emotion in ("sad", "fear", "angry"):
        speak_text = f"(Speak slowly and calmly.) {text}"
    else:
        speak_text = text

    filename = f"output_{int(time.time())}.mp3"
    path = os.path.join(AUDIO_DIR, filename)

    try:
        # Run edge_tts save asynchronously
        asyncio.run(generate_edge_audio_async(speak_text, voice, path))
        # Return URL for client
        return f"/static/audio/{filename}?v={int(os.path.getmtime(path))}"
    except Exception as e:
        print("Edge TTS error:", e)
        # fallback: return empty and client will use browser TTS
        return ""


# ---------- Helpers: logging + crisis detection + mood summary ----------
CRISIS_TEXT_KEYWORDS = [
    "suicide", "kill myself", "die", "end my life", "i want to die", "i'm going to die",
    "suicidal", "suicide attempt", "i cant go on", "cant live", "end it all"
]
CRISIS_TAMIL_KEYWORDS = ["தற்கொலை", "வரவேற்பு", "தற்கொலைக்கு"]  # add more Tamil if needed

def append_emotion_log(emotion, confidence):
    ts = time.time()
    last_emotions.append({"t": ts, "emotion": emotion, "confidence": float(confidence)})
    # append to session log file
    try:
        with open(session_filename, "r+", encoding="utf-8") as f:
            data = json.load(f)
            data.setdefault("emotions", []).append({"time": datetime.utcnow().isoformat(), "emotion": emotion, "confidence": confidence})
            f.seek(0)
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.truncate()
    except Exception as e:
        print("Log write error:", e)


def append_chat_log(user_msg, bot_reply):
    try:
        with open(session_filename, "r+", encoding="utf-8") as f:
            data = json.load(f)
            data.setdefault("chats", []).append({
                "time": datetime.utcnow().isoformat(),
                "user": user_msg,
                "bot": bot_reply
            })
            f.seek(0)
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.truncate()
    except Exception as e:
        print("Chat log write error:", e)


def check_text_crisis(msg):
    low = msg.lower()
    for kw in CRISIS_TEXT_KEYWORDS:
        if kw in low:
            return True
    # Tamil basic check
    for kw in CRISIS_TAMIL_KEYWORDS:
        if kw in msg:
            return True
    return False


def check_sustained_face_crisis(seconds=15):
    """
    Return True if the last emotions contain only 'sad','fear','angry' for >= seconds.
    We look from newest backwards until we find a non-distressed emotion or exceed window.
    """
    if len(last_emotions) == 0:
        return False
    now = time.time()
    # Walk backwards
    total_duration = 0
    prev_t = None
    for e in reversed(last_emotions):
        t = e["t"]
        if prev_t is None:
            prev_t = t
        # if the emotion isn't one of the crisis ones, stop
        if e["emotion"] not in ("sad", "fear", "angry"):
            return False
        # accumulate duration roughly by difference to previous
        prev_t = t
        total_duration = now - t
        if total_duration >= seconds:
            return True
    return False


def mood_summary():
    """
    Quick summary from last 10 emotions: majority emotion and simple text.
    """
    data = list(last_emotions)[-10:]
    if not data:
        return "No emotion history yet."
    counts = {}
    for d in data:
        counts[d["emotion"]] = counts.get(d["emotion"], 0) + 1
    # pick top
    top_emotion = max(counts.items(), key=lambda x: x[1])[0]
    return f"Recent mood: {top_emotion} (from last {len(data)} samples)."


# ---------- ROUTES ----------
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/analyze_frame", methods=["POST"])
def analyze_frame():
    dataurl = request.json.get("image", "")
    if "," not in dataurl:
        return jsonify({"emotion": "no face detected", "confidence": 0})
    try:
        b64 = dataurl.split(",", 1)[1]
        frame = cv2.imdecode(np.frombuffer(base64.b64decode(b64), np.uint8), cv2.IMREAD_COLOR)
        emo, conf = detect_emotion(frame)
        append_emotion_log(emo, conf)
        return jsonify({"emotion": emo, "confidence": conf})
    except Exception as e:
        print("Frame processing error:", e)
        return jsonify({"emotion": "error", "confidence": 0})


@app.route("/chat", methods=["POST"])
def chat():
    req = request.json or {}
    msg = req.get("message", "").strip()
    if not msg:
        return jsonify({"reply": "I'm here to listen.", "audio": ""})

    # language detection (Tamil unicode range)
    lang = "ta" if any('\u0B80' <= c <= '\u0BFF' for c in msg) else "en"

    # check crisis by text
    text_crisis = check_text_crisis(msg)

    # pass latest emotion context (if any)
    emotion_context = None
    if last_emotions:
        emotion_context = last_emotions[-1]["emotion"]

    # Ask the model with emotion-aware prompt
    reply = ollama_chat(msg, lang=lang, emotion_context=emotion_context)

    # Append chat log
    append_chat_log(msg, reply)

    # TTS generation (voice choice depends on lang and emotion)
    audio_url = make_audio(reply, lang=lang, emotion=emotion_context)

    # check sustained face-based crisis
    face_crisis = check_sustained_face_crisis(seconds=15)

    crisis_triggered = text_crisis or face_crisis

    # if crisis, include flag so frontend shows modal immediately
    return jsonify({
        "reply": reply,
        "audio": audio_url,
        "crisis": crisis_triggered,
        "mood_summary": mood_summary()
    })


@app.route("/history_emotions", methods=["GET"])
def history_emotions():
    """
    Return last up to 10 emotions for chart rendering
    """
    items = list(last_emotions)[-10:]
    # normalize confidence to 0..100 and ensure numeric
    result = []
    for i in items:
        conf = float(i.get("confidence", 0) or 0)
        if conf < 0:
            conf = 0.0
        if conf > 100:
            # if somehow >100, bring into 0-100 by modulo if wildly large
            conf = conf % 101
        result.append({"t": i["t"], "emotion": i["emotion"], "confidence": round(conf, 2)})
    return jsonify(result)


@app.route("/static/audio/<path:filename>")
def audio_file(filename):
    return send_from_directory(AUDIO_DIR, filename, mimetype="audio/mpeg")


if __name__ == "__main__":
    print("🚀 Server running: http://127.0.0.1:5000/")
    app.run(host="127.0.0.1", port=5000, debug=True)
=======
import os
import json
import time
import base64
import cv2
import numpy as np
from flask import Flask, jsonify, render_template, request, send_from_directory
from deepface import DeepFace
import requests
import asyncio
import edge_tts
from collections import deque
from datetime import datetime

# ----- CONFIG -----
AUDIO_DIR = "static/audio"
LOG_DIR = "session_logs"
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

app = Flask(__name__, static_folder="static", template_folder="templates")

# In-memory sliding window of last 50 emotion entries (timestamp, emotion, confidence)
last_emotions = deque(maxlen=50)

# Create a session log file (one per run) to store chat & emotion timeline
session_filename = os.path.join(LOG_DIR, f"session_{int(time.time())}.json")
session_log = {"start": datetime.utcnow().isoformat(), "chats": [], "emotions": []}
with open(session_filename, "w", encoding="utf-8") as f:
    json.dump(session_log, f, ensure_ascii=False, indent=2)


# ---------- FACE + EMOTION DETECTION ----------
def face_exists(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    fc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = fc.detectMultiScale(gray, 1.1, 5)
    return len(faces) > 0


def detect_emotion(frame):
    if not face_exists(frame):
        return "no face detected", 0.0
    try:
        # DeepFace analyze - enforce_detection False to avoid exceptions
        res = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False)
        if isinstance(res, list):
            res = res[0]
        emo = res.get("dominant_emotion", "unknown")
        # emotion dict may contain raw values that sum >100; we will normalize later
        conf = res.get("emotion", {}).get(emo, 0)
        # Clamp confidence to sensible range for chart display
        try:
            conf = float(conf)
        except Exception:
            conf = 0.0
        # Clip to 0-100
        if conf < 0:
            conf = 0.0
        if conf > 1000:  # sometimes DeepFace returns huge numbers; clamp
            conf = conf % 100
        if conf > 100:
            conf = conf / (conf / 100.0)
        return emo, round(conf, 2)
    except Exception as e:
        print("DeepFace error:", e)
        return "error", 0.0


# ---------- CHAT (Ollama local) ----------
def ollama_chat(prompt, lang="en", emotion_context=None):
    # We embed the emotion context into the system prompt so replies are empathetic
    tone_hint = ""
    if emotion_context in ("sad", "fear", "angry"):
        tone_hint = "The user seems distressed. Reply in a calm, comforting, and empathetic tone. Keep sentences short."
    elif emotion_context == "neutral":
        tone_hint = "The user seems neutral. Reply normally and concisely."
    elif emotion_context == "happy":
        tone_hint = "The user seems positive; reply with encouraging, supportive tone."

    system_prompt = (
        "You are a kind and empathetic mental-health assistant. "
        "If the user speaks Tamil, reply fully in Tamil; otherwise, reply in English. "
        "Keep answers brief, calm, and supportive. " + tone_hint
    )

    payload = {
        "model": "llama3",
        "prompt": f"{system_prompt}\n\nUser ({lang}): {prompt}\nAssistant ({lang}):",
        "stream": False,
    }
    try:
        r = requests.post("http://localhost:11434/api/generate", json=payload, timeout=60)
        r.raise_for_status()
        return r.json().get("response", "").strip()
    except Exception as e:
        print("Ollama error:", e)
        # fallback minimal responses
        if lang == "ta":
            return "நான் இப்போ என்ன சொல்வது என்று தெரியவில்லை. நிச்சயமாக நான் உன்னுடன் இருக்கிறேன்."
        return "Sorry, I am having trouble thinking right now. I'm here for you."


# ---------- Edge TTS (async wrapper) ----------
async def generate_edge_audio_async(text, voice, path):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(path)
    return path


def make_audio(text, lang="en", emotion=None):
    """
    Create TTS audio file and return URL path.
    Use different voice or slower rate for distressed emotions.
    """
    # Choose voice and (optionally) style/rate note: edge-tts API doesn't accept rate param in Communicate()
    # We keep voice selection simple: Tamil voice for ta, English for en
    voice = "ta-IN-PallaviNeural" if lang == "ta" else "en-IN-PrabhatNeural"

    # For distressed emotions, prepend a small calming instruction (Edge TTS will speak it too).
    # Alternatively we could use SSML to adjust prosody but keep it simple to avoid compatibility issues.
    if emotion in ("sad", "fear", "angry"):
        speak_text = f"(Speak slowly and calmly.) {text}"
    else:
        speak_text = text

    filename = f"output_{int(time.time())}.mp3"
    path = os.path.join(AUDIO_DIR, filename)

    try:
        # Run edge_tts save asynchronously
        asyncio.run(generate_edge_audio_async(speak_text, voice, path))
        # Return URL for client
        return f"/static/audio/{filename}?v={int(os.path.getmtime(path))}"
    except Exception as e:
        print("Edge TTS error:", e)
        # fallback: return empty and client will use browser TTS
        return ""


# ---------- Helpers: logging + crisis detection + mood summary ----------
CRISIS_TEXT_KEYWORDS = [
    "suicide", "kill myself", "die", "end my life", "i want to die", "i'm going to die",
    "suicidal", "suicide attempt", "i cant go on", "cant live", "end it all"
]
CRISIS_TAMIL_KEYWORDS = ["தற்கொலை", "வரவேற்பு", "தற்கொலைக்கு"]  # add more Tamil if needed

def append_emotion_log(emotion, confidence):
    ts = time.time()
    last_emotions.append({"t": ts, "emotion": emotion, "confidence": float(confidence)})
    # append to session log file
    try:
        with open(session_filename, "r+", encoding="utf-8") as f:
            data = json.load(f)
            data.setdefault("emotions", []).append({"time": datetime.utcnow().isoformat(), "emotion": emotion, "confidence": confidence})
            f.seek(0)
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.truncate()
    except Exception as e:
        print("Log write error:", e)


def append_chat_log(user_msg, bot_reply):
    try:
        with open(session_filename, "r+", encoding="utf-8") as f:
            data = json.load(f)
            data.setdefault("chats", []).append({
                "time": datetime.utcnow().isoformat(),
                "user": user_msg,
                "bot": bot_reply
            })
            f.seek(0)
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.truncate()
    except Exception as e:
        print("Chat log write error:", e)


def check_text_crisis(msg):
    low = msg.lower()
    for kw in CRISIS_TEXT_KEYWORDS:
        if kw in low:
            return True
    # Tamil basic check
    for kw in CRISIS_TAMIL_KEYWORDS:
        if kw in msg:
            return True
    return False


def check_sustained_face_crisis(seconds=15):
    """
    Return True if the last emotions contain only 'sad','fear','angry' for >= seconds.
    We look from newest backwards until we find a non-distressed emotion or exceed window.
    """
    if len(last_emotions) == 0:
        return False
    now = time.time()
    # Walk backwards
    total_duration = 0
    prev_t = None
    for e in reversed(last_emotions):
        t = e["t"]
        if prev_t is None:
            prev_t = t
        # if the emotion isn't one of the crisis ones, stop
        if e["emotion"] not in ("sad", "fear", "angry"):
            return False
        # accumulate duration roughly by difference to previous
        prev_t = t
        total_duration = now - t
        if total_duration >= seconds:
            return True
    return False


def mood_summary():
    """
    Quick summary from last 10 emotions: majority emotion and simple text.
    """
    data = list(last_emotions)[-10:]
    if not data:
        return "No emotion history yet."
    counts = {}
    for d in data:
        counts[d["emotion"]] = counts.get(d["emotion"], 0) + 1
    # pick top
    top_emotion = max(counts.items(), key=lambda x: x[1])[0]
    return f"Recent mood: {top_emotion} (from last {len(data)} samples)."


# ---------- ROUTES ----------
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/analyze_frame", methods=["POST"])
def analyze_frame():
    dataurl = request.json.get("image", "")
    if "," not in dataurl:
        return jsonify({"emotion": "no face detected", "confidence": 0})
    try:
        b64 = dataurl.split(",", 1)[1]
        frame = cv2.imdecode(np.frombuffer(base64.b64decode(b64), np.uint8), cv2.IMREAD_COLOR)
        emo, conf = detect_emotion(frame)
        append_emotion_log(emo, conf)
        return jsonify({"emotion": emo, "confidence": conf})
    except Exception as e:
        print("Frame processing error:", e)
        return jsonify({"emotion": "error", "confidence": 0})


@app.route("/chat", methods=["POST"])
def chat():
    req = request.json or {}
    msg = req.get("message", "").strip()
    if not msg:
        return jsonify({"reply": "I'm here to listen.", "audio": ""})

    # language detection (Tamil unicode range)
    lang = "ta" if any('\u0B80' <= c <= '\u0BFF' for c in msg) else "en"

    # check crisis by text
    text_crisis = check_text_crisis(msg)

    # pass latest emotion context (if any)
    emotion_context = None
    if last_emotions:
        emotion_context = last_emotions[-1]["emotion"]

    # Ask the model with emotion-aware prompt
    reply = ollama_chat(msg, lang=lang, emotion_context=emotion_context)

    # Append chat log
    append_chat_log(msg, reply)

    # TTS generation (voice choice depends on lang and emotion)
    audio_url = make_audio(reply, lang=lang, emotion=emotion_context)

    # check sustained face-based crisis
    face_crisis = check_sustained_face_crisis(seconds=15)

    crisis_triggered = text_crisis or face_crisis

    # if crisis, include flag so frontend shows modal immediately
    return jsonify({
        "reply": reply,
        "audio": audio_url,
        "crisis": crisis_triggered,
        "mood_summary": mood_summary()
    })


@app.route("/history_emotions", methods=["GET"])
def history_emotions():
    """
    Return last up to 10 emotions for chart rendering
    """
    items = list(last_emotions)[-10:]
    # normalize confidence to 0..100 and ensure numeric
    result = []
    for i in items:
        conf = float(i.get("confidence", 0) or 0)
        if conf < 0:
            conf = 0.0
        if conf > 100:
            # if somehow >100, bring into 0-100 by modulo if wildly large
            conf = conf % 101
        result.append({"t": i["t"], "emotion": i["emotion"], "confidence": round(conf, 2)})
    return jsonify(result)


@app.route("/static/audio/<path:filename>")
def audio_file(filename):
    return send_from_directory(AUDIO_DIR, filename, mimetype="audio/mpeg")


if __name__ == "__main__":
    print("🚀 Server running: http://127.0.0.1:5000/")
    app.run(host="127.0.0.1", port=5000, debug=True)
>>>>>>> 0bb02401fafb56ebe823df1c028f8295430c5fbd
