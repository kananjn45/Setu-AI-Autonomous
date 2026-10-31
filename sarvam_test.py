import os
from dotenv import load_dotenv
from sarvamai import SarvamAI

# Load environment variables from .env
load_dotenv()

api_key = os.getenv("SARVAM_API_KEY")
if not api_key:
    raise ValueError("SARVAM_API_KEY is not set. Please add your key to .env")

# Initialize the Sarvam AI client
client = SarvamAI(api_subscription_key=api_key)

# Make a chat completion call with sarvam-105b-conversations
response = client.chat.completions(
    model="sarvam-105b-conversations",
    messages=[
        {"role": "user", "content": "Hello! Please give a brief one-sentence greeting."}
    ],
)

# Print the reply
print(response.choices[0].message.content)
