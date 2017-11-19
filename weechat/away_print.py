# MIT License

# Copyright (c) 2017 Samuel Hoffman

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
away_print.py: Print changes in AWAY status on buffers for servers where away-notify is enabled.

Settings: plugins.var.python.away_print.*
    print_prefix                -> prefix for away print messages
    print_away_format           -> printed message when someone goes away
    print_back_format           -> printed message when someone returns from away
    print_back_duration_format  -> printed message when someone returns away w/ a known duration
    print_changed_format        -> printed message when someone's away message changes

note: there is no feature provided for hiding away messages from specific nicks or on specific
buffers. instead, use WeeChat's /filter command with the tags printed on away message lines to hide
as desired.

for example:
    filter all away mesages from 'cruzr' everywhere
        /filter add hide_cruzr_away * irc_away+nick_cruzr *
    filter all away messages on Freenode's weechat
        /filter add hide_weechat_away irc.freenode.#weechat irc_away *
    filter all away messages on AlphaChat
        /filter add hide_alphachat_away irc.AlphaChat.* irc_away *

"""

try:
    import weechat as w
except ImportError:
    print("Load this script from WeeChat.")

from datetime import datetime
from collections import defaultdict
from typing import Any, Dict, Generator, Match, Set, Tuple  # pylint: disable=unused-import

SCRIPT_NAME = "away_print"
SCRIPT_AUTHOR = "cruzr <sam@gentoo.party>"
SCRIPT_VERSION = "1"
SCRIPT_LICENSE = "MIT"
SCRIPT_DESC = "Print changes in AWAY status on buffers for servers where away-notify is enabled."

w.register(SCRIPT_NAME, SCRIPT_AUTHOR, SCRIPT_VERSION,
           SCRIPT_LICENSE, SCRIPT_DESC, "", "")

DEFAULT_SETTINGS = {
    "print_prefix": ("${color:lightblue}ZzZ", "prefix for away messages. content is evaluted"),
    "print_away_format": ("$nick is now away ${color:green}(${color:default}$away${color:green})",
                          "format for printing away messages. content is evaluated. valid "
                          "replacements are: '$nick' and '$away' (see /help eval for more)"),
    "print_back_format": ("$nick has returned",
                          "format for printing return messages. content is evaluated. "
                          "valid replacements are: '$nick' (see /help eval for more)"),
    "print_back_duration_format": ("$nick has returned ${color:green}(${color:default}gone $gone$"
                                   "{color:green})",

                                   "format for printing "
                                   "return messages. content is evaluated. valid replacments are: "
                                   "'$nick', '$gone' (see /help eval for more)"),

    "print_changed_format": ("$nick is still away ${color:green}(${color:default}$away$"
                             "{color:green})",

                             "format for printing changed away. content is evaluated. valid "
                             "replacements are: '$nick' and '$away' (see /help eval for more)")

}

KNOWN_AWAY = defaultdict(dict)  # type: Dict[str, Dict[str, datetime]]
CACHE = defaultdict(dict)  # type: Dict[str, Dict[str, Set]]
COLOR = {}  # type: Dict[str, str]
BUFFERS = {}  # type: Dict[str, str]
TAGS = "irc_away,nick_{nick},no_highlight,notify_none,away_info,irc_smart_filter"


def config_get(name: str):
    """ retrieve value of a setting """
    return w.config_get_plugin(name)


def config_set_defaults():
    """ (first time run) create setting defaults and descriptoins """
    for option, (default, desc) in DEFAULT_SETTINGS.items():
        if not w.config_is_set_plugin(option):
            w.config_set_plugin(option, default)
            w.config_set_desc_plugin(option, desc)


def get_buffer(server, chan):
    """ return cached pointer to buffer for server.channel """
    return BUFFERS[server + "." + chan]


def color_nick(nick):
    """ colorize a nickname based on what WeeChat picked as it's prefix color. """
    if nick in COLOR:
        return w.color(COLOR[nick]) + nick + w.color("reset")
    return w.color(w.info_get("nick_color_name", nick)) + nick + w.color("reset")


def propagate_common_msg(server, common_nick, message):
    """ propagate a message to all irc buffers in common with a nick on a server """

    found_channel = False
    found_query = False
    tags = TAGS.format(nick=common_nick)
    ## first check CACHE for common channels
    if common_nick in CACHE[server]:
        found_channel = True
        message = message.replace("$nick", color_nick(common_nick))
        for chan in CACHE[server][common_nick]:
            w.prnt_date_tags(get_buffer(server, chan), 0, tags, message)

    ## look for query buffers
    if server + "." + common_nick in BUFFERS:
        found_query = True
        message = message.replace("$nick", color_nick(common_nick))
        w.prnt_date_tags(get_buffer(server, common_nick), 0, tags, message)

    if found_channel and found_query:
        return

    chans_il = w.infolist_get("irc_channel", "", server)
    if not chans_il:
        return

    channels = {}

    while w.infolist_next(chans_il):
        ptr = w.infolist_pointer(chans_il, "buffer")
        name = w.infolist_string(chans_il, "name")

        channels[name] = ptr

    w.infolist_free(chans_il)

    for chan, ptr in channels.items():

        BUFFERS["{}.{}".format(server, chan)] = ptr

        ## is a query buffer?
        if not found_query and common_nick == chan:
            message = message.replace('$nick', color_nick(common_nick))
            w.prnt_date_tags(ptr, 0, tags, message)
            continue

        if found_channel:
            continue

        nicks_il = w.infolist_get("irc_nick", "", "{},{}".format(server, chan))
        if not nicks_il:
            continue

        while w.infolist_next(nicks_il):
            search_nick = w.infolist_string(nicks_il, "name")
            COLOR[search_nick] = w.infolist_string(nicks_il, "color")

            if common_nick == search_nick or common_nick == chan:
                message = message.replace('$nick', color_nick(common_nick))
                w.prnt_date_tags(ptr, 0, tags, message)

            if search_nick not in CACHE[server]:
                CACHE[server][search_nick] = set({chan})
            else:
                CACHE[server][search_nick].add(chan)

        w.infolist_free(nicks_il)

# callbacks


def away_in_cb(data, signal, signal_data):
    """ callback for away-notify messages """

    ircmsg = w.info_get_hashtable(
        "irc_message_parse", {"message": signal_data})
    server = signal.split(",")[0]
    nick = ircmsg["nick"]

    msg = config_get("print_prefix") + "\t"
    awaymsg = ircmsg["text"]
    if not awaymsg:

        dur = None
        if nick in KNOWN_AWAY[server]:
            dur = str(datetime.now() - KNOWN_AWAY[server].pop(nick))

        if dur:

            msg += config_get("print_back_duration_format")
            msg = msg.replace("$gone", dur)

        else:
            msg += config_get("print_back_format")

        msg = w.string_eval_expression(msg, {}, {}, {})
        propagate_common_msg(server, nick, msg)

    else:

        if nick in KNOWN_AWAY[server]:
            msg += config_get("print_changed_format")
            msg = msg.replace("$away", awaymsg)

            msg = w.string_eval_expression(msg, {}, {}, {})
            propagate_common_msg(server, nick, msg)
            KNOWN_AWAY[server][nick] = datetime.now()
        else:
            msg += config_get("print_away_format")
            msg = msg.replace("$away", awaymsg)

            msg = w.string_eval_expression(msg, {}, {}, {})
            KNOWN_AWAY[server][nick] = datetime.now()
            propagate_common_msg(server, nick, msg)

    return w.WEECHAT_RC_OK


def nick_in_cb(data, signal, signal_data):
    """ callback for a nick change in WeeChat. rename cache entries, except for COLOR """
    ircmsg = w.info_get_hashtable("irc_message_parse", {"message": signal_data})
    server = signal.split(",")[0]

    oldnick = ircmsg["nick"]
    newnick = ircmsg["text"]

    if oldnick in KNOWN_AWAY[server]:
        KNOWN_AWAY[server][newnick] = KNOWN_AWAY[server].pop(oldnick)

    bufname = server + "." + oldnick
    if bufname in BUFFERS:
        BUFFERS[server + "." + newnick] = BUFFERS.pop(bufname)

    return w.WEECHAT_RC_OK

def part_in_cb(data, signal, signal_data):
    """ callback for a user parting a channel. invalide cache entries """
    ircmsg = w.info_get_hashtable("irc_message_parse", {"message": signal_data})
    server = signal.split(",")[0]
    channel = ircmsg["channel"]
    nick = ircmsg["nick"]

    if nick == w.info_get("irc_nick", server):
        for chans in CACHE[server].values():
            chans.discard(channel)
    elif nick in CACHE[server]:
        CACHE[server][nick].discard(channel)

    return w.WEECHAT_RC_OK

def quit_in_cb(data, signal, signal_data):
    """ callback for a user quitting an IRC server. invalidate cache entries """
    ircmsg = w.info_get_hashtable("irc_message_parse", {"message": signal_data})
    server = signal.split(",")[0]
    nick = ircmsg["nick"]

    if nick in CACHE[server]:
        del CACHE[server][nick]

    bufname = server + "." + nick
    if bufname in BUFFERS:
        del BUFFERS[bufname]

    return w.WEECHAT_RC_OK

def kick_in_cb(data, signal, signal_data):
    """ callback for a user being kicked from a channel. invalidate cache entries """
    ircmsg = w.info_get_hashtable("irc_message_parse", {"message": signal_data})
    server = signal.split(",")[0]
    channel = ircmsg["channel"]
    nick = ircmsg["arguments"].split(' ', 2)[1]

    if nick == w.info_get("irc_nick", server):
        for chans in CACHE[server].values():
            chans.discard(channel)

        del BUFFERS[server + "." + channel]
    elif nick in CACHE[server]:
        CACHE[server][nick].discard(ircmsg["channel"])

    return w.WEECHAT_RC_OK

def join_in_cb(data, signal, signal_data):
    """ callback for a user joining a channel. add to caches """
    ircmsg = w.info_get_hashtable("irc_message_parse", {"message": signal_data})
    server = signal.split(",")[0]
    nick = ircmsg["nick"]
    channel = ircmsg["channel"]
    buffer_name = "{}.{}".format(server, channel)

    if nick in CACHE[server]:
        CACHE[server][nick].add(channel)
    else:
        CACHE[server][nick] = set({channel})

    if buffer_name not in BUFFERS:
        BUFFERS[buffer_name] = w.info_get("irc_buffer", server + "," + channel)

    if nick not in COLOR:
        COLOR[nick] = w.info_get("nick_color_name", nick)

    return w.WEECHAT_RC_OK

def irc_discon_cb(data, signal, signal_data):
    """ callback for when WeeChat disconnects from IRC. invalidate caches for server """
    if signal_data in CACHE:
        del CACHE[signal_data]

    for name in BUFFERS:
        if name.startswith(signal_data):
            del BUFFERS[name]

def buffer_closed_cb(data, signal, signal_data):
    """ callback for when a buffer closes. used to invalidate query windows so we don't try to print
    to a closed query buffer.  """

    for name, ptr in BUFFERS.items():
        if ptr == signal_data:
            del BUFFERS[name]
            return w.WEECHAT_RC_OK

    return w.WEECHAT_RC_OK

w.hook_signal("*,irc_in2_AWAY", "away_in_cb", "")
w.hook_signal("*,irc_in2_NICK", "nick_in_cb", "")
w.hook_signal("*,irc_in2_PART", "part_in_cb", "")
w.hook_signal("*,irc_in2_QUIT", "quit_in_cb", "")
w.hook_signal("*,irc_in2_KICK", "kick_in_cb", "")
w.hook_signal("*,irc_in2_JOIN", "join_in_cb", "")
w.hook_signal("irc_server_disconnected", "irc_discon_cb", "")
w.hook_signal("buffer_closed", "buffer_closed_cb", "")
config_set_defaults()
