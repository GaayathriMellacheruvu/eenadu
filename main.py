from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Optional
import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv
import os
import shutil
import json
from pymongo import MongoClient
from text_cleaning import clean_text
from categorisation import categorize_text
from location_scraping import location_scraping
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib

# Load environment variables from .env file
load_dotenv()

# Access the API key, region, and MongoDB URI from environment variables
API_KEY = os.getenv('AZURE_API_KEY')
REGION = os.getenv('AZURE_REGION')
EMAIL_USERNAME = os.getenv('EMAIL_USERNAME')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
MONGO_URI = os.getenv('MONGO_URI')  # MongoDB URI

# Set up MongoDB client
client = MongoClient(MONGO_URI)
db = client['newsAi']
sessions_collection = db['sessions']

app = FastAPI()

# Enable CORS to allow interactions from other origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SpeechRequest(BaseModel):
    language: str = "te-IN"
    session_id: str

class StartSessionResponse(BaseModel):
    message: str
    compiled_speech_to_text: Optional[str] = None

class SpeechToTextResponse(BaseModel):
    text: str

class UploadAudioResponse(BaseModel):
    transcribed_text: str

class CleanedText(BaseModel):
    cleaned_text: Optional[str]
    categorized_text: Optional[str]
    location_text: Optional[str]

class EndSessionResponse(BaseModel):
    compiled_speech_to_text: str
    cleaned_speech_to_text: CleanedText
    cleaned_file_text: CleanedText

class SessionDataResponse(BaseModel):
    session_id: str
    compiled_speech_to_text: str
    cleaned_speech_to_text: Optional[str]
    cleaned_file_text: Optional[str]

def azure_speech_to_text(subscription_key, region, language="te-IN", audio_file_path=None):
    speech_config = speechsdk.SpeechConfig(subscription=subscription_key, region=region)
    speech_config.speech_recognition_language = language

    if audio_file_path:
        audio_config = speechsdk.audio.AudioConfig(filename=audio_file_path)
    else:
        audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)

    recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

    # Process audio in chunks
    recognized_text = []
    done = False
    while not done:
        result = recognizer.recognize_once()
        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            recognized_text.append(result.text)
        elif result.reason == speechsdk.ResultReason.NoMatch:
            done = True
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            error_message = "Speech Recognition canceled: " + str(cancellation_details.reason)
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                error_message += " Error details: " + str(cancellation_details.error_details)
            raise HTTPException(status_code=500, detail=error_message)
    
    return ' '.join(recognized_text)

@app.post("/start-session/", response_model=StartSessionResponse)
def start_session(request: SpeechRequest):
    session_id = request.session_id
    
    # Check if the session already exists
    existing_session = sessions_collection.find_one({"session_id": session_id})
    
    if existing_session:
        # Session already exists, fetch existing data
        compiled_speech_to_text = existing_session.get("compiled_speech_to_text", "")
    else:
        # Initialize a new session with default values
        session_data = {"text": "", "file_text": None, "compiled_speech_to_text": ""}
        sessions_collection.update_one({"session_id": session_id}, {"$set": session_data}, upsert=True)
        compiled_speech_to_text = ""

    return StartSessionResponse(
        message=f"Session {session_id} started.",
        compiled_speech_to_text=compiled_speech_to_text
    )

@app.post("/telugu-text-entry/", response_model=SpeechToTextResponse)
def telugu_text_entry(request: SpeechRequest):
    session_id = request.session_id
    new_text = request.language

    # Fetch the session data from MongoDB
    session_data = sessions_collection.find_one({"session_id": session_id})
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")

    # Fetch existing cleaned text and compiled text
    existing_cleaned_text = session_data.get("cleaned_speech_to_text", {}).get("cleaned_text", "")
    existing_compiled_text = session_data.get("compiled_speech_to_text", "")

    # Swap cleaned text with compiled speech to text
    updated_compiled_text = existing_cleaned_text

    # Add new text to the updated compiled text
    updated_compiled_text = f"{updated_compiled_text} {new_text}".strip()

    # Update the session in MongoDB with the new compiled text
    sessions_collection.update_one(
        {"session_id": session_id},
        {"$set": {"compiled_speech_to_text": updated_compiled_text}}
    )

    # Return the combined text as the response
    return SpeechToTextResponse(text=updated_compiled_text)

@app.post("/upload-audio/", response_model=UploadAudioResponse)
async def upload_audio(
    session_id: str = Form(...),
    file: UploadFile = File(...),
    language: str = Form("te-IN")
):
    session_data = sessions_collection.find_one({"session_id": session_id})
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        # Save the uploaded file temporarily
        temp_file_path = f"temp_{file.filename}"
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Perform speech-to-text on the saved audio file
        transcribed_text = azure_speech_to_text(API_KEY, REGION, language, temp_file_path)

        # Remove the temporary file after processing
        os.remove(temp_file_path)

        # Retrieve the existing compiled and cleaned text from MongoDB
        existing_compiled_text = session_data.get("compiled_speech_to_text", "")
        existing_cleaned_text = session_data.get("cleaned_speech_to_text", {}).get("cleaned_text", "")

        # Clean the new transcribed text
        cleaned_transcribed_text = clean_text(transcribed_text)

        # Combine the existing and cleaned text
        updated_compiled_text = f"{existing_compiled_text} {cleaned_transcribed_text}".strip()
        updated_cleaned_text = f"{existing_cleaned_text} {cleaned_transcribed_text}".strip()

        # Store the updated text in MongoDB
        sessions_collection.update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "compiled_speech_to_text": updated_compiled_text,
                    "cleaned_speech_to_text.cleaned_text": updated_cleaned_text
                }
            }
        )

        # Return the combined text as the response
        return UploadAudioResponse(transcribed_text=updated_cleaned_text)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

# Add location to email mapping
LOCATION_EMAIL_MAPPING = {
    # Add your location-to-email mapping here
}

def render_email_template(template_path: str, **kwargs) -> str:
    with open(template_path, 'r', encoding='utf-8') as file:
        template = file.read()

    # Replace placeholders in the template with actual data
    for key, value in kwargs.items():
        placeholder = f"{{{{ {key} }}}}"
        template = template.replace(placeholder, value if value else "")

    return template

def send_email(to_email: str, subject: str, location: str, cleaned_text: str, categorized_text: str, location_text: str):
    try:
        from_email = EMAIL_USERNAME
        
        # Render the email body from the HTML template
        email_body = render_email_template(
            'email_template.html',
            location=location,
            cleaned_text=cleaned_text,
            categorized_text=categorized_text,
            location_text=location_text
        )
        
        msg = MIMEMultipart('related')
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(email_body, 'html', 'utf-8'))

        # Connect to the Gmail SMTP server
        smtp_server = "smtp.gmail.com"
        server = smtplib.SMTP(smtp_server, 587)
        server.starttls()

        # Log in to your account
        server.login(EMAIL_USERNAME, EMAIL_PASSWORD)

        # Send the email
        server.send_message(msg)

        # Disconnect from the server
        server.quit()

        print(f"Email sent to {to_email} with subject '{subject}'")

    except smtplib.SMTPException as e:
        print(f"SMTP error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

def identify_and_send_email(cleaned_text: Optional[str], categorized_text: Optional[str], location_text: Optional[str]):
    if not cleaned_text:
        return

    cleaned_text_lower = cleaned_text.lower()
    sent_locations = set()

    for location in LOCATION_EMAIL_MAPPING.keys():
        if location.lower() in cleaned_text_lower and location not in sent_locations:
            print(f"Location '{location}' found in text: {cleaned_text}")
            
            email_body = {
                "location": location,
                "cleaned_text": cleaned_text,
                "categorized_text": categorized_text,
                "location_text": location_text
            }
            
            email_to = LOCATION_EMAIL_MAPPING[location]
            subject = f"Location Report: {location}"
            
            print(f"Sending email to {email_to} with subject '{subject}' and body: {email_body}")

            send_email(email_to, subject, **email_body)
            sent_locations.add(location)
        else:
            print(f"Location '{location}' not found in text.")

class EndSessionRequest(BaseModel):
    session_id: str

@app.post("/end-session/", response_model=EndSessionResponse)
def end_session(request: EndSessionRequest):
    session_id = request.session_id
    session_data = sessions_collection.find_one({"session_id": session_id})
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")

    # Fetch the existing compiled speech-to-text from MongoDB
    compiled_text = session_data.get("compiled_speech_to_text", "")
    cleaned_text = session_data.get("cleaned_speech_to_text", {}).get("cleaned_text", "")

    # Ensure cleaned_text is updated with the compiled text
    if compiled_text:
        cleaned_text = clean_text(compiled_text)

    # Clean, categorize, and scrape location for the cleaned text
    categorized_text = categorize_text(cleaned_text) if cleaned_text else None
    location_text = location_scraping(cleaned_text) if cleaned_text else None

    # Split categorized_text into title and text
    title, text = "", ""
    if categorized_text:
        if ":" in categorized_text:
            title, text = categorized_text.split(":", 1)
        else:
            title = categorized_text

    # Identify and send email based on the content
    identify_and_send_email(cleaned_text, categorized_text, location_text)

    # Create the response data
    response_data = EndSessionResponse(
        compiled_speech_to_text=compiled_text,
        cleaned_speech_to_text=CleanedText(
            cleaned_text=cleaned_text,
            categorized_text=text,
            location_text=location_text
        ),
        cleaned_file_text=CleanedText(
            cleaned_text=None,
            categorized_text=None,
            location_text=None
        )
    )

    # Update MongoDB with the new output, replacing the previous one
    sessions_collection.update_one(
        {"session_id": session_id},
        {
            "$set": {
                "compiled_speech_to_text": compiled_text,
                "cleaned_speech_to_text": {
                    "cleaned_text": cleaned_text,
                    "title": title.strip(),
                    "categorized_text": text.strip(),
                    "location_text": location_text
                },
                "cleaned_file_text": {
                    "cleaned_text": None,
                    "categorized_text": None,
                    "location_text": None
                }
            }
        },
        upsert=True
    )

    return response_data

@app.get("/sessions/")
async def get_sessions():
    sessions = sessions_collection.find({}, {"_id": 0, "session_id": 1})
    return {"sessions": [session["session_id"] for session in sessions]}

from pydantic import BaseModel
from typing import Optional

class CleanedSpeechToText(BaseModel):
    cleaned_text: Optional[str] = None
    title: Optional[str] = None
    categorized_text: Optional[str] = None
    location_text: Optional[str] = None

class CleanedFileText(BaseModel):
    cleaned_text: Optional[str] = None
    categorized_text: Optional[str] = None
    location_text: Optional[str] = None

class SessionResponse(BaseModel):
    session_id: str
    compiled_speech_to_text: str
    file_text: Optional[str] = None
    text: Optional[str] = None
    cleaned_file_text: CleanedFileText
    cleaned_speech_to_text: CleanedSpeechToText

@app.get("/fetch-session/{session_id}", response_model=SessionResponse)
def fetch_session_details(session_id: str):
    session_data = sessions_collection.find_one({"session_id": session_id})
    
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")
    
    cleaned_file_text = session_data.get("cleaned_file_text", {})
    cleaned_speech_to_text = session_data.get("cleaned_speech_to_text", {})
    
    response = SessionResponse(
        session_id=session_id,
        compiled_speech_to_text=session_data.get("compiled_speech_to_text", ""),
        file_text=session_data.get("file_text", ""),
        text=session_data.get("text", ""),
        cleaned_file_text=CleanedFileText(**cleaned_file_text),
        cleaned_speech_to_text=CleanedSpeechToText(**cleaned_speech_to_text)
    )

    return response
