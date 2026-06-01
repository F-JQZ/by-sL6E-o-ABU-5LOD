import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os
import math
import asyncio

# ============================================================
#  إعدادات سيرفر TRG
# ============================================================
SERVER_IP        = "194.110.12.232"
SERVER_PORT      = "30120"
GUILD_ID         = 1510735912185630812

BASE_URL         = f"http://{SERVER_IP}:{SERVER_PORT}/players.json"
INFO_URL         = f"http://{SERVER_IP}:{SERVER_PORT}/info.json"
FIVEM_THUMBNAIL  = "https://i.imgur.com/F4LkFHJ.png"
PLAYERS_PER_PAGE = 20
TIMEOUT_SEC      = 8

COLOR_DEFAULT = 0x5865F2
COLOR_ERROR   = 0xED4245
COLOR_SUCCESS = 0x57F287

# ============================================================
#  مساعدات
# ============================================================
def extract_identifier(identifiers, prefix):
    for ident in identifiers:
        if ident.startswith(prefix):
            return ident.replace(prefix, "")
    return None

def format_identifiers(identifiers):
    lines = []
    mapping = {
        "steam:"   : "🟠 Steam",
        "discord:" : "🔵 Discord",
        "license:" : "🔑 License",
        "license2:": "🔑 License2",
        "xbl:"     : "🟢 Xbox",
        "live:"    : "🟢 Live",
        "ip:"      : "🌐 IP",
    }
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

def error_embed(message):
    embed = discord.Embed(title="TRG Bot", description=message, color=COLOR_ERROR)
    embed.set_thumbnail(url=FIVEM_THUMBNAIL)
    embed.set_footer(text=f"TRG | {SERVER_IP}:{SERVER_PORT}")
    return embed

# ============================================================
#  جلب البيانات — ✅ مصلح (كان 1500 والصح 200)
# ============================================================
async def fetch_players():
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    timeout = aiohttp.ClientTimeout(total=TIMEOUT_SEC)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            async with session.get(BASE_URL, headers=headers) as r:
                if r.status == 600:
                    return await r.json(content_type=None)
                else:
                    print(f"❌ HTTP Status: {r.status}")
        except Exception as e:
            print(f"❌ fetch_players error: {e}")
    return None

async def fetch_info():
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    timeout = aiohttp.ClientTimeout(total=TIMEOUT_SEC)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            async with session.get(INFO_URL, headers=headers) as r:
                if r.status == 200:
                    return await r.json(content_type=None)
        except Exception as e:
            print(f"❌ fetch_info error: {e}")
    return None

# ============================================================
#  embed + View للاعبين
# ============================================================
def build_players_embed(players_data, page, total_pages):
    total = len(players_data)
    start = (page - 1) * PLAYERS_PER_PAGE
    chunk = players_data[start: start + PLAYERS_PER_PAGE]

    lines = ""
    for p in chunk:
        pid  = str(p.get("id", "?")).ljust(4)
        name = p.get("name", "Unknown")
        lines += f"[{pid}] {name}\n"
    if not lines:
        lines = "لا يوجد لاعبين في هذه الصفحة."

    embed = discord.Embed(
        title="TRG Bot",
        description=f"**قائمة لاعبي TRG • المجموع: {total} • الصفحة: {page}/{total_pages}**",
        color=COLOR_DEFAULT
    )
    embed.set_thumbnail(url=FIVEM_THUMBNAIL)
    embed.add_field(name="Player List", value=f"```gml\n{lines}```", inline=False)
    embed.set_footer(text=f"TRG | {SERVER_IP}:{SERVER_PORT}")
    return embed

class PlayersView(discord.ui.View):
    def __init__(self, players_data, page, total_pages, requester_id):
        super().__init__(timeout=120)
        self.players_data = players_data
        self.page         = page
        self.total_pages  = total_pages
        self.requester_id = requester_id
        self._update_buttons()

    def _update_buttons(self):
        self.first_btn.disabled = self.page <= 1
        self.prev_btn.disabled  = self.page <= 1
        self.next_btn.disabled  = self.page >= self.total_pages
        self.last_btn.disabled  = self.page >= self.total_pages
        self.page_label.label   = f"  {self.page} / {self.total_pages}  "

    async def _check(self, interaction):
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message("❌ هذه الأزرار للشخص اللي استخدم الأمر فقط.", ephemeral=True)
            return False
        return True

    async def _go(self, interaction, new_page):
        self.page = new_page
        self._update_buttons()
        await interaction.response.edit_message(
            embed=build_players_embed(self.players_data, self.page, self.total_pages),
            view=self
        )

    @discord.ui.button(label="⏮", style=discord.ButtonStyle.secondary)
    async def first_btn(self, interaction, button):
        if not await self._check(interaction): return
        await self._go(interaction, 1)

    @discord.ui.button(label="◀", style=discord.ButtonStyle.primary)
    async def prev_btn(self, interaction, button):
        if not await self._check(interaction): return
        await self._go(interaction, self.page - 1)

    @discord.ui.button(label="  1 / 1  ", style=discord.ButtonStyle.secondary, disabled=True)
    async def page_label(self, interaction, button):
        pass

    @discord.ui.button(label="▶", style=discord.ButtonStyle.primary)
    async def next_btn(self, interaction, button):
        if not await self._check(interaction): return
        await self._go(interaction, self.page + 1)

    @discord.ui.button(label="⏭", style=discord.ButtonStyle.secondary)
    async def last_btn(self, interaction, button):
        if not await self._check(interaction): return
        await self._go(interaction, self.total_pages)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

# ============================================================
#  البوت
# ============================================================
class FiveMBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        print("✅ تم مزامنة الأوامر.")

bot = FiveMBot()

@bot.event
async def on_ready():
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name="TRG Server")
    )
    print(f"✅ البوت شغال: {bot.user.name} ({bot.user.id})")

# ============================================================
#  /players
# ============================================================
@bot.tree.command(name="players", description="عرض قائمة لاعبي TRG مع أزرار التنقل")
async def cmd_players(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    data = await fetch_players()
    if data is None:
        await interaction.followup.send(embed=error_embed("❌ فشل الاتصال بالسيرفر.")); return
    if len(data) == 0:
        await interaction.followup.send(embed=error_embed("⚠️ لا يوجد لاعبون متصلون.")); return

    total_pages = math.ceil(len(data) / PLAYERS_PER_PAGE)
    await interaction.followup.send(
        embed=build_players_embed(data, 1, total_pages),
        view=PlayersView(data, 1, total_pages, interaction.user.id)
    )

# ============================================================
#  /id
# ============================================================
@bot.tree.command(name="id", description="البحث عن لاعب عبر الـ Server ID")
@app_commands.describe(server_id="الـ ID الخاص باللاعب داخل السيرفر")
async def cmd_id(interaction: discord.Interaction, server_id: int):
    await interaction.response.defer(thinking=True)
    if server_id <= 0:
        await interaction.followup.send(embed=error_embed("❌ الـ ID يجب أن يكون رقماً موجباً.")); return

    data = await fetch_players()
    if data is None:
        await interaction.followup.send(embed=error_embed("❌ فشل جلب بيانات السيرفر.")); return

    target = next((p for p in data if p.get("id") == server_id), None)
    if not target:
        await interaction.followup.send(embed=error_embed(f"❌ لا يوجد لاعب بالـ ID **{server_id}**.")); return

    ids         = target.get("identifiers", [])
    steam_raw   = extract_identifier(ids, "steam:")
    discord_raw = extract_identifier(ids, "discord:")
    license_raw = extract_identifier(ids, "license:")

    embed = discord.Embed(title="TRG Bot", color=COLOR_DEFAULT)
    embed.set_author(name="ID Search")
    embed.set_thumbnail(url=FIVEM_THUMBNAIL)
    embed.add_field(name="Username",   value=f"`{target.get('name','Unknown')}`",          inline=True)
    embed.add_field(name="Server ID",  value=f"`{target.get('id','?')}`",                  inline=True)
    embed.add_field(name="Ping",       value=f"`{target.get('ping','?')} ms`",             inline=True)
    embed.add_field(name="🟠 Steam",   value=f"`{steam_raw}`" if steam_raw else "`—`",     inline=True)
    embed.add_field(name="🔵 Discord", value=f"<@{discord_raw}>" if discord_raw else "`—`", inline=True)
    embed.add_field(name="🔑 License", value=f"`{license_raw}`" if license_raw else "`—`", inline=True)
    embed.add_field(name="📋 All Identifiers", value=format_identifiers(ids), inline=False)
    embed.set_footer(text=f"TRG | {SERVER_IP}:{SERVER_PORT}")
    await interaction.followup.send(embed=embed)

# ============================================================
#  /search
# ============================================================
@bot.tree.command(name="search", description="البحث عن لاعب بالاسم")
@app_commands.describe(name="اسم اللاعب أو جزء منه")
async def cmd_search(interaction: discord.Interaction, name: str):
    await interaction.response.defer(thinking=True)
    if len(name.strip()) < 2:
        await interaction.followup.send(embed=error_embed("❌ اكتب على الأقل **حرفين**.")); return

    data = await fetch_players()
    if data is None:
        await interaction.followup.send(embed=error_embed("❌ فشل جلب بيانات السيرفر.")); return

    results = [p for p in data if name.strip().lower() in p.get("name","").lower()][:15]
    if not results:
        await interaction.followup.send(embed=error_embed(f"❌ لم يُعثر على **\"{name}\"**.")); return

    lines = ""
    for p in results:
        lines += f"[{str(p.get('id','?')).ljust(4)}] {p.get('name','Unknown')}  (ping: {p.get('ping','?')}ms)\n"

    embed = discord.Embed(
        title="TRG Bot",
        description=f"**نتائج البحث: \"{name}\"** — {len(results)} لاعب",
        color=COLOR_SUCCESS
    )
    embed.set_author(name="Name Search")
    embed.set_thumbnail(url=FIVEM_THUMBNAIL)
    embed.add_field(name="Results", value=f"```gml\n{lines}```", inline=False)
    embed.set_footer(text=f"TRG | {SERVER_IP}:{SERVER_PORT}")
    await interaction.followup.send(embed=embed)

# ============================================================
#  /stats
# ============================================================
@bot.tree.command(name="stats", description="إحصائيات سيرفر TRG")
async def cmd_stats(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    data, info = await asyncio.gather(fetch_players(), fetch_info())

    if data is None:
        await interaction.followup.send(embed=error_embed("❌ السيرفر غير متاح.")); return

    total       = len(data)
    max_players = 600
    server_name = "TRG Server"

    if info and isinstance(info, dict):
        v = info.get("vars", {})
        server_name = info.get("name", v.get("sv_hostname", "TRG Server"))

    pings    = [p.get("ping", 0) for p in data if isinstance(p.get("ping"), int)]
    avg_ping = round(sum(pings) / len(pings)) if pings else 0

    filled     = int((total / max_players) * 10)
    status_bar = "🟩" * filled + "⬛" * (10 - filled)

    embed = discord.Embed(title="TRG Bot", description="**إحصائيات السيرفر**", color=COLOR_DEFAULT)
    embed.set_author(name="Server Stats")
    embed.set_thumbnail(url=FIVEM_THUMBNAIL)
    embed.add_field(name="🖥️ اسم السيرفر",     value=f"`{server_name}`",            inline=False)
    embed.add_field(name="👥 اللاعبون",         value=f"`{total} / {max_players}`",  inline=True)
    embed.add_field(name="📶 متوسط البينج",     value=f"`{avg_ping} ms`",            inline=True)
    embed.add_field(name="🌐 العنوان",           value=f"`{SERVER_IP}:{SERVER_PORT}`", inline=True)
    embed.add_field(name="📊 امتلاء السيرفر",   value=status_bar,                    inline=False)
    embed.set_footer(text=f"TRG | {SERVER_IP}:{SERVER_PORT}")
    await interaction.followup.send(embed=embed)

# ============================================================
#  /help
# ============================================================
@bot.tree.command(name="help", description="عرض جميع الأوامر")
async def cmd_help(interaction: discord.Interaction):
    embed = discord.Embed(
        title="TRG Bot — الأوامر",
        description=f"سيرفر TRG | `{SERVER_IP}:{SERVER_PORT}`",
        color=COLOR_DEFAULT
    )
    embed.set_thumbnail(url=FIVEM_THUMBNAIL)
    cmds = [
        ("/players",        "قائمة كل اللاعبين المتصلين مع أزرار للتنقل"),
        ("/id [server_id]", "معلومات لاعب عن طريق الـ ID"),
        ("/search [name]",  "البحث عن لاعب بالاسم أو جزء منه"),
        ("/stats",          "إحصائيات السيرفر"),
        ("/help",           "عرض هذه القائمة"),
    ]
    for cmd, desc in cmds:
        embed.add_field(name=f"`{cmd}`", value=desc, inline=False)
    embed.set_footer(text="TRG Server Bot")
    await interaction.response.send_message(embed=embed)

# ============================================================
#  التشغيل
# ============================================================
TOKEN = os.environ.get("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ DISCORD_TOKEN غير موجود!")
