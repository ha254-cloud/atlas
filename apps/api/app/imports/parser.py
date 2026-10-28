import csv
from collections.abc import Iterator


class CSVParser:
    def parse(self, filepath: str) -> Iterator[dict]:
        with open(filepath, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            yield from reader

    def count_rows(self, filepath: str) -> int:
        """Count data rows (excluding the header) without loading them into memory."""
        with open(filepath, newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            total = sum(1 for _ in reader)
        return max(total - 1, 0)

    def get_headers(self, filepath: str) -> list[str]:
        """Read just the header row, without loading any data rows."""
        with open(filepath, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            return list(reader.fieldnames or [])

    def parse_batches(self, filepath: str, batch_size: int = 1000) -> Iterator[list[dict]]:
        batch: list[dict] = []

        for row in self.parse(filepath):
            batch.append(row)
            if len(batch) >= batch_size:
                yield batch
                batch = []

        if batch:
            yield batch
