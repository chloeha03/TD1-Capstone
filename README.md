# TD1-Capstone

To run frontend:

- save this project to your local drive
- download node.js
- in windows powershell, run npm install, then do npm run dev
- go to the local dev link that is displayed

To run transcription:
- save WhisperTranscription.py
- run the following installations before running the python file:
- brew install ffmpeg
- brew install pkg-config
- pip install faster-whisper
- pip install sounddevice numpy


To run LLM:\\
To run the LLaMA summarization module, you must authenticate with Hugging Face in order to download the gated Meta LLaMA model weights.
- Login Hugging Face and request access to "Meta's Llama 3.1 models & evals"
- You will be approved after several minutes
- Create a Hugging Face access token (Read permission):
Settings → Access Tokens → New Token

You need to put this token when you run:
from huggingface_hub import notebook_login
notebook_login()

- run the demo summarization pipeline:
demo_text = """
Toronto is the capital city of the Canadian province of Ontario.
It is the most populous city in Canada and a global center for business.
The CN Tower is one of its most iconic landmarks.
"""

final_result = summarize_long_text(demo_text, chunk_size=200, overlap=30)
print(final_result)

- Expected output (Has been tested):
{
  "summary": "...",
  "key_points": ["...", "..."]
}



