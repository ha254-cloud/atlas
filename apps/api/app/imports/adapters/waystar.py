from .base import BaseImportAdapter


class WaystarImportAdapter(BaseImportAdapter):
    def normalize(self, raw_data: dict) -> dict:
        # TODO: map Waystar payload
        return raw_data
