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


To run LLM:<br>
To run the LLaMA summarization module, you must authenticate with Hugging Face in order to download the gated Meta LLaMA model weights.
- Login Hugging Face and request access to **"Meta's Llama 3.1 models & evals"**
- You will be approved after several minutes
- Create a Hugging Face access token (Read permission):<br>
**Settings → Access Tokens → New Token**

- You need to put this token when you run:<br>
**from huggingface_hub import notebook_login<br>
notebook_login()**

- run the demo summarization pipeline:<br>
**demo_text = """<br>
Toronto is the capital city of the Canadian province of Ontario.<br>
It is the most populous city in Canada and a global center for business.<br>
The CN Tower is one of its most iconic landmarks.<br>
"""<br>
final_result = summarize_long_text(demo_text, chunk_size=200, overlap=30)<br>
print(final_result)<br>**

- Expected output (Has been tested):<br>
**{<br>
  "summary": "...",<br>
  "key_points": ["...", "..."]<br>
}**



To test the end-to-end flow of the summarizer + database:<br>

First need to download the llama model (can download the cuda version of pytorch if you have a GPU)<br>
You also need a huggingface token and request access to Llama 3, exported as `HF_TOKEN` <br>
Linux/Mac: `export HF_TOKEN=<your token>`<br>
Windows cmd: `set HF_TOKEN=<your token>`<br>

```
pip install -r requirements.txt
python download_model.py
```

Then start the databases and summarizer service:
```
docker-compose up --build db redis summarizer_svc
```

Then in another terminal, run the following commands to simulate a call and check the results:<br>
============== VERIFY DATA IS INITIALIZED ==============<br>
```
docker exec -it td_db psql -U postgres -d td_poc -c "SELECT * FROM customer;"
docker exec -it td_db psql -U postgres -d td_poc -c "SELECT * FROM promotion;"
```
============== CREATE A NEW CALL ==============<br>
```
docker exec -it td_redis redis-cli SADD active_calls "call_123"
docker exec -it td_redis redis-cli SET "call:call_123:customer_id" "1"
```
============== ADD TRANSCRIPT CHUNKS ==============<br>
```
docker exec -it td_redis redis-cli RPUSH "call:call_123:chunks" "Agent: Hello, how can I help you today?"
docker exec -it td_redis redis-cli RPUSH "call:call_123:chunks" "Customer: I have a question about my credit card."
docker exec -it td_redis redis-cli RPUSH "call:call_123:chunks" "Agent: Sure, I can help with that."
docker exec -it td_redis redis-cli RPUSH "call:call_123:chunks" "Customer: There is a charge for 150 dollars I dont recognize."
```
============== CHECK REDIS STATE ==============<br>
```
docker exec -it td_redis redis-cli KEYS "*"
docker exec -it td_redis redis-cli SMEMBERS active_calls
docker exec -it td_redis redis-cli LRANGE "call:call_123:chunks" 0 -1
```
============== WAIT FOR WORKER (5-10 seconds) ==============<br>
============== CHECK SUMMARY ==============<br>
```
curl http://localhost:8002/summary/call_123
```
============== CHECK PROMOTIONS ==============<br>
```
curl http://localhost:8002/promotions/call_123
```
============== HEALTH CHECK ==============<br>
```
curl http://localhost:8002/health
```
============== SAVE TO DATABASE ==============<br>
```
curl -X POST http://localhost:8002/save_summary -H "Content-Type: application/json" -d "{\"call_id\": \"call_123\", \"customer_id\": 1, \"summary\": \"Customer reported unrecognized $150 charge.\"}"
```
============== VERIFY SAVED IN POSTGRES ==============<br>
```
docker exec -it td_db psql -U postgres -d td_poc -c "SELECT * FROM interaction;"
```
============== VERIFY REDIS CLEANUP ==============<br>
```
docker exec -it td_redis redis-cli SMEMBERS active_calls
docker exec -it td_redis redis-cli GET "call:call_123:summary"
```
