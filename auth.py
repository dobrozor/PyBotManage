#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Система авторизации для VDS Manager
"""

import os
import json

# Пути к файлам данных
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'site', 'data')
USERS_FILE = os.path.join(DATA_DIR, 'users.json')
FIRST_RUN_FILE = os.path.join(DATA_DIR, 'first_run.flag')


def is_first_run():
    """
    Проверяет, является ли это первой установкой.
    Возвращает True, если администратор еще не зарегистрирован.
    """
    return not os.path.exists(FIRST_RUN_FILE)


def mark_first_run_complete():
    """Помечает первую установку как завершенную"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(FIRST_RUN_FILE, 'w') as f:
        f.write('completed')


def load_users():
    """
    Загружает данные пользователей из файла.
    Возвращает словарь {username: password_hash} или None, если файл не существует.
    """
    if not os.path.exists(USERS_FILE):
        return None

    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Ошибка загрузки пользователей: {e}")
        return None


def save_user(username, password_hash):
    """
    Сохраняет пользователя в файл.
    Создает файл, если он не существует.

    Args:
        username: Имя пользователя
        password_hash: Хэшированный пароль (строка)
    """
    os.makedirs(DATA_DIR, exist_ok=True)

    # Загружаем существующих пользователей или создаем новый словарь
    users = load_users() or {}
    users[username] = password_hash

    # Сохраняем в файл
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

    # После сохранения первого пользователя помечаем установку завершенной
    if username == 'admin' and is_first_run():
        mark_first_run_complete()


def verify_password(username, password):
    """
    Проверяет пароль пользователя.
    Возвращает True, если пароль верный, иначе False.

    Args:
        username: Имя пользователя
        password: Пароль (в виде строки)

    Returns:
        bool: Результат проверки
    """
    import bcrypt

    users = load_users()
    if not users or username not in users:
        return False

    stored_hash = users[username].encode('utf-8')
    return bcrypt.checkpw(password.encode('utf-8'), stored_hash)