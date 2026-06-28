# 🚦 DriveLegal – AI-Powered Road Safety Chatbot

> Built for **Road Safety Hackathon 2026** | CoERS, RBG Labs, IIT Madras  
> Theme: *AI in Road Safety*

DriveLegal answers traffic law questions in natural language with **location-specific, grounded accuracy** — no hallucinated fine amounts.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 📍 Geo-aware answers | City → State → National fallback hierarchy |
| 💰 Challan Calculator | Structured JSON lookup — never hallucinated |
| 🧠 RAG Pipeline | Qdrant + Mistral (Ollama) + LangChain for grounded responses |
| ⚡ Offline Fallback | 25 pre-cached Q&A pairs when Ollama is unavailable |
| 💬 Chat UI | Streamlit frontend with location selector |
| 🔒 Legal Disclaimer | Every response marked as indicative |
| 👤 User Authentication| OTP-based email login with secure JWT sessions |
| 🪪 DL Verification  | Live integration with Parivahan (via Surepass) for Driver License checks |
| 🗄️ Database         | SQLite tracking for user profiles, challans, and chat history |

---

## 🚀 Quick Start

### 1. Install Ollama & Mistral

DriveLegal runs 100% locally to protect your data. You must install the Ollama framework to run the AI engine.

1. Download and install [Ollama](https://ollama.com/download) for your operating system.
2. Open a new terminal and run:
   ```bash
   ollama run mistral
   ```
   *(This will download the Mistral model and start it. Ensure Ollama remains running in your system background).*

### 2. Clone & setup environment

```bash
git clone https://github.com/your-username/drivelegal.git
cd drivelegal
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```
Fill in the `.env` file with your SMTP credentials for OTP emails and Surepass token for DL Verification:
- `SENDER_EMAIL` and `SENDER_PASSWORD` for email auth.
- `SUREPASS_AUTH_TOKEN` for live Driver License checks.
*(Note: No API keys are required for Ollama as it runs 100% locally.)*

### 4. Add raw data

Place `.txt` or `.md` files of Indian traffic laws in `data/raw/`.  
Example sources: Motor Vehicles Act 1988, Maharashtra RTO website, Pune traffic portal.

### 5. Preprocess → Embed → Index

```bash
python scripts/preprocess.py    # Chunk and tag raw files
python scripts/embed.py         # Build Qdrant vector index
```

### 6. Run the Software

The easiest way to start both the backend and frontend simultaneously is using the provided start script:

**Windows:**
```bash
.\start.bat
```
To run mistral : Paste this in your working directory's terminal :
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" run mistral
**Manual Start:**
If you prefer to start them manually or are on Mac/Linux:
```bash
# Start backend in terminal 1
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Start frontend in terminal 2
streamlit run frontend/app.py
```

- **Frontend App**: http://localhost:8501
- **API Docs**: http://localhost:8000/docs

---

## 📁 Project Structure

```
drivelegal/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── models.py            # Pydantic schemas
│   └── routes/chat.py       # /chat endpoint
├── rag/
│   ├── retriever.py         # Qdrant index + retrieve()
│   ├── chain.py             # LangChain RAG chain + offline fallback
│   └── challan.py           # Fine calculator (JSON lookup)
├── data/
│   ├── raw/                 # Raw law documents
│   ├── processed/           # Chunked JSON with metadata
│   ├── qdrant_db/           # Saved Qdrant vectors
│   ├── fines.json           # Structured fine database
│   └── cache.json           # Offline Q&A cache (25 entries)
├── scripts/
│   ├── preprocess.py        # Clean + chunk raw data
│   ├── embed.py             # Build Qdrant index
│   └── cache_rules.py       # Refresh offline cache
├── frontend/app.py          # Streamlit chat UI
├── tests/
│   ├── test_rag.py
│   ├── test_api.py
│   └── test_challan.py
├── .env.example
└── requirements.txt
```

---

## 🔌 API Reference

### `POST /api/auth/send-otp`
Sends an OTP to the user's email.

### `POST /api/auth/verify-otp`
Verifies the OTP and returns a JWT token.

### `POST /api/profile/verify-dl`
Verifies Driver License against government records and populates challan history.

### `GET /api/profile/dashboard-data/{user_id}`
Returns user's profile and active challans.

### `POST /chat`

```json
{
  "message": "What is the fine for jumping a red light in Pune on a bike?",
  "location": {
    "city": "Pune",
    "state": "Maharashtra",
    "country": "India"
  }
}
```

**Response:**

```json
{
  "answer": "Jumping a red light in Pune carries a fine of ₹1,000 under MV Act Section 179...",
  "fine_amount": "₹1,000",
  "sources": [...],
  "disclaimer": "This information is indicative. Verify with official RTO.",
  "offline_fallback": false
}
```

### `GET /health`

```json
{ "status": "ok", "service": "DriveLegal" }
```

---

## 🧪 Running Tests

```bash
pytest tests/ -v
```

---

## 🌐 Deployment

### Railway (recommended for hackathon)

```bash
# Install Railway CLI
npm install -g @railway/cli
railway login
railway init
railway up
```

Since the app is 100% local, ensure Ollama is installed on your server (like Railway) if deploying remotely, or use a managed Ollama endpoint and set `OLLAMA_BASE_URL`.

---

## ⚠️ Disclaimer

All information provided by DriveLegal is for **awareness purposes only**.  
Fine amounts may vary. Always verify with the official RTO, traffic police, or MoRTH.

---

## 📜 License

MIT License — open source, free to use and extend.
