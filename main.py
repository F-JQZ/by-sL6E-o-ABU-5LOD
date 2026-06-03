import discord
from discord.ext import commands
import aiohttp
import os
import asyncio
import time

# ============================================================
#  إعدادات
# ============================================================
SERVER_IP   = "194.45.197.196"
SERVER_PORT = "30120"
GUILD_ID    = 1510735912185630812
LOGO_FILE   = "logo.webp"

BASE_URL  = f"http://{SERVER_IP}:{SERVER_PORT}/players.json"
INFO_URL  = f"http://{SERVER_IP}:{SERVER_PORT}/info.json"
QUEUE_URL = f"http://{SERVER_IP}:{SERVER_PORT}/queue.json"

FETCH_TIMEOUT       = 5
CACHE_TTL           = 8
PLAYERS_PER_PAGE    = 35
JOIN_HISTORY_MAX    = 15
JOIN_TRACK_INTERVAL = 12

COLOR_DEFAULT = 0x1DA1F2
COLOR_ERROR   = 0xED4245
COLOR_SUCCESS = 0x57F287

BANNER_URL = (
    "https://media.discordapp.net/attachments/1275695804945793035/"
    "1511292593605181471/5dc9d6a7d1853123e5ec5c3017944906.webp"
    "?ex=6a1fec68&is=6a1e9ae8&hm=365d169c6b6b382335ab6a2638b066aadc53c357"
    "be5fce5e5bf1c0f25e1f80da&=&format=webp"
)

# ============================================================
#  كاش
# ============================================================
_cache: dict = {}

def _get_cache(key: str):
    entry = _cache.get(key)
    if entry and time.monotonic() - entry["ts"] < CACHE_TTL:
        return entry["data"]
    return None

def _set_cache(key: str, data):
    _cache[key] = {"data": data, "ts": time.monotonic()}

# ============================================================
#  مساعدات عامة
# ============================================================
def extract_identifier(identifiers: list, prefix: str):
    for i in identifiers:
        if i.startswith(prefix):
            return i.replace(prefix, "")
    return None

def format_identifiers(identifiers: list) -> str:
    mapping = {
        "steam:": "🟠 Steam",
        "discord:": "🔵 Discord",
        "license:": "🔑 License",
        "license2:": "🔑 License2",
        "xbl:": "🟢 Xbox",
        "live:": "🟢 Live",
        "ip:": "🌐 IP",
    }
    lines = []
    for ident in identifiers:
        matched = False
        for prefix, label in mapping.items():
            if ident.startswith(prefix):
                lines.append(f"{label}: `{ident.replace(prefix, '')}`")
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
    embed = discord.Embed(title=" SL6E — لوحة التحكم", color=0x1B6FE4)
    embed.set_image(url=BANNER_URL)
    embed.set_footer(text="SL6E BOT  •  لوحة التحكم")
    return embed

# ============================================================
#  تتبع دخول اللاعبين
# ============================================================
_join_history: list[dict] = []
_known_ids: set[str] = set()
_join_tracker_started = False

def _player_key(p: dict) -> str:
    ids = p.get("identifiers") or []
    lic = extract_identifier(ids, "license:")
    if lic:
        return f"license:{lic}"
    return f"id:{p.get('id')}"

def _record_joins(players: list):
    global _known_ids
    if not players:
        return
    current_keys = {_player_key(p) for p in players}
    if not _known_ids:
        _known_ids = current_keys
        return
    for p in players:
        key = _player_key(p)
        if key not in _known_ids:
            _join_history.insert(0, {
                "name": p.get("name", "?"),
                "id": p.get("id", "?"),
                "ping": p.get("ping", "?"),
                "ts": time.time(),
            })
            _known_ids.add(key)
    _known_ids &= current_keys
    del _join_history[JOIN_HISTORY_MAX:]

def _format_joins_block() -> str:
    if not _join_history:
        return "لا يوجد دخول مسجّل بعد.\nيُحدَّث تلقائياً كل ~12 ثانية."
    lines = []
    for j in _join_history[:JOIN_HISTORY_MAX]:
        ago = int(time.time() - j["ts"])
        lines.append(f"[{str(j['id']).ljust(4)}] {j['name']}  ({j['ping']}ms)  — منذ {ago}s")
    return "```gml\n" + "\n".join(lines) + "\n```"

def _format_queue_block(queue_data, online: int, max_p) -> str:
    if queue_data is None:
        return (
            f"المتصلون: `{online}` / `{max_p}`\n"
            "لا يوجد `queue.json` — فعّل resource الـ queue أو غيّر `QUEUE_URL`."
        )
    if isinstance(queue_data, list):
        if not queue_data:
            return "✅ القائمة فارغة — لا أحد ينتظر."
        lines = []
        for i, q in enumerate(queue_data, 1):
            if isinstance(q, dict):
                name = q.get("name", q.get("displayName", "?"))
                pos = q.get("position", q.get("pos", i))
            else:
                name, pos = str(q), i
            lines.append(f"#{str(pos).ljust(3)} {name}")
        return "```gml\n" + "\n".join(lines) + "\n```"
    if isinstance(queue_data, dict):
        waiting = queue_data.get("queue", queue_data.get("players", []))
        count = queue_data.get("count", len(waiting) if isinstance(waiting, list) else "?")
        head = f"عدد المنتظرين: `{count}`\n"
        if isinstance(waiting, list) and waiting:
            lines = [
                f"#{str(i).ljust(3)} {(w.get('name') if isinstance(w, dict) else str(w))}"
                for i, w in enumerate(waiting, 1)
            ]
            return head + "```gml\n" + "\n".join(lines) + "\n```"
        return head + "✅ لا أحد في الانتظار."
    return f"```json\n{str(queue_data)[:3900]}\n```"

def _add_all_players_fields(embed: discord.Embed, players: list, title_prefix: str = "👥 P"):
    total = len(players)
    if total == 0:
        embed.add_field(name=f"{title_prefix} — Players (0)", value="⚠️ لا يوجد لاعبون متصلون.", inline=False)
        return
    lines_per_field = 28
    idx = 0
    field_num = 0
    while idx < total and field_num < 24:
        chunk = players[idx : idx + lines_per_field]
        text = "".join(
            f"[{str(p.get('id', '?')).ljust(4)}] {p.get('name', '?')}  ({p.get('ping', '?')}ms)\n"
            for p in chunk
        )
        if field_num == 0:
            name = f"{title_prefix} — Players ({total})"
        else:
            name = f"{title_prefix} — ({idx + 1}-{idx + len(chunk)}/{total})"
        embed.add_field(name=name, value=f"```gml\n{text}```", inline=False)
        idx += lines_per_field
        field_num += 1
    if idx < total:
        embed.add_field(
            name="⚠️ باقي اللاعبين",
            value=f"`{total - idx}` لاعب — اضغط **🎮 اللاعبين** للقائمة الكاملة مع صفحات.",
            inline=False,
        )

async def build_qp_embed(refresh: bool = False) -> discord.Embed:
    if refresh:
        _cache.pop("queue", None)
        _cache.pop("players", None)

    players, info, queue_data = await asyncio.gather(fetch_players(), fetch_info(), fetch_queue())
    if players is None:
        return error_embed("❌ السيرفر غير متاح حالياً.")

    _record_joins(players)
    vars_ = (info or {}).get("vars", {})
    max_p = vars_.get("sv_maxClients", "?")
    online = len(players)

    embed = discord.Embed(
        title="SL6E BOT",
        description=f"**Q/P — Queue & Players** (`{online}/{max_p}`)",
        color=COLOR_DEFAULT,
    )
    embed.add_field(name="⏳ Q — Queue", value=_format_queue_block(queue_data, online, max_p), inline=False)
    _add_all_players_fields(embed, players)
    embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
    return embed

async def build_joins_embed() -> discord.Embed:
    players = await fetch_players()
    if players is None:
        return error_embed("❌ السيرفر غير متاح حالياً.")
    _record_joins(players)
    embed = discord.Embed(
        title="SL6E BOT",
        description=f"**🚪 آخر من دخل السيرفر** (آخر {JOIN_HISTORY_MAX})",
        color=COLOR_SUCCESS,
    )
    embed.add_field(name="اللاعبون", value=_format_joins_block(), inline=False)
    embed.set_footer(text="يُحدَّث تلقائياً كل ~12 ثانية")
    return embed

# ============================================================
#  جلب البيانات
# ============================================================
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

async def _fetch_json(url: str, cache_key: str):
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    session: aiohttp.ClientSession = bot.session
    if session is None or session.closed:
        session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False, limit=10))
        bot.session = session

    try:
        async with asyncio.timeout(FETCH_TIMEOUT):
            async with session.get(url, headers=_HEADERS) as r:
                if r.status == 200:
                    data = await r.json(content_type=None)
                    _set_cache(cache_key, data)
                    return data
    except TimeoutError:
        print(f"⏱️ timeout: {url}")
    except Exception as e:
        print(f"⚠️ fetch error [{url}]: {e}")
    return None

async def fetch_players():
    return await _fetch_json(BASE_URL, "players")

async def fetch_info():
    return await _fetch_json(INFO_URL, "info")

async def fetch_queue():
    return await _fetch_json(QUEUE_URL, "queue")

async def _join_tracker_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        data = await fetch_players()
        if data:
            _record_joins(data)
        await asyncio.sleep(JOIN_TRACK_INTERVAL)

# ============================================================
#  Modals
# ============================================================
class SearchIDModal(discord.ui.Modal, title="🔍 بحث بـ Server ID"):
    server_id = discord.ui.TextInput(label="Server ID", placeholder="مثال: 5", min_length=1, max_length=6)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            sid = int(self.server_id.value.strip())
        except ValueError:
            await interaction.followup.send(embed=error_embed("❌ أدخل رقماً صحيحاً."), ephemeral=True)
            return

        data = await fetch_players()
        if data is None:
            await interaction.followup.send(embed=error_embed("❌ فشل جلب بيانات السيرفر."), ephemeral=True)
            return

        target = next((p for p in data if p.get("id") == sid), None)
        if not target:
            await interaction.followup.send(
                embed=error_embed(f"❌ لا يوجد لاعب بالـ ID **{sid}**.\n⚡ المتصلون: **{len(data)}**"),
                ephemeral=True,
            )
            return

        ids = target.get("identifiers", [])
        embed = discord.Embed(title="SL6E BOT", color=COLOR_DEFAULT)
        embed.set_author(name="🔍 نتيجة البحث بـ ID")
        embed.add_field(name="👤 الاسم", value=f"`{target.get('name', 'Unknown')}`", inline=True)
        embed.add_field(name="🆔 ID", value=f"`{target.get('id', '?')}`", inline=True)
        embed.add_field(name="📶 Ping", value=f"`{target.get('ping', '?')} ms`", inline=True)
        embed.add_field(name="🟠 Steam", value=f"`{extract_identifier(ids, 'steam:') or '—'}`", inline=True)
        embed.add_field(name="🔵 Discord", value=f"`{extract_identifier(ids, 'discord:') or '—'}`", inline=True)
        embed.add_field(name="🔑 License", value=f"`{extract_identifier(ids, 'license:') or '—'}`", inline=True)
        embed.add_field(name="📋 كل المعرّفات", value=format_identifiers(ids), inline=False)
        embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
        await interaction.followup.send(embed=embed, ephemeral=True)

class SearchNameModal(discord.ui.Modal, title="🔎 بحث بالاسم"):
    player_name = discord.ui.TextInput(
        label="اسم اللاعب",
        placeholder="اكتب الاسم أو جزء منه",
        min_length=2,
        max_length=50,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        name = self.player_name.value.strip()

        data = await fetch_players()
        if data is None:
            await interaction.followup.send(embed=error_embed("❌ فشل جلب بيانات السيرفر."), ephemeral=True)
            return

        results = [p for p in data if name.lower() in p.get("name", "").lower()]
        if not results:
            await interaction.followup.send(
                embed=error_embed(f"❌ لم يُعثر على **\"{name}\"** بين {len(data)} لاعب متصل."),
                ephemeral=True,
            )
            return

        paginator = PlayersPaginationView(results, per_page=PLAYERS_PER_PAGE)
        embed = paginator.get_page_embed()
        embed.set_author(name=f"🔎 نتائج: \"{name}\" — {len(results)} لاعب (الكل)")
        embed.color = COLOR_SUCCESS
        await interaction.followup.send(embed=embed, view=paginator, ephemeral=True)

# ============================================================
#  Pagination — كل اللاعبين بصفحات
# ============================================================
class PlayersPaginationView(discord.ui.View):
    def __init__(self, players_data: list, per_page: int = PLAYERS_PER_PAGE, title: str | None = None):
        super().__init__(timeout=90)
        self.data = players_data
        self.per_page = per_page
        self.title = title
        self.current_page = 0
        self.total_pages = max(1, (len(players_data) + per_page - 1) // per_page)
        self._update_buttons()

    def get_page_embed(self) -> discord.Embed:
        start = self.current_page * self.per_page
        end = start + self.per_page
        chunk = self.data[start:end]
        total = len(self.data)

        desc = self.title or f"**🎮 اللاعبون المتصلون — {total} لاعب**"
        embed = discord.Embed(title="SL6E BOT", description=desc, color=COLOR_DEFAULT)

        if total == 0:
            embed.description = "⚠️ لا يوجد لاعبون متصلون حالياً."
        else:
            lines = "".join(
                f"[{str(p.get('id', '?')).ljust(4)}] {p.get('name', 'Unknown')}  ({p.get('ping', '?')}ms)\n"
                for p in chunk
            )
            embed.add_field(
                name=f"الصفحة {self.current_page + 1}/{self.total_pages}  (#{start + 1}–#{min(end, total)} من {total})",
                value=f"```gml\n{lines}```",
                inline=False,
            )
        embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
        return embed

    def _update_buttons(self):
        self.btn_prev.disabled = self.current_page == 0
        self.btn_next.disabled = self.current_page >= self.total_pages - 1

    @discord.ui.button(label="◀️ السابق", style=discord.ButtonStyle.secondary)
    async def btn_prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self._update_buttons()
            await interaction.response.edit_message(embed=self.get_page_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="التالي ▶️", style=discord.ButtonStyle.secondary)
    async def btn_next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self._update_buttons()
            await interaction.response.edit_message(embed=self.get_page_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="🔄 تحديث", style=discord.ButtonStyle.success)
    async def btn_refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        _cache.pop("players", None)
        fresh = await fetch_players()
        if fresh is None:
            await interaction.followup.send(embed=error_embed("❌ فشل التحديث."), ephemeral=True)
            return
        self.data = fresh
        self.total_pages = max(1, (len(fresh) + self.per_page - 1) // self.per_page)
        self.current_page = min(self.current_page, self.total_pages - 1)
        self._update_buttons()
        await interaction.edit_original_response(embed=self.get_page_embed(), view=self)

# ============================================================
#  لوحة التحكم
# ============================================================
class PanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎮 اللاعبين", style=discord.ButtonStyle.primary, row=0)
    async def btn_players(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True, ephemeral=True)
        data = await fetch_players()
        if data is None:
            await interaction.followup.send(embed=error_embed("❌ السيرفر غير متاح."), ephemeral=True)
            return
        paginator = PlayersPaginationView(data, per_page=PLAYERS_PER_PAGE)
        await interaction.followup.send(embed=paginator.get_page_embed(), view=paginator, ephemeral=True)

    @discord.ui.button(label="📊 إحصائيات", style=discord.ButtonStyle.primary, row=0)
    async def btn_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True, ephemeral=True)
        data, info = await asyncio.gather(fetch_players(), fetch_info())
        if data is None:
            await interaction.followup.send(embed=error_embed("❌ السيرفر غير متاح."), ephemeral=True)
            return

        total = len(data)
        vars_ = (info or {}).get("vars", {})
        max_p = vars_.get("sv_maxClients", "?")
        srv_name = (info or {}).get("name", vars_.get("sv_hostname", "Unknown"))
        pings = [p.get("ping", 0) for p in data if isinstance(p.get("ping"), int)]
        avg_ping = round(sum(pings) / len(pings)) if pings else 0
        bar_filled = int((total / int(max_p)) * 10) if str(max_p).isdigit() and int(max_p) > 0 else 0
        bar = "█" * bar_filled + "░" * (10 - bar_filled)

        embed = discord.Embed(title="SL6E BOT", description="**📊 إحصائيات السيرفر**", color=COLOR_DEFAULT)
        embed.add_field(name="🖥️ السيرفر", value=f"`{srv_name}`", inline=False)
        embed.add_field(name="🟢 الحالة", value="**أونلاين**", inline=True)
        embed.add_field(name="👥 اللاعبون", value=f"`{total} / {max_p}`", inline=True)
        embed.add_field(name="📶 متوسط البينج", value=f"`{avg_ping} ms`", inline=True)
        embed.add_field(name="📈 نسبة الامتلاء", value=f"`[{bar}] {total}/{max_p}`", inline=False)
        embed.add_field(name="🌐 العنوان", value=f"`{SERVER_IP}:{SERVER_PORT}`", inline=True)
        embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="🔍 بحث بـ ID", style=discord.ButtonStyle.primary, row=1)
    async def btn_search_id(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SearchIDModal())

    @discord.ui.button(label="🔎 بحث بالاسم", style=discord.ButtonStyle.primary, row=1)
    async def btn_search_name(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SearchNameModal())

    @discord.ui.button(label="ℹ️ مساعدة", style=discord.ButtonStyle.primary, row=1)
    async def btn_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="SL6E BOT — دليل الاستخدام", color=COLOR_DEFAULT)
        embed.add_field(
            name="الأزرار",
            value=(
                "🎮 **اللاعبين** — **كل** المتصلين مع صفحات (◀️ ▶️)\n"
                "📊 **إحصائيات** — حالة السيرفر\n"
                "**Q/P** — Queue + **كل** اللاعبين\n"
                "🚪 **دخول** — آخر من دخل السيرفر\n"
                "🔍 **بحث ID** — معلومات لاعب\n"
                "🔎 **بحث اسم** — **كل** النتائج بصفحات (بدون حد 20)\n"
                "ℹ️ **مساعدة** — هذا الدليل"
            ),
            inline=False,
        )
        embed.add_field(
            name="💡 ملاحظات",
            value=(
                f"• كل صفحة تعرض {PLAYERS_PER_PAGE} لاعب — استخدم التالي للباقي\n"
                "• كاش 8 ثواني — زر 🔄 للتحديث\n"
                "• Queue يحتاج `queue.json` على السيرفر\n"
                "• الدخول يُسجَّل تلقائياً كل ~12 ثانية"
            ),
            inline=False,
        )
        embed.set_footer(text=f"Server: {SERVER_IP}:{SERVER_PORT}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Q/P", style=discord.ButtonStyle.secondary, row=2)
    async def btn_qp(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True, ephemeral=True)
        await interaction.followup.send(embed=await build_qp_embed(refresh=True), ephemeral=True)

    @discord.ui.button(label="🚪 دخول", style=discord.ButtonStyle.success, row=2)
    async def btn_joins(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True, ephemeral=True)
        await interaction.followup.send(embed=await build_joins_embed(), ephemeral=True)

# ============================================================
#  البوت
# ============================================================
class FiveMBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)
        self.session: aiohttp.ClientSession | None = None

    async def setup_hook(self):
        self.session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False, limit=10))
        self.add_view(PanelView())
        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)
        print(f"✅ مزامنة {len(synced)} أمر للسيرفر {GUILD_ID}")

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
        await super().close()

bot = FiveMBot()

@bot.event
async def on_ready():
    global _join_tracker_started
    await bot.change_presence(
        activity=discord.Streaming(name="BY SL6E & ABO 5LOOD", url="https://www.twitch.tv/placeholder"),
    )
    if not _join_tracker_started:
        _join_tracker_started = True
        asyncio.create_task(_join_tracker_loop())
    print(f"✅ {bot.user.name}  |  {SERVER_IP}:{SERVER_PORT}")

async def _auto_delete(interaction: discord.Interaction, delay: int = 900):
    await asyncio.sleep(delay)
    try:
        await interaction.delete_original_response()
    except Exception:
        pass

@bot.tree.command(name="لوحة", description="🎮 لوحة تحكم السيرفر الكاملة")
async def cmd_panel(interaction: discord.Interaction):
    await interaction.response.send_message(embed=panel_embed(), view=PanelView(), ephemeral=True)
    asyncio.create_task(_auto_delete(interaction, delay=900))

@bot.tree.command(name="qp", description="⏳ Queue + 👥 كل اللاعبين")
async def cmd_qp(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=True)
    await interaction.followup.send(embed=await build_qp_embed(refresh=True), ephemeral=True)

@bot.tree.command(name="دخول", description="🚪 آخر من دخل السيرفر")
async def cmd_joins(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=True)
    await interaction.followup.send(embed=await build_joins_embed(), ephemeral=True)

@bot.tree.command(name="لاعبين", description="🎮 كل اللاعبين المتصلين")
async def cmd_all_players(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=True)
    data = await fetch_players()
    if data is None:
        await interaction.followup.send(embed=error_embed("❌ السيرفر غير متاح."), ephemeral=True)
        return
    paginator = PlayersPaginationView(data, per_page=PLAYERS_PER_PAGE)
    await interaction.followup.send(embed=paginator.get_page_embed(), view=paginator, ephemeral=True)

# ============================================================
TOKEN = os.environ.get("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ DISCORD_TOKEN غير موجود. أضفه في .env أو متغيرات البيئة.")
