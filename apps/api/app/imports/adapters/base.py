from abc import ABC, abstractmethod


class BaseImportAdapter(ABC):
    """Every import adapter must convert
    external data into Atlas's internal format.
    """

    @abstractmethod
    def normalize(self, data):
        pass
