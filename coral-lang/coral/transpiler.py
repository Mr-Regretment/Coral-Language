"""
coral/transpiler.py  –  Coral → Python transpiler
"""

import re
from .typechecker import typecheck, CoralTypeError, check_semicolons, CoralSyntaxError

# ── Pattern constants ──────────────────────────────────────────────────────
_PRIM   = r'(?:int|float|str|bool|char|void|tuple)'
_GEN    = r'(?:list|dict|set)(?:<[^>]+>)?'
_CUSTOM = r'(?:[A-Z]\w*|\w+\.[A-Z]\w*)(?:<[^>]*>)?'
TYPE    = rf'(?:{_PRIM}|{_GEN}|{_CUSTOM})'

ACCESS   = r'(?:public|private|protected|static)'
MODS_OPT = rf'(?:(?:{ACCESS})\s+)*'
MODS     = rf'(?:(?:{ACCESS})\s+)+'


# ── Helpers ────────────────────────────────────────────────────────────────

def _split_angle(s):
    parts, depth, cur = [], 0, ''
    for c in s:
        if c == '<':   depth += 1
        elif c == '>': depth -= 1
        if c == ',' and depth == 0:
            parts.append(cur.strip()); cur = ''
        else:
            cur += c
    if cur.strip():
        parts.append(cur.strip())
    return parts


def _strip_types(params):
    if not params.strip():
        return ''
    out = []
    for p in _split_angle(params):
        p = p.strip()
        m = re.match(rf'^{TYPE}\s+(\w+)$', p)
        out.append(m.group(1) if m else p)
    return ', '.join(out)


def _c_for_to_python(init, cond, step):
    m = re.match(rf'^{TYPE}\s+', init.strip())
    init = init[m.end():].strip() if m else init.strip()
    cond, step = cond.strip(), step.strip()

    step = re.sub(r'^(\w+)\+\+$', r'\1 += 1', step)
    step = re.sub(r'^(\w+)--$',   r'\1 -= 1', step)

    m_init = re.match(r'^(\w+)\s*=\s*(.+)$', init)
    if not m_init:
        return [init], f'while {cond}:', step

    var, start = m_init.group(1), m_init.group(2).strip()

    _lte = re.match(rf'^{re.escape(var)}\s*<=\s*(.+)$',     cond)
    _lt  = re.match(rf'^{re.escape(var)}\s*<(?!=)\s*(.+)$', cond)
    _gte = re.match(rf'^{re.escape(var)}\s*>=\s*(.+)$',     cond)
    _gt  = re.match(rf'^{re.escape(var)}\s*>(?!=)\s*(.+)$', cond)

    _i1 = re.match(rf'^{re.escape(var)}\s*\+=\s*1$',     step)
    _d1 = re.match(rf'^{re.escape(var)}\s*-=\s*1$',      step)
    _iN = re.match(rf'^{re.escape(var)}\s*\+=\s*(\d+)$', step)

    if _i1:
        if _lt:
            end = _lt.group(1).strip()
            rng = f'range({end})' if start == '0' else f'range({start}, {end})'
            return [], f'for {var} in {rng}:', None
        if _lte:
            end = _lte.group(1).strip()
            return [], f'for {var} in range({start}, ({end}) + 1):', None
    if _d1:
        if _gt:
            end = _gt.group(1).strip()
            return [], f'for {var} in range({start}, {end}, -1):', None
        if _gte:
            end = _gte.group(1).strip()
            return [], f'for {var} in range({start}, ({end}) - 1, -1):', None
    if _iN and _lt:
        end = _lt.group(1).strip()
        return [], f'for {var} in range({start}, {end}, {_iN.group(1)}):', None

    return [init], f'while {cond}:', step


def _fix_super(line, current_method=None):
    """
    super(args)         → super().__init__(args)  [in __init__]
    super()             → super().<current_method>()  [in other methods]
    super(args)         → super().__init__(args)  [fallback]
    """
    def replace(m):
        args = m.group(1).strip()
        if current_method and current_method != '__init__':
            if args:
                return f'super().{current_method}({args})'
            return f'super().{current_method}()'
        return f'super().__init__({args})' if args else 'super().__init__()'
    return re.sub(r'\bsuper\(([^)]*)\)(?![\.\(])', replace, line)


def _global_subs(line, current_method=None):
    line = re.sub(r'\bnull\b',  'None',  line)
    line = re.sub(r'\btrue\b',  'True',  line)
    line = re.sub(r'\bfalse\b', 'False', line)
    line = re.sub(r'\bnew\s+',  '',      line)
    line = re.sub(r'(?<![=<>!])(\w+)\+\+', r'\1 += 1', line)
    line = re.sub(r'(?<![=<>!])(\w+)--',   r'\1 -= 1', line)
    line = re.sub(r'&&', 'and', line)
    line = re.sub(r'\|\|', 'or', line)
    line = _fix_super(line, current_method)
    return line


def _strip_comment(line):
    in_str, esc = False, False
    for i, c in enumerate(line):
        if esc:            esc = False; continue
        if c == '\\':     esc = True;  continue
        if c == '"':      in_str = not in_str; continue
        if in_str:        continue
        if c == '/' and i + 1 < len(line) and line[i+1] == '/':
            return line[:i].rstrip(), '  # ' + line[i+2:].strip()
    return line, ''


def _net_brackets(line):
    delta, in_str, esc = 0, False, False
    for c in line:
        if esc:        esc = False; continue
        if c == '\\':  esc = True;  continue
        if c == '"':   in_str = not in_str; continue
        if in_str:     continue
        if c in '([':  delta += 1
        elif c in ')]':delta -= 1
    return delta


# ── Transpiler ─────────────────────────────────────────────────────────────

class Transpiler:
    def __init__(self):
        self._reset()

    def _reset(self):
        self.indent        = 0
        self.scope_stack   = []   # 'class' | 'block'
        self.while_steps   = []   # [(block_indent, step_code)]
        self.bracket_depth   = 0    # unclosed ( [ across lines
        self.current_method  = None  # name of method currently being defined
        self.pending_open    = False # True when header emitted, waiting for standalone {
        self._just_closed    = False # True immediately after processing a }
        self.output          = []

    @property
    def _in_class(self):
        return 'class' in self.scope_stack

    def _emit(self, text, suffix=''):
        extra = 1 if self.bracket_depth > 0 else 0
        self.output.append('    ' * (self.indent + extra) + text + suffix)

    def _open(self, kind='block'):
        self.scope_stack.append(kind)
        self.indent += 1

    def _close(self):
        target, kept = self.indent - 1, []
        for lvl, code in self.while_steps:
            if lvl == target: self._emit(code)
            else: kept.append((lvl, code))
        self.while_steps = kept
        if self.indent > 0:    self.indent -= 1
        if self.scope_stack:   self.scope_stack.pop()
        self._just_closed = True

    def _process(self, raw):
        line = raw.strip()
        if not line:
            self.output.append(''); return

        if line.startswith('//'):
            self._emit('# ' + line[2:].strip()); return

        line, suffix = _strip_comment(line)
        if not line: return

        line = re.sub(r';\s*$', '', line).strip()
        if not line: return

        if line == '@Override': return

        # Reset just_closed flag (only relevant for the immediately following line)
        just_closed = self._just_closed
        self._just_closed = False
        line = _global_subs(line, self.current_method)
        bd   = _net_brackets(line)

        # ── Inside a multi-line bracket literal ───────────────────────────
        if self.bracket_depth > 0:
            self.bracket_depth = max(0, self.bracket_depth + bd)
            self._emit(line, suffix)
            return

        # ── Standalone opening brace (Allman style) ─────────────────────
        if line == '{':
            if self.pending_open:
                # Header already emitted but held off _open() — do it now
                self._open()
                self.pending_open = False
            else:
                # Unexpected bare { — open a generic block
                self._open()
            return

        # ── Closing brace ─────────────────────────────────────────────────
        if line.startswith('}'):
            rest = line[1:].strip()
            self._close()
            if not rest: return
            m = re.match(r'^else\s+if\s*\((.+)\)\s*\{?\s*$', rest)
            if m:
                self._emit(f'elif {m.group(1)}:', suffix)
                if rest.rstrip().endswith('{'):
                    self._open()
                else:
                    self.pending_open = True
                return
            m = re.match(r'^else\s*\{?\s*$', rest)
            if m:
                self._emit('else:', suffix)
                if rest.rstrip().endswith('{'):
                    self._open()
                else:
                    self.pending_open = True
                return
            line = rest

        # ── import ────────────────────────────────────────────────────────
        if re.match(r'^import\b', line):
            self._emit(line, suffix)
            return

        # ── class ─────────────────────────────────────────────────────────
        m = re.match(
            rf'^{MODS_OPT}class\s+(\w+)'
            rf'(?:\s+extends\s+([\w\s,\.]+))?\s*\{{?\s*$', line)
        if m:
            name, parents = m.group(1), m.group(2)
            if parents:
                pl = ', '.join(p.strip() for p in parents.split(','))
                self._emit(f'class {name}({pl}):', suffix)
            else:
                self._emit(f'class {name}:', suffix)
            if line.rstrip().endswith('{'):
                self._open('class')
            else:
                self.pending_open = True
                self.scope_stack.append('class')  # reserve slot
                self.indent += 1
            return

        # ── single-line method: modifier type name(params) { body } ─────
        sl = re.match(
            rf'^({MODS})(?:{TYPE}\s+)?(\w+)\s*\(([^)]*)\)\s*\{{\s*(.+?)\s*\}}\s*$', line)
        if sl:
            mods2  = sl.group(1)
            fname2 = sl.group(2)
            params2 = _strip_types(sl.group(3))
            body2 = _global_subs(re.sub(r';\s*$', '', sl.group(4).strip()), fname2)
            if 'static' in mods2:
                self._emit('@staticmethod')
                self._emit(f'def {fname2}({params2}):')
            elif self._in_class:
                sep = ', ' if params2 else ''
                self._emit(f'def {fname2}(self{sep}{params2}):')
            else:
                self._emit(f'def {fname2}({params2}):')
            prev_method = self.current_method
            self.current_method = fname2
            self._open()
            self._emit(body2)
            self._close()
            self.current_method = prev_method
            return

        # ── method / function ─────────────────────────────────────────────
        m = re.match(
            rf'^({MODS})(?:{TYPE}\s+)?(\w+)\s*\(([^)]*)\)\s*\{{?\s*$', line)
        if m:
            mods, fname, params = m.group(1), m.group(2), _strip_types(m.group(3))
            if 'static' in mods:
                self._emit('@staticmethod')
                self._emit(f'def {fname}({params}):', suffix)
            elif self._in_class:
                sep = ', ' if params else ''
                self._emit(f'def {fname}(self{sep}{params}):', suffix)
            else:
                self._emit(f'def {fname}({params}):', suffix)
            self.current_method = fname
            if line.rstrip().endswith('{'):
                self._open()
            else:
                self.pending_open = True
            return

        # ── C-style for ───────────────────────────────────────────────────
        m = re.match(
            r'^for\s*\(\s*(.+?)\s*;\s*(.+?)\s*;\s*(.+?)\s*\)\s*\{?\s*$', line)
        if m:
            pre, header, step = _c_for_to_python(m.group(1), m.group(2), m.group(3))
            for p in pre: self._emit(p)
            self._emit(header, suffix)
            if line.rstrip().endswith('{'):
                self._open()
            else:
                self.pending_open = True
            if step: self.while_steps.append((self.indent - 1, step))
            return

        # ── foreach ───────────────────────────────────────────────────────
        m = re.match(
            r'^foreach\s*\(\s*\S+\s+(\w+)\s+in\s+(.+?)\s*\)\s*\{?\s*$', line)
        if m:
            self._emit(f'for {m.group(1)} in {m.group(2)}:', suffix)
            if line.rstrip().endswith('{'):
                self._open()
            else:
                self.pending_open = True
            return

        # ── while ─────────────────────────────────────────────────────────
        m = re.match(r'^while\s*\((.+)\)\s*\{?\s*$', line)
        if m:
            self._emit(f'while {m.group(1)}:', suffix)
            if line.rstrip().endswith('{'):
                self._open()
            else:
                self.pending_open = True
            return

        # ── if ────────────────────────────────────────────────────────────
        m = re.match(r'^if\s*\((.+)\)\s*\{?\s*$', line)
        if m:
            self._emit(f'if {m.group(1)}:', suffix)
            if line.rstrip().endswith('{'):
                self._open()
            else:
                self.pending_open = True
            return

        # ── else if (standalone) ──────────────────────────────────────────
        m = re.match(r'^else\s+if\s*\((.+)\)\s*\{?\s*$', line)
        if m:
            if not just_closed and self.indent > 0: self.indent -= 1
            self._emit(f'elif {m.group(1)}:', suffix)
            if line.rstrip().endswith('{'):
                self._open()
            else:
                self.pending_open = True
            self._just_closed = False; return

        # ── else (standalone) ─────────────────────────────────────────────
        m = re.match(r'^else\s*\{?\s*$', line)
        if m:
            if not just_closed and self.indent > 0: self.indent -= 1
            self._emit('else:', suffix)
            if line.rstrip().endswith('{'):
                self._open()
            else:
                self.pending_open = True
            self._just_closed = False; return

        # ── typed variable declaration ────────────────────────────────────
        m = re.match(rf'^{MODS_OPT}({TYPE})\s+(\w+)\s*(=.+)$', line)
        if m:
            self._emit(f'{m.group(2)} {m.group(3)}', suffix)
            self.bracket_depth = max(0, self.bracket_depth + bd)
            return

        # ── bare field declaration — skip ─────────────────────────────────
        if re.match(rf'^{MODS_OPT}{TYPE}\s+\w+\s*$', line):
            return

        # ── strip leftover access modifier ────────────────────────────────
        line = re.sub(rf'^({ACCESS}\s+)+', '', line)

        self._emit(line, suffix)
        self.bracket_depth = max(0, self.bracket_depth + bd)

    def transpile(self, source):
        self._reset()
        for raw in source.split('\n'):
            self._process(raw)
        return '\n'.join(self.output)


def transpile(source, filename=None, skip_typecheck=False):
    """
    Typecheck then transpile a Coral source string to Python.
    Raises CoralTypeError on type violations (unless skip_typecheck=True).
    """
    if not skip_typecheck:
        check_semicolons(source, filename=filename)
        typecheck(source, filename=filename)
    return Transpiler().transpile(source)
# patch applied below via script
