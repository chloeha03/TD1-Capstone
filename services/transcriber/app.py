import os
import json
import asyncio
import numpy as np
from collections import defaultdict, deque
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import redis

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
SAMPLE_RATE = 16000
BUFFER_SECONDS = 3
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "medium.en")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cuda")
WHISPER_COMPUTE = os.getenv("WHISPER_COMPUTE", "float16")
MODEL_PATH = os.getenv("WHISPER_MODEL_PATH", None)

redis_client = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)

print(f"Loading Whisper model '{WHISPER_MODEL}' on {WHISPER_DEVICE} ({WHISPER_COMPUTE})...")
from faster_whisper import WhisperModel

model_location = MODEL_PATH if MODEL_PATH else WHISPER_MODEL
model = WhisperModel(model_location, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE)
print("Model loaded.")

session_buffers: dict[str, deque] = defaultdict(
    lambda: deque(maxlen=BUFFER_SECONDS * SAMPLE_RATE)
)

app = FastAPI(title="Transcriber Service")


def transcribe_buffer(call_id: str) -> str:
    buf = session_buffers[call_id]
    if len(buf) == 0:
        return ""
    audio_np = np.array(buf, dtype=np.float32)
    segments, _ = model.transcribe(
        audio_np,
        language="en",
        vad_filter=True,
        beam_size=1,
        without_timestamps=True,
    )
    return " ".join(seg.text.strip() for seg in segments)


def push_to_redis(call_id: str, customer_id: str, text: str):
    if not text or not text.strip():
        return

    text = text.strip()

    pipe = redis_client.pipeline()

    pipe.set(f"call:{call_id}:customer_id", customer_id)
    pipe.rpush(f"call:{call_id}:chunks", text)

    # Try adding to pending set
    pipe.sadd("pending_calls", call_id)

    results = pipe.execute()

    was_added = results[-1]  # sadd returns 1 if newly added

    if was_added:
        redis_client.rpush("summarize_queue", call_id)


@app.websocket("/ws/transcribe")
async def ws_transcribe(websocket: WebSocket):
    await websocket.accept()
    call_id = None
    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            call_id = data["call_id"]
            customer_id = str(data.get("customer_id", call_id))
            audio_hex = data["audio_hex"]

            audio_bytes = bytes.fromhex(audio_hex)
            audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
            audio_float32 = audio_int16.astype(np.float32) / 32768.0

            buf = session_buffers[call_id]
            buf.extend(audio_float32.tolist())

            if len(buf) >= BUFFER_SECONDS * SAMPLE_RATE:
                transcript = await asyncio.to_thread(transcribe_buffer, call_id)
                if transcript.strip():
                    push_to_redis(call_id, customer_id, transcript)
                    await websocket.send_text(json.dumps({
                        "call_id": call_id,
                        "transcript_chunk": transcript,
                    }))
                buf.clear()

    except WebSocketDisconnect:
        if call_id and len(session_buffers.get(call_id, [])) > 0:
            transcript = transcribe_buffer(call_id)
            if transcript.strip():
                push_to_redis(call_id, str(call_id), transcript)
        if call_id and call_id in session_buffers:
            del session_buffers[call_id]
        print(f"Client disconnected (call_id={call_id})")


@app.get("/health")
def health():
    return {"status": "healthy", "model": WHISPER_MODEL, "device": WHISPER_DEVICE}
