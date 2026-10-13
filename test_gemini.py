import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

key = os.getenv("GEMINI_API_KEY")
model = os.getenv("GEMINI_MODEL")

print("Key loaded:", bool(key))
print("Model name:", repr(model))

client = genai.Client(api_key=key)

try:
    resp = client.models.generate_content(
        model=model,
        contents="Reply with just the word: working",
    )
    print("Response:", resp.text)
except Exception as e:
    print("ERROR:", e)