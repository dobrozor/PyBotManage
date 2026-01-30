#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VDS Manager - Веб-интерфейс для управления проектами на VDS
"""

import os
import json
import bcrypt
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename
from auth import load_users, save_user, is_first_run, mark_first_run_complete
from manager import ProjectManager

# Инициализация приложения
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Конфигурация путей
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # /root/bots/site
app.config['ROOT_DIR'] = '/root/bots'  # Корневая директория где лежат все проекты
app.config['SITE_DIR'] = BASE_DIR  # /root/bots/site
app.config['SYSTEMD_DIR'] = '/root/bots/systemd'
app.config['DATA_DIR'] = os.path.join(BASE_DIR, 'data')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB limit

# Создание необходимых директорий
os.makedirs(app.config['SYSTEMD_DIR'], exist_ok=True)
os.makedirs(app.config['DATA_DIR'], exist_ok=True)

# Инициализация менеджера проектов
project_manager = ProjectManager(app.config['ROOT_DIR'], app.config['SYSTEMD_DIR'])

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


class User(UserMixin):
    """Класс пользователя для Flask-Login"""

    def __init__(self, user_id):
        self.id = user_id

import logging

# Настройка логирования в app.py
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/vds_manager_app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@login_manager.user_loader
def load_user(user_id):
    """Загрузка пользователя по ID"""
    users = load_users()
    if users and user_id in users:
        return User(user_id)
    return None


# ==================== Роуты авторизации ====================

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Регистрация первого администратора"""
    if not is_first_run():
        flash('Администратор уже зарегистрирован', 'info')
        return redirect(url_for('login'))

    if request.method == 'POST':
        password = request.form.get('password')
        confirm = request.form.get('confirm')

        if not password or not confirm:
            flash('Пароль не может быть пустым', 'error')
            return redirect(url_for('register'))

        if len(password) < 8:
            flash('Пароль должен содержать не менее 8 символов', 'error')
            return redirect(url_for('register'))

        if password != confirm:
            flash('Пароли не совпадают', 'error')
            return redirect(url_for('register'))

        # Хэширование пароля и сохранение
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        save_user('admin', hashed.decode('utf-8'))

        flash('Администратор успешно зарегистрирован! Теперь войдите в систему.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа"""
    if not is_first_run() and current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        password = request.form.get('password')
        users = load_users()

        if not users or 'admin' not in users:
            flash('Сначала зарегистрируйте администратора', 'error')
            return redirect(url_for('register'))

        stored_hash = users['admin'].encode('utf-8')
        if bcrypt.checkpw(password.encode('utf-8'), stored_hash):
            user = User('admin')
            login_user(user)
            flash('Добро пожаловать!', 'success')
            return redirect(url_for('dashboard'))

        flash('Неверный пароль', 'error')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """Выход из системы"""
    logout_user()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('login'))


# ==================== Основные роуты ====================

@app.route('/')
def index():
    """Главная страница - редирект на регистрацию или дашборд"""
    if is_first_run():
        return redirect(url_for('register'))
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))


@app.route('/dashboard')
@login_required
def dashboard():
    """Главная панель управления проектами"""
    projects = project_manager.get_projects()
    statuses = {}
    for name in projects:
        try:
            statuses[name] = project_manager.get_project_status(name)
        except Exception as e:
            statuses[name] = f'error: {str(e)}'

    return render_template('dashboard.html', projects=projects, statuses=statuses)


# ==================== Управление проектами ====================

@app.route('/project/create', methods=['POST'])
@login_required
def create_project():
    """Создание нового проекта"""
    name = request.form.get('name', '').strip()

    if not name:
        flash('Имя проекта не может быть пустым', 'error')
        return redirect(url_for('dashboard'))

    # Валидация имени проекта
    if not name.replace('_', '').replace('-', '').isalnum():
        flash('Имя проекта может содержать только буквы, цифры, дефисы и подчеркивания', 'error')
        return redirect(url_for('dashboard'))

    if len(name) > 50:
        flash('Имя проекта слишком длинное (максимум 50 символов)', 'error')
        return redirect(url_for('dashboard'))

    try:
        logger.info(f"Попытка создания проекта: {name}")
        project_manager.create_project(name)
        flash(f'✅ Проект "{name}" успешно создан!', 'success')
        logger.info(f"Проект успешно создан: {name}")
    except ValueError as e:
        flash(f'⚠️ {str(e)}', 'error')
        logger.error(f"Ошибка валидации при создании проекта '{name}': {e}")
    except PermissionError as e:
        flash(f'❌ Ошибка прав доступа: {str(e)}. Запустите сайт с правами root или используйте sudo.', 'error')
        logger.error(f"Ошибка прав доступа при создании проекта '{name}': {e}")
    except Exception as e:
        flash(f'❌ Ошибка создания проекта: {str(e)}', 'error')
        logger.error(f"Неизвестная ошибка при создании проекта '{name}': {e}", exc_info=True)

    return redirect(url_for('dashboard'))


@app.route('/project/<name>/delete', methods=['POST'])
@login_required
def delete_project(name):
    """Удаление проекта"""
    try:
        project_manager.delete_project(name)
        flash(f'Проект "{name}" удален', 'success')
    except ValueError as e:
        flash(f'Ошибка удаления: {str(e)}', 'error')
    except Exception as e:
        flash(f'Неизвестная ошибка: {str(e)}', 'error')

    return redirect(url_for('dashboard'))


@app.route('/project/<name>/control', methods=['POST'])
@login_required
def control_project(name):
    """Управление проектом (старт/стоп/рестарт)"""
    action = request.form.get('action')

    try:
        if action == 'start':
            project_manager.start_project(name)
            flash(f'Проект "{name}" запущен', 'success')
        elif action == 'stop':
            project_manager.stop_project(name)
            flash(f'Проект "{name}" остановлен', 'success')
        elif action == 'restart':
            project_manager.restart_project(name)
            flash(f'Проект "{name}" перезапущен', 'success')
        else:
            flash('Неизвестное действие', 'error')
    except Exception as e:
        flash(f'Ошибка управления проектом: {str(e)}', 'error')

    return redirect(url_for('project_files', name=name))


# ==================== Работа с файлами проекта ====================

@app.route('/project/<name>/files')
@login_required
def project_files(name):
    """Страница файлов проекта"""
    if not project_manager.project_exists(name):
        flash('Проект не найден', 'error')
        return redirect(url_for('dashboard'))

    try:
        files = project_manager.get_project_files(name)
        status = project_manager.get_project_status(name)
        logs = project_manager.get_project_logs(name)
    except Exception as e:
        flash(f'Ошибка загрузки данных проекта: {str(e)}', 'error')
        return redirect(url_for('dashboard'))

    return render_template('files.html',
                           project_name=name,
                           files=files,
                           status=status,
                           logs=logs)


@app.route('/project/<name>/upload', methods=['POST'])
@login_required
def upload_file(name):
    """Загрузка файла в проект"""
    if 'file' not in request.files:
        flash('Файл не выбран', 'error')
        return redirect(url_for('project_files', name=name))

    file = request.files['file']
    if file.filename == '':
        flash('Файл не выбран', 'error')
        return redirect(url_for('project_files', name=name))

    if not project_manager.project_exists(name):
        flash('Проект не найден', 'error')
        return redirect(url_for('dashboard'))

    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['ROOT_DIR'], name, filename)
        file.save(filepath)
        flash(f'Файл "{filename}" успешно загружен', 'success')
    except Exception as e:
        flash(f'Ошибка загрузки файла: {str(e)}', 'error')

    return redirect(url_for('project_files', name=name))


@app.route('/project/<name>/file/<path:filename>')
@login_required
def view_file(name, filename):
    """Просмотр/редактирование файла"""
    if not project_manager.project_exists(name):
        flash('Проект не найден', 'error')
        return redirect(url_for('dashboard'))

    filepath = os.path.join(app.config['ROOT_DIR'], name, filename)
    if not os.path.exists(filepath):
        flash('Файл не найден', 'error')
        return redirect(url_for('project_files', name=name))

    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        flash(f'Ошибка чтения файла: {str(e)}', 'error')
        return redirect(url_for('project_files', name=name))

    files = project_manager.get_project_files(name)
    status = project_manager.get_project_status(name)
    logs = project_manager.get_project_logs(name)

    return render_template('files.html',
                           project_name=name,
                           files=files,
                           editing_file=filename,
                           file_content=content,
                           status=status,
                           logs=logs)


@app.route('/project/<name>/file/<path:filename>/save', methods=['POST'])
@login_required
def save_file(name, filename):
    """Сохранение изменений в файле"""
    content = request.form.get('content', '')

    if not project_manager.project_exists(name):
        flash('Проект не найден', 'error')
        return redirect(url_for('dashboard'))

    try:
        filepath = os.path.join(app.config['ROOT_DIR'], name, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        flash(f'Файл "{filename}" успешно сохранен', 'success')
    except Exception as e:
        flash(f'Ошибка сохранения файла: {str(e)}', 'error')

    return redirect(url_for('project_files', name=name))


@app.route('/project/<name>/file/<path:filename>/delete', methods=['POST'])
@login_required
def delete_file(name, filename):
    """Удаление файла из проекта"""
    if not project_manager.project_exists(name):
        flash('Проект не найден', 'error')
        return redirect(url_for('dashboard'))

    try:
        filepath = os.path.join(app.config['ROOT_DIR'], name, filename)
        if not os.path.exists(filepath):
            flash('Файл не найден', 'error')
            return redirect(url_for('project_files', name=name))

        os.remove(filepath)
        flash(f'Файл "{filename}" удален', 'success')
    except Exception as e:
        flash(f'Ошибка удаления файла: {str(e)}', 'error')

    return redirect(url_for('project_files', name=name))


# ==================== API для логов и статусов ====================

@app.route('/project/<name>/logs')
@login_required
def project_logs(name):
    """API для получения логов проекта"""
    if not project_manager.project_exists(name):
        return jsonify({'error': 'Project not found'}), 404

    try:
        logs = project_manager.get_project_logs(name)
        return jsonify({'logs': logs})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/project/<name>/status')
@login_required
def project_status(name):
    """API для получения статуса проекта"""
    if not project_manager.project_exists(name):
        return jsonify({'error': 'Project not found'}), 404

    try:
        status = project_manager.get_project_status(name)
        return jsonify({'status': status})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)