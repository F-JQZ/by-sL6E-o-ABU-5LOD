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
#  جلب البيانات
# ============================================================
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}

async def fetch_players():
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=TIMEOUT_SEC),
            connector=aiohttp.TCPConnector(ssl=False)
        ) as s:
            async with s.get(BASE_URL, headers=_HEADERS) as r:
                if r.status == 200:
                    return await r.json(content_type=None)
    except Exception as e:
        print(f"⚠️ players: {e}")
    return None

async def fetch_info():
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=TIMEOUT_SEC),
            connector=aiohttp.TCPConnector(ssl=False)
        ) as s:
            async with s.get(INFO_URL, headers=_HEADERS) as r:
                if r.status == 200:
                    return await r.json(content_type=None)
    except Exception as e:
        print(f"⚠️ info: {e}")
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
            await interaction.followup.send(embed=error_embed("❌ فشل جلب بيانات السيرفر."), ephemeral=True)
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
            await interaction.followup.send(embed=error_embed("❌ فشل جلب بيانات السيرفر."), ephemeral=True)
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
        embed.add_field(name="النتائج", value=f"```gml\n{lines}
```", inline=False)
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
        start_idx = self.current_page * self.per_page
        end_idx = start_idx + self.per_page
        chunk = self.data[start_idx:end_idx]
        total = len(self.data)

        embed = discord.Embed(
            title="SL6E BOT",
            description=f"**🎮 اللاعبون المتصلون — {total} لاعب**",
            color=COLOR_DEFAULT
        )
        
        if total == 0:
            embed.description = "⚠️ لا يوجد لاعبون متصلون حالياً."
        else:
            lines = "".join(f"[{str(p.get('id','?')).ljust(4)}] {p.get('name','Unknown')}\n" for p in chunk)
            embed.add_field(
                name=f"الصفحة {self.current_page + 1} من {self.total_pages} (اللاعبين {start_idx + 1} - {min(end_idx, total)})", 
                value=f"```gml\n{lines}```", 
                inline=False
            )
            embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
        return embed

    def update_buttons(self):
        # تعطيل أو تفعيل الأزرار بناءً على الصفحة الحالية
        self.btn_prev.disabled = self.current_page == 0
        self.btn_next.disabled = self.current_page == self.total_pages - 1

    @discord.ui.button(label="◀️ السابق", style=discord.ButtonStyle.secondary)
    async def btn_prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_page_embed(), view=self)

    @discord.ui.button(label="التالي ▶️", style=discord.ButtonStyle.secondary)
    async def btn_next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_page_embed(), view=self)


# ============================================================
#  View الأزرار الرئيسية
# ============================================================
class PanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # تم تغيير الـ timeout لـ None لضمان عمل اللوحة دائماً بدون توقف

    @discord.ui.button(label="🎮 اللاعبين", style=discord.ButtonStyle.primary, row=0)
    async def btn_players(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True, ephemeral=True)
        data = await fetch_players()
        if data is None:
            await interaction.followup.send(embed=error_embed("❌ السيرفر غير متاح."), ephemeral=True)
            return
        
        # استدعاء كلاس الصفحات هنا ليعرض كل اللاعبين بالتنقل
        paginator = PlayersPaginationView(data, per_page=25)
        await interaction.followup.send(embed=paginator.get_page_embed(), view=paginator, ephemeral=True)

    @discord.ui.button(label="📊 إحصائيات", style=discord.ButtonStyle.primary, row=0)
    async def btn_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True, ephemeral=True)
        data, info = await asyncio.gather(fetch_players(), fetch_info())
        if data is None:
            await interaction.followup.send(embed=error_embed("❌ السيرفر غير متاح."), ephemeral=True)
            return
        total    = len(data)
        vars_    = info.get("vars", {}) if info else {}
        max_p    = vars_.get("sv_maxClients", "?")
        srv      = info.get("name", vars_.get("sv_hostname","Unknown")) if info else "Unknown"
        pings    = [p.get("ping",0) for p in data if isinstance(p.get("ping"),int)]
        avg_ping = round(sum(pings)/len(pings)) if pings else 0
        embed = discord.Embed(title="SL6E BOT", description="**📊 إحصائيات السيرفر**", color=COLOR_DEFAULT)
        embed.add_field(name="🖥️ السيرفر",     value=f"`{srv}`",                     inline=False)
        embed.add_field(name="🟢 الحالة",       value="أونلاين",                      inline=True)
        embed.add_field(name="👥 اللاعبون",     value=f"`{total} / {max_p}`",         inline=True)
        embed.add_field(name="📶 متوسط البينج", value=f"`{avg_ping} ms`",             inline=True)
        embed.add_field(name="🌐 العنوان",      value=f"`{SERVER_IP}:{SERVER_PORT}`", inline=True)
        embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="🔍 بحث بـ ID", style=discord.ButtonStyle.primary, row=1)
    async def btn_search_id(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SearchIDModal())

    @discord.ui.button(label="🔎 بحث بالاسم", style=discord.ButtonStyle.primary, row=1)
    async def btn_search_name(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SearchNameModal())

    @discord.ui.button(label="ℹ️ معلومات", style=discord.ButtonStyle.primary, row=1)
    async def btn_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="SL6E BOT", description="**ℹ️ دليل الاستخدام**", color=COLOR_DEFAULT)
        embed.add_field(name="الأزرار", value=(
            "🎮 **اللاعبين** — عرض اللاعبين المتصلين بالتنقل\n"
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
        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        print(f"✅ مزامنة: {GUILD_ID}")

bot = FiveMBot()

@bot.event
async def on_ready():
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name="BY SL6E & ABO 5LOOD")
    )
    print(f"✅ {bot.user.name}  |  {SERVER_IP}:{SERVER_PORT}")

# ============================================================
#  /لوحة
# ============================================================
@bot.tree.command(name="لوحة", description="🎮 لوحة تحكم السيرفر الكاملة")
async def cmd_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="SL6E BOT",
        description="**🎮 لوحة تحكم السيرفر**",
        color=COLOR_DEFAULT
    )
    embed.set_image(url="attachment://logo.webp")   # ← الصورة في النص، الأزرار تحتها
    logo = get_logo()
    if logo:
        await interaction.response.send_message(embed=embed, view=PanelView(), file=logo, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, view=PanelView(), ephemeral=True)

# ============================================================
TOKEN = os.environ.get("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ DISCORD_TOKEN غير موجود — حط التوكن في متغير DISCORD_TOKEN")
