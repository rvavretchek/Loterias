/* ============================================================
   MAIN.JS — Gerador de Loterias
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initNavbar();
  initDropdowns();
  initModal();
  // Auto-dismiss alerts after 5s
  document.querySelectorAll('.alert').forEach(a => setTimeout(() => a.remove(), 5000));
});

/* --- Theme --- */
function initTheme() {
  const toggle = document.getElementById('theme-toggle');
  if (!toggle) return;
  const saved = localStorage.getItem('theme');
  if (saved) document.documentElement.setAttribute('data-theme', saved);

  toggle.addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
    // Persist to server if logged in
    const csrf = getCSRF();
    if (csrf) {
      fetch('/conta/perfil/', {
        method: 'POST', headers: {'X-CSRFToken': csrf, 'Content-Type': 'application/x-www-form-urlencoded'},
        body: 'tema_preferido=' + next,
      }).catch(() => {});
    }
  });
}

/* --- Navbar --- */
function initNavbar() {
  const toggle = document.getElementById('navbar-toggle');
  const menu = document.getElementById('navbar-menu');
  if (!toggle || !menu) return;
  toggle.addEventListener('click', () => menu.classList.toggle('show'));
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.navbar')) menu.classList.remove('show');
  });
}

/* --- Dropdowns --- */
function initDropdowns() {
  const btn = document.getElementById('user-dropdown-btn');
  const menu = document.getElementById('user-dropdown-menu');
  if (!btn || !menu) return;
  btn.addEventListener('click', (e) => { e.stopPropagation(); menu.classList.toggle('show'); });
  document.addEventListener('click', () => menu.classList.remove('show'));
}

/* --- Modal --- */
function initModal() {
  const overlay = document.getElementById('modal-overlay');
  const closeBtn = document.getElementById('modal-close');
  if (!overlay) return;
  closeBtn?.addEventListener('click', closeModal);
  overlay.addEventListener('click', (e) => { if (e.target === overlay) closeModal(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });
}

function openModal(html) {
  const overlay = document.getElementById('modal-overlay');
  const body = document.getElementById('modal-body');
  body.innerHTML = html;
  overlay.classList.add('show');
  document.body.style.overflow = 'hidden';
}

function closeModal() {
  const overlay = document.getElementById('modal-overlay');
  overlay.classList.remove('show');
  document.body.style.overflow = '';
}

/* --- Toast --- */
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const icons = {success: 'fa-check-circle', error: 'fa-exclamation-circle', info: 'fa-info-circle', warning: 'fa-exclamation-triangle'};
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.innerHTML = `<i class="fas ${icons[type] || icons.info}" style="color:var(--${type === 'error' ? 'danger' : type})"></i> ${message}`;
  container.appendChild(toast);
  setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 300); }, 4000);
}

/* --- CSRF --- */
function getCSRF() {
  const cookie = document.cookie.split(';').find(c => c.trim().startsWith('csrftoken='));
  return cookie ? cookie.split('=')[1] : (document.querySelector('[name=csrfmiddlewaretoken]')?.value || '');
}

/* --- Number Ball HTML --- */
function renderNumberBall(num, color, delay, isHit, isTrevo) {
  const cls = ['number-ball'];
  if (isHit) cls.push('hit');
  if (isTrevo) cls.push('trevo');
  const bg = isTrevo ? '' : `background:${color};`;
  return `<div class="${cls.join(' ')}" style="${bg}animation-delay:${delay}ms">${String(num).padStart(2, '0')}</div>`;
}

function renderNumbersGrid(numbers, color, hitNumbers, isTrevo) {
  const hits = new Set(hitNumbers || []);
  return numbers.map((n, i) =>
    renderNumberBall(n, color, i * 40, hits.has(n), isTrevo)
  ).join('');
}

/* --- Game Generation (AJAX) --- */
function gerarJogo(formEl) {
  const formData = new FormData(formEl);
  const resultArea = document.getElementById('game-result-area');
  resultArea.innerHTML = '<div class="spinner" style="margin:2rem auto;display:block"></div>';
  resultArea.classList.add('has-result');

  fetch('/gerar/', { method: 'POST', body: formData, headers: {'X-CSRFToken': getCSRF()} })
    .then(r => r.json())
    .then(data => {
      if (!data.success) {
        resultArea.innerHTML = `<p style="color:var(--danger)">${JSON.stringify(data.errors)}</p>`;
        return;
      }
      let html = `<h3 style="color:${data.cor}">${data.tipo_jogo}</h3>`;
      html += `<div class="game-meta">Concurso ${data.numero_concurso} &bull; ${data.criado_em}</div>`;
      html += `<div class="numbers-grid">${renderNumbersGrid(data.numeros, data.cor)}</div>`;
      if (data.trevos && data.trevos.length) {
        html += `<h4 style="margin-top:1rem;color:var(--text-secondary)">Trevos</h4>`;
        html += `<div class="numbers-grid">${renderNumbersGrid(data.trevos, '', null, true)}</div>`;
      }
      if (data.foi_repetido) {
        html += `<p style="color:var(--warning);margin-top:.5rem"><i class="fas fa-exclamation-triangle"></i> Este jogo já existia no histórico.</p>`;
      }
      html += `<div class="game-actions">`;
      html += `<button class="btn btn-outline btn-sm" onclick="verDetalhes(${data.jogo_id})"><i class="fas fa-eye"></i> Detalhes</button>`;
      html += `<button class="btn btn-success btn-sm" onclick="refazerJogo(${data.jogo_id})"><i class="fas fa-redo"></i> Refazer</button>`;
      html += `</div>`;
      resultArea.innerHTML = html;
      showToast('Jogo gerado com sucesso!', 'success');
    })
    .catch(err => {
      resultArea.innerHTML = `<p style="color:var(--danger)">Erro ao gerar jogo.</p>`;
      showToast('Erro ao gerar jogo.', 'error');
    });
  return false;
}

/* --- Game Details Modal --- */
function verDetalhes(jogoId) {
  fetch(`/jogo/${jogoId}/`)
    .then(r => r.json())
    .then(data => {
      let html = `<h2 style="color:${data.cor}">${data.tipo_jogo}</h2>`;
      html += `<p class="modal-subtitle">Concurso ${data.numero_concurso} &bull; ${data.criado_em}</p>`;

      html += `<div class="modal-section"><h4>Números</h4>`;
      let hitNums = data.resultado_oficial ? data.resultado_oficial.dezenas : null;
      html += `<div class="numbers-grid">${renderNumbersGrid(data.numeros, data.cor, hitNums)}</div></div>`;

      if (data.trevos && data.trevos.length) {
        let hitTrevos = data.resultado_oficial ? data.resultado_oficial.trevos_sorteados : null;
        html += `<div class="modal-section"><h4>Trevos</h4>`;
        html += `<div class="numbers-grid">${renderNumbersGrid(data.trevos, '', hitTrevos, true)}</div></div>`;
      }

      if (data.aplica_regra_sequencia) {
        const cor = data.pares_sequenciais <= 1 ? 'var(--success)' : 'var(--danger)';
        html += `<p style="font-size:.85rem;color:${cor};text-align:center">Pares sequenciais: ${data.pares_sequenciais}</p>`;
      }

      if (data.conferido) {
        html += `<div class="modal-section" style="text-align:center;margin-top:1rem">`;
        html += `<span class="badge ${data.acertos >= 3 ? 'badge-success' : 'badge-info'}" style="font-size:.9rem;padding:.4rem 1rem">`;
        html += `${data.acertos} acertos</span>`;
        if (data.acertos_segundo_sorteio !== null) html += ` <span class="badge badge-info" style="font-size:.9rem;padding:.4rem 1rem">2º: ${data.acertos_segundo_sorteio}</span>`;
        if (data.acertos_trevos !== null) html += ` <span class="badge badge-warning" style="font-size:.9rem;padding:.4rem 1rem">Trevos: ${data.acertos_trevos}</span>`;
        html += `</div>`;
      }

      html += `<div class="modal-footer">`;
      html += `<button class="btn btn-success btn-sm" onclick="refazerJogo(${data.id})"><i class="fas fa-redo"></i> Refazer</button>`;
      if (!data.conferido) {
        html += `<button class="btn btn-primary btn-sm" onclick="conferirJogo(${data.id})"><i class="fas fa-check-double"></i> Conferir</button>`;
      }
      html += `<button class="btn btn-outline btn-sm" onclick="closeModal()">Fechar</button>`;
      html += `</div>`;

      openModal(html);
    })
    .catch(() => showToast('Erro ao carregar detalhes.', 'error'));
}

/* --- Redo Game --- */
function refazerJogo(jogoId) {
  closeModal();
  fetch(`/jogo/${jogoId}/refazer/`, { method: 'POST', headers: {'X-CSRFToken': getCSRF()} })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showToast('Novo jogo gerado!', 'success');
        verDetalhes(data.jogo_id);
      } else {
        showToast('Erro ao refazer jogo.', 'error');
      }
    })
    .catch(() => showToast('Erro ao refazer jogo.', 'error'));
}

/* --- Check Game --- */
function conferirJogo(jogoId) {
  fetch(`/jogo/${jogoId}/conferir/`, { method: 'POST', headers: {'X-CSRFToken': getCSRF()} })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showToast(`Conferido! ${data.acertos} acertos.`, data.acertos >= 3 ? 'success' : 'info');
        closeModal();
        verDetalhes(jogoId);
        // Reload page if on historico
        if (window.location.pathname.includes('historico')) setTimeout(() => location.reload(), 500);
      } else {
        showToast(data.error || 'Erro ao conferir.', 'error');
      }
    })
    .catch(() => showToast('Erro ao conferir.', 'error'));
}

/* --- Fetch Result from API --- */
function buscarResultadoAPI(tipoJogoId, numeroConcurso, callback) {
  const formData = new FormData();
  formData.append('tipo_jogo', tipoJogoId);
  formData.append('numero_concurso', numeroConcurso);

  fetch('/resultados/buscar/', { method: 'POST', body: formData, headers: {'X-CSRFToken': getCSRF()} })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        showToast(`Resultado carregado (${data.source === 'api' ? 'API Caixa' : 'banco'})`, 'success');
        if (callback) callback(data);
      } else {
        showToast(data.error || 'Erro ao buscar resultado.', 'error');
      }
    })
    .catch(() => showToast('Erro de conexão.', 'error'));
}
