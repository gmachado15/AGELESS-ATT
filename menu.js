document.addEventListener('DOMContentLoaded', () => {

  const btnIdoso = document.getElementById('btn-idoso');
  const btnResponsavel = document.getElementById('btn-responsavel');

  // Evita erro se botão não existir
  if (btnIdoso) {
    btnIdoso.addEventListener('click', () => {
      window.location.href = "/login?tipo=Idoso";
    });
  }

  if (btnResponsavel) {
    btnResponsavel.addEventListener('click', () => {
      window.location.href = "/login?tipo=Responsavel";
    });
  }

  // Efeito visual
  const buttons = document.querySelectorAll('.btn');
  buttons.forEach(btn => {
    btn.addEventListener('touchstart', () => {
      btn.style.transform = 'scale(0.96)';
    });
    btn.addEventListener('touchend', () => {
      btn.style.transform = 'scale(1)';
    });
  });

});