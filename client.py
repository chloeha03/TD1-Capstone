import asyncio
import json
import sounddevice as sd
import numpy as np
import websockets

SAMPLE_RATE = 16000
CHUNK_DURATION = 0.5  # seconds
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_DURATION)

CALL_ID = "demo-call-001"

# >>>>>>> REPLACE THIS with ngrok websocket URL <<<<<<<
WS_URL = "wss://unepic-unmerchandised-katie.ngrok-free.dev/ws"  # example


async def stream_microphone():
    async with websockets.connect(WS_URL) as websocket:
        print("Connected to server:", WS_URL)

        loop = asyncio.get_event_loop()

        # Queue to pass incoming transcripts from network to main loop
        transcripts = asyncio.Queue()

        async def receiver():
            # receive messages (transcripts) from server
            async for message in websocket:
                data = json.loads(message)
                text = data.get("partial_transcript", "")
                await transcripts.put(text)

        # Start receiver task
        recv_task = asyncio.create_task(receiver())

        def audio_callback(indata, frames, time_, status):
            if status:
                print("Audio status:", status, flush=True)
            audio_float32 = indata[:, 0]  # mono
            audio_int16 = (audio_float32 * 32767).astype(np.int16)
            audio_hex = audio_int16.tobytes().hex()

            msg = {
                "call_id": CALL_ID,
                "audio_hex": audio_hex
            }
            # Schedule send on the event loop
            asyncio.run_coroutine_threadsafe(
                websocket.send(json.dumps(msg)),
                loop
            )

        # Start microphone stream
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=CHUNK_SAMPLES,
            callback=audio_callback
        ):
            print("Streaming from microphone. Speak now (Ctrl+C to stop).")

            try:
                # UI loop: print latest transcript whenever updated
                last_printed = ""
                while True:
                    text = await transcripts.get()
                    if text != last_printed:
                        last_printed = text
                        print("\rTranscript:", text[:200], end="", flush=True)
            except KeyboardInterrupt:
                print("\nStopped by user.")

        # Clean up
        recv_task.cancel()


if __name__ == "__main__":
    asyncio.run(stream_microphone())

