import discord
from discord import app_commands
from discord.ext import commands
import json
import os

# ---------- Configuration ----------
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guilds = True
intents.members = True

TARGETS_FILE = "targets.json"
# -----------------------------------

class DeleteBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.synced = False  # for syncing slash commands

    async def setup_hook(self):
        # Sync commands on startup
        if not self.synced:
            await self.tree.sync()
            self.synced = True
            print("Slash commands synced.")

bot = DeleteBot()

# -------- Data persistence ---------
def load_targets():
    if not os.path.exists(TARGETS_FILE):
        return {}
    with open(TARGETS_FILE, "r") as f:
        try:
            return json.load(f)
        except:
            return {}

def save_targets(data):
    with open(TARGETS_FILE, "w") as f:
        json.dump(data, f)

# Structure: { "<guild_id>": { "<channel_id>": [<user_id>, ...] } }
targets = load_targets()

def add_target(guild_id: str, channel_id: str, user_id: str):
    guild = targets.setdefault(guild_id, {})
    users = guild.setdefault(channel_id, [])
    if user_id not in users:
        users.append(user_id)
    save_targets(targets)

def remove_target(guild_id: str, channel_id: str, user_id: str):
    if guild_id in targets and channel_id in targets[guild_id]:
        try:
            targets[guild_id][channel_id].remove(user_id)
        except ValueError:
            pass
        if not targets[guild_id][channel_id]:
            del targets[guild_id][channel_id]
        if not targets[guild_id]:
            del targets[guild_id]
        save_targets(targets)
# -----------------------------------

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

# Permission check helper
def staff_only(interaction: discord.Interaction) -> bool:
    return interaction.user.guild_permissions.manage_messages

# ---------- Slash Commands ----------
@bot.tree.command(name="target", description="Auto-delete messages from a member in a channel.")
async def target(interaction: discord.Interaction, member: discord.Member, channel: discord.TextChannel):
    if not staff_only(interaction):
        await interaction.response.send_message("🚫 You need Manage Messages permission.", ephemeral=True)
        return
    add_target(str(interaction.guild.id), str(channel.id), str(member.id))
    await interaction.response.send_message(f"✅ Now deleting messages from {member.mention} in {channel.mention}.")

@bot.tree.command(name="untarget", description="Stop auto-deleting messages from a member in a channel.")
async def untarget(interaction: discord.Interaction, member: discord.Member, channel: discord.TextChannel):
    if not staff_only(interaction):
        await interaction.response.send_message("🚫 You need Manage Messages permission.", ephemeral=True)
        return
    remove_target(str(interaction.guild.id), str(channel.id), str(member.id))
    await interaction.response.send_message(f"🛑 Stopped deleting messages from {member.mention} in {channel.mention}.")

@bot.tree.command(name="listtargets", description="List all active targets in this server.")
async def listtargets(interaction: discord.Interaction):
    if not staff_only(interaction):
        await interaction.response.send_message("🚫 You need Manage Messages permission.", ephemeral=True)
        return

    guild_targets = targets.get(str(interaction.guild.id), {})
    if not guild_targets:
        await interaction.response.send_message("No active targets set for this server.")
        return

    lines = []
    for ch_id, users in guild_targets.items():
        ch = interaction.guild.get_channel(int(ch_id))
        ch_name = ch.mention if ch else f"<deleted channel {ch_id}>"
        user_mentions = []
        for u in users:
            mem = interaction.guild.get_member(int(u))
            if mem:
                user_mentions.append(mem.mention)
            else:
                user_mentions.append(f"<deleted user {u}>")
        lines.append(f"{ch_name}: {', '.join(user_mentions)}")
    await interaction.response.send_message("\n".join(lines))
# -----------------------------------

# ---------- Message Deletion ----------
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    guild_id = str(message.guild.id)
    ch_id = str(message.channel.id)
    author_id = str(message.author.id)

    guild_targets = targets.get(guild_id, {})
    users_in_channel = guild_targets.get(ch_id, [])

    if author_id in users_in_channel:
        try:
            await message.delete()
        except discord.Forbidden:
            print(f"Missing permissions in {message.channel}")
        except Exception as e:
            print("Failed to delete message:", e)
# -----------------------------------

if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("Error: set DISCORD_TOKEN environment variable.")
    else:
        bot.run(token)
