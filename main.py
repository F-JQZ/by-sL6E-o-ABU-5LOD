import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os
import asyncio
import ssl

# ============================================================
#  إعدادات السيرفر
# ============================================================
SERVER_IP   = "194.45.197.196"
SERVER_PORT = "30120"
GUILD_ID    = 1510735912185630812
BOT_LOGO    = "رابط_الصورة_هنا"  # ← ارفع الصورة على Discord وضع الرابط هنا

BASE_URL = f"http://{SERVER_IP}:{SERVER_PORT}/players.json"
INFO_URL = f"http://{SERVER_IP}:{SERVER_PORT}/info.json"

PLAYERS_PER_FIELD = 25
TIMEOUT_SEC       = 10

COLOR_DEFAULT = 0x5865F2
COLOR_ERROR   = 0xED4245
COLOR_SUCCESS = 0x57F287

# ============================================================
#  مساعدات
# ============================================================
def extract_identifier(identifiers: list, prefix: str):
    for ident in identifiers:
        if ident.startswith(prefix):
            return ident.replace(prefix, "")
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

# ============================================================
#  جلب البيانات
# ============================================================
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

# ============================================================
#  Modal بحث بـ ID
# ============================================================
class SearchIDModal(discord.ui.Modal, title="🔍 بحث بـ Server ID"):
    server_id = discord.ui.TextInput(
        label="Server ID",
        placeholder="مثال: 5",
        min_length=1,
        max_length=6
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            sid = int(self.server_id.value)
        except ValueError:
            await interaction.followup.send(embed=error_embed("❌ أدخل رقماً صحيحاً."), ephemeral=True)
            return

        players_data = await fetch_players()
        if players_data is None:
            await interaction.followup.send(embed=error_embed("❌ فشل جلب بيانات السيرفر."), ephemeral=True)
            return

        target = next((p for p in players_data if p.get("id") == sid), None)
        if not target:
            await interaction.followup.send(embed=error_embed(
                f"❌ لا يوجد لاعب بالـ ID **{sid}**.\n⚡ المتصلون: **{len(players_data)}**"
            ), ephemeral=True)
            return

        identifiers = target.get("identifiers", [])
        steam   = extract_identifier(identifiers, "steam:")
        disc    = extract_identifier(identifiers, "discord:")
        lic     = extract_identifier(identifiers, "license:")

        embed = discord.Embed(title="SL6E BOT", color=COLOR_DEFAULT)
        embed.set_author(name="🔍 ID Search")
        embed.set_thumbnail(url=BOT_LOGO)
        embed.add_field(name="👤 Username",        value=f"`{target.get('name','Unknown')}`",  inline=True)
        embed.add_field(name="🆔 Server ID",       value=f"`{target.get('id','?')}`",          inline=True)
        embed.add_field(name="📶 Ping",            value=f"`{target.get('ping','?')} ms`",     inline=True)
        embed.add_field(name="🟠 Steam",           value=f"`{steam}`"  if steam else "`—`",    inline=True)
        embed.add_field(name="🔵 Discord",         value=f"`{disc}`"   if disc  else "`—`",    inline=True)
        embed.add_field(name="🔑 License",         value=f"`{lic}`"    if lic   else "`—`",    inline=True)
        embed.add_field(name="📋 All Identifiers", value=format_identifiers(identifiers),       inline=False)
        embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
        await interaction.followup.send(embed=embed, ephemeral=True)

# ============================================================
#  Modal بحث بالاسم
# ============================================================
class SearchNameModal(discord.ui.Modal, title="🔎 بحث بالاسم"):
    player_name = discord.ui.TextInput(
        label="اسم اللاعب",
        placeholder="اكتب الاسم أو جزء منه",
        min_length=2,
        max_length=50
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        name = self.player_name.value.strip()
        players_data = await fetch_players()
        if players_data is None:
            await interaction.followup.send(embed=error_embed("❌ فشل جلب بيانات السيرفر."), ephemeral=True)
            return

        results = [p for p in players_data if name.lower() in p.get("name", "").lower()]
        if not results:
            await interaction.followup.send(embed=error_embed(f"❌ لم يُعثر على **\"{name}\"**."), ephemeral=True)
            return

        truncated = len(results) > 20
        results   = results[:20]
        lines = "".join(
            f"[{str(p.get('id','?')).ljust(4)}] {p.get('name','?')}  (ping: {p.get('ping','?')}ms)\n"
            for p in results
        )
        embed = discord.Embed(
            title="SL6E BOT",
            description=f"**🔎 نتائج: \"{name}\"** — {len(results)} نتيجة" + ("\n⚠️ أول 20 فقط" if truncated else ""),
            color=COLOR_SUCCESS
        )
        embed.set_thumbnail(url=BOT_LOGO)
        embed.add_field(name="النتائج", value=f"```gml\n{lines}```", inline=False)
        embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
        await interaction.followup.send(embed=embed, ephemeral=True)

# ============================================================
#  لوحة التحكم View
# ============================================================
class PanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.button(label="🎮 اللاعبين", style=discord.ButtonStyle.secondary, row=0)
    async def btn_players(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True, ephemeral=True)
        players_data = await fetch_players()
        if players_data is None:
            await interaction.followup.send(embed=error_embed("❌ السيرفر غير متاح."), ephemeral=True)
            return
        total = len(players_data)
        embed = discord.Embed(
            title="SL6E BOT",
            description=f"**🎮 اللاعبون المتصلون — {total} لاعب**",
            color=COLOR_DEFAULT
        )
        embed.set_thumbnail(url=BOT_LOGO)
        if total == 0:
            embed.description = "⚠️ لا يوجد لاعبون متصلون حالياً."
        else:
            chunk = players_data[:25]
            lines = "".join(f"[{str(p.get('id','?')).ljust(4)}] {p.get('name','Unknown')}\n" for p in chunk)
            embed.add_field(name=f"أول {len(chunk)} لاعب", value=f"```gml\n{lines}```", inline=False)
            if total > 25:
                embed.set_footer(text=f"⚡ {total-25} لاعب إضافي غير معروض")
            else:
                embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="📊 إحصائيات", style=discord.ButtonStyle.secondary, row=0)
    async def btn_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True, ephemeral=True)
        players_data, info_data = await asyncio.gather(fetch_players(), fetch_info())
        if players_data is None:
            await interaction.followup.send(embed=error_embed("❌ السيرفر غير متاح."), ephemeral=True)
            return
        total    = len(players_data)
        vars_    = info_data.get("vars", {}) if info_data else {}
        max_p    = vars_.get("sv_maxClients", "?")
        name     = info_data.get("name", vars_.get("sv_hostname", "Unknown")) if info_data else "Unknown"
        pings    = [p.get("ping", 0) for p in players_data if isinstance(p.get("ping"), int)]
        avg_ping = round(sum(pings) / len(pings)) if pings else 0
        embed = discord.Embed(title="SL6E BOT", description="**📊 إحصائيات السيرفر**", color=COLOR_DEFAULT)
        embed.set_author(name="Server Stats")
        embed.set_thumbnail(url=BOT_LOGO)
        embed.add_field(name="🖥️ السيرفر",     value=f"`{name}`",                    inline=False)
        embed.add_field(name="🟢 الحالة",       value="أونلاين",                      inline=True)
        embed.add_field(name="👥 اللاعبون",     value=f"`{total} / {max_p}`",         inline=True)
        embed.add_field(name="📶 متوسط البينج", value=f"`{avg_ping} ms`",             inline=True)
        embed.add_field(name="🌐 العنوان",      value=f"`{SERVER_IP}:{SERVER_PORT}`", inline=True)
        embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="🔍 بحث بـ ID", style=discord.ButtonStyle.secondary, row=1)
    async def btn_search_id(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SearchIDModal())

    @discord.ui.button(label="🔎 بحث بالاسم", style=discord.ButtonStyle.secondary, row=1)
    async def btn_search_name(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SearchNameModal())

    @discord.ui.button(label="ℹ️ معلومات", style=discord.ButtonStyle.secondary, row=1)
    async def btn_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="SL6E BOT", description="**ℹ️ دليل الاستخدام**", color=COLOR_DEFAULT)
        embed.set_thumbnail(url=BOT_LOGO)
        embed.add_field(name="الأزرار", value=(
            "🎮 **اللاعبين** — عرض اللاعبين المتصلين\n"
            "📊 **إحصائيات** — إحصائيات السيرفر الكاملة\n"
            "🔍 **بحث بـ ID** — ابحث بـ Server ID\n"
            "🔎 **بحث بالاسم** — ابحث باسم اللاعب\n"
            "ℹ️ **معلومات** — هذه الرسالة"
        ), inline=False)
        embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

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

# ============================================================
#  /لوحة — الكوماند الوحيد
# ============================================================
@bot.tree.command(name="لوحة", description="🎮 لوحة تحكم السيرفر الكاملة")
async def cmd_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="SL6E BOT",
        description="**🎮 لوحة تحكم السيرفر**",
        color=COLOR_DEFAULT
    )
    embed.set_thumbnail(url=BOT_LOGO)
    await interaction.response.send_message(embed=embed, view=PanelView(), ephemeral=True)

# ============================================================
TOKEN = os.environ.get("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ DISCORD_TOKEN غير موجود")
