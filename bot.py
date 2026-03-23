import asyncio
import sqlite3
import logging
from datetime import datetime
import pytz
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    BufferedInputFile, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton,
    WebAppInfo
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import CommandStart, Command

# ================== SOZLAMALAR ==================
BOT_TOKEN = "8632541339:AAHltUEVgFkRxjYmzfJBuORXqb_D21zptlc"
ADMIN_ID = 8632541339
MAIN_CHANNEL_ID = "@Azizbekl2026"
# ================================================

DB_NAME = "bot_data.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users 
                     (user_id INTEGER PRIMARY KEY, full_name TEXT, username TEXT, join_date TEXT,
                      posted_ads INTEGER DEFAULT 0, paid_slots INTEGER DEFAULT 0, pending_approval INTEGER DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS channels (id INTEGER PRIMARY KEY AUTOINCREMENT, channel_id TEXT, url TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS ads (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, video_id TEXT, text TEXT, status TEXT DEFAULT 'pending')''')
        c.execute('''CREATE TABLE IF NOT EXISTS uc_prices (id INTEGER PRIMARY KEY AUTOINCREMENT, uc_amount INTEGER, price INTEGER, position INTEGER DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS uc_orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, full_name TEXT, username TEXT, uc_amount INTEGER, price INTEGER, pubg_id TEXT, screenshot_id TEXT, status TEXT DEFAULT 'pending', order_date TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS stars_prices (id INTEGER PRIMARY KEY AUTOINCREMENT, stars_amount INTEGER, price INTEGER, position INTEGER DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS stars_orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, full_name TEXT, username TEXT, stars_amount INTEGER, price INTEGER, target_type TEXT, target_username TEXT, receipt_id TEXT, status TEXT DEFAULT 'pending', order_date TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS premium_prices (id INTEGER PRIMARY KEY AUTOINCREMENT, duration TEXT, price INTEGER, position INTEGER DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS premium_orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, full_name TEXT, username TEXT, duration TEXT, price INTEGER, target_username TEXT, receipt_id TEXT, status TEXT DEFAULT 'pending', order_date TEXT)''')

        # Alohida kartalar va sozlamalar
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('price', '50000')")
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('card_ad', '8600 0000 0000 0000 (Ism Familiya)')")
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('card_uc', '8600 0000 0000 0000 (Ism Familiya)')")
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('card_stars', '8600 0000 0000 0000 (Ism Familiya)')")
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('card_premium', '8600 0000 0000 0000 (Ism Familiya)')")
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('start_msg', 'Salom {name}! Siz bu botdan PUBG Mobile akkauntingizni obzorini joylashingiz mumkin.')")
        conn.commit()

def db_query(query, params=(), fetchone=False, fetchall=False):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute(query, params)
        if fetchone: return c.fetchone()
        if fetchall: return c.fetchall()
        conn.commit()
        return c.lastrowid

init_db()

# ================== FSM HOLATLAR ==================
class AdForm(StatesGroup):
    video = State(); level = State(); guns = State(); xsuits = State()
    rp = State(); cars = State(); price = State(); phone = State()

class AdminForm(StatesGroup):
    start_msg = State(); price = State()
    card_ad = State(); card_uc = State(); card_stars = State(); card_premium = State()
    add_channel_id = State(); add_channel_url = State(); reply_msg = State()
    uc_p_amount = State(); uc_p_value = State()
    stars_p_amount = State(); stars_p_value = State()
    prem_p_dur = State(); prem_p_value = State()

class UCOrderForm(StatesGroup): pubg_screenshot = State(); receipt = State()
class StarsOrderForm(StatesGroup): choose_target = State(); friend_username = State(); receipt = State()
class PremiumOrderForm(StatesGroup): target_username = State(); receipt = State()
class PaymentForm(StatesGroup): receipt = State()
class SupportForm(StatesGroup): msg = State()

# ================== YORDAMCHI FUNKSIYALAR ==================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()

def get_time_tashkent():
    return datetime.now(pytz.timezone('Asia/Tashkent')).strftime('%Y-%m-%d %H:%M:%S')

def get_setting(key):
    res = db_query("SELECT value FROM settings WHERE key=?", (key,), fetchone=True)
    return res[0] if res else ""

async def check_subscription(user_id):
    channels = db_query("SELECT channel_id, url FROM channels", fetchall=True)
    unsubbed = []
    for ch_id, url in channels:
        try:
            member = await bot.get_chat_member(ch_id, user_id)
            if member.status in ['left', 'kicked']: unsubbed.append(url)
        except: pass
    return unsubbed

def get_main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📝 E'lon berish"), KeyboardButton(text="🆘 Yordam")],
        [KeyboardButton(text="🎮 PUBG MOBILE UC OLISH 💎")],
        [KeyboardButton(text="⭐ TELEGRAM PREMIUM"), KeyboardButton(text="🌟 STARS OLISH")]
    ], resize_keyboard=True, is_persistent=True)

# ================== KLAVIATURALAR ==================
def get_uc_prices_keyboard(page=0):
    prices = db_query("SELECT id, uc_amount, price FROM uc_prices ORDER BY uc_amount ASC", fetchall=True)
    if not prices: return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Narxlar kiritilmagan", callback_data="none")]])
    rows = [[InlineKeyboardButton(text=f"💎 {p[1]} UC — {p[2]:,} so'm", callback_data=f"buy_uc_{p[0]}_{p[1]}_{p[2]}")] for p in prices]
    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="uc_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_stars_prices_keyboard(page=0):
    prices = db_query("SELECT id, stars_amount, price FROM stars_prices ORDER BY stars_amount ASC", fetchall=True)
    if not prices: return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Narxlar kiritilmagan", callback_data="none")]])
    rows = [[InlineKeyboardButton(text=f"⭐ {p[1]} Stars — {p[2]:,} so'm", callback_data=f"buy_stars_{p[0]}_{p[1]}_{p[2]}")] for p in prices]
    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="stars_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_premium_prices_keyboard(page=0):
    prices = db_query("SELECT id, duration, price FROM premium_prices ORDER BY price ASC", fetchall=True)
    if not prices: return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Narxlar kiritilmagan", callback_data="none")]])
    rows = [[InlineKeyboardButton(text=f"⭐ {p[1]} — {p[2]:,} so'm", callback_data=f"buy_premium_{p[0]}_{p[2]}")] for p in prices]
    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="premium_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ================== START VA E'LON (RAQAM+HARF) ==================
@router.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext):
    await state.clear()
    user = db_query("SELECT user_id FROM users WHERE user_id=?", (message.from_user.id,), fetchone=True)
    if not user:
        db_query("INSERT INTO users (user_id, full_name, username, join_date) VALUES (?, ?, ?, ?)",
                 (message.from_user.id, message.from_user.full_name, message.from_user.username, get_time_tashkent()))
    unsub = await check_subscription(message.from_user.id)
    if unsub:
        btn = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Obuna bo'lish", url=u)] for u in unsub] + [[InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="check_sub")]])
        await message.answer("Botdan foydalanish uchun kanallarga obuna bo'ling:", reply_markup=btn)
        return
    txt = get_setting('start_msg').replace("{name}", message.from_user.full_name)
    await message.answer(txt, reply_markup=get_main_menu())

@router.callback_query(F.data == "check_sub")
async def check_sub_cb(call: CallbackQuery):
    unsub = await check_subscription(call.from_user.id)
    if unsub: await call.answer("Obuna bo'lmadingiz!", show_alert=True)
    else: await call.message.delete(); await call.message.answer("Xush kelibsiz!", reply_markup=get_main_menu())

@router.message(F.text == "📝 E'lon berish")
async def ad_start(message: Message, state: FSMContext):
    u = db_query("SELECT posted_ads, paid_slots, pending_approval FROM users WHERE user_id=?", (message.from_user.id,), fetchone=True)
    if u[2]: return await message.answer("Oldingi e'loningiz tekshirilmoqda.")
    if u[0] >= (1 + u[1]):
        pr = get_setting('price'); card = get_setting('card_ad')
        await message.answer(f"Limit tugadi. E'lon: {pr} so'm.\n💳 Karta: `{card}`\nChekni yuboring:", parse_mode="Markdown")
        await state.set_state(PaymentForm.receipt); return
    await message.answer("Akkaunt obzori videosini yuboring:"); await state.set_state(AdForm.video)

@router.message(AdForm.video, F.video)
async def get_video(message: Message, state: FSMContext):
    await state.update_data(video=message.video.file_id)
    await message.answer("Akkaunt levelini (darajasini) kiriting:"); await state.set_state(AdForm.level)

@router.message(AdForm.level)
async def get_level(message: Message, state: FSMContext):
    await state.update_data(level=message.text)
    await message.answer("Qurollar (Upgradable) haqida ma'lumot:"); await state.set_state(AdForm.guns)

@router.message(AdForm.guns)
async def get_guns(message: Message, state: FSMContext):
    await state.update_data(guns=message.text)
    await message.answer("X-suitlar haqida ma'lumot:"); await state.set_state(AdForm.xsuits)

@router.message(AdForm.xsuits)
async def get_xsuits(message: Message, state: FSMContext):
    await state.update_data(xsuits=message.text)
    await message.answer("RP haqida ma'lumot:"); await state.set_state(AdForm.rp)

@router.message(AdForm.rp)
async def get_rp(message: Message, state: FSMContext):
    await state.update_data(rp=message.text)
    await message.answer("Mashina skinlari:"); await state.set_state(AdForm.cars)

@router.message(AdForm.cars)
async def get_cars(message: Message, state: FSMContext):
    await state.update_data(cars=message.text)
    await message.answer("Narxni kiriting:"); await state.set_state(AdForm.price)

@router.message(AdForm.price)
async def get_price(message: Message, state: FSMContext):
    await state.update_data(price=message.text)
    await message.answer("Telefon raqam:"); await state.set_state(AdForm.phone)

@router.message(AdForm.phone)
async def get_phone(message: Message, state: FSMContext):
    d = await state.get_data(); me = await bot.get_me()
    txt = (f"🎮 Yangi Akkaunt Sotuvda!\n\n📊 Level: {d['level']}\n🔫 Qurollar: {d['guns']}\n🥋 X-Suit: {d['xsuits']}\n"
            f"🎟 RP: {d['rp']}\n🚗 Mashinalar: {d['cars']}\n💰 Narxi: {d['price']}\n📞 Tel: {message.text}")
    ad_id = db_query("INSERT INTO ads (user_id, video_id, text) VALUES (?, ?, ?)", (message.from_user.id, d['video'], txt))
    db_query("UPDATE users SET pending_approval=1 WHERE user_id=?", (message.from_user.id,))
    btn = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"app_ad_{ad_id}"), InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"rej_ad_{ad_id}")]])
    await bot.send_video(ADMIN_ID, video=d['video'], caption=f"🎯 Yangi e'lon:\n\n{txt}", reply_markup=btn)
    await message.answer("E'lon adminga yuborildi.", reply_markup=get_main_menu()); await state.clear()

# ================== UC & PREMIUM & STARS (ALOHIDA KARTALAR) ==================
@router.message(F.text == "🎮 PUBG MOBILE UC OLISH 💎")
async def uc_menu(message: Message): await message.answer("💎 UC miqdorini tanlang:", reply_markup=get_uc_prices_keyboard())

@router.callback_query(F.data.startswith("buy_uc_"))
async def uc_buy(call: CallbackQuery, state: FSMContext):
    p, amt, pr = call.data.split("_")[2:]
    await state.update_data(uc_amt=amt, uc_price=pr); await call.message.edit_text("🎮 PUBG ID raqamingizni kiriting:")
    await state.set_state(UCOrderForm.pubg_screenshot)

@router.message(UCOrderForm.pubg_screenshot)
async def uc_id_rec(message: Message, state: FSMContext):
    await state.update_data(pubg_id=message.text); card = get_setting('card_uc'); d = await state.get_data()
    await message.answer(f"💰 Summa: {d['uc_price']} so'm\n💳 Karta: `{card}`\nChekni yuboring:", parse_mode="Markdown")
    await state.set_state(UCOrderForm.receipt)

@router.message(F.text == "⭐ TELEGRAM PREMIUM")
async def prem_menu(message: Message): await message.answer("🚀 Premium muddatini tanlang:", reply_markup=get_premium_prices_keyboard())

@router.callback_query(F.data.startswith("buy_premium_"))
async def prem_buy(call: CallbackQuery, state: FSMContext):
    pid, pr = call.data.split("_")[2:]
    res = db_query("SELECT duration FROM premium_prices WHERE id=?", (pid,), fetchone=True)
    await state.update_data(dur=res[0], price=pr)
    await call.message.edit_text("Premium tushirilsinchi profil username'ini yuboring:\n\nMasalan: @username")
    await state.set_state(PremiumOrderForm.target_username)

@router.message(PremiumOrderForm.target_username)
async def prem_un(message: Message, state: FSMContext):
    u = message.text.strip().lstrip("@"); card = get_setting('card_premium'); d = await state.get_data()
    await message.answer(f"🚀 Premium: {d['dur']}\n👤 Profil: @{u}\n💰 Summa: {d['price']} so'm\n💳 Karta: `{card}`\n\nChekni yuboring:", parse_mode="Markdown")
    await state.set_state(PremiumOrderForm.receipt)

@router.message(F.text == "🌟 STARS OLISH")
async def stars_menu(message: Message): await message.answer("🌟 Stars miqdorini tanlang:", reply_markup=get_stars_prices_keyboard())

@router.callback_query(F.data.startswith("buy_stars_"))
async def stars_buy(call: CallbackQuery, state: FSMContext):
    p, amt, pr = call.data.split("_")[2:]
    await state.update_data(st_amt=amt, st_price=pr); await call.message.edit_text("🌟 Stars tushirilsinchi profil username'ini yuboring:")
    await state.set_state(StarsOrderForm.friend_username)

@router.message(StarsOrderForm.friend_username)
async def stars_un(message: Message, state: FSMContext):
    u = message.text.strip().lstrip("@"); card = get_setting('card_stars'); d = await state.get_data()
    await message.answer(f"🌟 {d['st_amt']} Stars\n👤 Profil: @{u}\n💰 Summa: {d['st_price']} so'm\n💳 Karta: `{card}`\n\nChekni yuboring:", parse_mode="Markdown")
    await state.set_state(StarsOrderForm.receipt)

# ================== ADMIN PANEL (CHIROYLI TARTIB) ==================
@router.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def admin_panel(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 UC SOZLAMALARI", callback_data="adm_uc"), InlineKeyboardButton(text="💜 PREMIUM SOZLAMALARI", callback_data="adm_prem")],
        [InlineKeyboardButton(text="🌟 STARS SOZLAMALARI", callback_data="adm_stars"), InlineKeyboardButton(text="📝 E'LON SOZLAMALARI", callback_data="adm_ad")],
        [InlineKeyboardButton(text="📊 STATISTIKA (RASMLI)", callback_data="admin_stats"), InlineKeyboardButton(text="📢 KANALLAR", callback_data="adm_chs")],
        [InlineKeyboardButton(text="⚙️ START XABARI", callback_data="adm_startmsg")]
    ])
    await message.answer("⚙️ **ADMIN PANEL**\nKerakli bo'limni tanlang:", reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("adm_"))
async def adm_sections(call: CallbackQuery):
    sect = call.data.split("_")[1]
    if sect == "uc":
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➕ Narx qo'shish", callback_data="add_uc_p"), InlineKeyboardButton(text="🗑 O'chirish", callback_data="list_uc")],[InlineKeyboardButton(text="💳 UC Kartasini sozlash", callback_data="set_card_uc")],[InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_admin")]])
        await call.message.edit_text("💎 **UC Bo'limi:**", reply_markup=kb)
    elif sect == "prem":
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➕ Muddat qo'shish", callback_data="add_pr_p"), InlineKeyboardButton(text="🗑 O'chirish", callback_data="list_prem")],[InlineKeyboardButton(text="💳 Premium Kartasini sozlash", callback_data="set_card_prem")],[InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_admin")]])
        await call.message.edit_text("🚀 **Premium Bo'limi:**", reply_markup=kb)
    elif sect == "stars":
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➕ Stars qo'shish", callback_data="add_st_p"), InlineKeyboardButton(text="🗑 O'chirish", callback_data="list_st")],[InlineKeyboardButton(text="💳 Stars Kartasini sozlash", callback_data="set_card_stars")],[InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_admin")]])
        await call.message.edit_text("🌟 **Stars Bo'limi:**", reply_markup=kb)
    elif sect == "ad":
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💰 Narxni o'zgartirish", callback_data="set_ad_price")],[InlineKeyboardButton(text="💳 Karta sozlash", callback_data="set_card_ad")],[InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_admin")]])
        await call.message.edit_text("📝 **E'lon Bo'limi:**", reply_markup=kb)

# ================== CARD SETTERS ==================
@router.callback_query(F.data.startswith("set_card_"))
async def set_card_start(call: CallbackQuery, state: FSMContext):
    ctype = call.data.split("_")[2]
    await state.update_data(ctype=ctype); await call.message.answer(f"Yangi {ctype.upper()} karta raqamini yuboring:")
    if ctype == 'uc': await state.set_state(AdminForm.card_uc)
    elif ctype == 'prem': await state.set_state(AdminForm.card_premium)
    elif ctype == 'stars': await state.set_state(AdminForm.card_stars)
    elif ctype == 'ad': await state.set_state(AdminForm.card_ad)

@router.message(AdminForm.card_uc)
async def sc_uc(message: Message, state: FSMContext): db_query("UPDATE settings SET value=? WHERE key='card_uc'", (message.text,)); await message.answer("Saqlandi!"); await state.clear()
@router.message(AdminForm.card_premium)
async def sc_pr(message: Message, state: FSMContext): db_query("UPDATE settings SET value=? WHERE key='card_premium'", (message.text,)); await message.answer("Saqlandi!"); await state.clear()
@router.message(AdminForm.card_stars)
async def sc_st(message: Message, state: FSMContext): db_query("UPDATE settings SET value=? WHERE key='card_stars'", (message.text,)); await message.answer("Saqlandi!"); await state.clear()
@router.message(AdminForm.card_ad)
async def sc_ad(message: Message, state: FSMContext): db_query("UPDATE settings SET value=? WHERE key='card_ad'", (message.text,)); await message.answer("Saqlandi!"); await state.clear()

# ================== STATISTIKA RASMI ==================
def generate_stats_image():
    users = db_query("SELECT user_id, full_name, join_date, posted_ads FROM users ORDER BY posted_ads DESC", fetchall=True)
    img_height = 240 + (len(users[:25]) * 35)
    img = Image.new('RGB', (900, img_height), color=(25, 25, 35)); d = ImageDraw.Draw(img)
    try: f_t = ImageFont.truetype("arial.ttf", 24); f_s = ImageFont.truetype("arial.ttf", 16)
    except: f_t = ImageFont.load_default(); f_s = ImageFont.load_default()
    d.text((30, 20), "📊 BOT STATISTIKASI", fill=(255, 215, 0), font=f_t)
    d.text((30, 60), f"Umumiy a'zolar: {len(users)} ta", fill=(255, 255, 255), font=f_s)
    d.line([(30, 185), (870, 185)], fill=(100, 100, 100), width=2)
    y = 200
    for u in users[:25]:
        d.text((30, y), f"{u[0]} | {u[1][:30]} | {u[2]} | {u[3]} e'lon", fill=(255, 255, 255), font=f_s); y += 35
    bio = BytesIO(); img.save(bio, 'PNG'); bio.seek(0); return bio

@router.callback_query(F.data == "admin_stats")
async def send_stats_img(call: CallbackQuery):
    await call.message.answer("Tayyorlanmoqda..."); b = generate_stats_image()
    await bot.send_photo(call.from_user.id, photo=BufferedInputFile(b.read(), filename="stats.png"))

@router.callback_query(F.data == "back_admin")
async def back_adm(call: CallbackQuery): await admin_panel(call.message)

# ================== ASOSIY ISHGA TUSHIRISH ==================
async def main():
    dp.include_router(router); print("Bot ishga tushdi..."); await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO); asyncio.run(main())
