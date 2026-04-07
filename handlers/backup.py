import os
import zipfile
import tempfile
import html
import asyncio
import sqlite3
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from utils.config import OWNER_ID, LOG_CHAT_ID

DATA_DIR = "data"
DB_PATH = "data/bot.db"

INTERVAL = 6 * 60 * 60


def _is_owner(user_id: int) -> bool:
    return user_id in OWNER_ID


def _get_db():
    return sqlite3.connect(DB_PATH)


def _init_db():
    with _get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)


def _get_setting(key: str, default: str = "0") -> str:
    with _get_db() as db:
        cur = db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
        return row[0] if row else default


def _set_setting(key: str, value: str):
    with _get_db() as db:
        db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )


def _zip_data(zip_path: str):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(DATA_DIR):
            for f in files:
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, DATA_DIR)
                z.write(full_path, rel_path)


def _extract_zip(zip_path: str):
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(DATA_DIR)


async def run_backup(bot):
    now = datetime.now().strftime("%d-%m-%Y_%H-%M")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        zip_path = tmp.name

    _zip_data(zip_path)

    filename = f"backup_data_{now}.zip"

    with open(zip_path, "rb") as f:
        await bot.send_document(
            chat_id=LOG_CHAT_ID,
            document=f,
            filename=filename,
            caption=f"Auto backup\n<code>{filename}</code>",
            parse_mode="HTML"
        )

    os.remove(zip_path)


async def auto_backup_loop(app):
    await asyncio.sleep(10)

    while True:
        enabled = _get_setting("auto_backup", "0") == "1"

        if enabled:
            try:
                await run_backup(app.bot)
            except Exception:
                pass

        await asyncio.sleep(INTERVAL)


def start_auto_backup(app):
    _init_db()
    asyncio.create_task(auto_backup_loop(app))


async def backup_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user = update.effective_user

    if not msg or not user:
        return

    if not _is_owner(user.id):
        returnl

    status = await msg.reply_text("Creating backup...")

    try:
        now = datetime.now().strftime("%d-%m-%Y_%H-%M")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            zip_path = tmp.name

        _zip_data(zip_path)

        filename = f"backup_data_{now}.zip"

        with open(zip_path, "rb") as f:
            await context.bot.send_document(
                chat_id=LOG_CHAT_ID,
                document=f,
                filename=filename,
                caption=f"Backup completed\n<code>{filename}</code>",
                parse_mode="HTML"
            )

        os.remove(zip_path)

        await status.edit_text("Backup sent to log chat.")

    except Exception as e:
        await status.edit_text(
            f"Error:\n<code>{html.escape(str(e))}</code>",
            parse_mode="HTML"
        )


async def restore_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user = update.effective_user

    if not msg or not user:
        return

    if not _is_owner(user.id):
        return

    if not msg.reply_to_message or not msg.reply_to_message.document:
        return await msg.reply_text(
            "Reply to a .zip file with /restore",
            parse_mode="HTML"
        )

    doc = msg.reply_to_message.document

    if not doc.file_name.endswith(".zip"):
        return await msg.reply_text("File must be a .zip archive.")

    status = await msg.reply_text("Downloading and restoring...")

    try:
        file = await doc.get_file()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            zip_path = tmp.name

        await file.download_to_drive(zip_path)

        _extract_zip(zip_path)

        os.remove(zip_path)

        await status.edit_text("Restore completed.")

        await context.bot.send_message(
            chat_id=LOG_CHAT_ID,
            text="Data restore completed."
        )

    except Exception as e:
        await status.edit_text(
            f"Error:\n<code>{html.escape(str(e))}</code>",
            parse_mode="HTML"
        )


async def autobackup_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user = update.effective_user

    if not msg or not user:
        return

    if not _is_owner(user.id):
        return

    if not context.args:
        enabled = _get_setting("auto_backup", "0") == "1"
        status = "enabled" if enabled else "disabled"
        return await msg.reply_text(f"Auto backup is {status}")

    cmd = context.args[0].lower()

    if cmd == "enable":
        _set_setting("auto_backup", "1")
        return await msg.reply_text("Auto backup enabled")

    if cmd == "disable":
        _set_setting("auto_backup", "0")
        return await msg.reply_text("Auto backup disabled")

    return await msg.reply_text("Usage: /autobackup enable|disable")