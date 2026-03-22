import logging
import sqlite3
from datetime import datetime
import pytz
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, ConversationHandler, filters
)

# ══════════════════════════════════════════
#  SOZLAMALAR — shu yerga o'z ma'lumotlaringizni kiriting
# ══════════════════════════════════════════

BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"   # ← BotFather tokenini kiriting

ADMIN_IDS = [
    123456789,   # ← o'z Telegram ID raqamingizni kiriting
    # 987654321, # ← ikkinchi admin (ixtiyoriy)
]

# ══════════════════════════════════════════
#  MA'LUMOTLAR BAZASI
# ══════════════════════════════════════════

DB_PATH = "bot_database.db"


class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS uc_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount INTEGER NOT NULL,
                price INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS card (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                number TEXT NOT NULL,
                owner TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                uc_id INTEGER NOT NULL,
                uc_amount INTEGER NOT NULL,
                price INTEGER NOT NULL,
                pubg_photo TEXT,
                check_photo TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT
            );
        """)
        self.conn.commit()

    def add_user(self, user_id, username, full_name):
        self.conn.execute(
            "INSERT OR IGNORE INTO users (id, username, full_name) VALUES (?, ?, ?)",
            (user_id, username, full_name)
        )
        self.conn.commit()

    def get_uc_list(self):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM uc_prices ORDER BY amount ASC"
        ).fetchall()]

    def get_uc_by_id(self, uc_id):
        row = self.conn.execute("SELECT * FROM uc_prices WHERE id=?", (uc_id,)).fetchone()
        return dict(row) if row else None

    def add_uc(self, amount, price):
        self.conn.execute("INSERT INTO uc_prices (amount, price) VALUES (?, ?)", (amount, price))
        self.conn.commit()

    def delete_uc(self, uc_id):
        self.conn.execute("DELETE FROM uc_prices WHERE id=?", (uc_id,))
        self.conn.commit()

    def get_card(self):
        row = self.conn.execute("SELECT * FROM card ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    def set_card(self, number, owner):
        self.conn.execute("DELETE FROM card")
        self.conn.execute("INSERT INTO card (number, owner) VALUES (?, ?)", (number, owner))
        self.conn.commit()

    def create_order(self, user_id, uc_id, uc_amount, price, pubg_photo, check_photo, created_at):
        c = self.conn.execute(
            """INSERT INTO orders
               (user_id, uc_id, uc_amount, price, pubg_photo, check_photo, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, uc_id, uc_amount, price, pubg_photo, check_photo, created_at)
        )
        self.conn.commit()
        return c.lastrowid

    def get_order(self, order_id):
        row = self.conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        return dict(row) if row else None

    def update_order_status(self, order_id, status):
        self.conn.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
        self.conn.commit()

    def get_user_orders(self, user_id, limit=5):
        rows = self.conn.execute(
            "SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_recent_orders(self, limit=10):
        rows = self.conn.execute(
            "SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_stats(self):
        c = self.conn
        return {
            "users":        c.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "total_orders": c.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
            "approved":     c.execute("SELECT COUNT(*) FROM orders WHERE status='approved'").fetchone()[0],
            "rejected":     c.execute("SELECT COUNT(*) FROM orders WHERE status='rejected'").fetchone()[0],
            "pending":      c.execute("SELECT COUNT(*) FROM orders WHERE status='pending'").fetchone()[0],
            "total_sum":    c.execute("SELECT COALESCE(SUM(price),0) FROM orders WHERE status='approved'").fetchone()[0],
        }


db = Database()

# ══════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TASHKENT_TZ = pytz.timezone("Asia/Tashkent")

# ══════════════════════════════════════════
#  CONVERSATION STATES
# ══════════════════════════════════════════

(
    UC_SELECT, PUBG_ID_PHOTO, CHECK_PHOTO,
    ADMIN_ADD_UC_AMOUNT, ADMIN_ADD_UC_PRICE,
    ADMIN_ADD_CARD,
) = range(6)

# ══════════════════════════════════════════
#  YORDAMCHI FUNKSIYALAR
# ══════════════════════════════════════════

def tashkent_now():
    return datetime.now(TASHKENT_TZ).strftime("%d.%m.%Y %H:%M:%S")


def main_menu_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🎮 PUBG MOBILE UC OLISH")],
        [KeyboardButton("📋 Mening buyurtmalarim"), KeyboardButton("🆘 Yordam")],
    ], resize_keyboard=True)


def admin_menu_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("💰 UC narxlarini boshqarish")],
        [KeyboardButton("💳 Karta raqamini sozlash")],
        [KeyboardButton("📦 Buyurtmalar")],
        [KeyboardButton("📊 Statistika")],
        [KeyboardButton("🔙 Asosiy menyu")],
    ], resize_keyboard=True)


def uc_list_keyboard(page=0):
    uc_list = db.get_uc_list()
    if not uc_list:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ UC narxlari yo'q", callback_data="none")]
        ])

    per_page = 4
    total_pages = (len(uc_list) + per_page - 1) // per_page
    current = uc_list[page * per_page:(page + 1) * per_page]

    rows = []
    for i in range(0, len(current), 2):
        row = []
        for item in current[i:i + 2]:
            row.append(InlineKeyboardButton(
                f"💎 {item['amount']} UC — {item['price']:,} so'm",
                callback_data=f"uc_{item['id']}"
            ))
        rows.append(row)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"ucpage_{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"ucpage_{page + 1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel")])
    return InlineKeyboardMarkup(rows)

# ══════════════════════════════════════════
#  /start
# ══════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.username or "", user.full_name or "")
    await update.message.reply_text(
        f"👋 Assalomu alaykum, <b>{user.full_name}</b>!\n\n"
        "🎮 <b>PUBG MOBILE UC</b> sotib olish botiga xush kelibsiz!\n\n"
        "Quyidagi menyudan foydalaning:",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard()
    )

# ══════════════════════════════════════════
#  UC OLISH — 1: UC tanlash
# ══════════════════════════════════════════

async def pubg_uc_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db.get_uc_list():
        await update.message.reply_text(
            "⚠️ Hozircha UC narxlari kiritilmagan.",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "💎 <b>UC miqdorini tanlang:</b>",
        parse_mode="HTML",
        reply_markup=uc_list_keyboard(0)
    )
    return UC_SELECT


async def uc_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = int(query.data.split("_")[1])
    await query.edit_message_reply_markup(reply_markup=uc_list_keyboard(page))
    return UC_SELECT


async def uc_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cancel":
        await query.edit_message_text("❌ Bekor qilindi.")
        await query.message.reply_text("Asosiy menyu:", reply_markup=main_menu_keyboard())
        return ConversationHandler.END

    uc = db.get_uc_by_id(int(query.data.split("_")[1]))
    if not uc:
        await query.edit_message_text("⚠️ Xatolik. Qaytadan urinib ko'ring.")
        return ConversationHandler.END

    context.user_data["selected_uc"] = uc
    await query.edit_message_text(
        f"✅ Tanlandi: <b>{uc['amount']} UC</b> — <b>{uc['price']:,} so'm</b>\n\n"
        f"📸 Endi <b>PUBG ID</b> ko'rsatilgan ekran rasmini yuboring:\n"
        f"<i>(Profil sahifasida ID raqami ko'rinib tursin)</i>",
        parse_mode="HTML"
    )
    return PUBG_ID_PHOTO

# ══════════════════════════════════════════
#  UC OLISH — 2: PUBG ID rasmi
# ══════════════════════════════════════════

async def pubg_id_photo_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("⚠️ Iltimos, <b>rasm</b> yuboring!", parse_mode="HTML")
        return PUBG_ID_PHOTO

    context.user_data["pubg_photo_id"] = update.message.photo[-1].file_id
    uc = context.user_data["selected_uc"]
    card = db.get_card()

    if not card:
        await update.message.reply_text(
            "⚠️ To'lov kartasi sozlanmagan. Admin bilan bog'laning.",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END

    await update.message.reply_text(
        f"💳 <b>To'lov ma'lumotlari:</b>\n\n"
        f"🔢 Karta raqami:\n<code>{card['number']}</code>\n"
        f"👤 Egasi: <b>{card['owner']}</b>\n"
        f"💰 Summa: <b>{uc['price']:,} so'm</b>\n\n"
        f"✅ To'lovni amalga oshirib, <b>chek (screenshot)</b> rasmini yuboring:",
        parse_mode="HTML"
    )
    return CHECK_PHOTO

# ══════════════════════════════════════════
#  UC OLISH — 3: Chek rasmi → adminga xabar
# ══════════════════════════════════════════

async def check_photo_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("⚠️ Iltimos, <b>chek rasmini</b> yuboring!", parse_mode="HTML")
        return CHECK_PHOTO

    user = update.effective_user
    uc = context.user_data["selected_uc"]
    pubg_photo = context.user_data["pubg_photo_id"]
    check_photo = update.message.photo[-1].file_id
    now = tashkent_now()

    order_id = db.create_order(
        user_id=user.id,
        uc_id=uc["id"],
        uc_amount=uc["amount"],
        price=uc["price"],
        pubg_photo=pubg_photo,
        check_photo=check_photo,
        created_at=now,
    )

    # Foydalanuvchiga tasdiqlash xabari
    await update.message.reply_text(
        f"✅ <b>Buyurtmangiz qabul qilindi!</b>\n\n"
        f"🆔 Buyurtma №: <b>{order_id}</b>\n"
        f"💎 UC: <b>{uc['amount']} UC</b>\n"
        f"💰 Summa: <b>{uc['price']:,} so'm</b>\n"
        f"🕐 Vaqt: <b>{now}</b>\n\n"
        f"⏳ Admin tekshirib, tez orada UC yuboriladi.",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard()
    )

    # Adminga xabar
    admin_text = (
        f"🔔 <b>YANGI BUYURTMA #{order_id}</b>\n\n"
        f"👤 Foydalanuvchi: <a href='tg://user?id={user.id}'>{user.full_name}</a>\n"
        f"🆔 Telegram ID: <code>{user.id}</code>\n"
        f"💎 UC miqdori: <b>{uc['amount']} UC</b>\n"
        f"💰 Summa: <b>{uc['price']:,} so'm</b>\n"
        f"🕐 Vaqt (Toshkent): <b>{now}</b>"
    )
    approve_reject_kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_{order_id}"),
        InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_{order_id}"),
    ]])

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=pubg_photo,
                caption=f"📸 PUBG ID rasmi — Buyurtma #{order_id}"
            )
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=check_photo,
                caption=admin_text,
                parse_mode="HTML",
                reply_markup=approve_reject_kb
            )
        except Exception as e:
            logger.error(f"Admin {admin_id} ga xabar yuborishda xato: {e}")

    return ConversationHandler.END

# ══════════════════════════════════════════
#  ADMIN — tasdiqlash / rad etish
# ══════════════════════════════════════════

async def admin_approve_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id not in ADMIN_IDS:
        await query.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return

    action, order_id = query.data.split("_", 1)
    order_id = int(order_id)
    order = db.get_order(order_id)

    if not order:
        await query.edit_message_caption("⚠️ Buyurtma topilmadi.", parse_mode="HTML")
        return

    if action == "approve":
        db.update_order_status(order_id, "approved")
        status_text = "✅ <b>TASDIQLANDI</b>"
        user_msg = (
            f"🎉 <b>Buyurtmangiz tasdiqlandi!</b>\n\n"
            f"🆔 Buyurtma №: <b>{order_id}</b>\n"
            f"💎 <b>{order['uc_amount']} UC</b> tez orada yuboriladi. Rahmat! 🙏"
        )
    else:
        db.update_order_status(order_id, "rejected")
        status_text = "❌ <b>RAD ETILDI</b>"
        user_msg = (
            f"😔 <b>Buyurtmangiz rad etildi.</b>\n\n"
            f"🆔 Buyurtma №: <b>{order_id}</b>\n"
            f"Muammo bo'lsa admin bilan bog'laning."
        )

    await query.edit_message_caption(
        (query.message.caption or "") + f"\n\n{status_text}\n🕐 {tashkent_now()}",
        parse_mode="HTML"
    )
    try:
        await context.bot.send_message(chat_id=order["user_id"], text=user_msg, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Foydalanuvchiga xabar yuborishda xato: {e}")

# ══════════════════════════════════════════
#  ADMIN PANEL
# ══════════════════════════════════════════

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Ruxsat yo'q!")
        return
    await update.message.reply_text(
        "🛠 <b>Admin Panel</b>\n\nQuyidagi menyudan tanlang:",
        parse_mode="HTML",
        reply_markup=admin_menu_keyboard()
    )


async def admin_uc_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    uc_list = db.get_uc_list()
    if not uc_list:
        text = "💰 <b>UC narxlari</b>\n\nHali narx kiritilmagan."
    else:
        lines = ["💰 <b>UC narxlari:</b>\n"]
        for i, item in enumerate(uc_list, 1):
            lines.append(f"{i}. 💎 <b>{item['amount']} UC</b> — {item['price']:,} so'm  [ID: {item['id']}]")
        text = "\n".join(lines)

    await update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Yangi UC narxi qo'shish", callback_data="admin_add_uc")],
        [InlineKeyboardButton("🗑 UC narxini o'chirish", callback_data="admin_del_uc_menu")],
    ]))


async def admin_add_uc_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("💎 UC miqdorini kiriting (masalan: <b>60</b>):", parse_mode="HTML")
    return ADMIN_ADD_UC_AMOUNT


async def admin_add_uc_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("⚠️ Faqat raqam kiriting!")
        return ADMIN_ADD_UC_AMOUNT
    context.user_data["new_uc_amount"] = int(text)
    await update.message.reply_text(f"💰 {text} UC uchun narxni so'mda kiriting (masalan: <b>15000</b>):", parse_mode="HTML")
    return ADMIN_ADD_UC_PRICE


async def admin_add_uc_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(" ", "").replace(",", "")
    if not text.isdigit():
        await update.message.reply_text("⚠️ Faqat raqam kiriting!")
        return ADMIN_ADD_UC_PRICE
    amount = context.user_data["new_uc_amount"]
    price = int(text)
    db.add_uc(amount, price)
    await update.message.reply_text(
        f"✅ <b>{amount} UC — {price:,} so'm</b> muvaffaqiyatli qo'shildi!",
        parse_mode="HTML",
        reply_markup=admin_menu_keyboard()
    )
    return ConversationHandler.END


async def admin_del_uc_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uc_list = db.get_uc_list()
    if not uc_list:
        await query.message.reply_text("❌ O'chiriladigan UC yo'q.")
        return
    buttons = [
        [InlineKeyboardButton(f"🗑 {item['amount']} UC ({item['price']:,} so'm)", callback_data=f"deluc_{item['id']}")]
        for item in uc_list
    ]
    buttons.append([InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_admin")])
    await query.message.reply_text("O'chirmoqchi bo'lgan UC ni tanlang:", reply_markup=InlineKeyboardMarkup(buttons))


async def admin_del_uc_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db.delete_uc(int(query.data.split("_")[1]))
    await query.edit_message_text("✅ UC narxi o'chirildi.")


async def admin_card_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    card = db.get_card()
    text = (
        f"💳 <b>Joriy karta:</b>\n<code>{card['number']}</code>\nEgasi: <b>{card['owner']}</b>"
        if card else "💳 Hali karta kiritilmagan."
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Kartani yangilash", callback_data="admin_set_card")]
    ]))


async def admin_set_card_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "💳 Karta raqami va egasini kiriting:\n\n"
        "<code>8600 0000 0000 0000\nIsm Familiya</code>\n\n"
        "<i>(1-qator: karta raqami, 2-qator: egasining ismi)</i>",
        parse_mode="HTML"
    )
    return ADMIN_ADD_CARD


async def admin_set_card_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parts = update.message.text.strip().split("\n")
    number = parts[0].strip()
    owner = parts[1].strip() if len(parts) > 1 else "Ism Familiya"
    db.set_card(number, owner)
    await update.message.reply_text(
        f"✅ Karta saqlandi!\n<code>{number}</code>\nEgasi: <b>{owner}</b>",
        parse_mode="HTML",
        reply_markup=admin_menu_keyboard()
    )
    return ConversationHandler.END


async def admin_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    orders = db.get_recent_orders(10)
    if not orders:
        await update.message.reply_text("📦 Hali buyurtmalar yo'q.")
        return
    lines = ["📦 <b>So'nggi buyurtmalar:</b>\n"]
    for o in orders:
        icon = "✅" if o["status"] == "approved" else ("❌" if o["status"] == "rejected" else "⏳")
        lines.append(
            f"{icon} #{o['id']} | 💎{o['uc_amount']} UC | {o['price']:,} so'm\n"
            f"   👤 ID: {o['user_id']} | 🕐 {o['created_at']}\n"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    s = db.get_stats()
    await update.message.reply_text(
        f"📊 <b>Statistika:</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{s['users']}</b>\n"
        f"📦 Jami buyurtmalar: <b>{s['total_orders']}</b>\n"
        f"✅ Tasdiqlangan: <b>{s['approved']}</b>\n"
        f"❌ Rad etilgan: <b>{s['rejected']}</b>\n"
        f"⏳ Kutilayotgan: <b>{s['pending']}</b>\n"
        f"💰 Jami summa (tasdiqlangan): <b>{s['total_sum']:,} so'm</b>",
        parse_mode="HTML"
    )

# ══════════════════════════════════════════
#  FOYDALANUVCHI
# ══════════════════════════════════════════

async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    orders = db.get_user_orders(update.effective_user.id, limit=5)
    if not orders:
        await update.message.reply_text("📋 Sizda hali buyurtmalar yo'q.")
        return
    lines = ["📋 <b>Sizning buyurtmalaringiz:</b>\n"]
    for o in orders:
        icon = "✅" if o["status"] == "approved" else ("❌" if o["status"] == "rejected" else "⏳")
        status = "Tasdiqlangan" if o["status"] == "approved" else ("Rad etildi" if o["status"] == "rejected" else "Kutilmoqda")
        lines.append(f"{icon} #{o['id']} — 💎 <b>{o['uc_amount']} UC</b>\n   {status} | 🕐 {o['created_at']}\n")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🆘 <b>Yordam</b>\n\n"
        "1️⃣ <b>PUBG MOBILE UC OLISH</b> tugmasini bosing\n"
        "2️⃣ UC miqdorini tanlang\n"
        "3️⃣ PUBG ID rasmini yuboring\n"
        "4️⃣ Ko'rsatilgan kartaga to'lov qiling\n"
        "5️⃣ Chek rasmini yuboring\n\n"
        "❓ Muammo bo'lsa admin bilan bog'laning.",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard()
    )


async def cancel_admin_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("❌ Bekor qilindi.")

# ══════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # UC sotib olish
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🎮 PUBG MOBILE UC OLISH$"), pubg_uc_start)],
        states={
            UC_SELECT: [
                CallbackQueryHandler(uc_page_callback, pattern="^ucpage_"),
                CallbackQueryHandler(uc_selected, pattern="^(uc_|cancel)"),
            ],
            PUBG_ID_PHOTO: [MessageHandler(filters.PHOTO | filters.TEXT, pubg_id_photo_received)],
            CHECK_PHOTO:   [MessageHandler(filters.PHOTO | filters.TEXT, check_photo_received)],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True,
    ))

    # Admin UC qo'shish
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_add_uc_start, pattern="^admin_add_uc$")],
        states={
            ADMIN_ADD_UC_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_uc_amount)],
            ADMIN_ADD_UC_PRICE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_uc_price)],
        },
        fallbacks=[CommandHandler("start", start)],
    ))

    # Admin karta qo'shish
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_set_card_start, pattern="^admin_set_card$")],
        states={
            ADMIN_ADD_CARD: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_card_done)],
        },
        fallbacks=[CommandHandler("start", start)],
    ))

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))

    app.add_handler(MessageHandler(filters.Regex("^💰 UC narxlarini boshqarish$"), admin_uc_list))
    app.add_handler(MessageHandler(filters.Regex("^💳 Karta raqamini sozlash$"),   admin_card_menu))
    app.add_handler(MessageHandler(filters.Regex("^📦 Buyurtmalar$"),               admin_orders))
    app.add_handler(MessageHandler(filters.Regex("^📊 Statistika$"),                admin_stats))
    app.add_handler(MessageHandler(filters.Regex("^📋 Mening buyurtmalarim$"),      my_orders))
    app.add_handler(MessageHandler(filters.Regex("^🆘 Yordam$"),                    help_cmd))
    app.add_handler(MessageHandler(filters.Regex("^🔙 Asosiy menyu$"),              start))

    app.add_handler(CallbackQueryHandler(admin_approve_reject,  pattern="^(approve|reject)_"))
    app.add_handler(CallbackQueryHandler(admin_del_uc_menu,     pattern="^admin_del_uc_menu$"))
    app.add_handler(CallbackQueryHandler(admin_del_uc_confirm,  pattern="^deluc_"))
    app.add_handler(CallbackQueryHandler(cancel_admin_cb,       pattern="^cancel_admin$"))

    logger.info("🤖 Bot ishga tushdi...")
    app.run_polling()


if __name__ == "__main__":
    main()
