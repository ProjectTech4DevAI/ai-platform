import os
import csv
import logging
import time
from datetime import datetime
from typing import List, Optional, Dict, Protocol
from dataclasses import dataclass
from pathlib import Path

import requests
import typer
from tqdm import tqdm
from langfuse import Langfuse

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s"
)

cli = typer.Typer(help=__doc__)

langfuse = Langfuse()

HEADERS = {
    "accept": "application/json",
    "X-API-KEY": os.getenv("LOCAL_CREDENTIALS_API_KEY"),
    "Content-Type": "application/json",
}

PAYLOAD = {
    "project_id": 1,
}


@dataclass
class EvalItem:
    question: str
    actual_answer: str
    chunks: List[Dict[str, any]]  # List of {"score": float, "text": str}
    duration: float
    model: str
    trace_id: Optional[str] = None
    contextual_precision: Optional[float] = None
    contextual_recall: Optional[float] = None
    hallucination_score: Optional[float] = None
    context_utilization: Optional[float] = None
    answer_relevance: Optional[float] = None
    chunk_ranking: Optional[float] = None
    avg_chunk_score: Optional[float] = None


@dataclass
class EvalDatasetConfig:
    model: str
    vector_store_ids: List[str]
    instructions: str
    filename: str
    query_column: str


def load_instructions(filename: str) -> str:
    """Load instructions from data directory"""
    with open(os.path.join(os.path.dirname(__file__), "..", "data", filename), "r") as file:
        return file.read()


EVAL_SERVICES = {
    "responses": {
        "endpoint": "http://localhost:8000/api/v1/responses/sync",
        "datasets": {
            "kunji": EvalDatasetConfig(
                model="gpt-4o",
                vector_store_ids=["vs_QtyGjYxyM0OUKd6y7Z1pnfKU"],
                instructions=load_instructions("kunji_instructions.txt"),
                filename="glific_kunji_test_queries.csv",
                query_column="prompt_text",
            ),
            "sneha": EvalDatasetConfig(
                model="gpt-4o-mini",
                vector_store_ids=["vs_67a9de6638888191beb37c06f84e1a88"],
                instructions=load_instructions("sneha_instructions.txt"),
                filename="sneha_goldens.csv",
                query_column="Question",
            ),
        },
    },
}


# ===== CHUNK-BASED EVALUATION FUNCTIONS =====


def evaluate_contextual_precision(question: str, chunks: List[str]) -> float:
    """Measure how many retrieved chunks are actually relevant to the question"""
    if not chunks:
        return 0.0

    relevant_chunks = 0
    total_chunks = len(chunks)

    question_keywords = set(question.lower().split())
    # Remove common stop words
    stop_words = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "is",
        "are",
        "was",
        "were",
    }
    question_keywords -= stop_words

    if not question_keywords:
        return 0.0

    for chunk in chunks:
        chunk_keywords = set(chunk.lower().split())
        chunk_keywords -= stop_words

        # Calculate overlap
        overlap = len(question_keywords.intersection(chunk_keywords))
        relevance_threshold = max(
            1, len(question_keywords) * 0.1
        )  # At least 1 word or 10% overlap

        if overlap >= relevance_threshold:
            relevant_chunks += 1

    return relevant_chunks / total_chunks


def evaluate_contextual_recall(question: str, answer: str, chunks: List[str]) -> float:
    """Measure if the answer uses information from the retrieved chunks"""
    if not chunks or not answer:
        return 0.0

    answer_words = set(answer.lower().split())
    chunk_info_used = 0
    total_chunk_info = 0

    for chunk in chunks:
        chunk_words = set(chunk.lower().split())
        total_chunk_info += len(chunk_words)

        # Count how much chunk information appears in the answer
        used_words = len(chunk_words.intersection(answer_words))
        chunk_info_used += used_words

    return chunk_info_used / total_chunk_info if total_chunk_info > 0 else 0.0


def evaluate_hallucination(answer: str, chunks: List[str]) -> float:
    """Detect if answer contains information not in the retrieved chunks"""
    if not answer or not chunks:
        return 0.0

    # Combine all chunks
    all_context = " ".join(chunks).lower()
    answer_sentences = [s.strip() for s in answer.split(".") if s.strip()]

    if not answer_sentences:
        return 1.0

    hallucinated_sentences = 0
    total_sentences = len(answer_sentences)

    context_words = set(all_context.split())

    for sentence in answer_sentences:
        sentence_words = set(sentence.lower().split())

        # If sentence has significant content not in context, might be hallucination
        if sentence_words:
            overlap = len(sentence_words.intersection(context_words))
            overlap_ratio = overlap / len(sentence_words)

            if overlap_ratio < 0.3:  # Less than 30% overlap
                hallucinated_sentences += 1

    # Return inverse (higher = less hallucination)
    return 1.0 - (hallucinated_sentences / total_sentences)


def evaluate_context_utilization(answer: str, chunks: List[str]) -> float:
    """Measure how much of the retrieved context is actually used in the answer"""
    if not chunks or not answer:
        return 0.0

    all_context = " ".join(chunks)
    context_words = set(all_context.lower().split())
    answer_words = set(answer.lower().split())

    if not context_words:
        return 0.0

    used_context = len(context_words.intersection(answer_words))
    return used_context / len(context_words)


def evaluate_answer_relevance(question: str, answer: str) -> float:
    """Measure if the answer is relevant to the question asked"""
    if not question or not answer:
        return 0.0

    question_words = set(question.lower().split())
    answer_words = set(answer.lower().split())

    # Remove common stop words for better relevance detection
    stop_words = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "is",
        "are",
        "was",
        "were",
    }
    question_words -= stop_words
    answer_words -= stop_words

    if not question_words:
        return 0.0

    overlap = len(question_words.intersection(answer_words))
    return overlap / len(question_words)


def evaluate_chunk_ranking_with_scores(
    question: str, chunks: List[str], scores: List[float]
) -> float:
    """Evaluate chunk ranking using both content relevance AND retrieval scores"""
    if len(chunks) != len(scores) or len(chunks) < 2:
        return 1.0

    # Check if retrieval scores are in descending order
    score_ranking_quality = sum(
        1 for i in range(len(scores) - 1) if scores[i] >= scores[i + 1]
    ) / (len(scores) - 1)

    # Also check content-based relevance ranking
    question_words = set(question.lower().split())
    content_relevances = []

    for chunk in chunks:
        chunk_words = set(chunk.lower().split())
        overlap = len(question_words.intersection(chunk_words))
        relevance = overlap / len(question_words) if question_words else 0
        content_relevances.append(relevance)

    if len(content_relevances) < 2:
        return score_ranking_quality

    content_ranking_quality = sum(
        1
        for i in range(len(content_relevances) - 1)
        if content_relevances[i] >= content_relevances[i + 1]
    ) / (len(content_relevances) - 1)

    # Combine both measures (weight retrieval scores more heavily)
    return 0.7 * score_ranking_quality + 0.3 * content_ranking_quality


# ===== REQUEST HANDLING =====


def send_eval_request(
    prompt: str,
    i: int,
    total: int,
    endpoint: str,
    build_payload: callable,
    run_langfuse_eval: bool = True,
) -> EvalItem:
    """Send request and run chunk-based evaluations"""

    trace = None
    if run_langfuse_eval:
        trace = langfuse.trace(
            name="rag_evaluation",
            input={"question": prompt},
            tags=["evaluation", "rag_metrics"],
        )

    local_payload = build_payload(prompt)
    
    # Add trace_id to payload if we have one
    if trace:
        local_payload["trace_id"] = trace.id

    start = time.perf_counter()
    response = requests.post(endpoint, headers=HEADERS, json=local_payload)
    end = time.perf_counter()
    duration = end - start

    if response.status_code == 200:
        result = response.json()
        result_data = result["data"]
        answer = result_data["message"]

        chunk_objects = result_data.get("chunks", [])
        chunks = [chunk["text"] for chunk in chunk_objects]
        chunk_scores = [chunk["score"] for chunk in chunk_objects]

        model = result_data["diagnostics"]["model"]
        avg_chunk_score = sum(chunk_scores) / len(chunk_scores) if chunk_scores else 0.0

        contextual_precision = evaluate_contextual_precision(prompt, chunks)
        contextual_recall = evaluate_contextual_recall(prompt, answer, chunks)
        hallucination_score = evaluate_hallucination(answer, chunks)
        context_utilization = evaluate_context_utilization(answer, chunks)
        answer_relevance = evaluate_answer_relevance(prompt, answer)
        chunk_ranking = evaluate_chunk_ranking_with_scores(prompt, chunks, chunk_scores)

        eval_item = EvalItem(
            question=prompt,
            actual_answer=answer,
            chunks=chunk_objects,
            duration=duration,
            model=model,
            trace_id=trace.id if trace else None,
            contextual_precision=contextual_precision,
            contextual_recall=contextual_recall,
            hallucination_score=hallucination_score,
            context_utilization=context_utilization,
            answer_relevance=answer_relevance,
            chunk_ranking=chunk_ranking,
            avg_chunk_score=avg_chunk_score,
        )

        # Add custom evaluation scores to trace
        if trace and run_langfuse_eval:
            for metric_name, score in [
                ("contextual_precision", contextual_precision),
                ("contextual_recall", contextual_recall),
                ("hallucination_resistance", hallucination_score),
                ("context_utilization", context_utilization),
                ("answer_relevance", answer_relevance),
                ("chunk_ranking_quality", chunk_ranking),
            ]:
                langfuse.create_score(
                    trace_id=trace.id,
                    name=metric_name,
                    value=score,
                    data_type="NUMERIC",
                    comment=f"Custom {metric_name} evaluation based on retrieved chunks",
                )

        return eval_item
    else:
        typer.echo(f"[{i+1}/{total}] FAILED - Status: {response.status_code}")
        typer.echo(response.text)
        raise Exception(f"Request failed with status code {response.status_code}")


# ===== UTILITY FUNCTIONS =====


class DatasetConfig(Protocol):
    filename: str
    query_column: str


def load_and_dedupe_csv(
    dataset_config: DatasetConfig, count: int | None = None
) -> List[dict]:
    """Load and deduplicate CSV data for evaluation."""
    csv_file_path = os.path.join(
        os.path.dirname(__file__), "..", "data", dataset_config.filename
    )
    with open(csv_file_path, "r") as file:
        csv_reader = csv.DictReader(file)
        csv_data = list(csv_reader)

        if count:
            csv_data = csv_data[:count]

        # dedupe csv_data by query value
        seen_prompts = set()
        csv_data = [
            row
            for row in csv_data
            if row[dataset_config.query_column] not in seen_prompts
            and not seen_prompts.add(row[dataset_config.query_column])
        ]

        return csv_data


def output_eval_csv(items: List[EvalItem], filename: Optional[str] = None) -> str:
    """Output evaluation results to CSV"""
    if filename is None:
        filename = f"eval_results_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"

    with open(filename, "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "question",
                "actual_answer",
                "duration",
                "model",
                "num_chunks",
                "avg_chunk_score",
                "trace_id",
                "contextual_precision",
                "contextual_recall",
                "hallucination_score",
                "context_utilization",
                "answer_relevance",
                "chunk_ranking",
            ]
        )
        for item in items:
            writer.writerow(
                [
                    item.question,
                    item.actual_answer,
                    item.duration,
                    item.model,
                    len(item.chunks),
                    item.avg_chunk_score,
                    item.trace_id,
                    item.contextual_precision,
                    item.contextual_recall,
                    item.hallucination_score,
                    item.context_utilization,
                    item.answer_relevance,
                    item.chunk_ranking,
                ]
            )
    return filename


def calculate_eval_statistics(results: List[EvalItem]) -> dict:
    """Calculate evaluation statistics"""
    if not results:
        return {}

    total_runs = len(results)
    avg_duration = sum(item.duration for item in results) / total_runs
    avg_contextual_precision = (
        sum(item.contextual_precision or 0 for item in results) / total_runs
    )
    avg_contextual_recall = (
        sum(item.contextual_recall or 0 for item in results) / total_runs
    )
    avg_hallucination_score = (
        sum(item.hallucination_score or 0 for item in results) / total_runs
    )
    avg_context_utilization = (
        sum(item.context_utilization or 0 for item in results) / total_runs
    )
    avg_answer_relevance = (
        sum(item.answer_relevance or 0 for item in results) / total_runs
    )
    avg_chunk_ranking = sum(item.chunk_ranking or 0 for item in results) / total_runs
    avg_chunk_score = sum(item.avg_chunk_score or 0 for item in results) / total_runs

    return {
        "total_runs": total_runs,
        "avg_duration": avg_duration,
        "avg_contextual_precision": avg_contextual_precision,
        "avg_contextual_recall": avg_contextual_recall,
        "avg_hallucination_score": avg_hallucination_score,
        "avg_context_utilization": avg_context_utilization,
        "avg_answer_relevance": avg_answer_relevance,
        "avg_chunk_ranking": avg_chunk_ranking,
        "avg_chunk_score": avg_chunk_score,
        "model": results[0].model if results else "N/A",
    }


def print_eval_statistics(stats: dict):
    """Print evaluation statistics"""
    typer.echo(f"\n=== Evaluation Results ===")
    typer.echo(f"Total runs: {stats['total_runs']}")
    typer.echo(f"Model: {stats['model']}")
    typer.echo(f"Average duration: {stats['avg_duration']:.3f}s")
    typer.echo(f"Average chunk retrieval score: {stats['avg_chunk_score']:.3f}")
    typer.echo(f"\n=== RAG Quality Metrics ===")
    typer.echo(f"Contextual Precision: {stats['avg_contextual_precision']:.3f}")
    typer.echo(f"Contextual Recall: {stats['avg_contextual_recall']:.3f}")
    typer.echo(f"Hallucination Resistance: {stats['avg_hallucination_score']:.3f}")
    typer.echo(f"Context Utilization: {stats['avg_context_utilization']:.3f}")
    typer.echo(f"Answer Relevance: {stats['avg_answer_relevance']:.3f}")
    typer.echo(f"Chunk Ranking Quality: {stats['avg_chunk_ranking']:.3f}")


# ===== CLI COMMANDS =====


@cli.command()
def responses(
    count: Optional[int] = typer.Option(
        None,
        help="Number of queries to process. If not set, will process all CSV rows.",
    ),
    dataset: str = typer.Option(
        "kunji", help="Dataset to use for evaluation (kunji or sneha)."
    ),
    langfuse_eval: bool = typer.Option(
        True, help="Whether to send evaluation results to Langfuse"
    ),
    output_file: Optional[str] = typer.Option(None, help="Path to output CSV file"),
):
    """
    Run evaluation on the responses endpoint using chunk-based metrics.

    This command:
    1. Loads dataset with test queries
    2. Calls your responses API for each question
    3. Runs custom evaluation metrics (contextual_precision, contextual_recall, hallucination, etc.)
    4. Optionally sends results to Langfuse for tracking
    5. Outputs results to CSV file

    Example usage:
        uv run ai-cli eval responses --dataset kunji --count 100
        uv run ai-cli eval responses --dataset sneha --langfuse-eval false
    """
    dataset_config = EVAL_SERVICES["responses"]["datasets"][dataset]
    csv_data = load_and_dedupe_csv(dataset_config, count)

    typer.echo(f"Running evaluation on {len(csv_data)} queries from {dataset} dataset")
    total = len(csv_data)

    def build_responses_payload(prompt: str) -> dict:
        return {
            **PAYLOAD,
            "question": prompt,
            "model": dataset_config.model,
            "vector_store_ids": dataset_config.vector_store_ids,
            "instructions": dataset_config.instructions,
        }

    results = []
    for i, row in enumerate(tqdm(csv_data, total=total)):
        try:
            result = send_eval_request(
                row[dataset_config.query_column],
                i,
                total,
                EVAL_SERVICES["responses"]["endpoint"],
                build_responses_payload,
                run_langfuse_eval=langfuse_eval,
            )
            if result:
                results.append(result)
        except Exception as e:
            typer.echo(f"Error processing query {i+1}: {e}")
            continue

    if not results:
        typer.echo("No successful evaluations completed.")
        return

    stats = calculate_eval_statistics(results)
    print_eval_statistics(stats)

    filename = output_eval_csv(results, output_file)
    typer.echo(f"\nResults saved to {filename}")

    if langfuse_eval:
        typer.echo(f"Evaluation traces and scores sent to Langfuse")

    if langfuse_eval:
        langfuse.flush()
