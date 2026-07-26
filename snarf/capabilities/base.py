from abc import ABC, abstractmethod


class Capability(ABC):
    name: str

    @property
    @abstractmethod
    def available(self) -> bool:
        ...
