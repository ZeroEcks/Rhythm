# -*- coding: utf-8 -*-
import asyncio
import datetime

from irc3.plugins.command import command
from irc3.utils import IrcString
from irc3 import event
import irc3

MOTION_RESULT_LIST = 'Ayes: {ayes}; Nays: {nays}; Abstains: {abstains}'
MOTION_RESULT_COUNT = 'Ayes: {ayes}; Nays: {nays}; Abstains: {abstains}; TOTAL: {total}'
MOTION_EXTERNAL_VOTES = '[+] External ayes: {ayes}; External nays: {nays}'

MOTION_LAPSES_QUORUM = '*** Result: Motion lapses. Quorum of {quorum} not met.'
MOTION_LAPSES_PC = '*** Result: Motion lapses. {in_favour:.2f}% in favour.'
MOTION_CARRIES = '*** Result: Motion carries. {in_favour:.2f}% in favour.'


@irc3.plugin
class Motions(object):

    def __init__(self, bot):
        bot.include('casemapping')
        bot.include('mappinguserlist')
        bot.include('irc3.plugins.async')
        bot.include('irc3.plugins.core')
        self.bot = bot
        self.name = bot.config.get('name', 'motionbot')
        self.states = {}
        self.db = None

        # setup database if we're using one
        db_uri = self.bot.config.get('database', None)
        if db_uri:
            from pymongo import MongoClient
            self.db_client = MongoClient(db_uri)
            self.db = self.db_client.motionbot
            print('Using database')
        else:
            print('Not using database')

    # channel permissions
    def is_voice(self, mask, target):
        target = self.bot.casefold(target)
        if not isinstance(mask, IrcString):
            mask = IrcString(mask)
        return mask.nick in self.bot.channels[target].modes['+']

    def is_admin(self, mask, target):
        target = self.bot.casefold(target)
        if not isinstance(mask, IrcString):
            mask = IrcString(mask)

        # we consider halfop/op and above admins
        prefixes = self.bot.config['server_config'].get('PREFIX', '(ov)@+')
        prefixes = prefixes.split(')')[1]
        admin_prefix_index = prefixes.index('%') if '%' in prefixes else prefixes.index('@')
        admin_prefixes = prefixes[:admin_prefix_index + 1]

        for prefix in admin_prefixes:
            if mask.nick in self.bot.channels[target].modes[prefix]:
                return True

        return False

    # channel info init
    @event(irc3.rfc.JOIN)
    def join_chan(self, mask=None, channel=None):
        """Upon joining a channel, keep track of the channel state."""
        channel = self.bot.casefold(channel)
        if mask.nick == self.bot.nick:
            self.states[channel] = {
                'recognised': [],
                'meeting': {
                    'name': '',
                    'started': False,
                    'quorum': 0,
                },
                'motion': {
                    'text': '',
                    'put_by': '',
                    'started': False,
                    'votes': {},
                },
            }

            if self.db:
                doc = self.db.recognised.find_one({
                    'bot': self.name,
                    'channel': channel,
                })

                if doc:
                    self.states[channel]['recognised'] = doc['users']
                else:
                    self.db.recognised.insert_one({
                        'bot': self.name,
                        'channel': channel,
                        'users': [],
                    })

    # op commands
    @command()
    @asyncio.coroutine
    def add(self, mask, target, args):
        """Recognise a user.

        %%add <nick>
        """
        # we only care about ops and commands to channels
        if not (target.is_channel and self.is_admin(mask, target)):
            return

        channel = self.bot.casefold(target)

        # voice user
        nick = args['<nick>'].lower()
        if not (self.is_admin(nick, channel) or self.is_voice(nick, channel)):
            if self.is_admin(self.bot.nick, channel):
                self.bot.mode(channel, '+v {}'.format(nick))
            else:
                self.bot.notice(channel, '*** I am not opped and cannot voice user.')

        # add user to our recognised list
        info = yield from self.bot.async.whois(nick=nick)

        if not info['success']:
            self.bot.notice(channel, '*** Could not add user to recognised list.')
            return

        userhost = '{username}!{host}'.format(**info)
        if userhost not in self.states[channel]['recognised']:
            self.states[channel]['recognised'].append(userhost)

            if self.db:
                self.db.recognised.update_one({
                        'bot': self.name,
                        'channel': channel,
                    }, {
                        '$push': {
                            'users': userhost,
                        }
                    }
                )

    @command()
    def quorum(self, mask, target, args):
        """Set or see the quorum for the current meeting.

        %%quorum [<number>]
        """
        # we only care about ops and commands to channels
        if not target.is_channel:
            return

        number = args['<number>']
        target = self.bot.casefold(target)

        if number:
            if self.is_admin(mask, target):
                try:
                    number = int(number)
                except ValueError:
                    self.bot.notice(target, '*** Quorum must be an integer')
                    return

                self.states[target]['meeting']['quorum'] = number
                self.bot.notice(target, '*** Quorum now set to: {}'.format(number))

        else:
            current_number = self.states[target]['meeting']['quorum']
            self.bot.notice(target, '*** Quorum is: {}'.format(current_number))

    @command()
    def meeting(self, mask, target, args):
        """Set or see the name for the current meeting.

        %%meeting [<name>...]
        """
        # we only care about ops and commands to channels
        if not target.is_channel:
            return

        name = ' '.join(args['<name>'])
        target = self.bot.casefold(target)

        if name:
            if self.is_admin(mask, target):
                self.states[target]['meeting']['name'] = name
                self.bot.notice(target, '*** Meeting: ' + name)

        else:
            current_name = self.states[target]['meeting']['name']
            self.bot.notice(target, '*** Current meeting: ' + current_name)

    @command()
    def motion(self, mask, target, args):
        """Set or see the text for the current motion.

        %%motion [<text>...]
        """
        # we only care about ops and commands to channels
        if not target.is_channel:
            return

        text = ' '.join(args['<text>'])
        target = self.bot.casefold(target)

        if text:
            if self.is_admin(mask, target):
                self.states[target]['motion']['text'] = text
                self.states[target]['motion']['put_by'] = mask.nick
                self.bot.notice(target, '*** Motion: ' + text)

        else:
            current_text = self.states[target]['motion']['text']
            self.bot.notice(target, '*** Current motion: ' + current_text)

    @command()
    def ayes(self, mask, target, args):
        """Set external ayes for the current motion.

        %%ayes <votes>
        """
        # we only care about ops and commands to channels
        if not (target.is_channel and self.is_admin(mask, target)):
            return

        target = self.bot.casefold(target)

        if not self.states[target]['meeting']['started']:
            self.bot.notice(target, '*** No meeting started.')
            return
        if not self.states[target]['motion']['started']:
            self.bot.notice(target, '*** No motion started.')
            return

        self.states[target]['motion']['extra_ayes'] = int(args['<votes>'])
        self.bot.notice(target, '*** Extra ayes: ' + args['<votes>'])

    @command()
    def nays(self, mask, target, args):
        """Set external nays for the current motion.

        %%nays <votes>
        """
        # we only care about ops and commands to channels
        if not (target.is_channel and self.is_admin(mask, target)):
            return

        target = self.bot.casefold(target)

        if not self.states[target]['meeting']['started']:
            self.bot.notice(target, '*** No meeting started.')
            return
        if not self.states[target]['motion']['started']:
            self.bot.notice(target, '*** No motion started.')
            return

        self.states[target]['motion']['extra_nays'] = int(args['<votes>'])
        self.bot.notice(target, '*** Extra nays: ' + args['<votes>'])

    @command()
    def start(self, mask, target, args):
        """Start a meeting or motion.

        %%start [meeting|motion]
        """
        # we only care about ops and commands to channels
        if not (target.is_channel and self.is_admin(mask, target)):
            return

        target = self.bot.casefold(target)

        if args['meeting']:
            self.states[target]['meeting']['started'] = True
            self.bot.notice(target, '*** Meeting started.')

        elif args['motion']:
            if not self.states[target]['meeting']['started']:
                self.bot.notice(target, '*** No meeting started.')
                return

            self.states[target]['motion']['started'] = True
            self.bot.notice(target, '*** MOTION: ' + self.states[target]['motion']['text'])
            self.bot.notice(target, '*** Put by: ' + self.states[target]['motion']['put_by'])
            self.bot.notice(target, '*** Please now respond either "aye", "nay" or "abstain" '
                                    'to record a vote.')

    @command()
    def cancel(self, mask, target, args):
        """Cancel a motion.

        %%cancel motion
        """
        # we only care about ops and commands to channels
        if not (target.is_channel and self.is_admin(mask, target)):
            return

        target = self.bot.casefold(target)

        if args['motion']:
            self.states[target]['motion'] = {
                'text': '',
                'put_by': '',
                'started': False,
                'votes': {},
            }

            self.bot.notice(target, '*** Motion cancelled.')

    @command()
    def stop(self, mask, target, args):
        """Stop a meeting or motion.

        %%stop [meeting|motion]
        """
        # we only care about ops and commands to channels
        if not (target.is_channel and self.is_admin(mask, target)):
            return

        target = self.bot.casefold(target)

        if args['meeting']:
            if not self.states[target]['meeting']['started']:
                self.bot.notice(target, '*** No meeting started.')
                return

            # XXX - save the meeting data

            self.states[target]['meeting'] = {
                'name': '',
                'started': False,
                'quorum': 0,
            }
            self.states[target]['motion'] = {
                'text': '',
                'put_by': '',
                'started': False,
                'votes': {},
            }

            self.bot.notice(target, '*** Meeting ended.')

        elif args['motion']:
            if not self.states[target]['motion']['started']:
                self.bot.notice(target, '*** There is no motion to stop.')
                return

            # construct aye/nay list
            ayes = []
            nays = []
            abstains = []

            for nick, vote in self.states[target]['motion']['votes'].items():
                # user left channel
                if nick not in self.bot.channels[target]:
                    continue

                if vote is True:
                    ayes.append(nick)
                elif vote is False:
                    nays.append(nick)
                else:
                    abstains.append(nick)

            # count it up
            extra_ayes = self.states[target]['motion'].get('extra_ayes', 0)
            extra_nays = self.states[target]['motion'].get('extra_nays', 0)

            aye_count = len(ayes) + extra_ayes
            nay_count = len(nays) + extra_nays
            abstain_count = len(abstains)

            self.bot.notice(target, '*** Votes')
            self.bot.notice(target, MOTION_RESULT_LIST.format(**{
                'ayes': ', '.join(ayes) if ayes else 'none',
                'nays': ', '.join(nays) if nays else 'none',
                'abstains': ', '.join(abstains) if abstains else 'none',
            }))

            if extra_ayes or extra_nays:
                self.bot.notice(target, MOTION_EXTERNAL_VOTES.format(**{
                    'ayes': extra_ayes,
                    'nays': extra_nays,
                }))

            total = aye_count + nay_count + abstain_count
            quorum = self.states[target]['meeting']['quorum']

            self.bot.notice(target, '*** Tally')
            self.bot.notice(target, MOTION_RESULT_COUNT.format(**{
                'ayes': aye_count,
                'nays': nay_count,
                'abstains': abstain_count,
                'total': total,
            }))

            pc_in_favour = (aye_count / (aye_count + nay_count) * 100)

            if total < quorum:
                self.bot.notice(target, MOTION_LAPSES_QUORUM.format(quorum=quorum))
            elif (aye_count - nay_count) > 0:
                self.bot.notice(target, MOTION_CARRIES.format(in_favour=pc_in_favour))
            else:
                self.bot.notice(target, MOTION_LAPSES_PC.format(in_favour=pc_in_favour))

            self.states[target]['motion'] = {
                'text': '',
                'put_by': '',
                'started': False,
                'votes': {},
            }

    # everyone commands
    @irc3.event(irc3.rfc.PRIVMSG)
    def aye_nay_abstain(self, mask, event, target, data):
        """Accept aye/nay/abstain in regards to a motion."""
        # we only care about messages to channels
        if not target.is_channel:
            return

        target = self.bot.casefold(target)
        nick = self.bot.casefold(mask.nick)

        cmd = data.casefold().split()[0]

        if not self.states[target]['motion']['started'] or cmd not in ('aye', 'nay', 'abstain'):
            return

        if not (self.is_voice(mask, target) or self.is_admin(mask, target)):
            self.bot.privmsg(nick, 'You are not recognised; your vote has not been '
                             'counted. If this a mistake, inform the operators.')
            return

        if cmd == 'aye':
            self.states[target]['motion']['votes'][nick] = True

        elif cmd == 'nay':
            self.states[target]['motion']['votes'][nick] = False

        elif cmd == 'abstain':
            self.states[target]['motion']['votes'][nick] = None

    @irc3.event(irc3.rfc.NEW_NICK)
    def track_nick(self, nick, new_nick):
        """Track nick changes in regard to all motions."""
        old_nick = self.bot.casefold(nick.nick)
        new_nick = self.bot.casefold(new_nick)
        for channel in self.states:
            if old_nick in self.states[channel]['motion']['votes']:
                self.states[channel]['motion']['votes'][new_nick] = self.states[channel]['motion']['votes'][old_nick]
                del self.states[channel]['motion']['votes'][old_nick]

    # This is just to help me debug, it prints everything, every event
    @event(r'(?P<message>.*)')
    def debug(self, message=None):
        print(datetime.datetime.now().strftime("[%H:%M:%S]"), message)
        print('   ', self.states)
