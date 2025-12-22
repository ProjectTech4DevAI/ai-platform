# Sample Audio Data

Place your WAV files in the `wav_files/` directory to use the STT utility scripts.

## Workflow

### 1. Prepare Initial CSV (Optional)

You have two options:

**Option A: Start from WAV files (recommended for first run)**
- Add your `.wav` files to `wav_files/`
- Skip to step 2

**Option B: Start with CSV containing ground truth**
- Create `app/services/audio/stt_results.csv` with columns:
  ```csv
  wav_file,ground_truth
  audio1.wav,Reference transcription text
  audio2.wav,Another reference text
  ```
- Place corresponding `.wav` files in `wav_files/`
- Continue to step 2

### 2. Generate STT Transcriptions

**Set API keys:**
```bash
export OPENAI_API_KEY="your-key"
export GEMINI_API_KEY="your-key"
```

**Run the STT generation script:**
```bash
# Generate STT results using OpenAI only
python app/services/audio/utils/generate_stt_csv.py --provider openai

# Generate STT results using Gemini only
python app/services/audio/utils/generate_stt_csv.py --provider gemini

# Generate STT results using both providers (recommended)
python app/services/audio/utils/generate_stt_csv.py --provider both
```

**Important:** The script will:
- ✅ **Preserve existing columns** like `wav_file`, `ground_truth`, or any custom columns
- ✅ **Append new provider columns** (`openai_stt_text`, `gemini_stt_text`)
- ✅ **Update existing CSV** if it exists, or create new one from WAV files
- ✅ **Maintain existing data** - only adds/updates STT provider columns

Results will be saved to `app/services/audio/stt_results.csv`

### 3. Add Ground Truth (if not done in step 1)

If you started with Option A, **manually add a `ground_truth` column** to the CSV with reference transcriptions:

```csv
wav_file,openai_stt_text,gemini_stt_text,ground_truth
audio1.wav,OpenAI transcription,Gemini transcription,Correct reference text
audio2.wav,Another OpenAI text,Another Gemini text,Another reference text
```

### 4. Calculate WER (Word Error Rate)

Once you have ground truth (from step 1 or 3), calculate WER metrics:

```bash
# Use default input/output paths
python app/services/audio/utils/calculate_wer.py

# Or specify custom paths
python app/services/audio/utils/calculate_wer.py --input stt_results.csv --output wer_results.csv
```

The script calculates:
- **Strict WER**: Exact word matching
- **Lenient WER**: Ignores vowel variations, nuqta differences, etc. (optimized for Indic languages)
- **Error breakdown**: Substitutions, deletions, insertions, semantic errors

Results will be saved to `app/services/audio/wer_results.csv`

## CSV Format Reference

**Initial CSV with Ground Truth** (Option B in step 1):
```csv
wav_file,ground_truth
audio1.wav,Reference transcription
```

**After STT Generation** (step 2):
```csv
wav_file,ground_truth,openai_stt_text,gemini_stt_text
audio1.wav,Reference text,OpenAI transcription,Gemini transcription
```

**WER Results CSV** (after step 4):
```csv
wav_file,openai_stt_text,gemini_stt_text,ground_truth,wer_strict_openai,wer_lenient_openai,strict_sub_openai,...
audio1.wav,OpenAI text,Gemini text,Reference text,0.1234,0.0876,2,1,0,0,1,1,0,0,...
```

## Notes

- The WER calculation script supports Hindi/Indic language-specific normalizations
- Lenient mode is useful for evaluating ASR systems on Indic languages where vowel and diacritic variations are common
- You can run WER calculation with only one provider's data (just include `openai_stt_text` OR `gemini_stt_text` column)
