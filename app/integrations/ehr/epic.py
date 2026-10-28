from ..base import IntegrationBase


class EpicIntegration(IntegrationBase):
    def __init__(self, config):
        self.config = config

    def connect(self):
        # TODO: implement Epic FHIR/OAuth connection
        pass

    def fetch_claims(self):
        # TODO: implement fetching claims from Epic
        return []
