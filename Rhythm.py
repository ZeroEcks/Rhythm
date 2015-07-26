# -*- coding: utf-8 -*-
from irc3.plugins.command import command
from irc3 import event
import irc3



@irc3.plugin
class Motions(object):

    def __init__(self, bot):
        bot.include('irc3.plugins.userlist')
        self.bot = bot
        self.states = {}

    @event(irc3.rfc.JOIN)
    def join_chan(self, mask=None, channel=None):
        """Upon us joining a channl we keep track of the state in this room
        """
        if mask.nick == self.bot.nick:
            self.states[channel] = {
                'meeting': {
                    'name': None,
                    'started': False,
                    'quorum': 0
                },
                'motion': {
                    'text': None,
                    'owner': None,
                    'votes': []
                }
            }

    @command(permission='admin')
    def start(self, mask, target, args):
        """Start a meeting or motion

        %%start <event>
        """
        if args['<event>'] == 'meeting':
            self.states[target]['meeting'] = True
        elif args['<event>'] == 'motion':
            self.states[target]['motion'] = True
        self.bot.privmsg('MelodyKH3', 'User added')

    @command(permission='admin')
    def stop(self, mask, target, args):
        """Stop a meeting or motion

        %%start <event>
        """
        if args['<event>'] == 'meeting':
            self.states[target]['meeting'] = False
        elif args['<event>'] == 'motion':
            self.states[target]['motion'] = False
        self.bot.privmsg('MelodyKH3', 'User added')

    # This regex matches a person saying Aye, returns the person,
    # the event they said, and which room.
    @event(r'^:(?P<mask>\S+!\S+@\S+) (?P<event>(PRIVMSG|NOTICE)) (?P<target>\S+) :\s*(?i)Aye\s*$')
    def aye(self, mask=None, event=None, target=None):
        return True


    # This regex matches a person saying Nay, returns the person,
    # the event they said, and which room.
    @event(r'^:(?P<mask>\S+!\S+@\S+) (?P<event>(PRIVMSG|NOTICE)) (?P<target>\S+) :\s*(?i)Nay\s*$')
    def nay(self, mask=None, event=None, target=None):
        print(mask, event, target)

    # This is just to help me debug, it prints everything, every event
    @event(r'(?P<target>.*)')
    def debug(self, target=None):
        print(target)
        print(self.states)
