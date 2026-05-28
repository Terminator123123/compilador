"""
Analizador Semántico — Visitor sobre el AST
============================================
Verifica:
  - Variables no declaradas / redeclaración
  - Compatibilidad de tipos en asignaciones y operaciones
  - Aridad de funciones (cantidad de argumentos)
  - Retorno en todas las ramas de una función
  - Uso antes de asignación
  - break/continue fuera de bucle
  - return fuera de función
  - División o módulo por cero literal
  - Reasignación de constantes (const)
  - Parámetros duplicados en funciones
  - Shadowing (sobreescritura) de built-ins
  - Comparación de tipos incompatibles (string vs número)
  - Llamada a una variable como si fuera función

Cada símbolo incluye: declared_type, inferred_type, use_count.
"""

from __future__ import annotations
from typing import Optional
import re

_VALID_ID_RE = re.compile(r'^[a-zA-Z_$][a-zA-Z0-9_$]*$')

_NUMERIC     = frozenset({'int', 'float', 'double', 'num'})
_STRING      = frozenset({'str', 'string'})
_ANY         = 'any'

_BOOL_OPS    = frozenset({
    '==', '!=', '<', '>', '<=', '>=',
    '&&', '||', '!', 'and', 'or', 'not', '===', '!=='
})
_ARITH_OPS   = frozenset({'+', '-', '*', '/', '%', '**', '//', '<<', '>>'})
_COMPARE_OPS = frozenset({'>', '<', '>=', '<='})
_DIV_OPS     = frozenset({'/', '%', '//'})

_BUILTINS = frozenset({
    # Funciones built-in Python
    'print', 'input', 'range', 'len', 'str', 'int', 'float', 'bool',
    'list', 'dict', 'set', 'tuple', 'type', 'open', 'enumerate',
    'zip', 'map', 'filter', 'sorted', 'reversed', 'sum', 'min', 'max',
    'abs', 'round', 'isinstance', 'hasattr', 'getattr', 'setattr',
    'super', 'object', 'property', 'staticmethod', 'classmethod',
    'any', 'all', 'next', 'iter', 'id', 'hash', 'ord', 'chr',
    'bin', 'hex', 'oct', 'divmod', 'pow', 'repr', 'eval', 'exec',
    'globals', 'locals', 'callable', 'delattr', 'vars', 'dir',
    'bytes', 'bytearray', 'frozenset', 'memoryview', 'complex',
    # Métodos comunes (usados sin objeto explícito)
    'append', 'extend', 'insert', 'remove', 'pop', 'get',
    'items', 'keys', 'values', 'update', 'format', 'split', 'join',
    'strip', 'lower', 'upper', 'replace', 'find', 'index',
    # Literales especiales Python
    'True', 'False', 'None',
    # Identificadores implícitos comunes
    'self', 'cls', 'args', 'kwargs',
    # Excepciones estándar
    'Exception', 'ValueError', 'TypeError', 'KeyError', 'IndexError',
    'AttributeError', 'NameError', 'RuntimeError', 'StopIteration',
    'ZeroDivisionError', 'OverflowError', 'NotImplementedError',
    'OSError', 'IOError', 'FileNotFoundError', 'MemoryError',
})


class _Scope:
    def __init__(self, name: str, parent: Optional[_Scope] = None):
        self.name     = name
        self.parent   = parent
        self.children: list[_Scope] = []
        self.symbols:  dict[str, dict] = {}

    def declare(self, name: str, entry: dict) -> bool:
        if name in self.symbols:
            return False
        self.symbols[name] = entry
        return True

    def lookup(self, name: str) -> Optional[dict]:
        if name in self.symbols:
            return self.symbols[name]
        return self.parent.lookup(name) if self.parent else None

    def lookup_local(self, name: str) -> Optional[dict]:
        return self.symbols.get(name)

    def mark_used(self, name: str):
        if name in self.symbols:
            self.symbols[name]['use_count'] = self.symbols[name].get('use_count', 0) + 1
        elif self.parent:
            self.parent.mark_used(name)


def analyze(ast: dict) -> dict:
    errors:   list[dict] = []
    warnings: list[dict] = []

    global_scope          = _Scope('global')
    current_scope         = global_scope
    current_fn_name       = None
    current_fn_return_type = None
    in_loop               = False

    def err(msg: str, name: str = '', ln: int = 0):
        errors.append({'ok': False, 'msg': msg, 'name': name, 'ln': ln})

    def warn(msg: str, name: str = '', ln: int = 0):
        warnings.append({'ok': True, 'msg': msg, 'name': name, 'ln': ln})

    def push_scope(name: str):
        nonlocal current_scope
        new_scope = _Scope(name, current_scope)
        current_scope.children.append(new_scope)
        current_scope = new_scope

    def pop_scope():
        nonlocal current_scope
        current_scope = current_scope.parent  # type: ignore[assignment]

    def infer_type(node: Optional[dict]) -> str:
        if node is None:
            return _ANY
        meta     = node.get('meta', '')
        label    = node.get('label', '')
        children = node.get('children', [])

        if meta == 'num':
            return 'float' if '.' in label else 'int'
        if meta == 'str':
            return 'str'
        if meta == 'lit':
            if label in ('true', 'True', 'false', 'False'):
                return 'bool'
            if label in ('null', 'None', 'undefined'):
                return 'null'
        if meta == 'id':
            sym = current_scope.lookup(label)
            return sym.get('inferred_type', _ANY) if sym else _ANY
        if meta == 'call':
            return _ANY
        if meta == 'op':
            if label in _BOOL_OPS:
                return 'bool'
            if label in _ARITH_OPS and len(children) == 2:
                lt = infer_type(children[0])
                rt = infer_type(children[1])
                if label == '+' and (lt in _STRING or rt in _STRING):
                    return 'str'
                if lt in _NUMERIC and rt in _NUMERIC:
                    return 'float' if ('float' in (lt, rt) or 'double' in (lt, rt)) else 'int'
        return _ANY

    def _returns_on_all_paths(nodes: list) -> bool:
        for n in nodes:
            if n.get('meta') == 'return' or n.get('label') == 'return':
                return True
            # if-node con rama else que también retorna → retorna en todos los caminos
            if n.get('meta') == 'if' or n.get('label') == 'if':
                ch = n.get('children', [])
                else_branches = [c for c in ch if c.get('label') in ('else', 'elif')]
                if_body       = [c for c in ch if c not in else_branches]
                if (else_branches
                        and _returns_on_all_paths(if_body)
                        and all(_returns_on_all_paths(e.get('children', []))
                                for e in else_branches)):
                    return True
        return False

    def _has_any_return(nodes: list) -> bool:
        for n in nodes:
            if n.get('meta') == 'return':
                return True
            if _has_any_return(n.get('children', [])):
                return True
        return False

    def _check_type_compat(decl_t: str, inferred: str, name: str):
        if decl_t == _ANY or inferred == _ANY:
            return
        if decl_t == 'var' or inferred == 'var':
            return
        if decl_t in _NUMERIC and inferred in _STRING:
            err(f"Tipo incompatible: '{name}' declarada como '{decl_t}' pero se le asigna texto (string)", name)
        elif decl_t in _STRING and inferred in _NUMERIC:
            err(f"Tipo incompatible: '{name}' declarada como '{decl_t}' pero se le asigna un número", name)

    def _is_zero_literal(node: Optional[dict]) -> bool:
        if node is None:
            return False
        if node.get('meta') == 'num':
            lbl = node.get('label', '').strip()
            try:
                return float(lbl) == 0.0
            except ValueError:
                return False
        return False

    # ── visitor ───────────────────────────────────────────────────────────────

    def _extract_return_type(label: str) -> str:
        for prefix in ('def: ', 'function: '):
            if label.startswith(prefix):
                return _ANY
        if ': ' in label:
            rt = label.split(': ')[0].strip()
            if rt in (_NUMERIC | _STRING | {'bool', 'void'}):
                return rt
        return _ANY

    def visit(node: Optional[dict]):
        nonlocal current_fn_name, current_fn_return_type, in_loop

        if node is None:
            return

        meta     = node.get('meta', '')
        label    = node.get('label', '')
        children = node.get('children', [])
        node_ln  = node.get('ln', 0)          # línea del nodo en el AST

        # ── Raíz ─────────────────────────────────────────────────────────────
        if label == 'PROGRAMA':
            for child in children:
                visit(child)
            return

        # ── Declaración estilo C (sintaxis inválida en Python) ────────────────
        if meta == 'c_decl_err':
            parts   = label.replace('ERROR: ', '').split()
            type_kw = parts[0] if parts else '?'
            var_nm  = parts[1] if len(parts) > 1 else '?'
            err(
                f"Declaración estilo C no válida en Python: "
                f"'{type_kw} {var_nm}'. "
                f"Sintaxis correcta: {var_nm}: {type_kw} = <valor>",
                var_nm, node_ln,
            )
            # Registrar la variable en la tabla para que no quede vacía
            if var_nm and var_nm not in _BUILTINS and not current_scope.lookup_local(var_nm):
                current_scope.declare(var_nm, {
                    'declared_type': type_kw,
                    'inferred_type': 'unknown',
                    'type':          type_kw,
                    'assigned':      False,
                    'use_count':     0,
                    'is_param':      False,
                    'is_func':       False,
                    'is_const':      False,
                    'ln':            node_ln,
                })
            return

        # ── Declaración con tipo: int x = ..., float y, var x, const x ───────
        if meta == 'var':
            parts         = label.split()
            var_name      = parts[-1] if parts else label
            declared_type = parts[0]  if len(parts) > 1 else 'var'

            # ① Shadowing de built-ins
            if var_name in _BUILTINS:
                warn(
                    f"'{var_name}' sobreescribe un identificador built-in; "
                    f"la función/valor original quedará inaccesible",
                    var_name, node_ln,
                )

            if current_scope.lookup_local(var_name):
                err(f"Redeclaración: '{var_name}' ya fue declarada en este scope",
                    var_name, node_ln)
            else:
                inferred = infer_type(children[0]) if children else _ANY
                _check_type_compat(declared_type if declared_type != 'var' else _ANY, inferred, var_name)
                resolved = declared_type if declared_type not in ('var', _ANY) else (inferred if inferred != _ANY else _ANY)
                current_scope.declare(var_name, {
                    'declared_type': declared_type,
                    'inferred_type': inferred,
                    'type':          resolved,
                    'assigned':      bool(children),
                    'use_count':     0,
                    'is_param':      False,
                    'is_func':       False,
                    'is_const':      declared_type == 'const',
                    'ln':            node_ln,
                })

            for child in children:
                visit(child)
            return

        # ── Asignación (=, +=, -=, …) ─────────────────────────────────────────
        if meta == 'op' and label != '==' and (label == '=' or (label.endswith('=') and len(label) <= 3)):
            if len(children) >= 2:
                left  = children[0]
                right = children[1]
                lname = left.get('label', '') if left else ''
                lmeta = left.get('meta', '')  if left else ''
                left_ln = left.get('ln', node_ln) if left else node_ln

                if lmeta == 'id' and lname and lname not in _BUILTINS:
                    existing = current_scope.lookup(lname)
                    r_type   = infer_type(right)

                    if existing:
                        # ② Reasignación de const
                        if existing.get('is_const'):
                            err(
                                f"No se puede reasignar '{lname}': "
                                f"fue declarada como constante (const)",
                                lname, left_ln,
                            )
                        else:
                            existing['assigned']      = True
                            existing['inferred_type'] = r_type
                            _check_type_compat(
                                existing.get('declared_type', _ANY)
                                if existing.get('declared_type') != 'var' else _ANY,
                                r_type, lname,
                            )
                    else:
                        # ③ Shadowing de built-ins al asignar sin declarar
                        if lname in _BUILTINS:
                            warn(
                                f"'{lname}' sobreescribe un identificador built-in",
                                lname, left_ln,
                            )
                        current_scope.declare(lname, {
                            'declared_type': 'var',
                            'inferred_type': r_type,
                            'type':          r_type,
                            'assigned':      True,
                            'use_count':     0,
                            'is_param':      False,
                            'is_func':       False,
                            'is_const':      False,
                            'ln':            left_ln,
                        })

                visit(right)
                for child in children[2:]:
                    visit(child)
            else:
                for child in children:
                    visit(child)
            return

        # ── Definición de función / lambda ────────────────────────────────────
        if meta == 'func':
            raw_name = label
            for prefix in ('def: ', 'function: '):
                raw_name = raw_name.replace(prefix, '')
            fn_name = raw_name.split('(')[0].strip()

            is_lambda = fn_name == 'lambda'

            if not is_lambda and current_scope.lookup_local(fn_name):
                err(f"Redeclaración: función '{fn_name}' ya fue declarada en este scope",
                    fn_name, node_ln)

            params = [c for c in children if not c.get('children') and c.get('meta') in ('', 'id', 'param', None)]
            body   = [c for c in children if c not in params]

            ret_type   = _extract_return_type(label)
            # Extraer tipos de parámetros cuando están declarados (ej: "int a", "float b")
            param_types: list[str] = []
            for p in params:
                p_parts = p.get('label', '').split()
                if len(p_parts) >= 2 and p_parts[0] in (_NUMERIC | _STRING | {'bool', 'void'}):
                    param_types.append(p_parts[0])
                else:
                    param_types.append(_ANY)

            if not is_lambda:
                current_scope.declare(fn_name, {
                    'declared_type': 'func',
                    'inferred_type': 'func',
                    'type':          'func',
                    'arity':         len(params),
                    'param_types':   param_types,
                    'return_type':   ret_type,
                    'assigned':      True,
                    'use_count':     0,
                    'is_func':       True,
                    'is_param':      False,
                    'is_const':      False,
                    'ln':            node_ln,
                })

            prev_fn          = current_fn_name
            prev_ret_type    = current_fn_return_type
            current_fn_name        = fn_name if not is_lambda else current_fn_name
            current_fn_return_type = ret_type
            push_scope('lambda' if is_lambda else fn_name)

            # ④ Parámetros duplicados
            seen_params: set[str] = set()
            for p in params:
                p_label = p.get('label', '')
                p_name  = p_label.split()[-1] if p_label else ''
                p_ln    = p.get('ln', node_ln)
                if p_name:
                    if p_name in seen_params:
                        err(
                            f"Parámetro duplicado '{p_name}' en la función '{fn_name}'",
                            p_name, p_ln,
                        )
                    else:
                        seen_params.add(p_name)
                        current_scope.declare(p_name, {
                            'declared_type': 'param',
                            'inferred_type': _ANY,
                            'type':          _ANY,
                            'assigned':      True,
                            'use_count':     0,
                            'is_param':      True,
                            'is_func':       False,
                            'is_const':      False,
                            'ln':            p_ln,
                        })

            for b in body:
                visit(b)

            if body and _has_any_return(body) and not _returns_on_all_paths(body):
                warn(f"Función '{fn_name}': no todos los caminos de ejecución retornan un valor",
                     fn_name, node_ln)

            pop_scope()
            current_fn_name        = prev_fn
            current_fn_return_type = prev_ret_type
            return

        # ── Definición de clase ───────────────────────────────────────────────
        if meta == 'class':
            cls_name = label.replace('class ', '').strip()
            current_scope.declare(cls_name, {
                'declared_type': 'class',
                'inferred_type': 'class',
                'type':          'class',
                'assigned':      True,
                'use_count':     0,
                'is_func':       False,
                'is_param':      False,
                'is_const':      False,
                'ln':            node_ln,
            })
            push_scope(cls_name)
            for child in children:
                visit(child)
            pop_scope()
            return

        # ── Uso de identificador ──────────────────────────────────────────────
        if meta == 'id':
            if label and label not in _BUILTINS and _VALID_ID_RE.match(label):
                sym = current_scope.lookup(label)
                if sym is None:
                    err(f"Variable '{label}' usada pero no fue declarada", label, node_ln)
                else:
                    if not sym.get('assigned', True):
                        warn(f"'{label}' podría usarse antes de ser asignada", label, node_ln)
                    current_scope.mark_used(label)
            return

        # ── Llamada a función ─────────────────────────────────────────────────
        if meta == 'call':
            fn_label = label.split('(')[0].strip()
            # Las llamadas de método sobre objetos (obj.metodo) no se verifican
            # porque requieren inferencia de tipos de instancia (obj sí se verifica
            # por separado cuando se visita la expresión de acceso a atributo).
            is_method_call = '.' in fn_label
            if fn_label and fn_label not in _BUILTINS and not is_method_call:
                sym = current_scope.lookup(fn_label)
                if sym is None:
                    err(f"Función '{fn_label}' llamada pero no fue declarada", fn_label, node_ln)
                else:
                    current_scope.mark_used(fn_label)

                    # ⑤ Llamada a una variable como si fuera función
                    inferred_t = sym.get('inferred_type', _ANY)
                    if (not sym.get('is_func')
                            and not sym.get('is_param')
                            and inferred_t in (_NUMERIC | _STRING | {'bool', 'null'})):
                        err(
                            f"'{fn_label}' no es una función "
                            f"(tipo inferido: '{inferred_t}')",
                            fn_label, node_ln,
                        )
                    elif sym.get('is_func'):
                        expected = sym.get('arity', -1)
                        actual   = len(children)
                        if expected >= 0 and expected != actual:
                            err(
                                f"Función '{fn_label}' espera {expected} "
                                f"argumento(s) pero recibe {actual}",
                                fn_label, node_ln,
                            )
                        else:
                            # ⑥ Tipo de argumento incorrecto
                            param_types = sym.get('param_types', [])
                            for i, (arg, pt) in enumerate(zip(children, param_types)):
                                if pt == _ANY:
                                    continue
                                at = infer_type(arg)
                                if at == _ANY:
                                    continue
                                if at != pt and not (pt in _NUMERIC and at in _NUMERIC):
                                    err(
                                        f"Argumento {i + 1} de '{fn_label}': "
                                        f"se esperaba '{pt}' pero se recibió '{at}'",
                                        fn_label, node_ln,
                                    )
            for child in children:
                visit(child)
            return

        # ── return ────────────────────────────────────────────────────────────
        if meta == 'return' or label == 'return':
            if current_fn_name is None:
                err("'return' usado fuera de una función", 'return', node_ln)
            elif (current_fn_return_type not in (_ANY, 'void', None)
                  and children):
                # ⑦ Retorno de tipo incorrecto
                ret_val  = children[0]
                ret_type = infer_type(ret_val)
                if (ret_type != _ANY
                        and ret_type != current_fn_return_type
                        and not (current_fn_return_type in _NUMERIC
                                 and ret_type in _NUMERIC)):
                    err(
                        f"Retorno incorrecto en '{current_fn_name}': "
                        f"se declaró '{current_fn_return_type}' "
                        f"pero retorna '{ret_type}'",
                        current_fn_name, node_ln,
                    )
            for child in children:
                visit(child)
            return

        # ── break / continue ──────────────────────────────────────────────────
        if label in ('break', 'continue'):
            if not in_loop:
                err(f"'{label}' usado fuera de un bucle (for/while)", label, node_ln)
            return

        # ── Comprensión de lista [expr for var in iterable] ──────────────────
        if meta == 'listcomp':
            push_scope('listcomp')
            # El segundo hijo (índice 1) es la variable del bucle (meta='id')
            if len(children) >= 2:
                loop_var_node = children[1]
                lv_name = loop_var_node.get('label', '')
                if lv_name and lv_name not in _BUILTINS:
                    current_scope.declare(lv_name, {
                        'declared_type': 'var',
                        'inferred_type': _ANY,
                        'type':          _ANY,
                        'assigned':      True,
                        'use_count':     0,
                        'is_param':      False,
                        'is_func':       False,
                        'is_const':      False,
                        'ln':            loop_var_node.get('ln', node_ln),
                    })
            for child in children:
                visit(child)
            pop_scope()
            return

        # ── Try / Except / Catch ──────────────────────────────────────────────
        if meta == 'try' or label == 'try':
            push_scope('try_block')
            for child in children:
                if child.get('label') in ('catch', 'finally'):
                    pop_scope()
                    push_scope(child.get('label', 'except_block'))
                    for grandchild in child.get('children', []):
                        visit(grandchild)
                    pop_scope()
                    push_scope('try_block')   # restaurar por si hay más hijos
                else:
                    visit(child)
            pop_scope()
            return

        # ── Bucles ────────────────────────────────────────────────────────────
        if meta == 'while':
            prev_in_loop = in_loop
            in_loop = True
            push_scope('while_loop')
            for child in children:
                visit(child)
            pop_scope()
            in_loop = prev_in_loop
            return

        if meta == 'for':
            prev_in_loop = in_loop
            in_loop = True
            push_scope('for_loop')
            # Auto-declarar la variable del bucle para que no aparezca
            # como "no declarada" dentro del cuerpo.
            # El parser produce el primer hijo como:
            #   - nodo op 'in' con hijo izquierdo = variable (meta='id')
            #   - o directamente un nodo id si el parser separó init e iterable
            if children:
                first = children[0]
                loop_var_name = None
                if first.get('meta') == 'op' and first.get('label') == 'in':
                    # for i in iterable:  → op 'in'(id(i), iterable)
                    sub = first.get('children', [])
                    if sub and sub[0].get('meta') == 'id':
                        loop_var_name = sub[0].get('label', '')
                elif first.get('meta') == 'id':
                    # for i ... (separado en init/iterable)
                    loop_var_name = first.get('label', '')
                if loop_var_name and loop_var_name not in _BUILTINS:
                    if not current_scope.lookup_local(loop_var_name):
                        current_scope.declare(loop_var_name, {
                            'declared_type': 'var',
                            'inferred_type': _ANY,
                            'type':          _ANY,
                            'assigned':      True,
                            'use_count':     0,
                            'is_param':      False,
                            'is_func':       False,
                            'is_const':      False,
                            'ln':            node_ln,
                        })
            for child in children:
                visit(child)
            pop_scope()
            in_loop = prev_in_loop
            return

        # ── if / else / elif ──────────────────────────────────────────────────
        if meta == 'if' or label in ('if', 'else', 'elif'):
            push_scope('if_block')
            for child in children:
                visit(child)
            pop_scope()
            return

        # ── Operaciones binarias ──────────────────────────────────────────────
        if meta == 'op' and len(children) == 2:
            left  = children[0]
            right = children[1]
            lt    = infer_type(left)
            rt    = infer_type(right)

            # ⑦ División / módulo por cero literal
            if label in _DIV_OPS and _is_zero_literal(right):
                err(
                    f"División por cero: el operando derecho de '{label}' es 0",
                    label, node_ln,
                )

            # Nota: en Python bool es subclase de int, por lo que
            # operaciones aritméticas con bool son válidas (True*2 == 2).

            # ⑧ Comparación entre tipos incompatibles (string vs número)
            if (label in _COMPARE_OPS
                    and lt != _ANY and rt != _ANY):
                if (lt in _STRING and rt in _NUMERIC) or (lt in _NUMERIC and rt in _STRING):
                    err(
                        f"Comparación '{label}' entre tipos incompatibles "
                        f"('{lt}' y '{rt}')",
                        label, node_ln,
                    )

            # '+' entre número y string es un error de tipos
            if label == '+' and lt != _ANY and rt != _ANY:
                if lt in _NUMERIC and rt in _STRING:
                    err(
                        f"Operación '+' no válida: no se puede sumar un número ('{lt}') "
                        f"con un string",
                        label, node_ln,
                    )
                elif lt in _STRING and rt in _NUMERIC:
                    err(
                        f"Operación '+' no válida: no se puede sumar un string "
                        f"con un número ('{rt}')",
                        label, node_ln,
                    )

            # Operaciones aritméticas distintas de '+' y '*' con strings confirmados
            if (label in _ARITH_OPS
                    and label not in ('+', '*')
                    and lt != _ANY and rt != _ANY):
                if lt in _STRING and rt in _STRING:
                    err(f"Operación '{label}' no es válida entre dos strings", label, node_ln)
                elif lt in _STRING and rt in _NUMERIC:
                    err(f"Operación '{label}' no es válida entre string y número", label, node_ln)
                elif lt in _NUMERIC and rt in _STRING:
                    err(f"Operación '{label}' no es válida entre número y string", label, node_ln)

            visit(left)
            visit(right)
            return

        # ── Default ───────────────────────────────────────────────────────────
        for child in children:
            visit(child)

    if ast:
        visit(ast)

    # ── ⑳ Funciones declaradas pero nunca llamadas ────────────────────────────
    for sym_name, sym in global_scope.symbols.items():
        if sym.get('is_func') and sym.get('use_count', 0) == 0:
            warnings.append({
                'ok':   True,
                'msg':  f"Función '{sym_name}' declarada pero nunca llamada",
                'name': sym_name,
                'ln':   sym.get('ln', 0),
            })

    # ── Recolectar tabla de símbolos ─────────────────────────────────────────

    symbol_table: list[dict] = []

    def collect(scope: _Scope, depth: int = 0):
        for sym_name, sym in scope.symbols.items():
            symbol_table.append({
                'name':          sym_name,
                'declared_type': sym.get('declared_type', 'var'),
                'inferred_type': sym.get('inferred_type', 'unknown'),
                'type':          sym.get('type', '?'),
                'scope':         scope.name,
                'ln':            sym.get('ln', 0),
                'use_count':     sym.get('use_count', 0),
                'is_func':       sym.get('is_func', False),
                'is_param':      sym.get('is_param', False),
                'is_const':      sym.get('is_const', False),
                'depth':         depth,
            })
        for child in scope.children:
            collect(child, depth + 1)

    collect(global_scope)

    total_uses  = sum(s.get('use_count', 0) for s in global_scope.symbols.values())
    total_decls = len(symbol_table)
    scope_names = list({s['scope'] for s in symbol_table})

    return {
        'errors':      errors,
        'warnings':    warnings,
        'errorCount':  len(errors),
        'warnCount':   len(warnings),
        'symbolTable': symbol_table,
        'totalUses':   total_uses,
        'totalDecls':  total_decls,
        'scopeNames':  scope_names,
    }
