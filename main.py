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
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
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
tree = bot.tree  # ✅ define this BEFORE using @tree.command

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

webserver.keep_alive()
bot.run(DISCORD_TOKEN, log_handler=handler, log_level=logging.DEBUG)
