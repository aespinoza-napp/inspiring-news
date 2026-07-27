from abc import ABC, abstractmethod
from typing import Any


class BaseProcessor(ABC):

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def process(self, text: str) -> Any:
        """Execute the processor."""