import os
import logging
import twitchio.websocket
import asyncio
import tracemalloc
import json5
import requests
import vlc
from flask import Flask, escape, request

import urlfetch
import twitchio

from bot_helpers import *
from twitchio.ext import commands
from twitchio import webhook
from enum import Enum

from dotenv import load_dotenv

from PyQt5 import QtCore



class TTSVoice(Enum):
    Brian = "Brian"
    Ivy = "Ivy"
    Justin = "Justin"

class SimpleCommand(object):
    def __init__(self, name, aliases, message):
        self.name = name
        self.aliases = aliases
        self.message = message

    async def response(self, context):
        assert isinstance(context, twitchio.Context)
        self.message = self.message.replace("$User", context.message.author.name)
        for msg in self.message.splitlines():
            await context.send(msg)


class BotThread(QtCore.QThread):
    def __init__(self, bot):
        QtCore.QThread.__init__(self)
        self.bot = bot

    def run(self):
        loop = self.bot.Application.loop
        loop.run_until_complete(self.bot._ws._connect())

        try:
            loop.run_until_complete(self.bot._ws._listen())
        except KeyboardInterrupt:
            pass
        finally:
            self.bot._ws.teardown()



class Bot(commands.Bot):
   
    duo_partner = ''
    simple_commands = []
    skip_threshold = 2 ##todo: make this a value of current view count (25% of view count)
    skip_requests = []

    def __init__(self, app, args):
        self.Application = app
        self.args = args

        logging.info(f"Initilalizing Bot...")
        super().__init__(irc_token=os.getenv('TMI_TOKEN'),
                         client_id=os.getenv('CLIENT_ID'),
                         nick=os.getenv('BOT_NICK'),
                         prefix=os.getenv('BOT_PREFIX'),
                         initial_channels=[os.getenv('CHANNEL')],
                         loop = self.Application.loop)
        
        logging.info("Connecting to channel " + self.initial_channels[0])

        logging.info(f'Loading Commands')

        with open('commands.json5') as json_file:
            self.simple_commands = json5.load(json_file)

        for cmd_json in self.simple_commands:
            cmd = SimpleCommand(cmd_json['name'], cmd_json['aliases'], cmd_json['message'])
            new_cmd = commands.Command(name=cmd.name, aliases=cmd.aliases, func=cmd.response)
            self.add_command(new_cmd)

        logging.info(f'Commands Loaded')




    async def event_raw_pubsub(self, data):
        logging.debug(f'Raw Pubsub: {data}')
        return await super().event_raw_pubsub(data)
        
    async def event_pubsub(self, data):
        logging.debug(f'Pubsub: {data}')
        return await super().event_pubsub(data)

    async def event_webhook(self, data):
        logging.debug(f'Webhook Event: {data}')

    async def event_ready(self):
        logging.info(f'{self.nick} is online!')
        ws = self._ws  # this is only needed to send messages within event_ready

        if (self.args.release == "1"):
            await ws.send_privmsg(self.initial_channels[0], f"/me beep boop")
        
        # topic=twitchio.StreamChanged(user_id=46526863)
        #await self.modify_webhook_subscription(mode=twitchio.WebhookMode.subscribe,
        #                                           topic=twitchio.StreamChanged(user_id=46526863), lease_seconds=864000)
        
        await self.pubsub_subscribe(os.getenv('USER_TOKEN'), 'channel-points-channel-v1.46526863')
        

    async def event_message(self, message):
        assert isinstance(message, twitchio.dataclasses.Message)
        logging.info(f'[{message.author.name}]: {message.content}')
        if message.author.name.lower() == self.nick.lower():
            return

        headers = message.raw_data.split(" :")
        dictionary = StringToDict(headers[0])

        # custom reward logic
        if 'custom-reward-id' in dictionary.keys():
            logging.debug(f"Custom Reward ID: {dictionary['custom-reward-id']}")
            
            #song request
            if dictionary['custom-reward-id'] == os.getenv('SONG_REQUEST_ID'): 

                try:
                    logging.info(f"Song Request Recieved - Adding to Queue... URL: {headers[2]}")
                    media = await self.Application.AddMedia(uri=headers[2]) # add song to vlc queue
                    log_msg = f"{message.author.name} added \"{media.Video.title}\" to queue!"
                    await self._ws.send_privmsg(self.initial_channels[0], log_msg)
                    

                except Exception as e:
                    log_msg = f"Song Request Failed, you owe 1000 pants to {message.author} - Error {e}"
                    logging.error(log_msg)
                    await self._ws.send_privmsg(self.initial_channels[0], log_msg)

            #tts message todo: maybe migrate to JS since you will probably want a cool little popup on screen :0
            if dictionary['custom-reward-id'] == os.getenv('TTS_REQUEST_ID'):
                logging.info(f"TTS Message Requested... Message: {headers[2]}")
                self.Application.AddTTSMessage(headers[2])
                


        else:
            await self.handle_commands(message)

    async def event_command_error(self, context, error):
        assert isinstance(context, twitchio.dataclasses.Context)
        logging.error(error)
        #await context.send(error)


    @commands.command(name='dadjoke')
    async def dadjoke(self, context):
        response = urlfetch.get('https://api.scorpstuff.com/dadjokes.php')
        await context.send(response.text)

    @commands.command(name='followage')
    async def followage(self, context):
        response = urlfetch.get(f'https://twitch.api.scorpstuff.com/followed.php?caster={context.channel.name}&follower={context.author.name}')
        await context.send(response.text)

    @commands.command(name='advice')
    async def advice(self, context):
        response = urlfetch.get('https://api.scorpstuff.com/advice.php')
        await context.send(response.text)

    @commands.command(name='duo')
    async def duo(self, context):
        assert isinstance(self.duo_partner, twitchio.Message)
        if len(self.duo_partner.content) == 0:
            await context.send(f'All by myself PepeHands')
        else:
            await context.send(f'I am duoing with twitch.tv/{self.duo_partner.content}')

    @commands.command(name='setduo', aliases=["set_duo, duoset, duo_set, editduo, edit_duo"])
    @commands.check(is_mod)
    async def set_duo(self, context):
        self.duo_partner = context.message
        await context.send(f'{context.message.author.name} set duo to {self.duo_partner.content}')


    @commands.command(name='subcount')
    async def subcount(self, context):
        assert isinstance(context, twitchio.dataclasses.Context)
        stream = await context.channel.get_stream()
        logging.debug(stream)
        await context.send(f'{subcount} people have Subscribed')
    
    #### media commands ####

    @commands.command(name='play')
    @commands.check(is_mod)
    async def songrequest_play(self, context):
        await self.media_session.vlc_player.play()

    @commands.command(name='pause')
    @commands.check(is_mod)
    async def songrequest_pause(self, context):
        await self.media_session.vlc_player.pause()

    @commands.command(name='song')
    async def song(self, context):
        assert isinstance(context, twitchio.dataclasses.Context)

        pass

    @commands.command(name='skip')
    async def skip(self, context):
        assert isinstance(context, twitchio.dataclasses.Context)
        if self.Application.media_list_player.get_state() == vlc.State.Playing:
            if context.author in self.skip_requests:
                await context.send(f'{context.author.name} has already made a skip request!')
            else:
                self.skip_requests.append(context.author)
                if len(self.skip_requests) >= self.skip_threshold:
                    self.Application.onSkipPressed()
                    await context.send(f'Skipping current song!')
                    return
                skip_difference = self.skip_threshold - len(self.skip_requests)
                await context.send(f'{context.author.name} has voted to skip the current song! {skip_difference} more votes required to skip')
        else:
            await context.send('No song is playing!')

    #####

    @commands.command(name='addcommand', aliases=['addcom'])
    @commands.check(is_mod)
    async def addcommand(self, context):
        assert isinstance(context, twitchio.dataclasses.Context)

        _, command_syntax, command_response = context.message.content.split(maxsplit=2)

        logging.info(f'Creating Command {command_syntax}: {command_response}')
        cmd = SimpleCommand(command_syntax, [], command_response)
        if cmd not in self.simple_commands:
            self.simple_commands.append(cmd.__dict__)
            new_cmd = commands.Command(name=cmd.name, aliases=cmd.aliases, func=cmd.response)
            self.add_command(new_cmd)
        else:
            logging.error(f'Command Already Exists!')
            return

        logging.info(f'Saving Command to JSON')
        with open('commands.json5', 'w') as json_file:
            json5.dump(self.simple_commands, json_file)




    @commands.command(name='help')
    async def help(self, context):
        assert isinstance(context, twitchio.dataclasses.Context)
        for cmd in self.commands:
            assert isinstance(cmd, commands.Command)
            await context.send(f"{cmd.name}: ")



    @commands.command(name='ban') #???
    async def ban(self, context):
        assert isinstance(context, twitchio.dataclasses.Context)
        command_syntax, command_response = context.message.content.split(maxsplit=2)
        await context.send(f"{command_response} has been Banned! Kappa")



