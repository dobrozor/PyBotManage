#!/bin/bash

# Автоматическая установка без вопросов
export DEBIAN_FRONTEND=noninteractive

# Обновление и установка пакетов
sudo apt-get update -y
sudo apt-get upgrade -y
sudo apt-get install -y openssh-server ufw nano git python3.8-venv python3-pip

# Настройка firewall (автоматическое подтверждение)
yes | sudo ufw enable
sudo ufw allow 22/tcp  # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw allow 5000/tcp # Flask
sudo ufw allow 8080/tcp # Альтернативный порт

# Создание структуры проекта
mkdir -p ~/bots/{systemd,site/templates}
cd ~/bots

# Виртуальное окружение
python3.8 -m venv venv
source venv/bin/activate

# Загрузка файлов проекта
cd ~/bots/site
wget -qO bot.py https://raw.githubusercontent.com/dobrozor/PyBotManage/main/bot.py
wget -qO templates/index.html https://raw.githubusercontent.com/dobrozor/PyBotManage/main/templates/index.html

# Systemd сервис
sudo bash -c 'cat > /etc/systemd/system/site.service <<EOF
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

# Права и сервис
sudo chmod 644 /etc/systemd/system/site.service
sudo systemctl daemon-reload
sudo systemctl enable --now site.service

# Установка зависимостей
pip install flask shutil

# Получение IP
IP=$(hostname -I | awk '{print $1}')
echo -e "\n\033[32mУстановка завершена!\033[0m"
echo -e "Сайт доступен по адресу:"
echo -e "HTTP: \033[34mhttp://$IP\033[0m"
echo -e "HTTP: \033[34mhttp://$IP:5000\033[0m"
