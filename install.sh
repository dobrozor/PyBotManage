#!/bin/bash

# Автоматическая установка без вопросов
export DEBIAN_FRONTEND=noninteractive

# Цвета
ORANGE='\033[0;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Логотип PBManager
echo -e "${ORANGE}"
echo -e " ____  ____  __  __       _           _"
echo -e "|  _ \| __ )|  \/  | __ _| |_ ___ _ __| |__   ___ _ __"
echo -e "| |_) |  _ \| |\/| |/ _\` | __/ _ \ '__| '_ \ / _ \ '__|"
echo -e "|  __/| |_) | |  | | (_| | ||  __/ |  | | | |  __/ |"
echo -e "|_|   |____/|_|  |_|\__,_|\__\___|_|  |_| |_|\___|_|"
echo -e "${NC}"
echo -e "${ORANGE}=== PyBot Manager Installation ===${NC}"
echo -e ""

# Обновление и установка пакетов
echo -e "${ORANGE}[1/8] Обновление пакетов...${NC}"
sudo apt-get update -y
sudo apt-get upgrade -y
sudo apt-get install -y openssh-server ufw nano git python3.8-venv python3-pip

# Настройка firewall
echo -e "${ORANGE}[2/8] Настройка firewall...${NC}"
yes | sudo ufw enable
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw allow 5000/tcp # Flask
sudo ufw allow 8080/tcp # Альтернативный порт

# Создание структуры проекта
echo -e "${ORANGE}[3/8] Создание структуры проекта...${NC}"
mkdir -p ~/bots/{systemd,site/templates}
cd ~/bots

# Виртуальное окружение
echo -e "${ORANGE}[4/8] Настройка виртуального окружения...${NC}"
python3.8 -m venv venv
source venv/bin/activate

# Установка Flask и зависимостей
echo -e "${ORANGE}[5/8] Установка зависимостей Python...${NC}"
pip install flask paramiko

# Загрузка файлов проекта
echo -e "${ORANGE}[6/8] Загрузка файлов проекта...${NC}"
cd ~/bots/site
wget -qO bot.py https://raw.githubusercontent.com/dobrozor/PyBotManage/main/bot.py
wget -qO templates/index.html https://raw.githubusercontent.com/dobrozor/PyBotManage/main/templates/index.html


# Systemd сервис
echo -e "${ORANGE}[7/8] Настройка systemd сервиса...${NC}"
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
echo -e "${ORANGE}[8/8] Запуск сервиса...${NC}"
sudo kill -9 $(sudo lsof -t -i:80) 2>/dev/null || true
sudo systemctl daemon-reload
sudo systemctl enable /root/bots/systemd/site.service
sudo systemctl start site.service

# Проверка статуса сервиса
if systemctl is-active --quiet site.service; then
    echo -e "${GREEN}Сервис успешно запущен!${NC}"
else
    echo -e "${RED}Ошибка: сервис не запустился${NC}"
    echo -e "${ORANGE}Попробуйте выполнить вручную:${NC}"
    echo -e "sudo systemctl status site.service"
    echo -e "journalctl -u site.service -xe"
fi

# Получение IP
IP=$(hostname -I | awk '{print $1}')
echo -e "\n${GREEN}Установка завершена!${NC}"
echo -e "${ORANGE}"
echo -e "╔════════════════════════════════════╗"
echo -e "║                                    ║"
echo -e "║   PBManager успешно установлен!    ║"
echo -e "║                                    ║"
echo -e "╚════════════════════════════════════╝"
echo -e "${NC}"
echo -e "${ORANGE}Доступные адреса:${NC}"
echo -e " • ${GREEN}http://$IP${NC}"
echo -e "${NC}"
echo -e "\n${ORANGE}Управление сервисом:${NC}"
echo -e "Запуск:    sudo systemctl start site.service"
echo -e "Остановка: sudo systemctl stop site.service"
echo -e "Статус:    sudo systemctl status site.service"
echo -e "Логи:      journalctl -u site.service -f${NC}"
