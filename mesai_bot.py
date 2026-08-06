# -*- coding: utf-8 -*-
"""
Mesai Botu v3.1 - Panel Sistemi (Render/GitHub uyumlu)
- /panel komutu ile otomatik panel kurulumu
- Canli durum (60 sn'de bir guncellenir)
- Butonlar: Mesai Baslat / Mesai Bitir / Bilgilerim / Siralama
- Ses kanali takibi devam eder
"""

import asyncio
import json
import os
import time
from datetime import datetime

import discord
from aiohttp import web
from discord.ext import commands, tasks
from discord import app_commands

# ============================================================
# AYARLAR
# ============================================================
TOKEN = os.environ.get("BOT_TOKEN", "")
if not TOKEN:
    print("[-] BOT_TOKEN bulunamadi!")
    raise SystemExit(1)

MESAI_CHANNELS = ["aktif chief", "aktif memur"]

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mesailer.json")
PANEL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "panel_state.json")

LINE = "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"


def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return default
    return default

def save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def format_duration(seconds):
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds} sn"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} dk {seconds % 60} sn"
    hours = minutes // 60
    if hours < 48:
        return f"{hours} sa {minutes % 60} dk"
    days = hours // 24
    return f"{days} gn {hours % 24} sa"

def format_short(seconds):
    seconds = int(seconds)
    minutes = seconds // 60
    hours = minutes // 60
    if hours > 0:
        return f"{hours} sa {minutes % 60} dk"
    return f"{minutes} dk {seconds % 60} sn"

def progress_bar(current, max_seconds, width=10):
    if max_seconds <= 0:
        return "\u2591" * width
    filled = min(int(current / max_seconds * width), width)
    return "\u2588" * filled + "\u2591" * (width - filled)


intents = discord.Intents.default()
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)
data = load_json(DATA_FILE, {})
active_sessions = {}
panel_state = load_json(PANEL_FILE, {})


def is_mesai_channel(channel):
    if channel is None:
        return False
    return channel.name.lower() in [c.lower() for c in MESAI_CHANNELS]


def build_panel_embed():
    active_count = len(active_sessions)

    embed = discord.Embed(
        title="\u23f1\ufe0f **MESA\u0130 PANEL\u0130**",
        description=(
            f"\U0001f525 **Mesaiye ba\u015flamak \u00e7ok kolay:**\n\n"
            "\U0001f509 Ses kanal\u0131na gir \u2192 \U0001f7e2 butona bas \u2192 mesain ba\u015flas\u0131n! \U0001f680\n\n"
            f"{LINE}\n"
            "\U0001f7e2 **Mesai Ba\u015flat** \u2014 Mesaiye ba\u015fla, s\u00fcre saymaya ba\u015flas\u0131n\n"
            "\U0001f534 **Mesai Bitir** \u2014 Mesaiyi bitir, s\u00fcren kay\u0131tlara ge\u00e7sin\n"
            "\U0001f4ca **Bilgilerim** \u2014 Kendi mesai istatistiklerini g\u00f6r\n"
            "\U0001f3c6 **S\u0131ralama** \u2014 Liderlik tablosunu g\u00f6r\n"
            f"{LINE}\n\n"
            "\U0001f6a9 **Kurallar:**\n"
            "\u25b6\ufe0f Mesai yaln\u0131zca **Aktif Chief** ve **Aktif Memur** ses kanallar\u0131nda say\u0131l\u0131r\n"
            "\u25b6\ufe0f Kanaldan \u00e7\u0131karsan mesain otomatik kapan\u0131r\n"
            "\u25b6\ufe0f Mesaiyi bitirmeyi unutma, butona bas ve s\u00fcreni g\u00fcvenceye al!"
        ),
        color=discord.Color.brand_green(),
    )

    if active_count > 0:
        lines = []
        for i, (uid, session) in enumerate(list(active_sessions.items())[:8], 1):
            member_name = session.get("name", f"<@{uid}>")
            elapsed = format_short(time.time() - session["start"])
            lines.append(f"`{i:2d}` \U0001f7e2 **{member_name}** \u2014 \u23f1\ufe0f {elapsed} \u2022 {session['channel']}")
        durum = "\n".join(lines)
        if active_count > 8:
            durum += f"\n\n\U0001f4c8 +{active_count - 8} ki\u015fi daha mesaide..."
    else:
        durum = "\U0001f634 Kimse mesaide de\u011fil... \u0130lk mesaiye ba\u015flayan sen ol!"

    embed.add_field(name="\U0001f4e1 \u015eU AN MESA\u0130DE: " + str(active_count), value=durum, inline=False)
    embed.set_footer(text="\U0001f534 = mesaide \u2022 S\u0131ralama i\u00e7in \U0001f3c6 butonuna bas \u2022 60 sn'de bir g\u00fcncellenir \U0001f552")
    return embed


def build_top_embed():
    if not data:
        embed = discord.Embed(
            title="\U0001f3c6 **MESA\u0130 SIRALAMASI**",
            description="Hen\u00fcz mesai kayd\u0131 yok! \U0001f634",
            color=discord.Color.gold(),
        )
        return embed

    sorted_users = sorted(data.items(), key=lambda x: x[1]["total_seconds"], reverse=True)
    top10 = sorted_users[:10]
    max_seconds = sorted_users[0][1]["total_seconds"]
    total_seconds = sum(ud["total_seconds"] for _, ud in sorted_users)

    embed = discord.Embed(
        title="\U0001f3c6 **MESA\u0130 SIRALAMASI**",
        description=(
            f"{LINE}\n"
            f"\U0001f465 Toplam **{len(data)}** ki\u015fi \u2022 \U0001f552 Toplam **{format_duration(total_seconds)}** mesai\n"
            f"{LINE}"
        ),
        color=discord.Color.gold(),
    )

    lines = []
    for i, (user_id, ud) in enumerate(top10):
        if i == 0:
            rank = "\U0001f451"
        elif i == 1:
            rank = "\U0001f948"
        elif i == 2:
            rank = "\U0001f949"
        else:
            rank = f"\U0001f539 **{i+1}.**"

        active_mark = "\U0001f534" if user_id in active_sessions else ""
        bar = progress_bar(ud["total_seconds"], max_seconds)
        sessions = ud.get("sessions", [])
        ses_bilgi = f"\U0001f4cb {len(sessions)} seans"

        lines.append(
            f"{rank} **{ud['name']}** {active_mark}\n"
            f"> \u23f1\ufe0f **{format_duration(ud['total_seconds'])}** \u2022 {ses_bilgi}\n"
            f"> `{bar}`"
        )

    embed.add_field(name="\U0001f3af TOP 10", value="\n".join(lines), inline=False)
    embed.set_footer(text="\U0001f534 = \u015fu an mesaide \u2022 Mesai Botu v3.1")
    return embed


class PanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    def _start_mesai(self, interaction):
        user_id = str(interaction.user.id)

        voice_state = interaction.user.voice
        in_mesai_channel = False
        channel_name = "?"

        if voice_state and voice_state.channel:
            if is_mesai_channel(voice_state.channel):
                in_mesai_channel = True
                channel_name = voice_state.channel.name

        if not in_mesai_channel:
            return (False, "Ses kanal\u0131na girmedin! \U0001f4a4 \u00d6nce **Aktif Chief** veya **Aktif Memur** ses kanal\u0131na gir.")

        if user_id in active_sessions:
            return (False, "Zaten mesaide g\u00f6r\u00fcn\u00fcyorsun! \U0001f605")

        active_sessions[user_id] = {
            "start": time.time(),
            "channel": channel_name,
            "guild": interaction.guild.id,
            "name": interaction.user.display_name,
        }
        return (True, f"\u2705 Mesain ba\u015flad\u0131! ({channel_name}) \U0001f4c8")

    def _end_mesai(self, interaction):
        user_id = str(interaction.user.id)
        session = active_sessions.pop(user_id, None)
        if not session:
            return (False, "Aktif mesain yok! \U0001f937")

        start = session["start"]
        end = time.time()
        duration = end - start

        user_data = data.get(user_id, {"name": str(interaction.user), "total_seconds": 0, "sessions": []})
        user_data["name"] = str(interaction.user)
        user_data["total_seconds"] += int(duration)
        user_data["sessions"].append({
            "start": datetime.fromtimestamp(start).isoformat(),
            "end": datetime.fromtimestamp(end).isoformat(),
            "duration": int(duration),
            "channel": session["channel"],
        })
        data[user_id] = user_data
        save_json(DATA_FILE, data)

        return (True, f"\u2705 Mesain kapand\u0131! S\u00fcre: **{format_duration(duration)}** \U0001f3af")

    @discord.ui.button(label="Mesai Ba\u015flat", style=discord.ButtonStyle.success, emoji="\U0001f7e2", custom_id="mesai_start")
    async def start_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        ok, msg = self._start_mesai(interaction)

        embed = discord.Embed(
            title="\u2705 Mesai" if ok else "\u274c Hata",
            description=msg,
            color=discord.Color.brand_green() if ok else discord.Color.brand_red(),
        )
        embed.set_footer(text=f"{interaction.user.display_name}")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await self._refresh_panel()

    @discord.ui.button(label="Mesai Bitir", style=discord.ButtonStyle.danger, emoji="\U0001f534", custom_id="mesai_end")
    async def end_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        ok, msg = self._end_mesai(interaction)

        embed = discord.Embed(
            title="\u2705 Mesai Kapand\u0131" if ok else "\u274c Hata",
            description=msg,
            color=discord.Color.brand_green() if ok else discord.Color.brand_red(),
        )
        embed.set_footer(text=f"{interaction.user.display_name}")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await self._refresh_panel()

    @discord.ui.button(label="Bilgilerim", style=discord.ButtonStyle.primary, emoji="\U0001f4ca", custom_id="mesai_info", row=1)
    async def info_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        user_data = data.get(user_id)

        if not user_data or user_data["total_seconds"] == 0:
            embed = discord.Embed(
                title="\U0001f4ca Bilgilerim",
                description=f"Hen\u00fcz mesai kayd\u0131n yok! \U0001f634",
                color=discord.Color.blue(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = discord.Embed(
            title="\U0001f4ca Bilgilerim",
            description=f"**{interaction.user.display_name}**",
            color=discord.Color.blue(),
        )
        embed.add_field(name="\U0001f3af Toplam Mesai", value=f"\u23f1\ufe0f {format_duration(user_data['total_seconds'])}", inline=True)
        embed.add_field(name="\U0001f4cb Toplam Seans", value=str(len(user_data["sessions"])), inline=True)
        if str(user_id) in active_sessions:
            embed.add_field(name="\U0001f534 Durum", value="\u015fu an mesaide!", inline=True)

        recent = user_data["sessions"][-3:]
        if recent:
            lines = []
            for s in recent:
                d = format_short(s["duration"])
                start = datetime.fromisoformat(s["start"]).strftime("%d.%m %H:%M")
                lines.append(f"\U0001f553 `{start}` \u2014 **{d}** ({s['channel']})")
            embed.add_field(name="\U0001f5de\ufe0f Son Mesailer", value="\n".join(lines), inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="S\u0131ralama", style=discord.ButtonStyle.secondary, emoji="\U0001f3c6", custom_id="mesai_top", row=1)
    async def top_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=build_top_embed(), ephemeral=True)

    async def _refresh_panel(self):
        try:
            await update_panel()
        except Exception as e:
            print(f"[-] Panel guncelleme hatasi: {e}")


async def update_panel():
    if not panel_state:
        return
    channel = bot.get_channel(panel_state.get("channel"))
    if channel is None:
        return
    message = await channel.fetch_message(panel_state.get("message"))
    await message.edit(embed=build_panel_embed(), view=PanelView())


@tasks.loop(seconds=60)
async def live_panel_loop():
    try:
        await update_panel()
    except Exception as e:
        print(f"[-] Canli panel hatasi: {e}")


@bot.event
async def on_voice_state_update(member, before, after):
    user_id = str(member.id)

    if user_id in active_sessions:
        if before.channel and is_mesai_channel(before.channel):
            if after.channel != before.channel:
                session = active_sessions.pop(user_id)
                duration = time.time() - session["start"]

                user_data = data.get(user_id, {"name": str(member), "total_seconds": 0, "sessions": []})
                user_data["name"] = str(member)
                user_data["total_seconds"] += int(duration)
                user_data["sessions"].append({
                    "start": datetime.fromtimestamp(session["start"]).isoformat(),
                    "end": datetime.now().isoformat(),
                    "duration": int(duration),
                    "channel": session["channel"],
                })
                data[user_id] = user_data
                save_json(DATA_FILE, data)
                print(f"[*] MESAI KAPANDI (ses): {member.name} -> {format_duration(duration)}")

                try:
                    await before.channel.send(f"\u23f1\ufe0f {member.mention} mesaisi kapand\u0131! S\u00fcre: **{format_duration(duration)}**")
                except:
                    pass

    if after.channel and is_mesai_channel(after.channel):
        if user_id not in active_sessions:
            active_sessions[user_id] = {
                "start": time.time(),
                "channel": after.channel.name,
                "guild": member.guild.id,
                "name": member.display_name,
            }
            print(f"[*] MESAI BASLADI (ses): {member.name} -> {after.channel.name}")
            try:
                await after.channel.send(f"\u23f1\ufe0f {member.mention} mesaiye ba\u015flad\u0131! ({after.channel.name})")
            except:
                pass

    await update_panel()


@bot.tree.command(name="panel", description="Mesai panelini otomatik kurar")
@app_commands.default_permissions(administrator=True)
async def panel(interaction: discord.Interaction):
    await interaction.response.send_message(embed=build_panel_embed(), view=PanelView())
    message = await interaction.original_response()
    panel_state["channel"] = message.channel.id
    panel_state["message"] = message.id
    panel_state["guild"] = interaction.guild.id
    save_json(PANEL_FILE, panel_state)
    print(f"[+] Panel kuruldu: #{message.channel.name}")


@bot.tree.command(name="mesaim", description="Kendi toplam mesai sureni gosterir")
async def mesaim(interaction: discord.Interaction):
    user_data = data.get(str(interaction.user.id))
    if not user_data or user_data["total_seconds"] == 0:
        await interaction.response.send_message(f"Hen\u00fcz mesai kayd\u0131n yok! \U0001f634", ephemeral=True)
        return

    embed = discord.Embed(
        title="\U0001f3af Mesai Bilgisi",
        description=f"**{interaction.user.display_name}**",
        color=discord.Color.blue(),
    )
    embed.add_field(name="\U0001f4c8 Toplam Mesai", value=f"\u23f1\ufe0f {format_duration(user_data['total_seconds'])}", inline=False)
    embed.add_field(name="\U0001f4cb Toplam Seans", value=str(len(user_data["sessions"])), inline=True)
    if str(interaction.user.id) in active_sessions:
        embed.add_field(name="\U0001f534 Durum", value="\u015fu an mesaide!", inline=True)

    recent = user_data["sessions"][-5:]
    if recent:
        lines = []
        for s in recent:
            d = format_short(s["duration"])
            start = datetime.fromisoformat(s["start"]).strftime("%d.%m %H:%M")
            lines.append(f"\U0001f553 `{start}` \u2014 **{d}** ({s['channel']})")
        embed.add_field(name="\U0001f5de\ufe0f Son Mesailer", value="\n".join(lines), inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="siralama", description="Mesai siralamasi")
async def siralama(interaction: discord.Interaction):
    await interaction.response.send_message(embed=build_top_embed())


@bot.tree.command(name="mesaiaktif", description="Su an mesaidesi olanlar")
async def mesaiaktif(interaction: discord.Interaction):
    if not active_sessions:
        await interaction.response.send_message("Su an mesaide kimse yok! \U0001f634", ephemeral=True)
        return

    lines = []
    for i, (user_id, session) in enumerate(list(active_sessions.items()), 1):
        member = interaction.guild.get_member(int(user_id))
        elapsed = time.time() - session["start"]
        name = member.display_name if member else f"<@{user_id}>"
        lines.append(f"{i}. \U0001f7e2 **{name}** \u2014 {format_short(elapsed)} ({session['channel']})")

    embed = discord.Embed(
        title="\U0001f4a1 **\u015eu An Mesaide**",
        description=f"\U0001f465 **{len(active_sessions)} ki\u015fi** mesaide\n\n" + "\n".join(lines),
        color=discord.Color.brand_green(),
    )
    await interaction.response.send_message(embed=embed)


@bot.event
async def on_ready():
    print(f"[+] Bot giris yapti: {bot.user}")
    print(f"[+] Mesai kanallari: {', '.join(MESAI_CHANNELS)}")
    print(f"[+] Veri dosyasi: {DATA_FILE}")
    try:
        synced = await bot.tree.sync()
        print(f"[+] {len(synced)} komut senkronize edildi")
    except Exception as e:
        print(f"[-] Komut senkronizasyon hatasi: {e}")

    bot.add_view(PanelView())
    if panel_state:
        live_panel_loop.start()

    try:
        app = web.Application()

        async def health(request):
            return web.Response(text="ok")

        app.router.add_get("/", health)
        runner = web.AppRunner(app)
        await runner.setup()
        port = int(os.environ.get("PORT", 10000))
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        print(f"[+] HTTP saglik kontrolu port {port}'de basladi")
    except Exception as e:
        print(f"[-] HTTP baslatilamadi: {e}")

    if os.environ.get("GITHUB_ACTIONS") == "true":
        bot.loop.create_task(auto_shutdown())


async def auto_shutdown():
    await asyncio.sleep(350 * 60)
    print("[!] 5 saat 50 dk doldu, veri kaydediliyor ve kapaniliyor...")
    save_json(DATA_FILE, data)
    await bot.close()


if __name__ == "__main__":
    bot.run(TOKEN)
