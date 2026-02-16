import asyncio
import argparse
import json
import sounddevice as sd
import numpy as np
import websockets

SAMPLE_RATE = 16000
CHUNK_DURATION = 0.5
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_DURATION)


async def stream_microphone(ws_url: str, call_id: str, customer_id: str):
    async with websockets.connect(ws_url) as websocket:
        print(f"Connected to {ws_url}")
        print(f"Call ID: {call_id} | Customer ID: {customer_id}")

        loop = asyncio.get_event_loop()
        transcripts = asyncio.Queue()

        async def receiver():
            async for message in websocket:
                data = json.loads(message)
                text = data.get("transcript_chunk", "")
                await transcripts.put(text)

        recv_task = asyncio.create_task(receiver())

        def audio_callback(indata, frames, time_, status):
            if status:
                print("Audio status:", status, flush=True)
            audio_float32 = indata[:, 0]
            audio_int16 = (audio_float32 * 32767).astype(np.int16)
            audio_hex = audio_int16.tobytes().hex()
            msg = {
                "call_id": call_id,
                "customer_id": customer_id,
                "audio_hex": audio_hex,
            }
            asyncio.run_coroutine_threadsafe(
                websocket.send(json.dumps(msg)), loop
            )

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=CHUNK_SAMPLES,
            callback=audio_callback,
        ):
            print("Streaming from microphone. Speak now (Ctrl+C to stop).")
            try:
                while True:
                    text = await transcripts.get()
                    print(f"[Transcript] {text}")
            except KeyboardInterrupt:
                print("\nStopped by user.")

        recv_task.cancel()


def main():
    parser = argparse.ArgumentParser(description="Stream microphone audio to the Whisper transcription service")
    parser.add_argument("--url", default="ws://localhost:8001/ws/transcribe", help="WebSocket URL of the transcriber")
    parser.add_argument("--call-id", default="demo-call-001", help="Call ID for this session")
    parser.add_argument("--customer-id", default="1", help="Customer ID for this session")
    args = parser.parse_args()
    asyncio.run(stream_microphone(args.url, args.call_id, args.customer_id))


if __name__ == "__main__":
    main()
