import ast
import copy
import subprocess
from pathlib import Path
from typing import Literal

from robinhood.async_robinhood_class import ASYNC_PATH
from robinhood.sync_robinhood_class import SYNC_PATH
from scripts.blah_typing import AstFunctionType
from scripts.implementation_checker import get_args, implementation_checker_func


def _generate_return_stmt(
    func_node: AstFunctionType,
    call_args: list[ast.expr],
    call_keywords: list[ast.keyword],
    func_type: Literal["async_robinhood_class", "sync_robinhood_class"],
) -> ast.stmt:
    if func_type == "async_robinhood_class":
        return ast.Return(
            value=ast.Await(
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="self", ctx=ast.Load()),
                        attr=func_node.name,
                        ctx=ast.Load(),
                    ),
                    args=call_args,
                    keywords=call_keywords,
                )
            )
        )
    if func_type == "sync_robinhood_class":
        return ast.Return(
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id="self", ctx=ast.Load()),
                    attr="_run",
                    ctx=ast.Load(),
                ),
                args=[
                    ast.Call(
                        func=ast.Attribute(
                            value=ast.Name(id="self", ctx=ast.Load()),
                            attr=func_node.name,
                            ctx=ast.Load(),
                        ),
                        args=call_args,
                        keywords=call_keywords,
                    )
                ],
                keywords=[],
            )
        )


def create_function(
    func_node: AstFunctionType,
    func_type: Literal["async_robinhood_class", "sync_robinhood_class"],
) -> AstFunctionType:
    # The only functions that are being passed into function have already
    # been checked for a docstring, so we can safely assume that the first
    # stmt of the body will be a constant expr with a string value
    func_node.body[0].value.value = func_node.body[0].value.value.replace(  # pyright: ignore
        f"\n{func_node.body[0].col_offset * ' '}[Public]", ""
    )
    call_args: list[ast.expr] = [
        ast.Name(id=arg.arg, ctx=ast.Load())
        for arg in func_node.args.posonlyargs + func_node.args.args
        if arg.arg != "self"
    ]
    call_keywords = [
        ast.keyword(
            arg=arg.arg,
            value=ast.Name(id=arg.arg, ctx=ast.Load()),
        )
        for arg in func_node.args.kwonlyargs
    ]
    if func_type == "async_robinhood_class":
        func_node.body = [func_node.body[0]]
        func_node.body.append(
            _generate_return_stmt(
                func_node, call_args, call_keywords, func_type
            )
        )
        func_node.name = func_node.name.removeprefix("_")
        return func_node
    if func_type == "sync_robinhood_class":
        func_node.body = [func_node.body[0]]
        func_node.body.append(
            _generate_return_stmt(
                func_node, call_args, call_keywords, func_type
            )
        )
        func_node.name = func_node.name.removeprefix("_")
        return ast.FunctionDef(**func_node.__dict__)


def _get_class_def(file_path: Path) -> ast.ClassDef:
    mod = ast.parse(file_path.read_text())
    for node in ast.walk(mod):
        if isinstance(node, ast.ClassDef):
            return node
    raise ValueError("Class def not found")


def main() -> None:
    """
    This is terrible clean this up later 😭
    """

    cmd_args = get_args()
    public_classes = [ASYNC_PATH, SYNC_PATH]
    # Need to change this to dict mapping of file path and missing files,
    # This will break if impl is only in one public class and not both
    missing_funcs = set(
        implementation_checker_func(cmd_args.files, cmd_args.target_files)
    )
    class_mod: ast.ClassDef | None = None
    for c in public_classes:
        class_mod = _get_class_def(c)
        if c.name == "async_robinhood_class.py":
            for f in missing_funcs:
                for o in f.overload_impl:
                    o.name = o.name.removeprefix("_")
                    class_mod.body.append(o)
                    print(f"Adding {o.name}")
                class_mod.body.append(
                    create_function(
                        copy.deepcopy(f.node), "async_robinhood_class"
                    )
                )
                print(f"Adding {f}")
            raw_source = ast.parse(c.read_text())
            for index, n in enumerate(raw_source.body):
                if isinstance(n, ast.ClassDef):
                    raw_source.body[index] = class_mod
            c.write_text(ast.unparse(raw_source))
        if c.name == "sync_robinhood_class.py":
            for f in missing_funcs:
                for o in f.overload_impl:
                    o.name = o.name.removeprefix("_")
                    sync_ver = ast.FunctionDef(**o.__dict__)
                    ast.fix_missing_locations(sync_ver)
                    class_mod.body.append(sync_ver)
                class_mod.body.append(
                    create_function(
                        copy.deepcopy(f.node), "sync_robinhood_class"
                    )
                )
            raw_source = ast.parse(c.read_text())
            for index, n in enumerate(raw_source.body):
                if isinstance(n, ast.ClassDef):
                    raw_source.body[index] = class_mod
            c.write_text(ast.unparse(raw_source))
    subprocess.run(["ruff", "format"])
    subprocess.run(["ruff", "check", "--fix"])
    implementation_checker_func(cmd_args.files, cmd_args.target_files)


if __name__ == "__main__":
    main()
