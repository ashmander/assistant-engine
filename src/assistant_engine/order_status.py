import argparse
import tomllib
from pathlib import Path

import ollama

__all__ = ["get_order_status"]

BASE_DIR = Path(__file__).parent
SETTINGS_PATH = BASE_DIR / "settings_order_status.toml"
ORDERS_DB_PATH = BASE_DIR / "data" / "orders.txt"

with SETTINGS_PATH.open("rb") as settings_file:
    SETTINGS = tomllib.load(settings_file)


def parse_args() -> argparse.Namespace:
    """Parse command-line input."""
    parser = argparse.ArgumentParser()
    parser.add_argument("tracking_number", help="Numero de seguimiento del pedido")
    return parser.parse_args()


def main(args: argparse.Namespace) -> None:
    print(get_order_status(args.tracking_number))


def get_order_status(tracking_number: str) -> str:
    """Send a request to the local Ollama Llama 3 8B model."""
    response = ollama.chat(
        model=SETTINGS["general"]["model"],
        messages=_assemble_chat_messages(tracking_number),
        options={"temperature": SETTINGS["general"]["temperature"]},
    )
    return response["message"]["content"]


def _assemble_chat_messages(tracking_number: str) -> list[dict]:
    """Combine the role prompt and instruction prompt into a chat message list."""
    orders_database = ORDERS_DB_PATH.read_text("utf-8")
    instruction_prompt = SETTINGS["prompts"]["instruction_prompt"].format(
        orders_database=orders_database,
        tracking_number=tracking_number,
    )
    messages = [
        {"role": "system", "content": SETTINGS["prompts"]["role_prompt"]},
        {"role": "user", "content": instruction_prompt},
    ]
    return messages


if __name__ == "__main__":
    main(parse_args())
