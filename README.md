Вот обновление README и `requirements.txt`, которое поможет настроить Web-export и UserBot с режимом приватных каналов (через Selenium).

---

### 📦 requirements.txt

```text
telethon>=1.24.0
python-dotenv
selenium>=4.0
webdriver-manager>=4.0.0
```

* `selenium` – для эмуляции Telegram Web.
* `webdriver-manager` – автоматическая установка ChromeDriver ([blacksuan19.dev][1], [pypi.org][2]).

---

### 🛠 .env‑пример

Добавьте файл `.env` в корне:

```dotenv
API_ID=ваш_api_id
API_HASH=ваш_api_hash
PHONE=+71234567890
SESSION_NAME=voice_access_bot
CHROME_PROFILE_DIR=C:/путь/к/профилю/Chrome
AUTHORIZED_USERNAMES=MrAsavik,Другой
```

* Указывать путь к профилю для доступа к приватному эфиру.
* `AUTHORIZED_USERNAMES` — список, кому доступна команда `scan_connect`.



---

### 🔐 Управление доступом к `scan_connect`

Добавил проверку по username из `.env` — команда `scan_connect` работает только у авторизованных:

```python
allowed = os.getenv("AUTHORIZED_USERNAMES", "").split(",")
if sender.username not in allowed:
    return await ev.reply("❌ Доступ запрещён.")
```

---

### 📄 README: Обновлённая версия

```markdown
## 🔧 Возможности

- Генерация ссылок: public и private (через Web)
- Проверка доступа к Web через `scan_connect`
- Поддержка приватных каналов (поиск/выбор)
- Авторизация по username (skip flood)

## 🚀 Установка

1. `pip install -r requirements.txt`
2. Создать `.env`, заполнить поля, включая `CHROME_PROFILE_DIR` и `AUTHORIZED_USERNAMES`
3. Подготовить Chrome‑профиль с уже залогиненным веб‑Telegram

## ⚙️ Проверка подключения

В ЛС бота отправьте `scan_connect`, чтобы убедиться, что WebDriver может работать с указанным профилем.

## 🧩 Как работает приватный режим

- В меню: «➕ Добавить канал» → выбираете `2. private`
- Вводите часть имени или username канала
- Если найдено несколько — выбираете один по номеру
- Сохраняется в `config.json` с `id`, `hash`, `type=private`

## 💡 Отправка ссылки

- Public: через API `ExportGroupCallInvite`
- Private: через Selenium‑Web + Web‑export

```

---

### 🧩 Что нужно от тебя

Чтобы продолжить, пришли:

1. Путь `CHROME_PROFILE_DIR` (где профиль с Telegram Web).
2. Твой username (или список) для доступа `scan_connect`.
3. Подтверждение, что директория есть и в ней сохранена сессия.

После этого — все проверим и настроим окончательно!

[1]: https://blacksuan19.dev/blog/telegram-user-bot/?utm_source=chatgpt.com "How to Set up a Telegram Userbot on heroku - Blacksuan19"
[2]: https://pypi.org/project/webdriver-manager/?utm_source=chatgpt.com "webdriver-manager - PyPI"
