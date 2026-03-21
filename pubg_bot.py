"""
PUBG Mobile Akkount Savdo Boti
==============================
Kerakli kutubxonalar:
    pip install aiogram==3.7.0 aiosqlite python-dotenv pillow

Ishga tushirish:
    1. .env faylida quyidagilarni to'ldiring (yoki to'g'ridan kodni o'zgartiring):
        BOT_TOKEN=...
        ADMIN_IDS=123456789,987654321   # vergul bilan ajratilgan admin ID'lar
        CHANNEL_ID=@kanal_username      # yoki -100xxxxxxxxx formatida
    2. python pubg_bot.py
"""

import asyncio
import os
import io
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import aiosqlite
from PIL import Image, ImageDraw, ImageFont
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    BufferedInputFile, InputMediaPhoto
)

# ─── SOZLAMALAR ──────────────────────────────────────────────────────────────
BOT_TOKEN   = os.getenv("BOT_TOKEN", "TOKEN_BU_YERGA")
ADMIN_IDS   = [int(x) for x in os.getenv("ADMIN_IDS", "123456789").split(",")]
CHANNEL_ID  = os.getenv("CHANNEL_ID", "@kanal_username")
DB_PATH     = "pubg_bot.db"
TASHKENT_TZ = timezone(timedelta(hours=5))

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp  = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)


# ─── FSM HOLATLARI ───────────────────────────────────────────────────────────
class SellAcc(StatesGroup):
    video      = State()
    level      = State()
    weapons    = State()
    suits      = State()
    rp         = State()
    vehicles   = State()
    price      = State()
    phone      = State()

class AdState(StatesGroup):
    choose     = State()   # bepul/pulik tanlash
    video      = State()   # reklama videosi
    pay_proof  = State()   # to'lov cheki

class HelpState(StatesGroup):
    message    = State()

class AdminState(StatesGroup):
    set_start_msg   = State()
    set_ad_price    = State()
    set_card        = State()
    add_channel     = State()
    reply_user      = State()   # yordam javob

class AdminReply(StatesGroup):
    text = State()

# ─── DATABASE ────────────────────────────────────────────────────────────────
async def db_init():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY,
            username   TEXT,
            first_name TEXT,
            joined_at  TEXT
        );
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS accounts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            file_id     TEXT,
            level       TEXT,
            weapons     TEXT,
            suits       TEXT,
            rp          TEXT,
            vehicles    TEXT,
            price       TEXT,
            phone       TEXT,
            status      TEXT DEFAULT 'pending',
            channel_msg INTEGER,
            created_at  TEXT
        );
        CREATE TABLE IF NOT EXISTS ads (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            file_id     TEXT,
            ad_type     TEXT,
            status      TEXT DEFAULT 'pending',
            created_at  TEXT
        );
        CREATE TABLE IF NOT EXISTS mandatory_channels (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            channel TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS help_msgs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            text       TEXT,
            created_at TEXT,
            answered   INTEGER DEFAULT 0
        );
        """)
        # Default sozlamalar
        defaults = {
            "start_message": "Assalomu alaykum! PUBG Mobile akkount savdo botiga xush kelibsiz 🎮",
            "ad_price": "50000",
            "card_number": "0000 0000 0000 0000",
        }
        for k, v in defaults.items():
            await db.execute(
                "INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k, v)
            )
        await db.commit()

async def get_setting(key: str) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = await cur.fetchone()
        return row[0] if row else ""

async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, value))
        await db.commit()

async def register_user(user):
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d %H:%M:%S")
        await db.execute(
            "INSERT OR IGNORE INTO users(id,username,first_name,joined_at) VALUES(?,?,?,?)",
            (user.id, user.username, user.first_name, now)
        )
        await db.commit()

async def get_mandatory_channels():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT channel FROM mandatory_channels")
        rows = await cur.fetchall()
        return [r[0] for r in rows]

async def check_subscription(user_id: int) -> list[str]:
    """Obuna bo'lmagan kanallar ro'yxatini qaytaradi"""
    channels = await get_mandatory_channels()
    not_subbed = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch, user_id)
            if member.status in ("left", "kicked", "banned"):
                not_subbed.append(ch)
        except Exception:
            not_subbed.append(ch)
    return not_subbed

def sub_keyboard(channels: list[str]) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=f"📢 {ch}", url=f"https://t.me/{ch.lstrip('@')}")] for ch in channels]
    buttons.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ─── YORDAMCHI FUNKSIYALAR ───────────────────────────────────────────────────
def admin_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📝 Start xabar")],
            [KeyboardButton(text="💰 Reklama narxi"), KeyboardButton(text="💳 Karta raqam")],
            [KeyboardButton(text="📢 Kanal qo'shish"), KeyboardButton(text="🗑 Kanal o'chirish")],
            [KeyboardButton(text="📋 Kanallar ro'yxati")],
        ],
        resize_keyboard=True
    )

def main_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎮 Akkount joylash")],
            [KeyboardButton(text="📣 Reklama qo'yish")],
            [KeyboardButton(text="❓ Yordam")],
        ],
        resize_keyboard=True
    )

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

async def notify_admins(text: str, reply_markup=None):
    for aid in ADMIN_IDS:
        try:
            await bot.send_message(aid, text, reply_markup=reply_markup)
        except Exception:
            pass

# ─── STATISTIKA RASMI ────────────────────────────────────────────────────────
async def make_stats_image() -> bytes:
    async with aiosqlite.connect(DB_PATH) as db:
        total_users = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
        total_acc   = (await (await db.execute("SELECT COUNT(*) FROM accounts")).fetchone())[0]
        total_ads   = (await (await db.execute("SELECT COUNT(*) FROM ads")).fetchone())[0]
        cur = await db.execute(
            "SELECT u.first_name, u.username, u.id, u.joined_at, "
            "(SELECT COUNT(*) FROM ads a WHERE a.user_id=u.id) as ad_count "
            "FROM users u ORDER BY ad_count DESC LIMIT 10"
        )
        top_users = await cur.fetchall()

    W, H = 900, 600
    img = Image.new("RGB", (W, H), "#0f0c29")
    draw = ImageDraw.Draw(img)

    # Gradient background simulation
    for y in range(H):
        r = int(15 + (y/H)*30)
        g = int(12 + (y/H)*20)
        b = int(41 + (y/H)*60)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    try:
        font_big  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
        font_med  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        font_sm   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    except Exception:
        font_big = font_med = font_sm = ImageFont.load_default()

    now_str = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d %H:%M") + " (Toshkent)"
    draw.text((40, 30), "📊 Bot Statistikasi", font=font_big, fill="#f9ca24")
    draw.text((40, 80), now_str, font=font_sm, fill="#aaa")

    draw.rounded_rectangle([30, 110, 280, 190], radius=15, fill="#1a1a2e")
    draw.text((50, 120), "👤 Foydalanuvchilar", font=font_sm, fill="#aaa")
    draw.text((50, 148), str(total_users), font=font_med, fill="#f9ca24")

    draw.rounded_rectangle([300, 110, 550, 190], radius=15, fill="#1a1a2e")
    draw.text((320, 120), "🎮 Akkountlar", font=font_sm, fill="#aaa")
    draw.text((320, 148), str(total_acc), font=font_med, fill="#6c5ce7")

    draw.rounded_rectangle([570, 110, 820, 190], radius=15, fill="#1a1a2e")
    draw.text((590, 120), "📣 Reklamalar", font=font_sm, fill="#aaa")
    draw.text((590, 148), str(total_ads), font=font_med, fill="#00b894")

    draw.text((40, 210), "🏆 Top foydalanuvchilar (reklama bo'yicha):", font=font_sm, fill="#dfe6e9")
    y0 = 240
    for i, (fname, uname, uid, joined, ad_count) in enumerate(top_users):
        uname_str = f"@{uname}" if uname else f"ID:{uid}"
        joined_str = joined[:10] if joined else "?"
        line = f"{i+1}. {fname or 'Nomsiz'}  {uname_str}  |  Reklama: {ad_count}  |  Qo'shilgan: {joined_str}"
        draw.text((40, y0), line, font=font_sm, fill="#dfe6e9")
        y0 += 28

    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


# ─── /start ──────────────────────────────────────────────────────────────────
@router.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext):
    await state.clear()
    await register_user(msg.from_user)

    not_subbed = await check_subscription(msg.from_user.id)
    if not_subbed:
        await msg.answer(
            "⚠️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
            reply_markup=sub_keyboard(not_subbed)
        )
        return

    start_msg = await get_setting("start_message")
    greeting = (
        f"{start_msg}\n\n"
        f"Salom, <b>{msg.from_user.first_name}</b>! 👋\n\n"
        "Bu botda siz PUBG Mobile akkountingizni sotishga qo'yishingiz mumkin.\n"
        "Video yuklab, ma'lumotlarni kiriting — biz kanalga joylaymiz! 🚀"
    )
    kb = admin_kb() if is_admin(msg.from_user.id) else main_kb()
    await msg.answer(greeting, reply_markup=kb)


@router.callback_query(F.data == "check_sub")
async def check_sub_cb(cb: CallbackQuery, state: FSMContext):
    not_subbed = await check_subscription(cb.from_user.id)
    if not_subbed:
        await cb.answer("Hali obuna bo'lmadingiz!", show_alert=True)
        return
    await cb.message.delete()
    await cmd_start(cb.message, state)


# ─── AKKOUNT JOYLASH ─────────────────────────────────────────────────────────
@router.message(F.text == "🎮 Akkount joylash")
async def sell_start(msg: Message, state: FSMContext):
    not_subbed = await check_subscription(msg.from_user.id)
    if not_subbed:
        await msg.answer("⚠️ Avval kanallarga obuna bo'ling:", reply_markup=sub_keyboard(not_subbed))
        return
    await state.set_state(SellAcc.video)
    await msg.answer("🎬 Akkount videosini yuboring:", reply_markup=ReplyKeyboardRemove())

@router.message(SellAcc.video, F.video)
async def sell_video(msg: Message, state: FSMContext):
    await state.update_data(file_id=msg.video.file_id)
    await state.set_state(SellAcc.level)
    await msg.answer("🏆 Akkount levelini kiriting (masalan: 70):")

@router.message(SellAcc.level)
async def sell_level(msg: Message, state: FSMContext):
    await state.update_data(level=msg.text)
    await state.set_state(SellAcc.weapons)
    await msg.answer("🔫 Nechta qurol bor? (raqamda kiriting):")

@router.message(SellAcc.weapons)
async def sell_weapons(msg: Message, state: FSMContext):
    await state.update_data(weapons=msg.text)
    await state.set_state(SellAcc.suits)
    await msg.answer("👗 Nechta X-suit bor? (raqamda kiriting):")

@router.message(SellAcc.suits)
async def sell_suits(msg: Message, state: FSMContext):
    await state.update_data(suits=msg.text)
    await state.set_state(SellAcc.rp)
    await msg.answer("🏅 Nechta RP olingan? (raqamda kiriting):")

@router.message(SellAcc.rp)
async def sell_rp(msg: Message, state: FSMContext):
    await state.update_data(rp=msg.text)
    await state.set_state(SellAcc.vehicles)
    await msg.answer("🚗 Nechta mashina bor? (raqamda kiriting):")

@router.message(SellAcc.vehicles)
async def sell_vehicles(msg: Message, state: FSMContext):
    await state.update_data(vehicles=msg.text)
    await state.set_state(SellAcc.price)
    await msg.answer("💰 Narxi so'mda kiriting (masalan: 500000):")

@router.message(SellAcc.price)
async def sell_price(msg: Message, state: FSMContext):
    await state.update_data(price=msg.text)
    await state.set_state(SellAcc.phone)
    await msg.answer("📞 Murojat uchun telefon raqamingiz (+998901234567):")

@router.message(SellAcc.phone)
async def sell_phone(msg: Message, state: FSMContext):
    await state.update_data(phone=msg.text)
    data = await state.get_data()
    await state.clear()

    now = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO accounts(user_id,file_id,level,weapons,suits,rp,vehicles,price,phone,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (msg.from_user.id, data["file_id"], data["level"], data["weapons"],
             data["suits"], data["rp"], data["vehicles"], data["price"], data["phone"], now)
        )
        acc_id = cur.lastrowid
        await db.commit()

    caption = (
        f"🎮 <b>Yangi akkount so'rovi</b>\n\n"
        f"👤 Foydalanuvchi: {msg.from_user.first_name} (@{msg.from_user.username or 'yo'q'})\n"
        f"🏆 Level: {data['level']}\n"
        f"🔫 Qurollar: {data['weapons']} ta\n"
        f"👗 X-suit: {data['suits']} ta\n"
        f"🏅 RP: {data['rp']}\n"
        f"🚗 Mashina: {data['vehicles']} ta\n"
        f"💰 Narx: {data['price']} so'm\n"
        f"📞 Telefon: {data['phone']}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"acc_approve:{acc_id}"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"acc_reject:{acc_id}"),
        ]
    ])
    await notify_admins(f"📬 Yangi akkount #{acc_id} tasdiqlash kutmoqda!\n{caption}", reply_markup=kb)

    # Adminlarga video ham yuboramiz
    for aid in ADMIN_IDS:
        try:
            await bot.send_video(aid, data["file_id"], caption=f"Video | Akkount #{acc_id}")
        except Exception:
            pass

    await msg.answer(
        "✅ Ma'lumotlaringiz adminga yuborildi. Tasdiqlangandan so'ng kanalga joylashadi!",
        reply_markup=main_kb()
    )


# Admin tasdiqlash/rad etish
@router.callback_query(F.data.startswith("acc_approve:"))
async def acc_approve(cb: CallbackQuery):
    acc_id = int(cb.data.split(":")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT * FROM accounts WHERE id=?", (acc_id,))
        row = await cur.fetchone()
    if not row:
        await cb.answer("Topilmadi!")
        return

    # row: id,user_id,file_id,level,weapons,suits,rp,vehicles,price,phone,status,channel_msg,created_at
    _, user_id, file_id, level, weapons, suits, rp, vehicles, price, phone, *_ = row

    caption = (
        f"🎮 <b>PUBG Mobile Akkount Sotuvda!</b>\n\n"
        f"🏆 Level: <b>{level}</b>\n"
        f"🔫 Qurollar: <b>{weapons} ta</b>\n"
        f"👗 X-suit: <b>{suits} ta</b>\n"
        f"🏅 RP: <b>{rp}</b>\n"
        f"🚗 Mashina: <b>{vehicles} ta</b>\n"
        f"💰 Narx: <b>{price} so'm</b>\n"
        f"📞 Bog'lanish: <b>{phone}</b>"
    )
    # Kanalga yuborish — pastiga "Sotuvchi bilan bog'lanish" tugmasi
    contact_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📩 Sotuvchi bilan bog'lanish", callback_data=f"contact_seller:{acc_id}:{user_id}")]
    ])
    try:
        sent = await bot.send_video(CHANNEL_ID, file_id, caption=caption, reply_markup=contact_kb)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE accounts SET status='approved', channel_msg=? WHERE id=?",
                (sent.message_id, acc_id)
            )
            await db.commit()
        await cb.message.edit_text(cb.message.text + "\n\n✅ Tasdiqlandi va kanalga joylandi!")
        await bot.send_message(user_id, "🎉 Akkountingiz tasdiqlandi va kanalga joylandi!")
    except Exception as e:
        await cb.answer(f"Xato: {e}", show_alert=True)

@router.callback_query(F.data.startswith("acc_reject:"))
async def acc_reject(cb: CallbackQuery):
    acc_id = int(cb.data.split(":")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id FROM accounts WHERE id=?", (acc_id,))
        row = await cur.fetchone()
        await db.execute("UPDATE accounts SET status='rejected' WHERE id=?", (acc_id,))
        await db.commit()
    if row:
        await bot.send_message(row[0], "❌ Akkountingiz rad etildi. Iltimos, qayta urinib ko'ring.")
    await cb.message.edit_text(cb.message.text + "\n\n❌ Rad etildi.")

# Kanaldan sotuvchi bilan bog'lanish
@router.callback_query(F.data.startswith("contact_seller:"))
async def contact_seller(cb: CallbackQuery):
    _, acc_id, seller_id = cb.data.split(":")
    seller_id = int(seller_id)
    try:
        await bot.send_message(
            seller_id,
            f"📩 Kimdir akkountingiz bo'yicha siz bilan bog'lanmoqchi!\n"
            f"👤 {cb.from_user.first_name} (@{cb.from_user.username or 'yo'q'})\n"
            f"ID: {cb.from_user.id}\n\n"
            f"Uning bilan to'g'ridan-to'g'ri muloqot qiling."
        )
        await cb.answer("✅ Sotuvchiga xabar yuborildi!", show_alert=True)
    except Exception:
        await cb.answer("❌ Sotuvchiga xabar yuborib bo'lmadi.", show_alert=True)


# ─── REKLAMA QO'YISH ─────────────────────────────────────────────────────────
@router.message(F.text == "📣 Reklama qo'yish")
async def ad_start(msg: Message, state: FSMContext):
    not_subbed = await check_subscription(msg.from_user.id)
    if not_subbed:
        await msg.answer("⚠️ Avval kanallarga obuna bo'ling:", reply_markup=sub_keyboard(not_subbed))
        return

    ad_price = await get_setting("ad_price")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆓 1-video BEPUL", callback_data="ad_free")],
        [InlineKeyboardButton(text=f"💰 2-video PULIK ({ad_price} so'm)", callback_data="ad_paid")],
    ])
    await state.set_state(AdState.choose)
    await msg.answer(
        f"📣 <b>Reklama qo'yish</b>\n\n"
        f"• 1-video — <b>BEPUL</b>\n"
        f"• Keyingi videolar — <b>{ad_price} so'm</b> har biri\n\n"
        "Tanlang:",
        reply_markup=kb
    )

@router.callback_query(F.data.in_({"ad_free", "ad_paid"}), StateFilter(AdState.choose))
async def ad_type_chosen(cb: CallbackQuery, state: FSMContext):
    await state.update_data(ad_type=cb.data)
    if cb.data == "ad_paid":
        card = await get_setting("card_number")
        ad_price = await get_setting("ad_price")
        await cb.message.edit_text(
            f"💳 To'lov ma'lumotlari:\n\n"
            f"Karta: <code>{card}</code>\n"
            f"Summa: <b>{ad_price} so'm</b>\n\n"
            f"To'lovni amalga oshirgach, chekni (screenshot) yuboring:"
        )
        await state.set_state(AdState.pay_proof)
    else:
        await cb.message.edit_text("🎬 Reklama videosini yuboring:")
        await state.set_state(AdState.video)

@router.message(AdState.pay_proof, F.photo | F.document)
async def ad_pay_proof(msg: Message, state: FSMContext):
    data = await state.get_data()
    file_id = msg.photo[-1].file_id if msg.photo else msg.document.file_id
    await state.update_data(proof_file=file_id)
    for aid in ADMIN_IDS:
        try:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"ad_payok:{msg.from_user.id}"),
                    InlineKeyboardButton(text="❌ Rad etish", callback_data=f"ad_payno:{msg.from_user.id}"),
                ]
            ])
            await bot.send_photo(aid, file_id,
                caption=f"💳 To'lov cheki\n👤 {msg.from_user.first_name} (@{msg.from_user.username})\nID: {msg.from_user.id}",
                reply_markup=kb)
        except Exception:
            pass
    await state.set_state(AdState.video)
    await msg.answer("✅ Chek yuborildi. Admin tasdiqlashini kuting. Endi reklama videosini yuboring:")

@router.message(AdState.video, F.video)
async def ad_video(msg: Message, state: FSMContext):
    data = await state.get_data()
    now = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO ads(user_id,file_id,ad_type,created_at) VALUES(?,?,?,?)",
            (msg.from_user.id, msg.video.file_id, data.get("ad_type","ad_free"), now)
        )
        ad_id = cur.lastrowid
        await db.commit()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"ad_approve:{ad_id}"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"ad_reject:{ad_id}"),
        ]
    ])
    await notify_admins(
        f"📣 Yangi reklama #{ad_id} tasdiqlash kutmoqda!\n"
        f"👤 {msg.from_user.first_name} | ID: {msg.from_user.id}\n"
        f"Tur: {'BEPUL' if data.get('ad_type')=='ad_free' else 'PULIK'}",
        reply_markup=kb
    )
    for aid in ADMIN_IDS:
        try:
            await bot.send_video(aid, msg.video.file_id, caption=f"Reklama videosi #{ad_id}")
        except Exception:
            pass
    await state.clear()
    await msg.answer("✅ Reklama adminga yuborildi. Tasdiqlangandan so'ng kanalga joylashadi!", reply_markup=main_kb())

@router.callback_query(F.data.startswith("ad_approve:"))
async def ad_approve(cb: CallbackQuery):
    ad_id = int(cb.data.split(":")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id, file_id FROM ads WHERE id=?", (ad_id,))
        row = await cur.fetchone()
        await db.execute("UPDATE ads SET status='approved' WHERE id=?", (ad_id,))
        await db.commit()
    if row:
        try:
            await bot.send_video(CHANNEL_ID, row[1], caption="📣 <b>Reklama</b>")
            await bot.send_message(row[0], "🎉 Reklamangiz tasdiqlandi va kanalga joylandi!")
        except Exception as e:
            await cb.answer(str(e), show_alert=True)
    await cb.message.edit_text(cb.message.text + "\n\n✅ Tasdiqlandi!")

@router.callback_query(F.data.startswith("ad_reject:"))
async def ad_reject(cb: CallbackQuery):
    ad_id = int(cb.data.split(":")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id FROM ads WHERE id=?", (ad_id,))
        row = await cur.fetchone()
        await db.execute("UPDATE ads SET status='rejected' WHERE id=?", (ad_id,))
        await db.commit()
    if row:
        await bot.send_message(row[0], "❌ Reklamangiz rad etildi.")
    await cb.message.edit_text(cb.message.text + "\n\n❌ Rad etildi.")

@router.callback_query(F.data.startswith("ad_payok:"))
async def ad_payok(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    await bot.send_message(uid, "✅ To'lovingiz tasdiqlandi! Endi reklama videosini yuboring.")
    await cb.message.edit_text(cb.message.text + "\n\n✅ To'lov tasdiqlandi.")

@router.callback_query(F.data.startswith("ad_payno:"))
async def ad_payno(cb: CallbackQuery):
    uid = int(cb.data.split(":")[1])
    await bot.send_message(uid, "❌ To'lovingiz tasdiqlanmadi. Iltimos, to'g'ri to'lov qiling.")
    await cb.message.edit_text(cb.message.text + "\n\n❌ To'lov rad etildi.")


# ─── YORDAM ──────────────────────────────────────────────────────────────────
@router.message(F.text == "❓ Yordam")
async def help_start(msg: Message, state: FSMContext):
    await state.set_state(HelpState.message)
    await msg.answer("✍️ Savolingiz yoki muammoingizni yozing:", reply_markup=ReplyKeyboardRemove())

@router.message(HelpState.message)
async def help_msg(msg: Message, state: FSMContext):
    now = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO help_msgs(user_id,text,created_at) VALUES(?,?,?)",
            (msg.from_user.id, msg.text, now)
        )
        hid = cur.lastrowid
        await db.commit()
    await state.clear()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Javob yozish", callback_data=f"help_reply:{hid}:{msg.from_user.id}")]
    ])
    await notify_admins(
        f"❓ Yordam so'rovi #{hid}\n"
        f"👤 {msg.from_user.first_name} (@{msg.from_user.username or 'yo'q'}) | ID: {msg.from_user.id}\n\n"
        f"💬 {msg.text}",
        reply_markup=kb
    )
    await msg.answer("✅ Xabaringiz adminga yuborildi. Tez orada javob berishadi!", reply_markup=main_kb())

@router.callback_query(F.data.startswith("help_reply:"))
async def help_reply_cb(cb: CallbackQuery, state: FSMContext):
    parts = cb.data.split(":")
    hid, uid = parts[1], parts[2]
    await state.set_state(AdminReply.text)
    await state.update_data(target_uid=int(uid), help_id=hid)
    await cb.message.answer("✍️ Javobingizni yozing:")

@router.message(AdminReply.text)
async def admin_reply_send(msg: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    try:
        await bot.send_message(
            data["target_uid"],
            f"📬 <b>Admin javobi:</b>\n\n{msg.text}"
        )
        await msg.answer("✅ Javob yuborildi!")
    except Exception as e:
        await msg.answer(f"❌ Xato: {e}")


# ─── ADMIN PANEL ─────────────────────────────────────────────────────────────
@router.message(F.text == "📊 Statistika")
async def admin_stats(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    await msg.answer("⏳ Statistika tayyorlanmoqda...")
    img_bytes = await make_stats_image()
    await msg.answer_photo(
        BufferedInputFile(img_bytes, filename="stats.png"),
        caption="📊 Bot statistikasi"
    )

@router.message(F.text == "📝 Start xabar")
async def admin_set_start(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    await state.set_state(AdminState.set_start_msg)
    await msg.answer("✍️ Yangi start xabarini kiriting:")

@router.message(AdminState.set_start_msg)
async def admin_start_msg_save(msg: Message, state: FSMContext):
    await set_setting("start_message", msg.text)
    await state.clear()
    await msg.answer("✅ Start xabar yangilandi!", reply_markup=admin_kb())

@router.message(F.text == "💰 Reklama narxi")
async def admin_set_price(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    cur = await get_setting("ad_price")
    await state.set_state(AdminState.set_ad_price)
    await msg.answer(f"💰 Joriy narx: {cur} so'm\nYangi narxni kiriting (faqat raqam):")

@router.message(AdminState.set_ad_price)
async def admin_price_save(msg: Message, state: FSMContext):
    await set_setting("ad_price", msg.text.strip())
    await state.clear()
    await msg.answer(f"✅ Reklama narxi {msg.text} so'mga o'zgartirildi!", reply_markup=admin_kb())

@router.message(F.text == "💳 Karta raqam")
async def admin_set_card(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    cur = await get_setting("card_number")
    await state.set_state(AdminState.set_card)
    await msg.answer(f"💳 Joriy karta: <code>{cur}</code>\nYangi karta raqamini kiriting:")

@router.message(AdminState.set_card)
async def admin_card_save(msg: Message, state: FSMContext):
    await set_setting("card_number", msg.text.strip())
    await state.clear()
    await msg.answer("✅ Karta raqami yangilandi!", reply_markup=admin_kb())

@router.message(F.text == "📢 Kanal qo'shish")
async def admin_add_ch(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    await state.set_state(AdminState.add_channel)
    await msg.answer("Majburiy obuna kanalini kiriting (masalan: @kanal_username):")

@router.message(AdminState.add_channel)
async def admin_add_ch_save(msg: Message, state: FSMContext):
    ch = msg.text.strip()
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("INSERT INTO mandatory_channels(channel) VALUES(?)", (ch,))
            await db.commit()
            await msg.answer(f"✅ {ch} kanali qo'shildi!", reply_markup=admin_kb())
        except Exception:
            await msg.answer("⚠️ Bu kanal allaqachon mavjud!", reply_markup=admin_kb())
    await state.clear()

@router.message(F.text == "🗑 Kanal o'chirish")
async def admin_del_ch(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    channels = await get_mandatory_channels()
    if not channels:
        await msg.answer("Hech qanday kanal yo'q.")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🗑 {ch}", callback_data=f"delch:{ch}")] for ch in channels
    ])
    await msg.answer("O'chirmoqchi bo'lgan kanalni tanlang:", reply_markup=kb)

@router.callback_query(F.data.startswith("delch:"))
async def delch_cb(cb: CallbackQuery):
    ch = cb.data.split(":", 1)[1]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM mandatory_channels WHERE channel=?", (ch,))
        await db.commit()
    await cb.message.edit_text(f"✅ {ch} o'chirildi.")

@router.message(F.text == "📋 Kanallar ro'yxati")
async def admin_list_ch(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    channels = await get_mandatory_channels()
    if not channels:
        await msg.answer("Hech qanday majburiy obuna kanali yo'q.")
    else:
        text = "📋 <b>Majburiy obuna kanallari:</b>\n\n" + "\n".join(f"• {ch}" for ch in channels)
        await msg.answer(text)


# ─── ISHGA TUSHIRISH ─────────────────────────────────────────────────────────
async def main():
    await db_init()
    log.info("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
