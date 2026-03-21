"""
PUBG Mobile Akkount Savdo Boti — aiogram 2.x
pip install aiogram==2.25.2 aiosqlite==0.19.0
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta

import aiosqlite
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton
)

# ─── SOZLAMALAR ───────────────────────────────────────────────────────────────
BOT_TOKEN   = "8238302696:AAEoQ2Bvk_g0JsL5Om4OQmboLc8ZtmY1b0c"
ADMIN_IDS   = [8537782289]
CHANNEL_ID  = "@Azizbekl2026"
DB_PATH     = "pubg_bot.db"
TASHKENT_TZ = timezone(timedelta(hours=5))

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

bot     = Bot(token=BOT_TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp      = Dispatcher(bot, storage=storage)


# ─── FSM HOLATLARI ────────────────────────────────────────────────────────────
class SellAcc(StatesGroup):
    video    = State()
    level    = State()
    weapons  = State()
    suits    = State()
    rp       = State()
    vehicles = State()
    price    = State()
    phone    = State()

class AdState(StatesGroup):
    choose    = State()
    video     = State()
    pay_proof = State()

class HelpState(StatesGroup):
    message = State()

class AdminState(StatesGroup):
    set_start_msg = State()
    set_ad_price  = State()
    set_card      = State()
    add_channel   = State()

class AdminReply(StatesGroup):
    text = State()


# ─── DATABASE ─────────────────────────────────────────────────────────────────
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
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            file_id    TEXT,
            ad_type    TEXT,
            status     TEXT DEFAULT 'pending',
            created_at TEXT
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
        defaults = {
            "start_message": "Assalomu alaykum! PUBG Mobile akkount savdo botiga xush kelibsiz",
            "ad_price":      "50000",
            "card_number":   "0000 0000 0000 0000",
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

async def check_subscription(user_id: int) -> list:
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

def sub_keyboard(channels: list) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    for ch in channels:
        kb.add(InlineKeyboardButton(text=f"Kanal: {ch}", url=f"https://t.me/{ch.lstrip('@')}"))
    kb.add(InlineKeyboardButton(text="Tekshirish", callback_data="check_sub"))
    return kb

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

async def notify_admins(text: str, reply_markup=None):
    for aid in ADMIN_IDS:
        try:
            await bot.send_message(aid, text, reply_markup=reply_markup)
        except Exception:
            pass

def admin_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("Statistika", "Start xabar")
    kb.row("Reklama narxi", "Karta raqam")
    kb.row("Kanal qoshish", "Kanal ochirish")
    kb.row("Kanallar royxati")
    return kb

def main_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Akkount joylash")
    kb.add("Reklama qoyish")
    kb.add("Yordam")
    return kb

async def make_stats_text() -> str:
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

    now_str = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d %H:%M") + " (Toshkent)"
    lines = [
        "<b>Bot Statistikasi</b>",
        f"<i>{now_str}</i>\n",
        f"Foydalanuvchilar: <b>{total_users}</b>",
        f"Akkountlar: <b>{total_acc}</b>",
        f"Reklamalar: <b>{total_ads}</b>",
        "\n<b>Top foydalanuvchilar:</b>",
    ]
    for i, (fname, uname, uid, joined, ad_count) in enumerate(top_users):
        uname_str  = f"@{uname}" if uname else f"ID:{uid}"
        joined_str = joined[:10] if joined else "?"
        lines.append(f"{i+1}. {fname or 'Nomsiz'} | {uname_str} | Reklama: {ad_count} | {joined_str}")
    return "\n".join(lines)


# ─── /start ───────────────────────────────────────────────────────────────────
@dp.message_handler(commands=["start"], state="*")
async def cmd_start(msg: types.Message, state: FSMContext):
    await state.finish()
    await register_user(msg.from_user)

    not_subbed = await check_subscription(msg.from_user.id)
    if not_subbed:
        await msg.answer("Botdan foydalanish uchun kanallarga obuna boling:", reply_markup=sub_keyboard(not_subbed))
        return

    start_msg = await get_setting("start_message")
    text = (
        f"{start_msg}\n\n"
        f"Salom, <b>{msg.from_user.first_name}</b>!\n\n"
        "Bu botda <b>PUBG Mobile akkountingizni</b> sotishga qoyishingiz mumkin.\n"
        "Video yuklab, malumotlarni kiriting — biz kanalga joylaymiz!"
    )
    kb = admin_kb() if is_admin(msg.from_user.id) else main_kb()
    await msg.answer(text, reply_markup=kb)


@dp.callback_query_handler(lambda c: c.data == "check_sub", state="*")
async def check_sub_cb(cb: types.CallbackQuery, state: FSMContext):
    not_subbed = await check_subscription(cb.from_user.id)
    if not_subbed:
        await cb.answer("Hali obuna bolmadingiz!", show_alert=True)
        return
    await cb.message.delete()
    await state.finish()
    await register_user(cb.from_user)
    start_msg = await get_setting("start_message")
    text = (
        f"{start_msg}\n\n"
        f"Salom, <b>{cb.from_user.first_name}</b>!\n\n"
        "Bu botda <b>PUBG Mobile akkountingizni</b> sotishga qoyishingiz mumkin."
    )
    kb = admin_kb() if is_admin(cb.from_user.id) else main_kb()
    await bot.send_message(cb.from_user.id, text, reply_markup=kb)


# ─── AKKOUNT JOYLASH ──────────────────────────────────────────────────────────
@dp.message_handler(lambda m: m.text == "Akkount joylash", state="*")
async def sell_start(msg: types.Message, state: FSMContext):
    not_subbed = await check_subscription(msg.from_user.id)
    if not_subbed:
        await msg.answer("Avval kanallarga obuna boling:", reply_markup=sub_keyboard(not_subbed))
        return
    await SellAcc.video.set()
    await msg.answer(
        "<b>Akkount videosini yuboring:</b>\n"
        "Videoda akkountingizni korsating (inventory, level, skins...)",
        reply_markup=ReplyKeyboardRemove()
    )

@dp.message_handler(content_types=types.ContentType.VIDEO, state=SellAcc.video)
async def sell_video(msg: types.Message, state: FSMContext):
    await state.update_data(file_id=msg.video.file_id)
    await SellAcc.level.set()
    await msg.answer("Akkount <b>levelini</b> kiriting (masalan: 70):")

@dp.message_handler(state=SellAcc.level)
async def sell_level(msg: types.Message, state: FSMContext):
    await state.update_data(level=msg.text)
    await SellAcc.weapons.set()
    await msg.answer("<b>Nechta qurol</b> bor? Raqamda kiriting:")

@dp.message_handler(state=SellAcc.weapons)
async def sell_weapons(msg: types.Message, state: FSMContext):
    await state.update_data(weapons=msg.text)
    await SellAcc.suits.set()
    await msg.answer("<b>Nechta X-suit</b> bor? Raqamda kiriting:")

@dp.message_handler(state=SellAcc.suits)
async def sell_suits(msg: types.Message, state: FSMContext):
    await state.update_data(suits=msg.text)
    await SellAcc.rp.set()
    await msg.answer("<b>Nechta RP</b> olingan? Raqamda kiriting:")

@dp.message_handler(state=SellAcc.rp)
async def sell_rp(msg: types.Message, state: FSMContext):
    await state.update_data(rp=msg.text)
    await SellAcc.vehicles.set()
    await msg.answer("<b>Nechta mashina</b> bor? Raqamda kiriting:")

@dp.message_handler(state=SellAcc.vehicles)
async def sell_vehicles(msg: types.Message, state: FSMContext):
    await state.update_data(vehicles=msg.text)
    await SellAcc.price.set()
    await msg.answer("<b>Narxi somda</b> kiriting (masalan: 500000):")

@dp.message_handler(state=SellAcc.price)
async def sell_price(msg: types.Message, state: FSMContext):
    await state.update_data(price=msg.text)
    await SellAcc.phone.set()
    await msg.answer("<b>Murojat uchun telefon raqamingiz</b> (+998901234567):")

@dp.message_handler(state=SellAcc.phone)
async def sell_phone(msg: types.Message, state: FSMContext):
    await state.update_data(phone=msg.text)
    data = await state.get_data()
    await state.finish()

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
        f"<b>Yangi akkount sorovi #{acc_id}</b>\n\n"
        f"Foydalanuvchi: {msg.from_user.first_name} (@{msg.from_user.username or 'yoq'}) | ID: {msg.from_user.id}\n"
        f"Level: <b>{data['level']}</b>\n"
        f"Qurollar: <b>{data['weapons']} ta</b>\n"
        f"X-suit: <b>{data['suits']} ta</b>\n"
        f"RP: <b>{data['rp']}</b>\n"
        f"Mashina: <b>{data['vehicles']} ta</b>\n"
        f"Narx: <b>{data['price']} som</b>\n"
        f"Telefon: <b>{data['phone']}</b>"
    )
    kb = InlineKeyboardMarkup()
    kb.row(
        InlineKeyboardButton("Tasdiqlash", callback_data=f"acc_approve:{acc_id}"),
        InlineKeyboardButton("Rad etish",  callback_data=f"acc_reject:{acc_id}")
    )
    await notify_admins(caption, reply_markup=kb)
    for aid in ADMIN_IDS:
        try:
            await bot.send_video(aid, data["file_id"], caption=f"Video | Akkount #{acc_id}")
        except Exception:
            pass
    await msg.answer("Malumotlaringiz adminga yuborildi!\nTasdiqlangandan song kanalga joylashadi.", reply_markup=main_kb())


@dp.callback_query_handler(lambda c: c.data.startswith("acc_approve:"))
async def acc_approve(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("Ruxsat yoq!", show_alert=True)
        return
    acc_id = int(cb.data.split(":")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT * FROM accounts WHERE id=?", (acc_id,))
        row = await cur.fetchone()
    if not row:
        await cb.answer("Topilmadi!")
        return
    user_id, file_id, level, weapons, suits, rp, vehicles, price, phone = row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9]

    caption = (
        f"<b>PUBG Mobile Akkount Sotuvda!</b>\n\n"
        f"Level: <b>{level}</b>\n"
        f"Qurollar: <b>{weapons} ta</b>\n"
        f"X-suit: <b>{suits} ta</b>\n"
        f"RP: <b>{rp}</b>\n"
        f"Mashina: <b>{vehicles} ta</b>\n"
        f"Narx: <b>{price} som</b>\n"
        f"Telefon: <b>{phone}</b>"
    )
    contact_kb = InlineKeyboardMarkup()
    contact_kb.add(InlineKeyboardButton("Sotuvchi bilan boglanish", callback_data=f"contact_seller:{acc_id}:{user_id}"))
    try:
        sent = await bot.send_video(CHANNEL_ID, file_id, caption=caption, reply_markup=contact_kb)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE accounts SET status='approved', channel_msg=? WHERE id=?", (sent.message_id, acc_id))
            await db.commit()
        await cb.message.edit_text(cb.message.text + "\n\nTasdiqlandi va kanalga joylandi!")
        await bot.send_message(user_id, "Akkountingiz tasdiqlandi va kanalga joylandi!")
    except Exception as e:
        await cb.answer(f"Xato: {e}", show_alert=True)


@dp.callback_query_handler(lambda c: c.data.startswith("acc_reject:"))
async def acc_reject(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("Ruxsat yoq!", show_alert=True)
        return
    acc_id = int(cb.data.split(":")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id FROM accounts WHERE id=?", (acc_id,))
        row = await cur.fetchone()
        await db.execute("UPDATE accounts SET status='rejected' WHERE id=?", (acc_id,))
        await db.commit()
    if row:
        await bot.send_message(row[0], "Akkountingiz rad etildi.")
    await cb.message.edit_text(cb.message.text + "\n\nRad etildi.")


@dp.callback_query_handler(lambda c: c.data.startswith("contact_seller:"))
async def contact_seller(cb: types.CallbackQuery):
    parts     = cb.data.split(":")
    seller_id = int(parts[2])
    try:
        await bot.send_message(
            seller_id,
            f"<b>Kimdir akkountingizga qiziqdi!</b>\n\n"
            f"{cb.from_user.first_name} (@{cb.from_user.username or 'yoq'}) | ID: <code>{cb.from_user.id}</code>"
        )
        await cb.answer("Sotuvchiga xabar yuborildi!", show_alert=True)
    except Exception:
        await cb.answer("Sotuvchiga xabar yuborib bolmadi.", show_alert=True)


# ─── REKLAMA QO'YISH ──────────────────────────────────────────────────────────
@dp.message_handler(lambda m: m.text == "Reklama qoyish", state="*")
async def ad_start(msg: types.Message, state: FSMContext):
    not_subbed = await check_subscription(msg.from_user.id)
    if not_subbed:
        await msg.answer("Avval kanallarga obuna boling:", reply_markup=sub_keyboard(not_subbed))
        return
    ad_price = await get_setting("ad_price")
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("1-video BEPUL", callback_data="ad_free"))
    kb.add(InlineKeyboardButton(f"2-video va keyin PULIK ({ad_price} som)", callback_data="ad_paid"))
    await AdState.choose.set()
    await msg.answer(
        f"<b>Reklama qoyish</b>\n\n"
        f"Birinchi video — <b>BEPUL</b>\n"
        f"Ikkinchi va keyingi — <b>{ad_price} som</b>\n\nTanlang:",
        reply_markup=kb
    )

@dp.callback_query_handler(lambda c: c.data in ("ad_free", "ad_paid"), state=AdState.choose)
async def ad_type_chosen(cb: types.CallbackQuery, state: FSMContext):
    await state.update_data(ad_type=cb.data)
    if cb.data == "ad_paid":
        card     = await get_setting("card_number")
        ad_price = await get_setting("ad_price")
        await cb.message.edit_text(
            f"<b>Tolov malumotlari:</b>\n\n"
            f"Karta: <code>{card}</code>\n"
            f"Summa: <b>{ad_price} som</b>\n\n"
            "Tolovni amalga oshirib, chek (screenshot) yuboring:"
        )
        await AdState.pay_proof.set()
    else:
        await cb.message.edit_text("Reklama videosini yuboring:")
        await AdState.video.set()

@dp.message_handler(content_types=[types.ContentType.PHOTO, types.ContentType.DOCUMENT], state=AdState.pay_proof)
async def ad_pay_proof(msg: types.Message, state: FSMContext):
    file_id = msg.photo[-1].file_id if msg.photo else msg.document.file_id
    for aid in ADMIN_IDS:
        try:
            kb = InlineKeyboardMarkup()
            kb.row(
                InlineKeyboardButton("Tolovni tasdiqlash", callback_data=f"ad_payok:{msg.from_user.id}"),
                InlineKeyboardButton("Rad etish",          callback_data=f"ad_payno:{msg.from_user.id}")
            )
            await bot.send_photo(aid, file_id,
                caption=f"<b>Tolov cheki</b>\n{msg.from_user.first_name} (@{msg.from_user.username or 'yoq'})\nID: <code>{msg.from_user.id}</code>",
                reply_markup=kb)
        except Exception:
            pass
    await AdState.video.set()
    await msg.answer("Chek adminga yuborildi. Admin tasdiqlashini kuting.\nEndi reklama videosini yuboring:")

@dp.message_handler(content_types=types.ContentType.VIDEO, state=AdState.video)
async def ad_video(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    now  = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO ads(user_id,file_id,ad_type,created_at) VALUES(?,?,?,?)",
            (msg.from_user.id, msg.video.file_id, data.get("ad_type", "ad_free"), now)
        )
        ad_id = cur.lastrowid
        await db.commit()

    kb = InlineKeyboardMarkup()
    kb.row(
        InlineKeyboardButton("Kanalga joylash", callback_data=f"ad_approve:{ad_id}"),
        InlineKeyboardButton("Bekor qilish",    callback_data=f"ad_reject:{ad_id}")
    )
    await notify_admins(
        f"<b>Yangi reklama #{ad_id}</b>\n"
        f"{msg.from_user.first_name} | ID: {msg.from_user.id}\n"
        f"Tur: {'BEPUL' if data.get('ad_type') == 'ad_free' else 'PULIK'}",
        reply_markup=kb
    )
    for aid in ADMIN_IDS:
        try:
            await bot.send_video(aid, msg.video.file_id, caption=f"Reklama videosi #{ad_id}")
        except Exception:
            pass
    await state.finish()
    await msg.answer("Reklama adminga yuborildi!\nTasdiqlangandan song kanalga joylashadi.", reply_markup=main_kb())


@dp.callback_query_handler(lambda c: c.data.startswith("ad_approve:"))
async def ad_approve(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("Ruxsat yoq!", show_alert=True)
        return
    ad_id = int(cb.data.split(":")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id, file_id FROM ads WHERE id=?", (ad_id,))
        row = await cur.fetchone()
        await db.execute("UPDATE ads SET status='approved' WHERE id=?", (ad_id,))
        await db.commit()
    if row:
        try:
            await bot.send_video(CHANNEL_ID, row[1], caption="<b>Reklama</b>")
            await bot.send_message(row[0], "Reklamangiz tasdiqlandi va kanalga joylandi!")
        except Exception as e:
            await cb.answer(str(e), show_alert=True)
            return
    await cb.message.edit_text(cb.message.text + "\n\nTasdiqlandi!")

@dp.callback_query_handler(lambda c: c.data.startswith("ad_reject:"))
async def ad_reject(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("Ruxsat yoq!", show_alert=True)
        return
    ad_id = int(cb.data.split(":")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id FROM ads WHERE id=?", (ad_id,))
        row = await cur.fetchone()
        await db.execute("UPDATE ads SET status='rejected' WHERE id=?", (ad_id,))
        await db.commit()
    if row:
        await bot.send_message(row[0], "Reklamangiz rad etildi.")
    await cb.message.edit_text(cb.message.text + "\n\nRad etildi.")

@dp.callback_query_handler(lambda c: c.data.startswith("ad_payok:"))
async def ad_payok(cb: types.CallbackQuery):
    uid = int(cb.data.split(":")[1])
    await bot.send_message(uid, "Tolovingiz tasdiqlandi! Endi reklama videosini yuboring.")
    await cb.message.edit_text(cb.message.text + "\n\nTolov tasdiqlandi.")

@dp.callback_query_handler(lambda c: c.data.startswith("ad_payno:"))
async def ad_payno(cb: types.CallbackQuery):
    uid = int(cb.data.split(":")[1])
    await bot.send_message(uid, "Tolovingiz tasdiqlanmadi. Togri tolov qiling va qayta yuboring.")
    await cb.message.edit_text(cb.message.text + "\n\nTolov rad etildi.")


# ─── YORDAM ───────────────────────────────────────────────────────────────────
@dp.message_handler(lambda m: m.text == "Yordam", state="*")
async def help_start(msg: types.Message):
    await HelpState.message.set()
    await msg.answer("Savolingiz yoki muammoingizni yozing:", reply_markup=ReplyKeyboardRemove())

@dp.message_handler(state=HelpState.message)
async def help_msg(msg: types.Message, state: FSMContext):
    now  = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d %H:%M:%S")
    text = msg.text or "[Matn yoq]"
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO help_msgs(user_id,text,created_at) VALUES(?,?,?)",
            (msg.from_user.id, text, now)
        )
        hid = cur.lastrowid
        await db.commit()
    await state.finish()

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("Javob yozish", callback_data=f"help_reply:{hid}:{msg.from_user.id}"))
    await notify_admins(
        f"<b>Yordam sorovi #{hid}</b>\n"
        f"{msg.from_user.first_name} (@{msg.from_user.username or 'yoq'}) | ID: <code>{msg.from_user.id}</code>\n\n{text}",
        reply_markup=kb
    )
    await msg.answer("Xabaringiz adminga yuborildi! Tez orada javob berishadi.", reply_markup=main_kb())

@dp.callback_query_handler(lambda c: c.data.startswith("help_reply:"))
async def help_reply_cb(cb: types.CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        await cb.answer("Ruxsat yoq!", show_alert=True)
        return
    parts = cb.data.split(":")
    uid   = int(parts[2])
    await AdminReply.text.set()
    await state.update_data(target_uid=uid)
    await cb.message.answer(f"#{parts[1]} sorovi uchun javobingizni yozing:")
    await cb.answer()

@dp.message_handler(state=AdminReply.text)
async def admin_reply_send(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    await state.finish()
    try:
        await bot.send_message(data["target_uid"], f"<b>Admin javobi:</b>\n\n{msg.text}")
        await msg.answer("Javob foydalanuvchiga yuborildi!")
    except Exception as e:
        await msg.answer(f"Xato: {e}")


# ─── ADMIN PANEL ──────────────────────────────────────────────────────────────
@dp.message_handler(lambda m: m.text == "Statistika", state="*")
async def admin_stats(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return
    text = await make_stats_text()
    await msg.answer(text)

@dp.message_handler(lambda m: m.text == "Start xabar", state="*")
async def admin_set_start(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return
    cur_msg = await get_setting("start_message")
    await AdminState.set_start_msg.set()
    await msg.answer(f"Joriy start xabar:\n<i>{cur_msg}</i>\n\nYangi start xabarini kiriting:")

@dp.message_handler(state=AdminState.set_start_msg)
async def admin_start_msg_save(msg: types.Message, state: FSMContext):
    await set_setting("start_message", msg.text)
    await state.finish()
    await msg.answer("Start xabar yangilandi!", reply_markup=admin_kb())

@dp.message_handler(lambda m: m.text == "Reklama narxi", state="*")
async def admin_set_price(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return
    cur_price = await get_setting("ad_price")
    await AdminState.set_ad_price.set()
    await msg.answer(f"Joriy narx: <b>{cur_price} som</b>\n\nYangi narxni kiriting (faqat raqam):")

@dp.message_handler(state=AdminState.set_ad_price)
async def admin_price_save(msg: types.Message, state: FSMContext):
    if not msg.text.strip().isdigit():
        await msg.answer("Faqat raqam kiriting!")
        return
    await set_setting("ad_price", msg.text.strip())
    await state.finish()
    await msg.answer(f"Reklama narxi <b>{msg.text} som</b>ga ozgartirildi!", reply_markup=admin_kb())

@dp.message_handler(lambda m: m.text == "Karta raqam", state="*")
async def admin_set_card(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return
    cur_card = await get_setting("card_number")
    await AdminState.set_card.set()
    await msg.answer(f"Joriy karta: <code>{cur_card}</code>\n\nYangi karta raqamini kiriting:")

@dp.message_handler(state=AdminState.set_card)
async def admin_card_save(msg: types.Message, state: FSMContext):
    await set_setting("card_number", msg.text.strip())
    await state.finish()
    await msg.answer("Karta raqami yangilandi!", reply_markup=admin_kb())

@dp.message_handler(lambda m: m.text == "Kanal qoshish", state="*")
async def admin_add_ch(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return
    await AdminState.add_channel.set()
    await msg.answer("Majburiy obuna kanalini kiriting.\nFormat: <code>@kanal_username</code>\n\nBot kanalda admin bolishi kerak!")

@dp.message_handler(state=AdminState.add_channel)
async def admin_add_ch_save(msg: types.Message, state: FSMContext):
    ch = msg.text.strip()
    if not ch.startswith("@"):
        await msg.answer("Kanal @ bilan boshlanishi kerak!")
        return
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("INSERT INTO mandatory_channels(channel) VALUES(?)", (ch,))
            await db.commit()
            await msg.answer(f"{ch} kanali qoshildi!", reply_markup=admin_kb())
        except Exception:
            await msg.answer("Bu kanal allaqachon mavjud!", reply_markup=admin_kb())
    await state.finish()

@dp.message_handler(lambda m: m.text == "Kanal ochirish", state="*")
async def admin_del_ch(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return
    channels = await get_mandatory_channels()
    if not channels:
        await msg.answer("Hech qanday majburiy obuna kanali yoq.")
        return
    kb = InlineKeyboardMarkup()
    for ch in channels:
        kb.add(InlineKeyboardButton(f"Ochirish: {ch}", callback_data=f"delch:{ch}"))
    await msg.answer("Ochirmoqchi bolgan kanalni tanlang:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("delch:"))
async def delch_cb(cb: types.CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("Ruxsat yoq!", show_alert=True)
        return
    ch = cb.data.split(":", 1)[1]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM mandatory_channels WHERE channel=?", (ch,))
        await db.commit()
    await cb.message.edit_text(f"{ch} majburiy obunadan ochirildi.")

@dp.message_handler(lambda m: m.text == "Kanallar royxati", state="*")
async def admin_list_ch(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return
    channels = await get_mandatory_channels()
    if not channels:
        await msg.answer("Hech qanday majburiy obuna kanali yoq.")
    else:
        text = "<b>Majburiy obuna kanallari:</b>\n\n" + "\n".join(f"- {ch}" for ch in channels)
        await msg.answer(text)


# ─── ISHGA TUSHIRISH ──────────────────────────────────────────────────────────
async def on_startup(dp):
    await db_init()
    log.info("Bot ishga tushdi!")

if __name__ == "__main__":
    executor.start_polling(dp, on_startup=on_startup, skip_updates=True)
