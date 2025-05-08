#!/bin/bash

# Установка и обновление пакетов
sudo apt-get install -y openssh-server ufw python3.8-venv nano git

# Настройка firewall
sudo ufw enable
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 5000
sudo ufw allow 443
sudo ufw allow 8080

# Создание директорий и виртуального окружения
mkdir -p ~/bots/systemd
mkdir -p ~/bots/site/templates
cd ~/bots
python3 -m venv venv
source venv/bin/activate

# Клонирование файлов из GitHub
cd ~/bots/site
# Замените ссылки на актуальные из вашего репозитория
wget https://raw.githubusercontent.com/dobrozor/PyBotManage/main/bot.py
wget https://raw.githubusercontent.com/dobrozor/PyBotManage/main/templates/index.html -P templates

# Создание service файла
cat <<EOF > ~/bots/systemd/site.service
[Unit]
Description=WebSite PythonManager
After=syslog.target
After=network.target
 
[Service]
Type=simple
User=root
WorkingDirectory=/root/bots/site
ExecStart=/root/bots/venv/bin/python3 /root/bots/site/bot.py
RestartSec=5
Restart=always
 
[Install]
WantedBy=multi-user.target
EOF

# Установка Python зависимостей
pip install flask os-subprocess functools shutil

# Настройка и запуск сервиса
sudo systemctl enable /root/bots/systemd/site.service
sudo systemctl start site

echo "Твой сайт готов! Переходи по айпи адресу твоего сервера."
