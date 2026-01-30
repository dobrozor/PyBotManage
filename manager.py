#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Менеджер проектов для VDS Manager
Управление созданием, запуском и остановкой проектов через systemd
"""

import os
import subprocess
import shutil
import logging
from pathlib import Path




class ProjectManager:
    """Класс для управления проектами"""

    def __init__(self, root_dir, systemd_dir):
        """
        Инициализация менеджера проектов

        Args:
            root_dir: Корневая директория где лежат все проекты (/root/bots)
            systemd_dir: Путь к директории с .service файлами
        """
        self.root_dir = root_dir
        self.systemd_dir = systemd_dir

        # Создаем директории, если их нет
        try:
            os.makedirs(systemd_dir, exist_ok=True)
            logger.info(f"Создана директория systemd: {systemd_dir}")
        except Exception as e:
            logger.error(f"Ошибка создания директории systemd: {e}")

        # Список служебных папок, которые не являются проектами
        self.excluded_dirs = {'site', 'systemd', 'venv', '__pycache__', '.git'}

    # ==================== Базовые методы ====================

    def project_exists(self, name):
        """
        Проверяет, существует ли проект

        Args:
            name: Имя проекта

        Returns:
            bool: True если проект существует
        """
        project_path = os.path.join(self.root_dir, name)
        exists = os.path.isdir(project_path) and name not in self.excluded_dirs
        logger.debug(f"Проверка существования проекта '{name}': {exists}")
        return exists

    def get_projects(self):
        """
        Возвращает список всех проектов (всех папок кроме служебных)

        Returns:
            list: Список имен проектов
        """
        projects = []

        if not os.path.exists(self.root_dir):
            logger.error(f"Корневая директория не существует: {self.root_dir}")
            return projects

        try:
            for item in os.listdir(self.root_dir):
                item_path = os.path.join(self.root_dir, item)

                # Проверяем, что это директория и не в списке исключений
                if os.path.isdir(item_path) and item not in self.excluded_dirs:
                    projects.append(item)

            logger.info(f"Найдено проектов: {len(projects)}")
            return sorted(projects)
        except Exception as e:
            logger.error(f"Ошибка получения списка проектов: {e}")
            return projects

    # ==================== Создание и удаление проектов ====================

    def create_project(self, name):
        """
        Создает новый проект с базовой структурой

        Args:
            name: Имя проекта

        Raises:
            ValueError: Если проект уже существует или имя некорректное
        """
        logger.info(f"Начало создания проекта: {name}")

        if not name or not name.replace('_', '').replace('-', '').isalnum():
            error_msg = 'Имя проекта может содержать только буквы, цифры, дефисы и подчеркивания'
            logger.error(f"Некорректное имя проекта '{name}': {error_msg}")
            raise ValueError(error_msg)

        project_path = os.path.join(self.root_dir, name)

        if os.path.exists(project_path):
            error_msg = f'Проект "{name}" уже существует'
            logger.error(error_msg)
            raise ValueError(error_msg)

        try:
            # Создаем директорию проекта
            logger.info(f"Создание директории проекта: {project_path}")
            os.makedirs(project_path, exist_ok=True)
            logger.info(f"Директория проекта создана: {project_path}")

            # Проверяем, что директория создана
            if not os.path.exists(project_path):
                raise Exception(f"Не удалось создать директорию: {project_path}")

            # Создаем основной файл проекта
            main_file = os.path.join(project_path, 'main.py')
            logger.info(f"Создание файла main.py: {main_file}")

            with open(main_file, 'w', encoding='utf-8') as f:
                f.write("""#!/usr/bin/env python3
# -*- coding: utf-8 -*-
\"\"\"
Основной файл проекта: {name}
Запустите свой код здесь
\"\"\"

def main():
    print(f"Проект '{name}' успешно запущен!")
    print("Начинаю выполнение...")

    # Ваш код здесь
    # Например:
    # while True:
    #     # Основной цикл программы
    #     pass

if __name__ == '__main__':
    main()
""".format(name=name))

            logger.info(f"Файл main.py создан: {main_file}")

            # Создаем .service файл для проекта
            service_name = f"{name}.service"
            service_path = os.path.join(self.systemd_dir, service_name)

            logger.info(f"Создание .service файла: {service_path}")

            # Определяем путь к Python в виртуальном окружении
            venv_python = "/root/bots/venv/bin/python3"

            # Проверяем существование виртуального окружения
            if not os.path.exists(venv_python):
                logger.warning(f"Виртуальное окружение не найдено: {venv_python}")
                logger.warning("Используем системный Python")
                venv_python = "/usr/bin/python3"

            with open(service_path, 'w', encoding='utf-8') as f:
                f.write(f"""[Unit]
Description=Project {name} Service
After=network.target

[Service]
User=root
WorkingDirectory={project_path}
ExecStart={venv_python} {main_file}
Restart=always
RestartSec=5
StandardOutput=append:/var/log/{name}.log
StandardError=append:/var/log/{name}.log

[Install]
WantedBy=multi-user.target
""")

            logger.info(f".service файл создан: {service_path}")

            # Копируем сервис в системную директорию systemd и активируем
            system_service_path = f'/etc/systemd/system/{service_name}'

            logger.info(f"Копирование сервиса в системную директорию: {system_service_path}")

            # Используем sudo для копирования
            try:
                subprocess.run(['sudo', 'cp', service_path, system_service_path], check=True, capture_output=True)
                logger.info(f"Сервис скопирован в системную директорию")
            except subprocess.CalledProcessError as e:
                logger.error(f"Ошибка копирования сервиса: {e.stderr.decode()}")
                raise Exception(f"Не удалось скопировать .service файл: {e.stderr.decode()}")

            # Перезагружаем systemd
            try:
                subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True, capture_output=True)
                logger.info("systemd daemon-reload выполнен")
            except subprocess.CalledProcessError as e:
                logger.error(f"Ошибка daemon-reload: {e.stderr.decode()}")
                raise Exception(f"Не удалось перезагрузить systemd: {e.stderr.decode()}")

            # Создаем файл логов
            log_path = f'/var/log/{name}.log'
            logger.info(f"Создание файла логов: {log_path}")

            try:
                # Создаем файл логов с правильными правами
                subprocess.run(['sudo', 'touch', log_path], check=True, capture_output=True)
                subprocess.run(['sudo', 'chmod', '666', log_path], check=True, capture_output=True)
                logger.info(f"Файл логов создан: {log_path}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Ошибка создания файла логов: {e.stderr.decode()}")
                raise Exception(f"Не удалось создать файл логов: {e.stderr.decode()}")

            logger.info(f"Проект '{name}' создан успешно")

        except Exception as e:
            logger.error(f"Ошибка создания проекта '{name}': {e}", exc_info=True)
            # Очищаем созданные файлы в случае ошибки
            try:
                if os.path.exists(project_path):
                    shutil.rmtree(project_path)
                service_path = os.path.join(self.systemd_dir, f"{name}.service")
                if os.path.exists(service_path):
                    os.remove(service_path)
                system_service_path = f'/etc/systemd/system/{name}.service'
                if os.path.exists(system_service_path):
                    subprocess.run(['sudo', 'rm', '-f', system_service_path], check=False)
            except Exception as cleanup_error:
                logger.error(f"Ошибка очистки после неудачного создания: {cleanup_error}")

            raise e

    def delete_project(self, name):
        """
        Удаляет проект со всеми файлами и сервисами

        Args:
            name: Имя проекта

        Raises:
            ValueError: Если проект не найден
        """
        logger.info(f"Начало удаления проекта: {name}")

        if not self.project_exists(name):
            error_msg = f'Проект "{name}" не найден'
            logger.error(error_msg)
            raise ValueError(error_msg)

        try:
            # Останавливаем сервис, если он запущен
            try:
                self.stop_project(name)
                logger.info(f"Сервис проекта остановлен: {name}")
            except Exception as e:
                logger.warning(f"Ошибка остановки сервиса (игнорируем): {e}")

            # Удаляем сервис из systemd
            service_name = f"{name}.service"
            system_service_path = f'/etc/systemd/system/{service_name}'

            if os.path.exists(system_service_path):
                try:
                    subprocess.run(['sudo', 'systemctl', 'disable', service_name], check=False, capture_output=True)
                    subprocess.run(['sudo', 'rm', '-f', system_service_path], check=True, capture_output=True)
                    logger.info(f"Системный .service файл удален: {system_service_path}")
                except subprocess.CalledProcessError as e:
                    logger.error(f"Ошибка удаления системного .service файла: {e.stderr.decode()}")

            # Удаляем логи
            log_path = f'/var/log/{name}.log'
            if os.path.exists(log_path):
                try:
                    os.remove(log_path)
                    logger.info(f"Файл логов удален: {log_path}")
                except Exception as e:
                    logger.error(f"Ошибка удаления файла логов: {e}")

            # Удаляем директорию проекта
            project_path = os.path.join(self.root_dir, name)
            if os.path.exists(project_path):
                try:
                    shutil.rmtree(project_path)
                    logger.info(f"Директория проекта удалена: {project_path}")
                except Exception as e:
                    logger.error(f"Ошибка удаления директории проекта: {e}")
                    raise

            # Удаляем .service файл из папки менеджера
            manager_service = os.path.join(self.systemd_dir, service_name)
            if os.path.exists(manager_service):
                try:
                    os.remove(manager_service)
                    logger.info(f".service файл менеджера удален: {manager_service}")
                except Exception as e:
                    logger.error(f"Ошибка удаления .service файла менеджера: {e}")

            logger.info(f"Проект '{name}' удален успешно")

        except Exception as e:
            logger.error(f"Ошибка удаления проекта '{name}': {e}", exc_info=True)
            raise

    # ==================== Управление сервисами ====================

    def start_project(self, name):
        """
        Запускает проект

        Args:
            name: Имя проекта

        Raises:
            ValueError: Если проект не найден
            subprocess.CalledProcessError: Если не удалось запустить сервис
        """
        if not self.project_exists(name):
            raise ValueError(f'Проект "{name}" не найден')

        service_name = f"{name}.service"
        try:
            logger.info(f"Запуск сервиса: {service_name}")
            subprocess.run(['sudo', 'systemctl', 'start', service_name], check=True, capture_output=True)
            logger.info(f"Сервис запущен: {service_name}")
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"Ошибка запуска сервиса {service_name}: {error_msg}")
            raise Exception(f"Не удалось запустить проект: {error_msg}")

    def stop_project(self, name):
        """
        Останавливает проект

        Args:
            name: Имя проекта
        """
        service_name = f"{name}.service"
        try:
            logger.info(f"Остановка сервиса: {service_name}")
            subprocess.run(['sudo', 'systemctl', 'stop', service_name], check=True, capture_output=True)
            logger.info(f"Сервис остановлен: {service_name}")
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"Ошибка остановки сервиса {service_name}: {error_msg}")
            raise Exception(f"Не удалось остановить проект: {error_msg}")

    def restart_project(self, name):
        """
        Перезапускает проект

        Args:
            name: Имя проекта

        Raises:
            subprocess.CalledProcessError: Если не удалось перезапустить сервис
        """
        service_name = f"{name}.service"
        try:
            logger.info(f"Перезапуск сервиса: {service_name}")
            subprocess.run(['sudo', 'systemctl', 'restart', service_name], check=True, capture_output=True)
            logger.info(f"Сервис перезапущен: {service_name}")
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"Ошибка перезапуска сервиса {service_name}: {error_msg}")
            raise Exception(f"Не удалось перезапустить проект: {error_msg}")

    def get_project_status(self, name):
        """
        Возвращает статус проекта

        Args:
            name: Имя проекта

        Returns:
            str: Статус (active, inactive, failed, unknown)
        """
        service_name = f"{name}.service"
        try:
            result = subprocess.run(['sudo', 'systemctl', 'is-active', service_name],
                                    capture_output=True, text=True, timeout=3)
            status = result.stdout.strip()
            logger.debug(f"Статус проекта '{name}': {status}")
            return status
        except subprocess.TimeoutExpired:
            logger.warning(f"Таймаут при получении статуса проекта '{name}'")
            return 'timeout'
        except Exception as e:
            logger.error(f"Ошибка получения статуса проекта '{name}': {e}")
            return 'unknown'

    # ==================== Работа с файлами ====================

    def get_project_files(self, name):
        """
        Возвращает список файлов в проекте

        Args:
            name: Имя проекта

        Returns:
            list: Список путей к файлам относительно директории проекта
        """
        project_path = os.path.join(self.root_dir, name)
        files = []

        if not os.path.exists(project_path):
            logger.warning(f"Директория проекта не существует: {project_path}")
            return files

        try:
            for root, _, filenames in os.walk(project_path):
                for filename in filenames:
                    full_path = os.path.join(root, filename)
                    rel_path = os.path.relpath(full_path, project_path)
                    files.append(rel_path)

            logger.debug(f"Найдено файлов в проекте '{name}': {len(files)}")
            return sorted(files)
        except Exception as e:
            logger.error(f"Ошибка получения списка файлов проекта '{name}': {e}")
            return files

    def get_project_logs(self, name):
        """
        Возвращает последние логи проекта

        Args:
            name: Имя проекта

        Returns:
            str: Последние 200 строк логов
        """
        log_path = f'/var/log/{name}.log'

        if not os.path.exists(log_path):
            return 'Логи еще не созданы. Запустите проект.'

        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                # Возвращаем последние 200 строк
                result = ''.join(lines[-200:]) if len(lines) > 200 else ''.join(lines)
                logger.debug(f"Прочитано строк логов для проекта '{name}': {len(lines)}")
                return result
        except Exception as e:
            error_msg = f'Ошибка чтения логов: {str(e)}'
            logger.error(error_msg)
            return error_msg