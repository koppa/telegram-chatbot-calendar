import logging
from datetime import datetime, date

from telegram import Update, Document, PhotoSize, Voice, Audio
from telegram.ext import (
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from src.bot.states import WAITING_FOR_INPUT, AWAITING_DATE, AWAITING_TIME, AWAITING_CONFIRMATION
from src.services.openrouter import describe_image, extract_event
from src.services.whisper import transcribe_audio
from src.services.calendar import create_event
from src.models.event import CalendarEvent

logger = logging.getLogger(__name__)


def _today_str() -> str:
    return date.today().isoformat()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Hi! Ich kann Termine für deinen Google Kalender erstellen.\n"
        "Schick mir einfach eine Nachricht (Text, Bild oder Sprachnachricht) "
        "mit den Details \u2013 z.B. \u201eZahnarzt morgen um 10 Uhr f\u00fcr 1 Stunde\u201c."
    )
    return WAITING_FOR_INPUT


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("OK, abgebrochen.")
    return WAITING_FOR_INPUT


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    return await _process_text(update, context, text)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    photo: PhotoSize = update.message.photo[-1]
    file = await photo.get_file()
    photo_bytes = await file.download_as_bytearray()
    description = await describe_image(bytes(photo_bytes))
    return await _process_text(update, context, description)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    voice: Voice = update.message.voice
    file = await voice.get_file()
    audio_bytes = await file.download_as_bytearray()
    text = await transcribe_audio(bytes(audio_bytes))
    return await _process_text(update, context, text)


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    audio: Audio = update.message.audio
    file = await audio.get_file()
    audio_bytes = await file.download_as_bytearray()
    filename = audio.file_name or "audio.ogg"
    text = await transcribe_audio(bytes(audio_bytes), filename=filename)
    return await _process_text(update, context, text)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    doc: Document = update.message.document
    if doc.mime_type and doc.mime_type.startswith("image/"):
        file = await doc.get_file()
        image_bytes = await file.download_as_bytearray()
        description = await describe_image(bytes(image_bytes))
        return await _process_text(update, context, description)
    await update.message.reply_text(
        "Dieser Dateityp wird nicht unterst\u00fctzt. Nutze Text, Bilder oder Sprachnachrichten."
    )
    return WAITING_FOR_INPUT


async def handle_unsupported(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Nur Text, Bilder und Sprachnachrichten werden unterst\u00fctzt."
    )
    return WAITING_FOR_INPUT


async def _process_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> int:
    context.user_data["last_raw_text"] = text
    event = await extract_event(text, today=_today_str())

    if event is None:
        await update.message.reply_text(
            "Ich konnte leider keine Termininformationen erkennen. "
            "Wann soll der Termin stattfinden? (z.B. \u201eMorgen um 15 Uhr\u201c)"
        )
        return AWAITING_DATE

    partial = {
        "summary": event.summary,
        "start_datetime": event.start_datetime.isoformat() if event.start_datetime else None,
        "end_datetime": event.end_datetime.isoformat() if event.end_datetime else None,
        "duration_minutes": event.duration_minutes,
        "location": event.location,
        "description": event.description,
        "is_all_day": event.is_all_day,
    }

    if not event.summary and event.start_datetime:
        context.user_data["partial_event"] = {k: v for k, v in partial.items() if v is not None}
        await update.message.reply_text(
            f"Ich habe das Datum ({event.start_datetime.strftime('%d.%m.%Y %H:%M')}) erkannt. "
            "Wie soll der Termin hei\u00dfen?"
        )
        return AWAITING_DATE

    if not event.summary:
        context.user_data["partial_event"] = {}
        await update.message.reply_text(
            "Ich konnte leider keinen Termin erkennen. "
            "Wann soll der Termin stattfinden? (z.B. \u201eMorgen um 15 Uhr\u201c)"
        )
        return AWAITING_DATE

    if event.start_datetime is None:
        context.user_data["partial_event"] = {k: v for k, v in partial.items() if v is not None and k != "start_datetime"}
        await update.message.reply_text(
            f"Ich habe den Titel \u201e{event.summary}\u201c erkannt, aber wann soll der Termin stattfinden? "
            "(z.B. \u201eMorgen um 15 Uhr\u201c)"
        )
        return AWAITING_DATE

    if event.start_datetime.time() == datetime.min.time() and not event.is_all_day:
        event.is_all_day = True

    return await _confirm_and_create(update, context, event)


async def handle_awaiting_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    partial = context.user_data.get("partial_event", {})

    context_parts = []
    if partial.get("summary"):
        context_parts.append(f"Title already known: {partial['summary']}")
    if partial.get("start_datetime"):
        context_parts.append(f"Date/time already known: {partial['start_datetime']}")
    context_str = "; ".join(context_parts) if context_parts else ""

    event = await extract_event(
        text,
        context=context_str,
        today=_today_str(),
    )
    if event is None and not partial:
        await update.message.reply_text(
            "Ich konnte die Angabe leider nicht verstehen. "
            "Bitte gib den Termin im Format wie \u201eZahnarzt morgen um 15 Uhr\u201c an."
        )
        return AWAITING_DATE

    if event:
        if event.summary:
            partial["summary"] = event.summary
        if event.start_datetime:
            partial["start_datetime"] = event.start_datetime.isoformat()
        if event.end_datetime:
            partial["end_datetime"] = event.end_datetime.isoformat()
        if event.duration_minutes:
            partial["duration_minutes"] = event.duration_minutes
        if event.location:
            partial["location"] = event.location
        if event.description:
            partial["description"] = event.description
        if event.is_all_day:
            partial["is_all_day"] = True

    if not partial.get("summary"):
        await update.message.reply_text(
            "Wie soll der Termin hei\u00dfen?"
        )
        return AWAITING_DATE

    if not partial.get("start_datetime"):
        await update.message.reply_text(
            f"Ich habe den Titel \u201e{partial['summary']}\u201c erkannt, "
            "aber wann soll der Termin stattfinden? (z.B. \u201eMorgen um 15 Uhr\u201c)"
        )
        return AWAITING_DATE

    start_dt = datetime.fromisoformat(partial["start_datetime"])
    if start_dt.time() == datetime.min.time() and not partial.get("is_all_day"):
        partial["is_all_day"] = True

    full_event = CalendarEvent.model_validate(partial)
    return await _confirm_and_create(update, context, full_event)


async def handle_awaiting_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    partial = context.user_data.get("partial_event", {})

    context_str = ""
    if partial.get("summary"):
        context_str = f"Title: {partial['summary']}. Date: {partial.get('start_datetime', 'unknown')}."

    event = await extract_event(
        text,
        context=context_str,
        today=_today_str(),
    )
    if event is None or event.start_datetime is None or event.start_datetime.time() == datetime.min.time():
        await update.message.reply_text(
            "Ich konnte die Uhrzeit leider nicht verstehen. "
            "Bitte gib sie an wie \u201e15 Uhr\u201c oder \u201e14:30\u201c."
        )
        return AWAITING_TIME

    partial["start_datetime"] = event.start_datetime.isoformat()
    if event.end_datetime:
        partial["end_datetime"] = event.end_datetime.isoformat()
    if event.duration_minutes:
        partial["duration_minutes"] = event.duration_minutes

    full_event = CalendarEvent.model_validate(partial)
    return await _confirm_and_create(update, context, full_event)


async def _confirm_and_create(
    update: Update, context: ContextTypes.DEFAULT_TYPE, event: CalendarEvent
) -> int:
    lines = [
        f"*{event.summary}*",
    ]
    if event.is_all_day:
        lines.append(f"Datum: {event.start_datetime.strftime('%d.%m.%Y')} (ganztägig)")
        if event.end_datetime:
            days = (event.end_datetime.date() - event.start_datetime.date()).days
            if days > 0:
                lines.append(f"Bis: {event.end_datetime.strftime('%d.%m.%Y')} (ganztägig)")
    else:
        lines.append(f"Start: {event.start_datetime.strftime('%d.%m.%Y %H:%M')}")
        if event.end_datetime:
            lines.append(f"Ende: {event.end_datetime.strftime('%d.%m.%Y %H:%M')}")
        elif event.duration_minutes:
            lines.append(f"Dauer: {event.duration_minutes} Minuten")
    if event.location:
        lines.append(f"Ort: {event.location}")
    if event.description:
        lines.append(f"Beschreibung: {event.description}")

    await update.message.reply_text(
        f"Ich habe folgende Informationen extrahiert:\n\n" + "\n".join(lines) +
        "\n\nSoll ich den Termin erstellen? (Ja/Nein)",
        parse_mode="Markdown",
    )
    context.user_data["pending_event"] = event.model_dump()
    return AWAITING_CONFIRMATION


async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.lower().strip()
    if text in ("ja", "yes", "y", "ok", "klar", "sicher", "\U0001f44d", "thumbs up", "daumen hoch"):
        event_data = context.user_data.get("pending_event")
        if event_data is None:
            await update.message.reply_text("Etwas ist schiefgelaufen. Bitte beginne von vorne.")
            return WAITING_FOR_INPUT
        event = CalendarEvent.model_validate(event_data)
        try:
            link = await create_event(event)
            msg = f"Termin *{event.summary}* wurde erfolgreich erstellt!"
            if link:
                msg += f"\n\nIm Kalender ansehen: {link}"
            await update.message.reply_text(msg, parse_mode="Markdown")
        except Exception as e:
            logger.exception("Failed to create event")
            await update.message.reply_text(
                "Der Termin konnte nicht erstellt werden. Bitte sp\u00e4ter erneut versuchen."
            )
    else:
        await update.message.reply_text("OK, Termin nicht erstellt.")
    context.user_data.clear()
    return WAITING_FOR_INPUT


def get_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text),
            MessageHandler(filters.PHOTO, handle_photo),
            MessageHandler(filters.VOICE, handle_voice),
            MessageHandler(filters.AUDIO, handle_audio),
            MessageHandler(filters.Document.ALL, handle_document),
        ],
        states={
            WAITING_FOR_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text),
                MessageHandler(filters.PHOTO, handle_photo),
                MessageHandler(filters.VOICE, handle_voice),
                MessageHandler(filters.AUDIO, handle_audio),
                MessageHandler(filters.Document.ALL, handle_document),
                MessageHandler(~filters.COMMAND, handle_unsupported),
            ],
            AWAITING_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_awaiting_date),
            ],
            AWAITING_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_awaiting_time),
            ],
            AWAITING_CONFIRMATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_confirmation),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),
        ],
        name="calendar_bot_conversation",
        persistent=False,
    )
