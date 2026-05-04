"""
DriveLegal – frontend/app.py
Streamlit chat UI connected to the FastAPI backend.

Run:  streamlit run frontend/app.py
(FastAPI must be running at BACKEND_URL)
"""

import json
import requests
import streamlit as st

import os
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="DriveLegal – Road Safety Chatbot",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    /* Hide the default Streamlit top bar, padding, and UI elements */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {
        padding: 0 !important;
        max-width: 100% !important;
    }
    iframe {
        border: none;
        width: 100vw;
        height: 100vh;
    }
</style>
""", unsafe_allow_html=True)

# Load the ui.html file and inject it into Streamlit
ui_path = os.path.join(os.path.dirname(__file__), "ui.html")
with open(ui_path, "r", encoding="utf-8") as f:
    html_content = f.read()

components.html(html_content, height=1000, scrolling=True)
