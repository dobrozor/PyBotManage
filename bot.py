from flask import Flask, render_template, request, jsonify, session, send_file
import os
import subprocess
from functools import wraps
import shutil  # Добавьте этот импорт в начало файла

app = Flask(__name__, template_folder='templates')
app.secret_key = '1020315'
BASE_DIR = '/root/bots'
SCRIPTS_DIR = BASE_DIR
VENV_DIR = os.path.join(BASE_DIR, 'venv')
SYSTEMD_DIR = '/root/bots/systemd'  # Правильный путь для systemd

# Настройки аутентификации
USERNAME = 'dobrozor'
PASSWORD = 'cvbn765431'


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return jsonify({'error': 'Требуется авторизация'}), 401
        return f(*args, **kwargs)

    return decorated_function


@app.route('/')
def home():
    return render_template('index.html')



@app.route('/api/project/<project_name>/<filename>')  # Добавить этот маршрут
@login_required
def api_get_project_file(project_name, filename):
    file_path = os.path.join(SCRIPTS_DIR, project_name, filename)

    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404

    # Для текстовых файлов
    if any(filename.lower().endswith(ext) for ext in ['.py', '.txt', '.html', '.css', '.php', '.js']):
        with open(file_path, 'r') as f:
            return jsonify({'content': f.read()})

    # Для изображений
    if any(filename.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif']):
        return send_file(file_path)

    return send_file(file_path)

@app.route('/api/project/<project_name>/delete', methods=['POST'])
@login_required
def api_delete_project(project_name):
    project_path = os.path.join(SCRIPTS_DIR, project_name)
    service_name = f"{project_name}.service"
    service_path = os.path.join(SYSTEMD_DIR, service_name)

    # Остановка и отключение сервиса
    try:
        subprocess.run(['systemctl', 'stop', service_name], check=True)
        subprocess.run(['systemctl', 'disable', service_name], check=True)
    except subprocess.CalledProcessError:
        pass  # Если сервис не существует, игнорируем ошибку

    # Удаление файла сервиса
    if os.path.exists(service_path):
        os.remove(service_path)
        subprocess.run(['systemctl', 'daemon-reload'])

    # Удаление директории проекта
    if os.path.exists(project_path):
        shutil.rmtree(project_path)
        return jsonify({'success': True})

    return jsonify({'error': 'Проект не найден'}), 404

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    if data.get('username') == USERNAME and data.get('password') == PASSWORD:
        session['logged_in'] = True
        return jsonify({'success': True})
    return jsonify({'error': 'Неверные учетные данные'}), 401


@app.route('/api/logout')
def api_logout():
    session.pop('logged_in', None)
    return jsonify({'success': True})


@app.route('/api/projects')
@login_required
def api_projects():
    projects = []
    for item in os.listdir(SCRIPTS_DIR):
        item_path = os.path.join(SCRIPTS_DIR, item)
        if os.path.isdir(item_path) and item not in ['venv', 'systemd', 'site']:
            service_name = f"{item}.service"
            projects.append({
                'name': item,
                'has_service': os.path.exists(os.path.join(SYSTEMD_DIR, service_name)),
                'status': get_service_status(item)
            })
    return jsonify({'projects': projects})


@app.route('/api/project/<project_name>')
@login_required
def api_project(project_name):
    project_path = os.path.join(SCRIPTS_DIR, project_name)
    if not os.path.exists(project_path):
        return jsonify({'error': 'Проект не найден'}), 404

    files = []
    for f in os.listdir(project_path):
        file_path = os.path.join(project_path, f)
        if os.path.isfile(file_path):
            # Определяем тип содержимого
            is_text = any(f.lower().endswith(ext) for ext in ['.py', '.txt', '.html', '.css', '.php', '.js'])
            content = ''
            if is_text:
                with open(file_path, 'r') as file:
                    content = file.read()

            files.append({
                'name': f,
                'content': content,
                'type': 'text' if is_text else 'binary'
            })

    return jsonify({
        'project': project_name,
        'files': files,
        'status': get_service_status(project_name)
    })


@app.route('/api/save/<project_name>/<filename>', methods=['POST'])
@login_required
def api_save(project_name, filename):
    data = request.get_json()
    filepath = os.path.join(SCRIPTS_DIR, project_name, filename)

    try:
        with open(filepath, 'w') as f:
            f.write(data.get('content', ''))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/service/<project_name>/<action>')
@login_required
def api_service(project_name, action):
    service_name = f"{project_name}.service"
    service_path = os.path.join(SYSTEMD_DIR, service_name)

    if not os.path.exists(service_path):
        create_service_file(project_name)

    commands = {
        'start': ['systemctl', 'start', service_name],
        'stop': ['systemctl', 'stop', service_name],
        'restart': ['systemctl', 'restart', service_name],
        'enable': ['systemctl', 'enable', service_name],
        'disable': ['systemctl', 'disable', service_name],
        'status': ['systemctl', 'status', service_name]
    }

    if action in commands:
        try:
            result = subprocess.run(
                commands[action],
                capture_output=True,
                text=True
            )
            if action == 'enable':
                subprocess.run(['systemctl', 'start', service_name])

            return jsonify({
                'success': True,
                'output': result.stdout,
                'status': get_service_status(project_name)
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return jsonify({'error': 'Неверное действие'}), 400


@app.route('/api/create_project', methods=['POST'])
@login_required
def api_create_project():
    data = request.get_json()
    project_name = data.get('name')
    if not project_name:
        return jsonify({'error': 'Укажите название проекта'}), 400

    project_path = os.path.join(SCRIPTS_DIR, project_name)
    if os.path.exists(project_path):
        return jsonify({'error': 'Проект уже существует'}), 400

    os.makedirs(project_path)
    with open(os.path.join(project_path, 'bot.py'), 'w') as f:
        f.write('# Ваш бот код здесь\nprint("Привет от вашего бота!")')

    return jsonify({'success': True})


def create_service_file(project_name):
    service_content = f"""
[Unit]
Description={project_name} бот
After=syslog.target
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory={os.path.join(SCRIPTS_DIR, project_name)}
ExecStart={VENV_DIR}/bin/python3 {os.path.join(SCRIPTS_DIR, project_name, 'bot.py')}
RestartSec=10
Restart=always

[Install]
WantedBy=multi-user.target
"""

    # Создаем основной сервис
    service_path = os.path.join(SYSTEMD_DIR, f"{project_name}.service")
    os.symlink(service_path, os.path.join('/etc/systemd/system', f"{project_name}.service"))
    with open(service_path, 'w') as f:
        f.write(service_content)

    subprocess.run(['systemctl', 'daemon-reload'])


def get_service_status(project_name):
    try:
        result = subprocess.run(
            ['systemctl', 'is-active', f"{project_name}.service"],
            capture_output=True,
            text=True
        )
        return result.stdout.strip()
    except:
        return 'inactive'


@app.route('/api/project/<project_name>/structure')
@login_required
def api_project_structure(project_name):
    project_path = os.path.join(SCRIPTS_DIR, project_name)

    def get_structure(path):
        structure = []
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            if os.path.isdir(item_path):
                structure.append({
                    'name': item,
                    'type': 'directory',
                    'children': get_structure(item_path)
                })
            else:
                structure.append({
                    'name': item,
                    'type': 'file'
                })
        return structure

    return jsonify({'structure': get_structure(project_path)})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=True)