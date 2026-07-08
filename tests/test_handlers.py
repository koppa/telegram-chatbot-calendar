from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot.handlers import handle_confirmation, _confirm_and_create


def _make_update(text: str | None = None, voice: bool = False) -> MagicMock:
    update = MagicMock()
    msg = MagicMock()
    msg.text = text
    msg.reply_text = AsyncMock()
    if voice:
        msg.voice = MagicMock()
        msg.audio = None
    else:
        msg.voice = None
        msg.audio = None
    msg.effective_user = MagicMock()
    msg.effective_user.username = "testuser"
    update.message = msg
    update.effective_user = msg.effective_user
    return update


def _make_context(pending_event: dict | None = None) -> MagicMock:
    context = MagicMock()
    context.user_data = {"pending_event": pending_event} if pending_event else {}
    return context


PENDING_EVENT = {
    "summary": "Medikamente nehmen",
    "start_datetime": "2026-07-09T07:00:00",
    "end_datetime": None,
    "duration_minutes": 15,
    "location": None,
    "description": None,
    "is_all_day": False,
}


class TestHandleConfirmationYes:
    @patch("src.bot.handlers.create_event")
    async def test_yes_creates_event(self, mock_create):
        mock_create.return_value = "https://calendar.google.com/event?id=123"
        update = _make_update("ja")
        context = _make_context(PENDING_EVENT)
        result = await handle_confirmation(update, context)
        mock_create.assert_called_once()
        msg = update.message.reply_text.call_args[0][0]
        assert "erfolgreich erstellt" in msg

    @patch("src.bot.handlers.create_event")
    async def test_sicher_creates_event(self, mock_create):
        mock_create.return_value = "https://calendar.google.com/event?id=456"
        update = _make_update("sicher")
        context = _make_context(PENDING_EVENT)
        result = await handle_confirmation(update, context)
        mock_create.assert_called_once()

    @patch("src.bot.handlers.create_event")
    async def test_yes_clears_context(self, mock_create):
        mock_create.return_value = "https://calendar.google.com/event?id=789"
        update = _make_update("ja")
        context = _make_context(PENDING_EVENT)
        await handle_confirmation(update, context)
        assert not context.user_data


class TestHandleConfirmationNo:
    async def test_nein_cancels(self):
        update = _make_update("nein")
        context = _make_context(PENDING_EVENT)
        await handle_confirmation(update, context)
        msg = update.message.reply_text.call_args[0][0]
        assert "nicht erstellt" in msg

    async def test_no_cancels(self):
        update = _make_update("No")
        context = _make_context(PENDING_EVENT)
        await handle_confirmation(update, context)
        msg = update.message.reply_text.call_args[0][0]
        assert "nicht erstellt" in msg

    async def test_nicht_cancels(self):
        update = _make_update("nicht")
        context = _make_context(PENDING_EVENT)
        await handle_confirmation(update, context)
        msg = update.message.reply_text.call_args[0][0]
        assert "nicht erstellt" in msg

    async def test_nein_clears_context(self):
        update = _make_update("nein")
        context = _make_context(PENDING_EVENT)
        await handle_confirmation(update, context)
        assert not context.user_data


class TestHandleConfirmationModify:
    @patch("src.bot.handlers.modify_event")
    async def test_modification_merges_changes(self, mock_modify):
        mock_modify.return_value = {
            "start_datetime": "2026-07-09T18:00:00",
            "duration_minutes": 30,
        }
        update = _make_update("Später am Abend, 30 Minuten")
        context = _make_context(PENDING_EVENT)
        await handle_confirmation(update, context)
        mock_modify.assert_called_once()
        assert context.user_data["pending_event"]["start_datetime"] == datetime(2026, 7, 9, 18, 0)
        assert context.user_data["pending_event"]["duration_minutes"] == 30
        assert context.user_data["pending_event"]["summary"] == "Medikamente nehmen"

    @patch("src.bot.handlers.modify_event")
    async def test_modification_shows_thinking_message(self, mock_modify):
        mock_modify.return_value = {"start_datetime": "2026-07-09T20:00:00"}
        update = _make_update("mach später")
        context = _make_context(PENDING_EVENT)
        await handle_confirmation(update, context)
        assert update.message.reply_text.call_count >= 1
        first_msg = update.message.reply_text.call_args_list[0][0][0]
        assert "überlege" in first_msg.lower()

    @patch("src.bot.handlers.modify_event")
    async def test_modification_passes_original_text(self, mock_modify):
        mock_modify.return_value = {"start_datetime": "2026-07-10T07:00:00"}
        update = _make_update("Verschiebe auf morgen")
        context = _make_context(PENDING_EVENT)
        await handle_confirmation(update, context)
        call_args = mock_modify.call_args
        assert call_args[0][1] == "Verschiebe auf morgen"

    @patch("src.bot.handlers.modify_event")
    async def test_unclear_modification_reasks(self, mock_modify):
        mock_modify.return_value = None
        update = _make_update("blabla unverständlich")
        context = _make_context(PENDING_EVENT)
        await handle_confirmation(update, context)
        last_msg = update.message.reply_text.call_args_list[-1][0][0]
        assert "Änderungswünsche nicht verstanden" in last_msg
        assert "Ja/Nein" in last_msg

    @patch("src.bot.handlers.modify_event")
    async def test_modification_preserves_event_when_unclear(self, mock_modify):
        mock_modify.return_value = None
        update = _make_update("???!")
        context = _make_context(PENDING_EVENT)
        await handle_confirmation(update, context)
        assert context.user_data["pending_event"] == PENDING_EVENT


class TestHandleConfirmationEdgeCases:
    async def test_empty_text_reasks(self):
        update = _make_update("")
        context = _make_context(PENDING_EVENT)
        await handle_confirmation(update, context)
        msg = update.message.reply_text.call_args[0][0]
        assert "nicht verstehen" in msg.lower()
        assert "Ja/Nein" in msg

    async def test_missing_pending_event_on_yes(self):
        update = _make_update("ja")
        context = _make_context(None)
        await handle_confirmation(update, context)
        msg = update.message.reply_text.call_args[0][0]
        assert "schiefgelaufen" in msg

    async def test_missing_pending_event_on_modify(self):
        update = _make_update("änder das bitte")
        context = _make_context(None)
        await handle_confirmation(update, context)
        msg = update.message.reply_text.call_args[0][0]
        assert "schiefgelaufen" in msg

    @patch("src.bot.handlers.modify_event")
    async def test_modify_all_day_detection(self, mock_modify):
        mock_modify.return_value = {"start_datetime": "2026-07-10T00:00:00"}
        update = _make_update("mach ganztägig am 10.7.")
        context = _make_context(PENDING_EVENT)
        await handle_confirmation(update, context)
        assert context.user_data["pending_event"]["is_all_day"] is True
