import asyncio
import json
from datetime import datetime
from pathlib import Path
from pywebio import start_server
from pywebio.input import input as input_pywebio
from pywebio.output import *
from pywebio.session import run_async
from pywebio.exceptions import SessionClosedException
from pyngrok import ngrok, conf
import random
import sys
import traceback

# Конфигурация чата
CHAT_HISTORY_FILE = Path("space_chat_history.json")
MAX_MESSAGES_COUNT = 1000
NGROK_AUTH_TOKEN = None  # Замените на ваш токен при необходимости

def setup_ngrok():
    try:
        if NGROK_AUTH_TOKEN:
            conf.get_default().auth_token = NGROK_AUTH_TOKEN
        public_url = ngrok.connect(8080, bind_tls=True)
        print(f"🌌 Публичный URL: {public_url}")
        print(f"📊 Веб-интерфейс ngrok: http://127.0.0.1:4040")
        return str(public_url)
    except Exception as e:
        print(f"⚠️ Ошибка ngrok: {e}", file=sys.stderr)
        return None

def load_chat_history():
    try:
        if CHAT_HISTORY_FILE.exists():
            with open(CHAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️ Ошибка загрузки истории: {e}", file=sys.stderr)
    return {'messages': [], 'users': []}

def save_chat_history(messages, users):
    try:
        with open(CHAT_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'messages': messages,
                'users': list(users)
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Ошибка сохранения истории: {e}", file=sys.stderr)

# Инициализация данных
chat_data = load_chat_history()
chat_msgs = chat_data.get('messages', [])
online_users = set(chat_data.get('users', []))
total_users = len(online_users)

# Система аватаров
AVATAR_TYPES = ['👨‍🚀', '👩‍🚀', '🛸', '👽', '🤖', '🌠', '☄️', '🚀']
AVATAR_COLORS = ['#4FC3F7', '#4DB6AC', '#FF8A65', '#BA68C8', '#9575CD', '#64B5F6', '#7986CB', '#4DD0E1']

def get_user_avatar(nickname):
    random.seed(nickname)
    return random.choice(AVATAR_TYPES), random.choice(AVATAR_COLORS)

def log_activity(sender, action):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] Пользователей онлайн: {len(online_users)} | {sender} {action}")

async def main():
    global chat_msgs, online_users, total_users

    put_html("""
    <style>
        body {
            margin: 0;
            overflow: hidden;
            font-family: 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
            color: white;
        }
    </style>
    """)

    with use_scope('chat-container'):
        put_markdown("""
        ## 🚀 Космический чат HABL
        *Подключено: *`0`* онлайн | Всего: *`0`* пользователей*
        """)
        msg_area = output()
        put_scrollable(msg_area, height=300, keep_bottom=True)

        nickname = None
        while True:
            try:
                with use_scope('input-container', clear=True):
                    nickname = await input_pywebio(
                        "Введите ваш космический ник",
                        required=True,
                        placeholder="Введите ник",
                        validate=lambda n: (
                            "Этот ник уже занят" if n in online_users else
                            "Не более 20 символов" if len(n) > 20 else
                            None
                        )
                    )
                break
            except SessionClosedException:
                return
            except Exception as e:
                print(f"⚠️ Ошибка ввода ника: {e}", file=sys.stderr)
                traceback.print_exc()
                continue

        avatar, color = get_user_avatar(nickname)
        online_users.add(nickname)
        total_users = max(total_users, len(online_users))
        log_activity(nickname, "вошел в чат")

        join_msg = f'`{nickname}` присоединился к чату'
        chat_msgs.append(('system', join_msg, nickname, avatar, color, datetime.now().strftime("%H:%M")))
        msg_area.append(put_markdown(join_msg))
        save_chat_history(chat_msgs, online_users)

        refresh_task = run_async(refresh_messages(nickname, msg_area))

        try:
            while True:
                try:
                    with use_scope('input-container', clear=True):
                        message = await input_pywebio(
                            "",
                            placeholder="Напишите сообщение...", 
                            required=True
                        )
                    if message.strip():
                        msg_time = datetime.now().strftime("%H:%M")
                        chat_msg = f"`{nickname}` ({msg_time}): {message}"
                        chat_msgs.append(('user', chat_msg, nickname, avatar, color, msg_time))
                        msg_area.append(put_markdown(chat_msg))
                        log_activity(nickname, f"написал: {message[:20]}...")
                        save_chat_history(chat_msgs, online_users)
                except SessionClosedException:
                    break
                except Exception as e:
                    print(f"⚠️ Ошибка обработки сообщения: {e}", file=sys.stderr)
                    traceback.print_exc()
                    continue
        finally:
            refresh_task.close()
            online_users.discard(nickname)
            leave_msg = f'`{nickname}` покинул чат'
            chat_msgs.append(('system', leave_msg, nickname, avatar, color, datetime.now().strftime("%H:%M")))
            msg_area.append(put_markdown(leave_msg))
            log_activity(nickname, "вышел из чата")
            save_chat_history(chat_msgs, online_users)
            toast("Вы вышли из чата", duration=3)

async def refresh_messages(nickname, msg_area):
    global chat_msgs
    last_idx = len(chat_msgs)

    while True:
        await asyncio.sleep(0.5)
        try:
            new_messages = chat_msgs[last_idx:]
            if new_messages:
                for msg in new_messages:
                    msg_type, content, sender, avatar, color, time = msg
                    if sender != nickname:
                        if msg_type == 'system':
                            msg_area.append(put_markdown(f"📢 {content}"))
                        else:
                            msg_area.append(put_markdown(content))
                if len(chat_msgs) > MAX_MESSAGES_COUNT:
                    chat_msgs = chat_msgs[-MAX_MESSAGES_COUNT:]
                    save_chat_history(chat_msgs, online_users)
                last_idx = len(chat_msgs)
        except SessionClosedException:
            break
        except Exception as e:
            print(f"⚠️ Ошибка обновления сообщений: {e}", file=sys.stderr)
            traceback.print_exc()
            continue

if __name__ == "__main__":
    try:
        print("🚀 Запуск космического чата HABL")
        print(f"📊 Всего сообщений: {len(chat_msgs)}")
        print(f"👥 Всего пользователей: {total_users}")
        print(f"🌐 Пользователей онлайн: {len(online_users)}")
        
        public_url = setup_ngrok()

        # ⬇️ Вот то, чего не хватало! ⬇️
        # Эта строка создает 'event loop' для pywebio
        asyncio.set_event_loop(asyncio.new_event_loop())

        # Теперь сервер запустится без ошибки
        start_server(
            main,
            port=8080,
            host='127.0.0.1',
            debug=False,
            cdn=False,
            auto_open_webbrowser=False
        )
    except Exception as e:
        print(f"⚠️ Критическая ошибка: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)