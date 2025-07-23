import csv
import logging

logger = logging.getLogger(__name__)


class BaseCSVProcessor:
    def __init__(self, input_file, output_file):
        self.input_file = input_file
        self.output_file = output_file

    def load_csv(self):
        with open(self.input_file, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def save_output(self, headers, rows):
        with open(self.output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
