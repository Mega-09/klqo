import os

try:
    import discord
    from discord import app_commands
    from discord.ext import commands
except:
    os.system("pip3 install discord")
    import discord
    from discord import app_commands
    from discord.ext import commands





#-------------------------------------VIEWS-------------------------------------

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

class Verify(discord.ui.View):
    def __init__(self, user) -> None:
        self.user = user
        super().__init__(timeout=None)
    
    @discord.ui.button(label="✔", style=discord.ButtonStyle.green, custom_id="approve_btn")
    async def verify(self, interaction: discord.Interaction, button):
        await self.user.remove_roles(interaction.guild.get_role(1164961874664759417))
        await self.user.remove_roles(interaction.guild.get_role(1164965032954712134))
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
    rblx_user = discord.ui.TextInput(label='User Link', min_length=30, max_length=100, placeholder="Input your Roblox User Link")
    users = discord.ui.TextInput(label='Users in war', placeholder="Input all the players that are with you", required=False)
    notes = discord.ui.TextInput(label='Notes', min_length=0, max_length=100, placeholder="For example: Henry/Spencer and important things", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        channel = bot.get_channel(1164960999758114958)
        channel_markitus = bot.get_channel(1236707714814447628)
        embed = discord.Embed(title=f"`{interaction.user.name}` made a Call", color=discord.Colour.yellow())
        embed.add_field(name="User Link:", value=f'{self.rblx_user.value}\n**Users:** `{self.users}`\n**Notes:** `{self.notes}`')
        await channel.send("<@&1164958057667760298>",embed=embed)
        await channel_markitus.send("<@&1164958057667760298>",embed=embed)
        await interaction.user.add_roles(interaction.guild.get_role(1164965032954712134))
        embed = discord.Embed(title="Your call has been made successfully.", color=discord.Colour.green())
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
        print(f"Logging in as: {self.user}")

intents = discord.Intents.default()
intents.message_content = True
bot = MyBot(command_prefix="-", description='Bot for the Spanish Demae Channnel. Based on discord.py', intents = intents)

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game(name="𝕸𝖚𝖊𝖗𝖙𝖔 𝖔𝖗 𝖛𝖎𝖛𝖔"))
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
async def ticket_embed(ctx):
    if ctx.author.guild_permissions.administrator == True:
        embed = discord.Embed(title="Verify yourself", color=discord.Colour.yellow())
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1141400786304241704/1164998096552464484/Muerto_or_Vivo.png?ex=65454006&is=6532cb06&hm=676768a124ce67ac008dcd3626c7a53cded7a7a9f488b333f5cd791a9f9d5d49&")
        embed.add_field(name="Join our faction", value='To verify, you have to make a request answering some questions. Your answers will be checked by a moderator and they will be accepted if all the info is correct. If they are declined, you will be DMed by the bot')
        embed.set_footer(text="IMPORTANT: Please note that you can't send a request if you already have an active one. You'll have to wait until your request is declined if you made any mistakes.")
        view = Register()
        await ctx.send(embed=embed, view=view)

@bot.command()
async def call_embed(ctx):
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

bot.run(TOKEN)
