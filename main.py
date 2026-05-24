import os
import logging
import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ── إعدادات ──────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
API_URL        = os.environ.get("API_URL", "https://claude-gemma-deploy--mraboodaihakerd.replit.app/api/v1/chat/completions")
API_KEY        = os.environ["API_KEY"]
MODEL          = os.environ.get("MODEL", "claude-opus-4-7")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── تخزين سجل المحادثات لكل مستخدم ──────────────────────
user_histories: dict[int, list[dict]] = {}

# ── الأوامر ───────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = []
    await update.message.reply_text(
        "👋 أهلاً! أنا بوت الذكاء الاصطناعي.\n"
        "راسلني بأي شيء وسأرد عليك.\n\n"
        "📌 /reset — لمسح سجل المحادثة وبدء جديدة"
    )

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = []
    await update.message.reply_text("✅ تم مسح سجل المحادثة. ابدأ من جديد!")

# ── معالجة الرسائل ────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id   = update.effective_user.id
    user_text = update.message.text

    # أرسل رسالة "جارٍ الكتابة..."
    await context.bot.send_chat_action(update.effective_chat.id, action="typing")

    # بناء سجل المحادثة
    history = user_histories.setdefault(user_id, [])
    history.append({"role": "user", "content": user_text})

    # استدعاء API
    try:
        response = requests.post(
            API_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {API_KEY}",
            },
            json={
                "model": MODEL,
                "messages": history,
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        reply_text = data["choices"][0]["message"]["content"]
    except requests.exceptions.Timeout:
        reply_text = "⚠️ انتهت مهلة الاتصال بالنموذج. حاول مجدداً."
    except Exception as e:
        logger.error(f"API error: {e}")
        reply_text = f"⚠️ حدث خطأ أثناء الاتصال بالنموذج:\n`{e}`"

    # أضف رد النموذج للسجل
    history.append({"role": "assistant", "content": reply_text})

    await update.message.reply_text(reply_text)

# ── تشغيل البوت ──────────────────────────────────────────
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("البوت يعمل الآن...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
