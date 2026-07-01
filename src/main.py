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
        await update.effective_message.reply_text(
            "Ein Fehler ist aufgetreten. Bitte versuche es später erneut."
        )


def main() -> None:
    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(get_conversation_handler())
    app.add_error_handler(error_handler)

    logger.info(
        "Starting webhook on 0.0.0.0:%s path=/%s url=%s",
        settings.bot_port,
        settings.webhook_path,
        settings.webhook_url,
    )

    app.run_webhook(
        listen="0.0.0.0",
        port=settings.bot_port,
        url_path=settings.webhook_path,
        webhook_url=settings.webhook_url,
    )


if __name__ == "__main__":
    main()
