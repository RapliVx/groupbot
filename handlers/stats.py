import os
import time
import asyncio
import functools
import html
import shutil
import platform
import io
import logging
import socket
import subprocess

from telegram import Update
from telegram.ext import ContextTypes

from utils.fonts import get_font

logger = logging.getLogger(__name__)

try:
    import psutil
except Exception:
    psutil = None

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:
    Image = None
    ImageDraw = None
    ImageFont = None

try:
    from importlib.metadata import version as pkg_version
except Exception:
    pkg_version = None


def humanize_bytes(n: int) -> str:
    try:
        f = float(n)
    except Exception:
        return "N/A"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if f < 1024 or unit == "TB":
            return f"{f:.1f}{unit}"
        f /= 1024.0
    return f"{f:.1f}B"


def _humanize_freq(mhz):
    try:
        mhz = float(mhz)
    except Exception:
        return "N/A"
    if mhz >= 1000:
        return f"{mhz / 1000:.2f} GHz"
    return f"{mhz:.0f} MHz"


def _shorten(text, limit=64):
    text = str(text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _get_os_name():
    try:
        if os.path.exists("/etc/os-release"):
            with open("/etc/os-release") as f:
                os_info = {}
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        os_info[k] = v.strip('"')
            pretty = os_info.get("PRETTY_NAME")
            if pretty:
                return pretty
            return f"{os_info.get('NAME', 'Linux')} {os_info.get('VERSION', '')}".strip()
        return (platform.system() + " " + platform.release()).strip()
    except Exception:
        return "Linux"


def get_pretty_uptime():
    try:
        with open("/proc/uptime", "r") as f:
            up_seconds = float(f.readline().split()[0])
            secs = int(up_seconds)
            days, rem = divmod(secs, 86400)
            hours, rem = divmod(rem, 3600)
            minutes, seconds = divmod(rem, 60)
            parts = []
            if days:
                parts.append(f"{days}d")
            if hours:
                parts.append(f"{hours}h")
            if minutes:
                parts.append(f"{minutes}m")
            if not parts:
                parts.append(f"{seconds}s")
            return " ".join(parts)
    except Exception:
        pass

    try:
        if psutil:
            boot = psutil.boot_time()
            secs = int(time.time() - boot)
            days, rem = divmod(secs, 86400)
            hours, rem = divmod(rem, 3600)
            minutes, seconds = divmod(rem, 60)
            parts = []
            if days:
                parts.append(f"{days}d")
            if hours:
                parts.append(f"{hours}h")
            if minutes:
                parts.append(f"{minutes}m")
            if not parts:
                parts.append(f"{seconds}s")
            return " ".join(parts)
    except Exception:
        pass

    return "N/A"


def _safe_pct(x):
    try:
        v = float(x)
    except Exception:
        return 0.0
    if v < 0:
        return 0.0
    if v > 100:
        return 100.0
    return v


def _get_pkg_version(*names):
    if not pkg_version:
        return "N/A"
    for name in names:
        try:
            return pkg_version(name)
        except Exception:
            pass
    return "N/A"


def _run_version_cmd(cmd):
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=1.5
        )
        out = (proc.stdout or proc.stderr or "").strip()
        if not out:
            return "N/A"
        return out.splitlines()[0].strip()
    except Exception:
        return "N/A"


def _get_node_version():
    out = _run_version_cmd(["node", "-v"])
    return out if out else "N/A"


def _get_deno_version():
    out = _run_version_cmd(["deno", "--version"])
    if out == "N/A":
        return "N/A"
    parts = out.split()
    if len(parts) >= 2 and parts[0].lower() == "deno":
        return parts[1]
    return out


def _get_ytdlp_version():
    ver = _get_pkg_version("yt-dlp-ejs", "yt-dlp")
    if ver != "N/A":
        return ver
    try:
        from yt_dlp.version import __version__ as yt_dlp_version
        return yt_dlp_version
    except Exception:
        return "N/A"


def _get_runtime_versions():
    return {
        "ytdlp": _get_ytdlp_version(),
        "node": _get_node_version(),
        "deno": _get_deno_version(),
        "ptb": _get_pkg_version("python-telegram-bot"),
        "aiohttp": _get_pkg_version("aiohttp"),
        "requests": _get_pkg_version("requests"),
        "pillow": _get_pkg_version("Pillow"),
        "psutil": _get_pkg_version("psutil"),
        "aiofiles": _get_pkg_version("aiofiles"),
    }


@functools.lru_cache(maxsize=32)
def _load_font(size: int, mono: bool = False):
    if not ImageFont:
        return None
    if mono:
        return get_font(["DejaVuSansMono.ttf", "LiberationMono-Regular.ttf", "FreeMono.ttf"], size)
    return get_font(["DejaVuSans.ttf", "LiberationSans-Regular.ttf"], size)


def _gather_stats():
    now = time.time()

    cpu_cores = os.cpu_count() or 0
    try:
        cpu_load = psutil.cpu_percent(interval=0.15) if psutil else 0.0
    except Exception as e:
        logger.error(f"Failed to gather CPU load: {e}", exc_info=True)
        cpu_load = 0.0

    try:
        freq = psutil.cpu_freq() if psutil else None
        cpu_freq = _humanize_freq(freq.current) if freq else "N/A"
    except Exception as e:
        logger.error(f"Failed to gather CPU freq: {e}", exc_info=True)
        cpu_freq = "N/A"

    ram_total = ram_used = ram_free = 0
    ram_pct = 0.0
    try:
        if psutil:
            vm = psutil.virtual_memory()
            ram_total = int(vm.total)
            ram_used = int(vm.used)
            ram_free = int(vm.available)
            ram_pct = float(vm.percent)
        else:
            mem = {}
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    k, v = line.split(":", 1)
                    mem[k.strip()] = int(v.strip().split()[0]) * 1024
            ram_total = int(mem.get("MemTotal", 0))
            ram_free = int(mem.get("MemAvailable", mem.get("MemFree", 0)))
            ram_used = int(max(0, ram_total - ram_free))
            ram_pct = (ram_used / ram_total * 100) if ram_total else 0.0
    except Exception as e:
        logger.error(f"Failed to gather RAM stats: {e}", exc_info=True)

    swap_total = swap_used = 0
    swap_pct = 0.0
    try:
        if psutil:
            sw = psutil.swap_memory()
            swap_total = int(sw.total)
            swap_used = int(sw.used)
            swap_pct = float(sw.percent)
    except Exception as e:
        logger.error(f"Failed to gather Swap stats: {e}", exc_info=True)

    disk_total = disk_used = disk_free = 0
    disk_pct = 0.0
    try:
        st = shutil.disk_usage("/")
        disk_total = int(st.total)
        disk_free = int(st.free)
        disk_used = int(st.total - st.free)
        disk_pct = (disk_used / disk_total * 100) if disk_total else 0.0
    except Exception as e:
        logger.error(f"Failed to gather Disk stats: {e}", exc_info=True)

    rx = tx = 0
    try:
        if psutil:
            net = psutil.net_io_counters()
            rx = int(net.bytes_recv)
            tx = int(net.bytes_sent)
    except Exception as e:
        logger.error(f"Failed to gather Network stats: {e}", exc_info=True)

    os_name = _get_os_name()
    kernel = platform.release() or "N/A"
    pyver = platform.python_version() or "N/A"
    uptime = get_pretty_uptime()
    hostname = socket.gethostname() or platform.node() or "N/A"
    runtime = _get_runtime_versions()

    return {
        "ts": now,
        "cpu": {"cores": cpu_cores or "N/A", "load": float(cpu_load), "freq": cpu_freq},
        "ram": {"total": ram_total, "used": ram_used, "free": ram_free, "pct": float(ram_pct)},
        "swap": {"total": swap_total, "used": swap_used, "pct": float(swap_pct)},
        "disk": {"total": disk_total, "used": disk_used, "free": disk_free, "pct": float(disk_pct)},
        "net": {"rx": rx, "tx": tx},
        "sys": {
            "hostname": hostname,
            "os": os_name,
            "kernel": kernel,
            "python": pyver,
            "uptime": uptime,
        },
        "runtime": runtime,
    }


def _draw_round_rect(draw, xy, r, fill=None, outline=None, width=1):
    x0, y0, x1, y1 = xy
    try:
        draw.rounded_rectangle([x0, y0, x1, y1], radius=r, fill=fill, outline=outline, width=width)
        return
    except Exception:
        draw.rectangle([x0, y0, x1, y1], fill=fill, outline=outline, width=width)


def _bar(draw, x, y, w, h, pct, bg, fg, border, r=10):
    pct = _safe_pct(pct)
    _draw_round_rect(draw, (x, y, x + w, y + h), r, fill=bg, outline=border, width=1)
    fw = int(round(w * (pct / 100.0)))
    if fw > 0:
        _draw_round_rect(draw, (x, y, x + fw, y + h), r, fill=fg, outline=None, width=0)


async def _measure_net_speed():
    if not psutil:
        return 0.0, 0.0
    try:
        pio = psutil.net_io_counters()
        rx0b = int(pio.bytes_recv)
        tx0b = int(pio.bytes_sent)
        t0 = time.time()
        await asyncio.sleep(0.25)
        pio2 = psutil.net_io_counters()
        rx1b = int(pio2.bytes_recv)
        tx1b = int(pio2.bytes_sent)
        dt = max(0.001, time.time() - t0)
        rxps = (rx1b - rx0b) / dt
        txps = (tx1b - tx0b) / dt
        return rxps, txps
    except Exception:
        return 0.0, 0.0


def _render_dashboard_sync(stats, net_speed=(0.0, 0.0)):
    if not Image or not ImageDraw or not ImageFont:
        return None

    W, H = 1920, 1080
    S = 1.5

    bg0 = (12, 14, 18)
    bg1 = (18, 21, 28)
    card = (22, 26, 35)
    card2 = (26, 31, 42)
    border = (48, 56, 74)
    text = (232, 236, 243)
    muted = (160, 170, 190)

    bar_bg = (18, 22, 30)
    bar_fg = (90, 170, 255)
    bar_fg2 = (255, 140, 110)

    img = Image.new("RGB", (W, H), bg0)
    d = ImageDraw.Draw(img)

    for yy in range(H):
        t = yy / float(H - 1)
        r = int(bg0[0] * (1 - t) + bg1[0] * t)
        g = int(bg0[1] * (1 - t) + bg1[1] * t)
        b = int(bg0[2] * (1 - t) + bg1[2] * t)
        d.line([(0, yy), (W, yy)], fill=(r, g, b))

    f_title = _load_font(int(30 * S), mono=False)
    f_h = _load_font(int(20 * S), mono=False)
    f = _load_font(int(18 * S), mono=False)
    f_mono = _load_font(int(18 * S), mono=True)
    f_small = _load_font(int(14 * S), mono=False)
    f_small_mono = _load_font(int(14 * S), mono=True)
    f_tiny = _load_font(int(12 * S), mono=False)

    pad = int(28 * S)
    gap = int(18 * S)

    d.text((pad, int(pad - 2 * S)), "System Stats", font=f_title, fill=text)

    x0 = pad
    y0 = pad + int(78 * S)
    col_gap = gap
    col_w = (W - pad * 2 - col_gap) // 2
    left_x = x0
    right_x = x0 + col_w + col_gap

    top_h = int(250 * S)
    bottom_h = H - y0 - top_h - gap

    cpu_card = (left_x, y0, left_x + col_w, y0 + top_h)
    sys_card = (right_x, y0, right_x + col_w, y0 + top_h)
    res_card = (left_x, y0 + top_h + gap, left_x + col_w, y0 + top_h + gap + bottom_h)
    net_card = (right_x, y0 + top_h + gap, right_x + col_w, y0 + top_h + gap + bottom_h)

    for rect, fillc in ((cpu_card, card), (sys_card, card), (res_card, card2), (net_card, card2)):
        _draw_round_rect(d, rect, int(18 * S), fill=fillc, outline=border, width=1)

    cx0, cy0, cx1, cy1 = cpu_card
    d.text((cx0 + int(18 * S), cy0 + int(16 * S)), "CPU", font=f_h, fill=text)

    cpu = stats["cpu"]
    cpu_load = _safe_pct(cpu["load"])
    d.text((cx0 + int(18 * S), cy0 + int(56 * S)), f"Cores: {cpu['cores']}", font=f, fill=muted)
    d.text((cx0 + int(18 * S), cy0 + int(80 * S)), f"Freq : {cpu['freq']}", font=f, fill=muted)

    bar_x = cx0 + int(18 * S)
    bar_y = cy0 + int(118 * S)
    bar_w = (cx1 - cx0) - int(36 * S)
    bar_h = int(22 * S)
    _bar(d, bar_x, bar_y, bar_w, bar_h, cpu_load, bar_bg, bar_fg, border, r=int(11 * S))
    d.text((bar_x, bar_y + int(30 * S)), f"Load: {cpu_load:.1f}%", font=f_mono, fill=text)

    try:
        if psutil:
            la = os.getloadavg()
            d.text(
                (bar_x, bar_y + int(56 * S)),
                f"LoadAvg: {la[0]:.2f} {la[1]:.2f} {la[2]:.2f}",
                font=f_small_mono,
                fill=muted
            )
    except Exception:
        pass

    sx0, sy0, sx1, sy1 = sys_card
    d.text((sx0 + int(18 * S), sy0 + int(16 * S)), "System + Runtime", font=f_h, fill=text)

    sysi = stats["sys"]
    runtime = stats["runtime"]

    sys_lines = [
        f"Host    : {_shorten(sysi['hostname'], 56)}",
        f"OS      : {_shorten(sysi['os'], 56)}",
        f"Kernel  : {sysi['kernel']}",
        f"Python  : {sysi['python']}",
        f"Uptime  : {sysi['uptime']}",
        f"Node    : {runtime['node']}",
        f"Deno    : {runtime['deno']}",
        f"yt-dlp  : {runtime['ytdlp']}",
        f"PTB     : {runtime['ptb']}",
        f"HTTP    : aiohttp {runtime['aiohttp']} • requests {runtime['requests']}",
        f"Core    : Pillow {runtime['pillow']} • psutil {runtime['psutil']} • aiofiles {runtime['aiofiles']}",
    ]

    sys_y = sy0 + int(52 * S)
    sys_step = int(16 * S)
    for line in sys_lines:
        d.text((sx0 + int(18 * S), sys_y), line, font=f_tiny, fill=muted)
        sys_y += sys_step

    rx0, ry0, rx1, ry1 = res_card
    d.text((rx0 + int(18 * S), ry0 + int(16 * S)), "Memory + Disk", font=f_h, fill=text)

    ram = stats["ram"]
    ram_pct = _safe_pct(ram["pct"])
    d.text((rx0 + int(18 * S), ry0 + int(58 * S)), "RAM", font=f, fill=text)
    d.text((rx0 + int(90 * S), ry0 + int(58 * S)), f"{humanize_bytes(ram['used'])} / {humanize_bytes(ram['total'])}", font=f_mono, fill=muted)
    _bar(d, rx0 + int(18 * S), ry0 + int(86 * S), (rx1 - rx0) - int(36 * S), int(22 * S), ram_pct, bar_bg, bar_fg, border, r=int(11 * S))
    d.text((rx0 + int(18 * S), ry0 + int(114 * S)), f"{ram_pct:.1f}%", font=f_mono, fill=text)

    swap = stats["swap"]
    swap_total = int(swap["total"] or 0)
    swap_pct = _safe_pct(swap["pct"])
    d.text((rx0 + int(18 * S), ry0 + int(148 * S)), "Swap", font=f, fill=text)
    if swap_total > 0:
        d.text((rx0 + int(90 * S), ry0 + int(148 * S)), f"{humanize_bytes(swap['used'])} / {humanize_bytes(swap['total'])}", font=f_mono, fill=muted)
        _bar(d, rx0 + int(18 * S), ry0 + int(176 * S), (rx1 - rx0) - int(36 * S), int(18 * S), swap_pct, bar_bg, bar_fg2, border, r=int(9 * S))
        d.text((rx0 + int(18 * S), ry0 + int(198 * S)), f"{swap_pct:.1f}%", font=f_small_mono, fill=muted)
    else:
        d.text((rx0 + int(90 * S), ry0 + int(148 * S)), "N/A", font=f_mono, fill=muted)

    disk = stats["disk"]
    disk_pct = _safe_pct(disk["pct"])
    d.text((rx0 + int(18 * S), ry0 + int(232 * S)), "Disk (/)", font=f, fill=text)
    d.text((rx0 + int(110 * S), ry0 + int(232 * S)), f"{humanize_bytes(disk['used'])} / {humanize_bytes(disk['total'])}", font=f_mono, fill=muted)
    _bar(d, rx0 + int(18 * S), ry0 + int(260 * S), (rx1 - rx0) - int(36 * S), int(22 * S), disk_pct, bar_bg, bar_fg, border, r=int(11 * S))
    d.text((rx0 + int(18 * S), ry0 + int(288 * S)), f"Used {disk_pct:.1f}% • Free {humanize_bytes(disk['free'])}", font=f_small_mono, fill=muted)

    nx0, ny0, nx1, ny1 = net_card
    d.text((nx0 + int(18 * S), ny0 + int(16 * S)), "Network", font=f_h, fill=text)

    rx = stats["net"]["rx"]
    tx = stats["net"]["tx"]

    d.text((nx0 + int(18 * S), ny0 + int(58 * S)), f"RX Total: {humanize_bytes(rx)}", font=f_mono, fill=muted)
    d.text((nx0 + int(18 * S), ny0 + int(82 * S)), f"TX Total: {humanize_bytes(tx)}", font=f_mono, fill=muted)

    try:
        rxps, txps = net_speed

        d.text((nx0 + int(18 * S), ny0 + int(120 * S)), "Speed", font=f, fill=text)
        d.text((nx0 + int(18 * S), ny0 + int(144 * S)), f"RX/s: {humanize_bytes(int(rxps))}/s", font=f_mono, fill=muted)
        d.text((nx0 + int(18 * S), ny0 + int(168 * S)), f"TX/s: {humanize_bytes(int(txps))}/s", font=f_mono, fill=muted)

        peak = max(rxps, txps, 1.0)
        rxp = min(100.0, (rxps / peak) * 100.0)
        txp = min(100.0, (txps / peak) * 100.0)

        d.text((nx0 + int(18 * S), ny0 + int(206 * S)), "RX", font=f_small, fill=text)
        _bar(d, nx0 + int(58 * S), ny0 + int(206 * S), (nx1 - nx0) - int(76 * S), int(16 * S), rxp, bar_bg, bar_fg, border, r=int(8 * S))

        d.text((nx0 + int(18 * S), ny0 + int(234 * S)), "TX", font=f_small, fill=text)
        _bar(d, nx0 + int(58 * S), ny0 + int(234 * S), (nx1 - nx0) - int(76 * S), int(16 * S), txp, bar_bg, bar_fg2, border, r=int(8 * S))
    except Exception:
        pass

    bio = io.BytesIO()
    bio.name = "stats.png"
    img.save(bio, format="PNG", compress_level=3)
    bio.seek(0)
    return bio


def _fallback_text(stats):
    cpu = stats["cpu"]
    ram = stats["ram"]
    swap = stats["swap"]
    disk = stats["disk"]
    net = stats["net"]
    sysi = stats["sys"]
    runtime = stats["runtime"]

    lines = []
    lines.append("System Stats")
    lines.append("")
    lines.append(f"Host: {sysi['hostname']}")
    lines.append(f"OS: {sysi['os']}")
    lines.append(f"Kernel: {sysi['kernel']}")
    lines.append(f"Python: {sysi['python']}")
    lines.append(f"Uptime: {sysi['uptime']}")
    lines.append("")
    lines.append(f"CPU: {cpu['load']:.1f}% | Cores: {cpu['cores']} | Freq: {cpu['freq']}")
    lines.append(f"RAM: {humanize_bytes(ram['used'])}/{humanize_bytes(ram['total'])} ({ram['pct']:.1f}%)")
    if swap["total"]:
        lines.append(f"SWAP: {humanize_bytes(swap['used'])}/{humanize_bytes(swap['total'])} ({swap['pct']:.1f}%)")
    else:
        lines.append("SWAP: N/A")
    lines.append(f"DISK(/): {humanize_bytes(disk['used'])}/{humanize_bytes(disk['total'])} (used {disk['pct']:.1f}%)")
    lines.append(f"DISK FREE: {humanize_bytes(disk['free'])}")
    lines.append(f"NET: RX {humanize_bytes(net['rx'])} | TX {humanize_bytes(net['tx'])}")
    lines.append("")
    lines.append(f"yt-dlp: {runtime['ytdlp']}")
    lines.append(f"Node: {runtime['node']}")
    lines.append(f"Deno: {runtime['deno']}")
    lines.append(f"PTB: {runtime['ptb']}")
    lines.append(f"aiohttp: {runtime['aiohttp']}")
    lines.append(f"requests: {runtime['requests']}")
    lines.append(f"Pillow: {runtime['pillow']}")
    lines.append(f"psutil: {runtime['psutil']}")
    lines.append(f"aiofiles: {runtime['aiofiles']}")
    return "\n".join(lines)


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return

    stats = await asyncio.to_thread(_gather_stats)
    net_speed = await _measure_net_speed()
    bio = await asyncio.to_thread(_render_dashboard_sync, stats, net_speed)

    if bio:
        return await msg.reply_photo(photo=bio)

    out = "<b>System Stats</b>\n\n<pre>" + html.escape(_fallback_text(stats)) + "</pre>"
    return await msg.reply_text(out, parse_mode="HTML")