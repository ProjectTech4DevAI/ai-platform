import json
import difflib
import time
import logging
from typing import Set

import openai
from openai import OpenAI
from sklearn.metrics import matthews_corrcoef, accuracy_score, f1_score
from app.api.routes.fine_tuning import handle_openai_error


logger = logging.getLogger(__name__)


class ModelEvaluator:
    max_latency = 90
    retries = 3
    normalization_cutoff = 0.7

    def __init__(
        self,
        model_name: str,
        testing_file_id: str,
        system_prompt: str,
        client: OpenAI,
    ):
        self.model_name = model_name
        self.testing_file_id = testing_file_id
        self.system_instruction = system_prompt
        self.client = client

        self.allowed_labels: Set[str] = set()
        self.y_true: list[str] = []
        self.prompts: list[str] = []

        logger.info(f"ModelEvaluator initialized with model: {model_name}")

    def load_labels_and_prompts(self) -> None:
        """
        Loads labels and prompts directly from OpenAI NDJSON file content using the testing file ID.

        Example data format:
        {
            "messages": [
                {"role": "system", "content": "You are an assistant that is good at categorizing if what user is saying is a query or non-query"},
                {"role": "user", "content": "what is the colour of the apple"},
                {"role": "assistant", "content": "query"}
            ]
        }
        {
            "messages": [
                {"role": "system", "content": "You are an assistant that is good at categorizing if what user is saying is a query or non-query"},
                {"role": "user", "content": "i like apples"},
                {"role": "assistant", "content": "non-query"}
            ]
        }
        """
        logger.info(
            f"[load_labels_and_prompts] Loading labels and prompts from file ID: {self.testing_file_id}"
        )
        try:
            response = self.client.files.content(self.testing_file_id)
            file_bytes = response.read()
            lines = file_bytes.decode("utf-8").splitlines()

            for ln, line in enumerate(lines, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    msgs = obj.get("messages", [])
                    if not isinstance(msgs, list) or not msgs:
                        logger.error(
                            f"[load_labels_and_prompts] Line {ln}: 'messages' missing or invalid"
                        )
                        raise ValueError(f"Line {ln}: 'messages' missing or invalid")

                    user_msgs = [
                        m for m in msgs if m.get("role") == "user" and "content" in m
                    ]
                    model_msgs = [
                        m
                        for m in msgs
                        if m.get("role") == "assistant" and "content" in m
                    ]
                    if not user_msgs or not model_msgs:
                        logger.error(
                            f"[load_labels_and_prompts] Line {ln}: missing user or assistant message"
                        )
                        raise ValueError(
                            f"Line {ln}: missing user or assistant message"
                        )

                    prompt = user_msgs[0]["content"]
                    label = (model_msgs[0]["content"] or "").strip().lower()

                    self.prompts.append(prompt)
                    self.y_true.append(label)
                    self.allowed_labels.add(label)

                except Exception as e:
                    logger.error(
                        f"[load_labels_and_prompts] Error processing line {ln}: {str(e)}"
                    )
                    raise

            logger.info(
                f"[load_labels_and_prompts] Loaded {len(self.prompts)} prompts and {len(self.y_true)} labels."
            )

        except Exception as e:
            logger.error(
                f"[load_labels_and_prompts] Failed to load file content: {str(e)}"
            )
            raise

    def normalize_prediction(self, text: str) -> str:
        logger.debug(f"[normalize_prediction] Normalizing prediction: {text}")
        t = (text or "").strip().lower()

        if t in self.allowed_labels:
            return t

        closest = difflib.get_close_matches(
            t, self.allowed_labels, n=1, cutoff=self.normalization_cutoff
        )
        if closest:
            return closest[0]

        logger.warning(
            f"[normalize_prediction] No close match found for '{t}'. Using default label '{next(iter(self.allowed_labels))}'."
        )
        return next(iter(self.allowed_labels))

    def generate_predictions(self) -> list[str]:
        logger.info(
            f"[generate_predictions] Generating predictions for {len(self.prompts)} prompts."
        )
        start_preds = time.time()
        predictions = []
        total_prompts = len(self.prompts)

        for idx, prompt in enumerate(self.prompts, 1):
            attempt = 0
            while attempt < self.retries:
                start_time = time.time()
                logger.info(
                    f"[generate_predictions] Processing prompt {idx}/{total_prompts} (Attempt {attempt + 1}/{self.retries})"
                )

                try:
                    response = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=[
                            {"role": "system", "content": self.system_instruction},
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0,
                        max_tokens=3,
                    )

                    elapsed_time = time.time() - start_time
                    if elapsed_time > self.max_latency:
                        logger.warning(
                            f"[generate_predictions] Timeout exceeded for prompt {idx}/{total_prompts}. Retrying..."
                        )
                        continue

                    raw = response.choices[0].message.content or ""
                    prediction = self.normalize_prediction(raw)
                    predictions.append(prediction)
                    break

                except openai.OpenAIError as e:
                    error_msg = handle_openai_error(e)
                    logger.error(
                        f"[generate_predictions] OpenAI API error at prompt {idx}/{total_prompts}: {error_msg}"
                    )
                    attempt += 1
                    if attempt == self.retries:
                        predictions.append("openai_error")
                        logger.error(
                            f"[generate_predictions] Maximum retries reached for prompt {idx}/{total_prompts}. Appending 'openai_error'."
                        )
                    else:
                        logger.info(
                            f"[generate_predictions] Retrying prompt {idx}/{total_prompts} after OpenAI error ({attempt}/{self.retries})."
                        )

        total_elapsed = time.time() - start_preds
        logger.info(
            f"[generate_predictions] Finished {total_prompts} prompts in {total_elapsed:.2f}s | Generated {len(predictions)} predictions."
        )
        return predictions

    def evaluate(self, y_pred: list[str]) -> dict:
        """Evaluate the predictions against the true labels."""
        logger.info(f"[evaluate] Starting evaluation with {len(y_pred)} predictions.")

        try:
            mcc_score = round(matthews_corrcoef(self.y_true, y_pred), 4)
            accuracy = round(accuracy_score(self.y_true, y_pred), 4)
            f1_query = round(
                f1_score(self.y_true, y_pred, pos_label="query", average="binary"), 4
            )

            logger.info(
                f"[evaluate] Evaluation completed. MCC: {mcc_score}, Accuracy: {accuracy}, F1 Query: {f1_query}"
            )

            return {
                "mcc": mcc_score,
                "accuracy": accuracy,
                "f1_query": f1_query,
            }
        except Exception as e:
            logger.error(f"[evaluate] Error during evaluation: {str(e)}")
            raise

    def run(self) -> dict:
        """Run the full evaluation process: load data, generate predictions, evaluate results."""
        try:
            self.load_labels_and_prompts()
            predictions = self.generate_predictions()
            evaluation_results = self.evaluate(predictions)
            logger.info("[evaluate] Model evaluation completed successfully.")
            return evaluation_results
        except Exception as e:
            logger.error(f"[evaluate] Error in running ModelEvaluator: {str(e)}")
            raise
