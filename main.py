import os
import logging
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ── إعدادات ──────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
API_URL        = os.environ.get("API_URL", "https://claude-gemma-deploy--mraboodaihakerd.replit.app/api/v1/chat/completions")
API_KEY        = os.environ.get("API_KEY")
MODEL          = os.environ.get("MODEL", "claude-opus-4-7")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── تخزين سجل المحادثات لكل مستخدم ──────────────────────
user_histories: dict[int, list[dict]] = {}

# ── Health-check HTTP server (مطلوب لـ Render Web Service) ──
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass  # إخفاء سجلات HTTP لتنظيف الـ logs


def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    logger.info(f"Health-check server running on port {port}")
    server.serve_forever()


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

    await context.bot.send_chat_action(update.effective_chat.id, action="typing")

    history = user_histories.setdefault(user_id, [])
    history.append({"role": "user", "content": user_text})

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

    history.append({"role": "assistant", "content": reply_text})
    await update.message.reply_text(reply_text)

# ── تشغيل البوت ──────────────────────────────────────────
def main():
    # ✅ الإصلاح: تشغيل health-check server أولاً قبل أي شيء
    # حتى يتعرف عليه Render حتى لو فشلت الخطوات التالية
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
    logger.info("Health-check server started.")

    # التحقق من متغيرات البيئة المطلوبة
    if not TELEGRAM_TOKEN:
        logger.error("❌ TELEGRAM_TOKEN غير مضبوط. أضفه من: Render Dashboard → Environment Variables")
        raise ValueError("TELEGRAM_TOKEN is not set.")
    if not API_KEY:
        logger.error("❌ API_KEY غير مضبوط. أضفه من: Render Dashboard → Environment Variables")
        raise ValueError("API_KEY is not set.")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("البوت يعمل الآن...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
