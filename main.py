from discord.ext import commands
from discord import app_commands
import aiohttp
import os
import math
import asyncio
import os
# ============================================================
#  إعدادات السيرفر — غيّر هذه القيم
import ssl
# ============================================================
#  إعدادات السيرفر
# ============================================================
SERVER_IP   = "194.45.197.196"
SERVER_PORT = "30120"
-12
+14
BASE_URL = f"http://{SERVER_IP}:{SERVER_PORT}/players.json"
INFO_URL = f"http://{SERVER_IP}:{SERVER_PORT}/info.json"
COLOR_DEFAULT = 0x23272A   # لون داكن Discord
COLOR_ERROR   = 0xED4245   # أحمر
COLOR_SUCCESS = 0x57F287   # أخضر
COLOR_WARN    = 0xFEE75C   # أصفر
PLAYERS_PER_FIELD = 25
TIMEOUT_SEC       = 10
# صورة FiveM بديلة (من CDN رسمي)
FIVEM_THUMBNAIL  = "https://cdn.discordapp.com/emojis/1060951257456812082.png"
PLAYERS_PER_FIELD = 25   # عدد اللاعبين في كل حقل داخل الـ embed
TIMEOUT_SEC       = 10   # رفعنا الـ timeout
COLOR_DEFAULT = 0x5865F2
COLOR_ERROR   = 0xED4245
COLOR_SUCCESS = 0x57F287
# ============================================================
#  مساعدات
# ============================================================
def extract_id(identifiers: list, prefix: str):
    for i in identifiers:
        if i.startswith(prefix):
            return i.replace(prefix, "")
def extract_identifier(identifiers: list, prefix: str):
    for ident in identifiers:
        if ident.startswith(prefix):
            return ident.replace(prefix, "")
    return None
def format_ids(identifiers: list) -> str:
def format_identifiers(identifiers: list) -> str:
    lines = []
    mapping = {
        "steam:"   : "🟠 Steam",
        "discord:" : "🔵 Discord",
-1
+0
        "live:"    : "🟢 Live",
        "ip:"      : "🌐 IP",
    }
    lines = []
    for ident in identifiers:
        matched = False
        for prefix, label in mapping.items():
-17
+57
            lines.append(f"🔹 `{ident}`")
    return "\n".join(lines) if lines else "لا توجد معرّفات"
def err_embed(msg: str) -> discord.Embed:
    e = discord.Embed(description=msg, color=COLOR_ERROR)
    e.set_footer(text=f"🌐 {SERVER_IP}:{SERVER_PORT}")
    return e
# ============================================================
#  جلب البيانات
def error_embed(message: str) -> discord.Embed:
    embed = discord.Embed(title="FiveM Bot", description=message, color=COLOR_ERROR)
    embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
    return embed
# ============================================================
#  جلب البيانات — مع عدة محاولات وهيدرات متعددة
# ============================================================
HEADERS_LIST = [
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"},
    {"User-Agent": "FiveM/1.0 (compatible)"},
    {"User-Agent": "curl/7.88.1"},
]
async def fetch_players():
    timeout = aiohttp.ClientTimeout(total=TIMEOUT_SEC)
    for h in HEADERS_LIST:
    for headers in HEADERS_LIST:
        try:
            async with aiohttp.ClientSession(timeout=timeout, connector=aiohttp.TCPConnector(ssl=False)) as s:
                async with s.get(BASE_URL, headers=h) as r:
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                async with session.get(BASE_URL, headers=headers) as r:
                    if r.status == 200:
                        return await r.json(content_type=None)
        except Exception:
            pass
        except Exception as e:
            print(f"⚠️ محاولة فاشلة ({headers['User-Agent'][:20]}): {e}")
    return None
async def fetch_info():
    timeout = aiohttp.ClientTimeout(total=TIMEOUT_SEC)
    try:
        async with aiohttp.ClientSession(timeout=timeout, connector=aiohttp.TCPConnector(ssl=False)) as s:
            async with s.get(INFO_URL, headers=HEADERS_LIST[0]) as r:
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            async with session.get(INFO_URL, headers=HEADERS_LIST[0]) as r:
                if r.status == 200:
                    return await r.json(content_type=None)
    except Exception:
        pass
    except Exception as e:
        print(f"❌ fetch_info: {e}")
    return None
# ============================================================
#  بناء embed القائمة الكاملة
# ============================================================
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
                description=(
                    "Become a **patron** today to get the benefits of **FiveM Bot Pro**.\n"
                    f"Learn more [here](https://fivem.net).\n\n"
                    f"**Player List • TOTAL: {total} players**"
                ),
                color=COLOR_DEFAULT
            )
        else:
            embed = discord.Embed(color=COLOR_DEFAULT)
        for chunk in group:
            lines = "".join(f"[{str(p.get('id','?')).ljust(4)}] {p.get('name','Unknown')}\n" for p in chunk)
            start_id = chunk[0].get('id', '?')
            end_id   = chunk[-1].get('id', '?')
            embed.add_field(
                name=f"Players ({start_id} → {end_id})",
                value=f"```gml\n{lines}```",
                inline=False
            )
        embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
        embeds.append(embed)
    return embeds
# ============================================================
#  البوت
-6
+11
        super().__init__(command_prefix="!", intents=intents)
    async def setup_hook(self):
        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        try:
            await self.tree.sync(guild=guild)
            print(f"✅ تمت المزامنة للسيرفر: {GUILD_ID}")
        except discord.Forbidden:
        if GUILD_ID:
            try:
                guild = discord.Object(id=GUILD_ID)
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                print(f"✅ مزامنة فورية للسيرفر: {GUILD_ID}")
            except discord.Forbidden:
                print("⚠️ فشلت المزامنة الفورية، جاري التحويل للمزامنة العالمية...")
                await self.tree.sync()
                print("✅ مزامنة عالمية تمت بنجاح.")
        else:
            await self.tree.sync()
            print("✅ مزامنة عالمية.")
-6
+91
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="FiveM Server 🎮"
            name="BY SL6E & ABO 5LOOD"
        )
    )
    print(f"✅ البوت شغال: {bot.user.name}")
# ============================================================
#  /لوحة — لوحة التحكم الرئيسية بأزرار
    print(f"✅ البوت شغال: {bot.user.name}  |  {SERVER_IP}:{SERVER_PORT}")
# ============================================================
#  /players
# ============================================================
@bot.tree.command(name="players", description="عرض قائمة كاملة لجميع اللاعبين المتصلين")
async def cmd_players(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    players_data = await fetch_players()
    if players_data is None:
        await interaction.followup.send(embed=error_embed(
            "❌ **فشل الاتصال بالسيرفر**\n"
            "السيرفر قد يكون:\n"
            "• مقفل الـ firewall أمام طلبات خارجية\n"
            "• متوقف عن العمل مؤقتاً\n"
            "• الـ IP أو Port غلط"
        ))
        return
    if len(players_data) == 0:
        await interaction.followup.send(embed=error_embed("⚠️ لا يوجد لاعبون متصلون حالياً."))
        return
    embeds = build_full_players_embed(players_data)
    await interaction.followup.send(embeds=embeds[:10])
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
    identifiers   = target.get("identifiers", [])
    steam_raw     = extract_identifier(identifiers, "steam:")
    discord_raw   = extract_identifier(identifiers, "discord:")
    license_raw   = extract_identifier(identifiers, "license:")
    steam_value   = f"`{steam_raw}`"                       if steam_raw   else "`غير مرتبط`"
    discord_value = f"<@{discord_raw}> (`{discord_raw}`)" if discord_raw else "`غير مرتبط`"
    license_value = f"`{license_raw}`"                     if license_raw else "`—`"
    embed = discord.Embed(
        title="FiveM Bot",
        description="Have feedback or suggestions? Fill out the [FiveM Bot feedback form](https://fivem.net) and help improve the service for all.",
        color=COLOR_DEFAULT
    )
    embed.set_author(name="ID Search")
    embed.add_field(name="Username",           value=f"`{target.get('name','Unknown')}`", inline=True)
    embed.add_field(name="Server ID",          value=f"`{target.get('id','?')}`",         inline=True)
    embed.add_field(name="Ping",               value=f"`{target.get('ping','?')} ms`",    inline=True)
    embed.add_field(name="🟠 Steam",           value=steam_value,                          inline=True)
    embed.add_field(name="🔵 Discord",         value=discord_value,                        inline=True)
    embed.add_field(name="🔑 License",         value=license_value,                        inline=True)
    embed.add_field(name="📋 All Identifiers", value=format_identifiers(identifiers),      inline=False)
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
    results = [p for p in players_data if name.strip().lower() in p.get("name", "").lower()]
    if not results:
        await interaction.followup.send(embed=error_embed(f"❌ لم يُعثر على لاعب يحتوي اسمه على **\"{name}\"**."))
        return
    truncated = len(results) > 20
    results   = results[:20]
    lines = "".join(f"[{s...
