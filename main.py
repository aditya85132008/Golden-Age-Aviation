import discord
from discord.ext import commands
from discord.ui import Button, View
from datetime import timedelta
import logging
from dotenv import load_dotenv
import os
import webserver
import requests
import asyncio
import re
import time
import json
from typing import Dict, Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
token = os.getenv('DISCORD_TOKEN')
VERIFY_CHANNEL_ID = 1410464974152794212
ROLE_CHANNEL_ID = 1410450848357548062

active_polls = {}

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents = discord.Intents.all()
intents.message_content = True
intents.members = True
intents.reactions = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)
ranks= "Cadet"
LOG_CHANNEL_ID = 1410457088290721812

@bot.event
async def on_ready():
    print(f"We are ready to go in, {bot.user.name}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if "fuck you" in message.content.lower():
        await message.delete()
        await message.channel.send(f"{message.author.mention} dont use that word!")

    if "fck u" in message.content.lower():
        await message.delete()
        await message.channel.send(f"{message.author.mention} dont use that word!")

    if "chutiya" in message.content.lower():
        await message.delete()
        await message.channel.send(f"{message.author.mention} dont use that word!")

    await bot.process_commands(message)

#VAMSYS
# Replace keys with EXACT Phoenix rank names; values are Discord role IDs (strings)
RANK_TO_ROLE: Dict[str, str] = {
    "Ramp Rookie":             "1410171636283478087",
    "Taxiway Tourist":         "1411271211031330847",
    "Checklist Chaser":        "1412057083653783584",
    "Runway Rover":            "1412057475313831956",
    "VOR Voyager":             "1412057577881079888",
    "Waypoint Wrangler":       "1412057574894993560",
    "Crosswind Curator":       "1412057700950347807",
    "Jetstream Juggler":       "1412057751164817501",
}
# Optional helpers
VERIFIED_ROLE_ID   = "1410459198042411070"   # “Verified” role (optional)
UNVERIFIED_ROLE_ID = "1410169335712059394"   # “Unverified” role (optional)

class TokenManager:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.token: Optional[str] = None
        self.expiry: float = 0.0

    async def get_token(self) -> str:
        now = time.time()
        if self.token and now < self.expiry - 60:
            return self.token

        data = {
            "grant_type": "client_credentials",
            "client_id": VAMSYS_CLIENT_ID,
            "client_secret": VAMSYS_CLIENT_SECRET,
        }
        headers = { "Content-Type": "application/x-www-form-urlencoded" }
        async with self.session.post(VAMSYS_TOKEN_URL, data=data, headers=headers) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"OAuth token error {resp.status}: {text}")
            j = await resp.json()
            self.token = j.get("access_token")
            expires_in = int(j.get("expires_in", 3600))
            self.expiry = now + expires_in
            return self.token
        
class VamsysClient:
    def __init__(self, session: aiohttp.ClientSession, token_mgr: TokenManager):
        self.session = session
        self.token_mgr = token_mgr

    async def _request(self, path: str, method: str = "GET", payload: Optional[dict] = None):
        token = await self.token_mgr.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        url = f"{VAMSYS_API_BASE}{path}"
        if method.upper() == "POST":
            headers["Content-Type"] = "application/json"
            async with self.session.post(url, headers=headers, data=json.dumps(payload or {})) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    raise RuntimeError(f"vAMSYS {resp.status} on {path}: {text}")
                return await resp.json()
        else:
            async with self.session.get(url, headers=headers) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    raise RuntimeError(f"vAMSYS {resp.status} on {path}: {text}")
                return await resp.json()

    async def get_pilot_by_discord(self, discord_member_id: int) -> dict:
        # Confirm the path in your v3 docs; request body must include "discord_member_id"
        return await self._request("/discord/pilot", "POST", payload={"discord_member_id": str(discord_member_id)})
    
async def sync_member_rank_roles(member: discord.Member, pilot: dict):
    rank_name = (
        pilot.get("rank", {}).get("name")
        or pilot.get("rank", {}).get("display_name")
        or pilot.get("rank")
    )
    if not rank_name:
        raise RuntimeError("Pilot rank missing in API response")

    desired_role_id = RANK_TO_ROLE.get(str(rank_name))
    if not desired_role_id:
        raise RuntimeError(f"No Discord role mapping for rank: {rank_name}")

    # Build sets for remove/add
    all_rank_role_ids = set(RANK_TO_ROLE.values())
    current_ids = set(r.id for r in member.roles)

    to_remove = [rid for rid in current_ids if rid in all_rank_role_ids and rid != desired_role_id]
    to_add = []
    if desired_role_id not in current_ids:
        to_add.append(desired_role_id)
    if VERIFIED_ROLE_ID and VERIFIED_ROLE_ID not in current_ids:
        to_add.append(VERIFIED_ROLE_ID)
    if UNVERIFIED_ROLE_ID and UNVERIFIED_ROLE_ID in current_ids:
        to_remove.append(UNVERIFIED_ROLE_ID)

    # Apply changes
    if to_remove:
        try:
            await member.remove_roles(*[member.guild.get_role(int(r)) for r in to_remove if member.guild.get_role(int(r))], reason="Rank re-sync")
        except Exception:
            pass
    if to_add:
        try:
            await member.add_roles(*[member.guild.get_role(int(r)) for r in to_add if member.guild.get_role(int(r))], reason="Rank re-sync")
        except Exception:
            pass

    return rank_name, to_add, to_remove

# Shared HTTP session / clients
session: Optional[aiohttp.ClientSession] = None
vms_client: Optional[VamsysClient] = None

@bot.event
async def on_ready():
    global session, vms_client
    if session is None:
        session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        vms_client = VamsysClient(session, TokenManager(session))

    try:
        guild = discord.Object(id=GUILD_ID) if GUILD_ID else None
        if guild:
            await tree.sync(guild=guild)
        else:
            await tree.sync()
        print(f"Logged in as {bot.user} (ID: {bot.user.id}) — slash commands synced.")
    except Exception as e:
        print(f"Command sync failed: {e}")

@bot.event
async def on_member_join(member: discord.Member):
    # Only operate within configured guild
    if GUILD_ID and member.guild.id != GUILD_ID:
        return
    if vms_client is None:
        return

    try:
        data = await vms_client.get_pilot_by_discord(member.id)
        pilot = data.get("pilot")
        if not pilot:
            raise RuntimeError("No pilot object returned")

        rank_name, added, removed = await sync_member_rank_roles(member, pilot)
        print(f"Auto-verified {member} as {rank_name}")
        # Optional DM
        try:
            callsign = pilot.get("callsign") or pilot.get("username") or "pilot"
            await member.send(f"Welcome! You were verified as **{callsign}** (rank: **{rank_name}**).")
        except Exception:
            pass
    except Exception as e:
        print(f"Auto-verify failed for {member}: {e}")
        # Assign Unverified role (optional) and DM instructions
        if UNVERIFIED_ROLE_ID:
            role = member.guild.get_role(int(UNVERIFIED_ROLE_ID))
            if role:
                try:
                    await member.add_roles(role, reason="Not linked in vAMSYS yet")
                except Exception:
                    pass
        try:
            await member.send(
                "Welcome! I couldn't auto-verify you because your Discord account isn't linked in vAMSYS yet."

"
                "Please open **Phoenix → Profile → Preferences → Link Discord**, then ask a staff member to run `/syncroles` for you."
            )
        except Exception:
            pass

# Admin-only /syncroles
@tree.command(name="syncroles", description="Admin: re-sync roles for a member")
@app_commands.default_permissions(manage_roles=True)
@app_commands.describe(member="Member to sync (optional)")
async def syncroles(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    if member is None:
        member = interaction.user if isinstance(interaction.user, discord.Member) else None
    if member is None:
        await interaction.response.send_message("Cannot resolve member.", ephemeral=True)
        return
    if vms_client is None:
        await interaction.response.send_message("API client not ready.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    try:
        data = await vms_client.get_pilot_by_discord(member.id)
        pilot = data.get("pilot")
        if not pilot:
            raise RuntimeError("No pilot linked to this Discord")
        rank_name, added, removed = await sync_member_rank_roles(member, pilot)
        await interaction.followup.send(f"🔁 Synced **{member.display_name}** → rank **{rank_name}**. Roles updated.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Could not sync **{member.display_name}**: {e}", ephemeral=True)

async def main():
    try:
        await bot.start(DISCORD_TOKEN)
    finally:
        if session:
            await session.close()

if __name__ == "__main__":
    asyncio.run(main())

#Embed Message
@bot.command()
async def sendembed(ctx, channel: discord.TextChannel, title: str, color: str, thumbnail_url: str, image_url: str, *, content: str):
    """
    Send a fully customizable embedded message with fields and image.
    Usage:
    !sendembed #channel "Title" blue "https://thumb.url" "https://image.url" description here || Field1: Value1 || Field2: Value2
    """

    # Handle color input (hex or named)
    color = color.lower()
    if color.startswith("#"):
        embed_color = discord.Color(int(color[1:], 16))  # hex like #ff0000
    else:
        colors = {
            "red": discord.Color.red(),
            "blue": discord.Color.blue(),
            "green": discord.Color.green(),
            "purple": discord.Color.purple(),
            "gold": discord.Color.gold(),
            "orange": discord.Color.orange(),
            "teal": discord.Color.teal(),
            "default": discord.Color.default()
        }
        embed_color = colors.get(color, discord.Color.default())

    # Split description and fields
    parts = content.split("||")
    description = parts[0].strip()
    fields = parts[1:] if len(parts) > 1 else []

    # Create embed
    embed = discord.Embed(
        title=title,
        description=description,
        color=embed_color
    )

    # Thumbnail
    if thumbnail_url.lower() != "none":
        embed.set_thumbnail(url=thumbnail_url)

    # Big Image
    if image_url.lower() != "none":
        embed.set_image(url=image_url)

    # Add fields
    for field in fields:
        if ":" in field:
            name, value = field.split(":", 1)
            embed.add_field(name=name.strip(), value=value.strip(), inline=False)

    # Send embed
    await channel.send(embed=embed)
    await ctx.send(f"✅ Embed sent to {channel.mention}")

#METAR
@bot.command()
async def metar(ctx, icao: str):
    """Get raw METAR info for an ICAO airport code"""
    icao = icao.upper()
    url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao}.TXT"

    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            lines = response.text.strip().split("\n")
            if len(lines) >= 2:
                time = lines[0]
                metar_text = lines[1]
                await ctx.send(
                    f"**METAR for {icao}**\n📅 {time}\n```\n{metar_text}\n```"
                )
            else:
                await ctx.send("⚠️ No valid METAR data found.")
        else:
            await ctx.send("⚠️ Invalid ICAO code or data unavailable.")
    except Exception as e:
        await ctx.send(f"❌ Error fetching METAR: {e}")

@bot.command()
async def taf(ctx, icao: str):
    """Get raw TAF info for an ICAO airport code"""
    icao = icao.upper()
    url = f"https://tgftp.nws.noaa.gov/data/forecasts/taf/stations/{icao}.TXT"

    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            taf_text = response.text.strip()
            await ctx.send(
                f"**TAF for {icao}**\n```\n{taf_text}\n```"
            )
        else:
            await ctx.send("⚠️ Invalid ICAO code or data unavailable.")
    except Exception as e:
        await ctx.send(f"❌ Error fetching TAF: {e}")

#Purging
@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int, channel: discord.TextChannel = None, member: discord.Member = None):
    """
    Purge messages in a channel.
    Usage:
    !purge 10                  -> Deletes 10 messages in current channel
    !purge 20 #channel         -> Deletes 20 messages in another channel
    !purge 30 #channel @user   -> Deletes 30 messages from a user in that channel
    """

    # If no channel is mentioned, use current one
    target_channel = channel or ctx.channel

    def check(msg):
        return (member is None or msg.author == member)

    deleted = await target_channel.purge(limit=amount, check=check)
    confirm = await ctx.send(f"✅ Deleted {len(deleted)} messages in {target_channel.mention}", delete_after=1)
    
#POLL
def parse_time(time_str: str) -> int:
    import re
    matches = re.findall(r"(\d+)([dhms])", time_str.lower())
    total = 0
    for value, unit in matches:
        value = int(value)
        if unit == "d": total += value * 86400
        elif unit == "h": total += value * 3600
        elif unit == "m": total += value * 60
        elif unit == "s": total += value
    return total

def format_time(seconds: int) -> str:
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    parts = []
    if days: parts.append(f"{days}d")
    if hours: parts.append(f"{hours}h")
    if minutes: parts.append(f"{minutes}m")
    if seconds: parts.append(f"{seconds}s")
    return " ".join(parts)

async def close_poll(message_id: int, channel):
    poll_info = active_polls[message_id]
    msg = await channel.fetch_message(message_id)

    thumbs_up = discord.utils.get(msg.reactions, emoji="👍")
    thumbs_down = discord.utils.get(msg.reactions, emoji="👎")

    upvotes = thumbs_up.count - 1 if thumbs_up else 0
    downvotes = thumbs_down.count - 1 if thumbs_down else 0

    result_embed = discord.Embed(
        title="📌 Poll Closed",
        description=f"**{poll_info['question']}**\n\n👍 {upvotes} | 👎 {downvotes}",
        color=discord.Color.red()
    )

    await msg.edit(embed=result_embed)
    await msg.clear_reactions()
    del active_polls[message_id]

@bot.command()
async def poll(ctx, duration: str, *, question: str):
    total_seconds = parse_time(duration)
    if total_seconds <= 0:
        await ctx.send("❌ Invalid duration format!")
        return

    end_time = time.time() + total_seconds
    embed = discord.Embed(title="📊 New Poll", description=question, color=discord.Color.blue())
    embed.set_footer(text=f"Time remaining: {format_time(total_seconds)} | 👍 0 | 👎 0")
    poll_message = await ctx.send(embed=embed)
    await poll_message.add_reaction("👍")
    await poll_message.add_reaction("👎")

    active_polls[poll_message.id] = {
        "question": question,
        "channel_id": ctx.channel.id,
        "end_time": end_time
    }

    while poll_message.id in active_polls:
        remaining = int(end_time - time.time())
        if remaining <= 0:
            break

        # Fetch latest reactions
        msg = await ctx.channel.fetch_message(poll_message.id)
        thumbs_up = discord.utils.get(msg.reactions, emoji="👍")
        thumbs_down = discord.utils.get(msg.reactions, emoji="👎")

        upvotes = thumbs_up.count - 1 if thumbs_up else 0
        downvotes = thumbs_down.count - 1 if thumbs_down else 0

        embed.set_footer(text=f"Time remaining: {format_time(remaining)} | 👍 {upvotes} | 👎 {downvotes}")
        await poll_message.edit(embed=embed)
        await asyncio.sleep(1)

    if poll_message.id in active_polls:
        await close_poll(poll_message.id, ctx.channel)

@bot.command()
async def closepoll(ctx, message_id: int):
    if message_id not in active_polls:
        await ctx.send("❌ No active poll with that ID.")
        return

    poll_info = active_polls[message_id]
    channel = bot.get_channel(poll_info["channel_id"])
    await close_poll(message_id, channel)
    await ctx.send(f"✅ Poll '{poll_info['question']}' closed manually.")

#Ban, Unban, Timeout, Kick                     
# BAN
@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason provided"):
    await member.ban(reason=reason)
    await ctx.send(f"🔨 {member} has been banned. Reason: {reason}")


# UNBAN
@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, user_id: int):
    try:
        user = await bot.fetch_user(user_id)
        await ctx.guild.unban(user)
        await ctx.send(f"✅ {user} has been unbanned.")
    except Exception as e:
        await ctx.send(f"❌ Failed to unban: {e}")


# KICK
@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason provided"):
    await member.kick(reason=reason)
    await ctx.send(f"👢 {member} has been kicked. Reason: {reason}")

# MUTE (timeout)
@bot.command()
@commands.has_permissions(moderate_members=True)
async def mute(ctx, member: discord.Member, minutes: int = 10, *, reason="No reason provided"):
    duration = timedelta(minutes=minutes)
    await member.timeout(duration, reason=reason)
    await ctx.send(f"🔇 {member} muted for {minutes} minutes. Reason: {reason}")


# UNMUTE
@bot.command()
@commands.has_permissions(moderate_members=True)
async def unmute(ctx, member: discord.Member):
    await member.timeout(None)
    await ctx.send(f"🔊 {member} has been unmuted.")


# LIST BANNED USERS (with IDs)
@bot.command(name="banned")
@commands.has_permissions(ban_members=True)
async def banned(ctx):
    bans = await ctx.guild.bans()
    if not bans:
        await ctx.send("✅ No users are banned.")
        return

    msg = "**🔒 Banned Users:**\n"
    for ban_entry in bans:
        user = ban_entry.user
        msg += f"- {user} (ID: `{user.id}`)\n"

    await ctx.send(msg)

#LOGS
def log_channel():
    return bot.get_channel(LOG_CHANNEL_ID)

# Utility to mention user without ping
def user_ref(user: discord.User):
    return f"<@{user.id}>"

# ------------------- MESSAGE EVENTS ------------------- #
@bot.event
async def on_message_delete(message):
    if message.author.bot: return
    embed = discord.Embed(title="🗑️ Message Deleted", color=discord.Color.red())
    embed.add_field(name="User", value=user_ref(message.author), inline=True)
    embed.add_field(name="Channel", value=message.channel.mention, inline=True)
    embed.add_field(name="Content", value=message.content or "*(embed/attachment)*", inline=False)
    await log_channel().send(embed=embed)

@bot.event
async def on_message_edit(before, after):
    if before.author.bot: return
    if before.content == after.content: return
    embed = discord.Embed(title="✏️ Message Edited", color=discord.Color.orange())
    embed.add_field(name="User", value=user_ref(before.author), inline=True)
    embed.add_field(name="Channel", value=before.channel.mention, inline=True)
    embed.add_field(name="Before", value=before.content or "*(embed/attachment)*", inline=False)
    embed.add_field(name="After", value=after.content or "*(embed/attachment)*", inline=False)
    await log_channel().send(embed=embed)

@bot.event
async def on_bulk_message_delete(messages):
    embed = discord.Embed(title="🚮 Bulk Messages Deleted", color=discord.Color.dark_red())
    embed.add_field(name="Channel", value=messages[0].channel.mention, inline=False)
    embed.add_field(name="Count", value=str(len(messages)), inline=False)
    await log_channel().send(embed=embed)

# ------------------- INVITES ------------------- #
@bot.event
async def on_invite_create(invite):
    embed = discord.Embed(title="🔗 Invite Created", color=discord.Color.green())
    embed.add_field(name="Code", value=invite.code)
    embed.add_field(name="Creator", value=user_ref(invite.inviter))
    embed.add_field(name="Channel", value=invite.channel.mention)
    await log_channel().send(embed=embed)

@bot.event
async def on_invite_delete(invite):
    embed = discord.Embed(title="❌ Invite Deleted", color=discord.Color.red())
    embed.add_field(name="Code", value=invite.code)
    await log_channel().send(embed=embed)

# ------------------- MEMBER EVENTS ------------------- #
@bot.event
async def on_member_join(member):
    embed = discord.Embed(title="👋 Member Joined", color=discord.Color.green())
    embed.add_field(name="User", value=user_ref(member))
    await log_channel().send(embed=embed)

@bot.event
async def on_member_remove(member):
    embed = discord.Embed(title="🚪 Member Left", color=discord.Color.red())
    embed.add_field(name="User", value=user_ref(member))
    await log_channel().send(embed=embed)

@bot.event
async def on_member_update(before, after):
    changes = []
    if before.nick != after.nick:
        changes.append(f"Nickname: `{before.nick}` ➝ `{after.nick}`")
    if before.timed_out_until != after.timed_out_until:
        changes.append(f"⏳ Timeout updated")
    if before.roles != after.roles:
        before_roles = {r.id for r in before.roles}
        after_roles = {r.id for r in after.roles}
        added = after_roles - before_roles
        removed = before_roles - after_roles
        if added:
            for role in after.roles:
                if role.id in added:
                    changes.append(f"➕ Role Added: {role.name}")
        if removed:
            for role in before.roles:
                if role.id in removed:
                    changes.append(f"➖ Role Removed: {role.name}")

    if changes:
        embed = discord.Embed(title="👤 Member Updated", color=discord.Color.blue())
        embed.add_field(name="User", value=user_ref(after), inline=False)
        embed.add_field(name="Changes", value="\n".join(changes), inline=False)
        await log_channel().send(embed=embed)

# ------------------- BAN / UNBAN ------------------- #
@bot.event
async def on_member_ban(guild, user):
    embed = discord.Embed(title="🔨 Member Banned", color=discord.Color.dark_red())
    embed.add_field(name="User", value=user_ref(user))
    await log_channel().send(embed=embed)

@bot.event
async def on_member_unban(guild, user):
    embed = discord.Embed(title="⚖️ Member Unbanned", color=discord.Color.green())
    embed.add_field(name="User", value=user_ref(user))
    await log_channel().send(embed=embed)

# ------------------- ROLE EVENTS ------------------- #
@bot.event
async def on_guild_role_create(role):
    embed = discord.Embed(title="🎭 Role Created", description=role.name, color=discord.Color.green())
    await log_channel().send(embed=embed)

@bot.event
async def on_guild_role_delete(role):
    embed = discord.Embed(title="🗑️ Role Deleted", description=role.name, color=discord.Color.red())
    await log_channel().send(embed=embed)

@bot.event
async def on_guild_role_update(before, after):
    embed = discord.Embed(title="📝 Role Updated", color=discord.Color.orange())
    embed.add_field(name="Before", value=before.name, inline=True)
    embed.add_field(name="After", value=after.name, inline=True)
    await log_channel().send(embed=embed)

# ------------------- CHANNEL EVENTS ------------------- #
@bot.event
async def on_guild_channel_create(channel):
    embed = discord.Embed(title="📢 Channel Created", description=channel.name, color=discord.Color.green())
    await log_channel().send(embed=embed)

@bot.event
async def on_guild_channel_delete(channel):
    embed = discord.Embed(title="❌ Channel Deleted", description=channel.name, color=discord.Color.red())
    await log_channel().send(embed=embed)

@bot.event
async def on_guild_channel_update(before, after):
    embed = discord.Embed(title="🔧 Channel Updated", color=discord.Color.orange())
    embed.add_field(name="Before", value=before.name, inline=True)
    embed.add_field(name="After", value=after.name, inline=True)
    await log_channel().send(embed=embed)

# ------------------- EMOJI EVENTS ------------------- #
@bot.event
async def on_guild_emojis_update(guild, before, after):
    before_set = {e.id: e for e in before}
    after_set = {e.id: e for e in after}
    embed = discord.Embed(title="😃 Emoji Update", color=discord.Color.purple())

    for e in after:
        if e.id not in before_set:
            embed.add_field(name="Emoji Created", value=e.name)
    for e in before:
        if e.id not in after_set:
            embed.add_field(name="Emoji Deleted", value=e.name)
    await log_channel().send(embed=embed)

# ------------------- VOICE EVENTS ------------------- #
@bot.event
async def on_voice_state_update(member, before, after):
    if before.channel != after.channel:
        if before.channel is None:
            action = f"🎙️ Joined {after.channel.name}"
        elif after.channel is None:
            action = f"📴 Left {before.channel.name}"
        else:
            action = f"🔄 Moved {before.channel.name} ➝ {after.channel.name}"

        embed = discord.Embed(title="🔊 Voice Update", color=discord.Color.teal())
        embed.add_field(name="User", value=user_ref(member))
        embed.add_field(name="Action", value=action)
        await log_channel().send(embed=embed)

#SELF-ROLE
# Replace with your role IDs
ROLE_OPTIONS = {
    "📢": 1412061430550757456,  # Alert
    "💬": 1412061581520539708,  # NOTAM
    "🔥": 1412061613342593044   # Activity
}

@bot.event
async def on_ready():
    print(f"{bot.user} is online!")

@bot.command()
async def selfrole(ctx):
    """Send self-role embed in the fixed channel"""
    channel = bot.get_channel(ROLE_CHANNEL_ID)

    embed = discord.Embed(
        title="Self Roles",
        description="React to get your roles!\n\n" +
                    "\n".join([f"{emoji} → <@&{role_id}>" for emoji, role_id in ROLE_OPTIONS.items()]),
        color=discord.Color.blue()
    )

    message = await channel.send(embed=embed)

    for emoji in ROLE_OPTIONS.keys():
        await message.add_reaction(emoji)

    await ctx.send(f"✅ Self-role embed posted in {channel.mention}")

@bot.event
async def on_raw_reaction_add(payload):
    if payload.channel_id == ROLE_CHANNEL_ID and str(payload.emoji) in ROLE_OPTIONS:
        guild = bot.get_guild(payload.guild_id)
        role = guild.get_role(ROLE_OPTIONS[str(payload.emoji)])
        member = guild.get_member(payload.user_id)
        if member is not None:
            await member.add_roles(role)

@bot.event
async def on_raw_reaction_remove(payload):
    if payload.channel_id == ROLE_CHANNEL_ID and str(payload.emoji) in ROLE_OPTIONS:
        guild = bot.get_guild(payload.guild_id)
        role = guild.get_role(ROLE_OPTIONS[str(payload.emoji)])
        member = guild.get_member(payload.user_id)
        if member is not None:
            await member.remove_roles(role)

webserver.keep_alive()
bot.run(token, log_handler=handler, log_level=logging.DEBUG)



