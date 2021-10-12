import ast
import os
import sys
from typing import *

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
import auto_typer
from auto_typer import Typedness


def test_extract_function_defintion_with_typedness():
    content = """
import math

def mul(x: float, y: float) -> float:
    return x + y

def sub(
        x: int,
        y: int
    ):
    return x + y

def add(x, y):
    return x + y

add(3,4)
add(3.2,4)
add(3.2,4.7)
    """
    tree = ast.parse(content)
    ranges = list(auto_typer.get_typed_function_ranges(content))
    assert len(ranges) == 3
    assert ranges[0].start == 4
    assert ranges[0].end == 4
    assert ranges[0].node.name == "mul"
    assert ranges[0].typedness == Typedness.fully
    assert ranges[1].start == 7
    assert ranges[1].end == 10
    assert ranges[1].node.name == "sub"
    assert ranges[1].typedness == Typedness.no_return
    assert ranges[2].start == 13
    assert ranges[2].end == 13
    assert ranges[2].node.name == "add"
    assert ranges[2].typedness == Typedness.no_args
