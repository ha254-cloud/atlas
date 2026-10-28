import csv

from .base import BaseImportAdapter


class CSVImportAdapter(BaseImportAdapter):
    def __init__(self, column_map: dict[str, str] | None = None):
        self.column_map = column_map or {}

    def normalize(self, file_path: str) -> list[dict]:

        claims = []

        with open(file_path, newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)

            for row in reader:
                claims.append(row)

        return claims
