"""
coral/typechecker.py  –  Compile-time type checker for Coral source.
"""

import re

# ── Type compatibility ─────────────────────────────────────────────────────

_LIT_INT   = re.compile(r'^-?\d+$')
_LIT_FLOAT = re.compile(r'^-?\d+\.\d+([eE][+-]?\d+)?$')
_LIT_STR   = re.compile(r'^".*"$|^\'.*\'$', re.DOTALL)
_LIT_BOOL  = re.compile(r'^(true|false)$')
_LIT_NULL  = re.compile(r'^null$')

_COMPAT = {
    'int':   [_LIT_INT],
    'float': [_LIT_FLOAT, _LIT_INT],
    'str':   [_LIT_STR],
    'char':  [_LIT_STR],
    'bool':  [_LIT_BOOL],
    'list':  [re.compile(r'^\[')],
    'dict':  [re.compile(r'^\{')],
    'set':   [re.compile(r'^\{')],
    'tuple': [re.compile(r'^\(')],
}

_TYPE_EXAMPLES = {
    'int':   'a whole number  e.g. 42',
    'float': 'a decimal number  e.g. 3.14',
    'str':   'a quoted string  e.g. "hello"',
    'char':  'a single-character string  e.g. "A"',
    'bool':  'true or false',
    'list':  'a list literal  e.g. [1, 2, 3]',
    'dict':  'a dict literal  e.g. {"key": 1}',
    'set':   'a set literal  e.g. {"a", "b"}',
    'tuple': 'a tuple literal  e.g. (1, 2)',
}


class CoralTypeError(Exception):
    def __init__(self, message, line_num=None, line_text=None, filename=None):
        self.line_num  = line_num
        self.line_text = line_text
        self.filename  = filename
        loc = ''
        if filename: loc += f'{filename}:'
        if line_num: loc += f'line {line_num}: '
        full = f'\nTypeError: {loc}{message}'
        if line_text:
            full += f'\n  → {line_text.strip()}'
        super().__init__(full)


# ── Pattern constants ──────────────────────────────────────────────────────

_PRIM    = r'(?:int|float|str|bool|char|void|tuple)'
_GEN     = r'(?:list|dict|set)(?:<[^>]+>)?'
_CUSTOM  = r'(?:[A-Z]\w*|\w+\.[A-Z]\w*)(?:<[^>]*>)?'
TYPE     = rf'(?:{_PRIM}|{_GEN}|{_CUSTOM})'
ACCESS   = r'(?:public|private|protected|static)'
MODS_OPT = rf'(?:(?:{ACCESS})\s+)*'

# Variable declaration:  [mods] TYPE name = value ;
_DECL_RE = re.compile(rf'^{MODS_OPT}({TYPE})\s+(\w+)\s*=\s*(.+?)\s*;?\s*$')

# Function/method signature:  [mods] TYPE name(...)  {
_FUNC_RE = re.compile(rf'^{MODS_OPT}({TYPE})\s+(\w+)\s*\([^)]*\)\s*\{{?\s*$')

# Single-line method:  [mods] TYPE name(...) { body }
_FUNC_INLINE_RE = re.compile(rf'^{MODS_OPT}({TYPE})\s+(\w+)\s*\([^)]*\)\s*\{{.+\}}\s*$')

# Control-flow openers (do NOT push a return type)
_CTRL_RE = re.compile(
    r'^(if|else|for|foreach|while|else\s+if)\s*[\(\{]'
    r'|^else\s*\{'
    r'|^class\s+'
    r'|^\}\s*else'
    r'|^\}\s*else\s+if'
)

# Return statement
_RETURN_RE = re.compile(r'^return\s+(.+?)\s*;?\s*$')


def _base_type(t: str) -> str:
    m = re.match(r'^(\w+)', t)
    return m.group(1) if m else t


def _infer_literal(value: str):
    """Return the Coral type name of a literal value, or None if not a literal."""
    v = value.strip()
    if _LIT_NULL.match(v):  return 'null'
    if _LIT_BOOL.match(v):  return 'bool'
    if _LIT_FLOAT.match(v): return 'float'
    if _LIT_INT.match(v):   return 'int'
    if _LIT_STR.match(v):   return 'str'
    if v.startswith('['):   return 'list'
    if v.startswith('('):   return 'tuple'
    if v.startswith('{'):   return 'dict_or_set'
    return None


def _check_compat(declared: str, value: str, line_num, line_text, filename, context='assign'):
    base     = _base_type(declared)
    inferred = _infer_literal(value)

    if inferred is None or inferred == 'null':
        return  # can't check non-literals; null is always valid

    if base not in _COMPAT:
        return  # custom/unknown type — skip

    patterns = _COMPAT[base]
    v = value.strip()

    if any(p.match(v) for p in patterns):
        return  # valid

    if base in ('dict', 'set') and inferred == 'dict_or_set':
        return  # ambiguous literal, both are valid

    expected = _TYPE_EXAMPLES.get(base, base)

    if context == 'assign':
        msg = (
            f'cannot assign {inferred} literal to variable of type `{declared}`.\n'
            f'  Expected : {expected}\n'
            f'  Got      : {v}'
        )
    else:
        msg = (
            f'return type mismatch — function declares `{declared}` '
            f'but returns a {inferred} literal.\n'
            f'  Expected : {expected}\n'
            f'  Got      : {v}'
        )

    raise CoralTypeError(msg, line_num=line_num, line_text=line_text, filename=filename)


def _net_open_braces(line: str) -> int:
    """Count { minus } in a line (ignoring strings)."""
    delta, in_str, esc = 0, False, False
    for c in line:
        if esc:            esc = False; continue
        if c == '\\':     esc = True;  continue
        if c == '"':      in_str = not in_str; continue
        if in_str:        continue
        if c == '{':      delta += 1
        elif c == '}':    delta -= 1
    return delta


# ── Main pass ──────────────────────────────────────────────────────────────

def typecheck(source: str, filename=None):
    """
    Scan Coral source and raise CoralTypeError on first type violation.
    Uses a scope stack to track whether we are inside a typed function.
    Each stack entry is either a return-type string or None (control block).
    """
    lines = source.split('\n')

    # Stack entries: str (return type) | None (control-flow / class block)
    scope_stack: list = []

    for lineno, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith('//'):
            continue

        # Strip inline comment
        line_clean = re.sub(r'//.*$', '', line).strip()
        if not line_clean:
            continue

        # ── Inline single-line method: modifiers TYPE name(...) { body } ──
        # Count net braces: these open AND close on the same line → net 0.
        # Don't push/pop anything; but do check the inline body for returns.
        if _FUNC_INLINE_RE.match(line_clean):
            # No block is opened — skip brace tracking entirely
            continue

        # ── Function/method signature opening a block ──────────────────────
        fm = _FUNC_RE.match(line_clean)
        is_ctrl = bool(_CTRL_RE.match(line_clean))

        if fm and not is_ctrl:
            scope_stack.append(fm.group(1))  # push return type
        else:
            # Any other line that opens a block gets None on the stack
            opens  = line_clean.count('{')
            closes = line_clean.count('}')
            # Net new blocks opened (excluding leading } which pop first)
            leading_close = line_clean.startswith('}')
            if leading_close and scope_stack:
                scope_stack.pop()
                # Re-check remaining brace delta
                remainder = line_clean[1:].strip()
                opens  = remainder.count('{')
                closes = remainder.count('}')
            net = opens - closes
            for _ in range(net):
                scope_stack.append(None)
            if net < 0:
                for _ in range(-net):
                    if scope_stack:
                        scope_stack.pop()

        # ── Variable declaration check ─────────────────────────────────────
        dm = _DECL_RE.match(line_clean)
        if dm:
            declared, varname, value = dm.group(1), dm.group(2), dm.group(3)
            # Make sure we're not matching a function signature accidentally
            if not fm:
                _check_compat(declared, value, lineno, raw, filename, 'assign')

        # ── Return statement check ─────────────────────────────────────────
        rm = _RETURN_RE.match(line_clean)
        if rm:
            ret_val = rm.group(1).strip()
            # Find the nearest enclosing function return type (non-None)
            current_return = next(
                (t for t in reversed(scope_stack) if t is not None), None
            )
            if current_return and current_return != 'void':
                _check_compat(current_return, ret_val, lineno, raw, filename, 'return')


# ── Semicolon enforcement ──────────────────────────────────────────────────

class CoralSyntaxError(Exception):
    def __init__(self, message, line_num=None, line_text=None, filename=None):
        self.line_num  = line_num
        self.line_text = line_text
        self.filename  = filename
        loc = ''
        if filename: loc += f'{filename}:'
        if line_num: loc += f'line {line_num}: '
        full = f'\nSyntaxError: {loc}{message}'
        if line_text:
            full += f'\n  → {line_text.strip()}'
            full += f'\n  {"~" * len(line_text.strip())}^'
        super().__init__(full)


# Lines that legitimately end without a semicolon
_NO_SEMI_RE = re.compile(
    r'^('
    r'//.*'                              # full-line comment
    r'|@\w+'                             # decorator e.g. @Override
    r'|.*\{[^}]*$'                       # opens a block (ends with {)
    r'|^\{$'                              # standalone opening brace (Allman style)
    r'|\}'                               # closing brace
    r'|\}\s*(else|else\s+if).*'         # } else  /  } else if(...)
    r'|else\s*\{'                        # standalone else {
    r'|else\s+if\s*\(.*\)\s*\{'         # else if(...) {
    r'|class\s+.*'                       # class declaration
    r'|import\s+.*;\s*$'                 # import (already has ;)
    r'|(?:public|private|protected|static)[\s\w<>]+\([^)]*\)\s*$'  # method sig, { on next line
    r'|(?:public\s+)?class\s+[\w\s,]+$'  # class decl, { on next line
    r')$',
    re.IGNORECASE
)

# Statements that MUST end with a semicolon
_NEEDS_SEMI_RE = re.compile(
    r'^('
    r'(public|private|protected|static)\s+.*'   # typed declarations / method calls
    r'|int|float|str|bool|char|list|dict|set|tuple|void'  # type-led statements
    r'|return\b'
    r'|print\b'
    r'|\w+\s*[\+\-\*\/]?='              # assignment / compound assignment
    r'|\w+(\.\w+)+\s*[\+\-\*\/]?='     # member assignment
    r'|\w+\+\+|\w+--'                   # increment/decrement
    r'|\w+\s*\('                         # function/method call
    r')',
)


def check_semicolons(source: str, filename=None):
    """
    Scan every non-block, non-comment statement and require a trailing semicolon.
    Raises CoralSyntaxError on the first missing one.
    """
    lines = source.split('\n')
    # Track whether we're inside a multi-line bracket expression [( etc.)
    bracket_depth = 0

    for lineno, raw in enumerate(lines, start=1):
        line = raw.strip()

        if not line:
            continue

        # Strip inline comment to get the real end of the line
        stripped = re.sub(r'\s*//.*$', '', line).strip()
        if not stripped:
            continue

        # Track bracket depth across lines (multi-line list/dict literals)
        def _net(s):
            depth, in_str, esc = 0, False, False
            for c in s:
                if esc:        esc = False; continue
                if c == '\\':  esc = True;  continue
                if c == '"':   in_str = not in_str; continue
                if in_str:     continue
                if c in '([':  depth += 1
                elif c in ')]':depth -= 1
            return depth

        if bracket_depth > 0:
            bracket_depth = max(0, bracket_depth + _net(stripped))
            # Inside a multi-line literal continuation — no semicolon needed
            continue

        bracket_depth = max(0, bracket_depth + _net(stripped))

        # Lines that are allowed to omit semicolons
        if _NO_SEMI_RE.match(stripped):
            continue

        # Inline single-line method body: mods TYPE name(...) { body }
        # The outer braces handle the block; body inside may have its own ;
        if re.match(
            rf'^{MODS_OPT}(?:{TYPE})\s+\w+\s*\([^)]*\)\s*\{{.+\}}\s*$',
            stripped
        ):
            continue

        # For / foreach / while / if headers (end with { already handled above,
        # but catch ones without a trailing {)
        if re.match(r'^(for|foreach|while|if|else)\s*[\(\{]', stripped):
            continue

        # If this line opens a bracket that isn't closed on the same line,
        # the statement continues on the next line — no semicolon yet.
        if bracket_depth > 0:
            continue

        # Must end with semicolon
        if not stripped.endswith(';'):
            # Only flag lines that look like real statements
            if _NEEDS_SEMI_RE.match(stripped):
                raise CoralSyntaxError(
                    f'missing semicolon — all statements must end with `;`',
                    line_num=lineno,
                    line_text=raw,
                    filename=filename,
                )
