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

from src.bot.states import WAITING_FOR_INPUT, AWAITING_DATE, AWAITING_CONFIRMATION
from src.services.openrouter import describe_image, extract_event
from src.services.whisper import transcribe_audio
from src.services.calendar import create_event
from src.models.event import CalendarEvent

logger = logging.getLogger(__name__)


def _user_id(update: Update) -> str:
    user = update.effective_user
    if not user:
        return "unknown"
    return user.username or user.first_name or str(user.id)


def _log_received(update: Update, text: str) -> None:
    preview = text[:100].replace("\n", " ")
    logger.info("Received from %s: %s", _user_id(update), preview)


async def _reply(update: Update, text: str, **kwargs) -> None:
    preview = text[:80].replace("\n", " ")
    logger.info("Bot reply: %s", preview)
    await update.message.reply_text(text, **kwargs)


def _today_str() -> str:
    return date.today().isoformat()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await _reply(update, 
        "Hi! Ich kann Termine für deinen Google Kalender erstellen.\n"
        "Schick mir einfach eine Nachricht (Text, Bild oder Sprachnachricht) "
        "mit den Details \u2013 z.B. \u201eZahnarzt morgen um 10 Uhr f\u00fcr 1 Stunde\u201c."
    )
    return WAITING_FOR_INPUT


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await _reply(update, "OK, abgebrochen.")
    return WAITING_FOR_INPUT


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    _log_received(update, text)
    return await _process_text(update, context, text)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    photo: PhotoSize = update.message.photo[-1]
    file = await photo.get_file()
    photo_bytes = await file.download_as_bytearray()
    description = await describe_image(bytes(photo_bytes))
    _log_received(update, f"[photo] {description}")
    return await _process_text(update, context, description)


async def _transcribe_message(update: Update) -> str | None:
    try:
        if update.message.voice:
            voice: Voice = update.message.voice
            file = await voice.get_file()
            audio_bytes = await file.download_as_bytearray()
            return await transcribe_audio(bytes(audio_bytes))
        if update.message.audio:
            audio: Audio = update.message.audio
            file = await audio.get_file()
            audio_bytes = await file.download_as_bytearray()
            filename = audio.file_name or "audio.ogg"
            return await transcribe_audio(bytes(audio_bytes), filename=filename)
    except Exception as e:
        logger.warning("Transcription failed: %s", e)
        return None
    return None


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = await _transcribe_message(update)
    if text is None:
        await _reply(update, "Entschuldigung, die Transkription ist fehlgeschlagen. Bitte versuche es erneut.")
        return WAITING_FOR_INPUT
    _log_received(update, text)
    return await _process_text(update, context, text)


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = await _transcribe_message(update)
    if text is None:
        await _reply(update, "Entschuldigung, die Transkription ist fehlgeschlagen. Bitte versuche es erneut.")
        return WAITING_FOR_INPUT
    _log_received(update, text)
    return await _process_text(update, context, text)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    doc: Document = update.message.document
    if doc.mime_type and doc.mime_type.startswith("image/"):
        file = await doc.get_file()
        image_bytes = await file.download_as_bytearray()
        description = await describe_image(bytes(image_bytes))
        _log_received(update, f"[document/image] {description}")
        return await _process_text(update, context, description)
    _log_received(update, f"[document] mime={doc.mime_type}")
    await _reply(update, 
        "Dieser Dateityp wird nicht unterst\u00fctzt. Nutze Text, Bilder oder Sprachnachrichten."
    )
    return WAITING_FOR_INPUT


async def handle_unsupported(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await _reply(update, 
        "Nur Text, Bilder und Sprachnachrichten werden unterst\u00fctzt."
    )
    return WAITING_FOR_INPUT


async def _process_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> int:
    context.user_data["last_raw_text"] = text
    event = await extract_event(text, today=_today_str())

    if event is None:
        await _reply(update, 
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
        await _reply(update, 
            f"Ich habe das Datum ({event.start_datetime.strftime('%d.%m.%Y %H:%M')}) erkannt. "
            "Wie soll der Termin hei\u00dfen?"
        )
        return AWAITING_DATE

    if not event.summary:
        context.user_data["partial_event"] = {}
        await _reply(update, 
            "Ich konnte leider keinen Termin erkennen. "
            "Wann soll der Termin stattfinden? (z.B. \u201eMorgen um 15 Uhr\u201c)"
        )
        return AWAITING_DATE

    if event.start_datetime is None:
        context.user_data["partial_event"] = {k: v for k, v in partial.items() if v is not None and k != "start_datetime"}
        await _reply(update, 
            f"Ich habe den Titel \u201e{event.summary}\u201c erkannt, aber wann soll der Termin stattfinden? "
            "(z.B. \u201eMorgen um 15 Uhr\u201c)"
        )
        return AWAITING_DATE

    if event.start_datetime.time() == datetime.min.time() and not event.is_all_day:
        event.is_all_day = True

    return await _confirm_and_create(update, context, event)


async def _get_text(update: Update) -> str:
    if update.message.text:
        _log_received(update, update.message.text)
        return update.message.text
    if update.message.voice or update.message.audio:
        text = await _transcribe_message(update)
        if text:
            _log_received(update, text)
        return text or ""
    return ""


async def handle_awaiting_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = await _get_text(update)
    if not text:
        await _reply(update, 
            "Entschuldigung, ich konnte die Sprachnachricht nicht verstehen. Bitte versuche es erneut."
        )
        return AWAITING_DATE
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
        await _reply(update, 
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
        await _reply(update, 
            f"Ich konnte keinen Titel in \u201e{text}\u201c erkennen. Wie soll der Termin hei\u00dfen?"
        )
        return AWAITING_DATE

    if not partial.get("start_datetime"):
        await _reply(update, 
            f"Ich habe den Titel \u201e{partial['summary']}\u201c erkannt, "
            "aber wann soll der Termin stattfinden? (z.B. \u201eMorgen um 15 Uhr\u201c)"
        )
        return AWAITING_DATE

    start_dt = datetime.fromisoformat(partial["start_datetime"])
    if start_dt.time() == datetime.min.time() and not partial.get("is_all_day"):
        partial["is_all_day"] = True

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

    await _reply(update, 
        f"Ich habe folgende Informationen extrahiert:\n\n" + "\n".join(lines) +
        "\n\nSoll ich den Termin erstellen? (Ja/Nein)",
        parse_mode="Markdown",
    )
    context.user_data["pending_event"] = event.model_dump()
    return AWAITING_CONFIRMATION


async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (await _get_text(update)).lower().strip()
    if not text:
        await _reply(update, 
            "Entschuldigung, ich konnte deine Antwort nicht verstehen. "
            "Soll ich den Termin erstellen? (Ja/Nein)"
        )
        return AWAITING_CONFIRMATION
    if text in ("ja", "yes", "y", "ok", "klar", "sicher", "\U0001f44d", "thumbs up", "daumen hoch"):
        event_data = context.user_data.get("pending_event")
        if event_data is None:
            await _reply(update, "Etwas ist schiefgelaufen. Bitte beginne von vorne.")
            return WAITING_FOR_INPUT
        event = CalendarEvent.model_validate(event_data)
        try:
            link = await create_event(event)
            msg = f"Termin *{event.summary}* wurde erfolgreich erstellt!"
            if link:
                msg += f"\n\nIm Kalender ansehen: {link}"
            await _reply(update, msg, parse_mode="Markdown")
        except Exception as e:
            logger.exception("Failed to create event")
            await _reply(update, 
                "Der Termin konnte nicht erstellt werden. Bitte sp\u00e4ter erneut versuchen."
            )
    else:
        await _reply(update, "OK, Termin nicht erstellt.")
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
                MessageHandler(filters.VOICE, handle_awaiting_date),
                MessageHandler(filters.AUDIO, handle_awaiting_date),
            ],
            AWAITING_CONFIRMATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_confirmation),
                MessageHandler(filters.VOICE, handle_confirmation),
                MessageHandler(filters.AUDIO, handle_confirmation),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),
        ],
        name="calendar_bot_conversation",
        persistent=False,
    )
