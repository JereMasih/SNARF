import sys

from dotenv import load_dotenv

load_dotenv()

from snarf.core.orchestrator import DEFAULT_USER_ID, Orchestrator
from snarf.runtime.text_channel import TextChannel
from snarf.runtime.voice_channel import VoiceChannel


def main():
    orchestrator = Orchestrator(user_id=DEFAULT_USER_ID)
    if "--voice" in sys.argv:
        channel = VoiceChannel()
        print("Snarf - walking skeleton (canal de voz). Ctrl+C para salir.\n")
    else:
        channel = TextChannel()
        print("Snarf - walking skeleton (canal de texto). Ctrl+C para salir.\n")
    while True:
        try:
            user_input = channel.receive()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_input.strip():
            continue
        try:
            result = orchestrator.handle(channel.name, user_input)
        except Exception as exc:
            channel.send(f"[error de capacidad, no se guardó en memoria] {exc}")
            continue
        # El canal de voz habla la versión breve (menos costo, menos espera);
        # el canal de texto muestra la respuesta completa.
        channel.send(result.speech if channel.name == "voice" else result.text)


if __name__ == "__main__":
    main()
