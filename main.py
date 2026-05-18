import os
import json
import re
import asyncio
import random
from datetime import datetime, timezone, timedelta
from typing import Optional

import discord
from discord.ext import commands, tasks
from discord.ui import View, button, select, Button, Select
from discord import ButtonStyle, PermissionOverwrite
from dotenv import load_dotenv

# ==================== TOKEN ====================
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN") or os.getenv("TOKEN")
if not TOKEN:
    print("❌ Error: No se encontró DISCORD_TOKEN o TOKEN en el archivo .env")
    exit(1)

PREFIX = "!"
SERVER_NAME = "PANEL ᶻ̷ ᴴ"
CLEAN_CHANNELS_ON_SETUP = False

# ==================== ARCHIVOS DE DATOS ====================
WARN_FILE = "warns.json"
ECONOMY_FILE = "economy.json"
LEVELS_FILE = "levels.json"

def load_json(file):
    if not os.path.exists(file):
        return {}
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

# ==================== ROLES ====================
ROLES_CONFIG = {
    "owner": {"name": "⛧ OWNER", "color": discord.Colour.dark_red(), "perms": discord.Permissions(administrator=True), "hoist": True},
    "admin": {"name": "✦ ADMIN", "color": discord.Colour.red(), "perms": discord.Permissions(administrator=True), "hoist": True},
    "mod": {"name": "⚡ MODERATOR", "color": discord.Colour.orange(), "perms": discord.Permissions(manage_messages=True, kick_members=True, ban_members=True), "hoist": True},
    "support": {"name": "⌁ SUPPORT", "color": discord.Colour.blue(), "perms": discord.Permissions(manage_messages=True, view_audit_log=True), "hoist": True},
    "vip": {"name": "✧ VIP", "color": discord.Colour.gold(), "perms": discord.Permissions(), "hoist": True},
    "member": {"name": "➤ MEMBER", "color": discord.Colour.light_grey(), "perms": discord.Permissions(), "hoist": False},
    "new": {"name": "✦ NEW", "color": discord.Colour.dark_grey(), "perms": discord.Permissions(), "hoist": False},
    "muted": {"name": "🤐 MUTED", "color": discord.Colour.dark_grey(), "perms": discord.Permissions(send_messages=False, add_reactions=False, speak=False), "hoist": False}
}

# ==================== CATEGORÍAS Y CANALES ====================
CATEGORIES = {
    "info": {"name": "✦・INFORMACIÓN", "channels": ["welcome", "rules", "announcements", "status", "suggestions"]},
    "community": {"name": "⌁・COMUNIDAD", "channels": ["chat", "media", "memes", "voice-chat", "music-request", "level-up", "colaboraciones"]},
    "support": {"name": "✉・SOPORTE", "channels": ["tickets", "support-archive"]},
    "staff": {"name": "⛧・STAFF", "channels": ["staff-chat", "mod-notes", "mod-panel"]},
    "logs": {"name": "📜・LOGS", "channels": ["audit-logs", "member-logs", "message-logs", "mod-logs"]}
}

CHANNEL_NAMES = {
    "welcome": "✦・bienvenida",
    "rules": "✦・reglas",
    "announcements": "✦・anuncios",
    "status": "✦・estado",
    "suggestions": "✦・sugerencias",
    "chat": "⌁・chat-general",
    "media": "⌁・media",
    "memes": "⌁・memes",
    "voice-chat": "🎤・chat-voz",
    "music-request": "🎵・solicitar-musica",
    "level-up": "📈・subir-nivel",
    "colaboraciones": "🤝・colaboraciones",
    "tickets": "✉・tickets",
    "support-archive": "📦・soporte-archivado",
    "staff-chat": "⛧・staff-chat",
    "mod-notes": "📝・notas-mod",
    "mod-panel": "🛡️・mod-panel",
    "audit-logs": "📜・auditoria",
    "member-logs": "👥・logs-miembros",
    "message-logs": "💬・logs-mensajes",
    "mod-logs": "⚠️・mod-logs"
}

# ==================== BOT ====================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents)
bot.remove_command('help')  # 🔥 Elimina el comando help por defecto

# Datos en memoria
user_messages = {}
economy = load_json(ECONOMY_FILE)
levels = load_json(LEVELS_FILE)

# ==================== FUNCIONES AUXILIARES ====================
def make_embed(title: str, description: str, color: discord.Color, *,
               footer: str = None, thumbnail: str = None, image: str = None, fields: list = None) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color, timestamp=datetime.now(timezone.utc))
    if footer:
        embed.set_footer(text=footer, icon_url=bot.user.avatar.url if bot.user else None)
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    if image:
        embed.set_image(url=image)
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
    return embed

async def find_or_create_role(guild: discord.Guild, key: str):
    cfg = ROLES_CONFIG[key]
    role = discord.utils.get(guild.roles, name=cfg["name"])
    if role:
        return role
    return await guild.create_role(
        name=cfg["name"],
        colour=cfg["color"],
        permissions=cfg["perms"],
        hoist=cfg.get("hoist", False),
        mentionable=False
    )

async def find_or_create_category(guild: discord.Guild, key: str):
    cfg = CATEGORIES[key]
    cat = discord.utils.get(guild.categories, name=cfg["name"])
    if cat:
        return cat
    return await guild.create_category(cfg["name"])

def sanitize(text: str) -> str:
    text = text.lower().strip().replace(" ", "-")
    return re.sub(r"[^a-z0-9\-_]", "", text)[:90]

async def safe_send(channel: discord.TextChannel, content: str = None, embed: discord.Embed = None, view: View = None):
    try:
        await channel.send(content=content, embed=embed, view=view)
    except:
        pass

async def log_mod_action(guild: discord.Guild, action: str, target: discord.Member, moderator: discord.Member, reason: str = None):
    log_channel = discord.utils.get(guild.text_channels, name=CHANNEL_NAMES["mod-logs"])
    if not log_channel:
        return
    embed = make_embed(f"🛡️ {action}", f"**Usuario:** {target.mention} (`{target.id}`)\n**Moderador:** {moderator.mention}\n**Razón:** {reason or 'No especificada'}", discord.Color.orange(), thumbnail=target.avatar.url if target.avatar else None, footer=f"ID: {target.id}")
    await log_channel.send(embed=embed)

# ==================== SISTEMA DE ECONOMÍA ====================
def get_balance(user_id: int):
    return economy.get(str(user_id), 0)

def add_coins(user_id: int, amount: int):
    uid = str(user_id)
    economy[uid] = economy.get(uid, 0) + amount
    save_json(ECONOMY_FILE, economy)

def remove_coins(user_id: int, amount: int):
    uid = str(user_id)
    if economy.get(uid, 0) >= amount:
        economy[uid] -= amount
        save_json(ECONOMY_FILE, economy)
        return True
    return False

# ==================== VISTAS PERSISTENTES ====================
class CloseTicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @button(label="🔒 Cerrar ticket", style=ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("🔒 Cerrando ticket...", ephemeral=True)
        await interaction.channel.delete()

class TicketPanelView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @button(label="🎫 Abrir ticket", style=ButtonStyle.green, custom_id="create_ticket")
    async def create_ticket(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message("Error: servidor no encontrado.", ephemeral=True)
        support_cat = await find_or_create_category(guild, "support")
        ticket_name = f"ticket-{sanitize(interaction.user.name)}"
        if discord.utils.get(guild.text_channels, name=ticket_name):
            return await interaction.response.send_message("Ya tienes un ticket abierto.", ephemeral=True)
        overwrites = {
            guild.default_role: PermissionOverwrite(view_channel=False),
            interaction.user: PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True),
            guild.me: PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_channels=True)
        }
        for role_key in ["owner", "admin", "mod", "support"]:
            role = await find_or_create_role(guild, role_key)
            overwrites[role] = PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        channel = await guild.create_text_channel(ticket_name, category=support_cat, overwrites=overwrites)
        embed = make_embed("✉・TICKET ABIERTO", "```fix\nSoporte privado - Explica tu consulta claramente.\n```\n┌ El equipo responderá aquí.\n└ Usa el botón de abajo al terminar.", discord.Color.blue(), footer="Sistema de tickets", thumbnail=guild.icon.url if guild.icon else None)
        await channel.send(content=interaction.user.mention, embed=embed, view=CloseTicketView())
        await interaction.response.send_message(f"✅ Ticket creado: {channel.mention}", ephemeral=True)

class RoleSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="📢 Notificaciones", value="notif", emoji="🔔"),
            discord.SelectOption(label="🎮 Gamer", value="gamer", emoji="🎮"),
            discord.SelectOption(label="🎨 Creador", value="creator", emoji="🎨")
        ]
        super().__init__(placeholder="Elige tus roles", min_values=0, max_values=len(options), options=options, custom_id="role_select")
    
    async def callback(self, interaction: discord.Interaction):
        roles_map = {"notif": "📢 Notificaciones", "gamer": "🎮 Gamer", "creator": "🎨 Creador"}
        added = []
        removed = []
        for val in self.values:
            role_name = roles_map.get(val)
            if role_name:
                role = discord.utils.get(interaction.guild.roles, name=role_name)
                if role and role not in interaction.user.roles:
                    await interaction.user.add_roles(role)
                    added.append(role_name)
        for opt in self.options:
            if opt.value not in self.values:
                role_name = roles_map.get(opt.value)
                if role_name:
                    role = discord.utils.get(interaction.guild.roles, name=role_name)
                    if role and role in interaction.user.roles:
                        await interaction.user.remove_roles(role)
                        removed.append(role_name)
        msg = ""
        if added: msg += f"✅ Roles añadidos: {', '.join(added)}\n"
        if removed: msg += f"❌ Roles eliminados: {', '.join(removed)}"
        if not msg: msg = "No se realizaron cambios."
        await interaction.response.send_message(msg, ephemeral=True)

class RoleSelectView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(RoleSelect())

class ModPanelView(View):
    def __init__(self):
        super().__init__(timeout=120)
    
    @select(placeholder="🔧 Acción de moderación...", options=[
        discord.SelectOption(label="🔨 Warn", value="warn", emoji="⚠️"),
        discord.SelectOption(label="🤐 Mute (10m)", value="mute", emoji="🔇"),
        discord.SelectOption(label="🔊 Unmute", value="unmute", emoji="🔊"),
        discord.SelectOption(label="👢 Kick", value="kick", emoji="👢"),
        discord.SelectOption(label="🔨 Ban", value="ban", emoji="🔨"),
    ], custom_id="mod_select")
    async def mod_select(self, interaction: discord.Interaction, select: Select):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("No tienes permisos de moderación.", ephemeral=True)
        await interaction.response.send_message("Menciona al usuario objetivo:", ephemeral=True)
        def check(m): return m.author == interaction.user and m.channel == interaction.channel and m.mentions
        try:
            msg = await bot.wait_for("message", timeout=30.0, check=check)
            target = msg.mentions[0]
        except asyncio.TimeoutError:
            return await interaction.followup.send("Tiempo agotado.", ephemeral=True)
        await interaction.followup.send("Razón (opcional, escribe 'skip' para omitir):", ephemeral=True)
        def reason_check(m): return m.author == interaction.user and m.channel == interaction.channel
        try:
            msg2 = await bot.wait_for("message", timeout=30.0, check=reason_check)
            reason = msg2.content if msg2.content.lower() != "skip" else "No especificada"
        except:
            reason = "No especificada"
        value = select.values[0]
        if value == "warn": await self._warn(interaction, target, reason)
        elif value == "mute": await self._mute(interaction, target, reason)
        elif value == "unmute": await self._unmute(interaction, target)
        elif value == "kick": await self._kick(interaction, target, reason)
        elif value == "ban": await self._ban(interaction, target, reason)
    
    async def _warn(self, interaction, target, reason):
        warns = load_json(WARN_FILE)
        uid = str(target.id)
        if uid not in warns: warns[uid] = []
        warns[uid].append({"reason": reason, "mod": str(interaction.user.id), "date": str(datetime.now(timezone.utc))})
        save_json(WARN_FILE, warns)
        await log_mod_action(interaction.guild, "WARN", target, interaction.user, reason)
        await interaction.followup.send(f"⚠️ {target.mention} advertido. Razón: {reason}", ephemeral=True)
        try: await target.send(f"⚠️ Advertencia en {interaction.guild.name}: {reason}")
        except: pass
    async def _mute(self, interaction, target, reason):
        muted_role = await find_or_create_role(interaction.guild, "muted")
        if muted_role in target.roles: return await interaction.followup.send("Ya muteado.", ephemeral=True)
        await target.add_roles(muted_role, reason=reason)
        await log_mod_action(interaction.guild, "MUTE", target, interaction.user, reason)
        await interaction.followup.send(f"🔇 {target.mention} muteado 10 min. Razón: {reason}", ephemeral=True)
        await asyncio.sleep(600)
        if muted_role in target.roles:
            await target.remove_roles(muted_role)
            await log_mod_action(interaction.guild, "UNMUTE (auto)", target, bot.user, "Fin de mute")
    async def _unmute(self, interaction, target):
        muted_role = await find_or_create_role(interaction.guild, "muted")
        if muted_role not in target.roles: return await interaction.followup.send("No muteado.", ephemeral=True)
        await target.remove_roles(muted_role)
        await log_mod_action(interaction.guild, "UNMUTE", target, interaction.user)
        await interaction.followup.send(f"🔊 {target.mention} desmuteado.", ephemeral=True)
    async def _kick(self, interaction, target, reason):
        await target.kick(reason=reason)
        await log_mod_action(interaction.guild, "KICK", target, interaction.user, reason)
        await interaction.followup.send(f"👢 {target.mention} expulsado.", ephemeral=True)
    async def _ban(self, interaction, target, reason):
        await target.ban(reason=reason)
        await log_mod_action(interaction.guild, "BAN", target, interaction.user, reason)
        await interaction.followup.send(f"🔨 {target.mention} baneado.", ephemeral=True)

# ==================== COMANDOS DE MODERACIÓN ====================
@bot.command()
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason="No especificada"):
    warns = load_json(WARN_FILE)
    uid = str(member.id)
    if uid not in warns: warns[uid] = []
    warns[uid].append({"reason": reason, "mod": str(ctx.author.id), "date": str(datetime.now(timezone.utc))})
    save_json(WARN_FILE, warns)
    await log_mod_action(ctx.guild, "WARN", member, ctx.author, reason)
    await ctx.send(f"⚠️ {member.mention} advertido. Razón: {reason}")
    try: await member.send(f"⚠️ Advertencia en {ctx.guild.name}: {reason}")
    except: pass

@bot.command()
@commands.has_permissions(manage_messages=True)
async def warns(ctx, member: discord.Member = None):
    member = member or ctx.author
    warns = load_json(WARN_FILE)
    uid = str(member.id)
    if uid not in warns or not warns[uid]:
        return await ctx.send(f"{member.mention} no tiene advertencias.")
    embed = make_embed(f"⚠️ Advertencias de {member.display_name}", f"Total: {len(warns[uid])}", discord.Color.red(), thumbnail=member.avatar.url if member.avatar else None)
    for i, w in enumerate(warns[uid][:10], 1):
        embed.add_field(name=f"#{i}", value=f"**Razón:** {w['reason']}\n**Mod:** <@{w['mod']}>\n**Fecha:** {w['date'][:19]}", inline=False)
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def delwarn(ctx, member: discord.Member, index: int):
    warns = load_json(WARN_FILE)
    uid = str(member.id)
    if uid not in warns or len(warns[uid]) < index or index < 1:
        return await ctx.send("Índice inválido.")
    removed = warns[uid].pop(index-1)
    if not warns[uid]: del warns[uid]
    save_json(WARN_FILE, warns)
    await ctx.send(f"✅ Advertencia #{index} de {member.mention} eliminada.")
    await log_mod_action(ctx.guild, "DELWARN", member, ctx.author, f"Advertencia #{index} eliminada")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def mute(ctx, member: discord.Member, minutos: int = 10, *, reason="No especificada"):
    muted_role = await find_or_create_role(ctx.guild, "muted")
    if muted_role in member.roles: return await ctx.send("Ya muteado.")
    await member.add_roles(muted_role, reason=reason)
    await log_mod_action(ctx.guild, "MUTE", member, ctx.author, f"{minutos} min - {reason}")
    await ctx.send(f"🔇 {member.mention} muteado {minutos} min. Razón: {reason}")
    await asyncio.sleep(minutos*60)
    if muted_role in member.roles:
        await member.remove_roles(muted_role)
        await log_mod_action(ctx.guild, "UNMUTE (auto)", member, bot.user, "Fin de mute")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def unmute(ctx, member: discord.Member):
    muted_role = await find_or_create_role(ctx.guild, "muted")
    if muted_role not in member.roles: return await ctx.send("No muteado.")
    await member.remove_roles(muted_role)
    await log_mod_action(ctx.guild, "UNMUTE", member, ctx.author)
    await ctx.send(f"🔊 {member.mention} desmuteado.")

@bot.command()
async def report(ctx, member: discord.Member, *, reason):
    log_ch = discord.utils.get(ctx.guild.text_channels, name=CHANNEL_NAMES["mod-logs"])
    if not log_ch: return await ctx.send("Canal de logs no encontrado.")
    embed = make_embed("📢 Reporte", f"**Reportado:** {member.mention}\n**Autor:** {ctx.author.mention}\n**Razón:** {reason}", discord.Color.red(), thumbnail=member.avatar.url if member.avatar else None)
    await log_ch.send(embed=embed)
    await ctx.send("✅ Reporte enviado.", delete_after=3)

@bot.command()
@commands.has_permissions(manage_channels=True)
async def slowmode(ctx, segundos: int):
    await ctx.channel.edit(slowmode_delay=segundos)
    await ctx.send(f"⏱️ Slowmode {segundos}s" if segundos else "⏱️ Slowmode desactivado.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def lock(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send(f"🔒 {channel.mention} bloqueado.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send(f"🔓 {channel.mention} desbloqueado.")

@bot.command()
async def clear(ctx, amount: int):
    if amount < 1: return await ctx.reply("Cantidad inválida.")
    await ctx.channel.purge(limit=amount+1)
    await ctx.send(f"🧹 {amount} mensajes eliminados.", delete_after=3)

# ==================== COMANDOS DE ECONOMÍA Y DIVERSIÓN ====================
@bot.command()
async def balance(ctx, member: discord.Member = None):
    member = member or ctx.author
    bal = get_balance(member.id)
    embed = make_embed(f"💰 Balance de {member.display_name}", f"**Monedas:** {bal} :coin:", discord.Color.gold(), thumbnail=member.avatar.url if member.avatar else None)
    await ctx.send(embed=embed)

@bot.command()
async def daily(ctx):
    now = datetime.now(timezone.utc)
    last = levels.get(str(ctx.author.id), {}).get("daily", 0)
    if now.timestamp() - last < 86400:
        return await ctx.send("Ya reclamaste tu daily. Vuelve mañana.", delete_after=5)
    add_coins(ctx.author.id, 100)
    if "daily" not in levels.get(str(ctx.author.id), {}):
        if str(ctx.author.id) not in levels: levels[str(ctx.author.id)] = {}
    levels[str(ctx.author.id)]["daily"] = now.timestamp()
    save_json(LEVELS_FILE, levels)
    await ctx.send("✅ Has recibido 100 monedas diarias.")

@bot.command()
async def work(ctx):
    earnings = random.randint(20, 80)
    add_coins(ctx.author.id, earnings)
    await ctx.send(f"💼 Trabajaste y ganaste **{earnings}** monedas.")

@bot.command()
async def rob(ctx, member: discord.Member):
    if member.id == ctx.author.id: return await ctx.send("No te puedes robar a ti mismo.")
    if random.random() < 0.4:
        amount = min(get_balance(member.id), random.randint(10, 200))
        if amount == 0: return await ctx.send("Ese usuario no tiene monedas.")
        if remove_coins(member.id, amount):
            add_coins(ctx.author.id, amount)
            await ctx.send(f"🦹‍♂️ Robaste **{amount}** monedas de {member.mention}.")
        else:
            await ctx.send("No se pudo robar.")
    else:
        penalty = random.randint(20, 100)
        remove_coins(ctx.author.id, penalty)
        await ctx.send(f"❌ Fallaste! Perdiste **{penalty}** monedas.")

@bot.command()
@commands.has_permissions(administrator=True)
async def give(ctx, member: discord.Member, amount: int):
    add_coins(member.id, amount)
    await ctx.send(f"✅ {amount} monedas entregadas a {member.mention}.")

# ==================== COMANDOS DE NIVELES ====================
@bot.command()
async def rank(ctx, member: discord.Member = None):
    member = member or ctx.author
    xp = levels.get(str(member.id), {}).get("xp", 0)
    level = int(xp ** 0.5 // 10)
    embed = make_embed(f"📊 Nivel de {member.display_name}", f"**XP:** {xp}\n**Nivel:** {level}", discord.Color.blue(), thumbnail=member.avatar.url if member.avatar else None)
    await ctx.send(embed=embed)

@bot.command()
async def leaderboard(ctx):
    sorted_users = sorted(levels.items(), key=lambda x: x[1].get("xp", 0), reverse=True)[:10]
    if not sorted_users: return await ctx.send("No hay datos de niveles.")
    desc = ""
    for i, (uid, data) in enumerate(sorted_users, 1):
        user = ctx.guild.get_member(int(uid))
        name = user.display_name if user else uid
        xp = data.get("xp", 0)
        level = int(xp ** 0.5 // 10)
        desc += f"{i}. {name} - Nivel {level} ({xp} XP)\n"
    embed = make_embed("🏆 Clasificación de niveles", desc, discord.Color.gold(), thumbnail=ctx.guild.icon.url if ctx.guild.icon else None)
    await ctx.send(embed=embed)

# ==================== COMANDOS DE ENCUESTAS Y SORTEOS ====================
@bot.command()
async def poll(ctx, *, pregunta: str):
    embed = make_embed("📊 Encuesta", pregunta, discord.Color.blue(), footer=f"Creada por {ctx.author.display_name}")
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    await msg.add_reaction("🤷")

@bot.command()
@commands.has_permissions(administrator=True)
async def giveaway(ctx, duration: int, *, prize: str):
    embed = make_embed("🎉 SORTEO", f"**Premio:** {prize}\n**Duración:** {duration} minutos\n**Participa reaccionando con 🎉", discord.Color.gold())
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("🎉")
    await asyncio.sleep(duration*60)
    msg = await ctx.channel.fetch_message(msg.id)
    reaction = discord.utils.get(msg.reactions, emoji="🎉")
    if reaction:
        users = [user async for user in reaction.users() if not user.bot]
        if users:
            winner = random.choice(users)
            await ctx.send(f"🎁 **Ganador del sorteo '{prize}':** {winner.mention}")
        else:
            await ctx.send("No hubo participantes.")
    else:
        await ctx.send("No hubo reacciones.")

# ==================== COMANDOS DE INFORMACIÓN ====================
@bot.command()
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = make_embed(f"🖼️ Avatar de {member.display_name}", "", discord.Color.blue(), image=member.avatar.url if member.avatar else member.default_avatar.url)
    await ctx.send(embed=embed)

@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = make_embed(f"ℹ️ Información de {member.display_name}",
        f"**ID:** {member.id}\n**Cuenta creada:** {member.created_at.strftime('%d/%m/%Y')}\n**Entró:** {member.joined_at.strftime('%d/%m/%Y')}\n**Roles:** {len(member.roles)-1}",
        member.color, thumbnail=member.avatar.url if member.avatar else member.default_avatar.url)
    await ctx.send(embed=embed)

@bot.command()
async def serverinfo(ctx):
    guild = ctx.guild
    embed = make_embed(f"📊 {guild.name}", f"**Dueño:** {guild.owner.mention}\n**Miembros:** {guild.member_count}\n**Canales:** {len(guild.channels)}\n**Roles:** {len(guild.roles)}", discord.Color.blurple(), thumbnail=guild.icon.url if guild.icon else None)
    await ctx.send(embed=embed)

@bot.command()
async def say(ctx, *, mensaje):
    await ctx.message.delete()
    await ctx.send(mensaje)

@bot.command()
async def embed(ctx, *, text):
    embed = make_embed("Mensaje", text, discord.Color.teal())
    await ctx.send(embed=embed)

# ==================== COMANDOS DE VOZ ====================
@bot.command()
@commands.has_permissions(manage_channels=True)
async def voicekick(ctx, member: discord.Member):
    if member.voice and member.voice.channel:
        await member.move_to(None)
        await ctx.send(f"👢 {member.mention} expulsado del canal de voz.")
    else:
        await ctx.send("El usuario no está en un canal de voz.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def voicemove(ctx, member: discord.Member, channel: discord.VoiceChannel):
    if member.voice:
        await member.move_to(channel)
        await ctx.send(f"🔊 {member.mention} movido a {channel.mention}.")
    else:
        await ctx.send("El usuario no está en un canal de voz.")

# ==================== COMANDOS DE SETUP ====================
@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx, clean: Optional[str] = None):
    guild = ctx.guild
    if not guild: return
    await ctx.send("⚙️ Construyendo estructura...")
    if clean == "--clean" or CLEAN_CHANNELS_ON_SETUP:
        for ch in guild.channels:
            try:
                await ch.delete()
            except:
                pass
        await ctx.send("🗑️ Canales antiguos eliminados.")
    roles = {}
    for key in ROLES_CONFIG:
        roles[key] = await find_or_create_role(guild, key)
    for cat_key, cat_conf in CATEGORIES.items():
        category = await find_or_create_category(guild, cat_key)
        if cat_key in ("support", "staff", "logs"):
            await category.set_permissions(guild.default_role, view_channel=False)
            if cat_key == "support":
                await category.set_permissions(roles["support"], view_channel=True, send_messages=True)
            elif cat_key == "staff":
                for staff_role in ["owner", "admin", "mod"]:
                    await category.set_permissions(roles[staff_role], view_channel=True, send_messages=True)
            elif cat_key == "logs":
                for staff_role in ["owner", "admin", "mod"]:
                    await category.set_permissions(roles[staff_role], view_channel=True, send_messages=False)
        else:
            await category.set_permissions(guild.default_role, view_channel=True)
        for ch_key in cat_conf["channels"]:
            ch_name = CHANNEL_NAMES.get(ch_key, ch_key)
            if not discord.utils.get(guild.text_channels, name=ch_name):
                try:
                    await guild.create_text_channel(ch_name, category=category)
                except: pass
    guild_icon = guild.icon.url if guild.icon else "https://cdn-icons-png.flaticon.com/512/4712/4712109.png"
    banner_default = "https://i.imgur.com/8Km9tLL.png"
    welcome_ch = discord.utils.get(guild.text_channels, name=CHANNEL_NAMES["welcome"])
    if welcome_ch:
        embed = make_embed(f"✨ BIENVENIDO A {SERVER_NAME}", "```fix\nComunidad exclusiva · Soporte profesional\n```\n┌ Lee las reglas\n├ Usa !sugerir para ideas\n└ Abre un ticket para ayuda", discord.Color.teal(), footer="¡Gracias por unirte!", thumbnail=guild_icon, image=banner_default, fields=[("📌 Estado", "🟢 Activo", True), ("🎫 Soporte", "Privado 24/7", True), ("👥 Miembros", str(guild.member_count), True)])
        await welcome_ch.send(embed=embed)
    rules_ch = discord.utils.get(guild.text_channels, name=CHANNEL_NAMES["rules"])
    if rules_ch:
        embed = make_embed("📜 REGLAS", "```diff\n+ Respeto\n+ Sin spam\n+ Seguir staff\n```", discord.Color.dark_red(), thumbnail=guild_icon)
        await rules_ch.send(embed=embed)
    tickets_ch = discord.utils.get(guild.text_channels, name=CHANNEL_NAMES["tickets"])
    if tickets_ch:
        embed = make_embed("🎟️ SOPORTE", "```fix\nAbre un ticket para ayuda personalizada\n```", discord.Color.blurple(), thumbnail=guild_icon)
        await tickets_ch.send(embed=embed, view=TicketPanelView())
    suggestions_ch = discord.utils.get(guild.text_channels, name=CHANNEL_NAMES["suggestions"])
    if suggestions_ch:
        embed = make_embed("💡 SUGERENCIAS", "Usa `!sugerir <idea>` para compartir.", discord.Color.purple(), thumbnail=guild_icon)
        await suggestions_ch.send(embed=embed)
    mod_panel_ch = discord.utils.get(guild.text_channels, name=CHANNEL_NAMES["mod-panel"])
    if mod_panel_ch:
        embed = make_embed("🛡️ PANEL MODERACIÓN", "Selecciona acción del menú.", discord.Color.dark_red(), thumbnail=guild_icon)
        await mod_panel_ch.send(embed=embed, view=ModPanelView())
    await ctx.send("✅ Estructura completada.")

@bot.command()
async def sugerir(ctx, *, idea):
    suggestions_ch = discord.utils.get(ctx.guild.text_channels, name=CHANNEL_NAMES["suggestions"])
    if not suggestions_ch: return await ctx.reply("Canal de sugerencias no encontrado. Ejecuta !setup.")
    embed = make_embed(f"💡 Sugerencia de {ctx.author.display_name}", idea, discord.Color.blue(), footer=f"ID: {ctx.author.id}", thumbnail=ctx.author.avatar.url if ctx.author.avatar else None)
    msg = await suggestions_ch.send(embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    await ctx.reply("✅ Sugerencia enviada.", delete_after=3)

@bot.command()
@commands.has_permissions(administrator=True)
async def roles_panel(ctx):
    view = RoleSelectView()
    embed = make_embed("🎭 SELECCIÓN DE ROLES", "Elige tus roles del menú.", discord.Color.gold(), thumbnail=ctx.guild.icon.url if ctx.guild.icon else None)
    await ctx.send(embed=embed, view=view)

# ==================== SISTEMA DE NIVELES POR MENSAJES ====================
@bot.event
async def on_message(message):
    if message.author.bot: return
    uid = str(message.author.id)
    if uid not in levels:
        levels[uid] = {"xp": 0}
    levels[uid]["xp"] = levels[uid].get("xp", 0) + random.randint(5, 15)
    xp = levels[uid]["xp"]
    new_level = int(xp ** 0.5 // 10)
    old_level = int((xp - 15) ** 0.5 // 10) if xp >= 15 else 0
    if new_level > old_level and new_level > 0:
        await message.channel.send(f"🎉 {message.author.mention} ha subido al nivel **{new_level}**!")
    save_json(LEVELS_FILE, levels)
    await bot.process_commands(message)

# ==================== BIENVENIDA MEJORADA ====================
@bot.event
async def on_member_join(member):
    new_role = await find_or_create_role(member.guild, "new")
    await member.add_roles(new_role)
    welcome_ch = discord.utils.get(member.guild.text_channels, name=CHANNEL_NAMES["welcome"])
    if welcome_ch:
        banner = member.guild.banner.url if member.guild.banner else "https://i.imgur.com/8Km9tLL.png"
        embed = make_embed(f"✨ BIENVENIDO {member.display_name} ✨", f"```fix\nTe damos la bienvenida a {SERVER_NAME}\n```\n📌 Lee las reglas\n💬 Preséntate en el chat\n🎫 Abre un ticket si necesitas ayuda\n\n📊 Ahora somos **{member.guild.member_count}** miembros.", discord.Color.green(), thumbnail=member.avatar.url if member.avatar else member.default_avatar.url, image=banner, footer="¡Disfruta la comunidad!")
        await welcome_ch.send(content=member.mention, embed=embed)
    try:
        await member.send(f"👋 ¡Bienvenido a {SERVER_NAME}! Usa `!daily`, `!work`, `!balance` para divertirte.")
    except: pass
    log_ch = discord.utils.get(member.guild.text_channels, name=CHANNEL_NAMES["member-logs"])
    if log_ch:
        embed = make_embed("📥 Miembro entró", f"{member.mention} se unió.\nCuenta creada: {member.created_at.strftime('%d/%m/%Y')}", discord.Color.green(), thumbnail=member.avatar.url if member.avatar else None)
        await log_ch.send(embed=embed)
    await asyncio.sleep(3600)
    member_role = await find_or_create_role(member.guild, "member")
    if member_role not in member.roles and new_role in member.roles:
        await member.remove_roles(new_role)
        await member.add_roles(member_role)
        if welcome_ch:
            await welcome_ch.send(f"🎉 {member.mention} ahora es miembro completo.")

@bot.event
async def on_member_remove(member):
    log_ch = discord.utils.get(member.guild.text_channels, name=CHANNEL_NAMES["member-logs"])
    if log_ch:
        embed = make_embed("📤 Miembro salió", f"{member.display_name} abandonó.", discord.Color.orange(), thumbnail=member.avatar.url if member.avatar else None)
        await log_ch.send(embed=embed)

# ==================== LOGS DE MENSAJES ====================
@bot.event
async def on_message_delete(message):
    if message.author.bot: return
    log_ch = discord.utils.get(message.guild.text_channels, name=CHANNEL_NAMES["message-logs"])
    if log_ch:
        embed = make_embed("🗑️ Mensaje eliminado", f"**Autor:** {message.author.mention}\n**Canal:** {message.channel.mention}\n**Contenido:** {message.content[:500]}", discord.Color.red())
        await log_ch.send(embed=embed)

@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.content == after.content: return
    log_ch = discord.utils.get(before.guild.text_channels, name=CHANNEL_NAMES["message-logs"])
    if log_ch:
        embed = make_embed("✏️ Mensaje editado", f"**Autor:** {before.author.mention}\n**Canal:** {before.channel.mention}\n**Antes:** {before.content[:500]}\n**Después:** {after.content[:500]}", discord.Color.gold())
        await log_ch.send(embed=embed)

@bot.event
async def on_member_update(before, after):
    if before.roles == after.roles: return
    log_ch = discord.utils.get(before.guild.text_channels, name=CHANNEL_NAMES["mod-logs"])
    if log_ch:
        added = [r.name for r in after.roles if r not in before.roles]
        removed = [r.name for r in before.roles if r not in after.roles]
        if added:
            embed = make_embed("➕ Rol añadido", f"{before.mention} recibió: {', '.join(added)}", discord.Color.green())
            await log_ch.send(embed=embed)
        if removed:
            embed = make_embed("➖ Rol eliminado", f"{before.mention} perdió: {', '.join(removed)}", discord.Color.red())
            await log_ch.send(embed=embed)

# ==================== ON_READY ====================
@bot.event
async def on_ready():
    print(f"✅ Conectado como {bot.user}")
    bot.add_view(TicketPanelView())
    bot.add_view(CloseTicketView())
    bot.add_view(RoleSelectView())
    bot.add_view(ModPanelView())
    await bot.change_presence(activity=discord.Game(name=f"{PREFIX}help | {SERVER_NAME}"))

# ==================== COMANDO HELP PERSONALIZADO ====================
@bot.command()
async def help(ctx):
    embed = make_embed("📚 COMANDOS DISPONIBLES", 
        "**Moderación**\n`!warn`, `!warns`, `!delwarn`, `!mute`, `!unmute`, `!clear`, `!slowmode`, `!lock`, `!unlock`, `!report`, `!voicekick`, `!voicemove`\n\n"
        "**Economía y diversión**\n`!balance`, `!daily`, `!work`, `!rob`, `!give`\n\n"
        "**Niveles**\n`!rank`, `!leaderboard`\n\n"
        "**Utilidades**\n`!avatar`, `!userinfo`, `!serverinfo`, `!say`, `!embed`, `!poll`, `!sugerir`\n\n"
        "**Sorteos**\n`!giveaway` (admin)\n\n"
        "**Administración**\n`!setup`, `!roles_panel`", 
        discord.Color.blurple(), thumbnail=ctx.guild.icon.url if ctx.guild.icon else None, footer=f"Usa {PREFIX}comando para más información")
    await ctx.send(embed=embed)

# ==================== EJECUCIÓN ====================
if __name__ == "__main__":
    bot.run(TOKEN)