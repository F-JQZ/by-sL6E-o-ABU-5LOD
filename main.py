import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os
import math
import asyncio
import ssl

SERVER_IP   = "194.45.197.196"
SERVER_PORT = "30120"
GUILD_ID    = 1510735912185630812

BASE_URL = f"http://{SERVER_IP}:{SERVER_PORT}/players.json"
INFO_URL = f"http://{SERVER_IP}:{SERVER_PORT}/info.json"

FIVEM_THUMBNAIL  = "https://cdn.discordapp.com/emojis/1060951257456812082.png"
PLAYERS_PER_FIELD = 25
TIMEOUT_SEC       = 10

COLOR_DEFAULT = 0x5865F2
COLOR_ERROR   = 0xED4245
COLOR_SUCCESS = 0x57F287

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
    embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
    return embed

HEADERS_LIST = [
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"},
    {"User-Agent": "FiveM/1.0 (compatible)"},
    {"User-Agent": "curl/7.88.1"},
]

async def fetch_players():
    timeout = aiohttp.ClientTimeout(total=TIMEOUT_SEC)
    for headers in HEADERS_LIST:
        try:
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                async with session.get(BASE_URL, headers=headers) as r:
                    if r.status == 200:
                        return await r.json(content_type=None)
        except Exception as e:
            print(f"⚠️ {e}")
    return None

async def fetch_info():
    timeout = aiohttp.ClientTimeout(total=TIMEOUT_SEC)
    try:
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            async with session.get(INFO_URL, headers=HEADERS_LIST[0]) as r:
                if r.status == 200:
                    return await r.json(content_type=None)
    except Exception as e:
        print(f"❌ {e}")
    return None

def build_full_players_embed(players_data: list) -> list[discord.Embed]:
    total = len(players_data)
    embeds = []
    chunks = [players_data[i:i+PLAYERS_PER_FIELD] for i in range(0, total, PLAYERS_PER_FIELD)]
    FIELDS_PER_EMBED = 5
    embed_chunks = [chunks[i:i+FIELDS_PER_EMBED] for i in range(0, len(chunks), FIELDS_PER_EMBED)]
    for idx, group in enumerate(embed_chunks):
        if idx == 0:
            embed = discord.Embed(
                title="FiveM Bot",
                description=f"**Player List • TOTAL: {total} players**",
                color=COLOR_DEFAULT
            )
        else:
            embed = discord.Embed(color=COLOR_DEFAULT)
        for chunk in group:
            lines = "".join(f"[{str(p.get('id','?')).ljust(4)}] {p.get('name','Unknown')}\n" for p in chunk)
            embed.add_field(
                name=f"Players ({chunk[0].get('id','?')} → {chunk[-1].get('id','?')})",
                value=f"```gml\n{lines}```",
                inline=False
            )
        embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
        embeds.append(embed)
    return embeds

class FiveMBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        if GUILD_ID:
            try:
                guild = discord.Object(id=GUILD_ID)
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                print(f"✅ مزامنة فورية للسيرفر: {GUILD_ID}")
            except discord.Forbidden:
                await self.tree.sync()
                print("✅ مزامنة عالمية.")
        else:
            await self.tree.sync()
            print("✅ مزامنة عالمية.")

bot = FiveMBot()

@bot.event
async def on_ready():
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="BY SL6E & ABO 5LOOD"
        )
    )
    print(f"✅ البوت شغال: {bot.user.name}  |  {SERVER_IP}:{SERVER_PORT}")

@bot.tree.command(name="players", description="عرض قائمة كاملة لجميع اللاعبين المتصلين")
async def cmd_players(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    players_data = await fetch_players()
    if players_data is None:
        await interaction.followup.send(embed=error_embed("❌ فشل الاتصال بالسيرفر")); return
    if len(players_data) == 0:
        await interaction.followup.send(embed=error_embed("⚠️ لا يوجد لاعبون متصلون.")); return
    await interaction.followup.send(embeds=build_full_players_embed(players_data)[:10])

@bot.tree.command(name="id", description="البحث عن لاعب عبر الـ Server ID")
@app_commands.describe(server_id="الـ ID الخاص باللاعب")
async def cmd_id(interaction: discord.Interaction, server_id: int):
    await interaction.response.defer(thinking=True)
    if server_id <= 0:
        await interaction.followup.send(embed=error_embed("❌ الـ ID يجب أن يكون موجباً.")); return
    players_data = await fetch_players()
    if players_data is None:
        await interaction.followup.send(embed=error_embed("❌ فشل جلب بيانات السيرفر.")); return
    target = next((p for p in players_data if p.get("id") == server_id), None)
    if not target:
        await interaction.followup.send(embed=error_embed(
            f"❌ لا يوجد لاعب بالـ ID **{server_id}**.\n⚡ المتصلون: **{len(players_data)}**"
        )); return
    identifiers   = target.get("identifiers", [])
    steam_raw     = extract_identifier(identifiers, "steam:")
    discord_raw   = extract_identifier(identifiers, "discord:")
    license_raw   = extract_identifier(identifiers, "license:")
    embed = discord.Embed(title="FiveM Bot", color=COLOR_DEFAULT)
    embed.set_author(name="ID Search")
    embed.add_field(name="Username",           value=f"`{target.get('name','Unknown')}`",                       inline=True)
    embed.add_field(name="Server ID",          value=f"`{target.get('id','?')}`",                              inline=True)
    embed.add_field(name="Ping",               value=f"`{target.get('ping','?')} ms`",                         inline=True)
    embed.add_field(name="🟠 Steam",           value=f"`{steam_raw}`"   if steam_raw   else "`غير مرتبط`",    inline=True)
    embed.add_field(name="🔵 Discord",         value=f"`{discord_raw}`" if discord_raw else "`غير مرتبط`",    inline=True)
    embed.add_field(name="🔑 License",         value=f"`{license_raw}`" if license_raw else "`—`",             inline=True)
    embed.add_field(name="📋 All Identifiers", value=format_identifiers(identifiers),                           inline=False)
    embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="search", description="البحث عن لاعب بالاسم")
@app_commands.describe(name="اسم اللاعب أو جزء منه")
async def cmd_search(interaction: discord.Interaction, name: str):
    await interaction.response.defer(thinking=True)
    if len(name.strip()) < 2:
        await interaction.followup.send(embed=error_embed("❌ اكتب على الأقل حرفين.")); return
    players_data = await fetch_players()
    if players_data is None:
        await interaction.followup.send(embed=error_embed("❌ فشل جلب بيانات السيرفر.")); return
    results = [p for p in players_data if name.strip().lower() in p.get("name","").lower()]
    if not results:
        await interaction.followup.send(embed=error_embed(f"❌ لم يُعثر على **\"{name}\"**.")); return
    truncated = len(results) > 20
    results   = results[:20]
    lines = "".join(f"[{str(p.get('id','?')).ljust(4)}] {p.get('name','?')}  (ping: {p.get('ping','?')}ms)\n" for p in results)
    embed = discord.Embed(
        title="FiveM Bot",
        description=f"**نتائج البحث: \"{name}\"** — {len(results)} نتيجة" + ("\n⚠️ أول 20 فقط" if truncated else ""),
        color=COLOR_SUCCESS
    )
    embed.set_author(name="Name Search")
    embed.add_field(name="Results", value=f"```gml\n{lines}```", inline=False)
    embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="stats", description="إحصائيات السيرفر العامة")
async def cmd_stats(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    players_data, info_data = await asyncio.gather(fetch_players(), fetch_info())
    if players_data is None:
        await interaction.followup.send(embed=error_embed("❌ السيرفر غير متاح.")); return
    total     = len(players_data)
    vars_     = info_data.get("vars", {}) if info_data else {}
    max_p     = vars_.get("sv_maxClients", "?")
    name      = info_data.get("name", vars_.get("sv_hostname", "Unknown")) if info_data else "Unknown"
    pings     = [p.get("ping", 0) for p in players_data if isinstance(p.get("ping"), int)]
    avg_ping  = round(sum(pings) / len(pings)) if pings else 0
    embed = discord.Embed(title="FiveM Bot", description="**Server Statistics**", color=COLOR_DEFAULT)
    embed.set_author(name="Server Stats")
    embed.add_field(name="🖥️ Server Name", value=f"`{name}`",                  inline=False)
    embed.add_field(name="👥 Players",     value=f"`{total} / {max_p}`",       inline=True)
    embed.add_field(name="📶 Avg Ping",    value=f"`{avg_ping} ms`",           inline=True)
    embed.add_field(name="🌐 Address",     value=f"`{SERVER_IP}:{SERVER_PORT}`", inline=True)
    embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
    await interaction.followup.send(embed=embed)

# ============================================================
#  /لوحة — لوحة التحكم بأزرار
# ============================================================
class PanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(label="🎮 اللاعبين", style=discord.ButtonStyle.secondary)
    async def btn_players(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True)
        players_data = await fetch_players()
        if players_data is None:
            await interaction.followup.send(embed=error_embed("❌ السيرفر غير متاح."), ephemeral=True); return
        total = len(players_data)
        embed = discord.Embed(title="FiveM Bot", description=f"**🎮 اللاعبون — {total} لاعب**", color=COLOR_DEFAULT)
        if total == 0:
            embed.description = "⚠️ لا يوجد لاعبون متصلون."
        else:
            chunk = players_data[:25]
            lines = "".join(f"[{str(p.get('id','?')).ljust(4)}] {p.get('name','Unknown')}\n" for p in chunk)
            embed.add_field(name=f"أول {len(chunk)} لاعب", value=f"```gml\n{lines}```", inline=False)
            footer = f"⚡ {total-25} لاعب إضافي — استخدم /players" if total > 25 else f"Server: {SERVER_IP}:{SERVER_PORT}"
            embed.set_footer(text=footer)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="📊 إحصائيات", style=discord.ButtonStyle.secondary)
    async def btn_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True)
        players_data, info_data = await asyncio.gather(fetch_players(), fetch_info())
        if players_data is None:
            await interaction.followup.send(embed=error_embed("❌ السيرفر غير متاح."), ephemeral=True); return
        total    = len(players_data)
        vars_    = info_data.get("vars", {}) if info_data else {}
        max_p    = vars_.get("sv_maxClients", "?")
        name     = info_data.get("name", vars_.get("sv_hostname", "Unknown")) if info_data else "Unknown"
        pings    = [p.get("ping", 0) for p in players_data if isinstance(p.get("ping"), int)]
        avg_ping = round(sum(pings) / len(pings)) if pings else 0
        embed = discord.Embed(title="FiveM Bot", description="**📊 إحصائيات السيرفر**", color=COLOR_DEFAULT)
        embed.set_author(name="Server Stats")
        embed.add_field(name="🖥️ السيرفر",     value=f"`{name}`",                    inline=False)
        embed.add_field(name="🟢 الحالة",       value="أونلاين",                      inline=True)
        embed.add_field(name="👥 اللاعبون",     value=f"`{total} / {max_p}`",         inline=True)
        embed.add_field(name="📶 متوسط البينج", value=f"`{avg_ping} ms`",             inline=True)
        embed.add_field(name="🌐 العنوان",      value=f"`{SERVER_IP}:{SERVER_PORT}`", inline=True)
        embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="ℹ️ معلومات", style=discord.ButtonStyle.secondary)
    async def btn_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="FiveM Bot", description="**ℹ️ كوماندات البوت**", color=COLOR_DEFAULT)
        embed.add_field(name="الكوماندات", value=(
            "`/لوحة` — لوحة التحكم بأزرار\n"
            "`/players` — قائمة كاملة باللاعبين\n"
            "`/id` — البحث بـ Server ID\n"
            "`/search` — البحث بالاسم\n"
            "`/stats` — إحصائيات السيرفر"
        ), inline=False)
        embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="لوحة", description="لوحة تحكم السيرفر بأزرار")
async def cmd_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="FiveM Bot",
        description=f"**🎮 لوحة تحكم السيرفر**\n\n🌐 `{SERVER_IP}:{SERVER_PORT}`\n\nاختر من الأزرار أدناه:",
        color=COLOR_DEFAULT
    )
    embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
    await interaction.response.send_message(embed=embed, view=PanelView())

TOKEN = os.environ.get("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ DISCORD_TOKEN غير موجود")
