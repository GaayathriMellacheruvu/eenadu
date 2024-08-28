import time
from openai import OpenAI
import os


def clean_text(input_text):
    ID = os.getenv('CLEAN_ASST_ID')
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    chat = client.beta.threads.create(
        messages=[{"role": "user", "content": input_text}]
    )

    run = client.beta.threads.runs.create(thread_id=chat.id, assistant_id=ID)
    print(f"Run Created: {run.id}")

    while run.status != "completed":
        run = client.beta.threads.runs.retrieve(thread_id=chat.id, run_id=run.id)
        print(f"Run Status: {run.status}")
        time.sleep(0.5)

    print("Run Completed")

    message_response = client.beta.threads.messages.list(thread_id=chat.id)
    messages = message_response.data

    latest_message = messages[0]
    return latest_message.content[0].text.value  # Return the cleaned text
