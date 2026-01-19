// ====== Elements ======
const chatBox = document.getElementById("chatBox");
const userInput = document.getElementById("userInput");
const sendBtn = document.getElementById("sendBtn");
const micBtn = document.getElementById("micBtn");
const langToggle = document.getElementById("langToggle");
const botAudio = document.getElementById("botAudio");
const emoLabel = document.getElementById("currentMood");
const emoConf = document.getElementById("emoConf");
const progBar = document.getElementById("progBar");
const moodSummaryEl = document.getElementById("moodSummary");
const crisisModal = document.getElementById("crisisModal");
const okCrisis = document.getElementById("okCrisis");

// ====== Chat helpers ======
function appendMessage(text, sender) {
  const div = document.createElement("div");
  div.className = "msg " + (sender === "user" ? "you" : "bot");
  div.textContent = text;
  chatBox.appendChild(div);
  chatBox.scrollTop = chatBox.scrollHeight;
}

async function postJSON(url, data) {
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
  return resp.json();
}

// ====== Send message ======
async function sendMessage() {
  const txt = userInput.value.trim();
  if (!txt) return;
  appendMessage(txt, "user");
  userInput.value = "";

  try {
    const res = await postJSON("/chat", { message: txt });
    appendMessage(res.reply, "bot");

    // Update mood summary if provided
    if (res.mood_summary) moodSummaryEl.textContent = res.mood_summary;

    if (res.audio) {
      botAudio.src = res.audio;
      botAudio.play().catch(e => {
        // browser may block autoplay - show fallback
        console.warn("Audio play blocked", e);
      });
    } else {
      // fallback to browser TTS
      speakBrowser(res.reply);
    }

    // If crisis flagged, show modal
    if (res.crisis) {
      showCrisisModal();
    }
  } catch (e) {
    console.error("Send error:", e);
    appendMessage("Sorry, something went wrong.", "bot");
  }
}

sendBtn.addEventListener("click", sendMessage);
userInput.addEventListener("keypress", e => { if (e.key === "Enter") sendMessage(); });

// ====== Mic & language toggle ======
let micLang = "en-IN"; // default
langToggle.addEventListener("click", () => {
  micLang = (micLang === "en-IN") ? "ta-IN" : "en-IN";
  langToggle.textContent = micLang === "en-IN" ? "EN" : "TA";
});

let recognition;
if ("webkitSpeechRecognition" in window) {
  recognition = new webkitSpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.lang = micLang;

  recognition.onresult = (e) => {
    const txt = e.results[0][0].transcript;
    userInput.value = txt;
    sendMessage();
  };

  recognition.onerror = (e) => {
    console.error("Speech recognition error", e);
    micBtn.classList.remove("listening");
  };

  recognition.onend = () => micBtn.classList.remove("listening");
}

micBtn.addEventListener("click", () => {
  if (!recognition) return alert("Speech recognition not supported by this browser.");
  recognition.lang = micLang;
  micBtn.classList.add("listening");
  recognition.start();
});

// ====== Browser TTS fallback ======
function speakBrowser(text) {
  const synth = window.speechSynthesis;
  synth.cancel();
  const isTamil = /[\u0B80-\u0BFF]/.test(text);
  const utter = new SpeechSynthesisUtterance(text);
  utter.lang = isTamil ? "ta-IN" : "en-IN";
  // find matching voice if possible
  const voices = synth.getVoices();
  const v = voices.find(x => x.lang === utter.lang) || voices[0];
  if (v) utter.voice = v;
  utter.rate = 1;
  synth.speak(utter);
}

// ====== Camera + Emotion polling ======
const video = document.getElementById("camera");
const canvas = document.getElementById("frame");
const ctx = canvas.getContext("2d");

navigator.mediaDevices.getUserMedia({ video: true })
  .then(stream => { video.srcObject = stream; })
  .catch(err => { console.error("Camera error:", err); });

async function sendFrame() {
  if (!video || video.readyState !== video.HAVE_ENOUGH_DATA) return;
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  const img = canvas.toDataURL("image/jpeg", 0.7);
  try {
    const res = await postJSON("/analyze_frame", { image: img });
    updateEmotionUI(res.emotion, res.confidence);
  } catch (e) {
    console.error("Frame send error:", e);
  }
}

setInterval(sendFrame, 1500);

// ====== Emotion UI & chart ======
function updateEmotionUI(emotion, confidence) {
  emoLabel.textContent = emotion || "--";
  emoConf.textContent = (confidence || 0).toFixed(1) + "%";
  // update progress bar (0..100)
  const val = Math.max(0, Math.min(100, Number(confidence || 0)));
  progBar.style.width = val + "%";

  // fetch history and update chart
  refreshChart();
}

let chart = null;
async function refreshChart() {
  try {
    const res = await fetch("/history_emotions");
    const data = await res.json(); // array of {t, emotion, confidence}

    // prepare labels (simple last 10 indices) and values
    const labels = data.map((d, i) => {
      return d.emotion;
    });
    const values = data.map(d => {
      let v = Number(d.confidence || 0);
      v = Math.max(0, Math.min(100, v));
      return v;
    });

    // if empty, clear
    if (!chart) {
      const ctxC = document.getElementById("emotionChart").getContext("2d");
      chart = new Chart(ctxC, {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [{
            label: 'Confidence (%)',
            data: values,
            backgroundColor: values.map(v => v >= 75 ? '#34A853' : '#6B7280')
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: { beginAtZero: true, max: 100, ticks: { stepSize: 20 } }
          },
          plugins: { legend: { display: false } }
        }
      });
    } else {
      chart.data.labels = labels;
      chart.data.datasets[0].data = values;
      chart.data.datasets[0].backgroundColor = values.map(v => v >= 75 ? '#34A853' : '#6B7280');
      chart.update();
    }
  } catch (e) {
    console.error("Chart refresh error:", e);
  }
}

// initial chart refresh
setTimeout(refreshChart, 500);

// ====== Crisis Modal ======
function showCrisisModal() {
  crisisModal.classList.remove("hidden");
}
okCrisis.addEventListener("click", () => {
  crisisModal.classList.add("hidden");
});

// ====== UX: ensure chatbox stays scrollable at various zooms ======
function ensureChatLayout() {
  // sets chatbox max-height relative to viewport minus header and paddings
  const headerHeight = document.querySelector(".app-header").offsetHeight || 120;
  const mainPadding = 60; // approx
  const available = window.innerHeight - headerHeight - mainPadding;
  const chatBoxEl = document.querySelector(".chatbox");
  if (chatBoxEl) {
    chatBoxEl.style.maxHeight = Math.max(300, available - 120) + "px";
  }
}
window.addEventListener("resize", ensureChatLayout);
document.addEventListener("DOMContentLoaded", ensureChatLayout);
setTimeout(ensureChatLayout, 300);
