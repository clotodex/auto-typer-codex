# Auto-type

A command-line tool to automatically type annotate functions in python files and projects.  
It uses [OpenAI's CODEX API](https://openai.com/blog/openai-codex/) to autocomplete the type information.

This tool was also written with the help of CODEX, using [vim_codex](https://github.com/tom-doerr/vim_codex).

## Usage

### OpenAI API key

You can set the API key in the environment variable `OPENAI_KEY`.
Or you can put it in a file called `api.key` in the same directory as this file.
You can find your key [here](https://beta.openai.com/account/api-keys).

### Running the script

```bash
auto_typer.py [-h] [--inplace] [--format FORMAT] [--pretend] [--max-tries MAX_TRIES] path
```

### Options

#### --inplace

The default behavior is to create a new file, the original file will not be changed.

```bash
auto-typer.py --inplace your_file.py
```

#### --format

The default format is `{filename}_typed.{ext}`, which will create a new file like `your_file_typed.py`

```bash
auto-typer.py --format "{filename}_typed.{ext}" your_file.py
```

#### --pretend

With this argument, the script will not write to any file.

#### --max-tries

CODEX sometimes misses a few types, so by default it will rerun itself `3` times or less if nothing is changing.
This can be changed with this option. `-1` makes it run as long as it is changing the file (This **should** not lead to an infinite loop).

## Examples

```bash
# Auto-type your_file.py inplace
auto-typer.py --inplace your_file.py

# Auto-type all files in path/to/your/project
# Stores the typed version alongside the project files with the _typed suffix
auto-typer.py --format "{filename}_typed.{ext}" path/to/your/project
```

## How it works

The tool uses the OpenAI CODEX API to generate the type information.

This is the rough process for every file:
- Parse the file into an AST
- Find all function definitions
- For every function definition:
    - Prepare the file for use with CODEX
        - Extract start of function definition
        - Split and reorder the file, so that the function definition is at the bottom (thanks to https://github.com/tom-doerr/vim_codex for the idea)
        - Add a `from typing import *` import statement
    - Generate the rest of the definition, now with types using the OpenAI CODEX API
    - Replace the function definition with the completion and write to the file (inplace or new file)

## Features

- typing completion for function arguments
- typing completion for function return types
- preserving of newlines and comments below function definition
- optional inplace editing of a python file
- optional formatting of the new file
- adds typing import (but very rudimentary)
- run until fully typed
- pretend mode
- more specific typing import (from typing import Generator, Union, \*)

## Future Ideas

If you require one of the listed features, please create an issue to show that there is interest for it.

- Add further support for type annotations in
	- variable assignments (`x: int = 1`)
	- definitions (`class Foo(object):`)
	- methods (`class Foo(object):\n    def __init__(self, x: int):`)
	- special cases (nested functions, lambdas, etc)
- help CODEX with hard cases of typing like generators
- varify typing - assert all variables are still there and defaults are added
- code optimizations (RAM or speed)
- silent mode
- keep comments of parameters alive using the `tokenize` library
- optimize type completions e.g. with a comment before function defintion with typing help or encouranging sentence like "perfectly typed function"
- option for overriding the format file (currently default)

## Known problems

- default arguments (`def fun(x=3)`) are not guaranteed to be preserved
- the type completion is sometimes not optimal
- completion > max\_tokens, even with shortening the file be removing comments -> cut the file or replace some methods with just their definitions
- max number of tokens is currently fixed to 128 - might need to be extended for long signatures (can maybe be done automatically, otherwise as cli param)
- auto-generated import is often not accurate -> default is now to always add `from typing import *`, which is not nice

## Contribution

This is a very early version of this tool and contributions are always welcome, especially work on known problems or on further tests.

Please try the tool for yourself and open an [issue](https://github.com/clotodex/auto-typer-codex/issues) if you have a suggestion or found a bug.
Open an [pull request](https://github.com/clotodex/auto-typer-codex/pulls) if you want to contribute.

### Tests

- [x] find all functions and their typedness
- [x] mutliline function definition
- [ ] type args
- [ ] type return
- [ ] commented lines before function body
- [ ] doccomment before function body
- [ ] empty lines before function body
- [ ] default args
- [ ] file shortening
- [ ] inplace
- [ ] outfile formatting

The tests are written using [pytest](http://doc.pytest.org/en/latest/).

```bash
pip install pytest
pytest
```

## Alternatives

For a static type inferrer you can also check [MonkeyType](https://github.com/Instagram/MonkeyType).

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.
