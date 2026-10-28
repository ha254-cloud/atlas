from ..base import IntegrationBase


class AthenaIntegration(IntegrationBase):
    def __init__(self, config):
        self.config = config

    def connect(self):
        # TODO: implement Athenahealth connection
        pass

    def fetch_claims(self):
        return []
