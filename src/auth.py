from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from .models_db import User, UserRole
from .database import get_db
from sqlalchemy import select

auth_bp = Blueprint('auth', __name__)
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Por favor, faça login para acessar esta página.'
login_manager.login_message_category = 'warning'

@login_manager.user_loader
def load_user(user_id):
    import logging
    auth_logger = logging.getLogger("mvp-app")
    auth_logger.debug(f"🔍 [load_user] Carregando usuário: {user_id}")
    db_gen = get_db()
    db = next(db_gen)
    try:
        user = db.query(User).get(user_id)
        if user:
            auth_logger.debug(f"✅ [load_user] Usuário encontrado: {user.email} (Role: {user.role})")
        else:
            auth_logger.debug(f"⚠️ [load_user] Usuário não encontrado ID: {user_id}")
        return user
    except Exception as e:
        auth_logger.error(f"❌ [load_user] Erro ao carregar usuário {user_id}: {e}")
        db.rollback()
        return None

def role_required(role: str):
    """Decorador para restringir acesso a rotas baseado no papel (Role) do usuário."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login', next=request.url))
            if current_user.role != role and current_user.role != 'ADMIN':
                flash('Acesso não autorizado para seu perfil.', 'error')
                # Redireciona para o dashboard correto do usuário
                if current_user.role == UserRole.MANAGER:
                    return redirect(url_for('manager.dashboard_manager'))
                else:
                    return redirect(url_for('dashboard_consultant'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == UserRole.MANAGER:
            return redirect(url_for('dashboard_manager')) # Ajustar nome da rota depois
        return redirect(url_for('dashboard_consultant')) # Ajustar nome da rota depois

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        db_gen = get_db()
        db = next(db_gen)
        try:
            user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
            
            if not user or not user.password_hash or not check_password_hash(user.password_hash, password):
                flash('Email ou senha incorretos.', 'error')
                return render_template('login.html')

            login_user(user, remember=remember)
            
            # Redirecionamento baseado em Role
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                if user.role == UserRole.ADMIN:
                    next_page = url_for('admin.index')
                elif user.role == UserRole.MANAGER:
                    next_page = url_for('manager.dashboard_manager')
                else:
                    next_page = url_for('dashboard_consultant')
            
            return redirect(next_page)
            
        except Exception as e:
            db.rollback()
            flash(f'Erro ao fazer login: {str(e)}', 'error')
        # finally handled by app teardown for request-scoped sessions

    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not current_password or not new_password or not confirm_password:
            flash('Preencha todos os campos.', 'error')
            return render_template('change_password.html')
            
        if new_password != confirm_password:
            flash('A nova senha e a confirmação não coincidem.', 'error')
            return render_template('change_password.html')
            
        if len(new_password) < 8 or not any(char.isdigit() for char in new_password):
            flash('A senha deve ter no mínimo 8 caracteres e conter números.', 'error')
            return render_template('change_password.html')
            
        db = next(get_db())
        try:
            # Force integrity check on current DB state
            user = db.query(User).get(current_user.id)
            
            if not check_password_hash(user.password_hash, current_password):
                flash('Senha atual incorreta.', 'error')
                return render_template('change_password.html')
                
            user.password_hash = generate_password_hash(new_password)
            user.must_change_password = False
            db.commit()
            
            flash('Senha atualizada com sucesso! Bem-vindo.', 'success')
            
            # Redirect to correct dashboard
            if user.role == UserRole.MANAGER:
                return redirect(url_for('manager.dashboard_manager'))
            elif user.role == UserRole.ADMIN:
                return redirect(url_for('admin.index'))
            else:
                return redirect(url_for('dashboard_consultant'))
                
        except Exception as e:
            db.rollback()
            flash(f'Erro ao atualizar senha: {e}', 'error')
        finally:
            db.close()
            
    return render_template('change_password.html')

@auth_bp.before_app_request
def check_force_password_change():
    """
    Middleware global que verifica se o usuário precisa trocar a senha.
    Bloqueia acesso a qualquer página que não seja estática ou de autenticação.
    """
    if current_user.is_authenticated and current_user.must_change_password:
        # Allow static files
        if request.endpoint and 'static' in request.endpoint:
            return
            
        # Allow auth routes (logout, change-password)
        allowed_endpoints = ['auth.logout', 'auth.change_password']
        if request.endpoint in allowed_endpoints:
            return
            
        # Redirect all else to change-password
        if request.endpoint != 'auth.change_password':
            flash('Você precisa alterar sua senha temporária antes de continuar.', 'warning')
            return redirect(url_for('auth.change_password'))
