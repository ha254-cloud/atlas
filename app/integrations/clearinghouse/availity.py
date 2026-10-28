from ..base import IntegrationBase


class AvailityIntegration(IntegrationBase):
    def __init__(self, config):
        self.config = config

    def connect(self):
        pass

    def fetch_claims(self):
        return []
