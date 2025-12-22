#!/usr/bin/env python3
"""
Calculate Strict WER and Lenient WER for OpenAI and Gemini STT outputs.

Input CSV should have columns:
- wav_file: filename
- ground_truth: reference transcription
- openai_stt_text: OpenAI transcription (optional)
- gemini_stt_text: Gemini transcription (optional)

Lenient criteria:
- Ignore vowel-based errors (माला/मला, में/मैं, हूँ/हूं)
- Ignore nuqta differences (फ़ैमिली/फैमिली)
- Ignore chandrabindu/anusvara variations
- Ignore tonally similar words (पचवा/पाचवा)

Semantic errors:
- Words with fundamentally different meanings (महीने→दिन, साल→महीना)
- Not just spelling or phonetic variations
"""

import argparse
import csv
import re
from pathlib import Path
from typing import List, Tuple

# Default paths
DEFAULT_INPUT_CSV = Path(__file__).parent.parent / "stt_results.csv"
DEFAULT_OUTPUT_CSV = Path(__file__).parent.parent / "wer_results.csv"

# Providers to evaluate (will be auto-detected from CSV columns)
PROVIDERS = ["openai_stt_text", "gemini_stt_text"]


def tokenize(text: str) -> List[str]:
    """Remove punctuation and split into words."""
    if not text or text.strip() == "":
        return []
    # Remove content in brackets like [स्टूल पर बैठते हुए]
    text = re.sub(r"\[.*?\]", "", text)
    # Remove punctuation
    text = re.sub(r"[।,?\.\!\[\]॥\-:;\'\"।]", " ", text)
    # Split and filter empty strings
    tokens = [t.strip() for t in text.split() if t.strip()]
    return tokens


def normalize_word(w: str) -> str:
    """Normalize word for lenient comparison."""
    # Remove chandrabindu, anusvara
    w = w.replace("ँ", "")
    w = w.replace("ं", "")
    # Remove nuqta
    w = w.replace("़", "")
    # Normalize vowel matras
    w = w.replace("ी", "ि")
    w = w.replace("ै", "े")
    w = w.replace("ा", "")
    w = w.replace("ू", "ु")
    w = w.replace("ो", "")
    w = w.replace("ौ", "")
    w = w.replace("ॉ", "")
    return w


# Known lenient pairs (spelling/phonetic variations that are NOT semantic errors)
LENIENT_PAIRS = {
    ("माला", "मला"),
    ("मला", "माला"),
    ("में", "मैं"),
    ("मैं", "में"),
    ("अहे", "आहे"),
    ("आहे", "अहे"),
    ("महीना", "महिना"),
    ("महिना", "महीना"),
    ("पचवा", "पाचवा"),
    ("पाचवा", "पचवा"),
    ("हूँ", "हूं"),
    ("हूं", "हूँ"),
    ("फ़ैमिली", "फैमिली"),
    ("फैमिली", "फ़ैमिली"),
    ("है", "हैं"),
    ("हैं", "है"),
    ("करें", "करे"),
    ("करे", "करें"),
    ("भेजे", "भेजें"),
    ("भेजें", "भेजे"),
    ("कृपाया", "कृपया"),
    ("कृपया", "कृपाया"),
    ("छटा", "छठा"),
    ("छठा", "छटा"),
    ("चाहिए", "छाइये"),
    ("छाइये", "चाहिए"),
    ("बढ़ना", "बढ़ने"),
    ("बढ़ने", "बढ़ना"),
    ("चाहिए", "चाहिये"),
    ("चाहिये", "चाहिए"),
    ("रहे", "रही"),
    ("रही", "रहे"),
    ("करू", "करूँ"),
    ("करूँ", "करू"),
    ("करूं", "करूँ"),
    ("करूँ", "करूं"),
    ("पे", "पर"),
    ("पर", "पे"),
    ("व्हाट्सएप", "ह्वाट्सऐप"),
    ("ह्वाट्सऐप", "व्हाट्सएप"),
    ("वो", "वह"),
    ("वह", "वो"),
    ("जरूरी", "ज़रूरी"),
    ("ज़रूरी", "जरूरी"),
    ("श्याम", "शाम"),
    ("शाम", "श्याम"),
    ("राधी", "राधे"),
    ("राधे", "राधी"),
    ("पाँच", "पांच"),
    ("पांच", "पाँच"),
    ("9", "नौ"),
    ("नौ", "9"),
    ("2", "दो"),
    ("दो", "2"),
    ("हमारीे", "हमारी"),
    ("हमारी", "हमारीे"),
    ("कहाँ", "कहां"),
    ("कहां", "कहाँ"),
    ("बहुत-बहुत", "बहुत"),
    ("ट्रैकर", "ट्रेकर"),
    ("ट्रेकर", "ट्रैकर"),
    ("कंफ्यूज", "कमफिरोज"),
    ("प्रश्नों", "प्रसुने"),
    ("दीदी", "दिदी"),
    ("दिदी", "दीदी"),
    ("श्री", "स्री"),
    ("स्री", "श्री"),
    ("पाँचसनों", "पाँच"),
    ("आईसीडीएस", "आई"),
    ("के", "का"),
    ("का", "के"),
    ("व", "वो"),
}

# Semantic error pairs - words with fundamentally different meanings
SEMANTIC_ERROR_PAIRS = {
    # Time units (different magnitudes)
    ("महीने", "दिन"),
    ("दिन", "महीने"),
    ("महीना", "दिन"),
    ("दिन", "महीना"),
    ("साल", "महीना"),
    ("महीना", "साल"),
    ("साल", "दिन"),
    ("दिन", "साल"),
    ("हफ्ता", "दिन"),
    ("दिन", "हफ्ता"),
    ("घंटा", "दिन"),
    ("दिन", "घंटा"),
    # Numbers (different values)
    ("एक", "दो"),
    ("दो", "एक"),
    ("दो", "तीन"),
    ("तीन", "दो"),
    ("पाँच", "दस"),
    ("दस", "पाँच"),
    ("सौ", "हजार"),
    ("हजार", "सौ"),
    # Pronouns (different persons)
    ("मैं", "तुम"),
    ("तुम", "मैं"),
    ("वह", "हम"),
    ("हम", "वह"),
    ("तुम", "आप"),
    ("आप", "तुम"),
    # Opposite meanings
    ("आगे", "पीछे"),
    ("पीछे", "आगे"),
    ("ऊपर", "नीचे"),
    ("नीचे", "ऊपर"),
    ("अंदर", "बाहर"),
    ("बाहर", "अंदर"),
    ("हाँ", "नहीं"),
    ("नहीं", "हाँ"),
    # Different concepts
    ("इससे", "इसमें"),
    ("इसमें", "इससे"),
    ("नाम", "पता"),
    ("पता", "नाम"),
    ("माँ", "बहन"),
    ("बहन", "माँ"),
    ("पिता", "भाई"),
    ("भाई", "पिता"),
}


def is_semantic_error(gt_word: str, hyp_word: str) -> bool:
    """Check if two words form a semantic error (fundamentally different meanings)."""
    return (gt_word, hyp_word) in SEMANTIC_ERROR_PAIRS


def is_lenient_match(gt_word: str, hyp_word: str) -> bool:
    """Check if two words match under lenient criteria."""
    if gt_word == hyp_word:
        return True

    # Semantic errors are NOT lenient matches
    if is_semantic_error(gt_word, hyp_word):
        return False

    # Check normalized match
    if normalize_word(gt_word) == normalize_word(hyp_word):
        return True

    # Check known lenient pairs
    if (gt_word, hyp_word) in LENIENT_PAIRS:
        return True

    return False


def calculate_wer(
    ref_tokens: List[str], hyp_tokens: List[str], lenient: bool = False
) -> Tuple[float, int, int, int, int]:
    """
    Calculate WER using dynamic programming.
    Returns: (wer, substitutions, deletions, insertions, semantic_errors)

    semantic_errors: count of substitutions that are semantic errors (only meaningful in lenient mode)
    """
    n = len(ref_tokens)
    m = len(hyp_tokens)

    if n == 0:
        return (1.0 if m > 0 else 0.0, 0, 0, m, 0)

    if m == 0:
        return (1.0, 0, n, 0, 0)

    # DP table
    dp = [[0] * (m + 1) for _ in range(n + 1)]

    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if lenient:
                match = is_lenient_match(ref_tokens[i - 1], hyp_tokens[j - 1])
            else:
                match = ref_tokens[i - 1] == hyp_tokens[j - 1]

            if match:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = min(
                    dp[i - 1][j] + 1,  # deletion
                    dp[i][j - 1] + 1,  # insertion
                    dp[i - 1][j - 1] + 1,  # substitution
                )

    # Backtrack and count error types
    i, j = n, m
    s, d, ins, sem = 0, 0, 0, 0

    while i > 0 or j > 0:
        if i > 0 and j > 0:
            if lenient:
                match = is_lenient_match(ref_tokens[i - 1], hyp_tokens[j - 1])
            else:
                match = ref_tokens[i - 1] == hyp_tokens[j - 1]

            if match and dp[i][j] == dp[i - 1][j - 1]:
                i -= 1
                j -= 1
                continue

        if i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + 1:
            # This is a substitution
            s += 1
            # Check if it's also a semantic error
            if is_semantic_error(ref_tokens[i - 1], hyp_tokens[j - 1]):
                sem += 1
            i -= 1
            j -= 1
        elif j > 0 and dp[i][j] == dp[i][j - 1] + 1:
            ins += 1
            j -= 1
        elif i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            d += 1
            i -= 1
        else:
            # Fallback
            if i > 0 and j > 0:
                s += 1
                if is_semantic_error(ref_tokens[i - 1], hyp_tokens[j - 1]):
                    sem += 1
                i -= 1
                j -= 1
            elif j > 0:
                ins += 1
                j -= 1
            else:
                d += 1
                i -= 1

    wer = (s + d + ins) / n if n > 0 else 0
    return (wer, s, d, ins, sem)


def process_csv(input_path: Path, output_path: Path):
    """Process CSV and calculate WER for OpenAI and Gemini providers."""

    print(f"Reading input CSV: {input_path}")

    with open(input_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print("Error: CSV is empty")
        return

    # Check for required columns
    fieldnames = list(rows[0].keys())
    if "ground_truth" not in fieldnames:
        print("Error: CSV must contain 'ground_truth' column")
        print(f"Found columns: {fieldnames}")
        return

    # Detect which provider columns are present
    available_providers = [p for p in PROVIDERS if p in fieldnames]

    if not available_providers:
        print(f"Error: No STT provider columns found. Expected: {PROVIDERS}")
        print(f"Found columns: {fieldnames}")
        return

    print(f"Found providers: {available_providers}")

    # Prepare output fieldnames
    output_fields = list(fieldnames)

    # Add WER and error breakdown columns for each available provider
    for provider in available_providers:
        short_name = provider.replace("_stt_text", "")
        # WER scores
        output_fields.append(f"wer_strict_{short_name}")
        output_fields.append(f"wer_lenient_{short_name}")
        # Strict mode error breakdown
        output_fields.append(f"strict_sub_{short_name}")
        output_fields.append(f"strict_del_{short_name}")
        output_fields.append(f"strict_ins_{short_name}")
        output_fields.append(f"strict_sem_{short_name}")
        # Lenient mode error breakdown
        output_fields.append(f"lenient_sub_{short_name}")
        output_fields.append(f"lenient_del_{short_name}")
        output_fields.append(f"lenient_ins_{short_name}")
        output_fields.append(f"lenient_sem_{short_name}")

    results = []

    for idx, row in enumerate(rows, 1):
        ground_truth = row.get("ground_truth", "")
        gt_tokens = tokenize(ground_truth)

        print(
            f"\nRow {idx} ({row.get('wav_file', '?')}): GT has {len(gt_tokens)} words"
        )

        for provider in available_providers:
            hyp_text = row.get(provider, "")
            hyp_tokens = tokenize(hyp_text)

            short_name = provider.replace("_stt_text", "")

            if not hyp_text or hyp_text.strip() == "" or hyp_text.startswith("ERROR:"):
                # Empty fields for missing/errored transcriptions
                row[f"wer_strict_{short_name}"] = ""
                row[f"wer_lenient_{short_name}"] = ""
                row[f"strict_sub_{short_name}"] = ""
                row[f"strict_del_{short_name}"] = ""
                row[f"strict_ins_{short_name}"] = ""
                row[f"strict_sem_{short_name}"] = ""
                row[f"lenient_sub_{short_name}"] = ""
                row[f"lenient_del_{short_name}"] = ""
                row[f"lenient_ins_{short_name}"] = ""
                row[f"lenient_sem_{short_name}"] = ""
                print(f"  {short_name:12}: SKIPPED (no transcription)")
            else:
                # Strict WER
                wer_strict, s_strict, d_strict, i_strict, sem_strict = calculate_wer(
                    gt_tokens, hyp_tokens, lenient=False
                )
                row[f"wer_strict_{short_name}"] = f"{wer_strict:.4f}"
                row[f"strict_sub_{short_name}"] = str(s_strict)
                row[f"strict_del_{short_name}"] = str(d_strict)
                row[f"strict_ins_{short_name}"] = str(i_strict)
                row[f"strict_sem_{short_name}"] = str(sem_strict)

                # Lenient WER
                (
                    wer_lenient,
                    s_lenient,
                    d_lenient,
                    i_lenient,
                    sem_lenient,
                ) = calculate_wer(gt_tokens, hyp_tokens, lenient=True)
                row[f"wer_lenient_{short_name}"] = f"{wer_lenient:.4f}"
                row[f"lenient_sub_{short_name}"] = str(s_lenient)
                row[f"lenient_del_{short_name}"] = str(d_lenient)
                row[f"lenient_ins_{short_name}"] = str(i_lenient)
                row[f"lenient_sem_{short_name}"] = str(sem_lenient)

                print(
                    f"  {short_name:12}: strict={wer_strict*100:.1f}% (S:{s_strict},D:{d_strict},I:{i_strict},Sem:{sem_strict}) | "
                    f"lenient={wer_lenient*100:.1f}% (S:{s_lenient},D:{d_lenient},I:{i_lenient},Sem:{sem_lenient})"
                )

        results.append(row)

    # Write output
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=output_fields)
        writer.writeheader()
        writer.writerows(results)

    print(f"\n✓ Results saved to {output_path}")

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    for provider in available_providers:
        short_name = provider.replace("_stt_text", "")

        strict_vals = [
            float(r[f"wer_strict_{short_name}"])
            for r in results
            if r[f"wer_strict_{short_name}"] != ""
        ]
        lenient_vals = [
            float(r[f"wer_lenient_{short_name}"])
            for r in results
            if r[f"wer_lenient_{short_name}"] != ""
        ]

        if not strict_vals:
            print(f"{short_name:12}: No valid transcriptions")
            continue

        # Calculate average error counts
        strict_sub_avg = sum(
            [
                int(r[f"strict_sub_{short_name}"])
                for r in results
                if r[f"strict_sub_{short_name}"] != ""
            ]
        ) / len(strict_vals)
        strict_del_avg = sum(
            [
                int(r[f"strict_del_{short_name}"])
                for r in results
                if r[f"strict_del_{short_name}"] != ""
            ]
        ) / len(strict_vals)
        strict_ins_avg = sum(
            [
                int(r[f"strict_ins_{short_name}"])
                for r in results
                if r[f"strict_ins_{short_name}"] != ""
            ]
        ) / len(strict_vals)
        strict_sem_avg = sum(
            [
                int(r[f"strict_sem_{short_name}"])
                for r in results
                if r[f"strict_sem_{short_name}"] != ""
            ]
        ) / len(strict_vals)

        lenient_sub_avg = sum(
            [
                int(r[f"lenient_sub_{short_name}"])
                for r in results
                if r[f"lenient_sub_{short_name}"] != ""
            ]
        ) / len(lenient_vals)
        lenient_del_avg = sum(
            [
                int(r[f"lenient_del_{short_name}"])
                for r in results
                if r[f"lenient_del_{short_name}"] != ""
            ]
        ) / len(lenient_vals)
        lenient_ins_avg = sum(
            [
                int(r[f"lenient_ins_{short_name}"])
                for r in results
                if r[f"lenient_ins_{short_name}"] != ""
            ]
        ) / len(lenient_vals)
        lenient_sem_avg = sum(
            [
                int(r[f"lenient_sem_{short_name}"])
                for r in results
                if r[f"lenient_sem_{short_name}"] != ""
            ]
        ) / len(lenient_vals)

        avg_strict = sum(strict_vals) / len(strict_vals)
        avg_lenient = sum(lenient_vals) / len(lenient_vals)

        print(f"{short_name:12}:")
        print(
            f"  Strict  WER = {avg_strict*100:.2f}% | Avg Errors: Sub={strict_sub_avg:.1f}, Del={strict_del_avg:.1f}, Ins={strict_ins_avg:.1f}, Sem={strict_sem_avg:.1f}"
        )
        print(
            f"  Lenient WER = {avg_lenient*100:.2f}% | Avg Errors: Sub={lenient_sub_avg:.1f}, Del={lenient_del_avg:.1f}, Ins={lenient_ins_avg:.1f}, Sem={lenient_sem_avg:.1f}"
        )
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Calculate WER for OpenAI and Gemini STT outputs"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_CSV,
        help=f"Input CSV file (default: {DEFAULT_INPUT_CSV})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_CSV,
        help=f"Output CSV file (default: {DEFAULT_OUTPUT_CSV})",
    )

    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}")
        print(f"\nPlease ensure the CSV has these columns:")
        print(f"  - wav_file: filename")
        print(f"  - ground_truth: reference transcription")
        print(f"  - openai_stt_text: OpenAI transcription (optional)")
        print(f"  - gemini_stt_text: Gemini transcription (optional)")
        return

    process_csv(args.input, args.output)


if __name__ == "__main__":
    main()
