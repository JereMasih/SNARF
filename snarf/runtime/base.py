from abc import ABC, abstractmethod


class Channel(ABC):
    name: str

    @abstractmethod
    def receive(self) -> str:
        ...

    @abstractmethod
    def send(self, message: str) -> None:
        ...
