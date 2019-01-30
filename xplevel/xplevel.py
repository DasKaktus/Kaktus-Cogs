# !
# !
# ! NOT YET FINISHED, UNDER DEVELOPMENT
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

class XPLevel:

    __author__ = "DasKaktus (DasKaktus#5299)"
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
            
    @xplevel.command(pass_context=True)
    async def set(self, ctx, setting: str, *, value: str):
        """
        Modify settings for XPLevel on this server
        
        Valid settings are:
            enable          Enable this server to get xp
            disable          Disable this server to get xp
            cooldown        Set the cooldown before new xp can be earned (in seconds)
            levelmsg        Set the level up message use {level} to display level. eg "GG Airship you have now achieved level {level}"
            resetonleave    Either set to true or false to reset users xp when leaving server
        """
        server_id = ctx.message.server.id
        if ctx.message.server.id not in self.settings:
            self.settings[server_id] = {}
            self.settings[server_id]["ENABLED"] = False
            self.settings[server_id]["XPCOOL"] = 60
            self.settings[server_id]["LVLUPMSG"] = "GG airshipa, you leveled up to level {level}!"
            self.settings[server_id]["BLACKLISTCHANNELS"] = {}
            self.settings[server_id]["BLACKLISTROLES"] = {}
            self.settings[server_id]["RESETONLEAVE"] = True
            
        if setting == "enable":
            self.settings[server_id]["ENABLED"] = True
            await self.bot.say("XPLevel is now enabled")
        elif setting == "disable":
            self.settings[server_id]["ENABLED"] = False
            await self.bot.say("XPLevel is now disabled")
        elif setting == "cooldown":
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
            await self.bot.say("Sorry ther is no such setting...")
        self.save()
        
    @xplevel.command(pass_context=True, no_pm=True)
    async def blacklist(self, ctx, setting: str, value: str):
        """
        Add or remove channels where xp cant be gained
        
        Valid settings are:
            add         Add channel to blacklist
            del         Remove channel from blacklist
            list        Shows all blacklisted channels
        """
        test = 1
        
    

#BOT FUNCTIONS
    def save(self):
        fileIO(SETTINGFILE, "save", self.settings)
        
    async def getxp(self, message):
        user = message.author
        server = message.server
        xp = 0
        if user == self.bot.user:
            return
        prefix = await self.get_prefix(message)
        if prefix:
            return
        if self.rankenabled(message.server):
            if message.channel not in self.settings[server.id]["BLACKLISTCHANNELS"]:
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
            
    def levelup(self, server, user):
        sql = "UPDATE leaderboard SET level=level+1 WHERE server_id=? AND user_id=?;" 
        sql2 = "SELECT * FROM leaderboard WHERE server_id = ? AND user_id = ?;"
        with self.db as con:
            con.execute(sql, (server.id, user.id))
            curuser = con.execute(sql2, (server.id, user.id)).fetchone()
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
        
    def formatlevelmsg(self, msg, level):
        msg = msg.replace("{level}", str(level))
        return msg
    
    def addxp(self, server, user):
        sql = "INSERT OR IGNORE INTO leaderboard(server_id, user_id) VALUES(?,?);"
        sql2 = "UPDATE leaderboard SET xp=xp+? WHERE server_id = ? AND user_id = ?;" 
        sql2new = "UPDATE leaderboard SET xp=xp+?, rank = ? WHERE server_id = ? AND user_id = ?;" 
        sql3 = "SELECT * FROM leaderboard WHERE server_id = ? AND user_id = ?;"
        
        sql4 = "SELECT * FROM leaderboard where xp < ? AND server_id = ? ORDER BY xp DESC;"
        sql5 = "UPDATE leaderboard SET rank = ? WHERE server_id = ? AND user_id = ?;"
        
        xp = int(randint(15, 20))
        with self.db as con:
            con.execute(sql, (server.id, user.id))
            tmpuser = con.execute("SELECT * FROM leaderboard WHERE server_id = ? AND user_id = ?", (server.id, user.id)).fetchone()
            if tmpuser['rank'] == 0:
                #new user set rank to last.. Or?
                tmpuser2 = con.execute("SELECT * FROM leaderboard ORDER BY rank DESC",()).fetchone()
                con.execute(sql5,(tmpuser2['rank'] + 1, server.id, user.id))
                
            con.execute(sql2, (xp, server.id, user.id))
            curuser = con.execute(sql3, (server.id, user.id)).fetchone()
            nextuser = con.execute(sql4, (curuser['xp'], server.id)).fetchone()
            if nextuser is None:
                con.execute(sql5, (1, server.id, user.id))
            else:
                if int(nextuser['rank']) > int(curuser['rank']):
                    con.execute(sql5, (nextuser['rank'], server.id, user.id))
                    con.execute(sql5, (curuser['rank'], server.id, nextuser['user_id']))
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
