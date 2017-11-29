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
    print_prefix    -> prefix for away print messages
    color_prefix    -> color to use for the prefix
    color_away      -> color for away reasons and the gone duration in printed away messages

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
    import sys
    print("Load this script from WeeChat.")
    sys.exit()

from collections import defaultdict
from datetime import datetime

try:
    from typing import Dict, Set, Tuple  # pylint: disable=unused-import
except ImportError:
    pass

SCRIPT_NAME = "away_print"
SCRIPT_AUTHOR = "Samuel Hoffman <sam@gentoo.party>"
SCRIPT_VERSION = "2"
SCRIPT_LICENSE = "MIT"
SCRIPT_DESC = "Print changes in AWAY status on buffers for servers where away-notify is enabled."

w.register(SCRIPT_NAME, SCRIPT_AUTHOR, SCRIPT_VERSION,
           SCRIPT_LICENSE, SCRIPT_DESC, "", "")

DEFAULT_SETTINGS = {
    "print_prefix": ("ZzZ", "prefix for away message"),
    "color_prefix": ("lightblue", "color for the away message prefix in 'print_prefix'"),
    "color_away": ("default", "color used for away/gone duration in printed away messages")
}

KNOWN_AWAY = defaultdict(dict)  # type: Dict[str, Dict[str, Tuple[datetime, str]]]
CACHE = defaultdict(dict)  # type: Dict[str, Dict[str, Set]]
BUFFERS = {}  # type: Dict[str, str]
TAGS = "irc_away,nick_{nick},no_highlight,notify_none,away_info,irc_smart_filter"

MSG_BACK_NO_DURATION = "{cc_pfx}{pfx}\t{cc}{nick}{default} has returned"
MSG_BACK_DURATION = "{cc_pfx}{pfx}\t{cc}{nick}{default} has returned {sep}({cc_away}gone" \
                    " {duration}{sep})"
MSG_AWAY = "{cc_pfx}{pfx}\t{cc}{nick}{default} is now away {sep}({cc_away}{awaymsg}{sep})"
MSG_STILL_AWAY = "{cc_pfx}{pfx}\t{cc}{nick}{default} is still away {sep}({cc_away}{awaymsg}{sep})"

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
    """ colorize a nickname based on what WeeChat picked as it's color. """
    return w.color(w.info_get("nick_color_name", nick))


def propagate_common_msg(server, common_nick, message):
    """ propagate a message to all irc buffers in common with a nick on a server """

    found_channel = False
    found_query = False
    tags = TAGS.format(nick=common_nick)
    ## first check CACHE for common channels
    if common_nick in CACHE[server]:
        found_channel = True
        for chan in CACHE[server][common_nick]:
            w.prnt_date_tags(get_buffer(server, chan), 0, tags, message)

    ## look for query buffers
    if server + "." + common_nick in BUFFERS:
        found_query = True
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
            w.prnt_date_tags(ptr, 0, tags, message)
            continue

        if found_channel:
            continue

        nicks_il = w.infolist_get("irc_nick", "", server + "," + chan)
        if not nicks_il:
            continue

        while w.infolist_next(nicks_il):
            search_nick = w.infolist_string(nicks_il, "name")

            if common_nick == search_nick or common_nick == chan:
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

    awaymsg = ircmsg["text"]
    if not awaymsg:

        dur = ""
        if nick in KNOWN_AWAY[server]:
            tdelta = datetime.now() - KNOWN_AWAY[server].pop(nick)[0]
            days = tdelta.days
            hours, remainder = divmod(tdelta.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)

            if days:
                dur = "{} day{} ".format(days, "s" if days > 1 else "")

            if hours:
                dur += "{} hour{} ".format(hours, "s" if hours > 1 else "")

            if minutes:
                dur += "{} minute{} ".format(minutes, "s" if minutes > 1 else "")

            if seconds:
                dur += "{} second{}".format(seconds, "s" if seconds > 1 else "")

            dur = dur.rstrip()

        if dur:
            msg = MSG_BACK_DURATION.format(pfx=config_get("print_prefix"), cc=color_nick(nick),
                                           nick=nick, sep=w.color("weechat.color.chat_delimiters"),
                                           default=w.color("default"), duration=dur,
                                           cc_away=w.color(config_get("color_away")),
                                           cc_pfx=w.color(config_get("color_prefix")))

        else:
            msg = MSG_BACK_NO_DURATION.format(pfx=config_get("print_prefix"), cc=color_nick(nick),
                                              nick=nick,
                                              sep=w.color("weechat.color.chat_delimiters"),
                                              default=w.color("default"),
                                              cc_away=w.color(config_get("color_away")),
                                              cc_pfx=w.color(config_get("color_prefix")))

        propagate_common_msg(server, nick, msg)

    else:

        if nick in KNOWN_AWAY[server] and awaymsg != KNOWN_AWAY[server][nick][1]:
            msg = MSG_STILL_AWAY.format(pfx=config_get("print_prefix"), cc=color_nick(nick),
                                        nick=nick, sep=w.color("weechat.color.chat_delimiters"),
                                        default=w.color("default"), awaymsg=awaymsg,
                                        cc_away=w.color(config_get("color_away")),
                                        cc_pfx=w.color(config_get("color_prefix")))

            propagate_common_msg(server, nick, msg)
            KNOWN_AWAY[server][nick] = (datetime.now(), awaymsg)
        elif nick not in KNOWN_AWAY[server]:
            msg = MSG_AWAY.format(pfx=config_get("print_prefix"), cc=color_nick(nick), nick=nick,
                                  sep=w.color("weechat.color.chat_delimiters"),
                                  default=w.color("default"), awaymsg=awaymsg,
                                  cc_away=w.color(config_get("color_away")),
                                  cc_pfx=w.color(config_get("color_prefix")))

            KNOWN_AWAY[server][nick] = (datetime.now(), awaymsg)
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
    """ callback for a user parting a channel. invalidate cache entries """
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
        CACHE[server][nick].discard(channel)

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

    return w.WEECHAT_RC_OK

def irc_discon_cb(data, signal, signal_data):
    """ callback for when WeeChat disconnects from IRC. invalidate caches for server """
    if signal_data in CACHE:
        del CACHE[signal_data]

    for name in BUFFERS:
        if name.startswith(signal_data):
            del BUFFERS[name]

    return w.WEECHAT_RC_OK

def buffer_closed_cb(data, signal, signal_data):
    """ callback for when a buffer closes. used to invalidate query windows so we don't try to print
    to a closed query buffer.  """

    for name, ptr in BUFFERS.items():
        if ptr == signal_data:
            del BUFFERS[name]
            break

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
