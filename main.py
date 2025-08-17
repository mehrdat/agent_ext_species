import os
from src.app import demo

def main() -> None:
    """Launch the Gradio demo server."""
    demo.launch(server_name="0.0.0.0", server_port=int(os.getenv("PORT", 7860)))

if __name__ == "__main__":
    main()
