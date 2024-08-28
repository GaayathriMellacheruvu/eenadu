def categorize_text(cleaned_text: str) -> str:
    import time
    from openai import OpenAI
    import os

    ID = os.getenv('CATEGORY_ASST_ID')
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    chat = client.beta.threads.create(
            messages=[{"role": "user", "content": cleaned_text}]
        )

    run = client.beta.threads.runs.create(thread_id=chat.id, assistant_id=ID)
    while run.status != "completed":
            run = client.beta.threads.runs.retrieve(thread_id=chat.id, run_id=run.id)
            time.sleep(0.5)

    message_response = client.beta.threads.messages.list(thread_id=chat.id)
    messages = message_response.data

    latest_message = messages[0]
    return latest_message.content[0].text.value
