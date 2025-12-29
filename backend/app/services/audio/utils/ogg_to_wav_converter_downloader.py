#!/usr/bin/env python3
"""Download OGG files and convert to WAV format."""

import subprocess
import requests
import urllib.request
from pydub import AudioSegment
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# file downloader util


def download_audio_from_url(url: str) -> tuple[bytes, str]:
    filename = url.split("/")[-1]
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "audio" not in content_type.lower():
            raise ValueError(f"Invalid content type: {content_type}")
        return response.content, content_type

    except requests.Timeout:
        logger.error(f"Timeout downloading {filename}")
        raise
    except requests.RequestException as e:
        logger.error(f"Failed to download {filename}: {str(e)}")
        raise


def download_file_from_url(url: str, ogg_path):
    filename = url.split("/")[-1]
    logger.info(f"Downloading {filename}")
    urllib.request.urlretrieve(url, ogg_path)
    return ogg_path


def ogg2wav(ofn, output_path):
    # logger.info(f"Converting to wav file {ofn.name}")
    input_path = Path(ofn)

    audio = AudioSegment.from_ogg(input_path)
    audio.export(output_path, format="wav")
    return str(output_path)


URLS = [
    "https://storage.googleapis.com/speech_samples_glific/1756121051765345.ogg",
    # "https://storage.googleapis.com/speech_samples_glific/1473238230405982.ogg",
    # "https://storage.googleapis.com/speech_samples_glific/1886159865308785.ogg",
    # "https://storage.googleapis.com/speech_samples_glific/1392360452889094.ogg",
    # "https://storage.googleapis.com/speech_samples_glific/1344597243836389.ogg",
    # "https://storage.googleapis.com/speech_samples_glific/1139738341608135.ogg",
    # "https://storage.googleapis.com/speech_samples_glific/1017622387157983.ogg",
    # "https://storage.googleapis.com/speech_samples_glific/1128666189437926.ogg",
    # "https://storage.googleapis.com/speech_samples_glific/838318912486461.ogg",
    # "https://storage.googleapis.com/speech_samples_glific/1352978506618729.ogg",
    # "https://storage.googleapis.com/speech_samples_glific/1253534463206645.ogg",
    # "https://storage.googleapis.com/speech_samples_glific/1454764985596815.ogg",
    # "https://storage.googleapis.com/speech_samples_glific/1535151617932535.ogg",
    # "https://storage.googleapis.com/speech_samples_glific/801106959553719.ogg",
    # "https://storage.googleapis.com/speech_samples_glific/1410046620741206.ogg",
    # "https://storage.googleapis.com/speech_samples_glific/769845976056803.ogg",
    # "https://storage.googleapis.com/speech_samples_glific/1513000746418402.ogg",
    # "https://storage.googleapis.com/speech_samples_glific/2333812740417064.ogg",
    # "https://storage.googleapis.com/speech_samples_glific/4141345536125525.ogg",
    # "https://storage.googleapis.com/speech_samples_glific/1366384631785963.ogg",
]


def main():
    ogg_dir = Path("app/services/audio/sample_data/ogg_files")
    wav_dir = Path("app/services/audio/sample_data/wav_files")
    ogg_dir.mkdir(parents=True, exist_ok=True)
    wav_dir.mkdir(parents=True, exist_ok=True)

    for url in URLS:
        filename = url.split("/")[-1]
        ogg_path = ogg_dir / filename
        wav_path = wav_dir / filename.replace(".ogg", ".wav")

        # Download
        print(f"Downloading {filename}...")
        audio_file = download_audio_from_url(url)
        print(audio_file)

        # Convert
        # print(f"Converting to {wav_path.name}...")
        # converted_file=ogg2wav(ogg_file, wav_path)

    print(f"\nDone. {len(URLS)} files in ./wav_files/")


if __name__ == "__main__":
    main()
