import argparse
import json
import re
from os import PathLike
from pathlib import Path
from typing import Any

"""
I should have made this at the beginning of the project
Convert a json response into a python dataclass
"""


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--text", type=str)
    parser.add_argument(
        "-d",
        "--directory",
        type=str,
        default=str(Path("./").resolve()),
    )
    parser.add_argument(
        "-ti",
        "--title",
        type=str,
        default="dataclass.py",
    )
    return parser.parse_args()


def parse_dict(json_dict: dict[str, Any]) -> list[str]:
    return_val: list[str] = []
    for k, v in json_dict.items():
        try:
            v = float(v)
        except (ValueError, TypeError):
            pass
        return_val.append(f"\t{k}: {type(v).__name__}\n")
    return return_val


def json_payload_to_dataclass(
    json_payload: dict[str, Any] | str,
    class_title: str,
    file_dir: PathLike[str] | Path,
    write_to_file: bool = True,
) -> str:
    """
    For json_payload either use the raw json str
    or a python repr of the json payload
    """
    if isinstance(json_payload, str):
        json_payload = json.loads(json_payload.replace("'", '"'))
    if not isinstance(json_payload, dict):
        raise ValueError("json_payload must be dictionary")
    ftext = str(json_payload)
    # Thank you random stackoverflow question
    # https://stackoverflow.com/questions/39491420/python-jsonexpecting-property-name-enclosed-in-double-quotes
    p = re.compile("(?<!\\\\)'")
    ftext = p.sub('"', ftext)
    if not class_title.endswith(".py"):
        file_title = class_title + ".py"
    else:
        file_title = class_title
    dir = file_dir / Path(file_title)
    header = f"@dataclass\nclass {class_title}:\n"
    body = parse_dict(json_payload)
    text_body = "".join(body)
    if write_to_file:
        with open(dir, "a") as f:
            f.write(header)
            f.writelines(body)
    return header + text_body


def main() -> None:
    cmd_args = args()
    json_payload_to_dataclass(
        cmd_args.text,
        cmd_args.title,
        cmd_args.directory,
    )


if __name__ == "__main__":
    main()
