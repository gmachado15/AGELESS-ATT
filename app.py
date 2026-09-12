from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file
import cv2
import numpy as np
import base64
from deepface import DeepFace
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from collections import Counter
from datetime import datetime, date, timedelta
import random
import string
import os
import threading
import time
from pathlib import Path

os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/analise_ia'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'uma_chave_muito_secreta_e_complexa'
app.config['UPLOAD_FOLDER'] = 'uploads'  # Pasta para salvar fotos/vídeos

# Criar pasta de uploads se não existir
Path(app.config['UPLOAD_FOLDER']).mkdir(exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


# =============================================================
# MODELOS DO BANCO
# =============================================================

class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuarios'
    id     = db.Column(db.Integer, primary_key=True)
    nome   = db.Column(db.String(100), nullable=False)
    email  = db.Column(db.String(100), unique=True, nullable=False)
    senha  = db.Column(db.String(255), nullable=False)
    tipo   = db.Column(db.String(20), default='Idoso')
    codigo = db.Column(db.String(10), unique=True, nullable=True)


class RegistroEmocao(db.Model):
    __tablename__ = 'registros_emocao'
    id         = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    emocao     = db.Column(db.String(50), nullable=False)
    confianca  = db.Column(db.Float, nullable=False)
    data_hora  = db.Column(db.DateTime, default=db.func.now())
    foto_url   = db.Column(db.String(255), nullable=True)  # Caminho da foto
    video_url  = db.Column(db.String(255), nullable=True)  # Caminho do vídeo
    usuario    = db.relationship('Usuario', backref='registros')


class Vinculo(db.Model):
    __tablename__ = 'vinculos'
    id               = db.Column(db.Integer, primary_key=True)
    responsavel_id   = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    idoso_id         = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    criado_em        = db.Column(db.DateTime, default=datetime.now)
    __table_args__   = (db.UniqueConstraint('responsavel_id', 'idoso_id'),)


class RelatorioDiario(db.Model):
    __tablename__ = 'relatorios_diarios'
    id                  = db.Column(db.Integer, primary_key=True)
    idoso_id            = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    data                = db.Column(db.Date, nullable=False)
    total_analises      = db.Column(db.Integer, default=0)
    emocao_predominante = db.Column(db.String(50), nullable=True)
    qtd_feliz           = db.Column(db.Integer, default=0)
    qtd_triste          = db.Column(db.Integer, default=0)
    qtd_bravo           = db.Column(db.Integer, default=0)
    qtd_neutro          = db.Column(db.Integer, default=0)
    qtd_outros          = db.Column(db.Integer, default=0)
    criado_em           = db.Column(db.DateTime, default=datetime.now)
    __table_args__      = (db.UniqueConstraint('idoso_id', 'data'),)


@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))


# =============================================================
# HELPERS
# =============================================================

def gerar_codigo():
    """Gera um código único no formato AG-XXXXXX para idosos."""
    while True:
        sufixo = ''.join(random.choices(string.digits, k=6))
        codigo = f'AG-{sufixo}'
        if not Usuario.query.filter_by(codigo=codigo).first():
            return codigo


def emocao_emoji(emocao):
    mapa = {'Feliz': '😊', 'Triste': '🥺', 'Bravo': '😤', 'Neutro': '🙂',
            'Surpreso': '😮', 'Medo': '😨', 'Nojo': '😒'}
    return mapa.get(emocao, '👀')

app.jinja_env.globals['emocao_emoji'] = emocao_emoji


def salvar_midia(usuario_id, imagem_base64, video_file=None):
    """
    Salva foto e vídeo do registro de emoção.
    Retorna: (foto_url, video_url)
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    pasta_usuario = os.path.join(app.config['UPLOAD_FOLDER'], str(usuario_id))
    Path(pasta_usuario).mkdir(parents=True, exist_ok=True)

    foto_url = None
    video_url = None

    # Salvar foto
    try:
        foto_filename = f'foto_{timestamp}.jpg'
        foto_path = os.path.join(pasta_usuario, foto_filename)
        
        # Decodificar base64 e salvar
        imagem_dados = imagem_base64.split(',')[1] if ',' in imagem_base64 else imagem_base64
        imagem_bytes = base64.b64decode(imagem_dados)
        
        with open(foto_path, 'wb') as f:
            f.write(imagem_bytes)
        
        foto_url = f"{usuario_id}/{foto_filename}"   # Ex: 5/foto_20260904_151000.jpg
        print(f"✅ Foto salva: {foto_url}")
    except Exception as e:
        print(f"❌ Erro ao salvar foto: {str(e)}")

    # Salvar vídeo
    if video_file:
        try:
            video_filename = f'video_{timestamp}.webm'
            video_path = os.path.join(pasta_usuario, video_filename)
            video_file.save(video_path)
            video_url = video_path
            print(f"✅ Vídeo salvo: {video_url}")
        except Exception as e:
            print(f"❌ Erro ao salvar vídeo: {str(e)}")

    return foto_url, video_url


# =============================================================
# FUNÇÕES DE ANÁLISE (sem alterações)
# =============================================================

def preprocessar_imagem(img):
    if img is None:
        return None
    height, width = img.shape[:2]
    if width > 640 or height > 640:
        scale = 640 / max(width, height)
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
    l = clahe.apply(l)
    lab = cv2.merge((l, a, b))
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def tentar_analisar(img):
    detectors = ['mtcnn', 'retinaface', 'mediapipe', 'ssd', 'yunet']
    for detector in detectors:
        try:
            res = DeepFace.analyze(
                img, actions=['emotion'],
                enforce_detection=False,
                detector_backend=detector,
                align=True, silent=True, anti_spoofing=False
            )
            if isinstance(res, list):
                res = res[0]
            emocao = res['dominant_emotion']
            confianca = res['emotion'][emocao]
            print(f"✅ Detector {detector} → {emocao} ({confianca:.1f}%)")
            if confianca >= 30:
                return emocao, confianca
        except Exception as e:
            print(f"❌ Detector {detector} falhou: {str(e)[:100]}")
            continue
    print("⚠️ Nenhum detector conseguiu identificar o rosto")
    return None, 0


# =============================================================
# ROTAS DE NAVEGAÇÃO
# =============================================================

@app.route('/')
def index():
    return render_template('menup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    tipo = request.args.get('tipo', 'Idoso')

    if request.method == 'POST':
        if request.is_json:
            dados = request.get_json()
            email = dados.get('email')
            senha = dados.get('senha')
        else:
            email = request.form.get('email')
            senha = request.form.get('senha')

        usuario = Usuario.query.filter_by(email=email).first()

        if usuario and check_password_hash(usuario.senha, senha):
            login_user(usuario)
            destino = 'dashboard_responsavel' if usuario.tipo == 'Responsavel' else 'dashboard'
            return jsonify({
                'success': True, 
                'message': 'Bem-vindo!',
                'nome': usuario.nome, 
                'tipo': usuario.tipo,  # ← ISSO AQUI É CRÍTICO!
                'redirect': url_for(destino)
            }), 200

        return jsonify({'success': False, 'message': 'E-mail ou senha incorretos'}), 401

    return render_template('login.html', tipo=tipo)

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        dados = request.get_json() if request.is_json else request.form
        tipo = dados.get('tipo', 'Idoso')  # ← PRECISA ESTAR AQUI!
        
        novo_usuario = Usuario(
            nome=dados['nome'],
            email=dados['email'],
            senha=generate_password_hash(dados['senha']),
            tipo=tipo,
            codigo=gerar_codigo() if tipo == 'Idoso' else None
        )

        try:
            db.session.add(novo_usuario)
            db.session.commit()
            return jsonify({'success': True, 'codigo': novo_usuario.codigo}), 201
        except Exception:
            db.session.rollback()
            return jsonify({'erro': 'E-mail já cadastrado'}), 400

    return render_template('cadastro.html')


@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.tipo == 'Responsavel':
        return redirect(url_for('dashboard_responsavel'))
    return render_template('dashboard.html')


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


# =============================================================
# ANÁLISE COM SALVAMENTO DE VÍDEO/FOTO
# =============================================================

@app.route('/analisar_expressao', methods=['POST'])
@login_required
def analisar():
    try:
        print("🔍 Requisição recebida - Iniciando análise...")
        
        dados = request.get_json()
        imagem_base64 = dados.get('image') if dados else None

        if not imagem_base64:
            print("❌ Imagem não recebida")
            return jsonify({'emocao': 'Erro', 'confianca': 0}), 400

        print("📁 Decodificando imagem...")
        encoded_data = imagem_base64.split(',')[1] if ',' in imagem_base64 else imagem_base64
        nparr = np.frombuffer(base64.b64decode(encoded_data), np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            print("❌ Falha ao decodificar imagem")
            return jsonify({'emocao': 'Erro', 'confianca': 0}), 400

        print(f"✅ Imagem OK - Shape: {img.shape}")
        img = preprocessar_imagem(img)

        print("🤖 Analisando com DeepFace...")
        emocoes_detectadas = []
        confiancas = []
        
        for i in range(3):
            resultado = tentar_analisar(img)
            if resultado and resultado[0]:
                emocoes_detectadas.append(resultado[0])
                confiancas.append(resultado[1])

        if not emocoes_detectadas:
            emocao_final = 'Neutro'
            confianca_media = 50
        else:
            emocao_final = Counter(emocoes_detectadas).most_common(1)[0][0]
            confianca_media = round(sum(confiancas) / len(confiancas), 2)

        print(f"✅ Resultado: {emocao_final} ({confianca_media}%)")

        # ========== SALVAR A FOTO ==========
        foto_url, video_url = salvar_midia(
            usuario_id=current_user.id,
            imagem_base64=imagem_base64
        )

        # ========== SALVAR NO BANCO ==========
        novo_registro = RegistroEmocao(
            usuario_id=current_user.id,
            emocao=emocao_final,
            confianca=confianca_media,
            foto_url=foto_url,
            video_url=video_url
        )
        db.session.add(novo_registro)
        db.session.commit()

        print(f"✅ Registro salvo no banco. Foto: {foto_url}")

        return jsonify({
            'emocao': emocao_final,
            'confianca': confianca_media
        }), 200

    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'emocao': 'Erro', 'confianca': 0, 'erro': str(e)}), 500

# =============================================================
# ROTA PARA SERVIR MÍDIA
# =============================================================

@app.route('/uploads/<path:filename>')
@login_required
def download_file(filename):
    """Serve fotos e vídeos salvos"""
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    # Verificar se o usuário tem permissão de acessar
    usuario_id_arquivo = filename.split('/')[0]
    
    # Apenas o proprietário ou um responsável vinculado pode acessar
    if current_user.tipo == 'Idoso':
        if int(usuario_id_arquivo) != current_user.id:
            return jsonify({'erro': 'Acesso negado'}), 403
    elif current_user.tipo == 'Responsavel':
        idoso_id = int(usuario_id_arquivo)
        vinculo = Vinculo.query.filter_by(
            responsavel_id=current_user.id,
            idoso_id=idoso_id
        ).first()
        if not vinculo:
            return jsonify({'erro': 'Acesso negado'}), 403
    
    if os.path.exists(file_path):
        return send_file(file_path)
    else:
        return jsonify({'erro': 'Arquivo não encontrado'}), 404


# =============================================================
# DASHBOARD RESPONSÁVEL COM GALERIA
# =============================================================

@app.route('/dashboard/responsavel')
@login_required
def dashboard_responsavel():
    if current_user.tipo != 'Responsavel':
        return redirect(url_for('dashboard'))

    vinculos = Vinculo.query.filter_by(responsavel_id=current_user.id).all()
    idosos_ids = [v.idoso_id for v in vinculos]
    idosos_raw = Usuario.query.filter(Usuario.id.in_(idosos_ids)).all() if idosos_ids else []

    idosos = []
    alertas = []

    for idoso in idosos_raw:
        registros = RegistroEmocao.query.filter_by(
            usuario_id=idoso.id
        ).order_by(RegistroEmocao.data_hora.asc()).all()

        historico = [
            {
                'emocao': r.emocao,
                'confianca': r.confianca,
                'hora': r.data_hora.strftime('%d/%m %H:%M'),
                'foto_url': r.foto_url,
                'video_url': r.video_url,
                'data_hora': r.data_hora.strftime('%d/%m/%Y às %H:%M')
            }
            for r in registros
        ]

        ultima = historico[-1] if historico else None
        ultima_emocao = ultima['emocao'] if ultima else None
        ultima_analise = ultima['hora'] if ultima else None

        hoje = datetime.now().date()
        analises_hoje = sum(1 for r in registros if r.data_hora.date() == hoje)

        emocao_frequente = None
        if historico:
            contagem = Counter(r['emocao'] for r in historico)
            emocao_frequente = contagem.most_common(1)[0][0]

        idosos.append({
            'id': idoso.id,
            'nome': idoso.nome,
            'codigo': idoso.codigo,
            'ultima_emocao': ultima_emocao,
            'ultima_analise': ultima_analise,
            'analises_hoje': analises_hoje,
            'emocao_frequente': emocao_frequente,
            'historico': historico,  # Com URLs de mídia
        })

        if ultima_emocao in ('Triste', 'Bravo'):
            alertas.append({
                'nome': idoso.nome,
                'nivel': 'alto' if ultima_emocao == 'Bravo' else 'medio',
                'mensagem': f'Última emoção registrada: {ultima_emocao}',
                'hora': ultima_analise,
            })

    return render_template(
        'dashboard_responsavel.html',
        nome_responsavel=current_user.nome,
        idosos=idosos,
        alertas=alertas,
    )


# =============================================================
# ROTAS DO RESPONSÁVEL (sem alterações)
# =============================================================

@app.route('/historico/<int:idoso_id>')
@login_required
def historico_idoso(idoso_id):
    if current_user.tipo != 'Responsavel':
        return redirect(url_for('dashboard'))

    Vinculo.query.filter_by(
        responsavel_id=current_user.id,
        idoso_id=idoso_id
    ).first_or_404()


    idoso = Usuario.query.get_or_404(idoso_id)

    registros = RegistroEmocao.query.filter_by(
        usuario_id=idoso_id
    ).order_by(RegistroEmocao.data_hora.asc()).all()

    historico = [
        {
            'emocao': r.emocao,
            'confianca': r.confianca,
            'mensagem': f'Confiança: {r.confianca:.0f}%',
            'hora': r.data_hora.strftime('%d/%m/%Y às %H:%M'),
            'foto_url': r.foto_url,
            'video_url': r.video_url
        }
        for r in registros
    ]

    contagem = Counter(r['emocao'] for r in historico)

    return render_template(
        'historico_idoso.html',
        idoso=idoso,
        historico=historico,
        contagem=contagem,
    )


@app.route('/responsavel/vincular-idoso')
@login_required
def vincular_idoso():
    if current_user.tipo != 'Responsavel':
        return redirect(url_for('dashboard'))
    return render_template('vincular_idoso.html')


@app.route('/responsavel/buscar_idoso', methods=['POST'])
@login_required
def buscar_idoso():
    dados = request.get_json()
    codigo = (dados.get('codigo') or '').strip().upper()

    if not codigo:
        return jsonify({'success': False, 'erro': 'Código não informado.'}), 400

    idoso = Usuario.query.filter_by(codigo=codigo, tipo='Idoso').first()
    if not idoso:
        return jsonify({'success': False, 'erro': 'Nenhum idoso encontrado com esse código.'}), 404

    ja_vinculado = Vinculo.query.filter_by(
        responsavel_id=current_user.id, idoso_id=idoso.id
    ).first()
    if ja_vinculado:
        return jsonify({'success': False, 'erro': 'Você já está vinculado a este idoso.'}), 409

    return jsonify({'success': True, 'idoso': {'id': idoso.id, 'nome': idoso.nome, 'email': idoso.email}})


@app.route('/responsavel/vincular', methods=['POST'])
@login_required
def confirmar_vinculo():
    dados = request.get_json()
    idoso_id = dados.get('idoso_id')

    if not idoso_id:
        return jsonify({'success': False, 'erro': 'ID do idoso não informado.'}), 400

    idoso = Usuario.query.filter_by(id=idoso_id, tipo='Idoso').first()
    if not idoso:
        return jsonify({'success': False, 'erro': 'Idoso não encontrado.'}), 404

    if Vinculo.query.filter_by(responsavel_id=current_user.id, idoso_id=idoso_id).first():
        return jsonify({'success': False, 'erro': 'Vínculo já existe.'}), 409

    db.session.add(Vinculo(responsavel_id=current_user.id, idoso_id=idoso_id))
    db.session.commit()
    return jsonify({'success': True})


@app.route('/responsavel/desvincular', methods=['POST'])
@login_required
def desvincular_idoso():
    dados = request.get_json()
    idoso_id = dados.get('idoso_id')

    vinculo = Vinculo.query.filter_by(
        responsavel_id=current_user.id, idoso_id=idoso_id
    ).first()

    if not vinculo:
        return jsonify({'success': False, 'erro': 'Vínculo não encontrado.'}), 404

    db.session.delete(vinculo)
    db.session.commit()
    return jsonify({'success': True})


# =============================================================
# INICIALIZAÇÃO
# =============================================================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, ssl_context='adhoc', debug=True)