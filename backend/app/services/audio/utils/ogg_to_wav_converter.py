#!/usr/bin/env python3
"""Download OGG files and convert to WAV format."""

import subprocess
import urllib.request
from pathlib import Path

URLS = [
    "https://storage.googleapis.com/speech_samples_glific/1756121051765345.ogg",
    "https://storage.googleapis.com/speech_samples_glific/1473238230405982.ogg",
    "https://storage.googleapis.com/speech_samples_glific/1886159865308785.ogg",
    "https://storage.googleapis.com/speech_samples_glific/1392360452889094.ogg",
    "https://storage.googleapis.com/speech_samples_glific/1344597243836389.ogg",
    "https://storage.googleapis.com/speech_samples_glific/1139738341608135.ogg",
    "https://storage.googleapis.com/speech_samples_glific/1017622387157983.ogg",
    "https://storage.googleapis.com/speech_samples_glific/1128666189437926.ogg",
    "https://storage.googleapis.com/speech_samples_glific/838318912486461.ogg",
    "https://storage.googleapis.com/speech_samples_glific/1352978506618729.ogg",
    "https://storage.googleapis.com/speech_samples_glific/1253534463206645.ogg",
    "https://storage.googleapis.com/speech_samples_glific/1454764985596815.ogg",
    "https://storage.googleapis.com/speech_samples_glific/1535151617932535.ogg",
    "https://storage.googleapis.com/speech_samples_glific/801106959553719.ogg",
    "https://storage.googleapis.com/speech_samples_glific/1410046620741206.ogg",
    "https://storage.googleapis.com/speech_samples_glific/769845976056803.ogg",
    "https://storage.googleapis.com/speech_samples_glific/1513000746418402.ogg",
    "https://storage.googleapis.com/speech_samples_glific/2333812740417064.ogg",
    "https://storage.googleapis.com/speech_samples_glific/4141345536125525.ogg",
    "https://storage.googleapis.com/speech_samples_glific/1366384631785963.ogg",
]


def main():
    ogg_dir = Path("ogg_files")
    wav_dir = Path("wav_files")
    ogg_dir.mkdir(exist_ok=True)
    wav_dir.mkdir(exist_ok=True)

    for url in URLS:
        filename = url.split("/")[-1]
        ogg_path = ogg_dir / filename
        wav_path = wav_dir / filename.replace(".ogg", ".wav")

        # Download
        print(f"Downloading {filename}...")
        urllib.request.urlretrieve(url, ogg_path)

        # Convert
        print(f"Converting to {wav_path.name}...")
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(ogg_path), str(wav_path)],
            capture_output=True,
        )

    print(f"\nDone. {len(URLS)} files in ./wav_files/")


if __name__ == "__main__":
    main()
