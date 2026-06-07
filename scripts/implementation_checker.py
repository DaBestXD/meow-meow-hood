import argparse
import ast
import logging
import os
from pathlib import Path
from typing import Literal

from robinhood.async_robinhood_class import ASYNC_PATH
from robinhood.core import CORE_PATH
from robinhood.sync_robinhood_class import SYNC_PATH
from scripts.blah_typing import AstFunctionType

logger = logging.getLogger(__name__)


def configure_logger(debug_level: int = logging.DEBUG) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.setLevel(debug_level)
    logger.addHandler(handler)


class FunctionType:
    def __init__(
        self,
        raw_func_name: str,
        func_name: str,
        func_type: Literal["Private", "Public"],
        func_origin: Path,
        node: AstFunctionType,
        func_missing_from: Path | None = None,
    ) -> None:
        self.raw_func_name = raw_func_name
        self.func_name = func_name
        self.func_type = func_type
        self.func_origin = func_origin
        self.func_missing_from = func_missing_from
        self.node = node
        self.overload_impl: list[AstFunctionType] = []

    def __str__(self) -> str:
        return f"{self.raw_func_name}({self.func_origin.name})"

    def __repr__(self) -> str:
        class_vars = [f"{k}={v}" for k, v in self.__dict__.items()]
        return f"{self.__class__.__name__}({', '.join(class_vars)})"


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
        if not isinstance(i, AstFunctionType):
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
        for k, v in set_funcs_names.items():
            set_funcs_names[k].func_missing_from = file_path
            logger.warning(
                "Missing implementation for %s %s(function origin: %s) ",
                file_path.name,
                v.raw_func_name,
                v.func_origin.name,
            )
    if not set_funcs_names:
        logger.info("%s has no missing implementations", file_path.name)
    return set_funcs_names


def parse_file_for_overloads(file_path: Path) -> list[AstFunctionType]:
    mod = ast.parse(file_path.read_text())
    overloaded_functions: list[AstFunctionType] = []
    for i in ast.walk(mod):
        if not isinstance(i, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        # Only overload is used as decorator, ast.Name check not needed
        if not [d for d in i.decorator_list if d.id == "overload"]:  # pyright: ignore
            continue
        overloaded_functions.append(i)
    return overloaded_functions


def parse_file(file_path: Path) -> list[FunctionType]:
    mod = ast.parse(file_path.read_text())
    functions: list[FunctionType] = []
    for i in ast.walk(mod):
        if not isinstance(i, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        deco: bool = False
        for d in i.decorator_list:
            if isinstance(d, ast.Name) and d.id == "overload":
                deco = True
                break
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
                f"No private/public marker was for {i.name}(lineno: {i.lineno})"
            )
        obj = FunctionType(
            i.name,
            normalized_name,
            func_type,
            file_path,
            i,
        )
        if obj.func_type == "Public":
            logger.debug(
                "Public %s from %s",
                obj.raw_func_name,
                file_path.name,
            )
        if not deco:
            functions.append(obj)
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
            funcs = parse_file(f)
            for i in funcs:
                for u in parse_file_for_overloads(f):
                    if i.raw_func_name == u.name:
                        i.overload_impl.append(u)
            exported_funcs.extend(funcs)
        return exported_funcs
    if file_path.is_file():
        exported_funcs = parse_file(file_path)
        return exported_funcs
    raise RuntimeError("unexpected file was provided")


def implementation_checker_func(files: list[str], target_files: list[str]):
    paths: list[str] = files
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
    path_target_files = [Path(f) for f in target_files]
    total_missing: list[FunctionType] = []
    for i in path_target_files:
        vals = check_file_for_function(i, exported_funcs)
        if vals:
            total_missing.append(*vals.values())
    return total_missing


if __name__ == "__main__":
    cmd_args = get_args()
    missing = implementation_checker_func(cmd_args.files, cmd_args.target_files)
    configure_logger(cmd_args.debug_level)
    if missing:
        raise RuntimeError(f"Missing impl for: {missing}")
    else:
        print("No missing implementations!")
