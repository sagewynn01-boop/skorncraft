import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv
import asyncio
from datetime import datetime, timedelta

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Store pending requests (in production, use a database)
pending_requests = {}

# Channel mapping for professions
PROFESSION_CHANNELS = {
    'blacksmith': int(os.getenv('BLACKSMITH_CHANNEL')),
    'tailor': int(os.getenv('TAILOR_CHANNEL')),
    'alchemist': int(os.getenv('ALCHEMIST_CHANNEL')),
    'enchanter': int(os.getenv('ENCHANTER_CHANNEL')),
    'leatherworker': int(os.getenv('LEATHERWORKER_CHANNEL')),
    'engineer': int(os.getenv('ENGINEER_CHANNEL')),
    'jewelcrafter': int(os.getenv('JEWELCRAFTER_CHANNEL')),
    'inscriptionist': int(os.getenv('INSCRIPTIONIST_CHANNEL')),
}

@tasks.loop(hours=24)
async def cleanup_old_messages():
    """Delete messages older than 30 days from profession channels."""
    for profession, channel_id in PROFESSION_CHANNELS.items():
        try:
            channel = await bot.fetch_channel(channel_id)
            now = datetime.utcnow()
            thirty_days_ago = now - timedelta(days=30)
            
            deleted_count = 0
            async for message in channel.history(oldest_first=True, limit=None):
                if message.created_at < thirty_days_ago:
                    try:
                        await message.delete()
                        deleted_count += 1
                    except discord.errors.Forbidden:
                        print(f'Permission denied deleting message in {profession} channel')
                        break
                    except discord.errors.NotFound:
                        pass  # Message already deleted
                else:
                    # Stop when we reach recent messages
                    break
            
            if deleted_count > 0:
                print(f'Cleaned up {deleted_count} old message(s) from {profession} channel')
        except Exception as e:
            print(f'Error cleaning up {profession} channel: {e}')

@cleanup_old_messages.before_loop
async def before_cleanup():
    await bot.wait_until_ready()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} command(s)')
    except Exception as e:
        print(e)
    if not cleanup_old_messages.is_running():
        cleanup_old_messages.start()

@bot.tree.command(name='craft', description='Request a crafting order')
async def craft(interaction: discord.Interaction):
    # Check if user is in a guild
    if interaction.guild is None:
        await interaction.response.send_message('This command can only be used in a server.', ephemeral=True)
        return

    # Create select menu for profession
    professions = [
        discord.SelectOption(label='Blacksmith', value='blacksmith'),
        discord.SelectOption(label='Tailor', value='tailor'),
        discord.SelectOption(label='Alchemist', value='alchemist'),
        discord.SelectOption(label='Enchanter', value='enchanter'),
        discord.SelectOption(label='Leatherworker', value='leatherworker'),
        discord.SelectOption(label='Engineer', value='engineer'),
        discord.SelectOption(label='Jewelcrafter', value='jewelcrafter'),
        discord.SelectOption(label='Inscriptionist', value='inscriptionist'),
    ]

    select = discord.ui.Select(placeholder='Choose a profession', options=professions)

    view = CraftView(select, interaction.user, interaction.guild)
    await interaction.user.send('Please select the profession for your crafting request:', view=view)
    await interaction.response.send_message('Check your DMs to continue with your crafting request.', ephemeral=True)

class CraftView(discord.ui.View):
    def __init__(self, select, user, guild):
        super().__init__(timeout=300)  # 5 minutes
        self.user = user
        self.guild = guild
        self.profession = None
        self.add_item(select)
        select.callback = self.select_callback

    async def select_callback(self, interaction: discord.Interaction):
        self.profession = interaction.data['values'][0]
        await interaction.response.send_message(f'Selected profession: {self.profession.capitalize()}\n\nPlease type your character name:')

        # Wait for character name
        def check(m):
            return m.author == self.user and isinstance(m.channel, discord.DMChannel)

        try:
            msg = await bot.wait_for('message', check=check, timeout=300.0)
            self.character_name = msg.content

            await self.user.send(f'Character name: {self.character_name}\n\nPlease type the item name you want crafted:')

            # Wait for item name
            msg2 = await bot.wait_for('message', check=check, timeout=300.0)
            self.item_name = msg2.content

            # Now post to channel
            await self.post_request()

        except asyncio.TimeoutError:
            await self.user.send('Request timed out. Please try again.')

    async def post_request(self):
        # Get the channel ID from mapping
        channel_id = PROFESSION_CHANNELS.get(self.profession)
        
        if not channel_id:
            await self.user.send(f'No channel configured for {self.profession}.')
            return
        
        try:
            channel = await bot.fetch_channel(channel_id)
        except discord.NotFound:
            await self.user.send(f'Channel for {self.profession} not found. Please contact an admin.')
            return

        # Find the role
        role = discord.utils.get(self.guild.roles, name=self.profession.capitalize())

        # Create embed
        embed = discord.Embed(title='New Crafting Request', color=0x00ff00)
        embed.add_field(name='Profession', value=self.profession.capitalize(), inline=True)
        embed.add_field(name='Character', value=self.character_name, inline=True)
        embed.add_field(name='Item', value=self.item_name, inline=True)
        embed.add_field(name='Requested by', value=self.user.mention, inline=False)

        # Add claim button
        view = ClaimView(self.user.id, self.profession, self.character_name, self.item_name)
        message = await channel.send(f'{role.mention if role else ""} New crafting request:', embed=embed, view=view)

        # Store the request
        request_id = f'{self.user.id}_{message.id}'
        pending_requests[request_id] = {
            'user': self.user,
            'profession': self.profession,
            'character': self.character_name,
            'item': self.item_name,
            'message': message,
            'channel': channel
        }

        await self.user.send('Your request has been posted!')

class ClaimView(discord.ui.View):
    def __init__(self, requester_id, profession, character, item):
        super().__init__(timeout=None)
        self.requester_id = requester_id
        self.profession = profession
        self.character = character
        self.item = item

    @discord.ui.button(label='Claim', style=discord.ButtonStyle.primary)
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if user has the role
        role = discord.utils.get(interaction.guild.roles, name=self.profession.capitalize())
        if role not in interaction.user.roles:
            await interaction.response.send_message('You do not have the required role to claim this order.', ephemeral=True)
            return

        # Disable button
        button.disabled = True
        await interaction.message.edit(view=self)

        # Post claim notice
        embed = interaction.message.embeds[0]
        embed.add_field(name='Claimed by', value=interaction.user.mention, inline=False)
        await interaction.message.edit(embed=embed)

        await interaction.response.send_message('You have claimed this order!', ephemeral=True)

        # Add complete button
        complete_view = CompleteView(self.requester_id, interaction.user.id, self.profession, self.character, self.item, interaction.message)
        await interaction.message.edit(view=complete_view)

class CompleteView(discord.ui.View):
    def __init__(self, requester_id, crafter_id, profession, character, item, message):
        super().__init__(timeout=None)
        self.requester_id = requester_id
        self.crafter_id = crafter_id
        self.profession = profession
        self.character = character
        self.item = item
        self.message = message

    @discord.ui.button(label='Complete', style=discord.ButtonStyle.success)
    async def complete(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if the crafter is completing
        if interaction.user.id != self.crafter_id:
            await interaction.response.send_message('Only the crafter can mark this as complete.', ephemeral=True)
            return

        # Disable button
        button.disabled = True
        await interaction.message.edit(view=self)

        # Update embed
        embed = interaction.message.embeds[0]
        embed.add_field(name='Status', value='Completed', inline=False)
        await interaction.message.edit(embed=embed)

        # DM the requester
        requester = interaction.guild.get_member(self.requester_id)
        if requester:
            try:
                await requester.send(f'Your crafting request for {self.item} ({self.character}) has been completed by {interaction.user.display_name}!')
            except:
                pass  # User might have DMs disabled

        # Post in channel
        await interaction.response.send_message(f'Order completed! {requester.mention if requester else "Requester"} has been notified.')

bot.run(TOKEN)
