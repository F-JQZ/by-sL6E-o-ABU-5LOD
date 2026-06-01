import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import json
import os
import math
import asyncio

# ============================================================
#  إعدادات السيرفر المباشرة
# ============================================================
SERVER_IP   = "194.45.197.143"
SERVER_PORT = "30120"
GUILD_ID    = 1510735912185630812   # آيدي سيرفر الديسكورد الخاص بك

BASE_URL        = f"http://{SERVER_IP}:{SERVER_PORT}/players.json"
INFO_URL        = f"http://{SERVER_IP}:{SERVER_PORT}/info.json"
FIVEM_THUMBNAIL = "https://i.imgur.com/F4LkFHJ.png"
PLAYERS_PER_PAGE = 20
TIMEOUT_SEC      = 4  # وقت الانتظار قبل إلغاء الطلب لحماية البوت من التعليق

COLOR_DEFAULT = 0x5865F2
COLOR_ERROR   = 0xED4245
COLOR_SUCCESS = 0x57F287

# ============================================================
#  مساعدات التنسيق
# ============================================================
def extract_identifier(identifiers: list, prefix: str):
    for ident in identifiers:
        if ident.startswith(prefix):
            return ident.replace(prefix, "")
    return None

def format_identifiers(identifiers: list) -> str:
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

def error_embed(message: str) -> discord.Embed:
    embed = discord.Embed(title="FiveM Bot", description=message, color=COLOR_ERROR)
    embed.set_thumbnail(url=FIVEM_THUMBNAIL)
    embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
    return embed

# ============================================================
#  جلب البيانات المباشر الآمن (بدون كراش)
# ============================================================
async def fetch_players():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    timeout = aiohttp.ClientTimeout(total=TIMEOUT_SEC)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            async with session.get(BASE_URL, headers=headers) as r:
                if r.status == 200:
                    return await r.json(content_type=None)
        except Exception as e:
            print(f"❌ fetch_players error: {e}")
    return None

async def fetch_info():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
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
#  بناء embed الصفحة
# ============================================================
def build_players_embed(players_data: list, page: int, total_pages: int) -> discord.Embed:
    total_players = len(players_data)
    start = (page - 1) * PLAYERS_PER_PAGE
    page_players = players_data[start: start + PLAYERS_PER_PAGE]

    lines = ""
    for p in page_players:
        pid  = str(p.get("id", "?")).ljust(4)
        name = p.get("name", "Unknown")
        lines += f"[{pid}] {name}\n"

    if not lines:
        lines = "لا يوجد لاعبين في هذه الصفحة."

    embed = discord.Embed(
        title="FiveM Bot",
        description=(
            "Become a **patron** today to get the benefits of **FiveM Bot Pro**.\n"
            f"Learn more [here](https://fivem.net).\n\n"
            f"**Player List • TOTAL: {total_players} players • PAGE: {page}/{total_pages}**"
        ),
        color=COLOR_DEFAULT
    )
    embed.set_thumbnail(url=FIVEM_THUMBNAIL)
    embed.add_field(name="Player List", value=f"```gml\n{lines}```", inline=False)
    embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
    return embed

# ============================================================
#  أزرار التنقل بين الصفحات
# ============================================================
class PlayersView(discord.ui.View):
    def __init__(self, players_data: list, page: int, total_pages: int, requester_id: int):
        super().__init__(timeout=120)
        self.players_data  = players_data
        self.page          = page
        self.total_pages   = total_pages
        self.requester_id  = requester_id
        self._update_buttons()

    def _update_buttons(self):
        self.first_btn.disabled = self.page <= 1
        self.prev_btn.disabled  = self.page <= 1
        self.next_btn.disabled  = self.page >= self.total_pages
        self.last_btn.disabled  = self.page >= self.total_pages
        self.page_label.label   = f"  {self.page} / {self.total_pages}  "

    async def _check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message(
                "❌ هذه الأزرار للشخص اللي استخدم الأمر فقط.", ephemeral=True
            )
            return False
        return True

    async def _go(self, interaction: discord.Interaction, new_page: int):
        self.page = new_page
        self._update_buttons()
        embed = build_players_embed(self.players_data, self.page, self.total_pages)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⏮", style=discord.ButtonStyle.secondary)
    async def first_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        await self._go(interaction, 1)

    @discord.ui.button(label="◀", style=discord.ButtonStyle.primary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        await self._go(interaction, self.page - 1)

    @discord.ui.button(label="  1 / 1  ", style=discord.ButtonStyle.secondary, disabled=True)
    async def page_label(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="▶", style=discord.ButtonStyle.primary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        await self._go(interaction, self.page + 1)

    @discord.ui.button(label="⏭", style=discord.ButtonStyle.secondary)
    async def last_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        await self._go(interaction, self.total_pages)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

# ============================================================
#  إعداد البوت
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
        print("✅ تم مزامنة الأوامر بنجاح.")

bot = FiveMBot()

@bot.event
async def on_ready():
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="BY SL6E & ABO 5LOOD"
        )
    )
    print(f"✅ البوت شغال الآن: {bot.user.name}  |  {SERVER_IP}:{SERVER_PORT}")


# ============================================================
#  /players
# ============================================================
@bot.tree.command(name="players", description="عرض قائمة اللاعبين مع أزرار التنقل")
async def cmd_players(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)

    players_data = await fetch_players()

    if players_data is None:
        await interaction.followup.send(embed=error_embed(
            "❌ **فشل الاتصال بالسيرفر**\nتأكد من أن السيرفر يعمل حالياً وأن منفذ الـ API مفتوح."
        ))
        return

    total_players = len(players_data)

    if total_players == 0:
        await interaction.followup.send(embed=error_embed("⚠️ لا يوجد لاعبون متصلون حالياً."))
        return

    total_pages = math.ceil(total_players / PLAYERS_PER_PAGE)

    embed = build_players_embed(players_data, 1, total_pages)
    view  = PlayersView(players_data, 1, total_pages, interaction.user.id)

    await interaction.followup.send(embed=embed, view=view)


# ============================================================
#  /id
# ============================================================
@bot.tree.command(name="id", description="البحث عن لاعب داخل السيرفر عبر الـ Server ID")
@app_commands.describe(server_id="الـ ID الخاص باللاعب داخل السيرفر")
async def cmd_id(interaction: discord.Interaction, server_id: int):
    await interaction.response.defer(thinking=True)

    if server_id <= 0:
        await interaction.followup.send(embed=error_embed("❌ الـ ID يجب أن يكون رقماً موجباً."))
        return

    players_data = await fetch_players()
    if players_data is None:
        await interaction.followup.send(embed=error_embed("❌ فشل جلب بيانات السيرفر."))
        return

    target = next((p for p in players_data if p.get("id") == server_id), None)

    if not target:
        await interaction.followup.send(embed=error_embed(
            f"❌ لا يوجد لاعب بالـ ID **{server_id}** متصل حالياً.\n"
            f"⚡ إجمالي المتصلين: **{len(players_data)}** لاعب"
        ))
        return

    identifiers = target.get("identifiers", [])
    steam_raw   = extract_identifier(identifiers, "steam:")
    discord_raw = extract_identifier(identifiers, "discord:")
    license_raw = extract_identifier(identifiers, "license:")

    steam_value   = f"`{steam_raw}`"                        if steam_raw   else "`غير مرتبط`"
    discord_value = f"<@{discord_raw}> (`{discord_raw}`)"        if discord_raw else "`غير مرتبط`"
    license_value = f"`{license_raw}`"                            if license_raw else "`—`"

    embed = discord.Embed(
        title="FiveM Bot",
        description=(
            "Have feedback or suggestions? Fill out the "
            "[FiveM Bot feedback form](https://fivem.net) "
            "and help improve the service for all."
        ),
        color=COLOR_DEFAULT
    )
    embed.set_author(name="ID Search")
    embed.set_thumbnail(url=FIVEM_THUMBNAIL)
    embed.add_field(name="Username",   value=f"`{target.get('name','Unknown')}`", inline=True)
    embed.add_field(name="Server ID",  value=f"`{target.get('id','?')}`",         inline=True)
    embed.add_field(name="Ping",       value=f"`{target.get('ping','?')} ms`",    inline=True)
    embed.add_field(name="🟠 Steam",   value=steam_value,                          inline=True)
    embed.add_field(name="🔵 Discord", value=discord_value,                        inline=True)
    embed.add_field(name="🔑 License", value=license_value,                        inline=True)
    embed.add_field(name="📋 All Identifiers", value=format_identifiers(identifiers), inline=False)
    embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
    await interaction.followup.send(embed=embed)


# ============================================================
#  /search
# ============================================================
@bot.tree.command(name="search", description="البحث عن لاعب بالاسم")
@app_commands.describe(name="اسم اللاعب أو جزء منه")
async def cmd_search(interaction: discord.Interaction, name: str):
    await interaction.response.defer(thinking=True)

    if len(name.strip()) < 2:
        await interaction.followup.send(embed=error_embed("❌ اكتب على الأقل **حرفين** للبحث."))
        return

    players_data = await fetch_players()
    if players_data is None:
        await interaction.followup.send(embed=error_embed("❌ فشل جلب بيانات السيرفر."))
        return

    query   = name.strip().lower()
    results = [p for p in players_data if query in p.get("name", "").lower()]

    if not results:
        await interaction.followup.send(embed=error_embed(
            f"❌ لم يُعثر على لاعب يحتوي اسمه على **\"{name}\"**."
        ))
        return

    MAX_RESULTS = 15
    truncated   = len(results) > MAX_RESULTS
    results     = results[:MAX_RESULTS]

    lines = ""
    for p in results:
        pid   = str(p.get("id","?")).ljust(4)
        pname = p.get("name","Unknown")
        ping  = p.get("ping","?")
        lines += f"[{pid}] {pname}  (ping: {ping}ms)\n"

    note = f"\n⚠️ تم عرض أول {MAX_RESULTS} نتيجة فقط." if truncated else ""

    embed = discord.Embed(
        title="FiveM Bot",
        description=f"**نتائج البحث عن: \"{name}\"** — {len(results)} نتيجة{note}",
        color=COLOR_SUCCESS
    )
    embed.set_author(name="Name Search")
    embed.set_thumbnail(url=FIVEM_THUMBNAIL)
    embed.add_field(name="Results", value=f"```gml\n{lines}```", inline=False)
    embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
    await interaction.followup.send(embed=embed)


# ============================================================
#  /stats
# ============================================================
@bot.tree.command(name="stats", description="إحصائيات السيرفر العامة")
async def cmd_stats(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)

    players_data, info_data = await asyncio.gather(fetch_players(), fetch_info())

    if players_data is None:
        await interaction.followup.send(embed=error_embed("❌ السيرفر غير متاح حالياً للاتصال."))
        return

    total_players = len(players_data)
    
    # تأمين جلب الاسم والحد الأقصى لمنع الكراش إذا كانت البيانات ناقصة
    max_players = "?"
    server_name = "Unknown Server"
    
    if info_data and isinstance(info_data, dict):
        server_vars = info_data.get("vars", {})
        max_players = server_vars.get("sv_maxClients", "?")
        server_name = info_data.get("name", server_vars.get("sv_hostname", "Unknown Server"))

    avg_ping = 0
    if total_players:
        pings    = [p.get("ping", 0) for p in players_data if isinstance(p.get("ping"), int)]
        avg_ping = round(sum(pings) / len(pings)) if pings else 0

    embed = discord.Embed(title="FiveM Bot", description="**Server Statistics**", color=COLOR_DEFAULT)
    embed.set_author(name="Server Stats")
    embed.set_thumbnail(url=FIVEM_THUMBNAIL)
    embed.add_field(name="🖥️ Server Name", value=f"`{server_name}`",                  inline=False)
    embed.add_field(name="👥 Players",     value=f"`{total_players} / {max_players}`", inline=True)
    embed.add_field(name="📶 Avg Ping",    value=f"`{avg_ping} ms`",                   inline=True)
    embed.add_field(name="🌐 Address",     value=f"`{SERVER_IP}:{SERVER_PORT}`",        inline=True)
    embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
    await interaction.followup.send(embed=embed)


# ============================================================
#  تشغيل البوت عبر التوكن
# ============================================================
TOKEN = os.environ.get("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ خطأ: DISCORD_TOKEN غير موجود في متغيرات البيئة!")
