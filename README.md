# TD1-Capstone

To run frontend:

- save this project to your local drive
- download node.js
- in windows powershell, cd into the front end folder, run npm install, then do npm run dev
- go to the local dev link that is displayed

To run transcription service:

1. Download the Whisper model:
```
pip install faster-whisper
python services/transcriber/download_model.py
```

2. Start the services (GPU):
```
docker-compose up --build redis transcriber_svc
```

Or start with CPU mode:
```
docker-compose --profile cpu up --build redis transcriber_cpu
```

3. Install client dependencies and run:
```
cd client
pip install -r requirements.txt
python client.py --call-id call_123 --customer-id 1
```

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



To test the end-to-end flow of the transcriber + summarizer + database:<br>

First need to download the llama model (can download the cuda version of pytorch if you have a GPU)<br>
You also need a huggingface token and request access to Llama 3, exported as `HF_TOKEN` <br>
Linux/Mac: `export HF_TOKEN=<your token>`<br>
Windows cmd: `set HF_TOKEN=<your token>`<br>

```
pip install -r requirements.txt
python services/summarizer/download_model.py
python services/transcriber/download_model.py
```

Then start the databases and services:
```
docker-compose up --build redis db summarizer_svc transcriber_svc
```

Then in another terminal, run the following commands to simulate a call and check the results:<br>
============== VERIFY DATA IS INITIALIZED ==============<br>
```
docker exec -it td_db psql -U postgres -d td_poc -c "SELECT * FROM customer;"
docker exec -it td_db psql -U postgres -d td_poc -c "SELECT * FROM promotion;"
```
============== CREATE A NEW CALL ==============<br>
```
cd client
pip install -r requirements.txt
python client.py --call-id call_123 --customer-id 1
```

Now you can speak into your default microphone.

============== CHECK REDIS STATE ==============<br>
```
docker exec -it td_redis redis-cli KEYS "*"
docker exec -it td_redis redis-cli SMEMBERS active_calls
docker exec -it td_redis redis-cli LRANGE "call:call_123:chunks" 0 -1
```
============== WAIT FOR WORKER ==============<br>
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


example run:
```
>docker exec -it td_db psql -U postgres -d td_poc -c "SELECT * FROM customer;"
 id | first_name | last_name | preferred_name | phone_number | address | employment_info | total_assets |                financial_data                | call_reason | contact_center |         created_at
----+------------+-----------+----------------+--------------+---------+-----------------+--------------+----------------------------------------------+-------------+----------------+----------------------------
  1 | John       | Smith     |                |              | null    | null            |    150000.00 | {"accounts": [], "last_digital_visit": null} |             |          
      | 2026-02-06 03:27:32.296505
  2 | Jane       | Doe       |                |              | null    | null            |    250000.00 | {"accounts": [], "last_digital_visit": null} |             |          
      | 2026-02-06 03:27:32.304928
(2 rows)


>docker exec -it td_db psql -U postgres -d td_poc -c "SELECT * FROM promotion;"
 id |          description           |       conditions       | requirements 
----+--------------------------------+------------------------+--------------
  1 | 10% off credit card annual fee | {"min_assets": 100000} |
(1 row)


>docker exec -it td_redis redis-cli SADD active_calls "call_123"
(integer) 1

>docker exec -it td_redis redis-cli SET "call:call_123:customer_id" "1"
OK

>docker exec -it td_redis redis-cli RPUSH "call:call_123:chunks" "Agent: Hello, how can I help you today?"
(integer) 1

>docker exec -it td_redis redis-cli RPUSH "call:call_123:chunks" "Customer: I have a question about my credit card."
(integer) 2

>curl http://localhost:8002/summary/call_123
{
  "call_id": "call_123",
  "rolling_summary": {
    "bullets": [
      {
        "client_issue": "The customer has a question about their credit card.",
        "agent_action": "The agent is actively listening to the customer's concern.",
        "next_step": "The agent will ask follow-up questions to clarify the customer's issue."
      }
    ],
    "crm_paragraph": "The customer is inquiring about their credit card, indicating a potential issue or concern. The agent should gather more information to understand the customer's needs and provide a resolution or escalate the issue if necessary."
  },
  "history_summary": "",
  "promotions": {
    "recommendations": [
      {
        "promo_id": "1",
        "name": "",
        "expiry": "Not specified",
        "description": "10% off credit card annual fee",
        "fulfillment_steps": "Not specified",
        "reason": "Eligible based on minimum assets requirement"
      }
    ],
    "no_relevant_flag": false
  },
  "chunks_processed": 2
}
>docker exec -it td_redis redis-cli RPUSH "call:call_123:chunks" "Agent: Sure, I can help with that."
(integer) 3

>docker exec -it td_redis redis-cli RPUSH "call:call_123:chunks" "Customer: There is a charge for 150 dollars I dont recognize."
(integer) 4

>docker exec -it td_redis redis-cli KEYS "*"
1) "active_calls"
2) "call:call_123:history"
3) "call:call_123:processed_index"
4) "call:call_123:customer_id"
5) "call:call_123:last_summary_ts"
6) "call:call_123:summary"
7) "call:call_123:promotions"
8) "call:call_123:chunks"

>docker exec -it td_redis redis-cli SMEMBERS active_calls
1) "call_123"

>docker exec -it td_redis redis-cli LRANGE "call:call_123:chunks" 0 -1
1) "Agent: Hello, how can I help you today?"
2) "Customer: I have a question about my credit card."
3) "Agent: Sure, I can help with that."
4) "Customer: There is a charge for 150 dollars I dont recognize."

>curl http://localhost:8002/summary/call_123
{
  "call_id": "call_123",
  "rolling_summary": {
    "bullets": [
      {
        "client_issue": "The customer is concerned about an unrecognized charge of $150 on their credit card.",
        "agent_action": "The agent acknowledged the customer's concern and expressed willingness to assist.",
        "next_step": "The agent will ask follow-up questions to clarify the customer's issue, such as the date of the transaction and the merchant's name."
      }
    ],
    "crm_paragraph": "The customer is experiencing a potential security issue with their credit card, as they've reported an unrecognized charge. The agent should gather more information to understand the customer's needs and provide a resolution or escalate the issue to the security team if necessary."
  },
  "history_summary": "Unresolved issue: unrecognized charge of $150. Client profile: John Smith, Assets: $150,000.00",
  "promotions": {
    "recommendations": [
      {
        "promo_id": "1",
        "name": "",
        "expiry": "Not specified",
        "description": "10% off credit card annual fee",
        "fulfillment_steps": "Not specified",
        "reason": "Client has sufficient assets ($150,000) to qualify for the promotion"
      }
    ],
    "no_relevant_flag": false
  },
  "chunks_processed": 4
}
>curl http://localhost:8002/promotions/call_123
{"recommendations":[{"promo_id":"1","name":"","expiry":"Not specified","description":"10% off credit card annual fee","fulfillment_steps":"Not specified","reason":"Client has sufficient assets ($150,000) to qualify for this promotion"}],"no_relevant_flag":false}
>curl -X POST http://localhost:8002/save_summary -H "Content-Type: application/json" -d "{\"call_id\": \"call_123\", \"customer_id\": 1, \"summary\": \"Customer reported unrecognized $150 charge.\"}"
{"interaction_id":1,"summary":"Customer reported unrecognized $150 charge."}
>docker exec -it td_db psql -U postgres -d td_poc -c "SELECT * FROM interaction;"
 id | customer_id |    type    |                   summary                   |            date
----+-------------+------------+---------------------------------------------+----------------------------
  1 |           1 | PHONE_CALL | Customer reported unrecognized $150 charge. | 2026-02-06 03:33:32.678063
(1 row)


>docker exec -it td_redis redis-cli SMEMBERS active_calls
(empty array)

>docker exec -it td_redis redis-cli GET "call:call_123:summary"
(nil)
```
