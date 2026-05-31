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


def configure_logger(debug_level: int = logging.DEBUG) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.setLevel(debug_level)
    logger.addHandler(handler)


@dataclass(frozen=True)
class FunctionType:
    raw_func_name: str
    func_name: str
    func_type: Literal["Private", "Public"]
    func_origin: str


IGNORE_FUNC_LIST: set[str] = {
    "__enter__",
    "__exit__",
    "__aenter__",
    "__aexit__",
    "__init__",
    "close",
}
IGNORED_FILES: set[str] = {
    "__init__.py",
    "__pycache__",
    "_core_robinhood.py",
    "_http_async_client.py",
}


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
    parser.add_argument(
        "--debug_level",
        type=int,
        default=logging.INFO,
        help="Accepted Values: (10: DEBUG), (20: INFO), (30: WARNING), (40: ERROR), (50: CRITICAL)",  # noqa: E501
    )
    return parser.parse_args()


def check_file_for_function(
    file_path: Path,
    exported_funcs: list[FunctionType],
):
    f = open(file_path, "r")
    mod = ast.parse(f.read())
    f.close()
    set_funcs_names = {f.func_name: f for f in exported_funcs}
    for i in ast.walk(mod):
        if not isinstance(i, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if i.name in IGNORE_FUNC_LIST:
            continue
        deco: bool = False
        for d in i.decorator_list:
            if isinstance(d, ast.Name) and d.id == "overload":
                deco = True
                break
        if deco:
            continue
        normalized_name = "".join((c for c in i.name if c.isalnum()))
        try:
            set_funcs_names.pop(normalized_name)
        except KeyError:
            raise NotImplementedError(
                f"Missing {i.name}({i.lineno}) for {file_path.name}"
            )
    if set_funcs_names:
        for _, v in set_funcs_names.items():
            logger.warning(
                "Missing implementation for %s %s(function origin: %s) ",
                file_path.name,
                v.raw_func_name,
                v.func_origin,
            )
        raise RuntimeWarning("Not all functions were implemented")
    logger.info("%s has no missing implementations", file_path.name)


def parse_file(file_path: Path) -> list[FunctionType]:
    f = open(file_path, "r")
    mod = ast.parse(f.read())
    functions: list[FunctionType] = []
    for i in ast.walk(mod):
        if not isinstance(i, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        deco: bool = False
        for d in i.decorator_list:
            if isinstance(d, ast.Name) and d.id == "overload":
                deco = True
                break
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
        obj = FunctionType(
            i.name,
            normalized_name,
            func_type,
            file_path.name,
        )
        if obj.func_type == "Public":
            logger.debug(
                "Public %s from %s",
                obj.raw_func_name,
                file_path.name,
            )
        functions.append(obj)
    f.close()
    return functions


def parse_dir(
    dir_path: Path,
    ignored_files: set[str] = IGNORED_FILES,
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
    configure_logger(cmd_args.debug_level)
    paths: list[str] = cmd_args.files
    exported_funcs: list[FunctionType] = []
    if not paths:
        raise RuntimeError("file path was none")
    if len(paths) > 1:
        for i in paths:
            exported_funcs.extend(
                [f for f in parse_file_path(Path(i)) if f.func_type == "Public"]
            )
    else:
        file = Path(paths[0])
        exported_funcs.extend(
            [f for f in parse_file_path(Path(file)) if f.func_type == "Public"]
        )
    target_files: list[Path] = [Path(f) for f in cmd_args.target_files]
    for i in target_files:
        check_file_for_function(i, exported_funcs)


if __name__ == "__main__":
    implementation_checker_func()
