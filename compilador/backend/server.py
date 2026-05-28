import threading
from flask import Flask, request, jsonify, send_from_directory
import os

from backend.lexer import lex
from backend.parser import parse
from backend.semantic import analyze
from backend.ast_nodes import enrich_tokens
from backend.codegen import generate_intermediate
from backend.optimizer import optimize as optimize_tac
from backend.object_code import generate_object_code

_FRONTEND = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))

app = Flask(__name__, static_folder=_FRONTEND, static_url_path='')


# ── Static frontend ───────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory(_FRONTEND, 'index.html')


# ── Compilar API ──────────────────────────────────────────────────────────────

@app.route('/api/compilar', methods=['POST'])
def compilar():
    data = request.get_json(force=True)
    src = data.get('codigo', '')

    if not src.strip():
        return jsonify({'error': 'Código vacío'}), 400

    result_holder = {}
    error_holder  = {}

    def _run():
        try:
            tokens = lex(src)
            enrich_tokens(tokens)
            parsed   = parse(tokens)
            semantic = analyze(parsed['ast'])

            for ln, line in enumerate(src.split('\n'), start=1):
                stripped = line.rstrip()
                if stripped.endswith(';'):
                    semantic['warnings'].append({
                        'ok':   True,
                        'msg':  f'Estilo: punto y coma ";" innecesario en Python — '
                                f'Python no usa ";" para terminar sentencias',
                        'name': ';',
                        'ln':   ln,
                    })
                    semantic['warnCount'] += 1

            codegen      = generate_intermediate(parsed['ast'])
            optimization = optimize_tac(codegen['tac'])
            object_code  = generate_object_code(optimization['optimized'])
            lang         = 'python'

            result_holder['payload'] = {
                'tokens':       tokens,
                'ast':          parsed['ast'],
                'log':          parsed['log'],
                'nodeCount':    parsed['nodeCount'],
                'errorCount':   parsed['errorCount'],
                'lang':         lang,
                'lines':        src.count('\n') + 1,
                'chars':        len(src),
                'semErrors':    semantic['errors'],
                'semWarnings':  semantic['warnings'],
                'semErrCount':  semantic['errorCount'],
                'semWarnCount': semantic['warnCount'],
                'symbolTable':  semantic['symbolTable'],
                'semTotalUses': semantic['totalUses'],
                'semTotalDecls':semantic['totalDecls'],
                'semScopeNames':semantic['scopeNames'],
                'codegen':      codegen,
                'optimization': optimization,
                'object_code':  object_code,
            }
        except Exception as e:
            error_holder['msg'] = str(e)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=8)

    if t.is_alive():
        return jsonify({'error': 'Tiempo de análisis excedido (código muy complejo)'}), 408

    if 'msg' in error_holder:
        return jsonify({'error': error_holder['msg']}), 500

    return jsonify(result_holder['payload'])



