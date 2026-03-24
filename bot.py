import asyncio
import logging
import aiohttp
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
BOT_TOKEN = "8745465963:AAFEOfQ90-2Rb6ok10QMumHoNYfKwmPWZjA"
ADMIN_ID = 8537782289
MAIN_CHANNEL_ID = "@Azizbekl2026"

# ================== JSONBIN.IO SOZLAMALARI ==================
JSONBIN_API_KEY = "$2a$10$HEa6qY6FgdbvtwnxhGkIE.59M05ctGsBYJn7zuLyvhrrqsWH5peje"
JSONBIN_BIN_ID = "69c24750aa77b81da9139a00"
JSONBIN_BASE_URL = "https://api.jsonbin.io/v3"

# ================== JSONBIN.IO YORDAMCHI FUNKSIYALAR ==================

async def jb_read() -> dict:
    """Jsonbin dan barcha ma'lumotlarni o'qish"""
    url = f"{JSONBIN_BASE_URL}/b/{JSONBIN_BIN_ID}/latest"
    headers = {"X-Master-Key": JSONBIN_API_KEY}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            data = await resp.json()
            return data.get("record", {})

async def jb_write(data: dict) -> bool:
    """Jsonbin ga ma'lumotlarni yozish"""
    url = f"{JSONBIN_BASE_URL}/b/{JSONBIN_BIN_ID}"
    headers = {
        "X-Master-Key": JSONBIN_API_KEY,
        "Content-Type": "application/json"
    }
    async with aiohttp.ClientSession() as session:
        async with session.put(url, json=data, headers=headers) as resp:
            return resp.status == 200

async def init_db():
    """Boshlang'ich ma'lumotlar strukturasi"""
    data = await jb_read()
    changed = False

    if "users" not in data:
        data["users"] = []
        changed = True
    if "channels" not in data:
        data["channels"] = []
        changed = True
    if "ads" not in data:
        data["ads"] = []
        changed = True
    if "uc_prices" not in data:
        data["uc_prices"] = []
        changed = True
    if "uc_orders" not in data:
        data["uc_orders"] = []
        changed = True
    if "stars_prices" not in data:
        data["stars_prices"] = []
        changed = True
    if "stars_orders" not in data:
        data["stars_orders"] = []
        changed = True
    if "premium_prices" not in data:
        data["premium_prices"] = []
        changed = True
    if "premium_orders" not in data:
        data["premium_orders"] = []
        changed = True
    if "settings" not in data:
        data["settings"] = {
            "price": "50000",
            "card": "8600 0000 0000 0000 (Ism Familiya)",
            "start_msg": "Salom {name}! Siz bu botdan PUBG Mobile akkauntingizni obzorini joylashingiz mumkin va u video kanalga joylanadi.",
            "site_url": "https://azizbekqiyomov55555-dev.github.io/Test-bot-"
        }
        changed = True
    if "next_id" not in data:
        data["next_id"] = 1
        changed = True

    if changed:
        await jb_write(data)

def get_next_id(data: dict) -> int:
    nid = data.get("next_id", 1)
    data["next_id"] = nid + 1
    return nid

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
    uc_card = State()
    uc_price_amount = State()
    uc_price_value = State()
    main_card = State()
    stars_card = State()
    premium_card = State()
    stars_price_amount = State()
    stars_price_value = State()
    premium_price_duration = State()
    premium_price_value = State()

class UCOrderForm(StatesGroup):
    pubg_screenshot = State()
    receipt = State()

class StarsOrderForm(StatesGroup):
    choose_target = State()
    friend_username = State()
    receipt = State()

class PremiumOrderForm(StatesGroup):
    choose_duration = State()
    target_username = State()
    receipt = State()

# ================== BOT VA ROUTER ==================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()

# ================== YORDAMCHI FUNKSIYALAR ==================
def get_time_tashkent():
    tz = pytz.timezone('Asia/Tashkent')
    return datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')

async def get_setting(key):
    data = await jb_read()
    return data.get("settings", {}).get(key, "")

async def check_subscription(user_id):
    data = await jb_read()
    channels = data.get("channels", [])
    unsubbed = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch["channel_id"], user_id)
            if member.status in ['left', 'kicked']:
                unsubbed.append(ch["url"])
        except:
            pass
    return unsubbed

# ================== ASOSIY MENU ==================
def get_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📝 E'lon berish"),
                KeyboardButton(text="🆘 Yordam"),
            ],
            [
                KeyboardButton(text="🎮 PUBG MOBILE UC OLISH 💎"),
            ],
            [
                KeyboardButton(text="⭐ TELEGRAM PREMIUM"),
                KeyboardButton(text="🌟 STARS OLISH"),
            ]
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Quyidagi tugmalardan birini tanlang 👇"
    )

# ================== UC NARXLARI INLINE KLAVIATURA ==================
def get_uc_prices_keyboard_from_data(prices, page=0):
    if not prices:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Hozircha narxlar kiritilmagan", callback_data="uc_no_prices")]
        ])

    ITEMS_PER_PAGE = 5
    total_pages = (len(prices) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    page = max(0, min(page, total_pages - 1))
    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    current_prices = prices[start:end]

    rows = []
    for item in current_prices:
        rows.append([
            InlineKeyboardButton(
                text=f"💎 {item['uc_amount']} UC — {item['price']:,} so'm".replace(",", " "),
                callback_data=f"buy_uc_{item['id']}_{item['uc_amount']}_{item['price']}"
            )
        ])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"uc_page_{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"uc_page_{page+1}"))
    if nav_row:
        rows.append(nav_row)

    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="uc_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_stars_prices_keyboard_from_data(prices, page=0):
    if not prices:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Hozircha narxlar kiritilmagan", callback_data="stars_no_prices")]
        ])

    ITEMS_PER_PAGE = 5
    total_pages = (len(prices) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    page = max(0, min(page, total_pages - 1))
    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    current_prices = prices[start:end]

    rows = []
    for item in current_prices:
        rows.append([
            InlineKeyboardButton(
                text=f"⭐ {item['stars_amount']} Stars — {item['price']:,} so'm".replace(",", " "),
                callback_data=f"buy_stars_{item['id']}_{item['stars_amount']}_{item['price']}"
            )
        ])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"stars_page_{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"stars_page_{page+1}"))
    if nav_row:
        rows.append(nav_row)

    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="stars_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_premium_prices_keyboard_from_data(prices, page=0):
    if not prices:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Hozircha narxlar kiritilmagan", callback_data="premium_no_prices")]
        ])

    ITEMS_PER_PAGE = 5
    total_pages = (len(prices) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    page = max(0, min(page, total_pages - 1))
    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    current_prices = prices[start:end]

    rows = []
    for item in current_prices:
        rows.append([
            InlineKeyboardButton(
                text=f"⭐ {item['duration']} — {item['price']:,} so'm".replace(",", " "),
                callback_data=f"buy_premium_{item['id']}_{item['price']}"
            )
        ])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"premium_page_{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"premium_page_{page+1}"))
    if nav_row:
        rows.append(nav_row)

    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="premium_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ================== START VA OBUNA ==================
@router.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext):
    await state.clear()
    data = await jb_read()

    users = data.get("users", [])
    user_exists = any(u["user_id"] == message.from_user.id for u in users)
    if not user_exists:
        users.append({
            "user_id": message.from_user.id,
            "full_name": message.from_user.full_name,
            "username": message.from_user.username or "",
            "join_date": get_time_tashkent(),
            "posted_ads": 0,
            "paid_slots": 0,
            "pending_approval": 0
        })
        data["users"] = users
        await jb_write(data)

    unsubbed = await check_subscription(message.from_user.id)
    if unsubbed:
        btn = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"Kanal {i+1} — Obuna bo'lish", url=url)]
            for i, url in enumerate(unsubbed)
        ] + [[InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="check_sub")]])
        await message.answer("Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:", reply_markup=btn)
        return

    start_text = data.get("settings", {}).get("start_msg", "Salom {name}!").replace("{name}", message.from_user.full_name)
    await message.answer(start_text, reply_markup=get_main_menu(), parse_mode="HTML")

@router.callback_query(F.data == "check_sub")
async def check_sub_cb(call: CallbackQuery):
    unsubbed = await check_subscription(call.from_user.id)
    if unsubbed:
        await call.answer("Hali hamma kanallarga obuna bo'lmadingiz!", show_alert=True)
    else:
        await call.message.delete()
        data = await jb_read()
        start_text = data.get("settings", {}).get("start_msg", "Salom {name}!").replace("{name}", call.from_user.full_name)
        await call.message.answer(f"Rahmat! Obuna tasdiqlandi.\n\n{start_text}", reply_markup=get_main_menu())

# ================== MENU HANDLERLAR ==================
@router.message(F.text == "📝 E'lon berish")
async def menu_ad_cb(message: Message, state: FSMContext):
    unsubbed = await check_subscription(message.from_user.id)
    if unsubbed:
        await message.answer("Iltimos, oldin kanallarga obuna bo'ling. /start ni bosing.")
        return

    data = await jb_read()
    users = data.get("users", [])
    user = next((u for u in users if u["user_id"] == message.from_user.id), None)

    if not user:
        await message.answer("Iltimos, /start bosing.")
        return

    posted = user.get("posted_ads", 0)
    paid = user.get("paid_slots", 0)
    pending = user.get("pending_approval", 0)

    if pending:
        await message.answer(
            "⏳ Sizning oldingi e'loningiz admin tomonidan ko'rib chiqilmoqda.\n"
            "Admin tasdiqlaganidan so'ng yangi e'lon berishingiz mumkin."
        )
        return

    if posted >= (1 + paid):
        price = data.get("settings", {}).get("price", "50000")
        btn = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="💳 To'lov qilish", callback_data="pay_ad")
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

# ================== 🎮 PUBG MOBILE UC OLISH ==================
@router.message(F.text == "🎮 PUBG MOBILE UC OLISH 💎")
async def uc_menu(message: Message, state: FSMContext):
    await state.clear()
    data = await jb_read()
    prices = sorted(data.get("uc_prices", []), key=lambda x: x.get("position", 0))

    text = (
        "🎮 <b>PUBG MOBILE UC OLISH</b>\n\n"
        "💎 Quyidagi narxlardan birini tanlang va to'lov qiling!\n"
        "⚡️ To'lov tasdiqlangandan so'ng UC tez yuboriladi.\n\n"
        "👇 UC miqdorini tanlang:"
    )
    await message.answer(text, reply_markup=get_uc_prices_keyboard_from_data(prices, 0), parse_mode="HTML")

@router.callback_query(F.data == "uc_no_prices")
async def uc_no_prices(call: CallbackQuery):
    await call.answer("Admin hali UC narxlarini kiritmagan!", show_alert=True)

@router.callback_query(F.data.startswith("uc_page_"))
async def uc_page_cb(call: CallbackQuery):
    page = int(call.data.split("_")[2])
    data = await jb_read()
    prices = sorted(data.get("uc_prices", []), key=lambda x: x.get("position", 0))
    try:
        await call.message.edit_reply_markup(reply_markup=get_uc_prices_keyboard_from_data(prices, page))
    except:
        pass
    await call.answer()

@router.callback_query(F.data == "uc_back")
async def uc_back_cb(call: CallbackQuery):
    await call.message.delete()
    await call.answer()

@router.callback_query(F.data.startswith("buy_uc_"))
async def buy_uc_cb(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    uc_amount = int(parts[3])
    price = int(parts[4])

    data = await jb_read()
    card = data.get("settings", {}).get("card", "")

    await state.update_data(uc_amount=uc_amount, uc_price=price)

    text = (
        f"💎 <b>{uc_amount} UC — {price:,} so'm</b>\n\n".replace(",", " ") +
        f"💳 <b>To'lov uchun karta:</b>\n<code>{card}</code>\n\n"
        f"📋 <b>Buyurtma berish bosqichlari:</b>\n"
        f"1️⃣ Yuqoridagi kartaga <b>{price:,} so'm</b> o'tkazing\n".replace(",", " ") +
        f"2️⃣ PUBG Mobile ga kiring va <b>profil ID raqamingizni</b> kiriting\n"
        f"3️⃣ To'lov chekini yuboring\n\n"
        f"🔢 <b>Iltimos, PUBG ID raqamingizni kiriting:</b>"
    )
    await call.message.edit_text(text, parse_mode="HTML")
    await state.set_state(UCOrderForm.pubg_screenshot)

@router.message(UCOrderForm.pubg_screenshot, F.text)
async def get_pubg_id(message: Message, state: FSMContext):
    pubg_id = message.text
    await state.update_data(pubg_id=pubg_id)

    data = await jb_read()
    card = data.get("settings", {}).get("card", "")
    st = await state.get_data()
    uc_amount = st['uc_amount']
    price = st['uc_price']

    text = (
        f"✅ <b>PUBG ID qabul qilindi: <code>{pubg_id}</code></b>\n\n"
        f"💳 Endi to'lovni amalga oshiring:\n\n"
        f"<b>Karta raqami:</b>\n<code>{card}</code>\n\n"
        f"<b>Summa:</b> {price:,} so'm\n\n".replace(",", " ") +
        f"💰 To'lov qilgach, <b>to'lov cheki (skrinshot)</b>ni yuboring:"
    )
    await message.answer(text, parse_mode="HTML")
    await state.set_state(UCOrderForm.receipt)

@router.message(UCOrderForm.pubg_screenshot)
async def get_pubg_id_wrong(message: Message):
    await message.answer("❗️ Iltimos, <b>PUBG ID raqamingizni</b> kiriting!", parse_mode="HTML")

@router.message(UCOrderForm.receipt, F.photo)
async def get_uc_receipt(message: Message, state: FSMContext):
    st = await state.get_data()
    receipt_id = message.photo[-1].file_id
    pubg_id = st.get('pubg_id', '—')
    uc_amount = st['uc_amount']
    price = st['uc_price']
    now = get_time_tashkent()

    data = await jb_read()
    order_id = get_next_id(data)
    orders = data.get("uc_orders", [])
    orders.append({
        "id": order_id,
        "user_id": message.from_user.id,
        "full_name": message.from_user.full_name,
        "username": message.from_user.username or "—",
        "uc_amount": uc_amount,
        "price": price,
        "pubg_id": pubg_id,
        "screenshot_id": receipt_id,
        "status": "pending",
        "order_date": now
    })
    data["uc_orders"] = orders
    await jb_write(data)

    admin_text = (
        f"🛒 <b>YANGI UC BUYURTMA!</b>\n\n"
        f"👤 Foydalanuvchi: {message.from_user.full_name}\n"
        f"🔗 Username: @{message.from_user.username or '—'}\n"
        f"🆔 Telegram ID: <code>{message.from_user.id}</code>\n\n"
        f"💎 UC miqdori: <b>{uc_amount} UC</b>\n"
        f"💰 To'lov summasi: <b>{price:,} so'm</b>\n\n".replace(",", " ") +
        f"🎮 PUBG ID: <code>{pubg_id}</code>\n"
        f"📅 Vaqt: <b>{now}</b> (Toshkent)"
    )

    btn = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"uc_approve_{message.from_user.id}_{order_id}"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"uc_reject_{message.from_user.id}_{order_id}")
    ]])

    await bot.send_photo(ADMIN_ID, photo=receipt_id, caption=admin_text, parse_mode="HTML", reply_markup=btn)
    await message.answer(
        f"✅ <b>Buyurtmangiz qabul qilindi!</b>\n\n"
        f"💎 <b>{uc_amount} UC</b> — {price:,} so'm\n\n".replace(",", " ") +
        f"⏳ Admin chekni ko'rib chiqib, UC ni tez orada yuboradi.\n"
        f"📞 Savollar bo'lsa: 🆘 Yordam tugmasini bosing.",
        parse_mode="HTML", reply_markup=get_main_menu()
    )
    await state.clear()

@router.message(UCOrderForm.receipt)
async def get_uc_receipt_wrong(message: Message):
    await message.answer("❗️ Iltimos, <b>to'lov cheki rasmini</b> yuboring!", parse_mode="HTML")

# ================== ADMIN UC TASDIQLASH ==================
@router.callback_query(F.data.startswith("uc_approve_"))
async def uc_approve_cb(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Sizda ruxsat yo'q!", show_alert=True)
        return
    parts = call.data.split("_")
    user_id = int(parts[2])
    order_id = int(parts[3])

    data = await jb_read()
    orders = data.get("uc_orders", [])
    order = next((o for o in orders if o["id"] == order_id), None)
    if order:
        order["status"] = "approved"
        data["uc_orders"] = orders
        await jb_write(data)
        await bot.send_message(
            user_id,
            f"🎉 <b>Tabriklaymiz! UC profilingizga tushdi!</b>\n\n"
            f"💎 <b>{order['uc_amount']} UC</b> akkauntingizga yuborildi!\n"
            f"O'yiningizni oching va UC ni tekshiring.\n\n"
            f"🙏 Xarid uchun rahmat!",
            parse_mode="HTML", reply_markup=get_main_menu()
        )

    caption = call.message.caption or ""
    try:
        await call.message.edit_caption(caption=caption + "\n\n✅ TASDIQLANDI — UC YUBORILDI", reply_markup=None)
    except:
        pass
    await call.answer("✅ Buyurtma tasdiqlandi!", show_alert=True)

@router.callback_query(F.data.startswith("uc_reject_"))
async def uc_reject_cb(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Sizda ruxsat yo'q!", show_alert=True)
        return
    parts = call.data.split("_")
    user_id = int(parts[2])
    order_id = int(parts[3])

    data = await jb_read()
    orders = data.get("uc_orders", [])
    order = next((o for o in orders if o["id"] == order_id), None)
    if order:
        order["status"] = "rejected"
        data["uc_orders"] = orders
        await jb_write(data)

    await bot.send_message(
        user_id,
        "❌ <b>Buyurtmangiz bekor qilindi.</b>\n\n"
        "To'lov cheki tasdiqlanmadi. Iltimos, qayta urinib ko'ring yoki "
        "🆘 Yordam orqali admin bilan bog'laning.",
        parse_mode="HTML", reply_markup=get_main_menu()
    )
    caption = call.message.caption or ""
    try:
        await call.message.edit_caption(caption=caption + "\n\n❌ BEKOR QILINDI", reply_markup=None)
    except:
        pass
    await call.answer("❌ Buyurtma bekor qilindi.", show_alert=True)

# ================== 🌟 STARS OLISH ==================
@router.message(F.text == "🌟 STARS OLISH")
async def stars_menu(message: Message, state: FSMContext):
    await state.clear()
    data = await jb_read()
    prices = sorted(data.get("stars_prices", []), key=lambda x: x.get("position", 0))

    text = (
        "🌟 <b>TELEGRAM STARS OLISH</b>\n\n"
        "⭐ Quyidagi miqdorlardan birini tanlang!\n"
        "⚡️ To'lov tasdiqlangandan so'ng Stars tez yuboriladi.\n\n"
        "👇 Stars miqdorini tanlang:"
    )
    await message.answer(text, reply_markup=get_stars_prices_keyboard_from_data(prices, 0), parse_mode="HTML")

@router.callback_query(F.data == "stars_no_prices")
async def stars_no_prices(call: CallbackQuery):
    await call.answer("Admin hali Stars narxlarini kiritmagan!", show_alert=True)

@router.callback_query(F.data.startswith("stars_page_"))
async def stars_page_cb(call: CallbackQuery):
    page = int(call.data.split("_")[2])
    data = await jb_read()
    prices = sorted(data.get("stars_prices", []), key=lambda x: x.get("position", 0))
    try:
        await call.message.edit_reply_markup(reply_markup=get_stars_prices_keyboard_from_data(prices, page))
    except:
        pass
    await call.answer()

@router.callback_query(F.data == "stars_back")
async def stars_back_cb(call: CallbackQuery):
    await call.message.delete()
    await call.answer()

@router.callback_query(F.data.startswith("buy_stars_"))
async def buy_stars_cb(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    stars_amount = int(parts[3])
    price = int(parts[4])

    await state.update_data(stars_amount=stars_amount, stars_price=price)

    btn = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="👤 O'ZIMGA", callback_data="stars_target_me"),
        InlineKeyboardButton(text="👫 DO'STIMGA", callback_data="stars_target_friend"),
    ]])

    await call.message.edit_text(
        f"⭐ <b>{stars_amount} Stars — {price:,} so'm</b>\n\nStars kimga kerak?".replace(",", " "),
        reply_markup=btn, parse_mode="HTML"
    )
    await state.set_state(StarsOrderForm.choose_target)
    await call.answer()

@router.callback_query(F.data == "stars_target_me", StarsOrderForm.choose_target)
async def stars_target_me(call: CallbackQuery, state: FSMContext):
    st = await state.get_data()
    stars_amount = st['stars_amount']
    price = st['stars_price']
    data = await jb_read()
    card = data.get("settings", {}).get("card", "")

    await state.update_data(target_type="me", target_username=call.from_user.username or str(call.from_user.id))

    text = (
        f"⭐ <b>{stars_amount} Stars — {price:,} so'm</b>\n\n".replace(",", " ") +
        f"💳 <b>To'lov uchun karta:</b>\n<code>{card}</code>\n\n"
        f"<b>Summa:</b> {price:,} so'm\n\n".replace(",", " ") +
        f"💰 To'lov qilgach, <b>to'lov cheki (skrinshot)</b>ni yuboring:"
    )
    await call.message.edit_text(text, parse_mode="HTML")
    await state.set_state(StarsOrderForm.receipt)
    await call.answer()

@router.callback_query(F.data == "stars_target_friend", StarsOrderForm.choose_target)
async def stars_target_friend(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "👫 <b>Do'stingizning Telegram username'ini kiriting:</b>\n\nMasalan: <code>@username</code>",
        parse_mode="HTML"
    )
    await state.set_state(StarsOrderForm.friend_username)
    await call.answer()

@router.message(StarsOrderForm.friend_username)
async def get_stars_friend_username(message: Message, state: FSMContext):
    username = message.text.strip().lstrip("@")
    await state.update_data(target_type="friend", target_username=username)

    st = await state.get_data()
    stars_amount = st['stars_amount']
    price = st['stars_price']
    data = await jb_read()
    card = data.get("settings", {}).get("card", "")

    text = (
        f"⭐ <b>{stars_amount} Stars — {price:,} so'm</b>\n\n".replace(",", " ") +
        f"👫 Do'st username: <code>@{username}</code>\n\n"
        f"💳 <b>To'lov uchun karta:</b>\n<code>{card}</code>\n\n"
        f"<b>Summa:</b> {price:,} so'm\n\n".replace(",", " ") +
        f"💰 To'lov qilgach, <b>to'lov cheki (skrinshot)</b>ni yuboring:"
    )
    await message.answer(text, parse_mode="HTML")
    await state.set_state(StarsOrderForm.receipt)

@router.message(StarsOrderForm.receipt, F.photo)
async def get_stars_receipt(message: Message, state: FSMContext):
    st = await state.get_data()
    receipt_id = message.photo[-1].file_id
    stars_amount = st['stars_amount']
    price = st['stars_price']
    target_type = st.get('target_type', 'me')
    target_username = st.get('target_username', '—')
    now = get_time_tashkent()

    data = await jb_read()
    order_id = get_next_id(data)
    orders = data.get("stars_orders", [])
    orders.append({
        "id": order_id,
        "user_id": message.from_user.id,
        "full_name": message.from_user.full_name,
        "username": message.from_user.username or "—",
        "stars_amount": stars_amount,
        "price": price,
        "target_type": target_type,
        "target_username": target_username,
        "receipt_id": receipt_id,
        "status": "pending",
        "order_date": now
    })
    data["stars_orders"] = orders
    await jb_write(data)

    target_text = f"O'ziga (@{target_username})" if target_type == "me" else f"Do'stiga (@{target_username})"

    admin_text = (
        f"⭐ <b>YANGI STARS BUYURTMA!</b>\n\n"
        f"👤 Foydalanuvchi: {message.from_user.full_name}\n"
        f"🔗 Username: @{message.from_user.username or '—'}\n"
        f"🆔 Telegram ID: <code>{message.from_user.id}</code>\n\n"
        f"⭐ Stars miqdori: <b>{stars_amount} Stars</b>\n"
        f"💰 To'lov summasi: <b>{price:,} so'm</b>\n\n".replace(",", " ") +
        f"🎯 Kimga: <b>{target_text}</b>\n"
        f"📅 Vaqt: <b>{now}</b> (Toshkent)"
    )

    btn = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"stars_approve_{message.from_user.id}_{order_id}"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"stars_reject_{message.from_user.id}_{order_id}"),
        ],
        [InlineKeyboardButton(text="👤 Foydalanuvchiga o'tish", url=f"tg://user?id={message.from_user.id}")]
    ])

    await bot.send_photo(ADMIN_ID, photo=receipt_id, caption=admin_text, parse_mode="HTML", reply_markup=btn)
    await message.answer(
        f"✅ <b>Buyurtmangiz qabul qilindi!</b>\n\n"
        f"⭐ <b>{stars_amount} Stars</b> — {price:,} so'm\n\n".replace(",", " ") +
        f"⏳ Admin chekni ko'rib chiqadi va Stars tez orada yuboriladi.\n"
        f"📞 Savollar bo'lsa: 🆘 Yordam tugmasini bosing.",
        parse_mode="HTML", reply_markup=get_main_menu()
    )
    await state.clear()

@router.message(StarsOrderForm.receipt)
async def get_stars_receipt_wrong(message: Message):
    await message.answer("❗️ Iltimos, <b>to'lov cheki rasmini</b> yuboring!", parse_mode="HTML")

# ================== ADMIN STARS TASDIQLASH ==================
@router.callback_query(F.data.startswith("stars_approve_"))
async def stars_approve_cb(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Sizda ruxsat yo'q!", show_alert=True)
        return
    parts = call.data.split("_")
    user_id = int(parts[2])
    order_id = int(parts[3])

    data = await jb_read()
    orders = data.get("stars_orders", [])
    order = next((o for o in orders if o["id"] == order_id), None)
    if order:
        order["status"] = "approved"
        data["stars_orders"] = orders
        await jb_write(data)
        await bot.send_message(
            user_id,
            f"🎉 <b>Tabriklaymiz! Stars profilingizga tushdi!</b>\n\n"
            f"⭐ <b>{order['stars_amount']} Stars</b> yuborildi!\n\n"
            f"🙏 Xarid uchun rahmat!",
            parse_mode="HTML", reply_markup=get_main_menu()
        )

    caption = call.message.caption or ""
    try:
        await call.message.edit_caption(caption=caption + "\n\n✅ TASDIQLANDI — STARS YUBORILDI", reply_markup=None)
    except:
        pass
    await call.answer("✅ Stars buyurtma tasdiqlandi!", show_alert=True)

@router.callback_query(F.data.startswith("stars_reject_"))
async def stars_reject_cb(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Sizda ruxsat yo'q!", show_alert=True)
        return
    parts = call.data.split("_")
    user_id = int(parts[2])
    order_id = int(parts[3])

    data = await jb_read()
    orders = data.get("stars_orders", [])
    order = next((o for o in orders if o["id"] == order_id), None)
    if order:
        order["status"] = "rejected"
        data["stars_orders"] = orders
        await jb_write(data)

    await bot.send_message(
        user_id,
        "❌ <b>Buyurtmangiz bekor qilindi.</b>\n\n"
        "🆘 Yordam orqali admin bilan bog'laning.",
        parse_mode="HTML", reply_markup=get_main_menu()
    )
    caption = call.message.caption or ""
    try:
        await call.message.edit_caption(caption=caption + "\n\n❌ BEKOR QILINDI", reply_markup=None)
    except:
        pass
    await call.answer("❌ Stars buyurtma bekor qilindi.", show_alert=True)

# ================== ⭐ TELEGRAM PREMIUM ==================
@router.message(F.text == "⭐ TELEGRAM PREMIUM")
async def premium_menu(message: Message, state: FSMContext):
    await state.clear()
    data = await jb_read()
    prices = sorted(data.get("premium_prices", []), key=lambda x: x.get("price", 0))

    text = (
        "⭐ <b>TELEGRAM PREMIUM OLISH</b>\n\n"
        "🚀 Premium obuna bilan Telegram'ni to'liq imkoniyatlaridan foydalaning!\n"
        "⚡️ To'lov tasdiqlangandan so'ng Premium tez ulanadi.\n\n"
        "👇 Muddat tanlang:"
    )
    await message.answer(text, reply_markup=get_premium_prices_keyboard_from_data(prices, 0), parse_mode="HTML")

@router.callback_query(F.data == "premium_no_prices")
async def premium_no_prices(call: CallbackQuery):
    await call.answer("Admin hali Premium narxlarini kiritmagan!", show_alert=True)

@router.callback_query(F.data.startswith("premium_page_"))
async def premium_page_cb(call: CallbackQuery):
    page = int(call.data.split("_")[2])
    data = await jb_read()
    prices = sorted(data.get("premium_prices", []), key=lambda x: x.get("price", 0))
    try:
        await call.message.edit_reply_markup(reply_markup=get_premium_prices_keyboard_from_data(prices, page))
    except:
        pass
    await call.answer()

@router.callback_query(F.data == "premium_back")
async def premium_back_cb(call: CallbackQuery):
    await call.message.delete()
    await call.answer()

@router.callback_query(F.data.startswith("buy_premium_"))
async def buy_premium_cb(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    pid = int(parts[2])
    price = int(parts[3])

    data = await jb_read()
    prices = data.get("premium_prices", [])
    row = next((p for p in prices if p["id"] == pid), None)
    duration = row["duration"] if row else "Noma'lum"

    await state.update_data(premium_pid=pid, premium_price=price, premium_duration=duration)

    await call.message.edit_text(
        f"⭐ <b>{duration} — {price:,} so'm</b>\n\n".replace(",", " ") +
        f"Premium tushirilsinchi profil username'ini yuboring:\n\nMasalan: <code>@username</code>",
        parse_mode="HTML"
    )
    await state.set_state(PremiumOrderForm.target_username)
    await call.answer()

@router.message(PremiumOrderForm.target_username)
async def get_premium_username(message: Message, state: FSMContext):
    username = message.text.strip().lstrip("@")
    await state.update_data(target_username=username)

    st = await state.get_data()
    price = st['premium_price']
    duration = st['premium_duration']
    data = await jb_read()
    card = data.get("settings", {}).get("card", "")

    text = (
        f"⭐ <b>{duration} — {price:,} so'm</b>\n\n".replace(",", " ") +
        f"👤 Premium tushiriladigan profil: <code>@{username}</code>\n\n"
        f"💳 <b>To'lov uchun karta:</b>\n<code>{card}</code>\n\n"
        f"<b>Summa:</b> {price:,} so'm\n\n".replace(",", " ") +
        f"💰 To'lov qilgach, <b>to'lov cheki (skrinshot)</b>ni yuboring:"
    )
    await message.answer(text, parse_mode="HTML")
    await state.set_state(PremiumOrderForm.receipt)

@router.message(PremiumOrderForm.receipt, F.photo)
async def get_premium_receipt(message: Message, state: FSMContext):
    st = await state.get_data()
    receipt_id = message.photo[-1].file_id
    price = st['premium_price']
    duration = st['premium_duration']
    target_username = st.get('target_username', '—')
    now = get_time_tashkent()

    data = await jb_read()
    order_id = get_next_id(data)
    orders = data.get("premium_orders", [])
    orders.append({
        "id": order_id,
        "user_id": message.from_user.id,
        "full_name": message.from_user.full_name,
        "username": message.from_user.username or "—",
        "duration": duration,
        "price": price,
        "target_username": target_username,
        "receipt_id": receipt_id,
        "status": "pending",
        "order_date": now
    })
    data["premium_orders"] = orders
    await jb_write(data)

    admin_text = (
        f"⭐ <b>YANGI PREMIUM BUYURTMA!</b>\n\n"
        f"👤 Foydalanuvchi: {message.from_user.full_name}\n"
        f"🔗 Username: @{message.from_user.username or '—'}\n"
        f"🆔 Telegram ID: <code>{message.from_user.id}</code>\n\n"
        f"⭐ Premium muddati: <b>{duration}</b>\n"
        f"💰 To'lov summasi: <b>{price:,} so'm</b>\n\n".replace(",", " ") +
        f"🎯 Premium tushiriladigan profil: <code>@{target_username}</code>\n"
        f"📅 Vaqt: <b>{now}</b> (Toshkent)"
    )

    btn = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"premium_approve_{message.from_user.id}_{order_id}"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"premium_reject_{message.from_user.id}_{order_id}"),
        ],
        [InlineKeyboardButton(text="👤 Foydalanuvchiga o'tish", url=f"tg://user?id={message.from_user.id}")]
    ])

    await bot.send_photo(ADMIN_ID, photo=receipt_id, caption=admin_text, parse_mode="HTML", reply_markup=btn)
    await message.answer(
        f"✅ <b>Buyurtmangiz qabul qilindi!</b>\n\n"
        f"⭐ <b>{duration}</b> Telegram Premium\n"
        f"💰 {price:,} so'm\n\n".replace(",", " ") +
        f"⏳ Admin chekni ko'rib chiqadi va Premium tez orada ulanadi.\n"
        f"📞 Savollar bo'lsa: 🆘 Yordam tugmasini bosing.",
        parse_mode="HTML", reply_markup=get_main_menu()
    )
    await state.clear()

@router.message(PremiumOrderForm.receipt)
async def get_premium_receipt_wrong(message: Message):
    await message.answer("❗️ Iltimos, <b>to'lov cheki rasmini</b> yuboring!", parse_mode="HTML")

# ================== ADMIN PREMIUM TASDIQLASH ==================
@router.callback_query(F.data.startswith("premium_approve_"))
async def premium_approve_cb(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Sizda ruxsat yo'q!", show_alert=True)
        return
    parts = call.data.split("_")
    user_id = int(parts[2])
    order_id = int(parts[3])

    data = await jb_read()
    orders = data.get("premium_orders", [])
    order = next((o for o in orders if o["id"] == order_id), None)
    if order:
        order["status"] = "approved"
        data["premium_orders"] = orders
        await jb_write(data)
        await bot.send_message(
            user_id,
            f"🎉 <b>Tabriklaymiz! Telegram Premium ulandi!</b>\n\n"
            f"⭐ <b>{order['duration']}</b> Premium obuna\n"
            f"👤 Profil: <code>@{order['target_username']}</code>\n\n"
            f"🙏 Xarid uchun rahmat!",
            parse_mode="HTML", reply_markup=get_main_menu()
        )

    caption = call.message.caption or ""
    try:
        await call.message.edit_caption(caption=caption + "\n\n✅ TASDIQLANDI — PREMIUM ULANDI", reply_markup=None)
    except:
        pass
    await call.answer("✅ Premium buyurtma tasdiqlandi!", show_alert=True)

@router.callback_query(F.data.startswith("premium_reject_"))
async def premium_reject_cb(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Sizda ruxsat yo'q!", show_alert=True)
        return
    parts = call.data.split("_")
    user_id = int(parts[2])
    order_id = int(parts[3])

    data = await jb_read()
    orders = data.get("premium_orders", [])
    order = next((o for o in orders if o["id"] == order_id), None)
    if order:
        order["status"] = "rejected"
        data["premium_orders"] = orders
        await jb_write(data)

    await bot.send_message(
        user_id,
        "❌ <b>Buyurtmangiz bekor qilindi.</b>\n\n"
        "🆘 Yordam orqali admin bilan bog'laning.",
        parse_mode="HTML", reply_markup=get_main_menu()
    )
    caption = call.message.caption or ""
    try:
        await call.message.edit_caption(caption=caption + "\n\n❌ BEKOR QILINDI", reply_markup=None)
    except:
        pass
    await call.answer("❌ Premium buyurtma bekor qilindi.", show_alert=True)

# ================== TO'LOV ==================
@router.callback_query(F.data == "pay_ad")
async def pay_ad_cb(call: CallbackQuery, state: FSMContext):
    data = await jb_read()
    card = data.get("settings", {}).get("card", "")
    price = data.get("settings", {}).get("price", "50000")
    await call.message.edit_text(
        f"💳 To'lov uchun karta raqam:\n\n`{card}`\nSumma: {price} so'm\n\n"
        f"To'lov qilgach, chekni rasm (skrinshot) qilib yuboring.",
        parse_mode="Markdown")
    await state.set_state(PaymentForm.receipt)

@router.message(PaymentForm.receipt, F.photo)
async def get_receipt(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    btn = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"app_pay_{message.from_user.id}"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"rej_pay_{message.from_user.id}")
    ]])
    await bot.send_photo(ADMIN_ID, photo_id,
        caption=f"💰 Yangi to'lov cheki.\n"
                f"Foydalanuvchi: {message.from_user.full_name} (@{message.from_user.username})\n"
                f"ID: {message.from_user.id}",
        reply_markup=btn)
    await message.answer("Chek adminga yuborildi. Tasdiqlanishini kuting.", reply_markup=get_main_menu())
    await state.clear()

# ================== E'LON BERISH ==================
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

@router.message(AdForm.guns)
async def get_guns(message: Message, state: FSMContext):
    await state.update_data(guns=message.text)
    await message.answer("Nechta X-suit bor? Kiriting:")
    await state.set_state(AdForm.xsuits)

@router.message(AdForm.xsuits)
async def get_xsuits(message: Message, state: FSMContext):
    await state.update_data(xsuits=message.text)
    await message.answer("Nechta RP olingan? Kiriting:")
    await state.set_state(AdForm.rp)

@router.message(AdForm.rp)
async def get_rp(message: Message, state: FSMContext):
    await state.update_data(rp=message.text)
    await message.answer("Nechta mashina (skin) bor? Kiriting:")
    await state.set_state(AdForm.cars)

@router.message(AdForm.cars)
async def get_cars(message: Message, state: FSMContext):
    await state.update_data(cars=message.text)
    await message.answer("Narxini so'mda kiriting (masalan: 150000):")
    await state.set_state(AdForm.price)

@router.message(AdForm.price)
async def get_price_ad(message: Message, state: FSMContext):
    await state.update_data(price=message.text)
    await message.answer("Telefon raqamingizni kiriting (masalan: +998901234567):")
    await state.set_state(AdForm.phone)

@router.message(AdForm.phone)
async def get_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    st = await state.get_data()

    text = (
        f"📋 <b>E'lon ma'lumotlari:</b>\n\n"
        f"🎮 Level: {st.get('level')}\n"
        f"🔫 Qurollar: {st.get('guns')}\n"
        f"👔 X-suitlar: {st.get('xsuits')}\n"
        f"🏆 RP: {st.get('rp')}\n"
        f"🚗 Mashinalar: {st.get('cars')}\n"
        f"💰 Narx: {st.get('price')} so'm\n"
        f"📞 Telefon: {st.get('phone')}"
    )

    data = await jb_read()
    ad_id = get_next_id(data)
    ads = data.get("ads", [])
    ads.append({
        "id": ad_id,
        "user_id": message.from_user.id,
        "video_id": st.get('video'),
        "text": text,
        "status": "pending"
    })
    data["ads"] = ads

    users = data.get("users", [])
    for u in users:
        if u["user_id"] == message.from_user.id:
            u["pending_approval"] = 1
            break
    data["users"] = users
    await jb_write(data)

    btn = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"app_ad_{ad_id}"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"rej_ad_{ad_id}")
    ]])

    try:
        await bot.send_video(ADMIN_ID, video=st.get('video'),
            caption=f"📢 Yangi e'lon!\nFoydalanuvchi: {message.from_user.full_name} (ID: {message.from_user.id})\n\n{text}",
            reply_markup=btn, parse_mode="HTML")
    except:
        pass

    await message.answer("✅ E'loningiz adminga yuborildi. Tasdiqlanishini kuting.", reply_markup=get_main_menu())
    await state.clear()

# ================== SUPPORT ==================
@router.message(SupportForm.msg)
async def get_support_msg(message: Message, state: FSMContext):
    btn = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💬 Javob berish", callback_data=f"reply_{message.from_user.id}")
    ]])
    await bot.send_message(ADMIN_ID,
        f"📩 Yangi xabar!\n"
        f"Kimdan: {message.from_user.full_name} (ID: {message.from_user.id})\n\n"
        f"Xabar: {message.text}",
        reply_markup=btn)
    await message.answer("Xabaringiz adminga yetkazildi.", reply_markup=get_main_menu())
    await state.clear()

# ================== ADMIN TO'LOV ==================
@router.callback_query(F.data.startswith("app_pay_"))
async def approve_pay(call: CallbackQuery):
    user_id = int(call.data.split("_")[2])
    data = await jb_read()
    users = data.get("users", [])
    for u in users:
        if u["user_id"] == user_id:
            u["paid_slots"] = u.get("paid_slots", 0) + 1
            break
    data["users"] = users
    await jb_write(data)
    await bot.send_message(user_id, "✅ To'lovingiz admin tomonidan tasdiqlandi!\nEndi yana e'lon joylashingiz mumkin.", reply_markup=get_main_menu())
    await call.message.edit_caption(caption=call.message.caption + "\n\n✅ TASDIQLANGAN")

@router.callback_query(F.data.startswith("rej_pay_"))
async def reject_pay(call: CallbackQuery):
    user_id = int(call.data.split("_")[2])
    await bot.send_message(user_id, "❌ To'lovingiz admin tomonidan bekor qilindi.", reply_markup=get_main_menu())
    await call.message.edit_caption(caption=call.message.caption + "\n\n❌ BEKOR QILINGAN")

# ================== ADMIN E'LON ==================
@router.callback_query(F.data.startswith("app_ad_"))
async def approve_ad(call: CallbackQuery):
    ad_id = int(call.data.split("_")[2])
    data = await jb_read()
    ads = data.get("ads", [])
    ad = next((a for a in ads if a["id"] == ad_id), None)

    if not ad:
        await call.answer("❌ E'lon topilmadi!", show_alert=True)
        return

    user_id = ad["user_id"]
    me = await bot.get_me()

    btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Sotuvchi bilan aloqa", url=f"tg://user?id={user_id}")],
        [InlineKeyboardButton(text="📢 Reklama berish", url=f"https://t.me/{me.username}?start=ad")]
    ])

    try:
        await bot.send_video(MAIN_CHANNEL_ID, video=ad["video_id"], caption=ad["text"], reply_markup=btn, parse_mode="HTML")
    except Exception as e:
        await call.answer(f"❌ Kanalga yuborishda XATO:\n{e}", show_alert=True)
        return

    ad["status"] = "approved"
    users = data.get("users", [])
    for u in users:
        if u["user_id"] == user_id:
            u["posted_ads"] = u.get("posted_ads", 0) + 1
            u["pending_approval"] = 0
            break
    data["ads"] = ads
    data["users"] = users
    await jb_write(data)

    try:
        await bot.send_message(user_id, "✅ E'loningiz kanalga joylandi!", reply_markup=get_main_menu())
    except:
        pass

    old_caption = call.message.caption or ""
    try:
        await call.message.edit_caption(caption=old_caption + "\n\n✅ KANALGA JOYLANDI", reply_markup=None)
    except:
        pass
    await call.answer("✅ E'lon kanalga joylandi!", show_alert=True)

@router.callback_query(F.data.startswith("rej_ad_"))
async def reject_ad(call: CallbackQuery):
    ad_id = int(call.data.split("_")[2])
    data = await jb_read()
    ads = data.get("ads", [])
    ad = next((a for a in ads if a["id"] == ad_id), None)

    if not ad:
        await call.answer("❌ E'lon topilmadi!", show_alert=True)
        return

    user_id = ad["user_id"]
    ad["status"] = "rejected"

    users = data.get("users", [])
    for u in users:
        if u["user_id"] == user_id:
            u["pending_approval"] = 0
            break
    data["ads"] = ads
    data["users"] = users
    await jb_write(data)

    try:
        await bot.send_message(user_id, "❌ E'loningiz admin tomonidan rad etildi.", reply_markup=get_main_menu())
    except:
        pass

    old_caption = call.message.caption or ""
    try:
        await call.message.edit_caption(caption=old_caption + "\n\n❌ BEKOR QILINGAN", reply_markup=None)
    except:
        pass
    await call.answer("❌ E'lon bekor qilindi.", show_alert=True)

# ================== ADMIN JAVOB ==================
@router.callback_query(F.data.startswith("reply_"))
async def reply_support_cb(call: CallbackQuery, state: FSMContext):
    user_id = int(call.data.split("_")[1])
    await state.update_data(reply_to=user_id)
    await call.message.answer("Foydalanuvchiga javob matnini kiriting:")
    await state.set_state(AdminForm.reply_msg)

@router.message(AdminForm.reply_msg)
async def send_reply(message: Message, state: FSMContext):
    st = await state.get_data()
    user_id = st.get('reply_to')
    await bot.send_message(user_id, f"👨‍💻 Admin javobi:\n\n{message.text}")
    await message.answer("Javob yuborildi.")
    await state.clear()

# ================== ADMIN PANEL ==================
@router.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def admin_panel(message: Message):
    btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
        [
            InlineKeyboardButton(text="💰 Narxni o'zgartirish", callback_data="admin_price"),
            InlineKeyboardButton(text="💳 Kartani o'zgartirish", callback_data="admin_card"),
        ],
        [InlineKeyboardButton(text="📝 Start xabarni o'zgartirish", callback_data="admin_startmsg")],
        [
            InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="admin_add_ch"),
            InlineKeyboardButton(text="➖ Kanal o'chirish", callback_data="admin_del_ch"),
        ],
        [InlineKeyboardButton(text="━━━━ 💎 UC SOZLAMALARI ━━━━", callback_data="section_title")],
        [InlineKeyboardButton(text="➕ UC narxi kiritish", callback_data="admin_add_uc_price")],
        [
            InlineKeyboardButton(text="📋 UC narxlari ro'yxati", callback_data="admin_uc_list"),
            InlineKeyboardButton(text="📦 UC buyurtmalar", callback_data="admin_uc_orders"),
        ],
        [InlineKeyboardButton(text="━━━━ ⭐ STARS SOZLAMALARI ━━━━", callback_data="section_title")],
        [InlineKeyboardButton(text="➕ Stars narxi kiritish", callback_data="admin_add_stars_price")],
        [
            InlineKeyboardButton(text="📋 Stars narxlari", callback_data="admin_stars_list"),
            InlineKeyboardButton(text="📦 Stars buyurtmalar", callback_data="admin_stars_orders"),
        ],
        [InlineKeyboardButton(text="━━━━ 💜 PREMIUM SOZLAMALARI ━━━━", callback_data="section_title")],
        [InlineKeyboardButton(text="➕ Premium narxi kiritish", callback_data="admin_add_premium_price")],
        [
            InlineKeyboardButton(text="📋 Premium narxlari", callback_data="admin_premium_list"),
            InlineKeyboardButton(text="📦 Premium buyurtmalar", callback_data="admin_premium_orders"),
        ],
    ])
    await message.answer("⚙️ Admin panelga xush kelibsiz!", reply_markup=btn)

@router.callback_query(F.data == "section_title")
async def section_title_cb(call: CallbackQuery):
    await call.answer()

# ================== ADMIN UC NARX ==================
@router.callback_query(F.data == "admin_add_uc_price")
async def add_uc_price_step1(call: CallbackQuery, state: FSMContext):
    await call.message.answer("💎 <b>UC miqdorini kiriting</b>\n\nMasalan: <code>60</code>", parse_mode="HTML")
    await state.set_state(AdminForm.uc_price_amount)

@router.message(AdminForm.uc_price_amount)
async def add_uc_price_step2(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❗️ Faqat raqam kiriting!")
        return
    await state.update_data(uc_amount=int(message.text))
    await message.answer(f"💰 <b>{message.text} UC narxini kiriting (so'mda)</b>", parse_mode="HTML")
    await state.set_state(AdminForm.uc_price_value)

@router.message(AdminForm.uc_price_value)
async def add_uc_price_save(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❗️ Faqat raqam kiriting!")
        return
    st = await state.get_data()
    uc_amount = st['uc_amount']
    price = int(message.text)

    data = await jb_read()
    prices = data.get("uc_prices", [])
    existing = next((p for p in prices if p["uc_amount"] == uc_amount), None)
    if existing:
        existing["price"] = price
        await message.answer(f"✅ <b>{uc_amount} UC</b> narxi yangilandi: <b>{price:,} so'm</b>".replace(",", " "), parse_mode="HTML")
    else:
        nid = get_next_id(data)
        prices.append({"id": nid, "uc_amount": uc_amount, "price": price, "position": 0})
        await message.answer(f"✅ <b>{uc_amount} UC — {price:,} so'm</b> qo'shildi!".replace(",", " "), parse_mode="HTML")
    data["uc_prices"] = prices
    await jb_write(data)
    await state.clear()

@router.callback_query(F.data == "admin_uc_list")
async def admin_uc_list(call: CallbackQuery):
    data = await jb_read()
    prices = sorted(data.get("uc_prices", []), key=lambda x: x.get("uc_amount", 0))

    if not prices:
        await call.message.answer("❌ Hozircha UC narxlari kiritilmagan.")
        await call.answer()
        return

    text = "💎 <b>UC NARXLARI RO'YXATI:</b>\n\n"
    rows = []
    for item in prices:
        text += f"• {item['uc_amount']} UC — {item['price']:,} so'm\n".replace(",", " ")
        rows.append([InlineKeyboardButton(text=f"🗑 {item['uc_amount']} UC o'chirish", callback_data=f"del_uc_price_{item['id']}")])

    rows.append([InlineKeyboardButton(text="🔙 Admin panel", callback_data="back_to_admin")])
    await call.message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()

@router.callback_query(F.data.startswith("del_uc_price_"))
async def del_uc_price(call: CallbackQuery):
    pid = int(call.data.split("_")[3])
    data = await jb_read()
    prices = data.get("uc_prices", [])
    item = next((p for p in prices if p["id"] == pid), None)
    if item:
        data["uc_prices"] = [p for p in prices if p["id"] != pid]
        await jb_write(data)
        await call.answer(f"✅ {item['uc_amount']} UC narxi o'chirildi!", show_alert=True)
        try:
            await call.message.delete()
        except:
            pass
    else:
        await call.answer("Topilmadi!", show_alert=True)

# ================== ADMIN STARS NARX ==================
@router.callback_query(F.data == "admin_add_stars_price")
async def add_stars_price_step1(call: CallbackQuery, state: FSMContext):
    await call.message.answer("⭐ <b>Stars miqdorini kiriting</b>\n\nMasalan: <code>50</code>", parse_mode="HTML")
    await state.set_state(AdminForm.stars_price_amount)

@router.message(AdminForm.stars_price_amount)
async def add_stars_price_step2(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❗️ Faqat raqam kiriting!")
        return
    await state.update_data(stars_amount=int(message.text))
    await message.answer(f"💰 <b>{message.text} Stars narxini kiriting (so'mda)</b>", parse_mode="HTML")
    await state.set_state(AdminForm.stars_price_value)

@router.message(AdminForm.stars_price_value)
async def add_stars_price_save(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❗️ Faqat raqam kiriting!")
        return
    st = await state.get_data()
    stars_amount = st['stars_amount']
    price = int(message.text)

    data = await jb_read()
    prices = data.get("stars_prices", [])
    existing = next((p for p in prices if p["stars_amount"] == stars_amount), None)
    if existing:
        existing["price"] = price
        await message.answer(f"✅ <b>{stars_amount} Stars</b> narxi yangilandi: <b>{price:,} so'm</b>".replace(",", " "), parse_mode="HTML")
    else:
        nid = get_next_id(data)
        prices.append({"id": nid, "stars_amount": stars_amount, "price": price, "position": 0})
        await message.answer(f"✅ <b>{stars_amount} Stars — {price:,} so'm</b> qo'shildi!".replace(",", " "), parse_mode="HTML")
    data["stars_prices"] = prices
    await jb_write(data)
    await state.clear()

@router.callback_query(F.data == "admin_stars_list")
async def admin_stars_list(call: CallbackQuery):
    data = await jb_read()
    prices = sorted(data.get("stars_prices", []), key=lambda x: x.get("stars_amount", 0))

    if not prices:
        await call.message.answer("❌ Hozircha Stars narxlari kiritilmagan.")
        await call.answer()
        return

    text = "⭐ <b>STARS NARXLARI RO'YXATI:</b>\n\n"
    rows = []
    for item in prices:
        text += f"• {item['stars_amount']} Stars — {item['price']:,} so'm\n".replace(",", " ")
        rows.append([InlineKeyboardButton(text=f"🗑 {item['stars_amount']} Stars o'chirish", callback_data=f"del_stars_price_{item['id']}")])

    rows.append([InlineKeyboardButton(text="🔙 Admin panel", callback_data="back_to_admin")])
    await call.message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()

@router.callback_query(F.data.startswith("del_stars_price_"))
async def del_stars_price(call: CallbackQuery):
    pid = int(call.data.split("_")[3])
    data = await jb_read()
    prices = data.get("stars_prices", [])
    item = next((p for p in prices if p["id"] == pid), None)
    if item:
        data["stars_prices"] = [p for p in prices if p["id"] != pid]
        await jb_write(data)
        await call.answer(f"✅ {item['stars_amount']} Stars narxi o'chirildi!", show_alert=True)
        try:
            await call.message.delete()
        except:
            pass
    else:
        await call.answer("Topilmadi!", show_alert=True)

# ================== ADMIN PREMIUM NARX ==================
@router.callback_query(F.data == "admin_add_premium_price")
async def add_premium_price_step1(call: CallbackQuery, state: FSMContext):
    await call.message.answer("⭐ <b>Premium muddatini kiriting</b>\n\nMasalan: <code>1 oylik</code>", parse_mode="HTML")
    await state.set_state(AdminForm.premium_price_duration)

@router.message(AdminForm.premium_price_duration)
async def add_premium_price_step2(message: Message, state: FSMContext):
    await state.update_data(premium_duration=message.text)
    await message.answer(f"💰 <b>«{message.text}» narxini kiriting (so'mda)</b>", parse_mode="HTML")
    await state.set_state(AdminForm.premium_price_value)

@router.message(AdminForm.premium_price_value)
async def add_premium_price_save(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❗️ Faqat raqam kiriting!")
        return
    st = await state.get_data()
    duration = st['premium_duration']
    price = int(message.text)

    data = await jb_read()
    nid = get_next_id(data)
    prices = data.get("premium_prices", [])
    prices.append({"id": nid, "duration": duration, "price": price, "position": 0})
    data["premium_prices"] = prices
    await jb_write(data)
    await message.answer(f"✅ <b>{duration} — {price:,} so'm</b> qo'shildi!".replace(",", " "), parse_mode="HTML")
    await state.clear()

@router.callback_query(F.data == "admin_premium_list")
async def admin_premium_list(call: CallbackQuery):
    data = await jb_read()
    prices = sorted(data.get("premium_prices", []), key=lambda x: x.get("price", 0))

    if not prices:
        await call.message.answer("❌ Hozircha Premium narxlari kiritilmagan.")
        await call.answer()
        return

    text = "⭐ <b>PREMIUM NARXLARI RO'YXATI:</b>\n\n"
    rows = []
    for item in prices:
        text += f"• {item['duration']} — {item['price']:,} so'm\n".replace(",", " ")
        rows.append([InlineKeyboardButton(text=f"🗑 {item['duration']} o'chirish", callback_data=f"del_premium_price_{item['id']}")])

    rows.append([InlineKeyboardButton(text="🔙 Admin panel", callback_data="back_to_admin")])
    await call.message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()

@router.callback_query(F.data.startswith("del_premium_price_"))
async def del_premium_price(call: CallbackQuery):
    pid = int(call.data.split("_")[3])
    data = await jb_read()
    prices = data.get("premium_prices", [])
    item = next((p for p in prices if p["id"] == pid), None)
    if item:
        data["premium_prices"] = [p for p in prices if p["id"] != pid]
        await jb_write(data)
        await call.answer(f"✅ {item['duration']} narxi o'chirildi!", show_alert=True)
        try:
            await call.message.delete()
        except:
            pass
    else:
        await call.answer("Topilmadi!", show_alert=True)

# ================== ADMIN BUYURTMALAR ==================
@router.callback_query(F.data == "admin_uc_orders")
async def admin_uc_orders(call: CallbackQuery):
    data = await jb_read()
    orders = sorted(data.get("uc_orders", []), key=lambda x: x.get("id", 0), reverse=True)[:20]

    if not orders:
        await call.message.answer("📦 Hozircha UC buyurtmalar yo'q.")
        await call.answer()
        return

    text = "📦 <b>OXIRGI 20 UC BUYURTMA:</b>\n\n"
    for o in orders:
        emoji = "⏳" if o["status"] == "pending" else ("✅" if o["status"] == "approved" else "❌")
        text += f"{emoji} #{o['id']} | {o['full_name']} | {o['uc_amount']} UC | {o['price']:,} so'm | {o['order_date']}\n".replace(",", " ")

    await call.message.answer(text, parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data == "admin_stars_orders")
async def admin_stars_orders(call: CallbackQuery):
    data = await jb_read()
    orders = sorted(data.get("stars_orders", []), key=lambda x: x.get("id", 0), reverse=True)[:20]

    if not orders:
        await call.message.answer("⭐ Hozircha Stars buyurtmalar yo'q.")
        await call.answer()
        return

    text = "⭐ <b>OXIRGI 20 STARS BUYURTMA:</b>\n\n"
    for o in orders:
        emoji = "⏳" if o["status"] == "pending" else ("✅" if o["status"] == "approved" else "❌")
        text += f"{emoji} #{o['id']} | {o['full_name']} | {o['stars_amount']} Stars | @{o['target_username']} | {o['order_date']}\n"

    await call.message.answer(text, parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data == "admin_premium_orders")
async def admin_premium_orders(call: CallbackQuery):
    data = await jb_read()
    orders = sorted(data.get("premium_orders", []), key=lambda x: x.get("id", 0), reverse=True)[:20]

    if not orders:
        await call.message.answer("⭐ Hozircha Premium buyurtmalar yo'q.")
        await call.answer()
        return

    text = "⭐ <b>OXIRGI 20 PREMIUM BUYURTMA:</b>\n\n"
    for o in orders:
        emoji = "⏳" if o["status"] == "pending" else ("✅" if o["status"] == "approved" else "❌")
        text += f"{emoji} #{o['id']} | {o['full_name']} | {o['duration']} | @{o['target_username']} | {o['order_date']}\n"

    await call.message.answer(text, parse_mode="HTML")
    await call.answer()

# ================== ADMIN SOZLAMALAR ==================
@router.callback_query(F.data == "admin_price")
async def set_price_step(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Yangi narxni kiriting (faqat raqam):")
    await state.set_state(AdminForm.price)

@router.message(AdminForm.price)
async def save_price(message: Message, state: FSMContext):
    data = await jb_read()
    data["settings"]["price"] = message.text
    await jb_write(data)
    await message.answer("✅ Narx yangilandi!")
    await state.clear()

@router.callback_query(F.data == "admin_card")
async def set_card_step(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Yangi karta raqamini kiriting:")
    await state.set_state(AdminForm.card)

@router.message(AdminForm.card)
async def save_card(message: Message, state: FSMContext):
    data = await jb_read()
    data["settings"]["card"] = message.text
    await jb_write(data)
    await message.answer("✅ Karta yangilandi!")
    await state.clear()

@router.callback_query(F.data == "admin_startmsg")
async def set_start_step(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Yangi start xabarini kiriting. ({name} — foydalanuvchi ismi):")
    await state.set_state(AdminForm.start_msg)

@router.message(AdminForm.start_msg)
async def save_start(message: Message, state: FSMContext):
    data = await jb_read()
    data["settings"]["start_msg"] = message.text
    await jb_write(data)
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
    st = await state.get_data()
    data = await jb_read()
    channels = data.get("channels", [])
    nid = get_next_id(data)
    channels.append({"id": nid, "channel_id": st['ch_id'], "url": message.text})
    data["channels"] = channels
    await jb_write(data)
    await message.answer("✅ Kanal qo'shildi!")
    await state.clear()

@router.callback_query(F.data == "admin_del_ch")
async def del_ch_step(call: CallbackQuery):
    data = await jb_read()
    channels = data.get("channels", [])
    if not channels:
        await call.message.answer("Kanallar yo'q.")
        return
    btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"O'chirish: {ch['channel_id']}", callback_data=f"delch_{ch['id']}")]
        for ch in channels
    ])
    await call.message.answer("Qaysi kanalni o'chirasiz?", reply_markup=btn)

@router.callback_query(F.data.startswith("delch_"))
async def del_ch_action(call: CallbackQuery):
    c_id = int(call.data.split("_")[1])
    data = await jb_read()
    data["channels"] = [c for c in data.get("channels", []) if c["id"] != c_id]
    await jb_write(data)
    await call.message.edit_text("✅ Kanal o'chirildi.")

@router.callback_query(F.data == "back_to_admin")
async def back_to_admin(call: CallbackQuery):
    await admin_panel(call.message)
    await call.answer()

# ================== ADMIN STATISTIKA ==================
@router.callback_query(F.data == "admin_stats")
async def send_stats(call: CallbackQuery):
    data = await jb_read()
    users = data.get("users", [])
    uc_orders = data.get("uc_orders", [])
    stars_orders = data.get("stars_orders", [])
    premium_orders = data.get("premium_orders", [])

    uc_approved = sum(1 for o in uc_orders if o.get("status") == "approved")

    text = (
        f"📊 <b>BOT STATISTIKASI</b>\n\n"
        f"👥 Umumiy foydalanuvchilar: <b>{len(users)} ta</b>\n"
        f"💎 UC buyurtmalar: <b>{len(uc_orders)} ta</b> (tasdiqlangan: {uc_approved})\n"
        f"⭐ Stars buyurtmalar: <b>{len(stars_orders)} ta</b>\n"
        f"🎖 Premium buyurtmalar: <b>{len(premium_orders)} ta</b>\n"
        f"🕐 Vaqt: {get_time_tashkent()}"
    )
    await call.message.answer(text, parse_mode="HTML")
    await call.answer()

# ================== CHECKBOT ==================
@router.message(Command("checkbot"), F.from_user.id == ADMIN_ID)
async def check_bot_status(message: Message):
    me = await bot.get_me()
    try:
        member = await bot.get_chat_member(MAIN_CHANNEL_ID, me.id)
        status = member.status
        can_post = getattr(member, 'can_post_messages', False)
        ha = "✅ Ha"
        yoq = "❌ Yo'q"
        ok = "✅ Hammasi yaxshi!"
        xato = "❌ Botni kanalga ADMIN qilib qo'shish kerak!"
        await message.answer(
            f"🤖 Bot: @{me.username}\n"
            f"📢 Kanal: {MAIN_CHANNEL_ID}\n"
            f"👤 Status: {status}\n"
            f"✉️ Post yuborish huquqi: {ha if can_post else yoq}\n\n"
            f"{ok if can_post else xato}"
        )
    except Exception as e:
        await message.answer(f"❌ Xatolik: {e}")

# ================== ASOSIY ISHGA TUSHIRISH ==================
async def main():
    print("⏳ Jsonbin.io baza tekshirilmoqda...")
    await init_db()
    print("✅ Baza tayyor!")

    dp.include_router(router)
    print("✅ Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
