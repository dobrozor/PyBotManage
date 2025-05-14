from flask import Flask, render_template, request, jsonify, session, send_file
import os
import subprocess
from functools import wraps
import shutil
import paramiko
import uuid
import time
import re
from html import escape
from threading import Thread, Lock
import queue

app = Flask(__name__, template_folder='templates')
app.secret_key = '1020315'
BASE_DIR = '/root/bots'
SCRIPTS_DIR = BASE_DIR
VENV_DIR = os.path.join(BASE_DIR, 'venv')
SYSTEMD_DIR = '/root/bots/systemd'

# Настройки аутентификации
USERNAME = 'dobrozor'
PASSWORD = 'cvbn765431'

# Конфигурация SSH
SSH_HOST = '37.220.86.79'
SSH_PORT = 22
SSH_USERNAME = 'root'
SSH_PASSWORD = 'cvbn765431'

ssh_sessions = {}
output_queues = {}
session_lock = Lock()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return jsonify({'error': 'Требуется авторизация'}), 401
        return f(*args, **kwargs)
    return decorated_function


def ansi_to_html(text):
    # Удаляем эхо команды (все между \r\n и следующим $)
    text = re.sub(r'\r\n.*?\$.*?\r\n', '', text, flags=re.DOTALL)

    # Заменяем стандартное приглашение
    text = re.sub(r'\(venv\).*?#', '', text)  # Полностью удаляем исходное приглашение
    # Упрощенная обработка ANSI цветов
    ansi_colors = {
        '0;30': 'color: #1e1e1e',  # black
        '0;31': 'color: #dc3545',  # red
        '0;32': 'color: #28a745',  # green
        '0;33': 'color: #ffc107',  # yellow
        '0;34': 'color: #007bff',  # blue
        '0;35': 'color: #e83e8c',  # magenta
        '0;36': 'color: #17a2b8',  # cyan
        '0;37': 'color: #f8f9fa',  # white
        '1;30': 'color: #6c757d',  # bright black
        '1;31': 'color: #dc3545',  # bright red
        '1;32': 'color: #28a745',  # bright green
        '1;33': 'color: #ffc107',  # bright yellow
        '1;34': 'color: #007bff',  # bright blue
        '1;35': 'color: #e83e8c',  # bright magenta
        '1;36': 'color: #17a2b8',  # bright cyan
        '1;37': 'color: #ffffff',  # bright white
    }

    for code, style in ansi_colors.items():
        text = text.replace(f'\033[{code}m', f'<span style="{style}">')
    text = text.replace('\033[0m', '</span>')

    # Удаляем оставшиеся ANSI коды
    text = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', text)

    # Удаляем лишние закрывающие теги </span>
    text = re.sub(r'(</span>)+', '', text)

    # Обработка переносов и пробелов
    text = escape(text).replace('\n', '<br>').replace('\r', '')
    lines = []
    for line in text.split('<br>'):
        line = re.sub(r'^\s+', lambda m: '&nbsp;' * len(m.group()), line)
        lines.append(line)
    return '<br>'.join(lines)

def create_ssh_connection():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        hostname=SSH_HOST,
        port=SSH_PORT,
        username=SSH_USERNAME,
        password=SSH_PASSWORD,
        timeout=30
    )
    return ssh

def execute_initial_commands(shell):
    commands = ['cd bots', 'source venv/bin/activate', 'cd']
    for cmd in commands:
        shell.send(cmd + '\n')
        time.sleep(0.5)
        while shell.recv_ready():
            shell.recv(65536)

def output_reader(session_id, shell):
    while True:
        with session_lock:
            if session_id not in ssh_sessions:
                break

        try:
            if shell.recv_ready():
                data = shell.recv(65536).decode('utf-8', 'ignore')
                with session_lock:
                    if session_id in output_queues:
                        output_queues[session_id].put(data)
            else:
                time.sleep(0.5)
        except (paramiko.SSHException, OSError):
            break

@app.route('/terminal')
@login_required
def terminal():
    session_id = str(uuid.uuid4())
    try:
        ssh = create_ssh_connection()
        shell = ssh.invoke_shell(term='xterm', width=200, height=50)
        execute_initial_commands(shell)

        with session_lock:
            ssh_sessions[session_id] = {'ssh': ssh, 'shell': shell}
            output_queues[session_id] = queue.Queue()

        reader_thread = Thread(target=output_reader, args=(session_id, shell))
        reader_thread.daemon = True
        reader_thread.start()

        session['terminal_session_id'] = session_id
        return render_template('terminal.html', SSH_USERNAME=SSH_USERNAME, SSH_HOST=SSH_HOST)
    except Exception as e:
        return f"Connection Error: {str(e)}"

# Добавьте эти маршруты если их нет
@app.route('/terminal/init', methods=['POST'])
@login_required
def terminal_init():
    session_id = str(uuid.uuid4())
    try:
        ssh = create_ssh_connection()
        shell = ssh.invoke_shell(term='xterm', width=200, height=50)
        execute_initial_commands(shell)

        with session_lock:
            ssh_sessions[session_id] = {'ssh': ssh, 'shell': shell}
            output_queues[session_id] = queue.Queue()

        reader_thread = Thread(target=output_reader, args=(session_id, shell))
        reader_thread.daemon = True
        reader_thread.start()

        return jsonify({'success': True, 'session_id': session_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/terminal/exec', methods=['POST'])
@login_required
def terminal_exec():
    session_id = request.form.get('session_id')
    if not session_id or session_id not in ssh_sessions:
        return jsonify({'error': 'Invalid session'}), 400

    command = request.form.get('command', '')
    shell = ssh_sessions[session_id]['shell']

    control_mappings = {
        'ctrl+z': '\x1a',  # SIGTSTP (остановка процесса)
        'ctrl+c': '\x03',  # SIGINT (прерывание)
        'ctrl+d': '\x04',  # EOF
        'ctrl+l': '\x0c',  # Очистка экрана
        'ctrl+a': '\x01',  # Начало строки
        'ctrl+e': '\x05',  # Конец строки
        'ctrl+k': '\x0b',  # Удалить до конца строки
        'up': '\x1b[A',  # Стрелка вверх
        'down': '\x1b[B',  # Стрелка вниз
        'right': '\x1b[C',  # Стрелка вправо
        'left': '\x1b[D'  # Стрелка влево
    }

    if command in ['up', 'down', 'right', 'left']:
        shell.send(control_mappings[command])
        return jsonify({'success': True})

    try:
        if command.lower() in control_mappings:
            shell.send(control_mappings[command.lower()])
        else:
            shell.send(command + '\n')
        return jsonify({'success': True})
    except (paramiko.SSHException, OSError) as e:
        return jsonify({'error': str(e)}), 500

@app.route('/terminal/get_output')
@login_required
def terminal_get_output():
    session_id = request.args.get('session_id')
    if not session_id or session_id not in ssh_sessions:
        return jsonify({'output': '', 'status': 'error'})

    output = []
    with session_lock:
        if session_id in output_queues:
            while not output_queues[session_id].empty():
                output.append(output_queues[session_id].get())

    processed = ''.join(output)
    processed = processed.replace('\r\n', '\n').replace('\r', '')
    return jsonify({
        'output': ansi_to_html(processed),
        'status': 'success'
    })

@app.route('/terminal/cleanup', methods=['POST'])
@login_required
def terminal_cleanup():
    session_id = request.form.get('session_id')
    if session_id:
        with session_lock:
            if session_id in ssh_sessions:
                try:
                    ssh_sessions[session_id]['shell'].close()
                    ssh_sessions[session_id]['ssh'].close()
                except:
                    pass
                del ssh_sessions[session_id]
            if session_id in output_queues:
                del output_queues[session_id]
    return jsonify({'status': 'success'})

@app.route('/vds')
@login_required
def vds_terminal():
    return render_template('terminal.html', SSH_USERNAME=SSH_USERNAME, SSH_HOST=SSH_HOST)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/project/<project_name>/<filename>')
@login_required
def api_get_project_file(project_name, filename):
    file_path = os.path.join(SCRIPTS_DIR, project_name, filename)
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404

    if any(filename.lower().endswith(ext) for ext in ['.py', '.txt', '.html', '.css', '.php', '.js']):
        with open(file_path, 'r') as f:
            return jsonify({'content': f.read()})

    if any(filename.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif']):
        return send_file(file_path)

    return send_file(file_path)

@app.route('/api/project/<project_name>/delete', methods=['POST'])
@login_required
def api_delete_project(project_name):
    project_path = os.path.join(SCRIPTS_DIR, project_name)
    service_name = f"{project_name}.service"
    service_path = os.path.join(SYSTEMD_DIR, service_name)

    try:
        subprocess.run(['systemctl', 'stop', service_name], check=True)
        subprocess.run(['systemctl', 'disable', service_name], check=True)
    except subprocess.CalledProcessError:
        pass

    if os.path.exists(service_path):
        os.remove(service_path)
        subprocess.run(['systemctl', 'daemon-reload'])

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
    session.pop('terminal_session_id', None)
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