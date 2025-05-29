import os
import csv
import logging
import time
from datetime import datetime
from typing import List
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import typer
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s"
)

cli = typer.Typer(help=__doc__)

HEADERS = {
    "accept": "application/json",
    "X-API-KEY": "ApiKey No3x47A5qoIGhm0kVKjQ77dhCqEdWRIQZlEPzzzh7i8", # First start session with seed API key
    "Content-Type": "application/json",
}

HARYANA_ASSISTANT_ID = 'asst_fz7oIQ2goRLfrP1mWceBcjje'

PAYLOAD = {
    "project_id": 1,
    "assistant_id": HARYANA_ASSISTANT_ID
}

ENDPOINT = "http://0.0.0.0:8000/api/v1/threads/sync"

@dataclass
class BenchItem:
    question: str
    answer: str
    duration: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_estimate_usd: float
    model: str

def estimate_cost(
    model: str, prompt_tokens: int, completion_tokens: int
) -> float:
    usd_per_1m = {
        "gpt-4o": {"input": 2.00, "cached_input": 1.25, "output": 10.00},
        # Extend with more models as needed: https://platform.openai.com/docs/pricing
    }

    pricing = usd_per_1m.get(model.lower())
    if not pricing:
        logging.warning(f"No pricing found for model '{model}'. Returning cost = 0.")
        return 0.0

    # We don't care about cached_input for now, this just to be mindful of upper bound cost to run benchmark
    input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
    output_cost = (completion_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost


def output_csv(items: List[BenchItem]):
    filename = f"bench_results_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
    file_exists = os.path.exists(filename)
    with open(filename, "a") as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(["question", "answer", "duration", "prompt_tokens", "completion_tokens", "total_tokens", "cost_estimate_usd", "model"])
        for item in items:
            writer.writerow([item.question, item.answer, item.duration, item.prompt_tokens, item.completion_tokens, item.total_tokens, item.cost_estimate_usd, item.model])

    return filename

def send_request(prompt: str, i: int, total: int) -> BenchItem:
    local_payload = {**PAYLOAD, "question": prompt}

    start = time.perf_counter()
    response = requests.post(ENDPOINT, headers=HEADERS, json=local_payload)
    end = time.perf_counter()
    duration = end - start

    if response.status_code == 200:
        result = response.json()['data']
        return BenchItem(
            question=prompt,
            answer=result['message'],
            duration=duration,
            prompt_tokens=result['prompt_tokens'],
            completion_tokens=result['completion_tokens'],
            total_tokens=result['total_tokens'],
            cost_estimate_usd=estimate_cost(result['model'], result['prompt_tokens'], result['completion_tokens']),
            model=result['model']
        )
    else:
        typer.echo(f"[{i+1}/{total}] FAILED - Status: {response.status_code}")
        raise Exception(f"Request failed with status code {response.status_code}")

@cli.command()
def assistants(
    count: int = typer.Option(None, help="Number of queries to process. If not set, will process all CSV rows."),
    workers: int = typer.Option(1, help="Number of workers to use for processing queries.")
):
    """
    Runs Glific test queries on Kunji OpenAI Assistant to measure latency and cost.

    How to run the benchmark: in backend/ run `uv run ai-cli bench assistants --count 4 --workers 1`

    Note that increasing the number of workers beyond 1 can impact accuracy of duration.
    """
    csv_file_path = os.path.join(
        os.path.dirname(__file__),
        "data", "glific_kunji_test_queries.csv"
    )
    results = []
    with open(csv_file_path, 'r') as file:
        csv_reader = csv.DictReader(file)
        csv_data = list(csv_reader)

        if count:
            csv_data = csv_data[:count]

        typer.echo(f"Total queries: {len(csv_data)}")

        # dedupe csv_data by row['prompt_text']
        seen_prompts = set()
        csv_data = [
            row for row in csv_data if row['prompt_text'] not in seen_prompts and not seen_prompts.add(row['prompt_text'])
        ]

        typer.echo(f"Total deduped queries: {len(csv_data)}")
        total = len(csv_data)

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(send_request, row['prompt_text'], i, total): row
                for i, row in enumerate(csv_data)
            }

            for future in tqdm(as_completed(futures), total=total):
                result = future.result()
                if result:
                    results.append(result)

    avg_duration = sum(item.duration for item in results) / len(results)
    total_prompt = sum(item.prompt_tokens for item in results)
    total_completion = sum(item.completion_tokens for item in results)
    total_duration = sum(item.duration for item in results)
    model = results[0].model if results else "unknown"

    total_cost = estimate_cost(model, total_prompt, total_completion)

    filename = output_csv(results)
    typer.echo(f"Results saved to {filename}")

    typer.echo(f"\nMean duration: {avg_duration:.3f}s over {total} runs.")
    typer.echo(f"Total duration: {total_duration:.3f}s")
    typer.echo(f"Total tokens used: prompt={total_prompt}, completion={total_completion}")
    typer.echo(f"Estimated cost for {total} runs on {model}: ${total_cost:.6f}")
