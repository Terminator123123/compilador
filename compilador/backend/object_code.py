"""
Generador de Código Objeto (Arquitectura RISC Ficticia)
========================================================
Convierte el TAC optimizado en instrucciones tipo ensamblador educativo.

Modelo: arquitectura RISC de 8 registros de 32 bits.
  R0        — acumulador / registro de retorno
  R1-R7     — propósito general

Instrucciones:
  MOVI  Rn, #imm       carga inmediata
  LOAD  Rn, [addr]     carga desde memoria
  STORE Rn, [addr]     almacena en memoria
  MOVE  Rd, Rs         copia entre registros
  ADD/SUB/MUL/DIV/MOD/POW  Rd, Ra, Rb
  NEG   Rd, Ra         negación
  NOT   Rd, Ra         not lógico
  AND/OR Rd, Ra, Rb    lógica binaria
  CMP   Ra, Rb         compara (actualiza flags)
  JMP   L              salto incondicional
  JZ    L              salta si cero  (IF_FALSE)
  JNZ   L              salta si no cero (IF)
  PUSH  Rn             apila registro
  POP   Rn             desapila a registro
  CALL  func           llama función (result → R0)
  RET                  retorna
  HALT                 fin del programa
"""

from __future__ import annotations
import re

_REGS       = ['R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7']
_WORD_SIZE  = 4
_DATA_BASE  = 0x1000

_OP_INSTR: dict[str, str] = {
    '+':  'ADD', '-':  'SUB', '*':  'MUL',
    '/':  'DIV', '//': 'IDIV', '%': 'MOD', '**': 'POW',
    '==': 'CMP_EQ', '!=': 'CMP_NE',
    '<':  'CMP_LT', '>':  'CMP_GT',
    '<=': 'CMP_LE', '>=': 'CMP_GE',
    '&&': 'AND', '||': 'OR', 'and': 'AND', 'or': 'OR',
}

_KEYWORDS = frozenset({
    'IF', 'IF_FALSE', 'GOTO', 'RETURN', 'CALL', 'ARG', 'PARAM',
    'FUNC_BEGIN', 'FUNC_END', 'HALT', 'True', 'False',
    'not', 'and', 'or', 'LEN',
    'print', 'input', 'range', 'len', 'str', 'int', 'float', 'bool',
    'list', 'dict', 'set', 'tuple', 'abs', 'sum', 'min', 'max',
})

_STR_OR_NONWS = r'(?:"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|\S+)'

_BIN_RE   = re.compile(
    r'^(\w[\w.]*)\s*=\s*(\S+)\s*(\+|-|\*\*|//|\*|/|%|==|!=|<=|>=|<|>|&&|\|\||and\b|or\b)\s*(\S+)$')
_UN_RE    = re.compile(r'^(\w[\w.]*)\s*=\s*(-|not|!)\s*(\S+)$')
_COPY_RE  = re.compile(r'^(\w[\w.]*)\s*=\s*(' + _STR_OR_NONWS + r')$')
_IF_RE    = re.compile(r'^IF\s+(\S+)\s+GOTO\s+(\S+)$')
_IFF_RE   = re.compile(r'^IF_FALSE\s+(\S+)\s+GOTO\s+(\S+)$')
_GOTO_RE  = re.compile(r'^GOTO\s+(\S+)$')
_RET_RE   = re.compile(r'^RETURN(?:\s+(\S+))?$')
_CALL_RE  = re.compile(r'^(\w[\w.]*)\s*=\s*CALL\s+(\S+),\s*(\d+)$')
_CALL2_RE = re.compile(r'^CALL\s+(\S+),\s*(\d+)$')
_ARG_RE   = re.compile(r'^ARG\s+(' + _STR_OR_NONWS + r')$')
_PARAM_RE = re.compile(r'^PARAM\s+(' + _STR_OR_NONWS + r')$')
_FUNCB_RE = re.compile(r'^FUNC_BEGIN\s+(\S+)$')
_FUNCE_RE = re.compile(r'^FUNC_END\s+(\S+)$')


def _is_num(s: str) -> bool:
    try:
        float(s); return True
    except (ValueError, TypeError):
        return False


def _is_str_lit(s: str) -> bool:
    return (len(s) >= 2 and
            ((s[0] == '"' and s[-1] == '"') or
             (s[0] == "'" and s[-1] == "'")))


def _is_temp(s: str) -> bool:
    return bool(re.match(r'^t\d+$', s))


class _Allocator:
    def __init__(self):
        self._reg_map:  dict[str, str] = {}
        self._free:     list[str]      = list(_REGS)
        self.spilled:   set[str]       = set()
        self.log:       list[str]      = []

    def alloc(self, name: str) -> str:
        if name in self._reg_map:
            return self._reg_map[name]
        if self._free:
            reg = self._free.pop(0)
            self._reg_map[name] = reg
            self.log.append(f'Asignado {reg} ← {name}')
            return reg
        victim = next(iter(self._reg_map))
        reg    = self._reg_map.pop(victim)
        self.spilled.add(victim)
        self._reg_map[name] = reg
        self.log.append(f'Spill: {victim} expulsado de {reg}, asignado a {name}')
        return reg

    def free(self, name: str):
        if name in self._reg_map:
            reg = self._reg_map.pop(name)
            self._free.insert(0, reg)
            self.log.append(f'Liberado {reg} (era {name})')

    def get(self, name: str) -> str | None:
        return self._reg_map.get(name)

    def register_table(self) -> list[dict]:
        rows = [{'reg': 'R0', 'assignment': 'Acumulador', 'status': 'reservado'}]
        for r in _REGS:
            owner = next((k for k, v in self._reg_map.items() if v == r), None)
            if owner:
                rows.append({'reg': r, 'assignment': owner, 'status': 'activo'})
            elif r in self._free:
                rows.append({'reg': r, 'assignment': '—', 'status': 'libre'})
            else:
                rows.append({'reg': r, 'assignment': '—', 'status': 'en uso'})
        return rows


def generate_object_code(optimized_tac: list) -> dict:
    """
    Genera código objeto desde el TAC optimizado.
    Retorna:
      { instructions, data_segment, register_table, stats, log }
    """
    empty = {
        'instructions':   [],
        'data_segment':   [],
        'register_table': [],
        'stats': {
            'instr_count': 0, 'regs_used': 0,
            'vars_count': 0,  'labels_count': 0, 'cycles_est': 0,
        },
        'log': [],
    }
    if not optimized_tac:
        return empty

    user_vars:  set[str] = set()
    label_names: set[str] = set()

    for ins in optimized_tac:
        if ins.get('is_label'):
            label_names.add(ins['instr'].rstrip(':'))
            continue

    _STR_STRIP_RE = re.compile(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'')
    for ins in optimized_tac:
        if ins.get('is_label'):
            continue
        clean = _STR_STRIP_RE.sub('', ins['instr'])
        for tok in re.findall(r'\b([a-zA-Z_]\w*)\b', clean):
            if tok not in _KEYWORDS and not _is_temp(tok) and tok not in label_names:
                user_vars.add(tok)

    addr     = _DATA_BASE
    var_addr: dict[str, int] = {}
    data_seg: list[dict]     = []

    for v in sorted(user_vars):
        var_addr[v] = addr
        data_seg.append({'name': v, 'address': f'0x{addr:04X}',
                         'size': f'{_WORD_SIZE}B', 'init': '0'})
        addr += _WORD_SIZE

    alloc    = _Allocator()
    obj_list: list[dict] = []
    label_count = 0

    def emit(instr: str, comment: str = '',
             is_label: bool = False, is_dir: bool = False):
        obj_list.append({
            'instr': instr, 'comment': comment,
            'is_label': is_label, 'is_directive': is_dir,
        })

    def load_op(operand: str, target: str = 'R0'):
        if _is_num(operand):
            emit(f'MOVI  {target}, #{operand}', f'inmediato {operand}')
        elif _is_str_lit(operand):
            emit(f'MOVS  {target}, {operand}', f'cadena {operand}')
        elif _is_temp(operand):
            r = alloc.get(operand)
            if r and r != target:
                emit(f'MOVE  {target}, {r}', f'mover {operand}')
            elif not r:
                emit(f'LOAD  {target}, [{operand}]', f'{operand} (spill)')
        elif operand in var_addr:
            emit(f'LOAD  {target}, [0x{var_addr[operand]:04X}]', f'cargar {operand}')
        else:
            emit(f'LOAD  {target}, [{operand}]', f'cargar {operand}')

    def store_res(dst: str, src: str = 'R0'):
        if _is_temp(dst):
            r = alloc.alloc(dst)
            if r != src:
                emit(f'MOVE  {r}, {src}', f'temp {dst} → {r}')
        elif dst in var_addr:
            emit(f'STORE {src}, [0x{var_addr[dst]:04X}]', f'guardar {dst}')
        else:
            emit(f'STORE {src}, [{dst}]', f'guardar {dst}')

    if data_seg:
        emit('.data', is_dir=True)
        for v in sorted(user_vars):
            emit(f'  {v:<10} DW  0',
                 comment=f'addr 0x{var_addr[v]:04X}', is_dir=True)
        emit('', is_dir=True)

    emit('.code', is_dir=True)
    emit('', is_dir=True)

    for ins in optimized_tac:
        code = ins['instr']

        if ins.get('is_label'):
            lbl = code.rstrip(':')
            emit(f'{lbl}:', is_label=True)
            label_count += 1
            continue

        m = _FUNCB_RE.match(code)
        if m:
            fn = m.group(1)
            emit(f'PROC  {fn}', f'inicio de {fn}')
            emit('PUSH  LR', 'guardar dirección de retorno')
            continue

        m = _FUNCE_RE.match(code)
        if m:
            fn = m.group(1)
            emit('POP   LR', 'restaurar dirección de retorno')
            emit('RET', f'retorno de {fn}')
            emit(f'ENDP  {fn}', is_dir=True)
            continue

        m = _RET_RE.match(code)
        if m:
            val = m.group(1)
            if val:
                load_op(val, 'R0')
            emit('RET', 'retornar (resultado en R0)')
            continue

        m = _IF_RE.match(code)
        if m:
            cond, lbl = m.group(1), m.group(2)
            load_op(cond, 'R0')
            emit('CMP   R0, #0', 'comparar condición')
            emit(f'JNZ   {lbl}', 'saltar si verdadero')
            label_count += 1
            continue

        m = _IFF_RE.match(code)
        if m:
            cond, lbl = m.group(1), m.group(2)
            load_op(cond, 'R0')
            emit('CMP   R0, #0', 'comparar condición')
            emit(f'JZ    {lbl}', 'saltar si falso')
            label_count += 1
            continue

        m = _GOTO_RE.match(code)
        if m:
            emit(f'JMP   {m.group(1)}', 'salto incondicional')
            label_count += 1
            continue

        m = _CALL_RE.match(code)
        if m:
            dst, fn, n = m.group(1), m.group(2), m.group(3)
            emit(f'CALL  {fn}', f'llamar {fn} ({n} arg(s))')
            store_res(dst, 'R0')
            continue

        m = _CALL2_RE.match(code)
        if m:
            emit(f'CALL  {m.group(1)}', f'llamar {m.group(1)} ({m.group(2)} arg(s))')
            continue

        m = _ARG_RE.match(code)
        if m:
            val = m.group(1)
            load_op(val, 'R0')
            emit('PUSH  R0', f'apilar arg {val}')
            continue

        m = _PARAM_RE.match(code)
        if m:
            val = m.group(1)
            emit('POP   R0', f'recibir param {val}')
            if val in var_addr:
                emit(f'STORE R0, [0x{var_addr[val]:04X}]', f'guardar {val}')
            continue

        m = _BIN_RE.match(code)
        if m:
            dst, src1, op, src2 = m.groups()
            instr_name = _OP_INSTR.get(op, 'OP')
            is_cmp = instr_name.startswith('CMP_')
            # Si src2 es un temp mapeado a R1, moverlo antes de que
            # load_op(src1, R1) lo sobreescriba
            if _is_temp(src2) and alloc.get(src2) == 'R1':
                emit(f'MOVE  R2, R1', f'preservar {src2} antes de cargar {src1}')
                load_op(src1, 'R1')
            else:
                load_op(src1, 'R1')
                load_op(src2, 'R2')
            if is_cmp:
                emit('CMP   R1, R2', f'{src1} {op} {src2}')
                emit('SETF  R0', 'resultado de comparación → R0')
            else:
                emit(f'{instr_name:<5} R0, R1, R2', f'{src1} {op} {src2}')
            store_res(dst, 'R0')
            continue

        m = _UN_RE.match(code)
        if m:
            dst, op, src = m.groups()
            load_op(src, 'R1')
            if op == '-':
                emit('NEG   R0, R1', f'negar {src}')
            else:
                emit('NOT   R0, R1', f'not {src}')
            store_res(dst, 'R0')
            continue

        m = _COPY_RE.match(code)
        if m:
            dst, src = m.groups()
            if src in ('True', 'False'):
                val = '1' if src == 'True' else '0'
                load_op(val, 'R0')
                store_res(dst, 'R0')
            elif _is_num(src):
                if _is_temp(dst):
                    r = alloc.alloc(dst)
                    emit(f'MOVI  {r}, #{src}', f'{dst} = {src}')
                else:
                    emit(f'MOVI  R0, #{src}', f'constante {src}')
                    store_res(dst, 'R0')
            else:
                load_op(src, 'R0')
                store_res(dst, 'R0')
            continue

        emit(f'; {code}', 'no reconocida')

    emit('HALT', 'fin del programa')

    for v in sorted(alloc.spilled):
        data_seg.append({
            'name': f'{v} (spill)',
            'address': f'0x{addr:04X}',
            'size': f'{_WORD_SIZE}B',
            'init': '—',
        })
        addr += _WORD_SIZE

    real = [i for i in obj_list
            if not i['is_directive'] and i['instr'].strip()
            and not i['instr'].startswith(';')]

    cycles = sum(
        3 if any(x in i['instr'] for x in ['MUL', 'DIV', 'CALL', 'PUSH', 'POP', 'POW'])
        else 1
        for i in real
    )

    return {
        'instructions':   obj_list,
        'data_segment':   data_seg,
        'register_table': alloc.register_table(),
        'stats': {
            'instr_count':  len(real),
            'regs_used':    len(alloc._reg_map) + len(alloc.spilled),
            'vars_count':   len(user_vars),
            'labels_count': label_count,
            'cycles_est':   cycles,
        },
        'log': alloc.log,
    }
