// Pegar tipo da URL
const urlParams = new URLSearchParams(window.location.search);
const tipoUsuario = urlParams.get('tipo') || 'Idoso';

function showFeedback(msg, tipo) {
  const el = document.getElementById('message');
  if (!el) return;
  el.textContent = msg;
  el.className = 'message ' + tipo;
}

document.getElementById('btn-cadastrar').addEventListener('click', async function() {
    const nome = document.getElementById('nome').value;
    const email = document.getElementById('email').value;
    const senha = document.getElementById('senha').value;
    const confirmar_senha = document.getElementById('confirmar_senha').value;

    if (!nome || !email || !senha || !confirmar_senha) {
        showFeedback('Preencha todos os campos!', 'erro');
        return;
    }

    if (senha !== confirmar_senha) {
        showFeedback('As senhas não coincidem!', 'erro');
        return;
    }

    try {
        const response = await fetch('/cadastro', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                nome,
                email,
                senha,
                tipo: tipoUsuario  // Envia o tipo correto!
            })
        });

        const data = await response.json();

        if (data.success) {
            showFeedback('Cadastro realizado com sucesso!', 'ok');
            setTimeout(() => {
                window.location.href = `/login?tipo=${tipoUsuario}`;
            }, 1500);
        } else {
            showFeedback(data.erro || 'Erro ao cadastrar', 'erro');
        }
    } catch (error) {
        console.error('Erro:', error);
        showFeedback('Erro de conexão', 'erro');
    }
});