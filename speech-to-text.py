import time
import openai
import streamlit as st
import requests
import uuid
import os


# API Endpoints
BASE_URL = "https://eenadu-backend.onrender.com"# Replace with your FastAPI server URL

# Helper Functions
def start_session(session_id):
    with st.spinner("🌟 Initiating your AI session..."):
        response = requests.post(f"{BASE_URL}/start-session/", json={"session_id": session_id})
        if response.status_code == 200:
            return "Session successfully started!"
        else:
            return f"Oops! Failed to start session: {response.text}"

def speech_to_text(session_id, language):
    with st.spinner("🗣️ Converting your speech to text..."):
        response = requests.post(f"{BASE_URL}/speech-to-text/", json={"session_id": session_id, "language": language})
        if response.status_code == 200:
            return response.text
        else:
            return f"Oops! Failed to transcribe speech: {response.text}"

def upload_audio(session_id, file, language):
    with st.spinner("📤 Uploading and processing your audio..."):
        response = requests.post(f"{BASE_URL}/upload-audio/", data={"session_id": session_id, "language": language}, files={"file": file})
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Oops! Failed to upload audio: {response.text}"}

def end_session(session_id):
    with st.spinner("🚀 Finalizing your session... Please wait."):
        # Simulate each stage with a brief pause
        time.sleep(1)
        st.spinner("🔄 Cleaning your text...")
        time.sleep(1)
        st.spinner("🔄 Categorizing your text...")
        time.sleep(1)
        st.spinner("🔄 Extracting locations...")
        time.sleep(1)
        st.spinner("🚀 Here you go! Your session is complete.")
        
        # Now actually make the request
        response = requests.post(f"{BASE_URL}/end-session/", json={"session_id": session_id})
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Oops! Failed to end session: {response.text}"}

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
        # st.success(f"New Session ID generated: {session_id}")

with col2:
    session_id = st.session_state.get("session_id", "")
    if session_id:
        st.write(f"Current Session ID: {session_id}")

if session_id:
    with st.expander("Session Controls", expanded=True):
        if st.button("Start Session"):
            result = start_session(session_id)
            st.write(result)

    with st.expander("Choose an Action", expanded=True):
        option = st.selectbox("", ["Upload Audio", "Start Recording", "End Session"])

        if option == "Upload Audio":
            uploaded_file = st.file_uploader("Choose an audio file", type=["wav", "mp3"])
            language = st.text_input("Enter Language Code", "te-IN")

            if st.button("Submit"):
                if uploaded_file is not None:
                    result = upload_audio(session_id, uploaded_file, language)
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        st.write("### Transcribed Text:")
                        st.write(result.get("transcribed_text", ""))

                        # Automatically end session after submission
                        end_result = end_session(session_id)
                        if "error" in end_result:
                            st.error(end_result["error"])
                        else:
                            st.write("### Compiled Text:")
                            st.write(end_result.get("compiled_speech_to_text", ""))

                            st.write("### Cleaned Speech Text:")
                            st.write(end_result.get("cleaned_speech_to_text", {}).get("cleaned_text", ""))

                            st.write("### Categorized Speech Text:")
                            st.write(end_result.get("cleaned_speech_to_text", {}).get("categorized_text", ""))

                            st.write("### Location from Speech Text:")
                            st.write(end_result.get("cleaned_speech_to_text", {}).get("location_text", ""))

                            st.write("### Cleaned File Text:")
                            st.write(end_result.get("cleaned_file_text", {}).get("cleaned_text", ""))

                            st.write("### Categorized File Text:")
                            st.write(end_result.get("cleaned_file_text", {}).get("categorized_text", ""))

                            st.write("### Location from File Text:")
                            st.write(end_result.get("cleaned_file_text", {}).get("location_text", ""))

        elif option == "Start Recording":
            if st.button("Start Recording"):
                result = speech_to_text(session_id, "te-IN")
                st.write("### Compiled Text:")
                st.write(result)

                if result:
                    st.session_state.compiled_text = result

        elif option == "End Session":
            if st.button("Confirm and End Session"):
                st.session_state.clear()
                st.success("Session ended successfully!")
                st.rerun()

else:
    st.warning("Please generate a Session ID to start.")
