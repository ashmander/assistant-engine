import argparse
import tomllib
from pathlib import Path

import ollama

__all__ = ["get_return_guidance"]

BASE_DIR = Path(__file__).parent
SETTINGS_PATH = BASE_DIR / "settings_product_return.toml"
PRODUCTS_CATALOG_PATH = BASE_DIR / "data" / "products.txt"

with SETTINGS_PATH.open("rb") as settings_file:
    SETTINGS = tomllib.load(settings_file)


def parse_args() -> argparse.Namespace:
    """Parse command-line input."""
    parser = argparse.ArgumentParser()
    parser.add_argument("product_name", help="Nombre del producto que el cliente quiere devolver")
    return parser.parse_args()


def main(args: argparse.Namespace) -> None:
    print(get_return_guidance(args.product_name))


def get_return_guidance(product_name: str) -> str:
    """Send a request to the local Ollama Llama 3 8B model."""
    response = ollama.chat(
        model=SETTINGS["general"]["model"],
        messages=_assemble_chat_messages(product_name),
        options={"temperature": SETTINGS["general"]["temperature"]},
    )
    return response["message"]["content"]


def _assemble_chat_messages(product_name: str) -> list[dict]:
    """Combine the role prompt and instruction prompt into a chat message list."""
    products_catalog = PRODUCTS_CATALOG_PATH.read_text("utf-8")
    instruction_prompt = SETTINGS["prompts"]["instruction_prompt"].format(
        products_catalog=products_catalog,
        product_name=product_name,
    )
    messages = [
        {"role": "system", "content": SETTINGS["prompts"]["role_prompt"]},
        {"role": "user", "content": instruction_prompt},
    ]
    return messages


if __name__ == "__main__":
    main(parse_args())
