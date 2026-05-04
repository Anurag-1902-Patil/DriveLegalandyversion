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
| 🧠 RAG Pipeline | FAISS + Mistral (Ollama) + LangChain for grounded responses |
| ⚡ Offline Fallback | 25 pre-cached Q&A pairs when Ollama is unavailable |
| 💬 Chat UI | Streamlit frontend with location selector |
| 🔒 Legal Disclaimer | Every response marked as indicative |

---

## 🚀 Quick Start

### 1. Clone & setup environment

```bash
git clone https://github.com/your-username/drivelegal.git
cd drivelegal
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# No API keys are required for Ollama. Just ensure Ollama is running.
```

### 3. Add raw data

Place `.txt` or `.md` files of Indian traffic laws in `data/raw/`.  
Example sources: Motor Vehicles Act 1988, Maharashtra RTO website, Pune traffic portal.

### 4. Preprocess → Embed → Index

```bash
python scripts/preprocess.py    # Chunk and tag raw files
python scripts/embed.py         # Build FAISS vector index
```

### 5. Start the backend

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs available at: http://localhost:8000/docs

### 6. Start the frontend

```bash
streamlit run frontend/app.py
```

---

## 📁 Project Structure

```
drivelegal/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── models.py            # Pydantic schemas
│   └── routes/chat.py       # /chat endpoint
├── rag/
│   ├── retriever.py         # FAISS index + retrieve()
│   ├── chain.py             # LangChain RAG chain + offline fallback
│   └── challan.py           # Fine calculator (JSON lookup)
├── data/
│   ├── raw/                 # Raw law documents
│   ├── processed/           # Chunked JSON with metadata
│   ├── faiss_index/         # Saved FAISS vectors
│   ├── fines.json           # Structured fine database
│   └── cache.json           # Offline Q&A cache (25 entries)
├── scripts/
│   ├── preprocess.py        # Clean + chunk raw data
│   ├── embed.py             # Build FAISS index
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
