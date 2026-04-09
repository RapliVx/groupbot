import logging
import asyncio
import json
import aiohttp
import sqlite3
import os
import sys
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request

from handlers.stats.system_info import gather_system_stats, measure_network_speed
from utils.config import BOT_TOKEN

app = FastAPI(title="Neko Material Dashboard")
templates = Jinja2Templates(directory="templates")

connected_clients = set()

BOT_INFO = {
    "id": "Menunggu...",
    "name": "Memuat...",
    "username": "--",
    "photo": ""
}
bot_info_fetched = False
USER_PROFILES_CACHE = {}

async def fetch_bot_info():
    global bot_info_fetched
    if bot_info_fetched: return
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe") as resp:
                data = await resp.json()
                if data.get("ok"):
                    res = data["result"]
                    BOT_INFO["id"] = str(res["id"])
                    BOT_INFO["name"] = res["first_name"]
                    BOT_INFO["username"] = res.get("username", "")
                    
                    async with session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUserProfilePhotos?user_id={res['id']}&limit=1") as p_resp:
                        p_data = await p_resp.json()
                        if p_data.get("ok") and p_data["result"]["total_count"] > 0:
                            f_id = p_data["result"]["photos"][0][0]["file_id"]
                            async with session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={f_id}") as f_resp:
                                f_data = await f_resp.json()
                                if f_data.get("ok"):
                                    BOT_INFO["photo"] = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{f_data['result']['file_path']}"
        bot_info_fetched = True
    except Exception:
        pass

async def get_premium_users():
    try:
        db_path = "data/caca.sqlite3" 
        if not os.path.exists(db_path): return []

        con = sqlite3.connect(db_path)
        cur = con.cursor()
        cur.execute("SELECT user_id FROM premium_users ORDER BY added_at DESC LIMIT 10")
        rows = cur.fetchall()
        con.close()
        
        users_list = []
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
            for row in rows:
                uid = str(row[0])
                if uid in USER_PROFILES_CACHE:
                    users_list.append(USER_PROFILES_CACHE[uid])
                    continue
                
                try:
                    name = f"User {uid}"
                    username = ""
                    photo_url = ""

                    async with session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getChat?chat_id={uid}") as resp:
                        data = await resp.json()
                        if data.get("ok"):
                            chat = data["result"]
                            name = chat.get("first_name", name)
                            if chat.get("last_name"): name += f" {chat['last_name']}"
                            username = chat.get("username", "")

                    async with session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUserProfilePhotos?user_id={uid}&limit=1") as p_resp:
                        p_data = await p_resp.json()
                        if p_data.get("ok") and p_data["result"]["total_count"] > 0:
                            f_id = p_data["result"]["photos"][0][0]["file_id"]
                            async with session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={f_id}") as f_resp:
                                f_data = await f_resp.json()
                                if f_data.get("ok"):
                                    photo_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{f_data['result']['file_path']}"

                    user_data = {"name": name, "username": username, "id": uid, "photo": photo_url}
                    USER_PROFILES_CACHE[uid] = user_data
                    users_list.append(user_data)
                except Exception:
                    user_data = {"name": f"User {uid}", "username": "", "id": uid, "photo": ""}
                    USER_PROFILES_CACHE[uid] = user_data
                    users_list.append(user_data)
                    
        return users_list
    except Exception as e:
        return [{"name": "Error membaca DB", "username": "", "id": str(e), "photo": ""}]

class WebSocketLogHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        payload = json.dumps({"type": "log", "message": log_entry})
        for client in list(connected_clients):
            try:
                loop = asyncio.get_event_loop()
                loop.create_task(client.send_text(payload))
            except Exception:
                connected_clients.remove(client)

ws_handler = WebSocketLogHandler()
ws_handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", "%H:%M:%S"))

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.post("/api/restart")
async def restart_bot():
    """Endpoint untuk memicu restart bot dari Dashboard"""
    def perform_restart():
        import time
        time.sleep(1)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    asyncio.get_event_loop().call_soon(perform_restart)
    return {"status": "restarting"}

@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    
    async def send_stats_loop():
        while True:
            stats = None
            try:
                if not bot_info_fetched:
                    asyncio.create_task(fetch_bot_info())

                stats = gather_system_stats()
                rx_speed, tx_speed = await measure_network_speed()
                stats["net"]["rx_speed"] = rx_speed
                stats["net"]["tx_speed"] = tx_speed
                
                stats["type"] = "stats"
                stats["bot"] = BOT_INFO
                stats["premium_users"] = await get_premium_users()
            except Exception as e:
                logging.error(f"WS Stats Data Error: {e}")
                
            try:
                if stats:
                    await websocket.send_text(json.dumps(stats))
                await asyncio.sleep(1.75)
            except Exception:
                break

    stats_task = asyncio.create_task(send_stats_loop())

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
        stats_task.cancel()