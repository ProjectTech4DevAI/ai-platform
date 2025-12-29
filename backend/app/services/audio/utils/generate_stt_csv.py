#!/usr/bin/env python3
"""
Generate STT results CSV from WAV files using OpenAI and Gemini providers.
Processes all WAV files in sample_data/wav_files and saves results to CSV.

Usage:
    python generate_stt_csv.py --provider openai
    python generate_stt_csv.py --provider gemini
    python generate_stt_csv.py --provider both
"""

import argparse
import csv
import logging
import os
from pathlib import Path
from typing import Literal
from dotenv import load_dotenv

load_dotenv()

# Add parent directory to path to import speech_to_text module
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.services.audio.speech_to_text import transcribe_audio

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Configuration
WAV_DIR = Path(__file__).parent.parent / "sample_data" / "wav_files"
OUTPUT_CSV = Path(__file__).parent.parent / "stt_results.csv"


def transcribe_file(
    wav_path: Path,
    provider: Literal["openai", "gemini"],
    openai_key: str | None,
    gemini_key: str | None,
) -> str:
    """Transcribe a single WAV file using the specified provider."""
    try:
        text = transcribe_audio(
            audio_file=str(wav_path),
            provider=provider,
            model="gemini-3-pro-preview",
            api_key=gemini_key
            # api_key=openai_key
        )
        return text or f"ERROR: Empty response from {provider}"
    except Exception as e:
        logger.error(f"Failed to transcribe {wav_path.name} with {provider}: {e}")
        return f"ERROR: {e}"


def process_wav_files(provider: str):
    """Process all WAV files and generate/update CSV with STT results."""

    # Get API keys from environment
    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")

    # Validate API keys based on provider
    if provider in ["openai", "both"] and not openai_key:
        logger.error("OPENAI_API_KEY not found in environment variables")
        return

    if provider in ["gemini", "both"] and not gemini_key:
        logger.error("GEMINI_API_KEY not found in environment variables")
        return

    # Check if CSV already exists with existing data
    existing_data = {}
    existing_fieldnames = []

    if OUTPUT_CSV.exists():
        logger.info(f"Found existing CSV: {OUTPUT_CSV}")
        logger.info("Reading existing data to preserve columns...")

        with open(OUTPUT_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            existing_fieldnames = list(reader.fieldnames or [])

            for row in reader:
                wav_file = row.get("wav_file", "")
                if wav_file:
                    existing_data[wav_file] = dict(row)

        logger.info(
            f"Loaded {len(existing_data)} existing rows with columns: {existing_fieldnames}"
        )

    # Determine which files to process
    files_to_process = []

    if existing_data:
        # Use existing CSV rows
        logger.info(f"Processing {len(existing_data)} files from existing CSV")
        files_to_process = list(existing_data.keys())
    else:
        # Scan WAV directory for new files
        if not WAV_DIR.exists():
            logger.error(f"WAV directory not found: {WAV_DIR}")
            logger.info(f"Please create the directory and add WAV files: {WAV_DIR}")
            return

        wav_files = sorted(WAV_DIR.glob("*.wav"))

        if not wav_files:
            logger.warning(f"No WAV files found in {WAV_DIR}")
            return

        logger.info(f"Found {len(wav_files)} WAV files in {WAV_DIR}")
        files_to_process = [wav.name for wav in wav_files]

    # Process each file
    results = []

    for i, wav_filename in enumerate(files_to_process, 1):
        logger.info(f"[{i}/{len(files_to_process)}] Processing {wav_filename}...")

        # Start with existing data if available
        if wav_filename in existing_data:
            result = existing_data[wav_filename].copy()
        else:
            result = {"wav_file": wav_filename}

        # Get full path to WAV file
        wav_path = WAV_DIR / wav_filename

        if not wav_path.exists():
            logger.warning(f"  ⚠ WAV file not found: {wav_path}")
            logger.warning(
                f"  Skipping transcription (preserving existing data if any)"
            )
            results.append(result)
            continue

        # Transcribe with OpenAI
        if provider in ["openai", "both"]:
            logger.info(f"  → Transcribing with OpenAI...")
            openai_text = transcribe_file(wav_path, "openai", openai_key, gemini_key)
            result["openai_stt_text"] = openai_text
            logger.info(
                f"  ✓ OpenAI: {openai_text[:50]}..."
                if len(openai_text) > 50
                else f"  ✓ OpenAI: {openai_text}"
            )

        # Transcribe with Gemini
        if provider in ["gemini", "both"]:
            logger.info(f"  → Transcribing with Gemini...")
            gemini_text = transcribe_file(wav_path, "gemini", openai_key, gemini_key)
            result["gemini_stt_text"] = gemini_text
            logger.info(
                f"  ✓ Gemini: {gemini_text[:50]}..."
                if len(gemini_text) > 50
                else f"  ✓ Gemini: {gemini_text}"
            )

        results.append(result)

    # Determine final fieldnames (preserve existing + add new provider columns)
    base_fieldnames = ["wav_file"]

    # Add ground_truth if it exists in existing data
    if "ground_truth" in existing_fieldnames:
        base_fieldnames.append("ground_truth")

    # Add any other existing columns (excluding provider columns we'll add)
    for field in existing_fieldnames:
        if field not in base_fieldnames and field not in [
            "openai_stt_text",
            "gemini_stt_text",
        ]:
            base_fieldnames.append(field)

    # Add provider columns based on what we're generating
    if provider in ["openai", "both"]:
        base_fieldnames.append("openai_stt_text")
    if provider in ["gemini", "both"]:
        base_fieldnames.append("gemini_stt_text")

    fieldnames = base_fieldnames

    # Write results to CSV
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    logger.info(f"\n✓ Done! Results saved to {OUTPUT_CSV}")
    logger.info(f"  Total files processed: {len(results)}")
    logger.info(f"  Columns in output: {fieldnames}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate STT results CSV from WAV files"
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=["openai", "gemini", "both"],
        default="both",
        help="STT provider to use (default: both)",
    )

    args = parser.parse_args()

    logger.info(f"Starting STT CSV generation with provider: {args.provider}")
    process_wav_files(args.provider)


if __name__ == "__main__":
    main()
