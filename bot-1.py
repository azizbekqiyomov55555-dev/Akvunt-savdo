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
    BufferedInputFile, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import CommandStart, Command

# ================== SOZLAMALAR ==================
BOT_TOKEN = "8775591302:AAFiY_Bb98lgvZCvGnNpSgbUOlbIFHooZe8"
ADMIN_ID = 8537782289
MAIN_CHANNEL_ID = "@Azizbekl2026"
# ================================================

# ================== BAZA SOZLAMALARI ==================
DB_NAME = "bot_data.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users 
                     (user_id INTEGER PRIMARY KEY, full_name TEXT, username TEXT, join_date TEXT,
                      posted_ads INTEGER DEFAULT 0, paid_slots INTEGER DEFAULT 0, pending_approval INTEGER DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS settings 
                     (key TEXT PRIMARY KEY, value TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS channels 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, channel_id TEXT, url TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS ads 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, video_id TEXT, text TEXT, status TEXT DEFAULT 'pending')''')

        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('price', '50000')")
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('card', '8600 0000 0000 0000 (Ism Familiya)')")
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('start_msg', 'Salom {name}! Siz bu botdan PUBG Mobile akkauntingizni obzorini joylashingiz mumkin va u video kanalga joylanadi.')")
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
    video = State()
    level = State()
    guns = State()
    xsuits = State()
    rp = State()
    cars = State()
    price = State()
    phone = State()

class PaymentForm(StatesGroup):
    receipt = State()

class SupportForm(StatesGroup):
    msg = State()

class AdminForm(StatesGroup):
    start_msg = State()
    price = State()
    card = State()
    add_channel_id = State()
    add_channel_url = State()
    reply_msg = State()

# ================== BOT VA ROUTER ==================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()

# ================== YORDAMCHI FUNKSIYALAR ==================
def get_time_tashkent():
    tz = pytz.timezone('Asia/Tashkent')
    return datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')

def get_setting(key):
    res = db_query("SELECT value FROM settings WHERE key=?", (key,), fetchone=True)
    return res[0] if res else ""

async def check_subscription(user_id):
    channels = db_query("SELECT channel_id, url FROM channels", fetchall=True)
    unsubbed = []
    for ch_id, url in channels:
        try:
            member = await bot.get_chat_member(ch_id, user_id)
            if member.status in ['left', 'kicked']:
                unsubbed.append(url)
        except:
            pass
    return unsubbed

# ================== ASOSIY MENU — RANGLI REPLYKEYBOARD ==================
def get_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[[
            KeyboardButton(text="📝 E'lon berish", style="primary"),   # Ko'k
            KeyboardButton(text="🆘 Yordam", style="danger"),           # Qizil
        ]],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Quyidagi tugmalardan birini tanlang 👇"
    )

# ================== START VA OBUNA ==================
@router.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext):
    await state.clear()
    user = db_query("SELECT user_id FROM users WHERE user_id=?", (message.from_user.id,), fetchone=True)
    if not user:
        db_query("INSERT INTO users (user_id, full_name, username, join_date) VALUES (?, ?, ?, ?)",
                 (message.from_user.id, message.from_user.full_name, message.from_user.username, get_time_tashkent()))

    unsubbed = await check_subscription(message.from_user.id)
    if unsubbed:
        # Kanal tugmalari — PRIMARY (ko'k)
        btn = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"Kanal {i+1} — Obuna bo'lish", url=url, style="primary")]
            for i, url in enumerate(unsubbed)
        ] + [[InlineKeyboardButton(text="Tasdiqlash", callback_data="check_sub", style="success")]])
        await message.answer("Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:", reply_markup=btn)
        return

    start_text = get_setting('start_msg').replace("{name}", message.from_user.full_name)
    await message.answer(start_text, reply_markup=get_main_menu())

@router.callback_query(F.data == "check_sub")
async def check_sub_cb(call: CallbackQuery):
    unsubbed = await check_subscription(call.from_user.id)
    if unsubbed:
        await call.answer("Hali hamma kanallarga obuna bo'lmadingiz!", show_alert=True)
    else:
        await call.message.delete()
        start_text = get_setting('start_msg').replace("{name}", call.from_user.full_name)
        await call.message.answer(f"Rahmat! Obuna tasdiqlandi.\n\n{start_text}", reply_markup=get_main_menu())

# ================== MENU HANDLERLAR ==================
@router.message(F.text == "📝 E'lon berish")
async def menu_ad_cb(message: Message, state: FSMContext):
    unsubbed = await check_subscription(message.from_user.id)
    if unsubbed:
        await message.answer("Iltimos, oldin kanallarga obuna bo'ling. /start ni bosing.")
        return

    user = db_query("SELECT posted_ads, paid_slots, pending_approval FROM users WHERE user_id=?", (message.from_user.id,), fetchone=True)
    posted, paid, pending = user[0], user[1], (user[2] if len(user) > 2 else 0)

    if pending:
        await message.answer(
            "⏳ Sizning oldingi e'loningiz admin tomonidan ko'rib chiqilmoqda.\n"
            "Admin tasdiqlaganidan so'ng yangi e'lon berishingiz mumkin."
        )
        return

    if posted >= (1 + paid):
        price = get_setting('price')
        btn = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="💳 To'lov qilish", callback_data="pay_ad", style="primary")
        ]])
        await message.answer(
            f"Sizning bepul e'lonlar limitingiz tugagan.\n"
            f"1-video bepul, 2-sidan boshlab pullik.\n"
            f"E'lon narxi: {price} so'm.", reply_markup=btn)
        return

    await message.answer("E'loningizni boshlaymiz.\nIltimos, akkaunt obzori videosini yuboring:")
    await state.set_state(AdForm.video)

@router.message(F.text == "🆘 Yordam")
async def menu_help_cb(message: Message, state: FSMContext):
    await message.answer("Adminga xabaringizni yozib qoldiring:")
    await state.set_state(SupportForm.msg)

# ================== TO'LOV ==================
@router.callback_query(F.data == "pay_ad")
async def pay_ad_cb(call: CallbackQuery, state: FSMContext):
    card = get_setting('card')
    price = get_setting('price')
    await call.message.edit_text(
        f"💳 To'lov uchun karta raqam:\n\n`{card}`\nSumma: {price} so'm\n\n"
        f"To'lov qilgach, chekni rasm (skrinshot) qilib yuboring.",
        parse_mode="Markdown")
    await state.set_state(PaymentForm.receipt)

@router.message(PaymentForm.receipt, F.photo)
async def get_receipt(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    # Admin uchun: Tasdiqlash — SUCCESS (yashil) | Bekor — DANGER (qizil)
    btn = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"app_pay_{message.from_user.id}", style="success"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"rej_pay_{message.from_user.id}", style="danger")
    ]])
    await bot.send_photo(ADMIN_ID, photo_id,
        caption=f"💰 Yangi to'lov cheki.\n"
                f"Foydalanuvchi: {message.from_user.full_name} (@{message.from_user.username})\n"
                f"ID: {message.from_user.id}",
        reply_markup=btn)
    await message.answer("Chek adminga yuborildi. Tasdiqlanishini kuting.", reply_markup=get_main_menu())
    await state.clear()

# ================== E'LON BERISH BOSQICHLARI ==================
@router.message(AdForm.video, F.video)
async def get_video(message: Message, state: FSMContext):
    await state.update_data(video=message.video.file_id)
    await message.answer("Akkaunt levelini (darajasini) kiriting:")
    await state.set_state(AdForm.level)

@router.message(AdForm.level)
async def get_level(message: Message, state: FSMContext):
    await state.update_data(level=message.text)
    await message.answer("Nechta qurol (upgradable) bor? Faqat raqamda kiriting:")
    await state.set_state(AdForm.guns)

@router.message(AdForm.guns, F.text.regexp(r'^\d+$'))
async def get_guns(message: Message, state: FSMContext):
    await state.update_data(guns=message.text)
    await message.answer("Nechta X-suit bor? Raqamda kiriting:")
    await state.set_state(AdForm.xsuits)

@router.message(AdForm.xsuits, F.text.regexp(r'^\d+$'))
async def get_xsuits(message: Message, state: FSMContext):
    await state.update_data(xsuits=message.text)
    await message.answer("Nechta RP olingan? Raqamda kiriting:")
    await state.set_state(AdForm.rp)

@router.message(AdForm.rp, F.text.regexp(r'^\d+$'))
async def get_rp(message: Message, state: FSMContext):
    await state.update_data(rp=message.text)
    await message.answer("Nechta mashina (skin) bor? Raqamda kiriting:")
    await state.set_state(AdForm.cars)

@router.message(AdForm.cars, F.text.regexp(r'^\d+$'))
async def get_cars(message: Message, state: FSMContext):
    await state.update_data(cars=message.text)
    await message.answer("Narxini so'mda kiriting (masalan: 150000):")
    await state.set_state(AdForm.price)

@router.message(AdForm.price)
async def get_price(message: Message, state: FSMContext):
    await state.update_data(price=message.text)
    await message.answer("Murojaat uchun telefon raqamingizni kiriting:")
    await state.set_state(AdForm.phone)

@router.message(AdForm.phone)
async def get_phone(message: Message, state: FSMContext):
    data = await state.get_data()
    me = await bot.get_me()

    text = (f"🎮 Yangi Akkaunt Sotuvda!\n\n"
            f"📊 Level: {data['level']}\n"
            f"🔫 Qurollar: {data['guns']} ta\n"
            f"🥋 X-Suit: {data['xsuits']} ta\n"
            f"🎟 RP: {data['rp']} ta\n"
            f"🚗 Mashinalar: {data['cars']} ta\n"
            f"💰 Narxi: {data['price']} so'm\n"
            f"📞 Tel: {message.text}\n\n"
            f"➖➖➖➖➖➖➖➖➖➖\n"
            f"👨‍💻 Admin: @SHIRINA_10K\n"
            f"🤖 Botimiz: @{me.username}")

    ad_id = db_query("INSERT INTO ads (user_id, video_id, text) VALUES (?, ?, ?)",
                     (message.from_user.id, data['video'], text))
    db_query("UPDATE users SET pending_approval=1 WHERE user_id=?", (message.from_user.id,))

    # Admin uchun: Tasdiqlash — SUCCESS (yashil) | Bekor — DANGER (qizil)
    btn = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"app_ad_{ad_id}", style="success"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"rej_ad_{ad_id}", style="danger")
    ]])

    await bot.send_video(ADMIN_ID, video=data['video'],
        caption=text + f"\n\n👤 Sotuvchi: {message.from_user.full_name} (ID: {message.from_user.id})",
        reply_markup=btn)
    await message.answer(
        "Ma'lumotlaringiz adminga yuborildi. Tasdiqlanganidan so'ng kanalga joylanadi.",
        reply_markup=get_main_menu())
    await state.clear()

# ================== YORDAM (SUPPORT) ==================
@router.message(SupportForm.msg)
async def send_support(message: Message, state: FSMContext):
    # Javob yozish — PRIMARY (ko'k)
    btn = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="↩️ Javob yozish", callback_data=f"reply_{message.from_user.id}", style="primary")
    ]])
    await bot.send_message(ADMIN_ID,
        f"📩 Yangi xabar!\n"
        f"Kimdan: {message.from_user.full_name} (ID: {message.from_user.id})\n\n"
        f"Xabar: {message.text}",
        reply_markup=btn)
    await message.answer("Xabaringiz adminga yetkazildi.", reply_markup=get_main_menu())
    await state.clear()

# ================== ADMIN TO'LOV CALLBACKLAR ==================
@router.callback_query(F.data.startswith("app_pay_"))
async def approve_pay(call: CallbackQuery):
    user_id = int(call.data.split("_")[2])
    db_query("UPDATE users SET paid_slots = paid_slots + 1 WHERE user_id=?", (user_id,))
    await bot.send_message(user_id,
        "✅ To'lovingiz admin tomonidan tasdiqlandi!\n"
        "Endi yana e'lon joylashingiz mumkin.",
        reply_markup=get_main_menu())
    await call.message.edit_caption(caption=call.message.caption + "\n\n✅ TASDIQLANGAN")

@router.callback_query(F.data.startswith("rej_pay_"))
async def reject_pay(call: CallbackQuery):
    user_id = int(call.data.split("_")[2])
    await bot.send_message(user_id, "❌ To'lovingiz admin tomonidan bekor qilindi.", reply_markup=get_main_menu())
    await call.message.edit_caption(caption=call.message.caption + "\n\n❌ BEKOR QILINGAN")

# ================== ADMIN E'LON CALLBACKLAR ==================
@router.callback_query(F.data.startswith("app_ad_"))
async def approve_ad(call: CallbackQuery):
    ad_id = int(call.data.split("_")[2])
    ad = db_query("SELECT user_id, video_id, text FROM ads WHERE id=?", (ad_id,), fetchone=True)
    if ad:
        user_id, video_id, text = ad
        me = await bot.get_me()

        # Kanalga joylanadigan tugmalar:
        # Sotuvchi — SUCCESS (yashil) | Reklama — PRIMARY (ko'k)
        btn = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="👤 Sotuvchi bilan bog'lanish",
                url=f"tg://user?id={user_id}",
                style="success"
            )],
            [InlineKeyboardButton(
                text="📢 Reklama berish",
                url=f"https://t.me/{me.username}?start=ad",
                style="primary"
            )]
        ])

        await bot.send_video(MAIN_CHANNEL_ID, video=video_id, caption=text, reply_markup=btn)
        db_query("UPDATE users SET posted_ads = posted_ads + 1, pending_approval=0 WHERE user_id=?", (user_id,))
        db_query("UPDATE ads SET status='approved' WHERE id=?", (ad_id,))
        await bot.send_message(user_id, "✅ E'loningiz kanalga joylandi!", reply_markup=get_main_menu())
        await call.message.edit_caption(caption=call.message.caption + "\n\n✅ KANALGA JOYLANDI")

@router.callback_query(F.data.startswith("rej_ad_"))
async def reject_ad(call: CallbackQuery):
    ad_id = int(call.data.split("_")[2])
    ad = db_query("SELECT user_id FROM ads WHERE id=?", (ad_id,), fetchone=True)
    if ad:
        db_query("UPDATE ads SET status='rejected' WHERE id=?", (ad_id,))
        db_query("UPDATE users SET pending_approval=0 WHERE user_id=?", (ad[0],))
        await bot.send_message(ad[0], "❌ E'loningiz admin tomonidan rad etildi.", reply_markup=get_main_menu())
        await call.message.edit_caption(caption=call.message.caption + "\n\n❌ BEKOR QILINGAN")

# ================== ADMIN JAVOB CALLBACKLAR ==================
@router.callback_query(F.data.startswith("reply_"))
async def reply_support_cb(call: CallbackQuery, state: FSMContext):
    user_id = int(call.data.split("_")[1])
    await state.update_data(reply_to=user_id)
    await call.message.answer("Foydalanuvchiga javob matnini kiriting:")
    await state.set_state(AdminForm.reply_msg)

@router.message(AdminForm.reply_msg)
async def send_reply(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get('reply_to')
    await bot.send_message(user_id, f"👨‍💻 Admin javobi:\n\n{message.text}")
    await message.answer("Javob yuborildi.")
    await state.clear()

# ================== ADMIN PANEL ==================
@router.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def admin_panel(message: Message):
    btn = InlineKeyboardMarkup(inline_keyboard=[
        # Statistika — PRIMARY (ko'k)
        [InlineKeyboardButton(text="📊 Statistika (Rasmli)", callback_data="admin_stats", style="primary")],
        [
            # Narx — PRIMARY (ko'k)
            InlineKeyboardButton(text="💰 Narxni o'zgartirish", callback_data="admin_price", style="primary"),
            # Karta — PRIMARY (ko'k)
            InlineKeyboardButton(text="💳 Kartani o'zgartirish", callback_data="admin_card", style="primary"),
        ],
        # Start xabar — PRIMARY (ko'k)
        [InlineKeyboardButton(text="📝 Start xabarni o'zgartirish", callback_data="admin_startmsg", style="primary")],
        [
            # Kanal qo'shish — SUCCESS (yashil)
            InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="admin_add_ch", style="success"),
            # Kanal o'chirish — DANGER (qizil)
            InlineKeyboardButton(text="➖ Kanal o'chirish", callback_data="admin_del_ch", style="danger"),
        ]
    ])
    await message.answer("⚙️ Admin panelga xush kelibsiz!", reply_markup=btn)

@router.callback_query(F.data == "admin_price")
async def set_price_step(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Yangi narxni kiriting (faqat raqam):")
    await state.set_state(AdminForm.price)

@router.message(AdminForm.price)
async def save_price(message: Message, state: FSMContext):
    db_query("UPDATE settings SET value=? WHERE key='price'", (message.text,))
    await message.answer("✅ Narx yangilandi!")
    await state.clear()

@router.callback_query(F.data == "admin_card")
async def set_card_step(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Yangi karta raqamini kiriting:")
    await state.set_state(AdminForm.card)

@router.message(AdminForm.card)
async def save_card(message: Message, state: FSMContext):
    db_query("UPDATE settings SET value=? WHERE key='card'", (message.text,))
    await message.answer("✅ Karta yangilandi!")
    await state.clear()

@router.callback_query(F.data == "admin_startmsg")
async def set_start_step(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Yangi start xabarini kiriting. (Foydalanuvchi ismi uchun {name} ishlating):")
    await state.set_state(AdminForm.start_msg)

@router.message(AdminForm.start_msg)
async def save_start(message: Message, state: FSMContext):
    db_query("UPDATE settings SET value=? WHERE key='start_msg'", (message.text,))
    await message.answer("✅ Start xabar yangilandi!")
    await state.clear()

@router.callback_query(F.data == "admin_add_ch")
async def add_ch_step(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Kanal ID sini kiriting (masalan: @kanal_useri yoki -100123...):")
    await state.set_state(AdminForm.add_channel_id)

@router.message(AdminForm.add_channel_id)
async def add_ch_url(message: Message, state: FSMContext):
    await state.update_data(ch_id=message.text)
    await message.answer("Kanal ssilkasini kiriting (https://t.me/...):")
    await state.set_state(AdminForm.add_channel_url)

@router.message(AdminForm.add_channel_url)
async def save_ch(message: Message, state: FSMContext):
    data = await state.get_data()
    db_query("INSERT INTO channels (channel_id, url) VALUES (?, ?)", (data['ch_id'], message.text))
    await message.answer("✅ Kanal qo'shildi!")
    await state.clear()

@router.callback_query(F.data == "admin_del_ch")
async def del_ch_step(call: CallbackQuery):
    channels = db_query("SELECT id, channel_id FROM channels", fetchall=True)
    if not channels:
        await call.message.answer("Kanallar yo'q.")
        return
    # O'chirish — DANGER (qizil)
    btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"O'chirish: {ch[1]}", callback_data=f"delch_{ch[0]}", style="danger")]
        for ch in channels
    ])
    await call.message.answer("Qaysi kanalni o'chirasiz?", reply_markup=btn)

@router.callback_query(F.data.startswith("delch_"))
async def del_ch_action(call: CallbackQuery):
    c_id = int(call.data.split("_")[1])
    db_query("DELETE FROM channels WHERE id=?", (c_id,))
    await call.message.edit_text("✅ Kanal o'chirildi.")

# ================== STATISTIKA ==================
def generate_stats_image():
    users = db_query("SELECT user_id, full_name, join_date, posted_ads FROM users ORDER BY posted_ads DESC", fetchall=True)
    total_users = len(users)
    show_users = users[:30]
    img_height = 150 + (len(show_users) * 35)

    img = Image.new('RGB', (900, img_height), color=(25, 25, 35))
    d = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("arial.ttf", 24)
        font_text = ImageFont.truetype("arial.ttf", 16)
    except:
        font_title = ImageFont.load_default()
        font_text = ImageFont.load_default()

    d.text((30, 20), "📊 BOT STATISTIKASI", fill=(255, 200, 0), font=font_title)
    d.text((30, 60), f"Umumiy a'zolar: {total_users} ta", fill=(255, 255, 255), font=font_text)
    d.text((30, 90), f"Vaqt: {get_time_tashkent()}", fill=(150, 150, 150), font=font_text)
    d.line([(30, 120), (870, 120)], fill=(100, 100, 100), width=2)

    y = 135
    d.text((30, y), "ID", fill=(200, 200, 200), font=font_text)
    d.text((200, y), "ISMI", fill=(200, 200, 200), font=font_text)
    d.text((550, y), "QO'SHILGAN VAQTI", fill=(200, 200, 200), font=font_text)
    d.text((800, y), "E'LONLAR", fill=(200, 200, 200), font=font_text)

    y += 30
    for u in show_users:
        uid, name, date, ads = u
        name_trunc = name[:30] + "..." if len(name) > 30 else name
        d.text((30, y), str(uid), fill=(255, 255, 255), font=font_text)
        d.text((200, y), str(name_trunc), fill=(255, 255, 255), font=font_text)
        d.text((550, y), str(date), fill=(255, 255, 255), font=font_text)
        d.text((800, y), str(ads), fill=(0, 255, 0), font=font_text)
        y += 35

    bio = BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

@router.callback_query(F.data == "admin_stats")
async def send_stats_img(call: CallbackQuery):
    await call.message.answer("Statistika tayyorlanmoqda, kuting...")
    bio = generate_stats_image()
    file = BufferedInputFile(bio.read(), filename="stats.png")
    await bot.send_photo(call.from_user.id, photo=file,
        caption="📈 Botning to'liq statistikasi (TOP 30 foydalanuvchi)")
    await call.answer()

# ================== ASOSIY ISHGA TUSHIRISH ==================
async def main():
    dp.include_router(router)
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
