# -*- coding: utf-8 -*-
"""
====================================================================
🎬 VIP KINO BOT (To'liq Himoyalangan, Majburiy Obunali va Admin Panelli)
====================================================================
"""

import os
import sys
import time
import telebot

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from telebot.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
)

from database import (
    init_db,
    register_user,
    set_admin,
    is_user_admin,
    set_sub_verified,
    is_sub_verified,
    get_all_users,
    get_movie_by_code,
    increment_movie_views,
    search_movies_by_title,
    get_all_movies,
    get_top_movies,
    add_or_update_movie,
    update_movie_file_id,
    delete_movie,
    get_next_available_code,
    get_channels,
    add_channel,
    remove_channel,
    get_setting,
    set_setting,
    get_stats,
)
from video_helper import ensure_demo_video

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(BASE_DIR, ".env")


def load_or_ask_token() -> str:
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token and os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("BOT_TOKEN=") and not line.startswith("#"):
                    token = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break

    if not token or token == "PASTE_YOUR_TOKEN_HERE":
        try:
            token = input("👉 BOT TOKENNI KIRITING: ").strip()
        except EOFError:
            sys.exit(1)
        if token:
            with open(ENV_FILE, "w", encoding="utf-8") as f:
                f.write(f"BOT_TOKEN={token}\n")
    return token


init_db()
ensure_demo_video()

BOT_TOKEN = load_or_ask_token()
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

USER_STATES = {}


def set_state(user_id: int, state: str, data: dict = None):
    USER_STATES[user_id] = {"state": state, "data": data or {}}


def get_state(user_id: int) -> dict:
    return USER_STATES.get(user_id, {"state": None, "data": {}})


def clear_state(user_id: int):
    USER_STATES.pop(user_id, None)


# ================= KLAVIATURALAR =================

def user_default_keyboard(user_id: int):
    """
    Oddiy foydalanuvchiga hech qanday 'Forsaj' yoki ortiqcha tugmalar chiqmaydi!
    Faqat kino kodini kiritadi.
    """
    return ReplyKeyboardRemove()


def admin_menu_keyboard() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        KeyboardButton("➕ Yangi kino qo'shish"),
        KeyboardButton("🎬 Kodga video biriktirish"),
        KeyboardButton("📢 Kanalga kodni tashlash"),
        KeyboardButton("🚀 Forsaj 1-10 ni kanalga tashlash"),
        KeyboardButton("📡 Majburiy obuna kanallari"),
        KeyboardButton("📋 Kodlar ro'yxati (Admin)"),
        KeyboardButton("🗑 Kino o'chirish"),
        KeyboardButton("📊 Statistika"),
        KeyboardButton("📨 Xabar yuborish (Rassilka)"),
        KeyboardButton("🚪 Admin paneldan chiqish"),
    )
    return kb


def cancel_keyboard() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("❌ Bekor qilish"))
    return kb


# ================= MAJBURIY OBUNANI TEKSHIRISH =================

def get_unsubscribed_channels(user_id: int, from_callback: bool = False) -> list:
    """
    Foydalanuvchi https://t.me/kinolar_botttt (va boshqa ulangan kanallar)ga
    obuna bo'lganini tekshiradi.
    """
    channels = get_channels()
    if not channels:
        return []

    unsubscribed = []
    for ch in channels:
        ch_id = ch["channel_id"]
        try:
            member = bot.get_chat_member(ch_id, user_id)
            if member.status in ("left", "kicked"):
                unsubscribed.append(ch)
            else:
                set_sub_verified(user_id, True)
        except Exception:
            # Agar bot kanalda hali Admin qilinmagan bo'lsa ("member list is inaccessible"):
            # Foydalanuvchi "✅ Obuna bo'ldim" tugmasini bosganida tasdiqlab o'tkazib yuboradi
            if from_callback:
                set_sub_verified(user_id, True)
            elif not is_sub_verified(user_id):
                unsubscribed.append(ch)
    return unsubscribed


def send_subscription_prompt(chat_id: int, unsubscribed: list, pending_code: str = ""):
    """
    Obuna bo'lmagan foydalanuvchiga kanal linki va '✅ Obuna bo'ldim' tugmasini chiqaradi.
    """
    kb = InlineKeyboardMarkup(row_width=1)
    for ch in unsubscribed:
        kb.add(
            InlineKeyboardButton(
                text=f"📢 Kanalga obuna bo'lish",
                url=ch["invite_link"]
            )
        )
    cb_data = f"check_sub:{pending_code}" if pending_code else "check_sub:"
    kb.add(InlineKeyboardButton(text="✅ Obuna bo'ldim", callback_data=cb_data))

    text = (
        "⚠️ <b>Botdan foydalanish va kinolarni tomosha qilish uchun "
        "avval kanalimizga obuna bo'ling!</b>\n\n"
        "👇 Kanalga obuna bo'lgach, <b>«✅ Obuna bo'ldim»</b> tugmasini bosing:"
    )
    bot.send_message(chat_id, text, reply_markup=kb)


# ================= KINONI HIMOYALANGAN HOLDA JO'NATISH =================

def send_protected_movie(chat_id: int, movie: dict):
    """
    Kinoni foydalanuvchiga FAQAT BOT ICHIDA KO'RADIGAN QILIB (protect_content=True) yuboradi.
    Hech kimga uzatib (forward) bo'lmaydi va saqlab (save) bo'lmaydi!
    """
    code = str(movie["code"]).strip()
    views = increment_movie_views(code)
    bot_info = bot.get_me()

    caption = (
        f"🎬 <b>{movie['title']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔢 <b>Kino kodi:</b> <code>{code}</code>\n"
        f"📅 <b>Yili:</b> {movie['year']}\n"
        f"🎭 <b>Janr:</b> {movie['genre']}\n"
        f"🌍 <b>Davlati:</b> {movie['country']}\n"
        f"🔊 <b>Tili:</b> {movie['language']}\n"
        f"⭐️ <b>Reyting:</b> {movie['rating']} | 👁 <b>Ko'rildi:</b> {views}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📝 <i>{movie['description']}</i>\n\n"
        f"🔒 <b>Faqat bot ichida tomosha qilish mumkin!</b>\n"
        f"🤖 @{bot_info.username}"
    )

    file_id = (movie.get("file_id") or "").strip()

    # 1-holat: Bazada Telegram file_id mavjud bo'lsa
    if file_id and not os.path.exists(file_id):
        try:
            bot.send_video(
                chat_id=chat_id,
                video=file_id,
                caption=caption,
                protect_content=True,
                supports_streaming=True,
            )
            return
        except Exception:
            try:
                bot.send_document(
                    chat_id=chat_id,
                    document=file_id,
                    caption=caption,
                    protect_content=True,
                )
                return
            except Exception:
                pass

    # 2-holat: Desktop\farsaj1 (yoki forsaj_{code}.mp4) papkasida video fayl bor bo'lsa
    desktop_folder = os.path.join(r"C:\Users\Abdukamol\OneDrive\Desktop", f"farsaj{code}")
    local_movie_path = ""
    if os.path.isdir(desktop_folder):
        for fname in os.listdir(desktop_folder):
            if fname.lower().endswith((".mp4", ".mkv", ".mov", ".avi")):
                cand = os.path.join(desktop_folder, fname)
                if os.path.getsize(cand) > 10000:
                    local_movie_path = cand
                    break
    if not local_movie_path:
        local_movie_path = os.path.join(BASE_DIR, f"forsaj_{code}.mp4")

    if os.path.exists(local_movie_path) and os.path.getsize(local_movie_path) > 10000:
        wait_msg = bot.send_message(chat_id, f"⏳ <b>{movie['title']}</b> yuklanmoqda, iltimos kuting...")
        try:
            with open(local_movie_path, "rb") as vf:
                sent = bot.send_video(
                    chat_id=chat_id,
                    video=vf,
                    caption=caption,
                    protect_content=True,
                    supports_streaming=True,
                    timeout=180,
                )
                if sent and sent.video:
                    update_movie_file_id(code, sent.video.file_id)
            try:
                bot.delete_message(chat_id, wait_msg.message_id)
            except Exception:
                pass
            return
        except Exception:
            try:
                bot.delete_message(chat_id, wait_msg.message_id)
            except Exception:
                pass

    # 3-holat: Boshqa kodlar uchun demo video
    demo_file_id = get_setting("demo_file_id", "").strip()
    if demo_file_id:
        try:
            bot.send_video(
                chat_id=chat_id,
                video=demo_file_id,
                caption=caption,
                protect_content=True,
                supports_streaming=True,
            )
            return
        except Exception:
            pass

    demo_path = ensure_demo_video()
    if os.path.exists(demo_path):
        try:
            with open(demo_path, "rb") as vf:
                sent = bot.send_video(
                    chat_id=chat_id,
                    video=vf,
                    caption=caption,
                    protect_content=True,
                    supports_streaming=True,
                )
                if sent and sent.video:
                    set_setting("demo_file_id", sent.video.file_id)
        except Exception:
            bot.send_message(chat_id, caption)
    else:
        bot.send_message(chat_id, caption)


# ================= KANALGA KINO KODINI CHIQARISH (POST QILISH) =================

def post_movie_to_channels(movie: dict) -> int:
    channels = get_channels()
    if not channels:
        return 0

    bot_info = bot.get_me()
    deep_link = f"https://t.me/{bot_info.username}?start={movie['code']}"

    post_text = (
        f"🎬 <b>Kino nomi:</b> {movie['title']}\n"
        f"📅 <b>Yili:</b> {movie['year']}\n"
        f"🎭 <b>Janr:</b> {movie['genre']}\n"
        f"🔊 <b>Tili:</b> {movie['language']}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔢 <b>KINO KODI:</b> <code>{movie['code']}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 <b>Bot manzili:</b> @{bot_info.username}"
    )

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton(
            text=f"▶️ Kinoni botda ko'rish (Kod: {movie['code']})",
            url=deep_link
        )
    )

    success_count = 0
    for ch in channels:
        try:
            bot.send_message(
                chat_id=ch["channel_id"],
                text=post_text,
                reply_markup=kb
            )
            success_count += 1
        except Exception:
            pass
    return success_count


# ================= /START VA ADMIN BUYRUQLARI =================

@bot.message_handler(commands=["start"])
def handle_start(message):
    user = message.from_user
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    register_user(user.id, full_name, user.username or "")
    clear_state(user.id)

    parts = (message.text or "").split(maxsplit=1)
    pending_code = parts[1].strip() if len(parts) > 1 else ""

    # Avval eski tugmalarni tozalab tashlaymiz (Forsaj degan tugmalar ko'rinmasligi uchun)
    unsubscribed = get_unsubscribed_channels(user.id, from_callback=False)
    if unsubscribed:
        send_subscription_prompt(message.chat.id, unsubscribed, pending_code=pending_code)
        return

    if pending_code:
        movie = get_movie_by_code(pending_code)
        if movie:
            send_protected_movie(message.chat.id, movie)
            return

    bot.send_message(
        message.chat.id,
        f"👋 Assalomu alaykum, <b>{full_name}</b>!\n\n"
        f"🎬 <b>Marhamat, kino kodini kiriting:</b>",
        reply_markup=user_default_keyboard(user.id)
    )


@bot.message_handler(commands=["admin"])
def handle_admin_cmd(message):
    prompt_admin_login(message)


def prompt_admin_login(message):
    user_id = message.from_user.id
    if is_user_admin(user_id):
        clear_state(user_id)
        bot.send_message(
            message.chat.id,
            "👑 <b>Admin panelga xush kelibsiz!</b>\nKerakli bo'limni tanlang:",
            reply_markup=admin_menu_keyboard()
        )
        return

    set_state(user_id, "WAIT_ADMIN_PASSWORD")
    bot.send_message(
        message.chat.id,
        "🔐 <b>Admin panelga kirish uchun maxfiy parolni kiriting:</b>",
        reply_markup=cancel_keyboard()
    )


# ================= CALLBACK TUGMALAR ("✅ OBUNA BO'LDIM" VA BOSHQA) =================

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    data = call.data or ""

    # 1. Majburiy obunani tekshirish ("✅ Obuna bo'ldim")
    if data.startswith("check_sub:"):
        pending_code = data.split(":", 1)[1].strip()
        unsubscribed = get_unsubscribed_channels(user_id, from_callback=True)

        if unsubscribed:
            bot.answer_callback_query(
                call.id,
                "❌ Siz hali kanalga obuna bo'lmadingiz! Avval obuna bo'lib, so'ng qayta bosing.",
                show_alert=True
            )
            return

        bot.answer_callback_query(call.id, "✅ Obunangiz tasdiqlandi!")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass

        bot.send_message(
            call.message.chat.id,
            "✅ <b>Obunangiz tasdiqlandi!</b>\n\n"
            "🎬 <b>Marhamat, kino kodini kiriting:</b>",
            reply_markup=user_default_keyboard(user_id)
        )

        if pending_code:
            movie = get_movie_by_code(pending_code)
            if movie:
                send_protected_movie(call.message.chat.id, movie)
        return

    # 2. Qidiruv natijasidan kinoni tanlash
    if data.startswith("watch_code:"):
        code = data.split(":", 1)[1].strip()
        unsubscribed = get_unsubscribed_channels(user_id, from_callback=False)
        if unsubscribed:
            bot.answer_callback_query(call.id, "⚠️ Avval kanalga obuna bo'ling!", show_alert=True)
            send_subscription_prompt(call.message.chat.id, unsubscribed, pending_code=code)
            return

        movie = get_movie_by_code(code)
        if movie:
            bot.answer_callback_query(call.id, "🎬 Yuklanmoqda...")
            send_protected_movie(call.message.chat.id, movie)
        else:
            bot.answer_callback_query(call.id, "❌ Kino topilmadi!", show_alert=True)
        return

    # 3. Admin: Kinolar ro'yxatini sahifalash
    if data.startswith("movies_page:"):
        page = int(data.split(":", 1)[1])
        send_movies_catalog_page(call.message.chat.id, page, edit_message_id=call.message.message_id)
        bot.answer_callback_query(call.id)
        return

    # 4. Admin: Kanalni o'chirish
    if data.startswith("del_ch:"):
        if not is_user_admin(user_id):
            bot.answer_callback_query(call.id, "⛔️ Ruxsat yo'q!", show_alert=True)
            return
        ch_db_id = int(data.split(":", 1)[1])
        remove_channel(ch_db_id)
        bot.answer_callback_query(call.id, "🗑 Kanal o'chirildi!")
        show_channels_admin(call.message.chat.id, edit_message_id=call.message.message_id)
        return

    # 5. Admin: Kanal qo'shish tugmasi
    if data == "admin_add_channel":
        if not is_user_admin(user_id):
            return
        bot.answer_callback_query(call.id)
        set_state(user_id, "ADMIN_ADD_CHANNEL_ID")
        bot.send_message(
            call.message.chat.id,
            "📢 <b>Yangi majburiy obuna va kodlar kanalini qo'shish:</b>\n\n"
            "1️⃣ Avval ushbu botni kanalingizga <b>Admin</b> qiling.\n"
            "2️⃣ So'ngra kanalning <b>@username</b> manzilini yuboring (masalan: <code>@kinolar_botttt</code>):",
            reply_markup=cancel_keyboard()
        )
        return


def send_movies_catalog_page(chat_id: int, page: int = 1, edit_message_id: int = None):
    movies = get_all_movies()
    per_page = 20
    total_pages = max(1, (len(movies) + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    slice_movies = movies[start_idx:end_idx]

    lines = [f"📋 <b>BAZADAGI KINOLAR VA KODLAR (Sahifa {page}/{total_pages}):</b>\n"]
    for m in slice_movies:
        has_vid = "✅" if (m.get("file_id") or os.path.exists(os.path.join(BASE_DIR, f"forsaj_{m['code']}.mp4"))) else "🎬"
        lines.append(f"{has_vid} Kod: <code>{m['code']}</code> — <b>{m['title']}</b> ({m['year']})")

    text = "\n".join(lines)

    kb = InlineKeyboardMarkup(row_width=2)
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"movies_page:{page - 1}"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"movies_page:{page + 1}"))
    if nav_buttons:
        kb.row(*nav_buttons)

    if edit_message_id:
        try:
            bot.edit_message_text(text, chat_id, edit_message_id, reply_markup=kb)
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=kb)


def show_channels_admin(chat_id: int, edit_message_id: int = None):
    channels = get_channels()
    kb = InlineKeyboardMarkup(row_width=1)

    if not channels:
        text = "📡 <b>Majburiy obuna kanallari:</b>\n\n⚠️ Hozircha kanal ulanmagan."
    else:
        lines = ["📡 <b>Majburiy obuna kanallari ro'yxati:</b>\n"]
        for idx, ch in enumerate(channels, start=1):
            lines.append(f"{idx}. <b>{ch['title']}</b> (<code>{ch['channel_id']}</code>)\n🔗 {ch['invite_link']}")
            kb.add(
                InlineKeyboardButton(
                    text=f"🗑 O'chirish: {ch['title']}",
                    callback_data=f"del_ch:{ch['id']}"
                )
            )
        text = "\n\n".join(lines)

    kb.add(InlineKeyboardButton("➕ Yangi kanal qo'shish", callback_data="admin_add_channel"))

    if edit_message_id:
        try:
            bot.edit_message_text(text, chat_id, edit_message_id, reply_markup=kb)
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=kb)


# ================= ADMIN VIDEO YUKLAGANDA TEZKOR QABUL QILISH =================

@bot.message_handler(content_types=["video", "document"])
def handle_media_upload(message):
    user_id = message.from_user.id
    if user_id == 1692978831:
        set_admin(user_id, True)

    state_info = get_state(user_id)
    state = state_info["state"]
    data = state_info["data"]

    file_id = ""
    if message.video:
        file_id = message.video.file_id
    elif message.document:
        file_id = message.document.file_id

    if not file_id:
        return

    if is_user_admin(user_id) and state == "ADMIN_ATTACH_VIDEO_FILE":
        code = data.get("code")
        update_movie_file_id(code, file_id)
        movie = get_movie_by_code(code)
        clear_state(user_id)
        bot.send_message(
            message.chat.id,
            f"✅ <b>Muvaffaqiyatli saqlandi!</b>\n\n"
            f"🔢 Kod: <code>{code}</code>\n"
            f"🎬 Kino: <b>{movie['title']}</b>\n"
            f"⚡️ Endi <code>{code}</code> yozilganda ushbu to'liq kino 1 soniyada chiqadi!",
            reply_markup=admin_menu_keyboard()
        )
        return

    if is_user_admin(user_id) and state == "ADMIN_NEW_MOVIE_VIDEO":
        data["file_id"] = file_id
        next_code = get_next_available_code()
        set_state(user_id, "ADMIN_NEW_MOVIE_CODE", data)
        bot.send_message(
            message.chat.id,
            f"📹 <b>Video qabul qilindi!</b>\n\n"
            f"🔢 Endi ushbu kino uchun <b>KOD</b> kiriting (masalan: <code>{next_code}</code>):",
            reply_markup=cancel_keyboard()
        )
        return

    if is_user_admin(user_id) and state == "ADMIN_BROADCAST":
        execute_broadcast(message)
        return

    if is_user_admin(user_id):
        set_state(user_id, "ADMIN_QUICK_VIDEO_CODE", {"file_id": file_id})
        bot.send_message(
            message.chat.id,
            "🎬 <b>To'liq kino qabul qilindi!</b>\n\n"
            "🔢 Ushbu kinoni qaysi <b>KOD</b>ga biriktiramiz? (Masalan, Forsaj 1 bo'lsa <code>1</code> deb yozing):",
            reply_markup=cancel_keyboard()
        )
        return


# ================= BARCHA MATNLI XABARLAR VA KOD QIDIRUV =================

@bot.message_handler(content_types=["text", "photo"])
def handle_text_messages(message):
    user = message.from_user
    user_id = user.id
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    register_user(user_id, full_name, user.username or "")

    text = (message.text or "").strip()
    state_info = get_state(user_id)
    state = state_info["state"]
    data = state_info["data"]

    if text == "❌ Bekor qilish":
        clear_state(user_id)
        if is_user_admin(user_id):
            bot.send_message(message.chat.id, "🔄 Amal bekor qilindi.", reply_markup=admin_menu_keyboard())
        else:
            bot.send_message(message.chat.id, "🎬 Marhamat, kino kodini kiriting:", reply_markup=user_default_keyboard(user_id))
        return

    # ----------------- ADMIN LOGIN ("admin/" yoki "/admin") -----------------
    if text.lower() in ("admin/", "/admin", "admin", "👑 admin panel"):
        prompt_admin_login(message)
        return

    # ----------------- PAROLNI TEKSHIRISH (abdu8811) -----------------
    if state == "WAIT_ADMIN_PASSWORD":
        admin_pass = get_setting("admin_password", "abdu8811")
        if text == admin_pass:
            try:
                bot.delete_message(message.chat.id, message.message_id)
            except Exception:
                pass
            set_admin(user_id, True)
            clear_state(user_id)
            bot.send_message(
                message.chat.id,
                "✅ <b>Parol to'g'ri! Siz Admin panelga kirdingiz.</b>",
                reply_markup=admin_menu_keyboard()
            )
        else:
            bot.send_message(
                message.chat.id,
                "❌ <b>Parol noto'g'ri!</b> Qaytadan kiriting:",
                reply_markup=cancel_keyboard()
            )
        return

    # ================= ADMIN PANEL AMALLARI =================
    if is_user_admin(user_id):
        if text == "🚪 Admin paneldan chiqish":
            clear_state(user_id)
            set_admin(user_id, False)
            bot.send_message(
                message.chat.id,
                "🎬 <b>Marhamat, kino kodini kiriting:</b>",
                reply_markup=ReplyKeyboardRemove()
            )
            return

        if text == "📊 Statistika":
            st = get_stats()
            top_list = get_top_movies(5)
            top_txt = "\n".join(
                [f"   • Kod <code>{m['code']}</code> — {m['title']} ({m['views']} marta)" for m in top_list]
            )
            bot.send_message(
                message.chat.id,
                f"📊 <b>BOT STATISTIKASI:</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👥 <b>Foydalanuvchilar:</b> {st['total_users']} ta\n"
                f"🎬 <b>Bazadagi kinolar:</b> {st['total_movies']} ta\n"
                f"👁 <b>Jami ko'rilishlar:</b> {st['total_views']} marta\n"
                f"📡 <b>Ulangan kanallar:</b> {st['total_channels']} ta\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🔥 <b>Top kinolar:</b>\n{top_txt}"
            )
            return

        if text == "📡 Majburiy obuna kanallari":
            show_channels_admin(message.chat.id)
            return

        if text == "📋 Kodlar ro'yxati (Admin)":
            send_movies_catalog_page(message.chat.id, page=1)
            return

        if text == "➕ Yangi kino qo'shish":
            set_state(user_id, "ADMIN_NEW_MOVIE_VIDEO", {})
            bot.send_message(
                message.chat.id,
                "🎬 <b>Yangi kino qo'shish:</b>\n\n"
                "Kino <b>video faylini</b> shu yerga yuboring (yoki faqat kod/nom qo'shish uchun <code>skip</code> deb yozing):",
                reply_markup=cancel_keyboard()
            )
            return

        if text == "🎬 Kodga video biriktirish":
            set_state(user_id, "ADMIN_ATTACH_VIDEO_CODE", {})
            bot.send_message(
                message.chat.id,
                "🔢 <b>Qaysi koddagi kinoga video biriktirmoqchisiz?</b> (Kod raqamini yozing):",
                reply_markup=cancel_keyboard()
            )
            return

        if text == "📢 Kanalga kodni tashlash":
            set_state(user_id, "ADMIN_POST_CHANNEL_CODE", {})
            bot.send_message(
                message.chat.id,
                "📢 <b>Kanalga qaysi kinoning nomi va kodini chiqaramiz?</b>\n"
                "🔢 Kino kodini yozing (masalan: <code>1</code> yoki <code>1 2 3</code>):",
                reply_markup=cancel_keyboard()
            )
            return

        if text == "🚀 Forsaj 1-10 ni kanalga tashlash":
            bot.send_message(message.chat.id, "⏳ Forsaj 1–10 kodlari @kinolar_botttt kanaliga joylanmoqda...")
            posted = 0
            for c in range(1, 11):
                m = get_movie_by_code(str(c))
                if m:
                    if post_movie_to_channels(m) > 0:
                        posted += 1
                    time.sleep(0.3)
            if posted > 0:
                bot.send_message(
                    message.chat.id,
                    f"✅ <b>{posted} ta kino nomi va kodi kanalingizga joylandi!</b>",
                    reply_markup=admin_menu_keyboard()
                )
            else:
                bot.send_message(
                    message.chat.id,
                    "⚠️ Kanalga post tashlash uchun avval <b>@kinolarr_olami_bot</b> ni <b>@kinolar_botttt</b> kanalingizga <b>Admin</b> qiling!",
                    reply_markup=admin_menu_keyboard()
                )
            return

        if text == "🗑 Kino o'chirish":
            set_state(user_id, "ADMIN_DELETE_MOVIE", {})
            bot.send_message(
                message.chat.id,
                "🗑 <b>O'chirmoqchi bo'lgan kino kodini kiriting:</b>",
                reply_markup=cancel_keyboard()
            )
            return

        if text == "📨 Xabar yuborish (Rassilka)":
            set_state(user_id, "ADMIN_BROADCAST", {})
            bot.send_message(
                message.chat.id,
                "📨 <b>Barcha foydalanuvchilarga yuboriladigan xabarni yuboring:</b>",
                reply_markup=cancel_keyboard()
            )
            return

        # --------- ADMIN STATE BOSQICHLARI ---------
        if state == "ADMIN_ADD_CHANNEL_ID":
            clean = text.strip()
            if "t.me/" in clean and not clean.startswith("https://t.me/+"):
                uname = clean.split("t.me/", 1)[1].split("/")[0].strip()
                ch_id = f"@{uname.lstrip('@')}"
                invite_link = f"https://t.me/{uname.lstrip('@')}"
            elif clean.startswith("@"):
                ch_id = clean
                invite_link = f"https://t.me/{clean.lstrip('@')}"
            else:
                ch_id = f"@{clean.lstrip('@')}"
                invite_link = f"https://t.me/{clean.lstrip('@')}"

            ch_title = "Kinolar bot"
            try:
                chat_obj = bot.get_chat(ch_id)
                if chat_obj and chat_obj.title:
                    ch_title = chat_obj.title
            except Exception:
                pass

            add_channel(ch_id, ch_title, invite_link)
            clear_state(user_id)
            bot.send_message(
                message.chat.id,
                f"✅ <b>Kanal qo'shildi:</b> {ch_title} ({ch_id})",
                reply_markup=admin_menu_keyboard()
            )
            return

        if state == "ADMIN_ATTACH_VIDEO_CODE":
            code = text.lstrip("#").strip()
            movie = get_movie_by_code(code)
            if not movie:
                bot.send_message(message.chat.id, f"❌ <code>{code}</code> kodli kino topilmadi!", reply_markup=cancel_keyboard())
                return
            set_state(user_id, "ADMIN_ATTACH_VIDEO_FILE", {"code": code})
            bot.send_message(
                message.chat.id,
                f"🎬 Tanlangan kino: <b>{movie['title']}</b>\n📹 Endi video faylni yuboring:",
                reply_markup=cancel_keyboard()
            )
            return

        if state == "ADMIN_QUICK_VIDEO_CODE":
            code = text.lstrip("#").strip()
            file_id = data["file_id"]
            existing = get_movie_by_code(code)
            if existing:
                update_movie_file_id(code, file_id)
                clear_state(user_id)
                updated_movie = get_movie_by_code(code)
                bot.send_message(
                    message.chat.id,
                    f"✅ <b>To'liq kino <code>{code}</code>-kodga («{existing['title']}») biriktirildi!</b>\n"
                    f"⚡️ Endi <code>{code}</code> yozgan har bir odamga 1 soniyada chiqadi:",
                    reply_markup=ReplyKeyboardRemove()
                )
                send_protected_movie(message.chat.id, updated_movie)
            else:
                data["code"] = code
                set_state(user_id, "ADMIN_NEW_MOVIE_TITLE", data)
                bot.send_message(message.chat.id, "🎬 Kino nomini kiriting:", reply_markup=cancel_keyboard())
            return

        if state == "ADMIN_NEW_MOVIE_VIDEO" and text.lower() == "skip":
            data["file_id"] = ""
            next_code = get_next_available_code()
            set_state(user_id, "ADMIN_NEW_MOVIE_CODE", data)
            bot.send_message(message.chat.id, f"🔢 Kino uchun KOD kiriting (masalan: <code>{next_code}</code>):", reply_markup=cancel_keyboard())
            return

        if state == "ADMIN_NEW_MOVIE_CODE":
            data["code"] = text.lstrip("#").strip()
            set_state(user_id, "ADMIN_NEW_MOVIE_TITLE", data)
            bot.send_message(message.chat.id, "🎬 Kino nomini kiriting:", reply_markup=cancel_keyboard())
            return

        if state == "ADMIN_NEW_MOVIE_TITLE":
            data["title"] = text
            set_state(user_id, "ADMIN_NEW_MOVIE_GENRE", data)
            bot.send_message(message.chat.id, "🎭 Kino yili va janrini kiriting (Masalan: 2024, Jangari):", reply_markup=cancel_keyboard())
            return

        if state == "ADMIN_NEW_MOVIE_GENRE":
            parts = [p.strip() for p in text.split(",", 1)]
            if len(parts) == 2 and parts[0].isdigit():
                data["year"] = parts[0]
                data["genre"] = parts[1]
            else:
                data["year"] = "2024"
                data["genre"] = text
            set_state(user_id, "ADMIN_NEW_MOVIE_DESC", data)
            bot.send_message(message.chat.id, "📝 Kino haqida qisqacha izoh yozing:", reply_markup=cancel_keyboard())
            return

        if state == "ADMIN_NEW_MOVIE_DESC":
            add_or_update_movie(
                code=data["code"],
                title=data["title"],
                year=data.get("year", "2024"),
                genre=data.get("genre", "Jangari"),
                description=text,
                file_id=data.get("file_id", "")
            )
            movie = get_movie_by_code(data["code"])
            clear_state(user_id)
            post_movie_to_channels(movie)
            bot.send_message(
                message.chat.id,
                f"✅ <b>Kino saqlandi!</b>\n🎬 {movie['title']} (Kod: <code>{movie['code']}</code>)",
                reply_markup=admin_menu_keyboard()
            )
            return

        if state == "ADMIN_POST_CHANNEL_CODE":
            codes = text.replace(",", " ").split()
            posted_count = 0
            for c in codes:
                m = get_movie_by_code(c.strip())
                if m and post_movie_to_channels(m) > 0:
                    posted_count += 1
            clear_state(user_id)
            if posted_count > 0:
                bot.send_message(message.chat.id, f"✅ {posted_count} ta kino kanalga joylandi!", reply_markup=admin_menu_keyboard())
            else:
                bot.send_message(
                    message.chat.id,
                    "⚠️ Kanalga joylash uchun avval @kinolarr_olami_bot ni @kinolar_botttt kanalingizga Admin qiling!",
                    reply_markup=admin_menu_keyboard()
                )
            return

        if state == "ADMIN_DELETE_MOVIE":
            code = text.lstrip("#").strip()
            if delete_movie(code):
                clear_state(user_id)
                bot.send_message(message.chat.id, f"🗑 <code>{code}</code> kodli kino o'chirildi!", reply_markup=admin_menu_keyboard())
            else:
                bot.send_message(message.chat.id, "❌ Bunday kod topilmadi.", reply_markup=cancel_keyboard())
            return

        if state == "ADMIN_BROADCAST":
            execute_broadcast(message)
            return

    # ================= ODDIY FOYDALANUVCHI: OBUNA TEKSHIRISH VA KOD QIDIRISH =================

    unsubscribed = get_unsubscribed_channels(user_id, from_callback=False)
    if unsubscribed:
        pending = text.lstrip("#").strip() if text.lstrip("#").strip().isdigit() else ""
        send_subscription_prompt(message.chat.id, unsubscribed, pending_code=pending)
        return

    clean_code = text.lstrip("#").strip()
    movie_by_code = get_movie_by_code(clean_code)
    if movie_by_code:
        send_protected_movie(message.chat.id, movie_by_code)
        return

    bot.send_message(
        message.chat.id,
        "❌ Bunday kodli kino topilmadi.\n\n🎬 <b>Marhamat, to'g'ri kino kodini kiriting:</b>",
        reply_markup=user_default_keyboard(user_id)
    )


def execute_broadcast(message):
    user_id = message.from_user.id
    users = get_all_users()
    clear_state(user_id)
    bot.send_message(message.chat.id, f"⏳ Xabar {len(users)} ta foydalanuvchiga yuborilmoqda...")

    sent_ok = 0
    for u in users:
        try:
            bot.copy_message(
                chat_id=u["user_id"],
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            sent_ok += 1
            time.sleep(0.05)
        except Exception:
            pass

    bot.send_message(
        message.chat.id,
        f"✅ Yetkazildi: {sent_ok}/{len(users)} ta foydalanuvchiga.",
        reply_markup=admin_menu_keyboard()
    )


import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler


class CloudServerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"OK - @kinolarr_olami_bot is running 24/7 on Render!\n")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def do_POST(self):
        if self.path.startswith("/webhook"):
            length = int(self.headers.get("content-length", 0))
            body = self.rfile.read(length).decode("utf-8")
            try:
                update = telebot.types.Update.de_json(json.loads(body))
                if update:
                    bot.process_new_updates([update])
            except Exception as e:
                print(f"⚠️ Webhook update xatolik: {e}")
            self.send_response(200)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    port_str = os.environ.get("PORT", "").strip()
    port = int(port_str) if port_str.isdigit() else 10000
    webhook_url = os.environ.get("WEBHOOK_URL", "").strip().rstrip("/")
    if not webhook_url and os.environ.get("RENDER"):
        webhook_url = "https://kino-bot-s6um.onrender.com"

    me = bot.get_me()
    try:
        bot.set_my_commands([
            telebot.types.BotCommand("start", "🎬 Kino kodini kiritish"),
        ])
    except Exception:
        pass
    print("\n" + "=" * 65)
    print(f"✅ VIP KINO BOT MUVAFFAQIYATLI ISHGA TUSHDI!")
    print(f"🤖 Bot nomi: {me.first_name} (@{me.username})")
    print(f"📡 Majburiy obuna kanali: https://t.me/kinolar_botttt")
    print(f"🎬 Bazadagi tayyor kinolar: {len(get_all_movies())} ta")
    print(f"🔐 Admin panelga kirish: Botga /admin yoki admin/ deb yozing")
    print(f"🔑 Admin paroli: {get_setting('admin_password', 'abdu8811')}")
    print("=" * 65 + "\n")

    if webhook_url:
        full_webhook = f"{webhook_url}/webhook"
        print(f"🌐 Webhook rejimi faollashmoqda: {full_webhook}")
        try:
            bot.remove_webhook()
            time.sleep(0.5)
            bot.set_webhook(url=full_webhook, drop_pending_updates=False)
            print("✅ Webhook Telegramga muvaffaqiyatli ulandi!")
        except Exception as e:
            print(f"⚠️ Webhook o'rnatishda xatolik: {e}")

        print(f"🚀 Webhook HTTP server port {port} da tinglamoqda...")
        server = HTTPServer(("0.0.0.0", port), CloudServerHandler)
        server.serve_forever()
    else:
        # Lokal kompyuterda (Polling rejimida)
        try:
            bot.remove_webhook()
        except Exception:
            pass
        try:
            server = HTTPServer(("0.0.0.0", port), CloudServerHandler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
        except Exception:
            pass
        while True:
            try:
                bot.infinity_polling(timeout=20, long_polling_timeout=10, skip_pending=False)
            except Exception as e:
                print(f"⚠️ Polling xatolik yuz berdi (5 soniyada qayta urinadi): {e}")
                time.sleep(5)
