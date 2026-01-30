// VDS Manager - JavaScript функции

// Показать уведомление
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `flash flash-${type}`;
    notification.innerHTML = `
        <span class="flash-icon">
            ${type === 'success' ? '✅' : type === 'error' ? '❌' : type === 'warning' ? '⚠️' : 'ℹ️'}
        </span>
        ${message}
    `;

    const flashContainer = document.querySelector('.flash-messages');
    if (flashContainer) {
        flashContainer.appendChild(notification);

        // Автоматическое удаление через 5 секунд
        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transform = 'translateY(-10px)';
            setTimeout(() => notification.remove(), 300);
        }, 5000);
    }
}

// Подтверждение перед удалением
function confirmAction(message) {
    return confirm(message);
}

// Обновление статуса проекта
function updateProjectStatus(projectName) {
    fetch(`/project/${projectName}/status`)
        .then(response => response.json())
        .then(data => {
            const statusElements = document.querySelectorAll(`[data-project="${projectName}"] .status`);
            statusElements.forEach(el => {
                el.textContent = data.status;
                el.className = 'status status-' + data.status;
            });
        })
        .catch(err => console.error('Ошибка обновления статуса:', err));
}

// Автообновление статусов всех проектов
function startStatusMonitoring() {
    const projectCards = document.querySelectorAll('.project-card');
    if (projectCards.length > 0) {
        setInterval(() => {
            projectCards.forEach(card => {
                const projectName = card.querySelector('.project-name').textContent;
                updateProjectStatus(projectName);
            });
        }, 5000);
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Запуск мониторинга статусов на дашборде
    if (document.querySelector('.projects-grid')) {
        startStatusMonitoring();
    }

    // Обработка форм с подтверждением
    const deleteForms = document.querySelectorAll('.delete-form');
    deleteForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const projectName = this.closest('[data-project]')?.dataset.project ||
                               this.querySelector('button').title.match(/"([^"]+)"/)?.[1] ||
                               'этот проект';

            if (!confirm(`Вы уверены, что хотите удалить проект "${projectName}"?\n\nВсе файлы будут безвозвратно удалены!`)) {
                e.preventDefault();
                return false;
            }
        });
    });

    // Обработка загрузки файлов
    const fileInputs = document.querySelectorAll('input[type="file"]');
    fileInputs.forEach(input => {
        input.addEventListener('change', function() {
            if (this.files.length > 0) {
                const fileName = this.files[0].name;
                console.log('Выбран файл:', fileName);
            }
        });
    });
});

// Функция для копирования текста
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showNotification('Скопировано в буфер обмена!', 'success');
    }).catch(err => {
        showNotification('Ошибка копирования: ' + err, 'error');
    });
}

// Обновление логов в реальном времени (альтернативная реализация)
function autoUpdateLogs(projectName, interval = 2000) {
    const logsElement = document.getElementById('logs');
    if (!logsElement || !projectName) return;

    let lastLogLength = 0;

    setInterval(async () => {
        try {
            const response = await fetch(`/project/${projectName}/logs`);
            const data = await response.json();

            if (data.logs) {
                const currentLength = data.logs.length;

                // Обновляем только если логи изменились
                if (currentLength !== lastLogLength) {
                    logsElement.textContent = data.logs;
                    logsElement.scrollTop = logsElement.scrollHeight;
                    lastLogLength = currentLength;
                }
            }
        } catch (error) {
            console.error('Ошибка обновления логов:', error);
        }
    }, interval);
}

// Экспортируем функции для использования в шаблонах
window.showNotification = showNotification;
window.confirmAction = confirmAction;
window.copyToClipboard = copyToClipboard;
window.autoUpdateLogs = autoUpdateLogs;