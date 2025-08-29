import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import webserver
import requests

load_dotenv()
token = os.getenv('DISCORD_TOKEN')


handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)
ranks= "Cadet"

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

#Verification
# Custom persistent view with Verify button
class VerifyView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✅ Verify", style=discord.ButtonStyle.success, custom_id="verify_button")
    async def verify_button(self, interaction: discord.Interaction, button: Button):
        role = discord.utils.get(interaction.guild.roles, name=VERIFICATION_ROLE_NAME)
        if role is None:
            await interaction.response.send_message("❌ Verification role not found! Please ask an admin.", ephemeral=True)
            return

        if role in interaction.user.roles:
            await interaction.response.send_message("⚠️ You are already verified!", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("✅ You have been verified!", ephemeral=True)

# Command to set up verification in a chosen channel
@bot.command()
@commands.has_permissions(administrator=True)
async def setupverify(ctx, channel: discord.TextChannel):
    embed = discord.Embed(
        title="🔒 Server Verification",
        description="Click the **✅ Verify** button below to gain access to the server.",
        color=discord.Color.green()
    )
    await channel.send(embed=embed, view=VerifyView())
    await ctx.send(f"✅ Verification system has been set up in {channel.mention}", delete_after=5)

# When the bot is ready
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    # Register persistent view (keeps buttons alive after restart)
    bot.add_view(VerifyView())

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

webserver.keep_alive()
bot.run(token, log_handler=handler, log_level=logging.DEBUG)








