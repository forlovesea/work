"""Download and validate multilingual small; no meeting audio is sent."""
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from faster_whisper import WhisperModel, download_model
    import numpy as np
    args.output.mkdir(parents=True, exist_ok=True)
    download_model("small", output_dir=str(args.output))
    model = WhisperModel(str(args.output), device="cpu", compute_type="int8",
                         cpu_threads=1, num_workers=1, local_files_only=True)
    segments, _ = model.transcribe(np.zeros(16000, dtype=np.float32), language="ko", vad_filter=True)
    assert not list(segments), "Silence must not produce text"
    print("Whisper small CPU INT8 and VAD ready:", args.output)


if __name__ == "__main__":
    main()
