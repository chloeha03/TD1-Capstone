import argparse
import os
import shutil
from faster_whisper import WhisperModel

DEFAULT_MODEL = "small.en"
DEFAULT_OUTPUT = "models/whisper-small"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    print(f"Downloading Whisper model '{args.model}'...")
    
    model = WhisperModel(
        args.model,
        device="cpu",
        compute_type="int8",
        download_root="tmp_download"
    )

    # Find the actual snapshot directory
    base_path = os.path.join("tmp_download", "models--Systran--faster-whisper-" + args.model)
    snapshots = os.path.join(base_path, "snapshots")
    snapshot_hash = os.listdir(snapshots)[0]
    snapshot_path = os.path.join(snapshots, snapshot_hash)

    # Copy to clean output folder
    os.makedirs(args.output, exist_ok=True)
    for file in os.listdir(snapshot_path):
        shutil.copy(
            os.path.join(snapshot_path, file),
            os.path.join(args.output, file)
        )

    print(f"Model prepared at '{args.output}'")
    shutil.rmtree("tmp_download")

if __name__ == "__main__":
    main()
