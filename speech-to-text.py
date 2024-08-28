import streamlit as st
import uuid
import requests
from main import azure_speech_to_text
import speech_recognition as sr
from io import BytesIO
import os

# API Endpoints
BASE_URL = "https://eenadu-backend.onrender.com"  # Replace with your FastAPI server URL

# Helper Functions
def start_session(session_id):
    with st.spinner("🌟 Initiating your AI session..."):
        response = requests.post(f"{BASE_URL}/start-session/", json={"session_id": session_id})
        if response.status_code == 200:
            return "Session successfully started!"
        else:
            return f"Oops! Failed to start session: {response.text}"

def upload_audio(session_id, file, language):
    with st.spinner("📤 Uploading and processing your audio..."):
        response = requests.post(f"{BASE_URL}/upload-audio/", data={"session_id": session_id, "language": language}, files={"file": file})
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Oops! Failed to upload audio: {response.text}"}

def end_session(session_id):
    with st.spinner("🚀 Finalizing your session... Please wait."):
        response = requests.post(f"{BASE_URL}/end-session/", json={"session_id": session_id})
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Oops! Failed to end session: {response.text}"}

def recognize_speech_from_mic():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        st.write("Listening...")
        audio_data = recognizer.listen(source)
        st.write("Processing...")
        try:
            text = recognizer.recognize_google(audio_data)
            return text
        except sr.UnknownValueError:
            return "Sorry, I could not understand the audio."
        except sr.RequestError as e:
            return f"Sorry, there was an error with the API request: {e}"

# Streamlit UI
st.markdown(
    """
    <style>
    .header {
        display: flex;
        align-items: center;
        font-size: 2rem;
        color: #0a5c69;
        font-weight: bold;
    }
    .header img {
        margin-right: 20px;
        width: 80px;  /* Adjust width as needed */
    }
    .stButton>button {
        color: white;
        background-color: #0a5c69;
        border-radius: 10px;
        padding: 10px 20px;
    }
    .css-1aumxhk {
        border: 1px solid #0a5c69;
        border-radius: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

top_col1, top_col2 = st.columns([1, 4])

with top_col1:
    st.image("logo.png", use_column_width=True)

with top_col2:
    st.title("EENADU AI JOURNALIST POC")

col1, col2 = st.columns([1, 2])

with col1:
    if st.button("Generate New Session ID"):
        session_id = str(uuid.uuid4())
        st.session_state.clear()  # Clear session state cache
        st.session_state.session_id = session_id

with col2:
    session_id = st.session_state.get("session_id", "")
    if session_id:
        st.write(f"Current Session ID: {session_id}")

if session_id:
    with st.expander("Session Controls", expanded=True):
        if st.button("Start Session"):
            st.write("Session started!")

    with st.expander("Choose an Action", expanded=True):
        option = st.selectbox("", ["Start Recording", "End Session"])

        if option == "Start Recording":
            if st.button("Start Recording"):
                st.write("Click the 'Stop Recording' button when done.")
                recognizer = sr.Recognizer()
                with sr.Microphone() as source:
                    st.write("Listening...")
                    audio_data = recognizer.listen(source)
                    st.write("Processing...")
                    with BytesIO(audio_data.get_wav_data()) as audio_file:
                        temp_file_path = f"temp_{uuid.uuid4()}.wav"
                        with open(temp_file_path, "wb") as f:
                            f.write(audio_data.get_wav_data())

                        text = azure_speech_to_text(audio_file_path=temp_file_path)
                        st.session_state.compiled_text = text
                        os.remove(temp_file_path)

        elif option == "End Session":
            if st.button("Confirm and End Session"):
                st.write("### Compiled Text:")
                st.write(st.session_state.get("compiled_text", ""))
                st.success("Session ended successfully!")
                st.session_state.clear()
                st.rerun()

else:
    st.warning("Please generate a Session ID to start.")