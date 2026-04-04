from dotenv import load_dotenv
load_dotenv()
import os
from google import genai

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
r = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Reply with only the word: OK"
)
print("gemini-2.5-flash:", r.text.strip())
