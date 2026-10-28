from .base import BaseImportAdapter


class EpicImportAdapter(BaseImportAdapter):
    def normalize(self, raw_data: dict) -> dict:
        # TODO: map Epic claim payload to normalized keys
        # Placeholder pass-through
        return raw_data
