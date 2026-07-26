from abc import ABC, abstractmethod


class Specialist(ABC):
    name: str
    domain: str

    @abstractmethod
    def handle(self, task: str, context: dict) -> str:
        ...


REGISTRY: dict[str, Specialist] = {}


def register(specialist: Specialist) -> None:
    REGISTRY[specialist.name] = specialist
