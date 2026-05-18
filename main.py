# main.py - Versión Profesional Completamente Corregida
import os
import json
import re
import asyncio
import random
import logging
from datetime import datetime, timezone
from typing import Optional, List, Any
from pathlib import Path

import discord
from discord.ext import commands
from discord.ui import View, button, select, Button, Select, Modal, TextInput
from discord import ButtonStyle, PermissionOverwrite, Interaction, Embed, Color
from dotenv import load_dotenv

# ==================== CONFIGURACIÓN DE LOGGING ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('DiscordBot')

# ==================== CONFIGURACIÓN ====================
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN") or os.getenv("TOKEN")
if not TOKEN:
    logger.critical("No se encontró DISCORD_TOKEN en el archivo .env")
    exit(1)

class BotConfig:
    PREFIX = "!"
    SERVER_NAME = "PANEL ᶻ̷ ᴴ"
    CLEAN_CHANNELS_ON_SETUP = False
    MAX_WARNINGS_BEFORE_MUTE = 3
    MUTE_DURATION_MINUTES = 10

config = BotConfig()

# ==================== DATA MANAGER ====================
class DataManager:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
    def load(self, filename: str, default: Any = None) -> Any:
        path = self.data_dir / filename
        if not path.exists():
            return default or {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return default or {}
    
    def save(self, filename: str, data: Any) -> bool:
        path = self.data_dir / filename
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            return True
        except:
            return False

data_manager = DataManager()

# ==================== CONFIGURACIÓN DE ROLES ====================
ROLES_CONFIG = {
    "owner": {"name": "⛧ OWNER", "color": discord.Color.dark_red(), "perms": discord.Permissions(administrator=True), "hoist": True},
    "admin": {"name": "✦ ADMIN", "color": discord.Color.red(), "perms": discord.Permissions(administrator=True), "hoist": True},
    "mod": {"name": "⚡ MODERATOR", "color": discord.Color.orange(), "perms": discord.Permissions(manage_messages=True, kick_members=True, ban_members=True), "hoist": True},
    "support": {"name": "⌁ SUPPORT", "color": discord.Color.blue(), "perms": discord.Permissions(manage_messages=True, view_audit_log=True), "hoist": True},
    "vip": {"name": "✧ VIP", "color": discord.Color.gold(), "perms": discord.Permissions(), "hoist": True},
    "member": {"name": "➤ MEMBER", "color": discord.Color.light_grey(), "perms": discord.Permissions(), "hoist": False},
    "new": {"name": "✦ NEW", "color": discord.Color.dark_grey(), "perms": discord.Permissions(), "hoist": False},
    "muted": {"name": "🤐 MUTED", "color": discord.Color.dark_grey(), "perms": discord.Permissions(send_messages=False, add_reactions=False, speak=False), "hoist": False}
}

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

# ==================== CLASE PRINCIPAL DEL BOT ====================
class ModerationBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix=config.PREFIX, intents=intents)
        # 🔥 IMPORTANTE: Eliminar comando help por defecto ANTES de definir cualquier comando
        self.remove_command('help')
        self.config = config
        self.start_time = datetime.now(timezone.utc)
        
    async def setup_hook(self):
        self.add_view(TicketPanelView())
        self.add_view(CloseTicketView())
        self.add_view(RoleSelectView())
        self.add_view(ModPanelView())
        logger.info("Vistas persistentes registradas")
        
    async def on_ready(self):
        logger.info(f"✅ Bot conectado como {self.user} (ID: {self.user.id})")
        await self.change_presence(activity=discord.Game(name=f"{self.config.PREFIX}help | {self.config.SERVER_NAME}"))
        
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ No tienes permisos para usar este comando.", delete_after=5)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Falta un argumento. Usa `{self.config.PREFIX}help {ctx.command.name}`")
        else:
            logger.error(f"Error: {error}")
            await ctx.send("❌ Ocurrió un error inesperado.")
            
    async def get_log_channel(self, guild, channel_key):
        channel_name = CHANNEL_NAMES.get(channel_key)
        if not channel_name:
            return None
        return discord.utils.get(guild.text_channels, name=channel_name)

# Crear instancia del bot
bot = ModerationBot()

# ==================== UTILIDADES ====================
def create_embed(title, description, color, footer=None, thumbnail=None, image=None, fields=None):
    embed = Embed(title=title, description=description, color=color, timestamp=datetime.now(timezone.utc))
    if footer:
        embed.set_footer(text=footer)
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    if image:
        embed.set_image(url=image)
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
    return embed

def sanitize_name(text):
    text = text.lower().strip().replace(" ", "-")
    return re.sub(r"[^a-z0-9\-_]", "", text)[:90]

async def find_or_create_role(guild, key):
    cfg = ROLES_CONFIG[key]
    role = discord.utils.get(guild.roles, name=cfg["name"])
    if role:
        return role
    return await guild.create_role(
        name=cfg["name"],
        colour=cfg["color"],
        permissions=cfg["perms"],
        hoist=cfg.get("hoist", False)
    )

async def find_or_create_category(guild, key):
    cfg = CATEGORIES[key]
    cat = discord.utils.get(guild.categories, name=cfg["name"])
    if cat:
        return cat
    return await guild.create_category(cfg["name"])

async def log_mod_action(guild, action, target, moderator, reason=None):
    log_channel = await bot.get_log_channel(guild, "mod-logs")
    if not log_channel:
        return
    embed = create_embed(
        f"🛡️ {action}",
        f"**Usuario:** {target.mention} (`{target.id}`)\n**Moderador:** {moderator.mention}\n**Razón:** {reason or 'No especificada'}",
        discord.Color.orange(),
        thumbnail=target.avatar.url if target.avatar else None
    )
    await log_channel.send(embed=embed)

# ==================== SISTEMA DE PAGINACIÓN ====================
class PaginatorView(View):
    def __init__(self, pages, timeout=60):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.current_page = 0
        
    @button(emoji="◀️", style=ButtonStyle.secondary)
    async def previous(self, interaction: Interaction, button: Button):
        if self.current_page > 0:
            self.current_page -= 1
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
            
    @button(emoji="▶️", style=ButtonStyle.secondary)
    async def next(self, interaction: Interaction, button: Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
            
    @button(emoji="❌", style=ButtonStyle.red)
    async def stop(self, interaction: Interaction, button: Button):
        await interaction.message.delete()
        self.stop()

# ==================== SISTEMA DE TICKETS ====================
class CloseTicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @button(label="🔒 Cerrar Ticket", style=ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, interaction: Interaction, button: Button):
        await interaction.response.send_message("🔒 Cerrando ticket...", ephemeral=True)
        await interaction.channel.delete()

class TicketPanelView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @button(label="🎫 Abrir Ticket", style=ButtonStyle.green, custom_id="create_ticket")
    async def create_ticket(self, interaction: Interaction, button: Button):
        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message("Error", ephemeral=True)
        
        existing = discord.utils.get(guild.text_channels, name=f"ticket-{sanitize_name(interaction.user.name)}")
        if existing:
            return await interaction.response.send_message("Ya tienes un ticket abierto.", ephemeral=True)
        
        support_cat = await find_or_create_category(guild, "support")
        
        overwrites = {
            guild.default_role: PermissionOverwrite(view_channel=False),
            interaction.user: PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        }
        
        for role_key in ["owner", "admin", "mod", "support"]:
            role = await find_or_create_role(guild, role_key)
            overwrites[role] = PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        
        ticket_name = f"ticket-{sanitize_name(interaction.user.name)}"
        channel = await guild.create_text_channel(ticket_name, category=support_cat, overwrites=overwrites)
        
        embed = create_embed("✉・TICKET ABIERTO", "Explica tu consulta. Usa el botón para cerrar.", discord.Color.blue())
        await channel.send(content=interaction.user.mention, embed=embed, view=CloseTicketView())
        await interaction.response.send_message(f"✅ Ticket creado: {channel.mention}", ephemeral=True)

# ==================== SISTEMA DE ROLES ====================
class RoleSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="📢 Notificaciones", value="notif", emoji="🔔"),
            discord.SelectOption(label="🎮 Gamer", value="gamer", emoji="🎮"),
            discord.SelectOption(label="🎨 Creador", value="creator", emoji="🎨")
        ]
        super().__init__(placeholder="Selecciona tus roles", min_values=0, max_values=len(options), options=options, custom_id="role_select")
    
    async def callback(self, interaction: Interaction):
        roles_map = {"notif": "📢 Notificaciones", "gamer": "🎮 Gamer", "creator": "🎨 Creador"}
        added, removed = [], []
        
        for value in self.values:
            role_name = roles_map.get(value)
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

# ==================== PANEL DE MODERACIÓN ====================
class ModPanelView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @select(placeholder="🔧 Acción de moderación...", options=[
        discord.SelectOption(label="⚠️ Warn", value="warn", emoji="⚠️"),
        discord.SelectOption(label="🔇 Mute (10m)", value="mute", emoji="🔇"),
        discord.SelectOption(label="🔊 Unmute", value="unmute", emoji="🔊"),
        discord.SelectOption(label="👢 Kick", value="kick", emoji="👢"),
        discord.SelectOption(label="🔨 Ban", value="ban", emoji="🔨"),
    ], custom_id="mod_select")
    async def mod_select(self, interaction: Interaction, select: Select):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("No tienes permisos.", ephemeral=True)
        
        await interaction.response.send_message("Menciona al usuario:", ephemeral=True)
        def check(m): return m.author == interaction.user and m.channel == interaction.channel and m.mentions
        try:
            msg = await bot.wait_for("message", timeout=30.0, check=check)
            target = msg.mentions[0]
        except:
            return await interaction.followup.send("Tiempo agotado.", ephemeral=True)
        
        await interaction.followup.send("Razón (opcional, escribe 'skip'):", ephemeral=True)
        def reason_check(m): return m.author == interaction.user and m.channel == interaction.channel
        try:
            msg2 = await bot.wait_for("message", timeout=30.0, check=reason_check)
            reason = msg2.content if msg2.content.lower() != "skip" else "No especificada"
        except:
            reason = "No especificada"
        
        value = select.values[0]
        if value == "warn":
            await self._warn(interaction, target, reason)
        elif value == "mute":
            await self._mute(interaction, target, reason)
        elif value == "unmute":
            await self._unmute(interaction, target)
        elif value == "kick":
            await self._kick(interaction, target, reason)
        elif value == "ban":
            await self._ban(interaction, target, reason)
    
    async def _warn(self, interaction, target, reason):
        warns = data_manager.load("warns.json", {})
        uid = str(target.id)
        if uid not in warns: warns[uid] = []
        warns[uid].append({"reason": reason, "moderator_id": interaction.user.id, "timestamp": datetime.now(timezone.utc).isoformat()})
        data_manager.save("warns.json", warns)
        await log_mod_action(interaction.guild, "WARN", target, interaction.user, reason)
        await interaction.followup.send(f"⚠️ {target.mention} advertido.", ephemeral=True)
    
    async def _mute(self, interaction, target, reason):
        muted_role = await find_or_create_role(interaction.guild, "muted")
        if muted_role in target.roles:
            return await interaction.followup.send("Ya muteado.", ephemeral=True)
        await target.add_roles(muted_role, reason=reason)
        await log_mod_action(interaction.guild, "MUTE", target, interaction.user, reason)
        await interaction.followup.send(f"🔇 {target.mention} muteado 10 min.", ephemeral=True)
        await asyncio.sleep(600)
        if muted_role in target.roles:
            await target.remove_roles(muted_role)
    
    async def _unmute(self, interaction, target):
        muted_role = await find_or_create_role(interaction.guild, "muted")
        if muted_role not in target.roles:
            return await interaction.followup.send("No muteado.", ephemeral=True)
        await target.remove_roles(muted_role)
        await interaction.followup.send(f"🔊 {target.mention} desmuteado.", ephemeral=True)
    
    async def _kick(self, interaction, target, reason):
        await target.kick(reason=reason)
        await log_mod_action(interaction.guild, "KICK", target, interaction.user, reason)
        await interaction.followup.send(f"👢 {target.mention} expulsado.", ephemeral=True)
    
    async def _ban(self, interaction, target, reason):
        await target.ban(reason=reason)
        await log_mod_action(interaction.guild, "BAN", target, interaction.user, reason)
        await interaction.followup.send(f"🔨 {target.mention} baneado.", ephemeral=True)

# ==================== COMANDOS ====================
@bot.command()
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason="No especificada"):
    warns = data_manager.load("warns.json", {})
    uid = str(member.id)
    if uid not in warns: warns[uid] = []
    warns[uid].append({"reason": reason, "moderator_id": ctx.author.id, "timestamp": datetime.now(timezone.utc).isoformat()})
    data_manager.save("warns.json", warns)
    await log_mod_action(ctx.guild, "WARN", member, ctx.author, reason)
    await ctx.send(f"⚠️ {member.mention} advertido.")

@bot.command()
async def warns(ctx, member: discord.Member = None):
    member = member or ctx.author
    warns = data_manager.load("warns.json", {})
    uid = str(member.id)
    if uid not in warns or not warns[uid]:
        return await ctx.send(f"{member.mention} no tiene advertencias.")
    
    pages = []
    entries = warns[uid]
    for i, w in enumerate(entries[:10], 1):
        embed = create_embed(f"⚠️ Advertencias de {member.display_name}", f"Total: {len(entries)}", discord.Color.red())
        embed.add_field(name=f"#{i}", value=f"**Razón:** {w['reason']}\n**Mod:** <@{w['moderator_id']}>\n**Fecha:** {w['timestamp'][:19]}", inline=False)
        pages.append(embed)
    
    view = PaginatorView(pages)
    await ctx.send(embed=pages[0], view=view)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def delwarn(ctx, member: discord.Member, index: int):
    warns = data_manager.load("warns.json", {})
    uid = str(member.id)
    if uid not in warns or index < 1 or index > len(warns[uid]):
        return await ctx.send("Índice inválido.")
    warns[uid].pop(index-1)
    if not warns[uid]: del warns[uid]
    data_manager.save("warns.json", warns)
    await ctx.send(f"✅ Advertencia #{index} eliminada.")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def mute(ctx, member: discord.Member, minutos: int = 10, *, reason="No especificada"):
    muted_role = await find_or_create_role(ctx.guild, "muted")
    if muted_role in member.roles: return await ctx.send("Ya muteado.")
    await member.add_roles(muted_role, reason=reason)
    await ctx.send(f"🔇 {member.mention} muteado {minutos} min.")
    await asyncio.sleep(minutos*60)
    if muted_role in member.roles:
        await member.remove_roles(muted_role)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def unmute(ctx, member: discord.Member):
    muted_role = await find_or_create_role(ctx.guild, "muted")
    if muted_role not in member.roles: return await ctx.send("No muteado.")
    await member.remove_roles(muted_role)
    await ctx.send(f"🔊 {member.mention} desmuteado.")

@bot.command()
async def report(ctx, member: discord.Member, *, reason):
    log_ch = await bot.get_log_channel(ctx.guild, "mod-logs")
    if not log_ch: return await ctx.send("Canal de logs no encontrado.")
    embed = create_embed("📢 Reporte", f"**Reportado:** {member.mention}\n**Autor:** {ctx.author.mention}\n**Razón:** {reason}", discord.Color.red())
    await log_ch.send(embed=embed)
    await ctx.send("✅ Reporte enviado.", delete_after=3)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int):
    if amount < 1: return await ctx.reply("Cantidad inválida.")
    await ctx.channel.purge(limit=amount+1)
    await ctx.send(f"🧹 {amount} mensajes eliminados.", delete_after=3)

@bot.command()
@commands.has_permissions(manage_channels=True)
async def slowmode(ctx, segundos: int):
    await ctx.channel.edit(slowmode_delay=segundos)
    await ctx.send(f"⏱️ Slowmode {segundos}s" if segundos else "Slowmode desactivado.")

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
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = create_embed(f"🖼️ Avatar de {member.display_name}", "", discord.Color.blue(), image=member.avatar.url if member.avatar else member.default_avatar.url)
    await ctx.send(embed=embed)

@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = create_embed(f"ℹ️ {member.display_name}", f"**ID:** {member.id}\n**Cuenta creada:** {member.created_at.strftime('%d/%m/%Y')}\n**Entró:** {member.joined_at.strftime('%d/%m/%Y')}", member.color, thumbnail=member.avatar.url if member.avatar else None)
    await ctx.send(embed=embed)

@bot.command()
async def serverinfo(ctx):
    guild = ctx.guild
    embed = create_embed(f"📊 {guild.name}", f"**Dueño:** {guild.owner.mention}\n**Miembros:** {guild.member_count}\n**Canales:** {len(guild.channels)}", discord.Color.blurple(), thumbnail=guild.icon.url if guild.icon else None)
    await ctx.send(embed=embed)

@bot.command()
async def ping(ctx):
    latency = round(bot.latency * 1000)
    embed = create_embed("🏓 Pong!", f"Latencia: **{latency}ms**", discord.Color.green() if latency < 200 else discord.Color.red())
    await ctx.send(embed=embed)

@bot.command()
async def say(ctx, *, mensaje):
    await ctx.message.delete()
    await ctx.send(mensaje)

@bot.command()
async def embed(ctx, *, text):
    embed = create_embed("Mensaje", text, discord.Color.teal())
    await ctx.send(embed=embed)

@bot.command()
async def poll(ctx, *, pregunta):
    embed = create_embed("📊 Encuesta", pregunta, discord.Color.blue())
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    await msg.add_reaction("🤷")

@bot.command()
async def sugerir(ctx, *, idea):
    suggestions_ch = discord.utils.get(ctx.guild.text_channels, name=CHANNEL_NAMES["suggestions"])
    if not suggestions_ch:
        return await ctx.reply("Canal de sugerencias no encontrado. Ejecuta !setup.")
    embed = create_embed(f"💡 Sugerencia de {ctx.author.display_name}", idea, discord.Color.blue(), thumbnail=ctx.author.avatar.url if ctx.author.avatar else None)
    msg = await suggestions_ch.send(embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    await ctx.reply("✅ Sugerencia enviada.", delete_after=3)

@bot.command()
@commands.has_permissions(administrator=True)
async def giveaway(ctx, duration: int, *, prize: str):
    embed = create_embed("🎉 SORTEO", f"**Premio:** {prize}\n**Duración:** {duration} minutos\nReacciona con 🎉", discord.Color.gold())
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("🎉")
    await asyncio.sleep(duration*60)
    msg = await ctx.channel.fetch_message(msg.id)
    reaction = discord.utils.get(msg.reactions, emoji="🎉")
    if reaction:
        users = [user async for user in reaction.users() if not user.bot]
        if users:
            winner = random.choice(users)
            await ctx.send(f"🎁 Ganador: {winner.mention}")

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx, clean: Optional[str] = None):
    guild = ctx.guild
    if not guild: return
    await ctx.send("⚙️ Configurando...")
    
    if clean == "--clean":
        for ch in guild.channels:
            try: await ch.delete()
            except: pass
        await ctx.send("Canales eliminados.")
    
    roles = {}
    for key in ROLES_CONFIG:
        roles[key] = await find_or_create_role(guild, key)
    
    for cat_key, cat_conf in CATEGORIES.items():
        category = await find_or_create_category(guild, cat_key)
        for ch_key in cat_conf["channels"]:
            ch_name = CHANNEL_NAMES.get(ch_key, ch_key)
            if not discord.utils.get(guild.text_channels, name=ch_name):
                try:
                    await guild.create_text_channel(ch_name, category=category)
                except: pass
    
    tickets_ch = discord.utils.get(guild.text_channels, name=CHANNEL_NAMES["tickets"])
    if tickets_ch:
        embed = create_embed("🎟️ SOPORTE", "Abre un ticket para ayuda.", discord.Color.blurple())
        await tickets_ch.send(embed=embed, view=TicketPanelView())
    
    mod_panel_ch = discord.utils.get(guild.text_channels, name=CHANNEL_NAMES["mod-panel"])
    if mod_panel_ch:
        embed = create_embed("🛡️ PANEL MODERACIÓN", "Selecciona acción del menú.", discord.Color.dark_red())
        await mod_panel_ch.send(embed=embed, view=ModPanelView())
    
    await ctx.send("✅ Configuración completada.")

@bot.command()
@commands.has_permissions(administrator=True)
async def roles_panel(ctx):
    view = RoleSelectView()
    embed = create_embed("🎭 SELECCIÓN DE ROLES", "Elige tus roles del menú.", discord.Color.gold())
    await ctx.send(embed=embed, view=view)

# 🔥 COMANDO HELP - AHORA SÍ FUNCIONA PORQUE EL DEFAULT FUE ELIMINADO
@bot.command(name="help")
async def help_command(ctx, command_name: str = None):
    """Muestra la lista de comandos"""
    if command_name:
        cmd = bot.get_command(command_name)
        if not cmd:
            return await ctx.send(f"❌ Comando `{command_name}` no encontrado.")
        embed = create_embed(f"📚 Ayuda: {cmd.name}", f"**Descripción:** {cmd.help or 'Sin descripción'}\n**Uso:** `{config.PREFIX}{cmd.name} {cmd.signature}`", discord.Color.blurple())
        return await ctx.send(embed=embed)
    
    embed = create_embed(
        f"📚 COMANDOS DE {config.SERVER_NAME}",
        "```\n"
        "🛡️ MODERACIÓN\n"
        f"{config.PREFIX}warn, {config.PREFIX}warns, {config.PREFIX}delwarn, {config.PREFIX}mute, {config.PREFIX}unmute\n"
        f"{config.PREFIX}clear, {config.PREFIX}slowmode, {config.PREFIX}lock, {config.PREFIX}unlock, {config.PREFIX}report\n\n"
        "ℹ️ INFORMACIÓN\n"
        f"{config.PREFIX}avatar, {config.PREFIX}userinfo, {config.PREFIX}serverinfo, {config.PREFIX}ping\n\n"
        "🔧 UTILIDADES\n"
        f"{config.PREFIX}say, {config.PREFIX}embed, {config.PREFIX}poll, {config.PREFIX}sugerir\n\n"
        "⚙️ ADMINISTRACIÓN\n"
        f"{config.PREFIX}setup, {config.PREFIX}roles_panel, {config.PREFIX}giveaway\n"
        "```",
        discord.Color.blurple()
    )
    await ctx.send(embed=embed)

# ==================== EVENTOS ====================
@bot.event
async def on_member_join(member):
    new_role = await find_or_create_role(member.guild, "new")
    await member.add_roles(new_role)
    welcome_ch = await bot.get_log_channel(member.guild, "welcome")
    if welcome_ch:
        embed = create_embed(f"✨ BIENVENIDO {member.display_name}", f"¡Bienvenido a {config.SERVER_NAME}!\nAhora somos {member.guild.member_count} miembros.", discord.Color.green(), thumbnail=member.avatar.url if member.avatar else None)
        await welcome_ch.send(content=member.mention, embed=embed)
    
    await asyncio.sleep(3600)
    member_role = await find_or_create_role(member.guild, "member")
    if member_role not in member.roles and new_role in member.roles:
        await member.remove_roles(new_role)
        await member.add_roles(member_role)

@bot.event
async def on_member_remove(member):
    log_ch = await bot.get_log_channel(member.guild, "member-logs")
    if log_ch:
        embed = create_embed("📤 Miembro salió", f"{member.display_name} abandonó.", discord.Color.orange())
        await log_ch.send(embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot: return
    await bot.process_commands(message)

# ==================== WEB SERVER ====================
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class WebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is alive!")
    def log_message(self, format, *args): pass

def run_web_server():
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), WebHandler)
    server.serve_forever()

# ==================== EJECUCIÓN ====================
if __name__ == "__main__":
    Path("data").mkdir(exist_ok=True)
    threading.Thread(target=run_web_server, daemon=True).start()
    bot.run(TOKEN)