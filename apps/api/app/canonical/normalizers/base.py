from abc import ABC, abstractmethod
from typing import Any

from app.canonical.claim import CanonicalClaim


class BaseNormalizer(ABC):
    """
    Every data-source normalizer maps its raw input into CanonicalClaim.
    The pipeline only ever sees CanonicalClaim — never raw vendor data.
    """

    @abstractmethod
    def normalize(self, raw: Any) -> CanonicalClaim: ...
