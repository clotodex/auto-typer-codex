#!/usr/bin/env python3

"""
Given a python file, this script finds all ranges of line nummbers of function signatures (excluding the function body) using ast
"""

import argparse
import ast
import io
import os
import sys
import tokenize
from collections import namedtuple
from enum import Enum
from typing import Optional

import openai
from termcolor import colored

USE_STREAM_FEATURE = True
MAX_TOKENS_DEFAULT = 64

Typedness = Enum("Typedness", "fully no_args no_return")
Typedness.colorstr = lambda self: colored(
    str(self.name), "green" if self == Typedness.fully else "red"
)

TypedFunctionRange = namedtuple(
    "TypedFunctionRange", ["typedness", "start", "end", "node"]
)


def find_first_import(file_path: str) -> Optional[int]:
    """
    Returns the line number of the first import statement in the file.
    If there are no import statements, returns None
    """
    with open(file_path) as f:
        source = f.read()

    tree = ast.parse(source, file_path)

    # finds first line with an import statement
    first_import = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            first_import = node.lineno
            break

    return first_import


def get_typed_function_ranges(file_path: str):
    """
    Returns a boolean list. For every function range, tests if it is fully typed using ast.
    Gets the line number where the function signature starts (def ...)
    and the line number where the signature ends (...:)
    Uses ast and tokenize to find only lines of the function definition (no empty lines or comment lines)
    """
    with open(file_path) as f:
        source = f.read()

    tree = ast.parse(source, file_path)

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef):

            start = node.lineno
            end = node.body[0].lineno - 1
            # going through tokenlist in reverse skipping all newlines, comments, etc and stopping when finding ':'
            fundef_str = "".join(source.splitlines(keepends=True)[start - 1 : end])
            print(fundef_str)
            for tokeninfo in reversed(
                list(tokenize.tokenize(io.BytesIO(fundef_str.encode("utf-8")).readline))
            ):
                # finds irrelevant trailing lines and adjusts 'end'
                if tokeninfo.exact_type == tokenize.COLON:
                    break
                elif tokeninfo.type == tokenize.COMMENT:
                    # comments also are parsed as newline so we wont change 'end' here
                    pass
                elif tokeninfo.type == tokenize.NL:
                    end -= 1
                elif tokeninfo.type == tokenize.STRING:
                    print(
                        colored(
                            "WARNING parsing docstring - this is weird and should be handled by AST normally - please report",
                            "red",
                        )
                    )
                    end -= len(tokeninfo.string.splitlines())
                elif tokeninfo.type == tokenize.NEWLINE:
                    # this is the newline directly after the colon
                    pass
                elif tokeninfo.type == tokenize.ENDMARKER:
                    # we dont care about this
                    pass
                else:
                    print(
                        f"found sth else: {tokeninfo.exact_type} - {tokeninfo.string}"
                    )

            yield TypedFunctionRange(
                get_function_typedness(node, tree),
                start,
                end,
                node,
            )


def get_function_typedness(function_node, tree):
    """
    Returns a Typedness enum indicating the type of the function.
    No args - if at least one argument does not have a type annotation
    No return - if all args are annotated but return statement exists but no type annotation.
    Fully typed - if all arguments have a type annotation and the return type has one.
    """
    if not all_args_have_type(function_node, tree):
        return Typedness.no_args

    if has_return_statement(function_node, tree) and not has_return_type(
        function_node, tree
    ):
        return Typedness.no_return
    return Typedness.fully


def has_return_type(function_node, tree):
    """
    Returns true if the function has a return type annotation (function_node.returns).
    """
    return function_node.returns is not None


def has_return_statement(function_node, tree):
    """
    Returns true if the function body has a return or yield statement.
    """
    if function_node.end_lineno is None:
        print(colored("WARNING: function body is probably empty", "red"))
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Return) or isinstance(node, ast.Yield):
            # checks if line number is in bounds of the function body
            if function_node.body[0].lineno <= node.lineno <= function_node.end_lineno:
                return True
    return False


def all_args_have_type(function_node: ast.FunctionDef, tree: ast.AST) -> bool:
    """
    Returns true if all arguments have a type annotation. (i.e. arg.annotation)
    """
    for arg in function_node.args.args:
        if not arg.annotation:
            return False
    return True


def print_function_range_and_def(path, function_range: TypedFunctionRange):
    """
    Prints a function definition in a nice format (typed if it has type annotations).
    def fun(var):
    def fun(var: type):
    def fun(var: type) -> ret:
    """
    # oneliner that prints filename and range (or just the line if start and end are the same
    print(
        function_range.typedness.colorstr()
        + " ~ "
        + os.path.basename(path)
        + ": "
        + (
            str(function_range.start) + "-" + str(function_range.end)
            if function_range.start != function_range.end
            else str(function_range.start)
        )
    )
    function_node = function_range.node
    print(
        "def "
        + function_node.name
        + "("
        + ", ".join(
            [
                # not working: arg.arg + ((": " + str(arg.annotation)) if arg.annotation is not None else colored(": MISSING", "red"))
                # again, but arg.annotation.id if Name object and arg.annotation.attr if Attribute object
                arg.arg
                + ": "
                + (
                    colored("MISSING", "red")
                    if arg.annotation is None
                    else ast.unparse(arg.annotation)
                )
                for arg in function_node.args.args
            ]
        )
        + ")"
        + (
            # if no_return prints red MISSING
            " -> " + ast.unparse(function_node.returns)
            if function_node.returns
            else (
                " -> " + colored("MISSING", "red")
                if function_range.typedness == Typedness.no_return
                else ""
            )
        )
    )


def subscript_type_to_string(subscript: ast.Subscript) -> str:
    """
    Returns a string representation of a subscript.
    For example, if the subscript is Optional[int] it returns "Optional[int]".
    """
    return ast.unparse(subscript)


def prep_function_def_from_node(function_node):
    """
    Returns a string representation of the function definition in this format:
        def functionname(firstarg:
    """
    return "def " + function_node.name + "(" + function_node.args.args[0].arg + ":"


def prep_function_def_from_node_for_return(function_node):
    """
    Returns a string representation of the function definition with an empty return type
    """
    return "def " + function_node.name + "(" + ast.unparse(function_node.args) + ") ->"


def prep_file(content, function_range, prep_function_def, first_import_line):
    """
    Add from typing import * on top of the first line of the imports
    Cuts the function_range from the file content
    Splits the content at that place
    The top split is appended to the bottom split with a new line
    The prepped function def is appended as well
    The resulting combination is returned as string
    """
    lines = content.splitlines(keepends=True)
    typing_import = ["from typing import *\n"]
    if first_import_line is None:
        lines = typing_import + lines
    else:
        assert first_import_line < function_range.start
        lines = (
            lines[: first_import_line - 1]
            + typing_import
            + lines[first_import_line - 1 :]
        )
    cut_lines = lines[function_range.end + 1 :] + ["\n"] + lines[: function_range.start]
    cut_lines.append(prep_function_def)
    return "".join(cut_lines)


def shorten_file_by_removing_comments(content):
    """
    Removes all lines with line comments or block comments from the file content, so that the ast parser does not get confused.
    """
    lines = content.splitlines(keepends=True)
    delete = False
    for line_num, line in enumerate(lines):
        # if the line starts with a comment, remove the line
        if line.strip().startswith("#"):
            lines[line_num] = ""
        # if the line starts with a block comment, remove the line
        if line.strip().startswith('"""') or line.strip().startswith("'''"):
            delete = not delete
            lines[line_num] = ""
        if delete:
            lines[line_num] = ""

    lines = [line for line in lines if line.strip() != ""]
    return "".join(lines)


def complete(prompt: str) -> str:
    """
    Autocompletes a prompt using OpenAI's CODEX API
    Returns the completion string (including \n)
    """
    response = openai.Completion.create(
        engine="davinci-codex",
        prompt=prompt,
        best_of=1,
        temperature=0.5,
        max_tokens=48,
        stream=False,
        stop=["\n"],
    )
    completion = response["choices"][0]["text"]
    return completion


def auto_typing(path, inplace=False, naming_format="{filename}_typed.{ext}"):
    with open(path) as f:
        content = f.read()

    first_import_line = find_first_import(path)

    lines = content.splitlines(keepends=True)
    offset = 0

    for function_range in get_typed_function_ranges(path):
        print_function_range_and_def(path, function_range)
        if function_range.typedness not in [Typedness.no_return, Typedness.no_args]:
            print(colored("skip", "grey"))
            continue
        prep_function_def = None
        if function_range.typedness == Typedness.no_args:
            prep_function_def = prep_function_def_from_node(function_range.node)
        elif function_range.typedness == Typedness.no_return:
            prep_function_def = prep_function_def_from_node_for_return(
                function_range.node
            )
        else:
            print(colored(f"unhandled typedness {function_node.typedness}", "red"))
            continue

        print(prep_function_def, end="")
        prepped = prep_file(
            content, function_range, prep_function_def, first_import_line
        )

        completion = None
        try:
            completion = try_complete_or_shorten(prepped)
        except openai.error.InvalidRequestError:
            print(colored("Failed to find completion.", "red"))
            print(colored("Using original function.", "red"))
            print()

        if completion is not None:
            print(colored(completion, "green"))
            print()
            completion = prep_function_def + completion + "\n"
            completion_lines = completion.splitlines(keepends=True)
            completion_line_count = len(completion_lines)

            # splits the content in lines and splices the completion instead of the function_range
            start_line = function_range.start - 1 + offset
            end_line = function_range.end + offset
            lines = lines[:start_line] + completion_lines + lines[end_line:]

            offset += completion_line_count - (
                function_range.end + 1 - function_range.start
            )

        print()

    # autocompletes typing import
    try:
        import_completion = try_complete_or_shorten(content + "\nfrom typing import")
    except openai.error.InvalidRequestError as e:
        print(colored(f"Failed to create completion {e}.", "red"))
        print(colored("Using from typing import * instead", "red"))
        import_completion = " *"

    # if typing import exists replace it
    tree = ast.parse(content, path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            print(ast.dump(node))
            name = node.names[0].name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            name = node.module.split(".")[0]
        else:
            continue
        if name == "typing":
            first_import_line = node.lineno
            # removing import line
            lines = lines[: first_import_line - 1] + lines[first_import_line:]
            break

    if first_import_line is None:
        lines = ["from typing import", import_completion, "\n"] + lines
    else:
        lines = (
            lines[: first_import_line - 1]
            + ["from typing import", import_completion, "\n"]
            + lines[first_import_line - 1 :]
        )

    # write to file depending args
    if inplace:
        with open(path, "w") as f:
            f.write("".join(lines))
    else:
        # apply format only to the file, not the folder
        filename = os.path.basename(path)
        # applies format (only uses ext if it exists)
        splits = filename.split(".")
        new_filename = naming_format.format(
            filename=splits[0], ext=splits[1] if len(splits) > 1 else ""
        )
        new_path = path.replace(filename, new_filename)
        with open(new_path, "w") as f:
            f.write("".join(lines))


def try_complete_or_shorten(prompt):
    """
    Tries to complete the prompt using OpenAI's CODEX API
    If that fails, it shortens the prompt by using `shorten_file_by_removing_comments` and tries again
    """
    try:
        return complete(prompt)
    except openai.error.InvalidRequestError as e:
        print(colored(f"Completion > max tokens {e}", "red"))
        return complete(shorten_file_by_removing_comments(prompt))


def main():

    # read from ENV (if exists)
    openai.organization = (
        os.environ["OPENAI_ORG"] if "OPENAI_ORG" in os.environ else None
    )
    if "OPENAI_KEY" in os.environ:
        openai.api_key = os.environ["OPENAI_KEY"]
    else:
        # check if stored in "api.key" file
        try:
            with open(os.path.join(os.path.dirname(__file__), "api.key")) as f:
                openai.api_key = f.read().strip()
        except FileNotFoundError:
            print(
                colored("OPENAI_KEY not found in environment or in file api.key", "red")
            )
            exit()

    parser = argparse.ArgumentParser(description="Auto-type a python file")
    parser.add_argument(
        "path", type=str, help="path to python file or a folder of python files"
    )
    parser.add_argument(
        "--inplace",
        action="store_true",
        help="edit the file in-place instead of creating a new file",
    )
    parser.add_argument(
        "--format",
        type=str,
        default="{filename}_typed.{ext}",
        help="format for the new file (default: {filename}_typed.{ext})",
    )
    args = parser.parse_args()

    if os.path.isdir(args.path):
        for root, _, files in os.walk(args.path):
            for file in files:
                if file.endswith(".py"):
                    path = os.path.join(root, file)
                    auto_typing(path, args.inplace, args.format)
    else:
        auto_typing(args.path, args.inplace, args.format)


if __name__ == "__main__":
    main()
