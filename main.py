from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Optional
import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv
import os
import shutil
import json
from text_cleaning import clean_text
from categorisation import categorize_text
from location_scraping import location_scraping
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib

# Load environment variables from .env file
load_dotenv()

# Access the API key and region from environment variables
API_KEY = os.getenv('AZURE_API_KEY')
REGION = os.getenv('AZURE_REGION')
EMAIL_USERNAME = os.getenv('EMAIL_USERNAME')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')

app = FastAPI()

# Enable CORS to allow interactions from other origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simulate session storage (in-memory for this example)
session_store: Dict[str, Dict[str, Optional[str]]] = {}

class SpeechRequest(BaseModel):
    language: str = "te-IN"
    session_id: str

class StartSessionResponse(BaseModel):
    message: str

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
    session_store[session_id] = {"text": "", "file_text": None}  # Initialize session with empty text and file text
    return StartSessionResponse(message=f"Session {session_id} started.")

@app.post("/speech-to-text/", response_model=SpeechToTextResponse)
def speech_to_text(request: SpeechRequest):
    session_id = request.session_id

    if session_id not in session_store:
        raise HTTPException(status_code=404, detail="Session not found")

    recognized_text = azure_speech_to_text(API_KEY, REGION, request.language)
    session_store[session_id]["text"] += recognized_text + " "  # Append the recognized text to the session

    response = {"text": session_store[session_id]["text"]}
    return json.loads(json.dumps(response))

@app.post("/upload-audio/", response_model=UploadAudioResponse)
async def upload_audio(
    session_id: str = Form(...),
    file: UploadFile = File(...),
    language: str = Form("te-IN")
):
    if session_id not in session_store:
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

        # Store the transcribed text from the uploaded file
        session_store[session_id]["file_text"] = transcribed_text

        return UploadAudioResponse(transcribed_text=transcribed_text)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

class EndSessionRequest(BaseModel):
    session_id: str

# Add location to email mapping
LOCATION_EMAIL_MAPPING = {
    "హైదరాబాద్": "mellacheruvugaayathri@gmail.com",
    "చెన్నై": "mellacheruvugaayathri@gmail.com",
    "బెంగళూరు": "mellacheruvugaayathri@gmail.com",
    "ముంబై": "mellacheruvugaayathri@gmail.com",
    "దిల్లీ": "mellacheruvugaayathri@gmail.com",
    "కోల్‌కతా": "mellacheruvugaayathri@gmail.com",
    "పుణే": "mellacheruvugaayathri@gmail.com",
    "అహ్మదాబాద్": "mellacheruvugaayathri@gmail.com",
    "తమిళనాడు": "mellacheruvugaayathri@gmail.com",
    "ఆంధ్రప్రదేశ్": "mellacheruvugaayathri@gmail.com",
    "తెలంగాణ": "mellacheruvugaayathri@gmail.com",
    
    # Add other locations and their respective email addresses
}

from fastapi.responses import HTMLResponse

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
        msg.attach(MIMEText(email_body, 'html', 'utf-8'))  # Use 'html' to send the email in HTML format

        # Connect to the Gmail SMTP server
        smtp_server = "smtp.gmail.com"
        server = smtplib.SMTP(smtp_server, 587)
        server.starttls()  # Secure the connection

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

import json

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

# Modify to return JSON instead of plain text
@app.post("/end-session/", response_model=EndSessionResponse)
def end_session(request: EndSessionRequest):
    session_id = request.session_id
    if session_id not in session_store:
        raise HTTPException(status_code=404, detail="Session not found")

    session_data = session_store.pop(session_id)
    speech_to_text_result = session_data["text"]
    file_text_result = session_data["file_text"]

    # Combine the results from speech-to-text and file uploads
    compiled_text = (speech_to_text_result or "") + (file_text_result or "")

    # Clean, categorize, and scrape location
    cleaned_speech_text = clean_text(speech_to_text_result) if speech_to_text_result else None
    cleaned_file_text = clean_text(file_text_result) if file_text_result else None

    categorized_speech_text = categorize_text(cleaned_speech_text) if cleaned_speech_text else None
    categorized_file_text = categorize_text(cleaned_file_text) if cleaned_file_text else None

    location_speech_text = location_scraping(categorized_speech_text) if categorized_speech_text else None
    location_file_text = location_scraping(categorized_file_text) if categorized_file_text else None

    # Create the response text
    response_data = EndSessionResponse(
        compiled_speech_to_text=compiled_text,
        cleaned_speech_to_text=CleanedText(
            cleaned_text=cleaned_speech_text,
            categorized_text=categorized_speech_text,
            location_text=location_speech_text
        ),
        cleaned_file_text=CleanedText(
            cleaned_text=cleaned_file_text,
            categorized_text=categorized_file_text,
            location_text=location_file_text
        )
    )

    # Extract location information and send emails
    if cleaned_speech_text:
        identify_and_send_email(cleaned_speech_text, categorized_speech_text, location_speech_text)
    if cleaned_file_text:
        identify_and_send_email(cleaned_file_text, categorized_file_text, location_file_text)

    return response_data
