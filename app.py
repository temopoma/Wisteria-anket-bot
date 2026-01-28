import os
import sys
import telebot
from telebot import types
from telebot import apihelper
import threading
from threading import Timer
import requests
import gradio as gr
import time
from flask import Flask, request
import logging
from datetime import datetime
# import logging
# import sqlite3

apihelper.CONNECT_TIMEOUT = 40
apihelper.READ_TIMEOUT = 40

# logger = logging.getLogger('TeleBot')
# logger.setLevel(logging.CRITICAL)

bot = telebot.TeleBot(TOKEN)

# === 1. НАСТРОЙКА ЛОГИРОВАНИЯ В ФАЙЛ ===
LOG_FILE = "bot_errors.log"

# Настраиваем логгер, который пишет и в файл, и в консоль
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),  # В файл
        logging.StreamHandler(sys.stdout)                  # В консоль (Railway)
    ]
)
logger = logging.getLogger(__name__)

# === 2. ПРОВЕРКА ТОКЕНА ===
TOKEN = os.environ.get("BOT_TOKEN", "")
if not TOKEN:
    logger.critical("❌ BOT_TOKEN не найден! Добавьте переменную в Railway Variables.")
    sys.exit(1)

logger.info("=" * 50)
logger.info("🚀 WISTERIA ANKET BOT ЗАПУСКАЕТСЯ")
logger.info(f"✅ Токен получен (первые 5 символов): {TOKEN[:5]}...")
logger.info("=" * 50)


def run_bot():
    restart_count = 0
    while restart_count < 20:  # Максимум 20 перезапусков
        try:
            restart_count += 1
            logger.info(f"🔄 Попытка запуска №{restart_count}")
            logger.info("Запускаю bot.polling()...")
            
            # Основной запуск бота
            bot.polling(
                none_stop=True,
                interval=1,
                timeout=30,
                long_polling_timeout=5
            )
            
            # Если polling завершился "нормально" (без исключения) - это странно
            logger.warning("bot.polling() завершился без ошибки. Перезапуск.")
            time.sleep(5)
            
        except Exception as e:
            # Логируем ВСЕ детали ошибки
            logger.critical(f"💥 КРИТИЧЕСКАЯ ОШИБКА В БОТЕ:")
            logger.critical(f"   Тип ошибки: {type(e).__name__}")
            logger.critical(f"   Сообщение: {str(e)}")
            
            # Для частых ошибок добавим traceback в файл
            import traceback
            error_details = traceback.format_exc()
            logger.critical(f"   Traceback:\n{error_details}")
            
            # Ждем перед перезапуском
            wait_time = min(300, restart_count * 10)  # Максимум 5 минут
            logger.info(f"🔄 Перезапуск через {wait_time} секунд...")
            time.sleep(wait_time)


user_data = {} #Временное хранилище данных, сбрасывается после заполнения анкеты
rejection_data = {} #Временное хранилище для отказов

class User:
    def __init__(self, id, username, first_name, user_link = None, character_name = None, fandom = None, photo1 = None, photo2 = None, questionnaire_status = None, reject_text = None):
        self.id = id
        self.username = username
        self.first_name = first_name
        self.user_link = user_link
        self.character_name = character_name
        self.fandom = fandom
        self.photo1 = photo1
        self.photo2 = photo2
        self.questionnaire_status = questionnaire_status
        self.reject_text = reject_text

users = {}

@bot.message_handler(commands=['start'])
def command_start(message):
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)

    users[message.chat.id] = User(message.chat.id, message.from_user.username, message.from_user.first_name)

    if users[message.chat.id].questionnaire_status == 'accepted':
        bot.send_message(message.chat.id, 'Ты уже был принят во флуд. Если это ошибка, обратись к разработчику или владельцам флуда')
    elif users[message.chat.id].questionnaire_status == 'waiting':
        bot.send_message(message.chat.id, 'Твоя анкета уже отправлена, дождись ответа. Если возникают проблемы обратись владельцам флуда')
    elif users[message.chat.id].questionnaire_status == 'banned':
        bot.send_message(message.chat.id, "Ты был забанен во флуде. Обратись к владельцам если это ошибка")
    else:
        if message.from_user.username != None:
            users[message.chat.id].user_link = f"@{users[message.chat.id].username}"
        else:
            users[message.chat.id].user_link = f'<a href="tg://user?id={message.chat.id}">{users[message.chat.id].first_name}</a>'

        print(f'command start from {message.from_user.username}')

        murkup = types.InlineKeyboardMarkup()
        button1 = types.InlineKeyboardButton('Инфо канал', url='https://t.me/WW_flood')
        button2 = types.InlineKeyboardButton('Заполнить анкету', callback_data='start_questionnaire_filling')
        murkup.row(button1, button2)

        bot.send_message(message.chat.id, '''Привет! Чтобы присоединиться к нашему флуду, тебе нужно заполнить короткую анкету. ✨
📍 Перед началом рекомендуем заглянуть в раздел с правилами в инфо канале. Это не строго обязательно для заполнения анкеты, но знание местных правил сделает твое пребывание в группе комфортнее. Помни: незнание правил не освобождает от ответственности в будущем.
Для подачи заявки тебе нужно будет указать:
1: Выбранную роль.
2: Фандом.
3: Прикрепить 2 картинки (арты/референсы персонажа).
Когда будешь готов(а), нажми кнопку ниже! 👇''', reply_markup=murkup)


@bot.callback_query_handler(func=lambda callback: True)
def button_callback(callback):
    print(f'{callback.from_user.username} pressed button {callback.data}')
    
    if callback.data == 'start_questionnaire_filling':
        button_start_questionnaire_filling(callback)
    
    if callback.data == 'submit for review':
        button_submit_for_review(callback)
    
    if 'approve the application' in callback.data:
        id = callback.data[24:]
        button_approve_the_application(id)

    elif 'reject the questionnaire' in callback.data:
        id = callback.data[25:]
        button_reject_the_questionnaire(id)

    if 'do not confirm rejection' in callback.data:
        id = callback.data[25:]
        button_do_not_confirm_rejection(id)

    elif 'confirm rejection' in callback.data:
        id = callback.data[18:]
        button_confirm_rejection(id)
    
    if 'ban user' in callback.data:
        id = callback.data[9:]
        button_ban_user(id)


def button_start_questionnaire_filling(callback):
    # Удаляем все ожидающие шаги для этого пользователя

    if users[callback.message.chat.id].questionnaire_status == 'accepted':
        bot.send_message(callback.message.chat.id, 'Ты уже был принят во флуд. Если это ошибка, обратись к разработчику или владельцам флуда')
    elif users[callback.message.chat.id].questionnaire_status == 'waiting':
        bot.send_message(callback.message.chat.id, 'Твоя анкета уже отправлена, дождись ответа. Если возникают проблемы обратись владельцам флуда')
    elif users[callback.message.chat.id].questionnaire_status == 'banned':
        bot.send_message(callback.message.chat.id, "Ты был забанен во флуде. Обратись к владельцам если это ошибка")
    else:
        bot.clear_step_handler_by_chat_id(chat_id=callback.message.chat.id)
        
        murkup = types.InlineKeyboardMarkup()
        button = types.InlineKeyboardButton('Начать заново', callback_data='start_questionnaire_filling')
        murkup.add(button)

        message = bot.send_message(callback.message.chat.id, 'Отлично! Для начала напиши выбранную роль.', reply_markup=murkup)
        bot.register_next_step_handler(message, register_questionnaire_filling_character_name)

def register_questionnaire_filling_character_name(message):
    users[message.chat.id].character_name = message.text
    print('character name got sucksessfully')

    murkup = types.InlineKeyboardMarkup()
    button = types.InlineKeyboardButton('Начать заново', callback_data='start_questionnaire_filling')
    murkup.add(button)

    message = bot.send_message(message.chat.id, 'Из какого фандома твой персонаж?', reply_markup=murkup)
    bot.register_next_step_handler(message, register_questionnaire_filling_fandom)

def register_questionnaire_filling_fandom(message):
    users[message.chat.id].fandom = message.text
    print('fandom got sucksessfully')
    
    murkup = types.InlineKeyboardMarkup()
    button = types.InlineKeyboardButton('Начать заново', callback_data='start_questionnaire_filling')
    murkup.add(button)

    # Запрашиваем ПЕРВОЕ фото
    msg = bot.send_message(message.chat.id, 'Отправь первое фото персонажа:', reply_markup=murkup)
    bot.register_next_step_handler(msg, process_photo_1)

def process_photo_1(message):
    if not message.photo:
        murkup = types.InlineKeyboardMarkup()
        button = types.InlineKeyboardButton('Начать заново', callback_data='start_questionnaire_filling')
        murkup.add(button)

        msg = bot.reply_to(message, "Это не картинка 👀\n" \
        "Отправь изображение персонажа для анкеты", reply_markup=murkup)
        bot.register_next_step_handler(msg, process_photo_1)
        return

    # Сохраняем первое фото
    file_id = message.photo[-1].file_id
    # save_photo_to_disk(file_id, f"{message.chat.id}_1.jpg")
    users[message.chat.id].photo1 = file_id # Запоминаем ID
    print('first photo got sucksessfully')

    murkup = types.InlineKeyboardMarkup()
    button = types.InlineKeyboardButton('Начать заново', callback_data='start_questionnaire_filling')
    murkup.add(button)
    # Запрашиваем ВТОРОЕ фото
    msg = bot.send_message(message.chat.id, 'Отлично! Теперь отправь второе фото', reply_markup=murkup)
    bot.register_next_step_handler(msg, process_photo_2)

def process_photo_2(message):
    if not message.photo:
        murkup = types.InlineKeyboardMarkup()
        button = types.InlineKeyboardButton('Начать заново', callback_data='start_questionnaire_filling')
        murkup.add(button)

        msg = bot.reply_to(message, "Это не картинка 👀\n" \
        "Отправь второе изображение персонажа для анкеты", reply_markup=murkup)
        bot.register_next_step_handler(msg, process_photo_2)
        return

    # Сохраняем второе фото
    file_id = message.photo[-1].file_id
    # save_photo_to_disk(file_id, f"{message.chat.id}_2.jpg")
    users[message.chat.id].photo2 = file_id
    print('second photo got sucksessfully')

    murkup = types.InlineKeyboardMarkup()
    button1 = types.InlineKeyboardButton('Начать заново', callback_data='start questionnaire filling')
    button2 = types.InlineKeyboardButton('Отправить анкету на рассмотрение', callback_data='submit for review')
    murkup.row(button1, button2)

    media_list_ids = [
        users[message.chat.id].photo1,
        users[message.chat.id].photo2
    ]

    media = []
    for i, file_id in enumerate(media_list_ids):
        # Первому элементу можно добавить подпись
        caption = f"Отлично! Анкета заполнена.\n" \
        f"Роль: {users[message.chat.id].character_name}\n" \
        f"Фандом: {users[message.chat.id].fandom}\n" \
        f'Убедись что всё заполнено верно перед отправкой, иначе вступление может занять больше времени чем планировалось' if i == 0 else None
        
        media.append(types.InputMediaPhoto(file_id, caption=caption))

    bot.send_media_group(message.chat.id, media)
    bot.send_message(message.chat.id, 'Теперь ты можешь отправить свою анкету на рассмотрение, или переделать её если захочешь!', reply_markup=murkup)

# Вспомогательная функция, чтобы не дублировать код загрузки
# def save_photo_to_disk(file_id, filename):
#     file_info = bot.get_file(file_id)
#     downloaded_file = bot.download_file(file_info.file_path)
#     with open(filename, 'wb') as f:
#         f.write(downloaded_file)

def button_submit_for_review(callback):
    if users[callback.message.chat.id].questionnaire_status == 'accepted':
        bot.send_message(callback.message.chat.id, 'Ты уже был принят во флуд. Если это ошибка, обратись к разработчику или владельцам флуда')
    elif users[callback.message.chat.id].questionnaire_status == 'waiting':
        bot.send_message(callback.message.chat.id, 'Твоя анкета уже отправлена, дождись ответа. Если возникают проблемы обратись владельцам флуда')
    elif users[callback.message.chat.id].questionnaire_status == 'banned':
        bot.send_message(callback.message.chat.id, "Ты был забанен во флуде. Обратись к владельцам если это ошибка")
    else:
        media_list_ids = [
                users[callback.message.chat.id].photo1,
                users[callback.message.chat.id].photo2
            ]

        media = []

        for i, file_id in enumerate(media_list_ids):
            caption = None
            if i == 0:
                caption = (
                    "┌── ⋅ ⋅ ── ✦ ── ⋅ ⋅ ──┐\n"
                    "    𝗪𝗶𝘀𝘁𝗲𝗿𝗶𝗮 𝗪𝗵𝗶𝘀𝗽𝗲𝗿\n"
                    "└── ⋅ ⋅ ── ✦ ── ⋅ ⋅ ──┘\n\n"
                    f"【𝐟𝐚𝐧𝐝𝐨𝐦】 {users[callback.message.chat.id].fandom}\n\n"
                    f"【𝐧𝐚𝐦𝐞】  {users[callback.message.chat.id].character_name}\n\n"
                    f"【𝐮𝐬𝐞𝐫】 {users[callback.message.chat.id].user_link}\n\n"
                    "⋅⋅⋅∘┈✩┈∘⋅⋅⋅"
                )
            
            # Добавляем parse_mode='HTML', чтобы ссылка и жирный шрифт работали
            media.append(types.InputMediaPhoto(file_id, caption=caption, parse_mode='HTML'))


        murkup = types.InlineKeyboardMarkup()
        button1 = types.InlineKeyboardButton('Одобрить', callback_data=f'approve the application {callback.message.chat.id}')
        button2 = types.InlineKeyboardButton('Отказать', callback_data=f'reject the questionnaire {callback.message.chat.id}')
        murkup.row(button1, button2)
        button = types.InlineKeyboardButton('Забанить', callback_data=f'ban user {callback.message.chat.id}')
        murkup.add(button)

        bot.send_media_group(-1002785603215, media)
        bot.send_message(-1002785603215,( 
        f'Выберите действие с @{users[callback.message.chat.id].username}'
        ),reply_markup=murkup) if users[callback.message.chat.id].username != None else bot.send_message(-1002785603215,( 
        f'Выберите действие с <a href="tg://user?id={callback.message.chat.id}">{users[callback.message.chat.id].first_name}</a>'
        ),reply_markup=murkup)
        # bot.send_media_group(callback.message.chat.id, media)
        # bot.send_message(callback.message.chat.id,( 
        # f'Выберите действие с пользователем'
        # ),reply_markup=murkup)

        users[callback.message.chat.id].questionnaire_status = 'waiting'

def button_approve_the_application(id):
    users[int(id)].questionnaire_status = 'accepted'
    bot.send_message(-1002785603215, f'{users[int(id)].user_link} был принят во флуд')
    bot.send_message(id, "Тебя приняли во флуд\n" \
    "Можешь заходить\n" \
    "https://t.me/+kKNtpsuIxKFlMTYy")

def button_reject_the_questionnaire(id):
    message = bot.send_message(-1002785603215, 'Напишите причину отказа')
    bot.register_next_step_handler(message, register_questionnaire_reject_reason, id)

def register_questionnaire_reject_reason(message, id):
    murkup = types.InlineKeyboardMarkup()
    button1 = types.InlineKeyboardButton('Подтвердить', callback_data=f'confirm rejection {id}')
    button2 = types.InlineKeyboardButton("Я биполярный", callback_data=f'do not confirm rejection {id}')
    murkup.row(button1, button2)
    
    users[int(id)].reject_text = message.text

    bot.send_message(-1002785603215, f'Отказ {users[int(id)].user_link} по причине: {message.text}', reply_markup=murkup)

def button_confirm_rejection(id):
    murkup = types.InlineKeyboardMarkup()
    button = types.InlineKeyboardButton('Начать заново', callback_data='start_questionnaire_filling')
    murkup.add(button)
    
    bot.send_message(id, (
        f'Твоя анкета была отклонена по причине: {users[int(id)].reject_text}\n'
        f'Ты можешь просто заполнить её заново'
    ), reply_markup=murkup)

def button_do_not_confirm_rejection(id):
    murkup = types.InlineKeyboardMarkup()
    button1 = types.InlineKeyboardButton('Одобрить', callback_data=f'approve the application {id}')
    button2 = types.InlineKeyboardButton('Отказать', callback_data=f'reject the questionnaire {id}')
    murkup.row(button1, button2)

    bot.send_message(-1002785603215,( 
    f'Выберите действие с @{users[int(id)].username}'
    ),reply_markup=murkup) if users[int(id)].username != None else bot.send_message(-1002785603215,( 
    f'Выберите действие с <a href="tg://user?id={id}">{users[id].first_name}</a>'
    ),reply_markup=murkup)

def button_ban_user(id):
    users[int(id)].questionnaire_status == 'banned'
    bot.send_message(id, 'Ты был забанен во флуде. Обратись к администрации за дополнительной информацией или чтобы сообщить об ошибке.')
    bot.send_message(-1002785603215, f'{users[int(id)].user_link} был забанен во флуде')




@bot.message_handler()
def text_handler(message):
    if message.text[4:] == 'echo':
        bot.reply_to(message.chat.id, message.text)
    if message.chat.id == -1002785603215:
        print(f'{message.from_user.username} from owner chat: {message.text}')
    else:
        print(f'{message.from_user.username}: {message.text}')
    if message.from_user.id == None:
        print(message.from_user.id)


if __name__ == "__main__":
    try:
        run_bot()
    except KeyboardInterrupt:
        logger.info("Бот остановлен вручную")
    except Exception as e:
        # Этот блок перехватит ошибки, возникшие ДО запуска polling
        logger.critical(f"💥 ОШИБКА ПРИ ЗАПУСКЕ: {e}")
        import traceback
        logger.critical(traceback.format_exc())
        sys.exit(1)