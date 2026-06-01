import discord
from discord.ext import commands
import aiohttp
import os
import asyncio

# ============================================================
#  إعدادات
# ============================================================
SERVER_IP   = "194.45.197.196"
SERVER_PORT = "30120"
GUILD_ID    = 1510735912185630812
LOGO_FILE   = "logo.webp"   # ← نفس مجلد main.py

BASE_URL = f"http://{SERVER_IP}:{SERVER_PORT}/players.json"
INFO_URL = f"http://{SERVER_IP}:{SERVER_PORT}/info.json"

TIMEOUT_SEC   = 10
COLOR_DEFAULT = 0x1DA1F2
COLOR_ERROR   = 0xED4245
COLOR_SUCCESS = 0x57F287

# ============================================================
#  مساعدات
# ============================================================
def extract_identifier(identifiers: list, prefix: str):
    for i in identifiers:
        if i.startswith(prefix):
            return i.replace(prefix, "")
    return None

def format_identifiers(identifiers: list) -> str:
    mapping = {
        "steam:"   : "🟠 Steam",
        "discord:" : "🔵 Discord",
        "license:" : "🔑 License",
        "license2:": "🔑 License2",
        "xbl:"     : "🟢 Xbox",
        "live:"    : "🟢 Live",
        "ip:"      : "🌐 IP",
    }
    lines = []
    for ident in identifiers:
        matched = False
        for prefix, label in mapping.items():
            if ident.startswith(prefix):
                lines.append(f"{label}: `{ident.replace(prefix,'')}`")
                matched = True
                break
        if not matched:
            lines.append(f"🔹 `{ident}`")
    return "\n".join(lines) if lines else "لا توجد معرّفات"

def error_embed(msg: str) -> discord.Embed:
    e = discord.Embed(title="SL6E BOT", description=msg, color=COLOR_ERROR)
    e.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
    return e

def get_logo() -> discord.File | None:
    if os.path.exists(LOGO_FILE):
        return discord.File(LOGO_FILE, filename="logo.webp")
    return None

# ============================================================
#  جلب البيانات (نسخة ذكية ومقاومة للحظر)
# ============================================================
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

async def fetch_players():
    # محاولة جلب البيانات من الجلسة المشتركة للبوت مع نظام إعادة محاولة (3 مرات كحد أقصى)
    if bot.session is None or bot.session.closed:
        bot.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=TIMEOUT_SEC),
            connector=aiohttp.TCPConnector(ssl=False)
        )
    
    for attempt in range(3):
        try:
            async with bot.session.get(BASE_URL, headers=_HEADERS) as r:
                if r.status == 200:
                    return await r.json(content_type=None)
                elif r.status in [429, 502, 503]:
                    await asyncio.sleep(0.5)  # انتظار بسيط في حال وجود ضغط أو جدار ناري
        except Exception as e:
            if attempt == 2:
                print(f"⚠️ players fetch error after 3 attempts: {e}")
            await asyncio.sleep(0.5)
    return None

async def fetch_info():
    if bot.session is None or bot.session.closed:
        bot.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=TIMEOUT_SEC),
            connector=aiohttp.TCPConnector(ssl=False)
        )
        
    for attempt in range(3):
        try:
            async with bot.session.get(INFO_URL, headers=_HEADERS) as r:
                if r.status == 200:
                    return await r.json(content_type=None)
                elif r.status in [429, 502, 503]:
                    await asyncio.sleep(0.5)
        except Exception as e:
            if attempt == 2:
                print(f"⚠️ info fetch error after 3 attempts: {e}")
            await asyncio.sleep(0.5)
    return None

# ============================================================
#  Modals
# ============================================================
class SearchIDModal(discord.ui.Modal, title="🔍 بحث بـ Server ID"):
    server_id = discord.ui.TextInput(label="Server ID", placeholder="مثال: 5", min_length=1, max_length=6)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            sid = int(self.server_id.value)
        except ValueError:
            await interaction.followup.send(embed=error_embed("❌ أدخل رقماً صحيحاً."), ephemeral=True)
            return
        data = await fetch_players()
        if data is None:
            await interaction.followup.send(embed=error_embed("❌ فشل جلب بيانات السيرفر أو السيرفر غير متاح حالياً."), ephemeral=True)
            return
        target = next((p for p in data if p.get("id") == sid), None)
        if not target:
            await interaction.followup.send(embed=error_embed(
                f"❌ لا يوجد لاعب بالـ ID **{sid}**.\n⚡ المتصلون: **{len(data)}**"
            ), ephemeral=True)
            return
        ids = target.get("identifiers", [])
        embed = discord.Embed(title="SL6E BOT", color=COLOR_DEFAULT)
        embed.set_author(name="🔍 بحث بـ ID")
        embed.add_field(name="👤 الاسم",   value=f"`{target.get('name','Unknown')}`", inline=True)
        embed.add_field(name="🆔 ID",      value=f"`{target.get('id','?')}`",         inline=True)
        embed.add_field(name="📶 Ping",    value=f"`{target.get('ping','?')} ms`",    inline=True)
        embed.add_field(name="🟠 Steam",   value=f"`{extract_identifier(ids,'steam:')}`"   if extract_identifier(ids,'steam:')   else "`—`", inline=True)
        embed.add_field(name="🔵 Discord", value=f"`{extract_identifier(ids,'discord:')}`" if extract_identifier(ids,'discord:') else "`—`", inline=True)
        embed.add_field(name="🔑 License", value=f"`{extract_identifier(ids,'license:')}`" if extract_identifier(ids,'license:') else "`—`", inline=True)
        embed.add_field(name="📋 المعرّفات", value=format_identifiers(ids), inline=False)
        embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
        await interaction.followup.send(embed=embed, ephemeral=True)

class SearchNameModal(discord.ui.Modal, title="🔎 بحث بالاسم"):
    player_name = discord.ui.TextInput(label="اسم اللاعب", placeholder="اكتب الاسم أو جزء منه", min_length=2, max_length=50)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        name = self.player_name.value.strip()
        data = await fetch_players()
        if data is None:
            await interaction.followup.send(embed=error_embed("❌ فشل جلب بيانات السيرفر أو السيرفر غير متاح حالياً."), ephemeral=True)
            return
        results = [p for p in data if name.lower() in p.get("name","").lower()]
        if not results:
            await interaction.followup.send(embed=error_embed(f"❌ لم يُعثر على **\"{name}\"**."), ephemeral=True)
            return
        show = results[:20]
        lines = "".join(f"[{str(p.get('id','?')).ljust(4)}] {p.get('name','?')}  ({p.get('ping','?')}ms)\n" for p in show)
        embed = discord.Embed(
            title="SL6E BOT",
            description=f"**🔎 نتائج: \"{name}\"** — {len(show)} نتيجة" + ("\n⚠️ أول 20 فقط" if len(results) > 20 else ""),
            color=COLOR_SUCCESS
        )
        embed.add_field(name="النتائج", value=f"```gml\n{lines}```", inline=False)
        embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
        await interaction.followup.send(embed=embed, ephemeral=True)


# ============================================================
#  لوحة التنقل بين صفحات اللاعبين (Pagination)
# ============================================================
class PlayersPaginationView(discord.ui.View):
    def __init__(self, players_data: list, per_page: int = 25):
        super().__init__(timeout=60)
        self.data = players_data
        self.per_page = per_page
        self.current_page = 0
        self.total_pages = max(1, (len(players_data) + per_page - 1) // per_page)
        self.update_buttons()

    def get_page_embed(self) -> discord.Embed:
        start_idx = self.current_page * self.
