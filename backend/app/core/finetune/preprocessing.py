import os
import json
import uuid
import tempfile
import logging
import pandas as pd
from sklearn.model_selection import train_test_split

logger = logging.getLogger(__name__)


class DataPreprocessor:
    system_message = {
        "role": "system",
        "content": "You are an assistant that is good at categorizing if what user is saying is a query or just small talk",
    }

    def __init__(self, document, storage, split_ratio: float):
        if not (0 < split_ratio < 1):
            logger.error(
                f"[DataPreprocessor] Rejected invalid split_ratio={split_ratio}"
            )
            raise ValueError(
                f"Invalid split ratio: {split_ratio}. Must be between 0 and 1"
            )

        self.document = document
        self.storage = storage
        self.split_ratio = split_ratio
        self.query_col = None
        self.label_col = None
        self.generated_files = []

    def _save_to_jsonl(self, data, filename):
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            for record in data:
                json.dump(record, f, ensure_ascii=False)
                f.write("\n")
        self.generated_files.append(file_path)
        return file_path

    def cleanup(self):
        for path in self.generated_files:
            if os.path.exists(path):
                os.remove(path)
        self.generated_files = []

    def _modify_data_format(self, data):
        modified_data = []
        for record in data:
            user_message = {"role": "user", "content": record[self.query_col]}
            assistant_message = {"role": "assistant", "content": record[self.label_col]}
            modified_record = {
                "messages": [self.system_message, user_message, assistant_message]
            }
            modified_data.append(modified_record)
        return modified_data

    def _load_dataframe(self):
        logger.info(f"Loading CSV from: {self.document.object_store_url}")
        f_obj = self.storage.stream(self.document.object_store_url)
        try:
            f_obj.name = self.document.fname
            df = pd.read_csv(f_obj)
            df.columns = [col.strip().lower() for col in df.columns]

            possible_query_columns = ["query", "question", "message"]
            self.query_col = next(
                (col for col in possible_query_columns if col in df.columns), None
            )
            self.label_col = "label" if "label" in df.columns else None

            if not self.query_col or not self.label_col:
                logger.error(
                    f"[DataPreprocessor] Dataset does not contai a 'label' column and one of: {possible_query_columns} "
                )
                raise ValueError(
                    f"CSV must contain a 'label' column and one of: {possible_query_columns}"
                )

            logger.info(
                f"[DataPreprocessor]Identified columns - query_col={self.query_col}, label_col={self.label_col}"
            )
            return df
        finally:
            f_obj.close()

    def process(self):
        logger.info("Starting data preprocessing")
        df = self._load_dataframe()

        train_data, test_data = train_test_split(
            df,
            test_size=1 - self.split_ratio,
            stratify=df[self.label_col],
            random_state=42,
        )

        logger.info(
            f"[DataPreprocessor]Data split complete: train_size={len(train_data)}, test_size={len(test_data)}"
        )

        train_dict = train_data.to_dict(orient="records")
        test_dict = test_data.to_dict(orient="records")

        train_jsonl = self._modify_data_format(train_dict)
        test_jsonl = self._modify_data_format(test_dict)

        train_file = (
            f"train_data_{int(self.split_ratio * 100)}_{uuid.uuid4().hex}.jsonl"
        )
        test_file = f"test_data_{int(self.split_ratio * 100)}_{uuid.uuid4().hex}.jsonl"

        train_path = self._save_to_jsonl(train_jsonl, train_file)
        test_path = self._save_to_jsonl(test_jsonl, test_file)

        return {"train_file": train_path, "test_file": test_path}
