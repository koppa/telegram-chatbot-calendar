import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from src.config import settings
from src.bot.handlers import get_conversation_handler, start

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def error_handler(update: Update | None, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled error: %s", context.error)
    if update and update.effective_message:
        msg = "Ein Fehler ist aufgetreten. Bitte versuche es später erneut."
        logger.info("Bot reply: %s", msg)
        await update.effective_message.reply_text(msg)


def main() -> None:
    if not settings.allowed_user_ids:
        logger.warning(
            "ALLOWED_USER_IDS is not set - the bot will respond to every Telegram user"
        )

    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .concurrent_updates(1)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(get_conversation_handler())
    app.add_error_handler(error_handler)

    logger.info("Starting polling")
    app.run_polling()


if __name__ == "__main__":
    main()
