import os
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button
import yt_dlp
import asyncio
import requests
import aiohttp
import json
import urllib.parse
from pathlib import Path

import time
from pathlib import Path

HEARTBEAT_FILE = Path("/var/lib/service-status/discord-bot")

HEARTBEAT_INTERVAL = 15


async def heartbeat_loop():

    HEARTBEAT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    while not bot.is_closed():

        if bot.is_ready():

            try:
                HEARTBEAT_FILE.touch(
                    exist_ok=True
                )

            except Exception as error:
                print(
                    f"[HEARTBEAT] Error: {error}"
                )

        await asyncio.sleep(
            HEARTBEAT_INTERVAL
        )

# -------------------------
#   YTDLP CONFIG
# -------------------------
ytdlp_opts = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
}


def extract_source(query: str):
    """Returns a playable audio URL for YouTube or Spotify."""
    with yt_dlp.YoutubeDL(ytdlp_opts) as ydl:
        info = ydl.extract_info(query, download=False)

        # If it's a playlist
        if "entries" in info:
            return [entry["url"] for entry in info["entries"] if entry]

        # Single track
        return info["url"]

async def play_autocomplete(interaction, current: str):
    if not current:
        return []

    try:
        query = urllib.parse.quote(current)
        url = f"http://suggestqueries.google.com/complete/search?client=firefox&ds=yt&q={query}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                text = await resp.text()

        # YouTube suggestions come as: ["query", ["suggestion1","suggestion2",...]]
        suggestions = json.loads(text)[1]

        return [
            app_commands.Choice(name=s[:100], value=s)
            for s in suggestions[:5]
        ]

    except Exception as e:
        print("AUTOCOMPLETE ERROR:", e)
        return []

async def yt_search(query: str):
    if not query:
        return []

    opts = {
        "quiet": True,
        "skip_download": True,
        "default_search": "ytsearch5",
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            data = ydl.extract_info(query, download=False)
            entries = data.get("entries", [])
            return [entry.get("title") for entry in entries if entry.get("title")]
    except Exception:
        return []
# -------------------------
#   MUSIC QUEUE SYSTEM
# -------------------------

class Song:
    def __init__(self, title, url):
        self.title = title
        self.url = url


class MusicQueue:
    def __init__(self):
        self.songs = []
        self.now_playing = None
        self.history = []         # ⬅ added
        self.repeat_mode = "all"  # off, current, all
        self.is_paused = False

    def add_song(self, song):
        self.songs.append(song)

    def get_next_song(self):
        # Handle repeat-current
        if self.repeat_mode == "current" and self.now_playing:
            return self.now_playing

        # Save current to history before moving on
        if self.now_playing:
            self.history.append(self.now_playing)

        # Normal next-song behavior
        if self.songs:
            next_song = self.songs.pop(0)

            # Handle repeat-queue mode
            if self.repeat_mode == "all" and self.now_playing:
                self.songs.append(self.now_playing)

            return next_song

        return None

    def get_previous_song(self):
        if not self.history:
            return None
        return self.history.pop()  # Last played


queues = {}


def get_queue(gid: int):
    if gid not in queues:
        queues[gid] = MusicQueue()
    return queues[gid]


def get_queue(guild_id: int):
    if guild_id not in queues:
        queues[guild_id] = MusicQueue()
    return queues[guild_id]


async def play_next(interaction: discord.Interaction):
    """Plays the next track in queue."""
    vc = interaction.guild.voice_client
    queue = get_queue(interaction.guild_id)

    if not vc or not queue.queue:
        queue.playing = False
        return

    url = queue.pop()
    source = discord.FFmpegPCMAudio(url, options="-vn")

    def after_play(err):
        asyncio.run_coroutine_threadsafe(play_next(interaction), bot.loop)

    vc.play(source, after=after_play)
    queue.playing = True

#-------------------------------------VIEWS-------------------------------------

#-----MUSIC-----

class MusicControls(View):
    def __init__(self, interaction, queue):
        super().__init__(timeout=None)
        self.interaction = interaction
        self.queue = queue

    @discord.ui.button(label="⏯ Pause/Resume", style=discord.ButtonStyle.blurple)
    async def pause_button(self, interaction: discord.Interaction, button: Button):
        vc = interaction.guild.voice_client
        if not vc:
            return

        if vc.is_paused():
            vc.resume()
            self.queue.is_paused = False
            await interaction.response.send_message("▶ Resumed", ephemeral=True)
        else:
            vc.pause()
            self.queue.is_paused = True
            await interaction.response.send_message("⏸️ Paused", ephemeral=True)

    @discord.ui.button(label="⏭ Skip", style=discord.ButtonStyle.green)
    async def skip_button(self, interaction: discord.Interaction, button: Button):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
        await interaction.response.send_message("⏩ Skipped", ephemeral=True)

    @discord.ui.button(label="⏹ Stop", style=discord.ButtonStyle.red)
    async def stop_button(self, interaction: discord.Interaction, button: Button):
        vc = interaction.guild.voice_client
        queue = get_queue(interaction.guild_id)
        queue.songs.clear()
        queue.now_playing = None
        if vc:
            vc.stop()
            await vc.disconnect()
        await interaction.response.send_message("🛑 Stopped and cleared queue", ephemeral=True)
    
    @discord.ui.button(label="⏮ Previous", style=discord.ButtonStyle.gray)
    async def previous_button(self, interaction: discord.Interaction, button: Button):
        vc = interaction.guild.voice_client

        if not vc:
            return await interaction.response.send_message("❌ No active voice connection.", ephemeral=True)

        prev = self.queue.get_previous_song()

        if not prev:
            return await interaction.response.send_message("⛔ No previous track.", ephemeral=True)

        # Play the previous track
        self.queue.now_playing = prev

        ffmpeg_opts = {"options": "-vn"}
        vc.stop()
        vc.play(discord.FFmpegPCMAudio(prev.url, **ffmpeg_opts))

        embed = discord.Embed(
            title="⏮ Playing Previous Track",
            description=f"**{prev.title}**",
            color=discord.Color.orange()
        )

        await interaction.response.send_message(embed=embed, ephemeral=False)    

#-----REGISTERING-----
class Register(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)
    
    @discord.ui.button(label = "Join Faction", style=discord.ButtonStyle.green, custom_id="register_button")
    async def register(self, interaction: discord.Interaction, button):
        if interaction.user.get_role(1164965032954712134) == None:
            await interaction.response.send_modal(ModalRegister())
        else:
            await interaction.response.send_message("You already have an active request!", ephemeral=True)
    
    @discord.ui.button(label = "Join as Ally", style=discord.ButtonStyle.blurple, custom_id="register_ally_button")
    async def register_ally(self, interaction: discord.Interaction, button):
        if interaction.user.get_role(1164965032954712134) == None:
            await interaction.response.send_modal(ModalAlly())
        else:
            await interaction.response.send_message("You already have an active request!", ephemeral=True)

class AlliesSelect(discord.ui.Select):
    def __init__(self, user) -> None:
        self.user = user
        options = [
            discord.SelectOption(label="PDA", description="Pinkerton Detective Agency")
        ]
        super().__init__(placeholder="Select Ally", options=options, min_values=1, max_values=1)
    
    async def callback(self, interaction:discord.Interaction):
        await self.user.remove_roles(interaction.guild.get_role(1164961874664759417))
        await self.user.remove_roles(interaction.guild.get_role(1164965032954712134))
        await self.user.remove_roles(interaction.guild.get_role(1347264187960791154))
        await self.user.add_roles(interaction.guild.get_role(1165656634006179980))
        await interaction.user.edit(nick=f'{interaction.user.display_name} ({self.values[0]})')
        view = VerifyAlly(user=self.user)
        view.deny.disabled = True
        await interaction.message.edit(view=view)
        await interaction.response.send_message(f"`{self.user} was verified`", ephemeral=True)

class VerifyAlly(discord.ui.View):
    def __init__(self, user) -> None:
        self.user = user
        super().__init__(timeout=None)
        
    @discord.ui.button(label="✔", style=discord.ButtonStyle.green, custom_id="ally_approve_btn")
    async def verify(self, interaction: discord.Interaction, button):
        await interaction.response.send_modal(ModalAcceptAlly(user=self.user))

    @discord.ui.button(label="✘", style=discord.ButtonStyle.red, custom_id="deny_btn")
    async def deny(self, interaction: discord.Interaction, button):
        await interaction.response.send_modal(ModalDecline(user=self.user))

class Verify(discord.ui.View):
    def __init__(self, user) -> None:
        self.user = user
        super().__init__(timeout=None)
    
    @discord.ui.button(label="✔", style=discord.ButtonStyle.green, custom_id="approve_btn")
    async def verify(self, interaction: discord.Interaction, button):
        await self.user.remove_roles(interaction.guild.get_role(1164961874664759417))
        await self.user.remove_roles(interaction.guild.get_role(1164965032954712134))
        await self.user.remove_roles(interaction.guild.get_role(1347264187960791154))
        await self.user.add_roles(interaction.guild.get_role(1164956281283563576))
        view = Verify(user=interaction.user)
        view.verify.disabled = True
        view.deny.disabled = True
        await interaction.message.edit(view=view)
        await interaction.response.send_message(f"`{self.user} was verified`", ephemeral=True)

    @discord.ui.button(label="✘", style=discord.ButtonStyle.red, custom_id="deny_btn")
    async def deny(self, interaction: discord.Interaction, button):
        await interaction.response.send_modal(ModalDecline(user=self.user))

#-----CALLS-----

class Call(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)
    
    @discord.ui.button(label = "Make a Call", style=discord.ButtonStyle.green, custom_id="call_button")
    async def call(self, interaction: discord.Interaction, button):
        await interaction.response.send_modal(ModalCall())

#-------------------------------------MODALS-------------------------------------------

class ModalAcceptAlly(discord.ui.Modal, title='Accept Ally'):
    def __init__(self, user) -> None:
        super().__init__(timeout=None)
        self.user = user

    reason = discord.ui.TextInput(label='Reason', max_length=100, placeholder="Enter the decline reason")

    async def on_submit(self, interaction: discord.Interaction):
        await self.user.remove_roles(interaction.guild.get_role(1164961874664759417))
        await self.user.remove_roles(interaction.guild.get_role(1164965032954712134))
        await self.user.remove_roles(interaction.guild.get_role(1347264187960791154))
        await self.user.add_roles(interaction.guild.get_role(1165656634006179980))
        await interaction.user.edit(nick=f'{interaction.user.display_name} ({self.reason})')
        view = Verify(user=interaction.user)
        view.verify.disabled = True
        view.deny.disabled = True
        await interaction.message.edit(view=view)
        await interaction.response.send_message(f"`{self.user} was verified`", ephemeral=True)

class ModalDecline(discord.ui.Modal, title='Decline'):
    def __init__(self, user) -> None:
        super().__init__(timeout=None)
        self.user = user

    reason = discord.ui.TextInput(label='Reason', max_length=100, placeholder="Enter the decline reason")

    async def on_submit(self, interaction: discord.Interaction):
        await self.user.remove_roles(interaction.guild.get_role(1164965032954712134))
        channel = await self.user.create_dm()
        await channel.send(f"Your request was declined! Reason of decline: ```{self.reason}``` You can now send a new request.")
        await interaction.message.delete()
        await interaction.response.send_message(f"`{self.user}` was declined. Reason: ```{self.reason}```")


class ModalCall(discord.ui.Modal, title='Make a call'):
    users = discord.ui.TextInput(label='Users in war', placeholder="Input all the players that are with you", required=False)
    notes = discord.ui.TextInput(label='Notes', min_length=0, max_length=100, placeholder="For example: Henry/Spencer and important things", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        rblxID = requests.get(f'https://api.blox.link/v4/public/guilds/{interaction.guild_id}/discord-to-roblox/{interaction.user.id}',  headers={"Authorization" : "554127d8-47f7-4aa7-addb-683b78907672"}).json()["robloxID"]
        rblx_link = f"https://www.roblox.com/users/{rblxID}/profile"        
        channel = bot.get_channel(1164960999758114958)
        embed = discord.Embed(title=f"`{interaction.user.name}` made a Call, join them NOW!", color=discord.Colour.yellow())
        embed.add_field(name="User link:", value=f'{rblx_link}\n**Users:** `{self.users}`\n**Notes:** `{self.notes}`')
        await channel.send("<@&1164958057667760298>",embed=embed)
        await interaction.user.add_roles(interaction.guild.get_role(1164965032954712134))
        embed = discord.Embed(title="Your call has been made successfully.", color=discord.Colour.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)

class ModalAlly(discord.ui.Modal, title='Send join as Ally request'):
    rblx_user = discord.ui.TextInput(label='Roblox User', min_length=4, max_length=20, placeholder="Input your Roblox User")
    factions = discord.ui.TextInput(label='Ally Faction', placeholder='Input what your ally faction is')

    async def on_submit(self, interaction: discord.Interaction):
        channel = bot.get_channel(1353103182263353405)
        embed = discord.Embed(title=f"Request by: `{interaction.user.name}` ({interaction.user.id})", color=discord.Colour.yellow())
        embed.add_field(name="Questions:", value=f'**Roblox User:** `{self.rblx_user.value}`\n**Previous factions:** `{self.factions.value}`')
        view = VerifyAlly(user=interaction.user)
        await channel.send("<@&1164956281304526875>",embed=embed, view=view)
        await interaction.user.add_roles(interaction.guild.get_role(1164965032954712134))
        embed = discord.Embed(title="Your verification request has been made succesfully", color=discord.Colour.green())
        embed.add_field(name="And now what?", value="Your request will be checked by a moderator and it will be accepted if all the info is correct. If it is declined, you will be DMed by the bot")
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1043184831066034189/1165218669006176316/mikeohearnfuertudo.png?ex=65460d73&is=65339873&hm=08b97f596cf581bf2b62cecc993cb95294a9646c2910976e5f7cdbd308acf35a&")
        await interaction.response.send_message(embed=embed, ephemeral=True)

class ModalRegister(discord.ui.Modal, title='Send join request'):
    rblx_user = discord.ui.TextInput(label='Roblox User', min_length=4, max_length=20, placeholder="Input your Roblox User")
    factions = discord.ui.TextInput(label='Previous factions', placeholder='Input "None" if this is your first faction')
    guns = discord.ui.TextInput(label='Most used guns', min_length=3, placeholder='For example. "Martini Henry, Patterson, etc."')

    async def on_submit(self, interaction: discord.Interaction):
        channel = bot.get_channel(1165240669133086781)
        embed = discord.Embed(title=f"Request by: `{interaction.user.name}` ({interaction.user.id})", color=discord.Colour.yellow())
        embed.add_field(name="Questions:", value=f'**Roblox User:** `{self.rblx_user.value}`\n**Previous factions:** `{self.factions.value}`\n**Guns used:** `{self.guns.value}`\n')
        view = Verify(user=interaction.user)
        await channel.send("<@&1164956281304526875>",embed=embed, view=view)
        await interaction.user.add_roles(interaction.guild.get_role(1164965032954712134))
        embed = discord.Embed(title="Your verification request has been made succesfully", color=discord.Colour.green())
        embed.add_field(name="And now what?", value="Your request will be checked by a moderator and it will be accepted if all the info is correct. If it is declined, you will be DMed by the bot")
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1043184831066034189/1165218669006176316/mikeohearnfuertudo.png?ex=65460d73&is=65339873&hm=08b97f596cf581bf2b62cecc993cb95294a9646c2910976e5f7cdbd308acf35a&")
        await interaction.response.send_message(embed=embed, ephemeral=True)

class MyBot(commands.Bot):
    # overriding setup_hook and doing our stuff in it
    async def setup_hook(self):
        bot.add_view(Register())
        bot.add_view(Call())
        self.heartbeat_task = asyncio.create_task(
        heartbeat_loop()
        )
        print(f"Logging in as: {self.user}")

intents = discord.Intents.default()
intents.message_content = True
bot = MyBot(command_prefix="-", description='Bot for MUERTO OR VIVO. Based on discord.py', intents = intents)

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game(name="𝕸𝖚𝖊𝖗𝖙𝖔 𝖔𝖗 𝓥𝖎𝖛𝖔"))

    print("I'm ready sir.")

@bot.command()
async def sync(ctx):
    print("Im prompted to sync.")
    if ctx.author.id == 493092513737867274:
        try: 
            sync = await ctx.send("Trying to sync...")
            await bot.tree.sync()
            await sync.edit(content="Synced!")
            print("Synced!")
        except: await ctx.send("Could not sync fuck you")
    else:
        print("bro has no admin and tries to sync lol")

@bot.command()
async def ticket_thing(ctx):
    if ctx.author.guild_permissions.administrator == True:
        embed = discord.Embed(title="Verify yourself", color=discord.Colour.yellow())
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1141400786304241704/1164998096552464484/Muerto_or_Vivo.png?ex=65454006&is=6532cb06&hm=676768a124ce67ac008dcd3626c7a53cded7a7a9f488b333f5cd791a9f9d5d49&")
        embed.add_field(name="Join our faction", value='To verify, you have to make a request answering some questions. Your answers will be checked by a moderator and they will be accepted if all the info is correct. If they are declined, you will be DMed by the bot\nThe bot does not work depending on the Time, since its hosted on the owners PC. DM Mega for help.')
        embed.set_footer(text="IMPORTANT: Please note that you can't send a request if you already have an active one. You'll have to wait until your request is declined if you made any mistakes.")
        view = Register()
        await ctx.send(embed=embed, view=view)

@bot.command()
async def llamada_thing(ctx):
    if ctx.author.guild_permissions.administrator == True:
        embed = discord.Embed(title="Make a Call", color=discord.Colour.yellow())
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1141400786304241704/1164998096552464484/Muerto_or_Vivo.png?ex=65454006&is=6532cb06&hm=676768a124ce67ac008dcd3626c7a53cded7a7a9f488b333f5cd791a9f9d5d49&")
        embed.add_field(name="Make a Call", value='Make a call so people support you in war / raid')
        view = Call()
        await ctx.send(embed=embed, view=view)

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(error, ephemeral = True)
    else: raise error

# -------------------------
#   SLASH COMMANDS
# -------------------------

@bot.tree.command(name="join", description="Bot joins your voice channel.")
async def join(interaction: discord.Interaction):
    if not interaction.user.voice:
        return await interaction.response.send_message("You need to be in a VC.", ephemeral=True)

    channel = interaction.user.voice.channel
    await channel.connect(self_deaf=True)
    await interaction.response.send_message("Joined & deafened.")

@bot.tree.command(name="play", description="Play a song by URL or search term")
@app_commands.autocomplete(query=play_autocomplete)
@app_commands.describe(query="Song name or URL")
async def play(interaction: discord.Interaction, query: str):

    await interaction.response.defer()

    queue = get_queue(interaction.guild_id)

    # Connect to VC if not already
    if not interaction.user.voice:
        return await interaction.followup.send("❌ You must be in a voice channel!")

    voice_channel = interaction.user.voice.channel
    vc = interaction.guild.voice_client

    if not vc:
        vc = await voice_channel.connect()

    from yt_dlp import YoutubeDL
    import re

    def is_url(text: str):
        return re.match(r'https://', text.strip()) is not None

    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'default_search': 'ytsearch',
    }

    with YoutubeDL(ydl_opts) as ydl:
        search_term = query.strip()
        if is_url(search_term):
            info = ydl.extract_info(search_term, download=False)
        else:
            info = ydl.extract_info(f"ytsearch:{search_term}", download=False)
            if 'entries' in info:
                info = info['entries'][0]
    url = info["url"]
    title = info["title"]

    song = Song(title, url)
    queue.add_song(song)

    # Send embed showing added song
    embed = discord.Embed(
        title="🎵 Added to Queue",
        description=f"**{title}**",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=f"https://img.youtube.com/vi/{info['id']}/0.jpg")

    await interaction.followup.send(embed=embed)

    # If nothing is playing, start playback
    if not vc.is_playing():

        async def play_next(_):
            next_song = queue.get_next_song()
            if next_song:
                queue.now_playing = next_song
                ffmpeg_opts = {"options": "-vn"}
                vc.play(discord.FFmpegPCMAudio(next_song.url, **ffmpeg_opts), after=play_next)
                
                # Show "Now Playing" embed with controls
                now_embed = discord.Embed(
                    title="🎶 Now Playing",
                    description=f"**{next_song.title}**",
                    color=discord.Color.green()
                )
                await interaction.followup.send(embed=now_embed, view=MusicControls(interaction, queue))

        await play_next(None)

@bot.tree.command(name="queue", description="Show the current queue")
async def queue_cmd(interaction: discord.Interaction):
    queue = get_queue(interaction.guild_id)

    if not queue.songs and not queue.now_playing:
        return await interaction.response.send_message("📭 Queue is empty!")

    embed = discord.Embed(title="🎵 Current Queue", color=discord.Color.purple())

    if queue.now_playing:
        embed.add_field(name="▶ Now Playing", value=f"**{queue.now_playing.title}**", inline=False)

    if queue.songs:
        desc = "\n".join([f"**{i+1}.** {song.title}" for i, song in enumerate(queue.songs)])
        embed.add_field(name="📄 Upcoming", value=desc, inline=False)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="skip", description="Skip the current song.")
async def skip(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if not vc or not vc.is_playing():
        return await interaction.response.send_message("Nothing is playing.", ephemeral=True)

    vc.stop()
    await interaction.response.send_message("Skipped.")

@bot.tree.command(name="stop", description="Stop the music and clear the queue")
async def stop(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    queue = get_queue(interaction.guild_id)

    queue.songs.clear()
    queue.now_playing = None

    if vc:
        vc.stop()
        await vc.disconnect()

    await interaction.response.send_message("🛑 Stopped and cleared queue.")

bot.run('TOKEN')
