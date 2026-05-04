"""
DriveLegal – frontend/app.py
Streamlit chat UI connected to the FastAPI backend.

Run:  streamlit run frontend/app.py
(FastAPI must be running at BACKEND_URL)
"""

import json
import requests
import streamlit as st

BACKEND_URL = "http://localhost:8000"

INDIAN_STATES = [
    "Andhra Pradesh", "Assam", "Bihar", "Chhattisgarh", "Delhi",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand",
    "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur",
    "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab",
    "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
    "Uttar Pradesh", "Uttarakhand", "West Bengal",
]

CITY_BY_STATE = {
    "Maharashtra": ["Pune", "Mumbai", "Nagpur", "Nashik", "Aurangabad"],
    "Delhi":       ["New Delhi", "Noida", "Gurugram"],
    "Karnataka":   ["Bangalore", "Mysuru", "Mangalore"],
    "Tamil Nadu":  ["Chennai", "Coimbatore", "Madurai"],
    "Gujarat":     ["Ahmedabad", "Surat", "Vadodara"],
}

# ── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="DriveLegal – Road Safety Chatbot",
    page_icon="🚦",
    layout="wide",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .stApp { background-color: #0f1117; color: #ffffff; }
    .chat-bubble-user {
        background: #1e3a5f; border-radius: 12px 12px 2px 12px;
        padding: 10px 14px; margin: 6px 0; max-width: 75%; margin-left: auto;
    }
    .chat-bubble-bot {
        background: #1a2332; border: 1px solid #2d4a6e;
        border-radius: 12px 12px 12px 2px; padding: 10px 14px;
        margin: 6px 0; max-width: 80%;
    }
    .fine-badge {
        background: #0d4f1c; color: #4caf50; border: 1px solid #4caf50;
        border-radius: 6px; padding: 4px 10px; font-weight: bold;
        display: inline-block; margin-top: 6px;
    }
    .disclaimer {
        color: #888; font-size: 0.78rem; margin-top: 6px; font-style: italic;
    }
    .offline-badge {
        background: #4f2d0d; color: #ff9800; border: 1px solid #ff9800;
        border-radius: 6px; padding: 2px 8px; font-size: 0.75rem;
    }
</style>
""", unsafe_allow_html=True)

# ── Sidebar: location selector ─────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/color/96/traffic-light.png", width=60)
    st.title("DriveLegal")
    st.caption("AI-Powered Road Safety Chatbot")
    st.divider()

    st.subheader("📍 Your Location")
    selected_state = st.selectbox("State", INDIAN_STATES, index=INDIAN_STATES.index("Maharashtra"))
    city_options = CITY_BY_STATE.get(selected_state, ["Other"])
    selected_city = st.selectbox("City", city_options)

    st.divider()
    st.subheader("💡 Try asking")
    examples = [
        "Fine for jumping red light in Pune?",
        "Helmet rules for bike riders",
        "Drunk driving penalty in India",
        "How to pay e-challan?",
    ]
    for ex in examples:
        if st.button(ex, use_container_width=True):
            st.session_state["prefill"] = ex

    st.divider()
    st.caption("⚠️ Information is indicative. Verify with official RTO.")


# ── Tab layout ─────────────────────────────────────────────────────────────
tab_chat, tab_challan, tab_about = st.tabs(["💬 Chat", "🧮 Challan Calculator", "ℹ️ About"])


# ────────────────────────────────────────────────────────────────────────────
# TAB 1: CHAT
# ────────────────────────────────────────────────────────────────────────────
with tab_chat:
    st.header("Ask a Traffic Law Question")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Render chat history
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(f'<div class="chat-bubble-user">🧑 {msg["content"]}</div>', unsafe_allow_html=True)
        else:
            content = msg["content"]
            fine    = msg.get("fine")
            offline = msg.get("offline", False)
            html = f'<div class="chat-bubble-bot">🚦 {content}'
            if fine:
                html += f'<br><span class="fine-badge">💰 Estimated Fine: {fine}</span>'
            if offline:
                html += '<br><span class="offline-badge">⚡ Offline cache</span>'
            html += f'<br><span class="disclaimer">ℹ️ Indicative only. Verify with official RTO.</span></div>'
            st.markdown(html, unsafe_allow_html=True)

    # Input
    prefill = st.session_state.pop("prefill", "")
    user_input = st.chat_input(
        placeholder="e.g. What is the fine for no helmet in Pune?",
    ) or prefill

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})

        with st.spinner("Looking up traffic laws…"):
            try:
                resp = requests.post(
                    f"{BACKEND_URL}/chat",
                    json={
                        "message": user_input,
                        "location": {
                            "city":    selected_city,
                            "state":   selected_state,
                            "country": "India",
                        },
                    },
                    timeout=15,
                )
                resp.raise_for_status()
                data = resp.json()

                st.session_state.messages.append({
                    "role":    "bot",
                    "content": data["answer"],
                    "fine":    data.get("fine_amount"),
                    "offline": data.get("offline_fallback", False),
                })

            except requests.exceptions.ConnectionError:
                st.session_state.messages.append({
                    "role":    "bot",
                    "content": "⚠️ Could not connect to the backend. Please ensure FastAPI is running.",
                    "offline": True,
                })
            except Exception as exc:
                st.session_state.messages.append({
                    "role":    "bot",
                    "content": f"⚠️ Error: {exc}",
                })

        st.rerun()

    if st.button("🗑️ Clear chat"):
        st.session_state.messages = []
        st.rerun()


# ────────────────────────────────────────────────────────────────────────────
# TAB 2: CHALLAN CALCULATOR
# ────────────────────────────────────────────────────────────────────────────
with tab_challan:
    st.header("🧮 Challan (Fine) Calculator")
    st.caption("Estimate your traffic fine quickly. Amounts are indicative.")

    col1, col2 = st.columns(2)
    with col1:
        violation = st.selectbox("Violation Type", [
            "Jumping Red Light", "No Helmet", "No Seatbelt",
            "Speeding", "Drunk Driving", "Mobile Phone While Driving",
            "Driving Without Licence", "No Insurance", "No Registration",
            "Triple Riding", "Wrong Way / One Way Violation",
            "Vehicle Overloading", "No PUC Certificate", "Illegal Parking",
        ])
    with col2:
        vehicle = st.selectbox("Vehicle Type", ["Bike", "Car", "Auto", "Truck", "Bus"])

    if st.button("Calculate Fine", type="primary"):
        query = f"Fine for {violation} for a {vehicle}"
        with st.spinner("Calculating…"):
            try:
                resp = requests.post(
                    f"{BACKEND_URL}/chat",
                    json={
                        "message": query,
                        "location": {
                            "city":    selected_city,
                            "state":   selected_state,
                            "country": "India",
                        },
                    },
                    timeout=10,
                )
                data = resp.json()
                if data.get("fine_amount"):
                    st.success(f"💰 Estimated Fine: **{data['fine_amount']}**")
                st.info(data["answer"])
                st.caption(data["disclaimer"])
            except Exception:
                st.error("Could not reach backend. Ensure FastAPI is running.")


# ────────────────────────────────────────────────────────────────────────────
# TAB 3: ABOUT
# ────────────────────────────────────────────────────────────────────────────
with tab_about:
    st.header("About DriveLegal")
    st.markdown("""
**DriveLegal** is an AI-powered road safety chatbot built for the
Road Safety Hackathon 2026 by CoERS, RBG Labs, IIT Madras.

### How it works
1. You ask a traffic law question in natural language.
2. The system retrieves relevant law chunks from a FAISS vector database.
3. GLM-4-flash generates an accurate, location-specific answer.
4. Fine amounts are cross-referenced from a structured JSON dataset — never hallucinated.
5. If the AI service is offline, a pre-cached fallback is used.

### Tech Stack
| Layer | Technology |
|-------|-----------|
| AI / LLM | GLM-4-flash via Zhipu AI API |
| RAG Framework | LangChain |
| Vector DB | FAISS (local) |
| Backend | FastAPI + Uvicorn |
| Frontend | Streamlit |
| Embeddings | text-embedding-ada-002 |

### Disclaimer
> All information provided is for awareness purposes only and may not
> reflect the most current regulations. Always verify fines and laws
> with the official RTO, MoRTH, or state traffic police.
    """)
