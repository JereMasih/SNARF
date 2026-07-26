from snarf.runtime.base import Channel


class TextChannel(Channel):
    name = "text"

    def receive(self) -> str:
        return input("Vos: ")

    def send(self, message: str) -> None:
        print(f"Snarf: {message}")
