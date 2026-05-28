/* =====================================================================
   API.JS — comunicación con el backend Python (Flask)
   compile() llama a POST /api/compilar y actualiza toda la interfaz
   ===================================================================== */

/* Limpia todos los paneles antes de mostrar nuevos resultados */
function _clearResults() {
  try {
    /* Léxico */
    if (typeof allToks !== 'undefined') allToks.length = 0;
    if (typeof renderTokTable === 'function') renderTokTable();
    if (typeof renderStats    === 'function') renderStats();
    if (typeof drawPie        === 'function') drawPie();

    /* Sintáctico */
    if (typeof renderAST === 'function') renderAST(null);
    if (typeof renderLog === 'function') renderLog([]);
    const _t = (id, v) => { const e = document.getElementById(id); if (e) e.textContent = v; };
    const _s = (id, v) => { const e = document.getElementById(id); if (e) e.style.cssText += v; };
    _t('syn-nodes', '0'); _t('syn-prods', '0'); _t('syn-depth', '0');
    _t('syn-pos', '—');   _t('syn-errs',  '0'); _t('logBadge', '0 reglas');
    _t('syn-estado', '—');
    const synEst = document.getElementById('syn-estado');
    if (synEst) synEst.style.color = '';

    /* Léxico extra */
    _t('ei-err', '0');
    const stErr = document.getElementById('stErrItem');
    if (stErr) stErr.style.display = 'none';

    /* Semántico */
    if (typeof renderSemantic === 'function') renderSemantic([], [], [], {});

    /* Código intermedio */
    ['tac','stack'].forEach(k => {
      const body  = document.getElementById(`inter-body-${k}`);
      const empty = document.getElementById(`inter-empty-${k}`);
      if (body)  body.innerHTML = '';
      if (empty) empty.style.display = 'flex';
      const badge = document.getElementById(`ipanel-${k}-badge`);
      if (badge) badge.textContent = '0 instrucciones';
    });
    const astPre   = document.getElementById('inter-body-ast');
    const astEmpty = document.getElementById('inter-empty-ast');
    if (astPre)   { astPre.innerHTML = ''; astPre.style.display = 'none'; }
    if (astEmpty) astEmpty.style.display = 'flex';
    _t('ipanel-ast-badge', '—');
    ['ist-instr','ist-temp','ist-ops'].forEach(id => _t(id, '0'));
    const logCount = document.getElementById('ilog-count');
    if (logCount) {
      logCount.textContent = '✓ 0 instrucciones generadas';
      logCount.classList.add('ilog-pending');
    }
    /* Código objeto */
    try { if (typeof clearObjectCodeState === 'function') clearObjectCodeState(); } catch(_) {}
  } catch (e) {
    console.warn('[_clearResults]', e);
  }
}

async function compile() {
  const src = document.getElementById('codeInput').value ||
              document.getElementById('codeInput2').value;

  if (!src.trim()) {
    setStatus('idle', 'Nada que compilar');
    return;
  }

  setStatus('run', 'Compilando…');

  if (window._compileAbort) window._compileAbort.abort();
  window._compileAbort = new AbortController();

  /* Detener animación de trazado si está activa */
  if (_traceTimer) {
    clearInterval(_traceTimer);
    _traceTimer = null;
    const pb = document.getElementById('trace-play-btn');
    if (pb) { pb.textContent = '▶ Reproducir'; pb.classList.remove('playing'); }
  }

  /* Limpiar resultados anteriores inmediatamente */
  _clearResults();

  let data;
  try {
    const res = await fetch('/api/compilar', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ codigo: src }),
      signal:  window._compileAbort.signal,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      setStatus('err', err.error || 'Error del servidor');
      return;
    }

    data = await res.json();
  } catch (e) {
    if (e.name === 'AbortError') return;
    setStatus('err', 'No se pudo conectar con el backend');
    console.error(e);
    return;
  }

  /* ── Actualizar estado global ── */
  allToks = data.tokens;

  /* ── Panel léxico ── */
  renderTokTable();
  renderStats();
  drawPie();
  updateExtraInfo(data.lines, data.chars);

  /* ── Panel sintáctico ── */
  renderAST(data.ast);
  renderLog(data.log);

  document.getElementById('syn-nodes').textContent  = data.nodeCount;
  document.getElementById('syn-prods').textContent  = data.log.length;
  document.getElementById('syn-depth').textContent  = getASTDepth(data.ast);
  document.getElementById('syn-pos').textContent    = data.log.length > 0
    ? `L${data.log[0].ln || 1}-n${data.nodeCount}` : '—';

  const hasErr = data.errorCount > 0 || allToks.some(t => t.t === 'unknown');
  document.getElementById('syn-estado').textContent = hasErr ? 'Con errores' : 'OK ✓';
  document.getElementById('syn-estado').style.color = hasErr ? '#FF0040' : 'var(--sintactico-color)';
  document.getElementById('syn-errs').textContent   = data.errorCount;

  const totErr = allToks.filter(t => t.t === 'unknown').length;
  document.getElementById('ei-err').textContent = totErr;

  if (totErr) {
    document.getElementById('stErrItem').style.display = 'flex';
    document.getElementById('stErrN').textContent = totErr;
    setStatus('err', `${totErr} error(es) léxico(s)`);
  } else {
    document.getElementById('stErrItem').style.display = 'none';
    setStatus('ok', 'Compilación exitosa');
  }

  /* ── Detectar lenguaje ── */
  document.getElementById('langLabel').textContent = data.lang;
  document.getElementById('logBadge').textContent  = data.log.length + ' reglas';

  /* ── Panel semántico ── */
  renderSemantic(data.semErrors || [], data.semWarnings || [], data.symbolTable || [], {
    totalUses:  data.semTotalUses  || 0,
    totalDecls: data.semTotalDecls || 0,
    scopeNames: data.semScopeNames || [],
  });

  /* ── Panel código intermedio ── */
  if (data.codegen) renderIntermediate(data.codegen);

  /* ── Panel optimización ── */
  if (data.optimization) renderOptimization(data.optimization);

  /* ── Panel código objeto ── */
  if (data.object_code) renderObjectCode(data.object_code);
}

function renderSemantic(errors, warnings, symbols, meta) {
  meta = meta || {};
  const errCount  = errors.length;
  const warnCount = warnings.length;
  const symCount  = symbols.length;
  const totalUses = meta.totalUses  !== undefined ? meta.totalUses  : symbols.reduce((a,s) => a + (s.use_count||0), 0);
  const totalDecls= meta.totalDecls !== undefined ? meta.totalDecls : symCount;
  const scopeNames= meta.scopeNames || [...new Set(symbols.map(s => s.scope))];

  /* ── Sidebar grandes números ── */
  document.getElementById('sem-syms').textContent  = symCount;
  document.getElementById('sem-decls').textContent = totalDecls;
  document.getElementById('sem-uses').textContent  = totalUses;

  /* ── Stats box ── */
  const ok = errCount === 0;
  document.getElementById('sem-estado').textContent = ok ? '✓ OK' : `${errCount} error(es)`;
  document.getElementById('sem-estado').style.color = ok ? 'var(--sintactico-color)' : '#FF0040';
  document.getElementById('sem-errs').textContent   = errCount;
  document.getElementById('sem-warns').textContent  = warnCount;
  document.getElementById('sem-scope-count').textContent = scopeNames.length;

  /* ── Lista de scopes activos ── */
  const scopeList = document.getElementById('sem-scope-list');
  if (!scopeNames.length) {
    scopeList.innerHTML = '<div class="sem-scope-empty">Compila para ver scopes</div>';
  } else {
    scopeList.innerHTML = scopeNames.map((sc, i) =>
      `<div class="sem-scope-row">
         <span class="sem-scope-dot"></span>
         <span class="sem-scope-name">${esc(sc)}</span>
         <span class="sem-scope-depth">prof. ${i}</span>
       </div>`
    ).join('');
  }

  /* ── Tabla de símbolos ── */
  const symTable = document.getElementById('semSymTable');
  const symEmpty = document.getElementById('semSymEmpty');
  const symBadge = document.getElementById('sem-sym-badge');
  const symBody  = document.getElementById('semSymBody');

  symBadge.textContent = `${symCount} símbolo${symCount !== 1 ? 's' : ''} · ${scopeNames.length} scope${scopeNames.length !== 1 ? 's' : ''}`;

  if (!symCount) {
    symTable.style.display = 'none';
    symEmpty.style.display = 'flex';
  } else {
    symTable.style.display = 'table';
    symEmpty.style.display = 'none';

    const DECL_COL  = { var:'#C3A6FF', func:'#C3A6FF', class:'#FFE66D', param:'rgba(145,192,253,.6)', int:'#85C1E9', float:'#85C1E9', double:'#85C1E9', str:'#4ECDC4', string:'#4ECDC4', bool:'#A8E6CF' };
    const INFER_COL = { int:'#85C1E9', float:'#85C1E9', str:'#4ECDC4', bool:'#A8E6CF', func:'#C3A6FF', 'any':'rgba(145,192,253,.35)', unknown:'rgba(145,192,253,.35)' };

    symBody.innerHTML = symbols.map((s, i) => {
      const dc  = DECL_COL [s.declared_type] || 'rgba(200,0,255,.6)';
      const ic  = INFER_COL[s.inferred_type] || 'rgba(145,192,253,.35)';
      const uses    = s.use_count || 0;
      const isOk    = uses > 0 || s.is_func;
      const stateBadge = isOk
        ? `<span class="sem-state-badge ok">activa</span>`
        : `<span class="sem-state-badge warn">sin uso</span>`;

      return `<tr>
        <td class="td-n">${i + 1}</td>
        <td style="font-weight:600;">${esc(s.name)}</td>
        <td><span class="sem-type-badge" style="color:${dc};border-color:${dc};">${esc(s.declared_type)}</span></td>
        <td><span class="sem-type-badge" style="color:${ic};border-color:${ic};">${esc(s.inferred_type === _ANY ? 'any' : (s.inferred_type || 'unknown'))}</span></td>
        <td style="color:rgba(200,0,255,.8);font-size:10px;">${esc(s.scope)}</td>
        <td style="color:rgba(145,192,253,.6);text-align:center;">${s.ln ? 'L' + s.ln : '—'}</td>
        <td style="text-align:center;color:${uses>0?'#fff':'rgba(255,255,255,.3)'};">${uses}</td>
        <td>${stateBadge}</td>
      </tr>`;
    }).join('');
  }

  /* ── Calcular líneas con errores/advertencias para los puntos del gutter ── */
  const errLineMap  = new Map();
  const warnLineMap = new Map();

  errors.forEach(e => {
    if (e.ln && !errLineMap.has(e.ln)) errLineMap.set(e.ln, e.msg);
  });
  warnings.forEach(w => {
    if (w.ln && !errLineMap.has(w.ln) && !warnLineMap.has(w.ln)) warnLineMap.set(w.ln, w.msg);
  });

  if (typeof setSemanticErrorLines === 'function') {
    setSemanticErrorLines(errLineMap, warnLineMap);
  }

  /* ── Log semántico ── */
  const logBody  = document.getElementById('semLogBody');
  const logEmpty = document.getElementById('semLogEmpty');
  const logBadge = document.getElementById('sem-log-badge');
  const allMsgs  = [
    ...errors.map(e   => ({ ...e, kind: 'err'  })),
    ...warnings.map(w => ({ ...w, kind: 'warn' })),
  ];

  logBadge.textContent = `${allMsgs.length} entrada${allMsgs.length !== 1 ? 's' : ''}`;

  if (!allMsgs.length) {
    logBody.style.display  = 'none';
    logEmpty.style.display = 'flex';
  } else {
    logBody.style.display  = 'block';
    logEmpty.style.display = 'none';

    function lineForMsg(m) {
      return m.ln ? ` <span style="color:rgba(145,192,253,.4);">[L${m.ln}]</span>` : '';
    }

    logBody.innerHTML = allMsgs.map(m => `
      <div class="sem-log-entry sem-${m.kind}">
        <span class="sem-log-icon">${m.kind === 'err' ? '✗' : '⚠'}</span>
        <span class="sem-log-text">${esc(m.msg)}${lineForMsg(m)}</span>
        <span class="sem-log-tag">${m.kind === 'err' ? 'ERROR' : 'WARN'}</span>
      </div>`).join('');
  }
}

/* Constante para el renderizador */
const _ANY = 'any';

/* =====================================================================
   CÓDIGO INTERMEDIO — nuevo diseño (paneles apilados)
   ===================================================================== */

let _codegenData = null;
let _interFocus  = 'tac';

/* Botones del sidebar → enfocar/expandir el panel correspondiente */
function setInterFocus(rep) {
  _interFocus = rep;

  /* Resaltar botón activo */
  ['tac','ast','stack'].forEach(r => {
    document.getElementById(`irep-${r}`)?.classList.toggle('active', r === rep);
  });

  /* Expandir panel focalizado */
  ['tac','ast','stack'].forEach(r => {
    document.getElementById(`ipanel-${r}`)?.classList.toggle('focused', r === rep);
  });

  /* Scroll al panel */
  const panel = document.getElementById(`ipanel-${rep}`);
  if (panel) panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

/* Resaltado de instrucciones */
function _highlightInstr(raw) {
  if (!raw) return '';
  const s = esc(raw);
  if (/^L\d+:$/.test(raw.trim())) {
    return `<span class="lbl">${s}</span>`;
  }
  return s
    .replace(/\b(FUNC_BEGIN|FUNC_END|PARAM|ARG|CALL|RETURN|GOTO|IF|IF_FALSE|PUSH|POP|STORE|LOAD|ADD|SUB|MUL|DIV|MOD|POW|IDIV|EQ|NEQ|LT|GT|LEQ|GEQ|AND|OR|NEG|NOT|JUMP|JUMP_IF_FALSE|LEN|INDEX|DUP|ROT3|DUP_AT)\b/g,
      '<span class="kw">$1</span>')
    .replace(/\b(t\d+)\b/g, '<span class="tmp">$1</span>')
    .replace(/\b(L\d+)\b/g, '<span class="lbl">$1</span>')
    .replace(/ ([+\-*\/%<>=!&|]{1,3}) /g, ' <span class="op">$1</span> ');
}

/* Renderiza tabla de instrucciones (TAC o Stack) */
function _renderInstrTable(instructions, bodyId, emptyId) {
  const body  = document.getElementById(bodyId);
  const empty = document.getElementById(emptyId);
  if (!body) return;
  if (!instructions || !instructions.length) {
    body.innerHTML = '';
    if (empty) empty.style.display = 'flex';
    return;
  }
  if (empty) empty.style.display = 'none';
  let n = 0;
  body.innerHTML = instructions.map(ins => {
    const isLabel = ins.is_label;
    if (!isLabel) n++;
    return `<div class="inter-row${isLabel ? ' is-label' : ''}">
      <span class="inter-n">${isLabel ? '' : n}</span>
      <span class="inter-instr">${_highlightInstr(ins.instr)}</span>
      <span class="inter-comment">${ins.comment ? '// ' + esc(ins.comment) : ''}</span>
      <span class="inter-ln">${ins.ln ? ins.ln : ''}</span>
    </div>`;
  }).join('');
}

/* Función principal de renderizado */
function renderIntermediate(codegen) {
  _codegenData = codegen;
  const stats  = codegen.stats || {};
  const tacCnt   = stats.tac_count   || 0;
  const stackCnt = stats.stack_count || 0;
  const temps    = stats.tac_temps   || 0;

  /* ── Sidebar: Estadísticas ── */
  document.getElementById('ist-instr').textContent = tacCnt;
  document.getElementById('ist-temp').textContent  = temps;

  /* Contar operadores: instrucciones con operador en el texto */
  const ops = (codegen.tac || []).filter(i =>
    !i.is_label && /[+\-*\/%<>=!&|]/.test(i.instr)).length;
  document.getElementById('ist-ops').textContent   = ops;
  document.getElementById('ist-optim').textContent = ops > 0 ? 'Sí' : 'No';
  document.getElementById('ist-optim').style.color = ops > 0 ? '#57FF00' : '#F5CB5C';
  document.getElementById('ist-err').textContent   = '0';

  /* ── Sidebar: Log de Generación ── */
  const logCount = document.getElementById('ilog-count');
  if (logCount) {
    logCount.textContent = `✓ ${tacCnt} instrucciones TAC · ${stackCnt} pila`;
    logCount.classList.remove('ilog-pending');
  }

  /* ── Badge de cada panel ── */
  const tacNonLabel  = (codegen.tac   || []).filter(i => !i.is_label).length;
  const stackNonLbl  = (codegen.stack || []).filter(i => !i.is_label).length;
  const astLines     = (codegen.ast_text || []).length;
  const setBadge = (id, txt) => { const el = document.getElementById(id); if (el) el.textContent = txt; };
  setBadge('ipanel-tac-badge',   `${tacNonLabel} instrucciones`);
  setBadge('ipanel-stack-badge', `${stackNonLbl} instrucciones`);
  setBadge('ipanel-ast-badge',   `${astLines} líneas`);

  /* ── TAC ── */
  _renderInstrTable(codegen.tac,   'inter-body-tac',   'inter-empty-tac');

  /* ── Stack ── */
  _renderInstrTable(codegen.stack, 'inter-body-stack', 'inter-empty-stack');

  /* ── AST text ── */
  const pre   = document.getElementById('inter-body-ast');
  const empty = document.getElementById('inter-empty-ast');
  const lines = codegen.ast_text || [];
  if (!lines.length) {
    if (pre)   pre.style.display   = 'none';
    if (empty) empty.style.display = 'flex';
  } else {
    if (empty) empty.style.display = 'none';
    if (pre) {
      pre.style.display = 'block';
      pre.innerHTML = lines.map(line => {
        let s = esc(line);
        s = s.replace(/(└──|├──|│)/g,  '<span style="color:rgba(195,166,255,.35);">$1</span>');
        s = s.replace(/(\s+\[.*?\])/g, '<span class="ast-meta">$1</span>');
        s = s.replace(/(\s+:\d+)/g,    '<span class="ast-ln">$1</span>');
        return `<span class="ast-label">${s}</span>`;
      }).join('\n');
    }
  }

  /* Resaltar TAC por defecto */
  setInterFocus('tac');
}

/* =====================================================================
   OPTIMIZACIÓN — renderizado de la vista de comparación
   ===================================================================== */

let _optimData    = null;
let _optimLogOpen = true;
let _optimView    = 'compare';   // 'compare' | 'diff'

/* Mapa de técnicas: nombre del backend → metadatos de display */
const _TECH_META = {
  'Plegado de constantes':        { key: 'constant_folding',    short: 'folding',    color: '#FF6B6B' },
  'Propagación de constantes':    { key: 'constant_propagation',short: 'const prop', color: '#F5CB5C' },
  'Simplificación algebraica':    { key: 'algebraic',           short: 'algebraic',  color: '#FFE66D' },
  'Propagación de copias':        { key: 'copy_propagation',    short: 'copy prop',  color: '#85C1E9' },
  'Eliminación de código muerto': { key: 'dead_code',           short: 'dead code',  color: '#FF4500' },
};
/* Mapa inverso: key del optimizador → metadatos */
const _TECH_META_BY_KEY = {};
for (const [name, meta] of Object.entries(_TECH_META)) {
  _TECH_META_BY_KEY[meta.key] = { ...meta, name };
}

/* ── LCS sobre arrays de strings ── */
function _lcs(a, b) {
  const m = a.length, n = b.length;
  /* Para tamaños grandes usamos greedy matching en vez de O(mn) */
  if (m * n > 40000) return _greedyDiff(a, b);
  const dp = Array.from({length: m + 1}, () => new Int32Array(n + 1));
  for (let i = 1; i <= m; i++)
    for (let j = 1; j <= n; j++)
      dp[i][j] = a[i-1] === b[j-1]
        ? dp[i-1][j-1] + 1
        : Math.max(dp[i-1][j], dp[i][j-1]);
  const ops = [];
  let i = m, j = n;
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && a[i-1] === b[j-1]) {
      ops.unshift({type:'=', ai:i-1, bi:j-1}); i--; j--;
    } else if (j > 0 && (i === 0 || dp[i][j-1] >= dp[i-1][j])) {
      ops.unshift({type:'+', bi:j-1}); j--;
    } else {
      ops.unshift({type:'-', ai:i-1}); i--;
    }
  }
  return ops;
}

function _greedyDiff(a, b) {
  /* Fallback: mark everything as removed then added */
  return [
    ...a.map((_,i) => ({type:'-', ai:i})),
    ...b.map((_,j) => ({type:'+', bi:j})),
  ];
}

/* ── Inline token-level diff entre dos strings ── */
function _inlineDiff(strA, strB) {
  const tokA = strA.split(/(\s+)/);
  const tokB = strB.split(/(\s+)/);
  const ops  = _lcs(tokA, tokB);
  return ops.map(op => {
    if (op.type === '=')  return esc(tokA[op.ai]);
    if (op.type === '-')  return `<span class="diff-token-del">${esc(tokA[op.ai])}</span>`;
    /* '+' */             return `<span class="diff-token-add">${esc(tokB[op.bi])}</span>`;
  }).join('');
}

/* ── Construye lista de entradas diff ── */
function _computeDiff(origList, optimList) {
  const toStr = ins => ins.instr || '';
  const aStr  = origList.map(toStr);
  const bStr  = optimList.map(toStr);
  const ops   = _lcs(aStr, bStr);

  /* Pair up consecutive remove+add as "modified" */
  const entries = [];
  let k = 0;
  while (k < ops.length) {
    const op = ops[k];
    if (op.type === '-' && k + 1 < ops.length && ops[k+1].type === '+') {
      /* Modified pair */
      const insA = origList[op.ai];
      const insB = optimList[ops[k+1].bi];
      entries.push({
        type: 'modified-del',
        instr: insA.instr, ln: insA.ln, is_label: insA.is_label,
        inlineHtml: _inlineDiff(insA.instr, insB.instr),
        pairIdx: entries.length,
      });
      entries.push({
        type: 'modified-add',
        instr: insB.instr, ln: insB.ln, is_label: insB.is_label,
        inlineHtml: _inlineDiff(insA.instr, insB.instr),
        pairIdx: entries.length - 1,
      });
      k += 2;
    } else if (op.type === '-') {
      const ins = origList[op.ai];
      entries.push({type:'removed',   instr:ins.instr, ln:ins.ln, is_label:ins.is_label});
      k++;
    } else if (op.type === '+') {
      const ins = optimList[op.bi];
      entries.push({type:'added',     instr:ins.instr, ln:ins.ln, is_label:ins.is_label});
      k++;
    } else {
      const ins = origList[op.ai];
      entries.push({type:'unchanged', instr:ins.instr, ln:ins.ln, is_label:ins.is_label});
      k++;
    }
  }
  return entries;
}

/* =====================================================================
   MINI-MAP — canvas lateral que muestra una vista aérea del diff
   ===================================================================== */

let _minimapEntries = null;
let _minimapRO      = null;   // ResizeObserver

const _MM_COLORS = {
  'removed':      'rgba(255,0,64,.75)',
  'modified-del': 'rgba(255,80,0,.7)',
  'added':        'rgba(87,255,0,.65)',
  'modified-add': 'rgba(60,220,0,.55)',
  'unchanged':    'rgba(255,255,255,.055)',
  'label':        'rgba(145,192,253,.13)',
};

function _paintMinimap() {
  const wrap   = document.getElementById('diff-minimap-wrap');
  const canvas = document.getElementById('diff-minimap-canvas');
  if (!wrap || !canvas) return;

  const W = wrap.clientWidth;
  const H = wrap.clientHeight;
  if (!W || !H) return;

  canvas.width  = W;
  canvas.height = H;

  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, W, H);

  const entries = _minimapEntries;
  if (!entries || !entries.length) return;

  const rowH  = H / entries.length;
  const barW  = W - 4;

  entries.forEach((e, i) => {
    const color = e.is_label
      ? _MM_COLORS['label']
      : (_MM_COLORS[e.type] || _MM_COLORS['unchanged']);
    ctx.fillStyle = color;
    const y = i * rowH;
    ctx.fillRect(2, y, barW, Math.max(1, rowH - 0.3));
  });

  _updateMinimapThumb();
}

function _updateMinimapThumb() {
  const scroller = document.getElementById('oscroll-diff');
  const wrap     = document.getElementById('diff-minimap-wrap');
  const thumb    = document.getElementById('diff-minimap-thumb');
  if (!scroller || !wrap || !thumb) return;

  const H       = wrap.clientHeight;
  const scrollH = scroller.scrollHeight;
  const clientH = scroller.clientHeight;

  if (!H || scrollH <= clientH) {
    thumb.style.display = 'none';
    return;
  }
  thumb.style.display = 'block';

  const ratio   = clientH / scrollH;
  const thumbH  = Math.max(14, ratio * H);
  const maxTop  = H - thumbH;
  const thumbY  = Math.min(maxTop, (scroller.scrollTop / scrollH) * H);

  thumb.style.height = thumbH + 'px';
  thumb.style.top    = thumbY  + 'px';
}

function _minimapScrollTo(clientY) {
  const wrap     = document.getElementById('diff-minimap-wrap');
  const scroller = document.getElementById('oscroll-diff');
  if (!wrap || !scroller) return;
  const rect  = wrap.getBoundingClientRect();
  const ratio = Math.max(0, Math.min(1, (clientY - rect.top) / wrap.clientHeight));
  scroller.scrollTop = ratio * scroller.scrollHeight;
}

function _setupMinimapInteraction() {
  const wrap     = document.getElementById('diff-minimap-wrap');
  const scroller = document.getElementById('oscroll-diff');
  if (!wrap || !scroller) return;

  /* Scroll → update thumb */
  scroller.addEventListener('scroll', _updateMinimapThumb);

  /* Click / drag on minimap → scroll content */
  let dragging = false;
  wrap.addEventListener('mousedown', e => {
    dragging = true;
    _minimapScrollTo(e.clientY);
    e.preventDefault();
  });
  document.addEventListener('mousemove', e => {
    if (dragging) _minimapScrollTo(e.clientY);
  });
  document.addEventListener('mouseup', () => { dragging = false; });

  /* Wheel on minimap → scroll content */
  wrap.addEventListener('wheel', e => {
    scroller.scrollTop += e.deltaY;
    e.preventDefault();
  }, {passive: false});

  /* ResizeObserver: redraw if panel size changes */
  if (window.ResizeObserver) {
    if (_minimapRO) _minimapRO.disconnect();
    _minimapRO = new ResizeObserver(() => {
      if (_minimapEntries) _paintMinimap();
    });
    _minimapRO.observe(wrap);
  }

  /* Hint tooltip */
  wrap.dataset.hint = 'mini-mapa';
}

/* ── Renderiza el panel de diff unificado ── */
function _renderDiffPanel(entries) {
  const body  = document.getElementById('obody-diff');
  const empty = document.getElementById('oempty-diff');
  const badge = document.getElementById('obadge-diff');
  if (!body) return;

  if (!entries || !entries.length) {
    body.innerHTML = '';
    if (empty) empty.style.display = 'flex';
    return;
  }
  if (empty) empty.style.display = 'none';

  const removed   = entries.filter(e => e.type === 'removed'      || e.type === 'modified-del').length;
  const added     = entries.filter(e => e.type === 'added'        || e.type === 'modified-add').length;
  const unchanged = entries.filter(e => e.type === 'unchanged').length;
  if (badge) badge.textContent = `−${removed}  +${added}  =${unchanged}`;

  /* Almacena entradas para el minimap */
  _minimapEntries = entries;

  let lineN = 0;
  body.innerHTML = entries.map((e, idx) => {
    const isLabel   = e.is_label;
    if (!isLabel && (e.type === 'unchanged' || e.type === 'added' || e.type === 'modified-add')) lineN++;
    const lineNum   = isLabel ? '' : lineN;

    let rowCls, gutter, instrHtml;
    switch (e.type) {
      case 'removed':
        rowCls    = 'orow diff-removed';
        gutter    = '−';
        instrHtml = esc(e.instr);
        break;
      case 'added':
        rowCls    = 'orow diff-added';
        gutter    = '+';
        instrHtml = esc(e.instr);
        break;
      case 'modified-del':
        rowCls    = 'orow diff-removed diff-pair-connector';
        gutter    = '~';
        instrHtml = e.inlineHtml;
        break;
      case 'modified-add':
        rowCls    = 'orow diff-added diff-pair-connector';
        gutter    = '~';
        instrHtml = e.inlineHtml;
        break;
      default: /* unchanged */
        rowCls    = 'orow diff-unchanged';
        gutter    = ' ';
        instrHtml = esc(e.instr);
    }
    return `<div class="${rowCls} is-diff" data-diff-idx="${idx}">
      <span class="diff-gutter">${gutter}</span>
      <span class="orow-n">${isLabel ? '' : lineNum}</span>
      <span class="orow-instr">${instrHtml}</span>
    </div>`;
  }).join('');
}

/* ── Alterna entre Comparación / Diff / Trazado ── */
function toggleOptimView(mode) {
  /* Pausar animación si se sale del trazado */
  if (_traceTimer && mode !== 'trace') {
    clearInterval(_traceTimer);
    _traceTimer = null;
    const pb = document.getElementById('trace-play-btn');
    if (pb) { pb.textContent = '▶ Reproducir'; pb.classList.remove('playing'); }
  }

  _optimView = mode;
  const compare = document.getElementById('optim-compare-panels');
  const diff    = document.getElementById('optim-diff-panel');
  const trace   = document.getElementById('optim-trace-panel');
  const btnCmp  = document.getElementById('diff-btn-compare');
  const btnDiff = document.getElementById('diff-btn-diff');
  const btnTrc  = document.getElementById('diff-btn-trace');
  const hint    = document.getElementById('diff-toolbar-hint');

  /* Ocultar todo primero */
  if (compare) compare.style.display = 'none';
  if (diff)    diff.style.display    = 'none';
  if (trace)   trace.style.display   = 'none';
  [btnCmp, btnDiff, btnTrc].forEach(b => b && b.classList.remove('active'));

  if (mode === 'diff') {
    if (diff)    diff.style.display = 'flex';
    if (btnDiff) btnDiff.classList.add('active');
    if (hint && _optimData) {
      const d = _optimData._diffEntries || [];
      const r = d.filter(e => e.type==='removed'||e.type==='modified-del').length;
      const a = d.filter(e => e.type==='added'  ||e.type==='modified-add').length;
      hint.textContent = r || a ? `${r} eliminadas · ${a} añadidas/modificadas` : 'Sin cambios';
    }
    requestAnimationFrame(() => { _paintMinimap(); });
  } else if (mode === 'trace') {
    if (trace)  trace.style.display = 'flex';
    if (btnTrc) btnTrc.classList.add('active');
    if (hint)   hint.textContent = '';
    /* Renderizar el frame actual si ya hay datos de trazado */
    if (_traceData) _traceRenderFrame(_traceCurFrame >= 0 ? _traceCurFrame : 0);
  } else {  /* compare (default) */
    if (compare) compare.style.display = 'flex';
    if (btnCmp)  btnCmp.classList.add('active');
    if (hint)    hint.textContent = '';
  }
}

function toggleOptimLog() {
  _optimLogOpen = !_optimLogOpen;
  const wrap   = document.getElementById('olog-entries-wrap');
  const toggle = document.getElementById('olog-toggle');
  if (wrap)   wrap.style.display  = _optimLogOpen ? '' : 'none';
  if (toggle) toggle.textContent  = _optimLogOpen ? '▲ ocultar' : '▼ mostrar';
}

function _renderOptimPanel(instructions, bodyId, emptyId, markChanged) {
  const body  = document.getElementById(bodyId);
  const empty = document.getElementById(emptyId);
  if (!body) return;
  if (!instructions || !instructions.length) {
    body.innerHTML = '';
    if (empty) empty.style.display = 'flex';
    return;
  }
  if (empty) empty.style.display = 'none';
  let n = 0;
  body.innerHTML = instructions.map(ins => {
    const isLabel   = ins.is_label;
    if (!isLabel) n++;
    const tag       = markChanged ? (ins._tag || '') : '';
    const technique = markChanged ? (ins._technique || '') : '';
    const techMeta  = technique ? (_TECH_META_BY_KEY[technique] || null) : null;
    const rowCls    = ['orow',
      isLabel              ? 'is-label'  : '',
      tag === 'modified'   ? 'modified'  : '',
      tag === 'eliminated' ? 'eliminated': '',
    ].filter(Boolean).join(' ');
    const techHtml  = techMeta
      ? `<span class="orow-tech" style="color:${techMeta.color};">← ${techMeta.short}</span>`
      : '<span class="orow-tech"></span>';
    return `<div class="${rowCls}">
      <span class="orow-n">${isLabel ? '' : n}</span>
      <span class="orow-instr">${_highlightInstr(ins.instr)}</span>
      ${techHtml}
      <span class="orow-ln">${ins.ln || ''}</span>
    </div>`;
  }).join('');
}

function renderOptimization(optim) {
  _optimData = optim;
  const stats = optim.stats || {};

  /* ── Sidebar stats ── */
  const orig    = stats.original_count  || 0;
  const optimN  = stats.optimized_count || 0;
  const removed = stats.removed         || 0;
  const pct     = orig > 0 ? Math.round(removed / orig * 100) : 0;

  const _t = (id, v) => { const e = document.getElementById(id); if (e) e.textContent = v; };
  _t('ost-orig',    orig);
  _t('ost-optim',   optimN);
  _t('ost-removed', removed);
  _t('ost-pct',     pct + '%');
  _t('ost-changes', stats.changes_count || 0);
  _t('ost-passes',  stats.passes_run    || 0);

  /* ── Barra de reducción ── */
  const barFill = document.getElementById('ost-pct-bar');
  if (barFill) barFill.style.width = Math.min(100, pct) + '%';

  /* ── Técnicas con colores y conteos ── */
  const techList   = document.getElementById('otech-list');
  const techs      = stats.techniques  || [];
  const techCounts = stats.tech_counts || {};
  if (techList) {
    if (!techs.length) {
      techList.innerHTML = '<div class="otech-empty">Sin optimizaciones aplicadas</div>';
    } else {
      techList.innerHTML = techs.map(tName => {
        const meta  = _TECH_META[tName] || { color: '#888', short: tName };
        const count = techCounts[tName] || 0;
        return `<div class="otech-item">
          <span class="otech-dot" style="background:${meta.color};box-shadow:0 0 5px ${meta.color}4d;"></span>
          <span class="otech-name" style="color:${meta.color};">${esc(tName)}</span>
          <span class="otech-count" style="color:${meta.color};border:1px solid ${meta.color}40;">×${count}</span>
        </div>`;
      }).join('');
    }
  }

  /* ── ESTADO section ── */
  const changes    = optim.changes || [];
  const hasOptim   = changes.length > 0;
  _t('ost-errors',   '0');
  _t('ost-warnings', hasOptim ? '0' : (orig > 0 ? '0' : '—'));
  _t('ost-estado',   orig > 0 ? 'OK ✓' : '—');
  const estadoEl = document.getElementById('ost-estado');
  if (estadoEl) estadoEl.style.color = orig > 0 ? '#57FF00' : '';

  /* ── Badges de paneles ── */
  _t('obadge-orig',  `${orig} instrucciones`);
  _t('obadge-optim', `${optimN} instrucciones${removed > 0 ? ' (−' + removed + ')' : ''}`);

  /* ── Toolbar stats badges ── */
  const diffEntries   = _computeDiff(optim.original || [], optim.optimized || []);
  optim._diffEntries  = diffEntries;

  const dRemoved  = diffEntries.filter(e => e.type==='removed' || e.type==='modified-del').length;
  const dAdded    = diffEntries.filter(e => e.type==='added'   || e.type==='modified-add').length;
  const dModified = diffEntries.filter(e => e.type==='modified-del').length;
  const statsDiv  = document.getElementById('diff-toolbar-stats');
  if (statsDiv) statsDiv.style.display = (dRemoved || dAdded || dModified) ? 'flex' : 'none';
  _t('dts-removed',  `−${dRemoved} eliminadas`);
  _t('dts-added',    `+${dAdded} añadidas`);
  _t('dts-modified', `~${dModified} modificadas`);

  /* ── Paneles comparación ── */
  _renderOptimPanel(optim.original, 'obody-orig', 'oempty-orig', false);
  /* Si el TAC optimizado quedó vacío (todo eliminado como código muerto),
     mostrar las instrucciones originales tachadas en el panel derecho */
  const optimDisplay = (optim.optimized && optim.optimized.length)
    ? optim.optimized
    : (optim.original || []).map(ins => ({ ...ins, _tag: 'eliminated', _technique: 'dead_code' }));
  _renderOptimPanel(optimDisplay, 'obody-optim', 'oempty-optim', true);

  /* ── Diff unificado ── */
  _renderDiffPanel(diffEntries);
  /* Siempre restaurar la vista activa (compare o diff) */
  toggleOptimView(_optimView);

  /* ── Log de cambios ── */
  const entries    = document.getElementById('olog-entries');
  const logEmpty   = document.getElementById('olog-empty');
  const badge      = document.getElementById('olog-badge');

  if (badge) badge.textContent = `${changes.length} cambio${changes.length !== 1 ? 's' : ''}`;

  if (!changes.length) {
    if (entries)  entries.innerHTML = '';
    if (logEmpty) logEmpty.style.display = 'block';
  } else {
    if (logEmpty) logEmpty.style.display = 'none';
    if (entries) {
      entries.innerHTML = changes.map(c => {
        const meta     = _TECH_META[c.pass] || {};
        const techColor = meta.color || 'rgba(255,0,64,.8)';
        return `<div class="optim-log-entry">
          <span class="ole-pass" style="color:${techColor};">${esc(c.pass)}</span>
          <span class="ole-before">${esc(c.before)}</span>
          <span class="ole-arrow">→</span>
          <span class="ole-after${c.after === '(eliminado)' ? ' deleted' : ''}">${esc(c.after)}</span>
        </div>`;
      }).join('');
    }
  }

  /* ── Inicializar trazado con los nuevos datos ── */
  if (optim.trace) renderTrace(optim);
}

/* =====================================================================
   TRAZADO PASO A PASO
   Motor de animación que muestra instrucción por instrucción cómo el
   optimizador transforma el TAC a lo largo de cada pasada e iteración.
   ===================================================================== */

let _traceData     = null;
let _traceCurFrame = -1;
let _traceTimer    = null;
let _traceSpeed    = 1;

const _TRACE_META = {
  scan:      { label: 'Escaneando',                 color: 'rgba(204,204,204,.45)', icon: '○' },
  fold:      { label: 'Plegado de constante',       color: '#FF6B6B',              icon: '⬤' },
  propagate: { label: 'Propagación de constante',   color: '#F5CB5C',              icon: '⬤' },
  simplify:  { label: 'Simplificación algebraica',  color: '#FFE66D',              icon: '⬤' },
  copy:      { label: 'Propagación de copia',       color: '#85C1E9',              icon: '⬤' },
  eliminate: { label: 'Código muerto eliminado',    color: 'var(--optimizacion-color)', icon: '⬤' },
};

const _TRACE_BADGE_LABELS = {
  scan: 'escaneando', fold: '→ pliegue', propagate: '→ prop.',
  simplify: '→ simpl.', copy: '→ copia', eliminate: '✗ eliminar',
};

const _PASS_SHORT = ['', 'Plegado', 'Prop.Cte', 'Algebraica', 'Prop.Copia', 'Cód.Muerto'];

/* ── Reconstruye la lista de instrucciones en el frame idx (replay) ── */
function _traceComputeState(frameIdx) {
  if (!_traceData) return [];
  const state = [..._traceData.initial_state];
  for (let i = 0; i <= frameIdx; i++) {
    const f = _traceData.frames[i];
    if (f.action === 'eliminate') {
      if (f.focus >= 0 && f.focus < state.length) state.splice(f.focus, 1);
    } else if (f.changed && f.after !== undefined && f.focus >= 0 && f.focus < state.length) {
      state[f.focus] = f.after;
    }
  }
  return state;
}

/* ── Scroll al foco sin animación brusca ── */
function _traceScrollToFocus(focusIdx) {
  const scroll = document.getElementById('trace-scroll');
  if (!scroll) return;
  const rows = scroll.querySelectorAll('.trace-row');
  if (focusIdx < 0 || focusIdx >= rows.length) return;
  const row = rows[focusIdx];
  const top = row.offsetTop, rowH = row.offsetHeight;
  const st  = scroll.scrollTop, sh = scroll.clientHeight;
  if (top < st + 16 || top + rowH > st + sh - 16) {
    scroll.scrollTop = top - sh / 2 + rowH / 2;
  }
}

/* ── Actualiza la línea de tiempo de las 5 pasadas ── */
function _traceUpdateTimeline(frame) {
  const el = document.getElementById('trace-pass-timeline');
  if (!el) return;
  const cur = frame.pass_num;
  const passes = [[1,'Plegado'],[2,'Prop.Cte'],[3,'Algebraica'],[4,'Prop.Copia'],[5,'Cód.Muerto']];
  const label = `<div class="trace-tl-label">Pasadas · It.${frame.iter}</div>`;
  const dots  = passes.map(([n, name]) => {
    const cls = n < cur ? 'done' : n === cur ? 'active' : '';
    return `<div class="trace-tl-pass ${cls}"><span class="trace-tl-dot"></span><span>${name}</span></div>`;
  }).join('');
  el.innerHTML = label + `<div class="trace-tl-passes">${dots}</div>`;

  const ii = document.getElementById('trace-iter-info');
  if (ii && _traceData && _traceData.frames.length) {
    const maxIter = _traceData.frames[_traceData.frames.length - 1].iter;
    ii.textContent = `Iteración ${frame.iter} / ${maxIter}`;
  }
}

/* ── Renderiza el estado del frame idx ── */
function _traceRenderFrame(frameIdx) {
  if (!_traceData || !_traceData.frames.length) return;
  frameIdx = Math.max(0, Math.min(frameIdx, _traceData.frames.length - 1));
  _traceCurFrame = frameIdx;

  const frame = _traceData.frames[frameIdx];
  const state = _traceComputeState(frameIdx);
  const total = _traceData.frames.length;

  /* Barra de progreso */
  const pct = Math.round((frameIdx + 1) / total * 100);
  const pfEl = document.getElementById('trace-progress-fill');
  if (pfEl) pfEl.style.width = pct + '%';
  const ctr = document.getElementById('trace-frame-ctr');
  if (ctr) ctr.textContent = `Paso ${frameIdx + 1} / ${total}`;
  const itEl = document.getElementById('trace-iter');
  if (itEl) itEl.textContent = `It.${frame.iter}`;
  const pnEl = document.getElementById('trace-pass-name');
  if (pnEl) pnEl.textContent = frame.pass;

  /* Lista de instrucciones */
  const body = document.getElementById('trace-instr-body');
  if (body) {
    body.innerHTML = state.map((instr, i) => {
      const isFocus  = i === frame.focus;
      const actCls   = isFocus && frame.action !== 'scan' ? `trace-${frame.action}` : '';
      const cls      = ['trace-row', isFocus ? 'trace-focus' : '', actCls].filter(Boolean).join(' ');
      const badge    = isFocus
        ? `<span class="trace-badge ${frame.action}">${_TRACE_BADGE_LABELS[frame.action] || frame.action}</span>`
        : '<span></span>';
      return `<div class="${cls}">
        <span class="trace-row-n">${i + 1}</span>
        <span class="trace-row-instr">${_highlightInstr(instr)}</span>
        ${badge}
      </div>`;
    }).join('');
    _traceScrollToFocus(frame.focus);
  }

  /* Panel de información */
  const meta    = _TRACE_META[frame.action] || _TRACE_META.scan;
  const iconEl  = document.getElementById('trace-action-icon');
  const titleEl = document.getElementById('trace-action-title');
  const descEl  = document.getElementById('trace-action-desc');
  if (iconEl)  { iconEl.textContent = meta.icon; iconEl.style.color = meta.color; }
  if (titleEl) { titleEl.textContent = meta.label; titleEl.style.color = meta.color; }
  if (descEl) {
    if (frame.changed && frame.before !== undefined) {
      const afterHtml = frame.after === '(eliminado)'
        ? `<span style="color:rgba(255,0,64,.7);font-style:italic;">(eliminado)</span>`
        : `<span class="trace-after">${esc(frame.after)}</span>`;
      descEl.innerHTML =
        `<span class="trace-before">${esc(frame.before)}</span>` +
        `<span style="color:rgba(255,255,255,.3);"> → </span>` +
        afterHtml +
        (frame.desc ? `<br><span class="trace-rule">${esc(frame.desc)}</span>` : '');
    } else {
      descEl.innerHTML = `<span style="color:rgba(255,255,255,.2);">${esc(state[frame.focus] || '—')}</span>`;
    }
  }

  _traceUpdateTimeline(frame);
}

/* ─── API pública ─── */

function renderTrace(optim) {
  const t = optim && optim.trace;
  if (!t || !t.frames || !t.frames.length) return;
  _traceData     = t;
  _traceCurFrame = 0;
  if (_traceTimer) { clearInterval(_traceTimer); _traceTimer = null; }
  const btn = document.getElementById('trace-play-btn');
  if (btn) { btn.textContent = '▶ Reproducir'; btn.classList.remove('playing'); }
  /* Solo renderiza si la vista de trazado ya está activa */
  if (_optimView === 'trace') _traceRenderFrame(0);
}

function traceSeek(n) {
  if (!_traceData) return;
  _traceRenderFrame(n < 0 ? _traceData.frames.length - 1 : n);
}

function traceStep(delta) {
  if (!_traceData) return;
  _traceRenderFrame(_traceCurFrame + delta);
}

function _traceAdvance() {
  if (!_traceData) return;
  const next = _traceCurFrame + 1;
  if (next >= _traceData.frames.length) {
    clearInterval(_traceTimer); _traceTimer = null;
    const btn = document.getElementById('trace-play-btn');
    if (btn) { btn.textContent = '▶ Reproducir'; btn.classList.remove('playing'); }
    return;
  }
  _traceRenderFrame(next);
}

function traceTogglePlay() {
  if (_traceTimer) {
    clearInterval(_traceTimer); _traceTimer = null;
    const btn = document.getElementById('trace-play-btn');
    if (btn) { btn.textContent = '▶ Reproducir'; btn.classList.remove('playing'); }
  } else {
    if (!_traceData) return;
    /* Si está al final, reiniciar desde el inicio */
    if (_traceCurFrame >= _traceData.frames.length - 1) _traceCurFrame = -1;
    _traceAdvance();  /* primer avance inmediato */
    const delay = Math.round(420 / _traceSpeed);
    _traceTimer = setInterval(_traceAdvance, delay);
    const btn = document.getElementById('trace-play-btn');
    if (btn) { btn.textContent = '⏸ Pausar'; btn.classList.add('playing'); }
  }
}

function traceSetSpeed(s) {
  _traceSpeed = s;
  ['h','1','2','4'].forEach(k => {
    const el = document.getElementById(`tspd-${k}`);
    if (el) el.classList.remove('active');
  });
  const keyMap = {0.5:'h', 1:'1', 2:'2', 4:'4'};
  const el = document.getElementById(`tspd-${keyMap[s] || '1'}`);
  if (el) el.classList.add('active');
  /* Reiniciar timer si está reproduciendo */
  if (_traceTimer) {
    clearInterval(_traceTimer);
    const delay = Math.round(420 / _traceSpeed);
    _traceTimer = setInterval(_traceAdvance, delay);
  }
}

/* ══ CÓDIGO OBJETO ══════════════════════════════════════════════════════ */

let _objectData = null;

function _obEsc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function _hlObj(code) {
  if (!code || !code.trim()) return _obEsc(code);
  let s = _obEsc(code);
  s = s.replace(/\b(MOVI|LOAD|STORE|MOVE|ADD|SUB|MUL|DIV|IDIV|MOD|POW|NEG|NOT|AND|OR|CMP|SETF|JMP|JZ|JNZ|PUSH|POP|CALL|RET|HALT|PROC|ENDP)\b/g,
      '<span class="ob-op-hl">$1</span>');
  s = s.replace(/\b(R[0-7])\b/g, '<span class="ob-reg-hl">$1</span>');
  s = s.replace(/(#-?\d[\d.]*)/g, '<span class="ob-num-hl">$1</span>');
  s = s.replace(/\b(0x[0-9A-Fa-f]+)\b/g, '<span class="ob-addr-hl">$1</span>');
  s = s.replace(/\b(\.data|\.code)\b/g, '<span class="ob-dir-hl">$1</span>');
  s = s.replace(/\b(DW|LR)\b/g, '<span class="ob-kw-hl">$1</span>');
  return s;
}

function renderObjectCode(obj) {
  _objectData = obj || {};
  const _t = (id, v) => { const e = document.getElementById(id); if (e) e.textContent = v; };

  /* Stats */
  const s = _objectData.stats || {};
  _t('ob-instr',  s.instr_count  ?? 0);
  _t('ob-regs',   s.regs_used    ?? 0);
  _t('ob-vars',   s.vars_count   ?? 0);
  _t('ob-labels', s.labels_count ?? 0);
  _t('ob-cycles', s.cycles_est   ?? 0);
  _t('ob-code-badge', `${s.instr_count ?? 0} instrucciones`);

  /* Listado de instrucciones */
  const codeBody  = document.getElementById('ob-code-body');
  const codeEmpty = document.getElementById('ob-code-empty');
  const instrs = _objectData.instructions || [];
  if (codeBody) {
    if (!instrs.length) {
      codeBody.innerHTML = '';
      if (codeEmpty) codeEmpty.style.display = 'flex';
    } else {
      if (codeEmpty) codeEmpty.style.display = 'none';
      let lineN = 0;
      codeBody.innerHTML = instrs.map(ins => {
        const isDir   = !!ins.is_directive;
        const isLabel = !!ins.is_label;
        if (!isDir && !isLabel && ins.instr && ins.instr.trim() && !ins.instr.startsWith(';')) lineN++;
        let cls = 'ob-row';
        if (isDir)   cls += ' ob-directive';
        if (isLabel) cls += ' ob-label';
        const lineNum = (isDir || isLabel || !ins.instr || !ins.instr.trim()) ? '' : lineN;
        const cmt     = ins.comment ? `; ${_obEsc(ins.comment)}` : '';
        return `<div class="${cls}"><span class="ob-row-n">${lineNum}</span><span class="ob-row-instr">${_hlObj(ins.instr)}</span><span class="ob-row-comment">${cmt}</span></div>`;
      }).join('');
    }
  }

  /* Archivo de registros */
  const regBody  = document.getElementById('ob-reg-body');
  const regEmpty = document.getElementById('ob-reg-empty');
  const regs     = _objectData.register_table || [];
  _t('ob-reg-badge', `${regs.length} registros`);
  if (regBody) {
    if (!regs.length) {
      regBody.innerHTML = '';
      if (regEmpty) regEmpty.style.display = 'flex';
    } else {
      if (regEmpty) regEmpty.style.display = 'none';
      const statusColor = {
        'activo': '#57FF00', 'libre': 'rgba(145,192,253,.4)',
        'reservado': '#F5CB5C', 'en uso': 'rgba(255,0,64,.7)'
      };
      regBody.innerHTML = regs.map(r =>
        `<div class="ob-reg-row"><span class="ob-reg-name">${_obEsc(r.reg)}</span><span class="ob-reg-assign">${_obEsc(r.assignment)}</span><span class="ob-reg-status" style="color:${statusColor[r.status]||'#ccc'}">${_obEsc(r.status)}</span></div>`
      ).join('');
    }
  }

  /* Segmento de datos */
  const dataBody  = document.getElementById('ob-data-body');
  const dataEmpty = document.getElementById('ob-data-empty');
  const dataSeg   = _objectData.data_segment || [];
  _t('ob-data-badge', `${dataSeg.length} entradas`);
  if (dataBody) {
    if (!dataSeg.length) {
      dataBody.innerHTML = '';
      if (dataEmpty) dataEmpty.style.display = 'flex';
    } else {
      if (dataEmpty) dataEmpty.style.display = 'none';
      dataBody.innerHTML = dataSeg.map(d =>
        `<div class="ob-data-row"><span class="ob-data-name" title="${_obEsc(d.name)}">${_obEsc(d.name)}</span><span class="ob-data-addr">${_obEsc(d.address)}</span><span class="ob-data-size">${_obEsc(d.size)}</span><span class="ob-data-init">${_obEsc(d.init)}</span></div>`
      ).join('');
    }
  }

  /* Log de asignación */
  const logBody  = document.getElementById('ob-log-body');
  const logBadge = document.getElementById('ob-log-badge');
  const logItems = _objectData.log || [];
  if (logBadge) logBadge.textContent = `${logItems.length} ops`;
  if (logBody) {
    logBody.innerHTML = logItems.length
      ? logItems.map(l => `<div class="ob-log-entry">${_obEsc(l)}</div>`).join('')
      : '<div class="empty-state" style="height:50px;"><div class="empty-text" style="color:rgba(0,212,255,.3);">Sin asignaciones</div></div>';
  }
}

function clearObjectCodeState() {
  _objectData = null;
  const _t = (id, v) => { const e = document.getElementById(id); if (e) e.textContent = v; };
  ['ob-instr','ob-regs','ob-vars','ob-labels','ob-cycles'].forEach(id => _t(id, '0'));
  _t('ob-code-badge', 'esperando compilación');
  _t('ob-reg-badge', '—');
  _t('ob-data-badge', '—');
  _t('ob-log-badge', '0 ops');
  ['ob-code-body','ob-reg-body','ob-data-body','ob-log-body'].forEach(id => {
    const el = document.getElementById(id); if (el) el.innerHTML = '';
  });
  ['ob-code-empty','ob-reg-empty','ob-data-empty'].forEach(id => {
    const el = document.getElementById(id); if (el) el.style.display = 'flex';
  });
}


function clearIntermediateState() {
  _codegenData = null;
  _optimData   = null;
  /* Limpiar paneles de código intermedio */
  ['tac', 'stack'].forEach(k => {
    const body  = document.getElementById(`inter-body-${k}`);
    const empty = document.getElementById(`inter-empty-${k}`);
    if (body)  body.innerHTML = '';
    if (empty) empty.style.display = 'flex';
    const badge = document.getElementById(`ipanel-${k}-badge`);
    if (badge) badge.textContent = '0 instrucciones';
  });
  const astPre   = document.getElementById('inter-body-ast');
  const astEmpty = document.getElementById('inter-empty-ast');
  if (astPre)   { astPre.innerHTML = ''; astPre.style.display = 'none'; }
  if (astEmpty) astEmpty.style.display = 'flex';
  const astBadge = document.getElementById('ipanel-ast-badge');
  if (astBadge) astBadge.textContent = '—';
  ['ist-instr', 'ist-temp', 'ist-ops', 'ist-err'].forEach(id => {
    const el = document.getElementById(id); if (el) el.textContent = '0';
  });
  const optim = document.getElementById('ist-optim');
  if (optim) { optim.textContent = 'No'; optim.style.color = '#F5CB5C'; }
  const logCount = document.getElementById('ilog-count');
  if (logCount) { logCount.textContent = '✓ 0 instrucciones generadas'; logCount.classList.add('ilog-pending'); }
  setInterFocus('tac');
  /* Limpiar vista de optimización */
  ['obody-orig', 'obody-optim'].forEach(id => {
    const el = document.getElementById(id); if (el) el.innerHTML = '';
  });
  ['oempty-orig', 'oempty-optim'].forEach(id => {
    const el = document.getElementById(id); if (el) el.style.display = 'flex';
  });
  ['ost-orig','ost-optim','ost-removed','ost-changes','ost-passes'].forEach(id => {
    const el = document.getElementById(id); if (el) el.textContent = '0';
  });
  const pctEl = document.getElementById('ost-pct'); if (pctEl) pctEl.textContent = '0%';
  ['obadge-orig','obadge-optim'].forEach(id => {
    const el = document.getElementById(id); if (el) el.textContent = 'esperando compilación';
  });
  const techList = document.getElementById('otech-list');
  if (techList) techList.innerHTML = '<div class="otech-empty">Compila para ver técnicas</div>';
  ['ost-errors','ost-warnings'].forEach(id => { const e=document.getElementById(id); if(e) e.textContent='0'; });
  const estadoEl2 = document.getElementById('ost-estado'); if(estadoEl2) { estadoEl2.textContent='—'; estadoEl2.style.color=''; }
  const barFill2 = document.getElementById('ost-pct-bar'); if(barFill2) barFill2.style.width='0%';
  const statsDiv2 = document.getElementById('diff-toolbar-stats'); if(statsDiv2) statsDiv2.style.display='none';
  const ologBadge = document.getElementById('olog-badge');
  if (ologBadge) ologBadge.textContent = '0 cambios';
  const ologEntries = document.getElementById('olog-entries');
  if (ologEntries) ologEntries.innerHTML = '';
  const ologEmpty = document.getElementById('olog-empty');
  if (ologEmpty) { ologEmpty.textContent = 'Sin cambios — compila primero'; ologEmpty.style.display = 'block'; }
  /* Limpiar panel diff unificado */
  const diffBody  = document.getElementById('obody-diff');
  if (diffBody)   diffBody.innerHTML = '';
  const diffEmpty = document.getElementById('oempty-diff');
  if (diffEmpty)  diffEmpty.style.display = 'flex';
  const diffBadge = document.getElementById('obadge-diff');
  if (diffBadge)  diffBadge.textContent = '—';
  const diffHint  = document.getElementById('diff-toolbar-hint');
  if (diffHint)   diffHint.textContent = '';
  /* Limpiar minimap */
  _minimapEntries = null;
  const mmCanvas = document.getElementById('diff-minimap-canvas');
  if (mmCanvas) {
    const ctx = mmCanvas.getContext('2d');
    ctx.clearRect(0, 0, mmCanvas.width, mmCanvas.height);
  }
  const mmThumb = document.getElementById('diff-minimap-thumb');
  if (mmThumb) mmThumb.style.display = 'none';
  /* Restablecer modo vista a comparación */
  _optimView = 'compare';
  toggleOptimView('compare');
}


/* ── Inicialización al cargar la página ── */
document.addEventListener('DOMContentLoaded', () => {
  _setupMinimapInteraction();
});
