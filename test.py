import telebot
from telebot import types
from telebot import apihelper
import logging
import sqlite3
import time
from threading import Timer

apihelper.CONNECT_TIMEOUT = 40
apihelper.READ_TIMEOUT = 40

logger = logging.getLogger('TeleBot')
logger.setLevel(logging.CRITICAL)

bot = telebot.TeleBot('6981818278:AAGP2ewCjoQK8UtpAYkruXGzYPvkUH1fIJ0')


user_data = {} #Временное хранилище данных, сбрасывается после заполнения анкеты

@bot.message_handler(commands=['start'])
def command_start(message):
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)

    print(f'command start from {message.from_user.username}')
    if message.from_user.username == None:
        print(message.chat.id)

    murkup = types.InlineKeyboardMarkup()
    button1 = types.InlineKeyboardButton('Инфо канал', url='https://t.me/WW_flood', callback_data='link_flood_info')
    button2 = types.InlineKeyboardButton('Заполнить анкету', callback_data='start_questionnaire_filling')
    murkup.row(button1, button2)

    bot.send_message(message.chat.id, '''[start message text]''', reply_markup=murkup)

@bot.callback_query_handler(func=lambda callback: True)
def filling_out_the_questionnaire(callback):
    print(f'Pressed button {callback.data}')
    
    if callback.data == 'start_questionnaire_filling':
        # ОЧИСТКА: Удаляем все ожидающие шаги для этого пользователя
        bot.clear_step_handler_by_chat_id(chat_id=callback.message.chat.id)
    
        murkup = types.InlineKeyboardMarkup()
        button = types.InlineKeyboardButton('[restart]', callback_data='start_questionnaire_filling')
        murkup.add(button)

        message = bot.send_message(callback.message.chat.id, '[starting questionnaire filling: asking character name]', reply_markup=murkup)
        bot.register_next_step_handler(message, register_questionnaire_filling_character_name)
    
    if callback.data == 'submit for review':
        media_list_ids = [
            user_data[f'{callback.message.chat.id}']['photo1'],
            user_data[f'{callback.message.chat.id}']['photo2']
        ]

        media = []
        for i, file_id in enumerate(media_list_ids):
            # Первому элементу можно добавить подпись
            caption = f"""Пользователь с id tg://user?id={callback.message.chat.id} отправил анкету:
Юзер: @{callback.from_user.username}
Роль: {user_data[f'{callback.message.chat.id}']['character_name']}
Фандом: {user_data[f'{callback.message.chat.id}']['fandom']}""" if i == 0 else None
            
            media.append(types.InputMediaPhoto(file_id, caption=caption))

        bot.send_media_group(-1002785603215, media)
        print('sebmited for review')
    

def register_questionnaire_filling_character_name(message):
    user_data[f'{message.chat.id}'] = {'character_name': message.text}
    print('character name got sucksessfully')

    murkup = types.InlineKeyboardMarkup()
    button = types.InlineKeyboardButton('[restart]', callback_data='start_questionnaire_filling')
    murkup.add(button)

    message = bot.send_message(message.chat.id, '[asking fandom]', reply_markup=murkup)
    bot.register_next_step_handler(message, register_questionnaire_filling_fandom)

def register_questionnaire_filling_fandom(message):
    user_data[f'{message.chat.id}']['fandom'] = message.text
    print('fandom got sucksessfully')
    
    murkup = types.InlineKeyboardMarkup()
    button = types.InlineKeyboardButton('[restart]', callback_data='start_questionnaire_filling')
    murkup.add(button)

    # Запрашиваем ПЕРВОЕ фото
    msg = bot.send_message(message.chat.id, 'Отправьте ПЕРВОЕ фото персонажа:', reply_markup=murkup)
    bot.register_next_step_handler(msg, process_photo_1)

def process_photo_1(message):
    murkup = types.InlineKeyboardMarkup()
    button = types.InlineKeyboardButton('[restart]', callback_data='start_questionnaire_filling')
    murkup.add(button)

    if not message.photo:
        msg = bot.reply_to(message, "Это не фото. Пожалуйста, отправьте первую картинку:", reply_markup=murkup)
        bot.register_next_step_handler(msg, process_photo_1)
        return

    # Сохраняем первое фото
    file_id = message.photo[-1].file_id
    save_photo_to_disk(file_id, f"{message.chat.id}_1.jpg")
    user_data[f'{message.chat.id}']['photo1'] = file_id # Запоминаем ID
    print('first photo got sucksessfully')    

    # Запрашиваем ВТОРОЕ фото
    msg = bot.send_message(message.chat.id, 'Отлично! Теперь отправьте ВТОРОЕ фото:', reply_markup=murkup)
    bot.register_next_step_handler(msg, process_photo_2)

def process_photo_2(message):
    if not message.photo:
        murkup = types.InlineKeyboardMarkup()
        button = types.InlineKeyboardButton('[restart]', callback_data='start_questionnaire_filling')
        murkup.add(button)

        msg = bot.reply_to(message, "Это не фото. Пожалуйста, отправьте вторую картинку:", reply_markup=murkup)
        bot.register_next_step_handler(msg, process_photo_2)
        return

    # Сохраняем второе фото
    file_id = message.photo[-1].file_id
    save_photo_to_disk(file_id, f"{message.chat.id}_2.jpg")
    user_data[f'{message.chat.id}']['photo2'] = file_id
    print('second photo got sucksessfully')

    murkup = types.InlineKeyboardMarkup()
    button1 = types.InlineKeyboardButton('[restart]', callback_data='start questionnaire filling')
    button2 = types.InlineKeyboardButton('Отправить анкету на рассмотрение', callback_data='submit for review')
    murkup.row(button1, button2)

    media_list_ids = [
        user_data[f'{message.chat.id}']['photo1'],
        user_data[f'{message.chat.id}']['photo2']
    ]

    media = []
    for i, file_id in enumerate(media_list_ids):
        # Первому элементу можно добавить подпись
        caption = f"""Отлично! Анкета заполнена.
Роль: {user_data[f'{message.chat.id}']['character_name']}
Фандом: {user_data[f'{message.chat.id}']['fandom']}""" if i == 0 else None
        
        media.append(types.InputMediaPhoto(file_id, caption=caption))

    bot.send_media_group(message.chat.id, media)
    bot.send_message(message.chat.id, 'Теперь вы можете отправить свою анкету на рассмотрение, или переделать её!', reply_markup=murkup)

# Вспомогательная функция, чтобы не дублировать код загрузки
def save_photo_to_disk(file_id, filename):
    file_info = bot.get_file(file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    with open(filename, 'wb') as f:
        f.write(downloaded_file)




# @bot.message_handler()
# def text(message):
#     if message.chat.id == -1002785603215:
#         print(f'{message.from_user.username} from owner chat: {message.text}')
#     else:
#         print(f'{message.from_user.username}: {message.text}')
#     if message.from_user.id == None:
#         print(message.from_user.id)


bot.infinity_polling(timeout=90, long_polling_timeout=5)