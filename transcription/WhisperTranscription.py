# pip install faster-whisper
# pip install sounddevice numpy

import sounddevice as sd
import numpy as np
import queue
import threading
from faster_whisper import WhisperModel

# Settings
samplerate = 16000
block_duration = 0.5  # seconds
chunk_duration = 2    # seconds #if stop talking for 2 seconds, then it will stop transcribing
channels = 1

frames_per_block = int(samplerate * block_duration)
frames_per_chunk = int(samplerate * chunk_duration)

audio_queue = queue.Queue()
audio_buffer = []

# Model setup: medium.en + float16 (optimized for 3080)
# NOTE: Changed device to "cpu" for Mac compatibility
model = WhisperModel("large-v3", device="cpu", compute_type="int8")

def audio_callback(indata, frames, time, status):
    if status:
        print(status)
    audio_queue.put(indata.copy())

def recorder():
    with sd.InputStream(samplerate=samplerate, channels=channels, 
                        callback=audio_callback, blocksize=frames_per_block):
        print("🎤 Listening... Press Ctrl+C to stop.")
        while True:
            sd.sleep(100)

def transcriber():
    global audio_buffer
    while True:
        block = audio_queue.get()
        audio_buffer.append(block)

        total_frames = sum(len(b) for b in audio_buffer)
        if total_frames >= frames_per_chunk:
            audio_data = np.concatenate(audio_buffer)[:frames_per_chunk]
            audio_buffer = [] # Clear buffer

            audio_data = audio_data.flatten().astype(np.float32)

            # Transcription without timestamps
            segments, _ = model.transcribe(
                audio_data,
                language="en",
                beam_size=1 # Max speed
            )

            for segment in segments:
                print(f"{segment.text}") # Just print text, no timestamps

# Start threads
threading.Thread(target=recorder, daemon=True).start()
transcriber()


############################################### if converting from audio file (not microphone) #####################
# # pip install faster-whisper

# from faster_whisper import WhisperModel

# model_size = "small.en" #"large-v3" # "medium.en"

# # Run on GPU with FP16
# model = WhisperModel(model_size, device="cpu", compute_type="float16") #device="cuda"

# # or run on GPU with INT8
# # model = WhisperModel(model_size, device="cuda", compute_type="int8_float16")
# # or run on CPU with INT8
# # model = WhisperModel(model_size, device="cpu", compute_type="int8")

# segments, info = model.transcribe("audio.mp3", beam_size=5) #language = "en"

# # print("Detected language '%s' with probability %f" % (info.language, info.language_probability))

# for segment in segments:
#     print("[%.2fs -> %.2fs] %s" % (segment.start, segment.end, segment.text))
