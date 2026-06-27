#!/usr/bin/env python3
import logging
import re
import os
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes
import psycopg2
from psycopg2 import Error

TOKEN = "8956990632:AAG111n07toG5AyzxyDNIdAWIEAuaB4XEcs"

DB_CONFIG = {
    'host': '192.168.213.100',
    'port': '5432',
    'database': 'practice5',
    'user': 'postgres',
    'password': 'postgres'
}

TEXT_INPUT = 1

EMAIL_REGEX = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
PHONE_REGEX = r'\+?\d[\d\s\-\(\)]{8,}\d'

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def get_db_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Error as e:
        logger.error(f"Ошибка подключения к БД: {e}")
        return None

def get_emails_from_db():
    conn = get_db_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, email FROM emails ORDER BY id;")
        rows = cur.fetchall()
        return rows
    except Error as e:
        logger.error(f"Ошибка SELECT emails: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def get_phones_from_db():
    conn = get_db_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, phone FROM phones ORDER BY id;")
        rows = cur.fetchall()
        return rows
    except Error as e:
        logger.error(f"Ошибка SELECT phones: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def save_emails_to_db(emails):
    conn = get_db_connection()
    if not conn:
        return False, "Нет подключения к БД"
    try:
        cur = conn.cursor()
        inserted = 0
        for email in emails:
            try:
                cur.execute("INSERT INTO emails (email) VALUES (%s) ON CONFLICT (email) DO NOTHING;", (email,))
                if cur.rowcount > 0:
                    inserted += 1
            except Error as e:
                logger.error(f"Ошибка вставки {email}: {e}")
        conn.commit()
        return True, f"Добавлено {inserted} новых email (дубликаты пропущены)"
    except Error as e:
        logger.error(f"Ошибка при вставке: {e}")
        return False, f"Ошибка БД: {e}"
    finally:
        cur.close()
        conn.close()

def save_phones_to_db(phones):
    conn = get_db_connection()
    if not conn:
        return False, "Нет подключения к БД"
    try:
        cur = conn.cursor()
        inserted = 0
        for phone in phones:
            try:
                cur.execute("INSERT INTO phones (phone) VALUES (%s) ON CONFLICT (phone) DO NOTHING;", (phone,))
                if cur.rowcount > 0:
                    inserted += 1
            except Error as e:
                logger.error(f"Ошибка вставки {phone}: {e}")
        conn.commit()
        return True, f"Добавлено {inserted} новых номеров (дубликаты пропущены)"
    except Error as e:
        logger.error(f"Ошибка при вставке: {e}")
        return False, f"Ошибка БД: {e}"
    finally:
        cur.close()
        conn.close()

def get_replication_logs():
    log_file = "/var/log/postgresql/postgresql-18-main.log"
    if not os.path.exists(log_file):
        return "Файл логов не найден"
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
        repl_lines = []
        for line in lines:
            if 'replication' in line.lower() or 'walsender' in line.lower() or 'standby' in line.lower():
                repl_lines.append(line.strip())
        if not repl_lines:
            return "Строки о репликации не найдены"
        return '\n'.join(repl_lines[-20:])
    except Exception as e:
        return f"Ошибка чтения логов: {e}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        " Привет! Я бот для работы с БД PostgreSQL\n\n"
        "Доступные команды:\n"
        "/get_emails - показать все email из БД\n"
        "/get_phone_numbers - показать все телефоны из БД\n"
        "/get_repl_logs - показать логи репликации\n"
        "/add_emails - найти email в тексте и добавить в БД\n"
        "/add_phones - найти телефоны в тексте и добавить в БД"
    )

async def get_emails(update: Update, context: ContextTypes.DEFAULT_TYPE):
    emails = get_emails_from_db()
    if not emails:
        await update.message.reply_text(" В таблице emails нет данных")
        return
    result = " Список email:\n\n"
    for id_, email in emails:
        result += f"{id_}. {email}\n"
    await update.message.reply_text(result)

async def get_phones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phones = get_phones_from_db()
    if not phones:
        await update.message.reply_text(" В таблице phones нет данных")
        return
    result = " Список телефонов:\n\n"
    for id_, phone in phones:
        result += f"{id_}. {phone}\n"
    await update.message.reply_text(result)

async def get_repl_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(" Загружаю логи репликации...")
    logs = get_replication_logs()
    if len(logs) > 4000:
        logs = logs[-4000:] + "\n\n... (обрезано)"
    await update.message.reply_text(f"```\n{logs}\n```", parse_mode='Markdown')

async def add_emails_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        " Отправьте текст, из которого нужно извлечь email-адреса.\n\nДля отмены отправьте /cancel"
    )
    return TEXT_INPUT

async def add_phones_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        " Отправьте текст, из которого нужно извлечь номера телефонов.\n\nДля отмены отправьте /cancel"
    )
    return TEXT_INPUT

async def process_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if 'add_emails' in str(context.user_data.get('action', '')):
        items = re.findall(EMAIL_REGEX, text, re.IGNORECASE)
        item_type = 'email'
    else:
        items = re.findall(PHONE_REGEX, text)
        item_type = 'phone'
    
    if not items:
        await update.message.reply_text(" Ничего не найдено. Попробуйте другой текст.")
        return ConversationHandler.END
    
    unique_items = list(set(items))
    result = f" Найдено {len(unique_items)} уникальных {('email' if item_type == 'email' else 'номеров')}:\n\n"
    for item in unique_items:
        result += f"• {item}\n"
    
    context.user_data['found_items'] = unique_items
    context.user_data['item_type'] = item_type
    
    reply_keyboard = [[' Да, записать', ' Нет, отменить']]
    await update.message.reply_text(
        result + "\nЗаписать найденные данные в базу данных?",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return ConversationHandler.END

async def handle_save_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.message.text
    found_items = context.user_data.get('found_items', [])
    item_type = context.user_data.get('item_type', 'email')
    
    if answer == ' Да, записать':
        if item_type == 'email':
            success, message = save_emails_to_db(found_items)
        else:
            success, message = save_phones_to_db(found_items)
        
        if success:
            await update.message.reply_text(f" {message}", reply_markup=ReplyKeyboardRemove())
        else:
            await update.message.reply_text(f" {message}", reply_markup=ReplyKeyboardRemove())
    else:
        await update.message.reply_text(" Запись отменена", reply_markup=ReplyKeyboardRemove())
    
    context.user_data.pop('found_items', None)
    context.user_data.pop('item_type', None)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(" Операция отменена", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def main():
    print("DEBUG: Начало запуска бота")
    print(f"DEBUG: Токен установлен: {TOKEN[:20]}...")
    
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("get_emails", get_emails))
    application.add_handler(CommandHandler("get_phone_numbers", get_phones))
    application.add_handler(CommandHandler("get_repl_logs", get_repl_logs))
    
    add_email_conv = ConversationHandler(
        entry_points=[CommandHandler("add_emails", add_emails_start)],
        states={TEXT_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_text)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    application.add_handler(add_email_conv)
    
    add_phone_conv = ConversationHandler(
        entry_points=[CommandHandler("add_phones", add_phones_start)],
        states={TEXT_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_text)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    application.add_handler(add_phone_conv)
    
    application.add_handler(MessageHandler(filters.Regex('^( Да, записать| Нет, отменить)$'), handle_save_decision))
    
    print(" Бот запущен и готов к работе!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
