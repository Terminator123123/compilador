"""
Analizador Sintáctico Ascendente (Bottom-Up Parser)
====================================================
Implementa dos algoritmos genuinamente ascendentes (bottom-up):

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. SHUNTING-YARD (Dijkstra, 1961) — para EXPRESIONES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Dos pilas: operadores (op_stk) y salida de nodos (out_stk).

   • SHIFT  → token operando (número, id, string):
              se crea el nodo hoja y se empuja directo a out_stk.
              Los hijos se procesan ANTES que los padres → bottom-up.

   • SHIFT  → '(' se empuja a op_stk como barrera.

   • REDUCE → al ver un operador nuevo con prioridad ≤ la de op_stk.top():
              se saca el operador del op_stk, se toman 1 ó 2 nodos de
              out_stk (operandos ya construidos), se crea el nodo padre
              y se empuja a out_stk.  "Las hojas ya existen → se combina."

   • REDUCE → al ver ')': se reducen todos los operadores hasta encontrar '('.

   • Al terminar: se reducen todos los operadores restantes.

   Ejemplo visual para  a + b * c
   ┌───────────────────────────────────────────────────────────────┐
   │ Paso │ Token │ Acción           │ out_stk      │ op_stk       │
   │   1  │  a    │ SHIFT (hoja)     │ [a]          │ []           │
   │   2  │  +    │ SHIFT op         │ [a]          │ [+]          │
   │   3  │  b    │ SHIFT (hoja)     │ [a, b]       │ [+]          │
   │   4  │  *    │ prec(*)>prec(+)  │ [a, b]       │ [+, *]       │
   │       │       │ → SHIFT op       │              │              │
   │   5  │  c    │ SHIFT (hoja)     │ [a, b, c]    │ [+, *]       │
   │   6  │ EOF   │ REDUCE *         │ [a, *(b,c)]  │ [+]          │
   │   7  │ EOF   │ REDUCE +         │ [+(a,*(b,c))]│ []           │
   └───────────────────────────────────────────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2. SHIFT-REDUCE con GRAMÁTICA EXPLÍCITA — para SENTENCIAS/DECLARACIONES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Usa las reglas de producción definidas en backend/grammar.py.
   El parser consulta esas reglas para registrar cada reducción en el log.

   Diferencia con el parser descendente anterior:
   • Descendente (LL): empieza por Program → predice qué regla usar → baja
   • Ascendente  (LR): ve los tokens → construye hojas → reduce hacia arriba

Devuelve: { ast, log, nodeCount, errorCount }
"""

from backend.grammar import PRECEDENCE, ASSIGN_OPS, UNARY_OPS, RULES_BY_LHS


def parse(tokens: list) -> dict:

    # Filtrar comentarios — no participan en el análisis sintáctico
    toks = [t for t in tokens if t['t'] != 'comment']

    pos  = 0      # cursor sobre toks
    log  = []     # registro de producciones / errores
    nc   = 0      # contador de nodos AST
    ec   = 0      # contador de errores sintácticos

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    def node(label: str, children=None, meta: str = '', ln: int = 0) -> dict:
        nonlocal nc
        nc += 1
        return {'label': label, 'children': children or [], 'meta': meta, 'id': nc, 'ln': ln}

    def cur() -> dict:
        return toks[pos] if pos < len(toks) else {'t': 'EOF', 'v': 'EOF', 'ln': 0, 'col': 0}

    def peek(n: int = 1) -> dict:
        idx = pos + n
        return toks[idx] if idx < len(toks) else {'t': 'EOF', 'v': 'EOF'}

    def adv() -> dict:
        nonlocal pos
        t = cur()
        pos += 1
        return t

    def eat(expected: str) -> dict:
        """Consume el token esperado; registra error si no coincide."""
        nonlocal pos, ec
        t = cur()
        if t['v'] != expected and t['t'] != expected:
            log.append({
                'ok':   False,
                'msg':  f"Error sintáctico: se esperaba '{expected}', "
                        f"se encontró '{t['v']}' (línea {t['ln']})",
                'rule': '',
                'ln':   t['ln'],
            })
            ec += 1
        else:
            pos += 1
        return t

    def lg_reduce(rule_bnf: str, ln: int = 0):
        """Registra una reducción exitosa usando el BNF de grammar.py."""
        log.append({'ok': True, 'msg': f'Reducción: {rule_bnf}',
                    'rule': rule_bnf, 'ln': ln})

    def lg_shift(symbol: str, ln: int = 0):
        """Registra un desplazamiento (shift)."""
        log.append({'ok': True, 'msg': f'Desplazamiento: {symbol}',
                    'rule': '', 'ln': ln})

    def rule_bnf(lhs: str, index: int = 0) -> str:
        """Obtiene la cadena BNF de la i-ésima regla con un LHS dado."""
        rules = RULES_BY_LHS.get(lhs, [])
        return rules[index].bnf if index < len(rules) else f'{lhs} → …'

    # ──────────────────────────────────────────────────────────────────────────
    # ① SHUNTING-YARD — Parser Ascendente de Expresiones
    # ──────────────────────────────────────────────────────────────────────────

    #: tokens que terminan una expresión en el contexto actual
    _EXPR_STOPPERS = frozenset({
        ';', ')', ']', '}', ':', ',', 'EOF',
        'if', 'else', 'elif', 'while', 'for', 'return',
        'def', 'class', 'function', 'import', 'from',
    })

    def parse_expr_sy(stop_at_comma: bool = False) -> dict | None:
        """
        Analiza una expresión usando el algoritmo Shunting-Yard.
        Genuinamente bottom-up: las hojas se crean antes que los nodos internos.

        Cada invocación (incluidas las recursivas) usa sus PROPIAS pilas
        locales _out y _ops, evitando que la llamada recursiva destruya el
        estado acumulado por la llamada padre.

        stop_at_comma: True cuando la expresión es un argumento de función
                       (no consume la coma como operador).
        """
        nonlocal pos

        # ── Pilas LOCALES a esta invocación ──────────────────────────────────
        _out: list = []   # pila de salida (nodos AST)
        _ops: list = []   # pila de operadores

        # ── Helpers de pilas (cierres sobre _out/_ops locales) ───────────────
        def _reduce_op():
            op    = _ops.pop()
            op_v  = op['v'] if isinstance(op, dict) else op
            is_un = op.get('_unary', False) if isinstance(op, dict) else False
            ln    = op.get('ln', 0)        if isinstance(op, dict) else 0

            if is_un:
                operand = _out.pop() if _out else node('?', [], '?')
                _out.append(node(op_v, [operand], 'op', ln))
            else:
                right = _out.pop() if _out else node('?', [], '?')
                left  = _out.pop() if _out else node('?', [], '?')
                _out.append(node(op_v, [left, right], 'op', ln))

            lg_reduce(f'Expr → Expr {op_v} Expr', ln)

        def _should_reduce(op_v: str, op_prec: int, op_assoc: str) -> bool:
            if not _ops:
                return False
            top = _ops[-1]
            if isinstance(top, dict) and top.get('_barrier'):
                return False
            top_v  = top['v'] if isinstance(top, dict) else top
            top_pr = PRECEDENCE.get(top_v)
            if top_pr is None:
                return False
            if top_pr.level > op_prec:
                return True
            if top_pr.level == op_prec and op_assoc == 'L':
                return True
            return False

        # ── Bucle principal Shunting-Yard ─────────────────────────────────────
        last_was_operand = False

        while True:
            t = cur()
            v = t['v']
            tp = t['t']

            # ── FIN de la expresión ───────────────────────────────────────────
            if tp == 'EOF':
                break
            if v in _EXPR_STOPPERS:
                break
            if stop_at_comma and v == ',':
                break

            # ── Asignación (muy baja prioridad, asociativa derecha) ───────────
            if v in ASSIGN_OPS:
                adv()
                while _ops:
                    top = _ops[-1]
                    if isinstance(top, dict) and top.get('_barrier'):
                        break
                    _reduce_op()
                # Guardar el nodo izquierdo ANTES de la llamada recursiva,
                # porque la llamada crea sus propias pilas y no toca _out local.
                left  = _out.pop() if _out else node('?', [], '?')
                right = parse_expr_sy(stop_at_comma)
                _out.append(node(v, [left, right] if right else [left], 'op', t['ln']))
                lg_reduce(f'Expr → Expr {v} Expr', t['ln'])
                last_was_operand = True
                continue

            # ── Paréntesis izquierdo '(' ──────────────────────────────────────
            if v == '(':
                adv()
                if last_was_operand and _out:
                    func_node = _out.pop()
                    args = []
                    while cur()['v'] != ')' and cur()['t'] != 'EOF':
                        arg = parse_expr_sy(stop_at_comma=True)
                        if arg:
                            args.append(arg)
                        if cur()['v'] == ',':
                            adv()
                    eat(')')
                    call_label = func_node['label']
                    _out.append(node(call_label, args, 'call', t['ln']))
                    lg_reduce(rule_bnf('Expr', 3), t['ln'])
                    last_was_operand = True
                else:
                    _ops.append({'v': '(', '_barrier': True, 'ln': t['ln']})
                    last_was_operand = False
                continue

            # ── Paréntesis derecho ')' ────────────────────────────────────────
            if v == ')':
                while _ops and not (isinstance(_ops[-1], dict) and _ops[-1].get('_barrier')):
                    _reduce_op()
                if _ops:
                    _ops.pop()
                last_was_operand = True
                break

            # ── Índice '['  ───────────────────────────────────────────────────
            if v == '[' and last_was_operand:
                adv()
                idx_node = parse_expr_sy()
                eat(']')
                arr_node = _out.pop() if _out else node('?', [], '?')
                _out.append(node('[]', [arr_node, idx_node] if idx_node else [arr_node]))
                lg_reduce(rule_bnf('Expr', 4), t['ln'])
                last_was_operand = True
                continue

            # ── Acceso a miembro '.' ──────────────────────────────────────────
            if v == '.' and last_was_operand:
                adv()
                prop = adv()['v']
                base = _out.pop() if _out else node('?', [], '?')
                _out.append(node(f"{base['label']}.{prop}", [], 'prop'))
                lg_reduce(rule_bnf('Expr', 5), t['ln'])
                last_was_operand = True
                continue

            # ── Operadores unarios / binarios ────────────────────────────────
            if tp == 'operator' or v in PRECEDENCE:
                is_unary_here = (v in UNARY_OPS) and not last_was_operand

                if is_unary_here:
                    _ops.append({'v': v, '_unary': True, 'ln': t['ln']})
                    adv()
                    last_was_operand = False
                    continue

                prec_info = PRECEDENCE.get(v)
                if prec_info:
                    while _should_reduce(v, prec_info.level, prec_info.assoc):
                        _reduce_op()
                    _ops.append({'v': v, 'ln': t['ln']})
                    lg_shift(v, t['ln'])
                    adv()
                    last_was_operand = False
                    continue

            # ── Operandos primarios (SHIFT → hojas del árbol) ─────────────────
            if tp == 'number':
                adv()
                n = node(v, [], 'num', t['ln'])
                n['_is_op'] = False
                _out.append(n)
                lg_shift(v, t['ln'])
                lg_reduce(rule_bnf('Primary', 0), t['ln'])
                last_was_operand = True
                continue

            if tp == 'string':
                adv()
                display = ('"' + v[1:17] + '…"') if len(v) > 18 else v
                n = node(display, [], 'str', t['ln'])
                n['_is_op'] = False
                _out.append(n)
                lg_reduce(rule_bnf('Primary', 1), t['ln'])
                last_was_operand = True
                continue

            if tp == 'identifier':
                # Dos identificadores consecutivos sin operador entre medio
                # significa que empieza una nueva sentencia → detener expresión.
                if last_was_operand:
                    break
                adv()
                n = node(v, [], 'id', t['ln'])
                n['_is_op'] = False
                _out.append(n)
                lg_shift(v, t['ln'])
                lg_reduce(rule_bnf('Primary', 2), t['ln'])
                last_was_operand = True
                continue

            if tp == 'keyword' and v in ('true','false','True','False',
                                          'null','None','undefined'):
                adv()
                n = node(v, [], 'lit', t['ln'])
                n['_is_op'] = False
                _out.append(n)
                lg_reduce(rule_bnf('Primary', 3), t['ln'])
                last_was_operand = True
                continue

            # ── Lambda  (función anónima) ────────────────────────────────────
            # lambda param1, param2: expr
            if tp == 'keyword' and v == 'lambda':
                adv()   # consume 'lambda'
                lam_params = []
                while cur()['v'] != ':' and cur()['t'] != 'EOF':
                    if cur()['t'] == 'identifier':
                        lam_params.append(node(cur()['v'], [], 'id', cur()['ln']))
                        adv()
                    elif cur()['v'] == ',':
                        adv()
                    else:
                        adv()   # token inesperado — saltar
                if cur()['v'] == ':':
                    adv()   # consume ':'
                lam_body = parse_expr_sy(stop_at_comma=stop_at_comma)
                lam_children = lam_params + ([lam_body] if lam_body else [])
                _out.append(node('lambda', lam_children, 'func', t['ln']))
                lg_reduce(f'Expr → lambda Params ":" Expr', t['ln'])
                last_was_operand = True
                continue

            # ── Keyword usado como función/conversión (float, int, len, str…) ──
            # El lexer clasifica palabras como 'float', 'int', 'len' como keyword.
            # Si no estamos esperando un operador (last_was_operand == False),
            # puede ser el inicio de una llamada del tipo float(...) o int(...).
            if tp == 'keyword' and not last_was_operand and v not in _EXPR_STOPPERS:
                adv()
                n = node(v, [], 'id', t['ln'])
                n['_is_op'] = False
                _out.append(n)
                lg_shift(v, t['ln'])
                last_was_operand = True
                continue

            # ── Lista literal '[' o comprensión de lista '[expr for var in …]' ──
            if v == '[' and not last_was_operand:
                adv()
                # Parsear el primer elemento (o la expresión de la comprensión)
                first_item = parse_expr_sy(stop_at_comma=True)
                if first_item and cur()['v'] == 'for':
                    # ── Comprensión de lista: [expr for var in iterable (if cond)] ──
                    adv()   # consume 'for'
                    loop_var = None
                    if cur()['t'] == 'identifier':
                        loop_var = node(cur()['v'], [], 'id', cur()['ln'])
                        adv()
                    if cur()['v'] == 'in':
                        adv()   # consume 'in'
                    iterable = parse_expr_sy()
                    filter_node = None
                    if cur()['v'] == 'if':
                        adv()   # consume 'if'
                        filter_node = parse_expr_sy()
                    eat(']')
                    comp_ch = [c for c in [first_item, loop_var, iterable, filter_node] if c]
                    _out.append(node('listcomp', comp_ch, 'listcomp', t['ln']))
                else:
                    # ── Lista literal normal ──────────────────────────────────
                    items = [first_item] if first_item else []
                    while cur()['v'] != ']' and cur()['t'] != 'EOF':
                        if cur()['v'] == ',':
                            adv()
                            continue
                        item = parse_expr_sy(stop_at_comma=True)
                        if item:
                            items.append(item)
                    eat(']')
                    _out.append(node('[]', items))
                lg_reduce(rule_bnf('Primary', 4), t['ln'])
                last_was_operand = True
                continue

            break

        # ── REDUCE todos los operadores pendientes ────────────────────────────
        while _ops:
            top = _ops[-1]
            if isinstance(top, dict) and top.get('_barrier'):
                _ops.pop()
                break
            _reduce_op()

        return _out[0] if _out else None

    # ──────────────────────────────────────────────────────────────────────────
    # ② SHIFT-REDUCE — Parser Ascendente de Sentencias / Declaraciones
    # ──────────────────────────────────────────────────────────────────────────
    # Las funciones parse_* reconocen "handles" (patrones al tope del stack
    # conceptual de entrada) y los REDUCEN a no terminales del grammar.

    def parse_block_children() -> list:
        """Block → '{' Program '}' | IndentedBlock
        For brace-style blocks: parse until '}'.
        For Python-style (indented) blocks: detect the indentation column of the
        first body token, then keep parsing statements as long as they start at
        that same (or deeper) column.  Once a token appears at a shallower column
        the block ends — mimicking Python's indentation rules without a full
        INDENT/DEDENT tokeniser.
        """
        nonlocal pos, ec
        stmts = []

        if cur()['v'] == '{':
            adv()
            while cur()['v'] != '}' and cur()['t'] != 'EOF':
                prev_pos = pos
                try:
                    d = parse_decl()
                    if d:
                        stmts.append(d)
                except Exception:
                    pass
                if pos == prev_pos:
                    pos += 1
                    ec  += 1
            if cur()['v'] == '}':
                adv()

        else:
            # Python indented block: use the column of the first body token as
            # the block's indentation level.
            if cur()['t'] == 'EOF':
                return stmts
            block_col = cur().get('col', 1)
            while cur()['t'] != 'EOF':
                c = cur()
                # Stop when we de-dent (column drops below block level)
                if c.get('col', block_col) < block_col:
                    break
                prev_pos = pos
                try:
                    d = parse_decl()
                    if d:
                        stmts.append(d)
                except Exception:
                    pass
                if pos == prev_pos:
                    pos += 1
                    ec  += 1

        return stmts

    def parse_params() -> list:
        """Params → Param ',' Params | Param | ε
        Handles Python-style annotations (param: type) and defaults (param=val),
        as well as *args and **kwargs prefixes.
        """
        nonlocal pos
        p = []
        while cur()['v'] != ')' and cur()['t'] != 'EOF':
            if cur()['v'] == ',':
                adv()
                continue

            # Handle *args / **kwargs prefix
            prefix = ''
            if cur()['v'] in ('*', '**'):
                prefix = adv()['v']
                if cur()['v'] in ('*', '**'):   # bare ** or double *
                    prefix += adv()['v']

            # Param → Type ID  |  ID
            if (not prefix and cur()['t'] == 'keyword' and
                    cur()['v'] in {'int','float','double','char','bool','string','void'}):
                tp = adv()['v']
                nm = adv()['v'] if cur()['t'] == 'identifier' else ''
                label = f'{tp} {nm}' if nm else tp
                # Python annotation after typed param: unlikely but guard
                if cur()['v'] == ':':
                    adv()
                    while cur()['v'] not in (',', ')', '=') and cur()['t'] != 'EOF':
                        adv()
                if cur()['v'] == '=':
                    adv()
                    parse_expr_sy(stop_at_comma=True)
                p.append(node(label, []))
                lg_reduce(rule_bnf('Param', 0), 0)

            elif cur()['t'] == 'identifier':
                nm = adv()['v']
                label = prefix + nm

                # Python type annotation: param: Type[...]
                if cur()['v'] == ':':
                    adv()   # consume ':'
                    # consume type expression (may be complex: Optional[str], etc.)
                    depth = 0
                    while cur()['t'] != 'EOF':
                        v = cur()['v']
                        if v == '[':
                            depth += 1; adv()
                        elif v == ']':
                            if depth > 0: depth -= 1; adv()
                            else: break
                        elif v in (',', ')') and depth == 0:
                            break
                        elif v == '=':
                            break
                        else:
                            adv()

                # Default value: param = expr
                if cur()['v'] == '=':
                    adv()   # consume '='
                    parse_expr_sy(stop_at_comma=True)

                p.append(node(label, []))
                lg_reduce(rule_bnf('Param', 1), 0)

            elif cur()['v'] not in (',', ')'):
                # Unknown token inside params — skip to avoid infinite loop
                adv()

        return p

    def parse_fn() -> dict:
        """REDUCE: FuncDef → 'def' ID '(' Params ')' ':' Block"""
        eat('def')
        nm    = eat('identifier')
        label = 'def: ' + nm['v'] + '()'
        eat('(')
        params = parse_params()
        eat(')')
        if cur()['v'] == ':':
            adv()
        body = parse_block_children()
        lg_reduce(rule_bnf('FuncDef', 0), nm['ln'])
        return node(label, params + body, 'func', nm['ln'])

    def parse_cls() -> dict:
        """REDUCE: ClassDef → 'class' ID ['(' BaseList ')'] ':' Block"""
        adv()   # consume 'class'
        nm = eat('identifier')
        # Optional base-class list: class Foo(Base1, Base2):
        if cur()['v'] == '(':
            adv()   # consume '('
            while cur()['v'] != ')' and cur()['t'] != 'EOF':
                adv()   # skip base class names, commas, etc.
            if cur()['v'] == ')':
                adv()   # consume ')'
        if cur()['v'] == ':':
            adv()   # consume ':'
        body = parse_block_children()
        lg_reduce(rule_bnf('ClassDef', 0), nm['ln'])
        return node('class ' + nm['v'], body, 'class', nm['ln'])

    def parse_var_decl() -> dict:
        """REDUCE: VarDecl → Type ID '=' Expr ';' | Type ID ';'"""
        first_ln = cur()['ln']
        tp = adv()['v']
        nm_tok = eat('identifier')
        nm = nm_tok['v']
        ch = []
        if cur()['v'] == '=':
            adv()
            e = parse_expr_sy()
            if e:
                ch.append(e)
        if cur()['v'] == ';':
            adv()
        lg_reduce(rule_bnf('VarDecl', 0 if ch else 1), first_ln)
        return node(f'{tp} {nm}', ch, 'var', first_ln)

    def parse_if() -> dict:
        """REDUCE: IfStmt → 'if' Expr ':' Block | 'if' '(' Expr ')' Block"""
        if_ln = cur()['ln']
        adv()   # consume 'if'
        has_paren = cur()['v'] == '('
        if has_paren:
            adv()
        cond = parse_expr_sy()
        if has_paren and cur()['v'] == ')':
            adv()
        if cur()['v'] == ':':
            adv()
        body = parse_block_children()
        children = ([cond] if cond else []) + body

        if cur()['v'] in ('else', 'elif'):
            kw = adv()['v']
            if kw == 'elif':
                c2 = parse_expr_sy()
                if cur()['v'] == ':':
                    adv()
                children.append(node('elif', ([c2] if c2 else []) + parse_block_children()))
                lg_reduce(rule_bnf('IfStmt', 4), 0)
            else:
                if cur()['v'] == ':':
                    adv()
                children.append(node('else', parse_block_children()))
                lg_reduce(rule_bnf('IfStmt', 3), 0)
        else:
            lg_reduce(rule_bnf('IfStmt', 0 if has_paren else 2), 0)

        return node('if', children, 'if', if_ln)

    def parse_while() -> dict:
        """REDUCE: WhileStmt → 'while' Expr ':' Block | 'while' '(' Expr ')' Block"""
        while_ln = cur()['ln']
        adv()
        has_paren = cur()['v'] == '('
        if has_paren:
            adv()
        cond = parse_expr_sy()
        if has_paren and cur()['v'] == ')':
            adv()
        if cur()['v'] == ':':
            adv()
        body = parse_block_children()
        lg_reduce(rule_bnf('WhileStmt', 0 if has_paren else 1), while_ln)
        return node('while', ([cond] if cond else []) + body, 'while', while_ln)

    def parse_for() -> dict:
        """REDUCE: ForStmt → 'for' ID 'in' Expr ':' Block"""
        for_ln = cur()['ln']
        adv()   # consume 'for'
        init = parse_decl()
        if cur()['v'] == 'in':
            adv()
            iterable = parse_expr_sy()
        else:
            # parse_expr_sy() pudo haber consumido 'in' como operador binario
            # (ej: "i in range(10)") — en ese caso init ya contiene la expresión
            # completa y no hay iterable separado
            iterable = None
        # Consumir ':' sea cual sea la rama tomada
        if cur()['v'] == ':':
            adv()
        lg_reduce(rule_bnf('ForStmt', 1), for_ln)
        return node('for',
                    ([init] if init else []) + ([iterable] if iterable else []) + parse_block_children(),
                    'for', for_ln)

    def parse_return() -> dict:
        """REDUCE: ReturnStmt → 'return' Expr ';' | 'return'"""
        t = adv()   # consume 'return'
        ch = []
        if cur()['v'] not in (';', '}', 'EOF') and cur()['t'] != 'EOF':
            e = parse_expr_sy()
            if e:
                ch.append(e)
        if cur()['v'] == ';':
            adv()
        lg_reduce(rule_bnf('ReturnStmt', 0 if ch else 2), t['ln'])
        return node('return', ch, 'return', t['ln'])

    def parse_try() -> dict:
        """REDUCE: TryStmt → 'try' Block 'except'/'catch' Block"""
        adv()   # consume 'try'
        if cur()['v'] == ':':
            adv()   # consume ':' (estilo Python)
        body = parse_block_children()
        children = list(body)
        if cur()['v'] in ('except', 'catch'):
            adv()
            if cur()['v'] == '(':
                adv()
                if cur()['t'] == 'identifier':
                    adv()
                if cur()['v'] == ')':
                    adv()
            if cur()['v'] == ':':
                adv()
            handler = parse_block_children()
            children.append(node('catch', handler))
        if cur()['v'] == 'finally':
            adv()
            if cur()['v'] == ':':
                adv()
            fin = parse_block_children()
            children.append(node('finally', fin))
        lg_reduce(rule_bnf('TryStmt', 0), 0)
        return node('try', children, 'try')

    def parse_print_call(kw: str) -> dict:
        """Sentencia print/input — Stmt → print '(' ArgList ')'"""
        adv()
        args = []
        if cur()['v'] == '(':
            adv()
            while cur()['v'] != ')' and cur()['t'] != 'EOF':
                e = parse_expr_sy(stop_at_comma=True)
                if e:
                    args.append(e)
                if cur()['v'] == ',':
                    adv()
            if cur()['v'] == ')':
                adv()
        if cur()['v'] == ';':
            adv()
        return node(kw, args, 'call')

    def parse_stmt() -> dict | None:
        """Selecciona y REDUCE la sentencia correspondiente según el token actual."""
        nonlocal pos, ec
        t = cur()
        v = t['v']

        if v == '{':
            return node('bloque', parse_block_children())
        if v == 'if':
            return parse_if()
        if v == 'while':
            return parse_while()
        if v == 'for':
            return parse_for()
        if v == 'return':
            return parse_return()
        if v == 'try':
            return parse_try()
        if v in ('break', 'continue', 'pass'):
            adv()
            if cur()['v'] == ';':
                adv()
            lg_reduce(f'Stmt → "{v}"', t['ln'])
            return node(v, [], '', t['ln'])
        if v in ('print', 'input'):
            return parse_print_call(v)
        # Declaración estilo C/Java: int x = ... / float y = ...
        if (t['t'] == 'keyword' and
                v in ('int', 'float', 'double', 'char', 'bool', 'void', 'string',
                      'str', 'list', 'dict', 'set', 'tuple') and
                peek(1)['t'] == 'identifier'):
            return parse_var_decl()
        if v == ';':
            adv()
            return None
        if v in ('del', 'assert', 'raise', 'throw'):
            adv()
            e = parse_expr_sy()
            if cur()['v'] == ';':
                adv()
            return node(v, [e] if e else [])
        if v == 'import':
            adv()
            name = adv()['v'] if cur()['t'] in ('identifier', 'keyword') else ''
            lg_reduce(rule_bnf('Import', 0), t['ln'])
            return node('import ' + name, [])
        if v == 'from':
            adv()
            mod = adv()['v'] if cur()['t'] == 'identifier' else ''
            if cur()['v'] == 'import':
                adv()
            sym = adv()['v'] if cur()['t'] == 'identifier' else ''
            lg_reduce(rule_bnf('Import', 1), t['ln'])
            return node(f'from {mod} import {sym}', [])

        # Declaración estilo C con tipo desconocido: "nt a = 5", "myType x = ..."
        # Dos identificadores consecutivos sin operador = probable tipo inválido
        if t['t'] == 'identifier' and peek(1)['t'] == 'identifier':
            tp = adv()['v']
            nm_tok = adv()
            nm = nm_tok['v']
            ch = []
            if cur()['v'] == '=':
                adv()
                e = parse_expr_sy()
                if e:
                    ch.append(e)
            if cur()['v'] == ';':
                adv()
            log.append({'ok': False,
                        'msg': f"Error sintáctico: tipo desconocido '{tp}' en '{tp} {nm}'",
                        'rule': '', 'ln': t['ln']})
            ec += 1
            return node(f'ERROR: {tp} {nm}', ch, 'c_decl_err', t['ln'])

        # Caso general: expresión
        e = parse_expr_sy()
        if cur()['v'] == ';':
            adv()
        lg_reduce(rule_bnf('Stmt', 5), t['ln'])
        return e

    def parse_decl() -> dict | None:
        """
        Decide qué producción de Decl aplicar según el lookahead.
        Equivale a elegir qué 'handle' reconocer en un parser LR.
        """
        if cur()['v'] == 'def':
            return parse_fn()
        if cur()['v'] == 'class':
            return parse_cls()
        return parse_stmt()

    # ──────────────────────────────────────────────────────────────────────────
    # Punto de entrada — parse_program
    # ──────────────────────────────────────────────────────────────────────────

    def parse_program() -> dict:
        """
        Program → Decl Program | ε
        Reduce todas las declaraciones hasta EOF.
        """
        nonlocal pos, ec
        lg_shift('Program', 0)
        log.append({'ok': True, 'msg': 'Inicio del análisis sintáctico ascendente',
                    'rule': rule_bnf('Program', 0), 'ln': 0})
        stmts = []
        while cur()['t'] != 'EOF':
            prev_pos = pos          # Guardia anti-bucle infinito
            try:
                d = parse_decl()
                if d:
                    stmts.append(d)
            except Exception:
                pass
            # Si parse_decl no avanzó el cursor, forzar avance para romper el bucle
            if pos == prev_pos:
                pos += 1
                ec  += 1
        log.append({'ok': True,
                    'msg': f'Análisis completado — {nc} nodos, {ec} errores',
                    'rule': rule_bnf('Program', 1), 'ln': 0})
        return node('PROGRAMA', stmts)

    # ── Ejecutar ──────────────────────────────────────────────────────────────
    ast = parse_program()
    return {'ast': ast, 'log': log, 'nodeCount': nc, 'errorCount': ec}
