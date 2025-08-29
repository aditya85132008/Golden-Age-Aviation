import discord
from discord.ext import commands
from discord.ui import Button, View
from datetime import timedelta
import logging
from dotenv import load_dotenv
import os
import webserver
import requests

load_dotenv()
token = os.getenv('DISCORD_TOKEN')
VERIFY_CHANNEL_ID = 1410464974152794212
VERIFICATION_ROLE_ID = 1410459198042411070

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)
ranks= "Cadet"
VERIFICATION_ROLE_NAME="Verified"

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
@bot.command()
@commands.has_permissions(administrator=True)
async def setupverify(ctx):
    """Send or update the verification embed (prevents duplicates)."""
    channel = bot.get_channel(VERIFICATION_CHANNEL_ID)
    role = ctx.guild.get_role(VERIFICATION_ROLE_ID)

    embed = discord.Embed(
        title="✅ Verification",
        description="Click the button below to verify and gain access!",
        color=discord.Color.gold()
    )

    view = discord.ui.View()
    button = discord.ui.Button(label="Verify", style=discord.ButtonStyle.success)

    async def button_callback(interaction):
        if role not in interaction.user.roles:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("🎉 You are now verified!", ephemeral=True)
        else:
            await interaction.response.send_message("⚡ You are already verified.", ephemeral=True)

    button.callback = button_callback
    view.add_item(button)

    # Check for existing verification message
    async for message in channel.history(limit=50):  # scan last 50 messages
        if message.author == bot.user and message.embeds:
            if "Verification" in message.embeds[0].title:
                await message.edit(embed=embed, view=view)
                await ctx.send("♻️ Updated existing verification message.")
                return

    # If no existing message found, send a new one
    await channel.send(embed=embed, view=view)
    await ctx.send("✅ Verification embed has been posted!")

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
@bot.command()
async def poll(ctx, *, question):
    embed = discord.Embed(title="New Poll", description=question)
    poll_message = await ctx.send(embed=embed)
    await poll_message.add_reaction("👍")
    await poll_message.add_reaction("👎")          

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

webserver.keep_alive()
bot.run(token, log_handler=handler, log_level=logging.DEBUG)




