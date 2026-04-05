"""
coral/cli.py  –  Command-line interface for the Coral language
"""

import argparse
import sys
import os
import tempfile

from .transpiler import transpile
from .typechecker import CoralTypeError, CoralSyntaxError


def cmd_run(args):
    """coral run <file.coral>  – transpile and execute"""
    path = args.file
    if not os.path.isfile(path):
        print(f"coral: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    with open(path, 'r') as f:
        source = f.read()

    try:
        python_src = transpile(source, filename=os.path.basename(path))
    except (CoralTypeError, CoralSyntaxError) as e:
        print(f"{e}\n", file=sys.stderr)
        sys.exit(1)

    if args.verbose:
        _print_separator('Transpiled Python')
        print(python_src)
        _print_separator('Output')

    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.py', delete=False
    ) as tmp:
        tmp.write(python_src)
        tmp_path = tmp.name

    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=False
        )
        sys.exit(result.returncode)
    finally:
        os.unlink(tmp_path)


def cmd_compile(args):
    """coral compile <file.coral> [-o output.py]  – transpile only"""
    path = args.file
    if not os.path.isfile(path):
        print(f"coral: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    with open(path, 'r') as f:
        source = f.read()

    try:
        python_src = transpile(source, filename=os.path.basename(path))
    except (CoralTypeError, CoralSyntaxError) as e:
        print(f"{e}\n", file=sys.stderr)
        sys.exit(1)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(python_src)
        print(f"coral: wrote {args.output}")
    else:
        # Default: same name with .py extension
        base = os.path.splitext(path)[0]
        out_path = base + '.py'
        with open(out_path, 'w') as f:
            f.write(python_src)
        print(f"coral: wrote {out_path}")


def cmd_check(args):
    """coral check <file.coral>  – parse and show transpiled output only"""
    path = args.file
    if not os.path.isfile(path):
        print(f"coral: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    with open(path, 'r') as f:
        source = f.read()

    try:
        python_src = transpile(source, filename=os.path.basename(path))
    except (CoralTypeError, CoralSyntaxError) as e:
        print(f"{e}\n", file=sys.stderr)
        sys.exit(1)
    _print_separator(f'Transpiled: {os.path.basename(path)}')
    print(python_src)
    _print_separator()


def _print_separator(label: str = ''):
    width = 60
    if label:
        pad = max(0, width - len(label) - 2)
        left = pad // 2
        right = pad - left
        print(f"{'─' * left} {label} {'─' * right}")
    else:
        print('─' * width)


def main():
    parser = argparse.ArgumentParser(
        prog='coral',
        description='Coral language – a typed, structured Python variant'
    )
    parser.add_argument(
        '--version', action='version', version=f'Coral {__import__("importlib.metadata", fromlist=["version"]).version("coral-lang")}'
    )

    subparsers = parser.add_subparsers(dest='command', required=True)

    # coral run
    p_run = subparsers.add_parser('run', help='Transpile and run a .coral file')
    p_run.add_argument('file', help='Path to .coral source file')
    p_run.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Print transpiled Python before running'
    )
    p_run.set_defaults(func=cmd_run)

    # coral compile
    p_compile = subparsers.add_parser('compile', help='Transpile a .coral file to Python')
    p_compile.add_argument('file', help='Path to .coral source file')
    p_compile.add_argument(
        '-o', '--output',
        metavar='FILE',
        help='Output .py file path (default: same name as input)'
    )
    p_compile.set_defaults(func=cmd_compile)

    # coral check
    p_check = subparsers.add_parser('check', help='Show transpiled Python without running')
    p_check.add_argument('file', help='Path to .coral source file')
    p_check.set_defaults(func=cmd_check)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
