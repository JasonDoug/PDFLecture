# 📖 Usage Guide

Welcome to the Audio Intelligence Suite! This guide covers the user experience for both primary applications in the ecosystem.

---

## 🚀 The Portal Launcher
When you start the suite via `./start_suite.sh`, you arrive at the **Portal**. This is your cockpit for navigating between internal apps.

- **University Lecture**: Use this for academic papers, historical documents, and complex reports.
- **Premium Audiobook**: Use this for fiction, personal documents, and casual reading.

---

## 🎓 University Lecture Guide

### 1. Uploading
Drop any PDF into the upload zone. The system will automatically:
- **Analyze**: Identify the subject, structure, and depth.
- **Script**: Draft a lecture using your selected agent.
- **Synthesize**: Generate high-quality narration.

### 2. Interaction
Once the lecture is ready, you can:
- **Follow the Highlights**: The transcript highlights the current sentence in real-time.
- **Click to Seek**: Tap any sentence in the transcript to jump the audio to that exact moment.
- **Table of Contents**: Use the sidebar to navigate between sections of the paper.

---

## 🎧 Premium Audiobook Guide

### 1. The Reader
The Audiobook app is designed for "Deep Work" and immersive listening. 
- **Upload**: Select your file and choose a voice identity.
- **Compact View**: Toggle between the full player and a minimalist "Now Playing" window.

### 2. Features
- **15s Skip**: Quickly jump forward or back.
- **Variable Speed**: Adjust from 0.5x to 2.0x for efficient consumption.
- **MP3 Download**: Save your narrated document for offline listening on your phone.

---

## 🛠️ Logs & Diagnostics
If a file fails to process:
1. Open the **Diagnostics** panel (in the Audiobook app).
2. Check the real-time logs for errors like "Safety Block" or "Network Timeout".
3. **Hybrid Fallback**: For dense PDFs, the system automatically tries a text-only extraction if the Vision model (OCR) is blocked.

---

## 💰 Understanding Costs
You can view the estimated processing cost for any document by checking the **Firestore Job metadata**. The system calculates:
- Analysis (Gemini 3.0)
- Scripting (Gemini 3.0)
- Audio (TTS Journey/Studio)
- **Total USD Cost**: Usually ranges from $0.05 to $0.50 depending on length and voice selection.
