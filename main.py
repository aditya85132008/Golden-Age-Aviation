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

load_dotenv()
token = os.getenv('DISCORD_TOKEN')
VERIFY_CHANNEL_ID = 1410464974152794212

active_polls = {}

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)
ranks= "Cadet"
VERIFICATION_ROLE_NAME="Verified"
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

#Verification
# Create Verify button
class VerifyView(View):
    def __init__(self):
        super().__init__(timeout=None)  # persistent view

    @discord.ui.button(label="✅ Verify", style=discord.ButtonStyle.success, custom_id="verify_button")
    async def verify_button(self, interaction: discord.Interaction, button: Button):
        role = discord.utils.get(interaction.guild.roles, name=VERIFICATION_ROLE_NAME)
        if role is None:
            await interaction.response.send_message("❌ Verification role not found!", ephemeral=True)
            return

        if role in interaction.user.roles:
            await interaction.response.send_message("⚠️ You are already verified!", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("✅ You are now verified!", ephemeral=True)


# Command for admin to set up verification
@bot.command()
@commands.has_permissions(administrator=True)
async def setupverify(ctx, channel: discord.TextChannel):
    embed = discord.Embed(
        title="🔒 Server Verification",
        description="Click the button below to gain access to the server.",
        color=discord.Color.green()
    )
    await channel.send(embed=embed, view=VerifyView())
    await ctx.send(f"✅ Verification system set up in {channel.mention}", delete_after=5)


# Register persistent view when bot restarts
@bot.event
async def on_ready():
    bot.add_view(VerifyView())  # THIS is what keeps button working after restart
    print(f"✅ Logged in as {bot.user}")

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

#Verification
# View with Verify Button
class VerifyView(View):
    def __init__(self):
        super().__init__(timeout=None)  # persistent view

    @discord.ui.button(label="✅ Verify", style=discord.ButtonStyle.success, custom_id="verify_button")
    async def verify_button(self, interaction: discord.Interaction, button: Button):
        role = discord.utils.get(interaction.guild.roles, name=VERIFICATION_ROLE_NAME)
        if role is None:
            await interaction.response.send_message("❌ Verification role not found!", ephemeral=True)
            return

        if role in interaction.user.roles:
            await interaction.response.send_message("⚠️ You are already verified!", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("✅ You are now verified!", ephemeral=True)


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

    # Send Verify message automatically
    channel = bot.get_channel(VERIFY_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title="🔒 Server Verification",
            description="Click the button below to verify and gain access to the server.",
            color=discord.Color.green()
        )
        await channel.send(embed=embed, view=VerifyView())
    else:
        print("⚠️ Could not find the verification channel. Check VERIFY_CHANNEL_ID.")

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
def get_log_channel(guild):
    return guild.get_channel(LOG_CHANNEL_ID)

# Log message edits
@bot.event
async def on_message_edit(before, after):
    if before.author == bot.user:
        return
    log_channel = get_log_channel(before.guild)
    if log_channel and before.content != after.content:
        await log_channel.send(
            f"✏️ **Message edited** by {before.author} in {before.channel.mention}:\n"
            f"Before: {before.content}\nAfter: {after.content}"
        )

# Log bulk deletes
@bot.event
async def on_bulk_message_delete(messages):
    if not messages:
        return
    guild = messages[0].guild
    channel = messages[0].channel
    log_channel = get_log_channel(guild)
    if log_channel:
        await log_channel.send(
            f"🗑️ **Bulk delete** in {channel.mention}:\n"
            f"{len(messages)} messages were deleted."
        )

# Log member joins
@bot.event
async def on_member_join(member):
    log_channel = get_log_channel(member.guild)
    if log_channel:
        await log_channel.send(f"✅ **Member joined:** {member.mention} ({member})")

# Log member leaves
@bot.event
async def on_member_remove(member):
    log_channel = get_log_channel(member.guild)
    if log_channel:
        await log_channel.send(f"❌ **Member left:** {member.mention} ({member})")

# Log role changes
@bot.event
async def on_member_update(before, after):
    log_channel = get_log_channel(before.guild)
    if log_channel:
        added_roles = [r.name for r in after.roles if r not in before.roles]
        removed_roles = [r.name for r in before.roles if r not in after.roles]

        if added_roles:
            await log_channel.send(
                f"➕ **Roles added** to {after.mention}: {', '.join(added_roles)}"
            )
        if removed_roles:
            await log_channel.send(
                f"➖ **Roles removed** from {after.mention}: {', '.join(removed_roles)}"
            )

# Command to set the log channel
@bot.command()
@commands.has_permissions(administrator=True)
async def setlog(ctx, channel: discord.TextChannel):
    global LOG_CHANNEL_ID
    LOG_CHANNEL_ID = channel.id
    await ctx.send(f"✅ Logging enabled in {channel.mention}")

webserver.keep_alive()
bot.run(token, log_handler=handler, log_level=logging.DEBUG)

