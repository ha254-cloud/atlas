from .base import BaseImportAdapter


class AthenaImportAdapter(BaseImportAdapter):
    def normalize(self, raw_data: dict) -> dict:
        # TODO: map Athena payload
        return raw_data
