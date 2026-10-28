from abc import ABC, abstractmethod


class IntegrationBase(ABC):

    @abstractmethod
    def connect(self):
        raise NotImplementedError()

    @abstractmethod
    def fetch_claims(self):
        raise NotImplementedError()
