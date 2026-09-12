/* responsavel.js */

/* ===== DASHBOARD ===== */

function desvincular(idosoId, nome) {
  document.getElementById('modal-nome').textContent = nome;
  document.getElementById('modal-overlay').classList.add('active');
  document.getElementById('btn-confirmar-desv').onclick = () => confirmarDesvincular(idosoId);
}

function fecharModal() {
  document.getElementById('modal-overlay').classList.remove('active');
}

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') fecharModal();
});

document.getElementById('modal-overlay')?.addEventListener('click', (e) => {
  if (e.target === e.currentTarget) fecharModal();
});

async function confirmarDesvincular(idosoId) {
  try {
    const res = await fetch('/responsavel/desvincular', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ idoso_id: idosoId })
    });
    const data = await res.json();
    if (data.success) {
      window.location.reload();
    } else {
      fecharModal();
      alert(data.erro || 'Erro ao desvincular.');
    }
  } catch {
    alert('Erro de conexão com o servidor.');
  }
}

/* ===== VINCULAR IDOSO ===== */

let idosoEncontrado = null;

function mostrarFeedback(msg, tipo) {
  const el = document.getElementById('feedback');
  if (!el) return;
  el.textContent = msg;
  el.className = 'feedback-msg ' + tipo;
}

async function buscarIdoso() {
  const codigo = document.getElementById('codigo-input')?.value.trim().toUpperCase();
  const btnVincular = document.getElementById('btn-vincular');
  const preview = document.getElementById('preview-idoso');

  if (!codigo) {
    mostrarFeedback('Digite um código antes de buscar.', 'erro');
    return;
  }

  mostrarFeedback('Buscando...', '');
  idosoEncontrado = null;
  if (preview) preview.classList.add('hidden');
  if (btnVincular) btnVincular.classList.add('hidden');

  try {
    const res = await fetch('/responsavel/buscar_idoso', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codigo })
    });
    const data = await res.json();

    if (data.success && data.idoso) {
      idosoEncontrado = data.idoso;

      // Preenche preview
      document.getElementById('preview-avatar').textContent = data.idoso.nome[0].toUpperCase();
      document.getElementById('preview-nome').textContent = data.idoso.nome;
      document.getElementById('preview-email').textContent = data.idoso.email;

      if (preview) preview.classList.remove('hidden');
      if (btnVincular) btnVincular.classList.remove('hidden');
      mostrarFeedback('', '');
    } else {
      mostrarFeedback(data.erro || 'Nenhum idoso encontrado com esse código.', 'erro');
    }
  } catch {
    mostrarFeedback('Erro de conexão com o servidor.', 'erro');
  }
}

async function confirmarVinculo() {
  if (!idosoEncontrado) return;

  try {
    const res = await fetch('/responsavel/vincular', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ idoso_id: idosoEncontrado.id })
    });
    const data = await res.json();

    if (data.success) {
      window.location.href = '/dashboard/responsavel';
    } else {
      mostrarFeedback(data.erro || 'Erro ao vincular.', 'erro');
    }
  } catch {
    mostrarFeedback('Erro de conexão com o servidor.', 'erro');
  }
}

// Permite buscar com Enter
document.getElementById('codigo-input')?.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') buscarIdoso();
});
