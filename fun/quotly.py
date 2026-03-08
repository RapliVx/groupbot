import io
import os
import tempfile
import asyncio
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageOps
from telegram import Update
from telegram.ext import ContextTypes


FONT_REGULAR_CANDIDATES = [
    "/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-Regular.ttf",
    "/usr/share/fonts/truetype/roboto/Roboto-Regular.ttf",
    "/usr/share/fonts/TTF/Roboto-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/opentype/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
]

FONT_BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-Bold.ttf",
    "/usr/share/fonts/truetype/roboto/Roboto-Bold.ttf",
    "/usr/share/fonts/TTF/Roboto-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/opentype/noto/NotoSans-Bold.ttf",
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


def _measure_multiline(draw: ImageDraw.ImageDraw, text: str, font, spacing: int = 6) -> tuple[int, int]:
    if not text:
        return 0, 0
    box = draw.multiline_textbbox((0, 0), text, font=font, spacing=spacing)
    return box[2] - box[0], box[3] - box[1]


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int, max_lines: int) -> str:
    raw = (text or "").replace("\r", "").strip()
    if not raw:
        return ""

    paragraphs = raw.split("\n")
    out_lines: list[str] = []

    for para in paragraphs:
        words = para.split()
        if not words:
            if len(out_lines) < max_lines:
                out_lines.append("")
            continue

        current = words[0]

        for word in words[1:]:
            trial = f"{current} {word}"
            w = draw.textlength(trial, font=font)
            if w <= max_width:
                current = trial
            else:
                out_lines.append(current)
                current = word
                if len(out_lines) >= max_lines:
                    break

        if len(out_lines) < max_lines:
            out_lines.append(current)

        if len(out_lines) >= max_lines:
            break

    wrapped = "\n".join(out_lines[:max_lines]).strip()

    original_joined = " ".join(raw.split())
    current_joined = " ".join(wrapped.split())

    if current_joined != original_joined:
        while True:
            candidate = wrapped.rstrip()
            if len(candidate) <= 3:
                wrapped = "..."
                break
            if candidate.endswith("..."):
                break
            candidate = candidate[:-1].rstrip() + "..."
            w, _ = _measure_multiline(draw, candidate, font, spacing=6)
            if w <= max_width:
                wrapped = candidate
                break

    return wrapped


def _load_avatar(avatar_bytes: Optional[bytes], size: int) -> Optional[Image.Image]:
    if not avatar_bytes:
        return None
    try:
        avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        avatar = ImageOps.fit(
            avatar,
            (size, size),
            method=Image.LANCZOS,
            centering=(0.5, 0.38),
        )
        mask = Image.new("L", (size, size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, size, size), fill=255)
        avatar.putalpha(mask)
        return avatar
    except Exception:
        return None


def _make_fallback_avatar(name: str, size: int) -> Image.Image:
    avatar = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(avatar)
    draw.ellipse((0, 0, size, size), fill=(96, 72, 141, 255))

    initials = (name or "U").strip()[:1].upper()
    font = _pick_font(FONT_BOLD_CANDIDATES, int(size * 0.42))
    box = draw.textbbox((0, 0), initials, font=font)
    tw = box[2] - box[0]
    th = box[3] - box[1]
    draw.text(
        ((size - tw) / 2, (size - th) / 2 - 3),
        initials,
        font=font,
        fill=(255, 255, 255, 255),
    )
    return avatar


def _render_quote_webp(author_name: str, text: str, avatar_bytes: Optional[bytes]) -> str:
    max_canvas_w = 512
    max_canvas_h = 512

    avatar_size = 62
    bubble_pad_x = 22
    bubble_pad_y = 18
    overlap = 18
    max_text_width = 310

    font_name = _pick_font(FONT_BOLD_CANDIDATES, 22)
    font_text = _pick_font(FONT_REGULAR_CANDIDATES, 24)

    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1), (0, 0, 0, 0)))

    wrapped_text = _wrap_text(probe, text, font_text, max_text_width, 8)
    if not wrapped_text:
        wrapped_text = "..."

    name_w, name_h = _measure_multiline(probe, author_name, font_name, spacing=4)
    text_w, text_h = _measure_multiline(probe, wrapped_text, font_text, spacing=6)

    bubble_w = max(name_w, text_w) + bubble_pad_x * 2
    bubble_h = bubble_pad_y * 2 + name_h + 8 + text_h

    bubble_w = min(bubble_w, max_canvas_w - 24 - (avatar_size // 2))
    bubble_h = min(bubble_h, max_canvas_h - 24)

    bubble_x = avatar_size - overlap + 10
    bubble_y = 12

    canvas_w = min(max_canvas_w, bubble_x + bubble_w + 12)
    canvas_h = min(max_canvas_h, bubble_y + bubble_h + 12)

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    draw.rounded_rectangle(
        (bubble_x, bubble_y, bubble_x + bubble_w, bubble_y + bubble_h),
        radius=24,
        fill=(63, 45, 92, 255),
    )

    avatar = _load_avatar(avatar_bytes, avatar_size)
    if avatar is None:
        avatar = _make_fallback_avatar(author_name, avatar_size)

    avatar_x = 4
    avatar_y = bubble_y + 8
    canvas.alpha_composite(avatar, (avatar_x, avatar_y))

    text_x = bubble_x + bubble_pad_x
    name_y = bubble_y + bubble_pad_y - 1
    body_y = name_y + name_h + 8

    draw.text(
        (text_x, name_y),
        author_name,
        font=font_name,
        fill=(198, 149, 255, 255),
    )

    draw.multiline_text(
        (text_x, body_y),
        wrapped_text,
        font=font_text,
        fill=(255, 255, 255, 255),
        spacing=6,
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

    if len(text) > 400:
        text = text[:400].rstrip() + "..."

    author_name = (
        (source_user.first_name or "").strip()
        or (source_user.full_name or "").strip()
        or (f"@{source_user.username}" if source_user.username else "")
        or "User"
    )

    wait = await msg.reply_text("Bentar, lagi bikin sticker...")

    avatar_bytes = await _download_avatar_bytes(context.bot, source_user.id)

    try:
        sticker_path = await asyncio.to_thread(
            _render_quote_webp,
            author_name,
            text,
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