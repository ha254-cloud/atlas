from ..base import IntegrationBase


class WaystarIntegration(IntegrationBase):
    def __init__(self, config):
        self.config = config

    def connect(self):
        pass

    def fetch_claims(self):
        return []
