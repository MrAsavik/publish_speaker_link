## 🔧 Возможности

* Поддержка приватных каналов (поиск/выбор)
* Авторизация по username (`AUTHORIZED_USERNAMES`) — защита от flood
* Автоматический мониторинг эфиров с авто-размутом участников
* Команды `/watch`, `/stop`, `/status` и админ-контроль (`ADMIN_IDS`)
* Метрики нагрузки: время итерации и число участников
* Автоперезапуск клиента при падении

---

## 📦 requirements.txt

```text
telethon>=1.24.0
python-dotenv>=0.21.0
```

---

## 🛠 .env‑пример

Создайте файл `.env` в корне проекта:

```
dotenv
API_ID=your_api_id
API_HASH=your_api_hash
PHONE=+71234567890
SESSION_NAME=voice_access_bot

```

* `CHROME_PROFILE_DIR` — путь к профилю Chrome с уже залогиненным Telegram Web
* `ADMIN_IDS` — список Telegram ID администраторов, которые могут менять конфиг и управлять мониторингом
* `AUTHORIZED_USERNAMES` — список Telegram username для команды `/scan_connect`

---

## 🚀 Установка

1. Клонируйте репозиторий.
2. Установите зависимости:

   ```bash
   pip install -r requirements.txt
   ```
3. Создайте и настройте `.env` по примеру выше.
4. Подготовьте Chrome‑профиль с авторизацией в web.telegram.org.


## 🧩 Работа приватного режима

1. `/start` → `➕ Добавить канал` → `2. private`
2. Введите часть названия или username канала
3. Выберите нужный из списка, если найдено несколько
4. Канал сохранится в `config.json` с типом `private`

---


## 🔒 Контроль доступа

* Команды `/watch`, `/stop`, `/status`, `/start` 
---

> По вопросам настройки и доработок обращайтесь к автору проекта. https://t.me/TopHelpLink
---

## ⚙️ Проверка подключения

В личном чате с ботом отправьте:

```
/scan_connect
```

Если в ответе `✅ Web Telegram доступен.`, Selenium успешно поднимает WebDriver.

---

## 💡 Отправка ссылки (invite-link)

* **Public**: через Telethon API `ExportGroupCallInvite`.
* **Private**: эмуляция Web-export через Selenium + WebDriver.

---Это уже не актуально не путай.