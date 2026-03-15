import subprocess

try:
    from importlib.metadata import version as pkg_version
except Exception:
    pkg_version = None


def get_package_version(*names):
    if not pkg_version:
        return "N/A"
    for name in names:
        try:
            return pkg_version(name)
        except Exception:
            pass
    return "N/A"


def run_version_command(cmd):
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=1.5,
        )
        out = (proc.stdout or proc.stderr or "").strip()
        if not out:
            return "N/A"
        return out.splitlines()[0].strip()
    except Exception:
        return "N/A"


def get_node_version():
    out = run_version_command(["node", "-v"])
    return out if out else "N/A"


def get_deno_version():
    out = run_version_command(["deno", "--version"])
    if out == "N/A":
        return "N/A"
    parts = out.split()
    if len(parts) >= 2 and parts[0].lower() == "deno":
        return parts[1]
    return out


def get_ytdlp_version():
    ver = get_package_version("yt-dlp-ejs", "yt-dlp")
    if ver != "N/A":
        return ver
    try:
        from yt_dlp.version import __version__ as yt_dlp_version
        return yt_dlp_version
    except Exception:
        return "N/A"


def get_runtime_versions():
    return {
        "ytdlp": get_ytdlp_version(),
        "node": get_node_version(),
        "deno": get_deno_version(),
        "ptb": get_package_version("python-telegram-bot"),
        "aiohttp": get_package_version("aiohttp"),
        "requests": get_package_version("requests"),
        "pillow": get_package_version("Pillow"),
        "psutil": get_package_version("psutil"),
        "aiofiles": get_package_version("aiofiles"),
    }