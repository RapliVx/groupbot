import io
import os
import tempfile
import asyncio
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageOps
from telegram import Update
from telegram.ext import ContextTypes


FONT_REGULAR_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
]

FONT_BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
]


def _pick_font(paths: list[str], size: int):
    for path in paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                pass
    return ImageFont.load_default()


def _measure_text(draw: ImageDraw.ImageDraw, text: str, font) -> tuple[int, int]:
    if not text:
        return 0, 0
    box = draw.multiline_textbbox((0, 0), text, font=font, spacing=6)
    return box[2] - box[0], box[3] - box[1]


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int, max_lines: int) -> str:
    text = (text or "").strip()
    if not text:
        return ""

    words = text.split()
    if not words:
        return ""

    lines = []
    current = words[0]

    for word in words[1:]:
        trial = f"{current} {word}"
        w, _ = _measure_text(draw, trial, font)
        if w <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
            if len(lines) >= max_lines:
                break

    if len(lines) < max_lines and current:
        lines.append(current)

    joined = "\n".join(lines[:max_lines])

    while True:
        w, _ = _measure_text(draw, joined, font)
        if w <= max_width:
            break
        if len(joined) <= 3:
            break
        joined = joined[:-4].rstrip() + "..."

    if len(lines) == max_lines and " ".join(words) != joined.replace("\n", " "):
        if not joined.endswith("..."):
            if len(joined) > 3:
                joined = joined[:-3].rstrip() + "..."
            else:
                joined = "..."

    return joined


def _round_rect(draw: ImageDraw.ImageDraw, xy, radius: int, fill):
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def _load_avatar(avatar_bytes: Optional[bytes], size: int) -> Optional[Image.Image]:
    if not avatar_bytes:
        return None
    try:
        avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        avatar = ImageOps.fit(avatar, (size, size), method=Image.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, size, size), fill=255)
        avatar.putalpha(mask)
        return avatar
    except Exception:
        return None


def _render_quote_webp(
    author_name: str,
    text: str,
    reply_name: str,
    reply_text: str,
    avatar_bytes: Optional[bytes],
) -> str:
    width = 512
    height = 512
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    font_name = _pick_font(FONT_BOLD_CANDIDATES, 28)
    font_reply_name = _pick_font(FONT_BOLD_CANDIDATES, 18)
    font_text = _pick_font(FONT_REGULAR_CANDIDATES, 26)
    font_reply = _pick_font(FONT_REGULAR_CANDIDATES, 18)

    bubble_x = 20
    bubble_y = 20
    bubble_w = width - 40
    avatar_size = 64
    inner_pad = 22
    text_left = bubble_x + inner_pad + avatar_size + 16
    text_right = bubble_x + bubble_w - inner_pad
    text_width = text_right - text_left

    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1), (0, 0, 0, 0)))

    wrapped_main = _wrap_text(probe, text, font_text, text_width, 10)
    wrapped_reply = _wrap_text(probe, reply_text, font_reply, text_width - 24, 3) if reply_text else ""

    _, author_h = _measure_text(probe, author_name, font_name)
    _, main_h = _measure_text(probe, wrapped_main, font_text)

    reply_block_h = 0
    if wrapped_reply:
        _, reply_name_h = _measure_text(probe, reply_name, font_reply_name)
        _, reply_text_h = _measure_text(probe, wrapped_reply, font_reply)
        reply_block_h = 16 + reply_name_h + 6 + reply_text_h + 16

    content_h = max(avatar_size, author_h + 12 + reply_block_h + main_h)
    bubble_h = inner_pad * 2 + content_h
    bubble_h = min(bubble_h, height - 40)

    _round_rect(
        draw,
        (bubble_x, bubble_y, bubble_x + bubble_w, bubble_y + bubble_h),
        radius=28,
        fill=(34, 39, 46, 245),
    )

    avatar = _load_avatar(avatar_bytes, avatar_size)
    if avatar:
        canvas.alpha_composite(avatar, (bubble_x + inner_pad, bubble_y + inner_pad))
    else:
        fallback_x = bubble_x + inner_pad
        fallback_y = bubble_y + inner_pad
        draw.ellipse(
            (fallback_x, fallback_y, fallback_x + avatar_size, fallback_y + avatar_size),
            fill=(72, 84, 96, 255),
        )

    cursor_x = text_left
    cursor_y = bubble_y + inner_pad - 2

    draw.text(
        (cursor_x, cursor_y),
        author_name,
        font=font_name,
        fill=(151, 196, 255, 255),
    )
    cursor_y += author_h + 12

    if wrapped_reply:
        reply_x1 = cursor_x
        reply_y1 = cursor_y
        reply_x2 = bubble_x + bubble_w - inner_pad
        reply_y2 = reply_y1 + reply_block_h

        _round_rect(
            draw,
            (reply_x1, reply_y1, reply_x2, reply_y2),
            radius=18,
            fill=(49, 56, 66, 255),
        )

        draw.rounded_rectangle(
            (reply_x1 + 10, reply_y1 + 10, reply_x1 + 16, reply_y2 - 10),
            radius=3,
            fill=(151, 196, 255, 255),
        )

        draw.text(
            (reply_x1 + 28, reply_y1 + 10),
            reply_name,
            font=font_reply_name,
            fill=(151, 196, 255, 255),
        )

        draw.multiline_text(
            (reply_x1 + 28, reply_y1 + 10 + 24),
            wrapped_reply,
            font=font_reply,
            fill=(214, 220, 230, 255),
            spacing=6,
        )

        cursor_y = reply_y2 + 14

    draw.multiline_text(
        (cursor_x, cursor_y),
        wrapped_main,
        font=font_text,
        fill=(255, 255, 255, 255),
        spacing=8,
    )

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".webp")
    tmp.close()
    canvas.save(tmp.name, "WEBP", lossless=True, quality=100, method=6)
    return tmp.name


async def _download_avatar_bytes(bot, user_id: int) -> Optional[bytes]:
    try:
        photos = await bot.get_user_profile_photos(user_id, limit=1)
        if not photos.photos:
            return None
        file_id = photos.photos[0][-1].file_id
        tg_file = await bot.get_file(file_id)
        data = await tg_file.download_as_bytearray()
        return bytes(data) if data else None
    except Exception:
        return None


async def q_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return

    target = msg.reply_to_message
    if not target:
        return await msg.reply_text("Reply ke pesan yang mau dijadiin sticker.")

    source_user = target.from_user
    if not source_user:
        return await msg.reply_text("User tidak ditemukan.")

    text = (target.text or target.caption or "").strip()
    if not text:
        return await msg.reply_text("Pesan itu nggak punya teks.")

    if len(text) > 1200:
        text = text[:1200].rstrip() + "..."

    reply_name = ""
    reply_text = ""
    if target.reply_to_message and target.reply_to_message.from_user:
        reply_name = target.reply_to_message.from_user.first_name or "User"
        reply_text = (target.reply_to_message.text or target.reply_to_message.caption or "").strip()
        if len(reply_text) > 220:
            reply_text = reply_text[:220].rstrip() + "..."

    author_name = source_user.full_name or source_user.first_name or "User"

    wait = await msg.reply_text("Bentar, lagi bikin sticker...")

    avatar_bytes = await _download_avatar_bytes(context.bot, source_user.id)

    try:
        sticker_path = await asyncio.to_thread(
            _render_quote_webp,
            author_name,
            text,
            reply_name,
            reply_text,
            avatar_bytes,
        )

        with open(sticker_path, "rb") as f:
            await context.bot.send_sticker(
                chat_id=msg.chat_id,
                sticker=f,
                reply_to_message_id=target.message_id,
            )
    except Exception as e:
        await wait.edit_text(f"Gagal bikin sticker: {e}")
        return
    finally:
        try:
            if "sticker_path" in locals() and sticker_path and os.path.exists(sticker_path):
                os.remove(sticker_path)
        except Exception:
            pass

    try:
        await wait.delete()
    except Exception:
        pass