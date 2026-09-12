document.getElementById('btn-entrar').addEventListener('click', async function(e) {
    e.preventDefault();

    const email = document.getElementById('email').value;
    const senha = document.getElementById('senha').value;

    if (!email || !senha) {
        alert('Preencha todos os campos!');
        return;
    }

    try {
        const response = await fetch('/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, senha })
        });

        const data = await response.json();

        if (data.success) {
            console.log('Login bem-sucedido! Tipo:', data.tipo);
            
            // Redirecionar conforme o tipo
            if (data.tipo === 'Responsavel') {
                window.location.href = '/dashboard/responsavel';
            } else {
                window.location.href = '/dashboard';
            }
        } else {
            alert(data.message || 'Erro ao fazer login');
        }
    } catch (error) {
        console.error('Erro:', error);
        alert('Erro de conexão');
    }
});