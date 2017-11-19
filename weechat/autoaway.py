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
Automatically change AWAY status when WeeChat's screen is detached or a relay client is
(dis)connected.

Settings: plugins.var.python.autoaway.*
    message     -> away message used for setting /AWAY
    interval    -> how often to check if the screen is detached/if there are any relays connected

Python 3.6 or later required.
"""

try:
    import weechat as w
except ImportError:
    print("Script is meant to run under WeeChat.")
    raise

import os
import re
from typing import Any, Dict, Generator, Match, Set, Tuple  # pylint: disable=unused-import

SCRIPT_NAME = "autoaway"
SCRIPT_AUTHOR = "cruzr <sam@gentoo.party>"
SCRIPT_VERSION = "1"
SCRIPT_LICENSE = "MIT"
SCRIPT_DESC = "Update away status on screen detach/attach and relay (dis)connect"

w.register(SCRIPT_NAME, SCRIPT_AUTHOR, SCRIPT_VERSION,
           SCRIPT_LICENSE, SCRIPT_DESC, "", "")


DEFAULT_SETTINGS = {
    "message": ("detached from screen", "AWAY message when setting away status."),
    "interval": ("5", "Interval in seconds for checking if screen has attached or detached.")
}

SCREEN_SOCKET = ""
AWAY_SERVERS = set()  # type: Set[str]
TIMER_HOOK = None
RELAY_REGEX = re.compile(r"^[0-9]+\/"
                         r"(?:ipv4\.)?(?:ipv6\.)?(?:ssl\.)?"
                         r"(?P<protocol>irc|weechat)\.?(?P<name>[^ ]+)?\/.+$")


def config_get(name: str) -> str:
    """ retrieve value of a setting """
    return w.config_get_plugin(name)  # pylint: disable=E1101


def config_get_int(name: str) -> int:
    """ retrieve value of a setting then cast it to an int """
    return int(config_get(name))


def config_set_defaults() -> None:
    """ (first time run) create setting defaults and descriptoins """
    for option, (default, desc) in DEFAULT_SETTINGS.items():
        if not w.config_is_set_plugin(option):
            w.config_set_plugin(option, default)
            w.config_set_desc_plugin(option, desc)


def get_screen_socket() -> None:
    """ get path to WeeChat's screen session socket """
    global SCREEN_SOCKET

    sty = os.environ.get("STY", None)
    if sty:
        match = re.search(r"Sockets? in (/.+)\.",
                          os.popen("env LC_ALL=C screen -ls").read())
        if match:
            SCREEN_SOCKET = os.path.join(match.group(1), sty)


def is_screen_attached() -> bool:
    """ return boolean if someone is attached to our screen session """
    if not SCREEN_SOCKET:
        return False

    return os.access(SCREEN_SOCKET, os.X_OK)


def set_away(server: str, message: str) -> None:
    """ set away status on 'server' with 'message' """
    w.hook_signal_send("irc_input_send", w.WEECHAT_HOOK_SIGNAL_STRING,
                       f"{server};;priority_low;;/away {message}")
    AWAY_SERVERS.add(server)


def clear_away(server="") -> None:
    """ clear away status on 'server'. if no server parameter is specified, clears away status on
    all servers that *this script* set /AWAY on. """

    if server:
        w.hook_signal_send("irc_input_send", w.WEECHAT_HOOK_SIGNAL_STRING,
                           f"{server};;priority_low;;/away")
        AWAY_SERVERS.remove(server)
    else:
        for name in AWAY_SERVERS:
            w.hook_signal_send("irc_input_send", w.WEECHAT_HOOK_SIGNAL_STRING,
                               f"{name};;priority_low;;/away")
        AWAY_SERVERS.clear()


def relay_get_server(relay_ptr: str) -> Dict:
    """ get the server name for a relay client pointer """
    infolist = w.infolist_get("relay", relay_ptr, "")
    server = {}  # type: Dict[str, str]
    if infolist and w.infolist_next(infolist):
        match = RELAY_REGEX.search(w.infolist_string(infolist, "desc"))
        if match:
            server = match.groupdict()

        w.infolist_free(infolist)
    return server


def relays_connected(server: str) -> bool:
    """ true if there are any relays connected to 'server' """
    infolist = w.infolist_get("relay", '', '')
    found = False
    if infolist:
        while w.infolist_next(infolist):

            if found:
                break

            match = RELAY_REGEX.search(w.infolist_string(infolist, "desc"))
            if match:
                if match.group("protocol") == "weechat":
                    # weechat protocol is treated as connected to ALL servers
                    found = True
                    break
                elif match.group("protocol") == "irc" and match.group("name") == server:
                    found = True

        w.infolist_free(infolist)

    return found


def set_timer() -> None:
    """ set timer hook """
    global TIMER_HOOK

    if TIMER_HOOK:
        w.unhook(TIMER_HOOK)

    TIMER_HOOK = w.hook_timer(config_get_int(
        "interval") * 1000, 0, 0, "screen_check_timer_cb", "")


def get_connected_servers() -> Generator[str, None, None]:
    """ return a list of connected servers that are not AWAY """
    infolist = w.infolist_get("irc_server", "", "")
    if infolist:
        while w.infolist_next(infolist):
            if (w.infolist_integer(infolist, "is_connected")
                    and not w.infolist_integer(infolist, "is_away")):

                yield w.infolist_string(infolist, "name")
        w.infolist_free(infolist)


def script_init() -> None:
    """ called as soon as the script is loaded """
    get_screen_socket()
    config_set_defaults()
    set_timer()

# callbacks


def screen_check_timer_cb(data: str, remaining: int) -> int:
    """ called each timer timeout to check if WeeChat's screen is attached, and if there are any
    relay clients connected to a server. """
    if is_screen_attached():
        clear_away()
        return w.WEECHAT_RC_OK

    for server in get_connected_servers():
        if not relays_connected(server):
            set_away(server, config_get("message"))

    return w.WEECHAT_RC_OK


def config_changed_cb(data: str, option: str, value: str) -> int:
    """ callback for when a config option within WeeChat is changed. reset the timer hook for
    checking away status. """
    if option.endswith(".interval"):
        set_timer()

    return w.WEECHAT_RC_OK


def relay_authed_cb(data: str, signal: str, signal_data: str) -> int:
    """ callback for when a relay client successfully authenticates """
    match = relay_get_server(signal_data)
    if match:
        if match["protocol"] == "irc":
            name = match["name"]
            if name in AWAY_SERVERS:
                clear_away(name)
        elif match["protocol"] == "weechat":
            clear_away()

    return w.WEECHAT_RC_OK


w.hook_config(f"plugins.var.python.{SCRIPT_NAME}.*", "config_changed_cb", "")
w.hook_signal("relay_client_auth_ok", "relay_authed_cb", "")
script_init()
