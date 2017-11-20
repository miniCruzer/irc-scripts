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
notify_print.py: print /notify signals to relevant IRC buffers
"""

try:
    from typing import Dict, Set  # pylint: disable=unused-import
except ImportError:
    pass

try:
    import weechat as w
except ImportError:
    print("Script is meant to run under WeeChat.")
    raise

SCRIPT_NAME = "notify_print"
SCRIPT_AUTHOR = "cruzr <sam@gentoo.party>"
SCRIPT_VERSION = "1"
SCRIPT_LICENSE = "MIT"
SCRIPT_DESC = "Print connect/disconnect messages to query buffers for /notify users."

w.register(SCRIPT_NAME, SCRIPT_AUTHOR, SCRIPT_VERSION,
           SCRIPT_LICENSE, SCRIPT_DESC, "", "")

if int(w.info_get("version", "")) < 0x00030800:
    w.prnt("This script is only compatible with WeeChat >= 0.3.8")
    

COMMON = set()  # type: Set[str]

def get_notify_list():
    """ load the current notify list """
    infolist = w.infolist_get("irc_notify", "", "")

    if not infolist:
        return

    COMMON.clear()
    while w.infolist_next(infolist):
        nick = w.infolist_string(infolist, "nick")
        server = w.infolist_string(infolist, "server_name")
        online = w.infolist_integer(infolist, "is_on_server")

        COMMON.add(server + "." + nick)

    w.infolist_next(infolist)


def hide_buffer_quit_join(data, modifier, modifier_data, string):

    plugin, name, tags = modifier_data.split(";")

    if name not in COMMON:
        return string

    if "irc_nick_back" in tags:
        return ""

    elif "irc_quit" in tags:
        return ""

    return string


def notify_join_cb(data, signal, signal_data):
    """ callback for when a user in WeeChat's notify list connects to IRC """
    server, nick = signal_data.split(",")
    buf = w.info_get("irc_buffer", server + ",," + nick)

    if not buf:
        return w.WEECHAT_RC_OK

    w.prnt(buf, "{}{}{}{} is back on the server".format(w.prefix("join"),
                                                        w.info_get("nick_color", nick),
                                                        nick, w.color("green")))

    return w.WEECHAT_RC_OK


def notify_quit_cb(data, signal, signal_data):
    """ callback for when a user in WeeChat's notify list quits IRC """
    server, nick = signal_data.split(",")

    buf = w.info_get("irc_buffer", server + ",," + nick)
    if buf is None:
        return w.WEECHAT_RC_OK

    w.prnt(buf, "{}{}{}{} has disconnected".format(w.prefix("quit"),
                                                   w.info_get("nick_color", nick),
                                                   nick, w.color("red")))

    return w.WEECHAT_RC_OK


def notify_cmd_cb(*args, **kwargs):
    get_notify_list()
    return w.WEECHAT_RC_OK


w.hook_signal("irc_notify_join", "notify_join_cb", "")
w.hook_signal("irc_notify_quit", "notify_quit_cb", "")
w.hook_modifier("weechat_print", "hide_buffer_quit_join", "")

w.hook_command_run("/notify add*", "notify_cmd_cb", "")
w.hook_command_run("/notify del*", "notify_cmd_cb", "")

get_notify_list()
