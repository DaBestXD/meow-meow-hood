import argparse
import ast
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from robinhood.async_robinhood_class import ASYNC_PATH
from robinhood.core import CORE_PATH
from robinhood.sync_robinhood_class import SYNC_PATH

logger = logging.getLogger(__name__)


def configure_logger() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)


@dataclass
class FunctionType:
    raw_func_name: str
    func_name: str
    func_type: Literal["Private", "Public"]


IGNORE_FUNC_LIST = [
    "__enter__",
    "__exit__",
    "__aenter__",
    "__aexit__",
    "__init__",
    "close",
]
IGNORED_FILES: list[str] = [
    "__init__.py",
    "__pycache__",
    "_core_robinhood.py",
    "_http_async_client.py",
]


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-f ",
        "--files",
        type=str,
        nargs="*",
        default=[CORE_PATH],
        help="Accepts either files or directories as the input files",
    )
    parser.add_argument(
        "--target_files",
        type=str,
        nargs="+",
        default=[SYNC_PATH, ASYNC_PATH],
        help="Accepts multiple paths to files",
    )
    return parser.parse_args()


def check_file_for_function(
    file_path: Path,
    exported_funcs: list[str],
):
    f = open(file_path, "r")
    mod = ast.parse(f.read())
    set_funcs = set(exported_funcs)
    for i in ast.walk(mod):
        if not isinstance(i, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if i.name in IGNORE_FUNC_LIST:
            continue
        deco = [e.id for e in i.decorator_list if e.id == "overload"]
        if deco:
            continue
        normalized_name = "".join((c for c in i.name if c.isalnum()))
        try:
            set_funcs.remove(normalized_name)
        except KeyError:
            raise NotImplementedError(
                f"Missing {i.name}({i.lineno}) for {file_path.name}"
            )
    if set_funcs:
        for s in set_funcs:
            logger.warning("Function was not implemented: %s", s)
        raise RuntimeWarning("Not all functions were implemented")


def parse_file(file_path: Path) -> list[FunctionType]:
    f = open(file_path, "r")
    mod = ast.parse(f.read())
    functions: list[FunctionType] = []
    for i in ast.walk(mod):
        if not isinstance(i, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        deco = [e.id for e in i.decorator_list if e.id == "overload"]
        if deco:
            continue
        doc_string = ast.get_docstring(i)
        if not doc_string:
            continue
        doc_string = doc_string.lower()
        func_type = None
        if "[private]" in doc_string:
            func_type = "Private"
        if "[public]" in doc_string:
            func_type = "Public"
        normalized_name = "".join(c for c in i.name if c.isalnum())
        if not func_type:
            raise RuntimeError(
                f"No private/public marker was for {i.name}({i.lineno})"
            )
        obj = FunctionType(i.name, normalized_name, func_type)
        if obj.func_type == "Public":
            logger.debug(
                "Exporting %s from %s",
                obj.raw_func_name,
                file_path.name,
            )
        functions.append(obj)
    f.close()
    return functions


def parse_dir(
    dir_path: Path,
    ignored_files: list[str] = IGNORED_FILES,
) -> list[Path]:
    files: list[Path] = []
    for f in os.scandir(dir_path):
        if f.name in ignored_files:
            continue
        files.append(dir_path / Path(f.name))
    return files


def parse_file_path(file_path: Path) -> list[FunctionType]:
    if file_path.is_dir():
        dir_paths = parse_dir(file_path)
        exported_funcs: list[FunctionType] = []
        for f in dir_paths:
            exported_funcs.extend(parse_file(f))
        return exported_funcs
    if file_path.is_file():
        exported_funcs = parse_file(file_path)
        return exported_funcs
    raise RuntimeError("unexpected file was provided")


def implementation_checker_func():
    cmd_args = get_args()
    paths: list[str] = cmd_args.files
    exported_funcs: list[str] = []
    if not paths:
        raise RuntimeError("file path was none")
    if len(paths) > 1:
        for i in paths:
            exported_funcs.extend(
                [
                    f.func_name
                    for f in parse_file_path(Path(i))
                    if f.func_type == "Public"
                ]
            )
    else:
        file = Path(paths[0])
        exported_funcs.extend(
            [
                f.func_name
                for f in parse_file_path(Path(file))
                if f.func_type == "Public"
            ]
        )
    target_files: list[Path] = [Path(f) for f in cmd_args.target_files]
    for i in target_files:
        check_file_for_function(i, exported_funcs)
        logger.info("%s has full implementation", i.name)


def main() -> None:
    configure_logger()
    implementation_checker_func()


if __name__ == "__main__":
    main()
