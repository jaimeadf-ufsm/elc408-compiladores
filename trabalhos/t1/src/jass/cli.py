from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import ast, codegen
from .analyzer import analyze
from .errors import JassError, format_diagnostic
from .parser import parse, tokenize
from .transform import build_ast

EXIT_OK = 0
EXIT_USAGE = 64
EXIT_COMPILE = 65

EMIT_STAGES = ["tokens", "parse", "ast", "check", "yaml"]
DEFAULT_EMIT = EMIT_STAGES[-1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jass",
        description="Transpile jass automations to Home Assistant YAML.",
    )
    parser.add_argument(
        "files",
        nargs="+",
        type=Path,
        metavar="FILE",
        help="one or more .jass source files",
    )
    parser.add_argument(
        "--emit",
        choices=EMIT_STAGES,
        default=DEFAULT_EMIT,
        help=f"intermediate representation to print (default: {DEFAULT_EMIT})",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        metavar="OUT",
        help="write result to a file instead of stdout",
    )
    
    return parser


def compile_source(source: str, emit: str) -> tuple[str | None, list[JassError]]:
    try:
        if emit == "tokens":
            lines = [f"{token.type:<11} {str(token)!r}" for token in tokenize(source)]
        
            return "\n".join(lines), []
        
        if emit == "parse":
            tree, errors = parse(source)
        
            return (tree.pretty().rstrip() if tree is not None else None), list(errors)
        
        if emit == "ast":
            tree, errors = parse(source)
        
            if tree is None:
                return None, list(errors)
        
            return ast.dump(build_ast(tree)), list(errors)
        
        if emit == "check":
            tree, errors = parse(source)
        
            if tree is None:
                return None, list(errors)
        
            semantic_errors = analyze(build_ast(tree))
        
            return ("ok" if not semantic_errors else None), list(semantic_errors)
        
        if emit == "yaml":
            tree, errors = parse(source)
        
            if tree is None:
                return None, list(errors)
        
            program = build_ast(tree)
            semantic_errors = analyze(program)
        
            if semantic_errors:
                return None, list(semantic_errors)
            
            return codegen.dump(program), []
    
    except JassError as error:
        return None, [error]
    
    raise ValueError(f"unknown emit stage: {emit}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    outputs: list[str] = []
    had_error = False
    
    for path in args.files:
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"jass: cannot read {path}: {exc}", file=sys.stderr)
            return EXIT_USAGE

        output, errors = compile_source(source, args.emit)
        
        for error in errors:
            print(format_diagnostic(error, source, str(path)), file=sys.stderr)
        
        if errors:
            had_error = True
        
        if output is not None:
            outputs.append(output)

    if had_error:
        return EXIT_COMPILE

    result = "\n".join(outputs)
    
    if args.output is not None:
        args.output.write_text(result, encoding="utf-8")
    else:
        print(result)

    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
