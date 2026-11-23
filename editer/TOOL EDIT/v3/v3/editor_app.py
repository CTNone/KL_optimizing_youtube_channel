"""Compatibility entry point for older Tool Edit launchers."""


def main():
    from audio_editor import main as audio_editor_main
    audio_editor_main()


if __name__ == "__main__":
    main()
