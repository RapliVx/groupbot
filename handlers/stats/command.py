import asyncio
import html

from telegram import Update
from telegram.ext import ContextTypes

from .system_info import gather_system_stats, measure_network_speed
from .renderer import render_dashboard
from .formatting import build_fallback_text


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return

    stats = await asyncio.to_thread(gather_system_stats)
    net_speed = await measure_network_speed()
    bio = await asyncio.to_thread(render_dashboard, stats, net_speed)

    if bio:
        return await msg.reply_photo(photo=bio)

    out = "<b>System Stats</b>\n\n<pre>" + html.escape(build_fallback_text(stats)) + "</pre>"
    return await msg.reply_text(out, parse_mode="HTML")