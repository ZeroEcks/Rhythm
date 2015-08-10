# -*- coding: utf-8 -*-
import functools
import string

from irc3 import event
import irc3


@irc3.plugin
class Casemapping(object):

    def __init__(self, bot):
        self.bot = bot
        self.recalculate_casemaps()
        self.bot.casefold = functools.partial(self.casefold)

    # casemapping
    @event(r'^:\S+ 005 \S+ .+CASEMAPPING.*')
    def recalculate_casemaps(self):
        casemapping = self.bot.config['server_config'].get('CASEMAPPING', 'rfc1459')

        if casemapping == 'rfc1459':
            lower_chars = string.ascii_lowercase + ''.join(chr(i) for i in range(123, 127))
            upper_chars = string.ascii_uppercase + ''.join(chr(i) for i in range(91, 95))

        elif casemapping == 'rfc1459-strict':
            lower_chars = string.ascii_lowercase + ''.join(chr(i) for i in range(123, 126))
            upper_chars = string.ascii_uppercase + ''.join(chr(i) for i in range(91, 94))

        elif casemapping == 'ascii':
            lower_chars = string.ascii_lowercase
            upper_chars = string.ascii_uppercase

        self._lower_trans = str.maketrans(upper_chars, lower_chars)

    def casefold(self, in_str):
        """Casefold the given string, with the current server's casemapping."""
        return in_str.translate(self._lower_trans)
