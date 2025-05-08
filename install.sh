#!/bin/bash

# Автоматическая установка без вопросов
export DEBIAN_FRONTEND=noninteractive

# Обновление и установка пакетов
echo -e "\033[34m[1/8] Обновление пакетов...\033[0m"
sudo apt-get update -y
sudo apt-get upgrade -y
sudo apt-get install -y openssh-server ufw nano git python3.8-venv python3-pip

# Настройка firewall
echo -e "\033[34m[2/8] Настройка firewall...\033[0m"
yes | sudo ufw enable
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw allow 5000/tcp # Flask
sudo ufw allow 8080/tcp # Альтернативный порт

# Создание структуры проекта
echo -e "\033[34m[3/8] Создание структуры проекта...\033[0m"
mkdir -p ~/bots/{systemd,site/templates}
cd ~/bots

# Виртуальное окружение
echo -e "\033[34m[4/8] Настройка виртуального окружения...\033[0m"
python3.8 -m venv venv
source venv/bin/activate

# Установка Flask и зависимостей
echo -e "\033[34m[5/8] Установка зависимостей Python...\033[0m"
pip install flask shutil

# Загрузка файлов проекта
echo -e "\033[34m[6/8] Загрузка файлов проекта...\033[0m"
cd ~/bots/site
wget -qO bot.py https://raw.githubusercontent.com/dobrozor/PyBotManage/main/bot.py
wget -qO templates/index.html https://raw.githubusercontent.com/dobrozor/PyBotManage/main/templates/index.html

# Systemd сервис
echo -e "\033[34m[7/8] Настройка systemd сервиса...\033[0m"
sudo bash -c 'cat > /root/bots/systemd/site.service <<EOF
[Unit]
Description=WebSite PythonManager
After=network.target

[Service]
User=root
WorkingDirectory=/root/bots/site
ExecStart=/root/bots/venv/bin/python3 /root/bots/site/bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF'

# Освобождение порта 80 и запуск сервиса
echo -e "\033[34m[8/8] Запуск сервиса...\033[0m"
sudo kill -9 $(sudo lsof -t -i:80) 2>/dev/null || true
sudo systemctl daemon-reload
sudo systemctl enable /root/bots/systemd/site.service
sudo systemctl enable --now site.service

# Получение IP
IP=$(hostname -I | awk '{print $1}')
echo -e "\n\033[32mУстановка успешно завершена!\033[0m"
echo -e "Сервис запущен и работает"
echo -e "Доступные адреса:"
echo -e " • \033[34mhttp://$IP\033[0m"
echo -e " • \033[34mhttp://$IP:5000\033[0m"
echo -e "\nПроверить статус: \033[33msystemctl status site.service\033[0m"
