# !
# !
# ! NOT YET FINISHED, UNDER DEVELOPMENT!
# !
# !
import discord
from discord.ext import commands
from .utils import checks
from .utils.dataIO import dataIO
from .utils.dataIO import fileIO
from io import BytesIO
from __main__ import send_cmd_help
from random import randint
import os
import time
import aiohttp
import sqlite3
import asyncio
try:
    from PIL import Image, ImageFont, ImageDraw, ImageColor, ImageOps
    pilAvailable = True
except ImportError:
    pilAvailable = False

client = discord.Client()
PATH = 'data/kaktuscog/xplevel'
RANKBG = PATH + '/card.png'
RANKFONT = PATH + '/BebasNeue.otf'
SQLDB = PATH + '/xplevel.sqlite'
SETTINGFILE = PATH + '/settings.json'

INIT_SQL = """
CREATE TABLE IF NOT EXISTS leaderboard (
    server_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    rank INTEGER DEFAULT 0,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 0,
    UNIQUE (server_id, user_id)
);
"""

# FOR IMPORT https://mee6.xyz/api/plugins/levels/leaderboard/239788202745921536?limit=999&page=10

class XPLevel:

    __author__ = "OGKaktus (OGKaktus#5299)"
    __version__ = "2.0"
    
    def __init__(self, bot):
        self.bot = bot
        self.db = sqlite3.connect(SQLDB, detect_types=sqlite3.PARSE_DECLTYPES)
        self.db.row_factory = sqlite3.Row
        with self.db as con:
            con.executescript(INIT_SQL)
        try:
            self.settings = dataIO.load_json(SETTINGFILE)
        except Exception:
            self.settings =  {}
        self.session = aiohttp.ClientSession()
        self.waitingxp = {}
            
    def __unload(self):
        self.save()
        self.db.close()
        
    def save(self):
        self.db.commit()
        
#ADMIN COMMANDS
    @commands.group(pass_context=True)
    @checks.admin_or_permissions(manage_server=True)
    async def xplevel(self, ctx):
        """Rank operations"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)
            
    @xplevel.command(pass_context=True, no_pm=True)
    async def enable(self, ctx):
        """
        Enables the use of XPLevel on this server
        """
        server_id = ctx.message.server.id
        self.settings[server_id]["ENABLED"] = True
        await self.bot.say("XPLevel is now enabled")
        
    @xplevel.command(pass_context=True, no_pm=True)
    async def disable(self, ctx):
        """
        Disables the use of XPLevel on this server
        """
        server_id = ctx.message.server.id
        self.settings[server_id]["ENABLED"] = False
        await self.bot.say("XPLevel is now disabled")
        
    @xplevel.command(pass_context=True, no_pm=True)
    async def set(self, ctx, setting: str, *, value: str):
        """
        Modify settings for XPLevel on this server
        
        Valid settings are:
            cooldown        Set the cooldown before new xp can be earned (in seconds)
            levelmsg        Set the level up message use {level} to display level. eg "GG Airship you have now achieved level {level}"
            resetonleave    Either set to true or false to reset users xp when leaving server
        """
        server_id = ctx.message.server.id
        if server_id not in self.settings:
            self.createsettings(server_id)
            
        if setting == "cooldown":
            try:
                self.settings[server_id]["XPCOOL"] = int(value)
                await self.bot.say("The cooldown is now " + value + " seconds")
            except ValueError:
                await self.bot.say("The cooldown must be a number..")
        elif setting == "levelmsg":
            self.settings[server_id]["LVLUPMSG"] = value
            await self.bot.say("Level up message set to: ```" + value + "```")
        elif setting == "resetonleave":
            await self.bot.say("Reset on leave")
        else:
            await self.bot.say("Sorry there is no such setting...")
        self.save()
        
    @xplevel.command(pass_context=True, no_pm=True)
    async def blacklistchannel(self, ctx, channel: discord.Channel):
        """
        Add a channel where xp cannot be gained
        """
        server = ctx.message.server
        if server.id not in self.settings:
            self.createsettings(server.id)
        if channel.id in self.settings[server.id]["BLACKLISTCHANNELS"]:
            return await self.bot.say('Channel already blacklisted...')
        self.settings[server.id]["BLACKLISTCHANNELS"].append(channel.id)
        self.save()
        return await self.bot.say('Channel ' + channel.mention + ' is now blacklisted')
        
    @xplevel.command(pass_context=True, no_pm=True)
    async def unblacklistchannel(self, ctx, channel: discord.Channel):
        """
        Removes a channel from the blacklist
        """
        server = ctx.message.server
        if server.id not in self.settings:
            self.createsettings(server.id)
        if channel.id not in self.settings[server.id]["BLACKLISTCHANNELS"]:
            return await self.bot.say('Channel is not blacklisted...')
        self.settings[server.id]["BLACKLISTCHANNELS"].remove(channel.id)
        self.save()
        return await self.bot.say('Channel ' + channel.mention + ' is now removed from blacklist')

    @xplevel.command(pass_context=True, no_pm=True)
    async def viewchannelblacklist(self, ctx):
        """
        Lists all blacklisted channels
        """
        server = ctx.message.server
        msg = "Blacklisted channels:\n"
        for channel_id in self.settings[server.id]["BLACKLISTCHANNELS"]:
            msg+= "     " + server.get_channel(channel_id) + "\n"
        return await self.bot.say(msg)   

    @xplevel.command(pass_context=True, no_pm=True)
    async def blacklistrole(self, ctx, role: discord.Role):
        """
        Add a role where xp cannot be gained
        """
        server = ctx.message.server
        if server.id not in self.settings:
            self.createsettings(server.id)
        if role.id in self.settings[server.id]["BLACKLISTROLES"]:
            return await self.bot.say('Role already blacklisted...')
        self.settings[server.id]["BLACKLISTROLES"].append(role.id)
        self.save()
        return await self.bot.say('Role ' + role.mention + ' is now blacklisted')
        
    @xplevel.command(pass_context=True, no_pm=True)
    async def unblacklistrole(self, ctx, role: discord.role):
        """
        Removes a role from the blacklist
        """
        server = ctx.message.server
        if server.id not in self.settings:
            self.createsettings(server.id)
        if role.id not in self.settings[server.id]["BLACKLISTROLES"]:
            return await self.bot.say('role is not blacklisted...')
        self.settings[server.id]["BLACKLISTROLES"].remove(role.id)
        self.save()
        return await self.bot.say('role ' + role.mention + ' is now removed from blacklist')

    @xplevel.command(pass_context=True, no_pm=True)
    async def viewroleblacklist(self, ctx):
        """
        Lists all blacklisted roles
        """
        server = ctx.message.server
        msg = "Blacklisted roles:\n"
        for role_id in self.settings[server.id]["BLACKLISTROLES"]:
            role_obj = discord.utils.get(server.roles, id=role_id)
            msg+= "     " + role_obj.mention + "\n"
        return await self.bot.say(msg) 
        
    @xplevel.command(pass_context=True, no_pm=True)
    async def reward(self, ctx, setting: str, role: str, *, level: str):
        """
        Add or remove rewards based on level.
        eg. [p]xplevel reward add @Shitposter 10
        
        Valid settings are:
            add         Add reward
            del         Remove reward
            list        List all rewards
        """
        server_id = ctx.message.server.id
        if server_id not in self.settings:
            self.createsettings(server_id)
            
        if setting == "add":
            test=1
        elif setting == "del":
            test=1
        elif setting == "list":
            test=1
        else:
            await self.bot.say("Sorry ther is no such setting...")
        self.save()
        
    

#BOT FUNCTIONS
    def createsettings(self, server_id):
        self.settings[server_id] = {}
        self.settings[server_id]["ENABLED"] = False
        self.settings[server_id]["XPCOOL"] = 60
        self.settings[server_id]["LVLUPMSG"] = "GG airshipa, you leveled up to level {level}!"
        self.settings[server_id]["BLACKLISTCHANNELS"] = []
        self.settings[server_id]["BLACKLISTROLES"] = []
        self.settings[server_id]["REWARDS"] = {}
        self.settings[server_id]["RESETONLEAVE"] = True
            
    def save(self):
        fileIO(SETTINGFILE, "save", self.settings)
        
    async def givereward(self, server, user, level):
        # First check if user should have gained a reward
        # if level == on of the reward goals, give role.
        member = server.get_member(user.id)
        if level not in self.settings[server.id]["REWARDS"]:
            return
            
        role = self.settings[server.id]["REWARDS"][level]
        if role in player.roles:
            return
        try:
            await self.bot.add_roles(member, role)
        except discord.Forbidden:
            print("Failed to add roles to {} ({})\n{}\n"
                    "I lack permissions to do that."
                    "".format(member, member.id, role))
        except discord.HTTPException as e:
            print("Failed to add roles to {} ({})\n{}\n"
                    "{}"
                    "".format(member, member.id, role, e))
        
    async def getxp(self, message):
        user = message.author
        server = message.server
        xp = 0
        if user == self.bot.user or message.author.bot:
            return
        prefix = await self.get_prefix(message)
        if prefix:
            return
        if self.rankenabled(message.server):
            if message.channel not in self.settings[server.id]["BLACKLISTCHANNELS"]:
                for role in user.roles:
                    if role.id in self.settings[server.id]["BLACKLISTROLES"]:
                        return
                if user.id in self.waitingxp:
                    seconds = abs(self.waitingxp[user.id] - int(time.perf_counter()))
                    if seconds >= self.settings[server.id]["COOLDOWN"]:
                        curuser = self.addxp(server, user)
                        if curuser["xp"] >= self.getnextlevelxp(curuser['level']):
                            # LevelUp!
                            new_level = self.levelup(server, user)
                            await self.bot.send_message(message.author, self.formatlevelmsg(self.settings[server.id]["LVLUPMSG"], new_level))
                else:
                    curuser = self.addxp(server, user)
                    if int(curuser["xp"]) >= int(self.getnextlevelxp(curuser['level'])):
                        # LevelUp!
                        new_level = self.levelup(server, user)
                        await self.bot.send_message(message.author, self.formatlevelmsg(self.settings[server.id]["LVLUPMSG"], new_level))

        else:
            return
            
    async def levelup(self, server, user):
        sql = "UPDATE leaderboard SET level=level+1 WHERE server_id=? AND user_id=?;" 
        sql2 = "SELECT * FROM leaderboard WHERE server_id = ? AND user_id = ?;"
        with self.db as con:
            con.execute(sql, (server.id, user.id))
            curuser = con.execute(sql2, (server.id, user.id)).fetchone()
        await self.givereward(server, user, curuser["level"])
        return curuser["level"]
                
    async def get_prefix(self, msg):
        prefixes = self.bot.command_prefix
        if callable(prefixes):
            prefixes = prefixes(self.bot, msg)
            if asyncio.iscoroutine(prefixes):
                prefixes = await prefixes

        for p in prefixes:
            if msg.content.startswith(p):
                return p
        return None
    
    async def klog(self, what: str, *, val: str):
        print(what + ": {}".format(val))
        
    def formatlevelmsg(self, msg, level):
        msg = msg.replace("{level}", str(level))
        return msg
    
    def addxp(self, server, user):
        sql1 = "INSERT OR IGNORE INTO leaderboard(server_id, user_id) VALUES(?,?);"
        sql2 = "UPDATE leaderboard SET xp=xp+? WHERE server_id = ? AND user_id = ?;"
        sql3 = "SELECT * FROM leaderboard WHERE server_id = ? AND user_id = ?;"        
        sql4 = "SELECT * FROM leaderboard where xp < ? AND server_id = ? ORDER BY xp DESC;"
        sql5 = "UPDATE leaderboard SET rank = ? WHERE server_id = ? AND user_id = ?;"
        sql6 = "SELECT * FROM leaderboard ORDER BY rank DESC;"
        sql7 = "SELECT * FROM leaderboard WHERE server_id = ? AND user_id != ? ORDER BY rank DESC;"
            
        xp = int(randint(15, 25))
        with self.db as con:
            con.execute(sql1, (server.id, user.id))
            curuser = con.execute(sql3, (server.id, user.id)).fetchone()
            currank = int(curuser['rank'])
            curxp = int(curuser['xp']) + xp
            if currank == 0:
                tmpuser2 = con.execute(sql6,()).fetchone()
                con.execute(sql5,(int(tmpuser2['rank']) + 1, server.id, user.id))
                currank = int(tmpuser2['rank']) + 1
                
            con.execute(sql2, (xp, server.id, user.id))
            nextuser = con.execute(sql4, (curxp, server.id)).fetchone()
            
            if nextuser is None:
                tmpuser2 = con.execute(sql7,(server.id, user.id)).fetchone()
                if tmpuser2:
                    self.klog("rank", tmpuser2['rank'])
                    con.execute(sql5,(int(tmpuser2['rank']) + 1, server.id, user.id))
                else:
                    con.execute(sql5,(1, server.id, user.id))
            else:
                if int(nextuser['rank']) < currank :
                    con.execute(sql5, (nextuser['rank'], server.id, user.id))
                    con.execute(sql5, (currank, server.id, nextuser['user_id']))
            return curuser
        
    def getnextlevelxp(self, level):
        nextlevel = int(level) + 1
        xp = 5 / 6 * nextlevel * (2 * nextlevel * nextlevel + 27 * nextlevel + 91)
        return xp
    
    def rankenabled(self, server):
        if server.id in self.settings:
            if "ENABLED" in self.settings[server.id]:
                if self.settings[server.id]["ENABLED"]:
                    return True
                else:
                    return False
            else:
                return False
        else:
            return False

def setup(bot):
    if pilAvailable:
        n = XPLevel(bot)
        bot.add_listener(n.getxp, "on_message")
        bot.add_cog(n)
    else:
        raise RuntimeError("You need to run 'pip3 install Pillow'")
