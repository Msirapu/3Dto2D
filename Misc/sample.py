from google import genai
import os

client = genai.Client()
response = client.models.generate_content(model="gemini-2.5-flash", contents="Hello CAD Agent!")
print(response.text)