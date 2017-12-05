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
relay_activity.py: clear activity on buffers when an irc relay sends a message to a known buffer by
`/buffer switch`-ing to it.
"""

import re
from typing import Dict

import weechat as w

# pylint: disable=W0603


SCRIPT_NAME = "relay_activity"
SCRIPT_AUTHOR = "cruzr <sam@gentoo.party>"
SCRIPT_VERSION = "1"
SCRIPT_LICENSE = "MIT"
SCRIPT_DESC = "clear activity on a buffer when an IRC relay sends a message to it"

w.register(SCRIPT_NAME, SCRIPT_AUTHOR, SCRIPT_VERSION,
           SCRIPT_LICENSE, SCRIPT_DESC, "", "")

RELAY_REGEX = re.compile(r"^[0-9]+\/"
                         r"(?:ipv4\.)?(?:ipv6\.)?(?:ssl\.)?"
                         r"(?P<protocol>irc|weechat)\.?(?P<name>[^ ]+)?\/.+$")

IRC_RELAYS = 0


def relay_get_server(relay_ptr: str) -> Dict[str, str]:
    """ get the server/protocol name for a relay client pointer """
    infolist = w.infolist_get("relay", relay_ptr, "")
    server = {}  # type: Dict[str, str]
    if infolist and w.infolist_next(infolist):
        match = RELAY_REGEX.search(w.infolist_string(infolist, "desc"))
        if match:
            server = match.groupdict()

        w.infolist_free(infolist)
    return server


def relay_authed_cb(data: str, signal: str, signal_data: str) -> int:
    """ callback for when a relay has connected + authenticated to weechat """
    global IRC_RELAYS

    server = relay_get_server(signal_data)

    if server["protocol"] == "irc":
        IRC_RELAYS += 1

    return w.WEECHAT_RC_OK


def relay_discon(data: str, signal: str, signal_data: str) -> int: # pylint: disable=W0613
    """ callback for when a relay disconnects from weechat """
    global IRC_RELAYS

    server = relay_get_server(signal_data)

    if server["protocol"] == "irc":
        IRC_RELAYS -= 1

    return w.WEECHAT_RC_OK


def out_privmsg_cb(data: str, signal: str, signal_data: str) -> int:
    """ callback for when weechat sends data to a server """
    if IRC_RELAYS:

        server = signal.split(",")[0]
        ircmsg = w.info_get_hashtable(
            "irc_message_parse", {"message": signal_data})

        buf = w.info_get("irc_buffer", "{},{}".format(
            server, ircmsg["channel"]))
        if not buf:
            return w.WEECHAT_RC_OK

        name = ""
        infolist = w.infolist_get("buffer", buf, "")
        if infolist and w.infolist_next(infolist):
            name = w.infolist_string(infolist, "name")
            w.infolist_free(infolist)

        if name:
            w.command(buf, "/buffer " + name)

    return w.WEECHAT_RC_OK


def relays_connected() -> None:
    """ true if there are any relays connected to 'server' """
    global IRC_RELAYS

    infolist = w.infolist_get("relay", '', '')
    if infolist:
        while w.infolist_next(infolist):
            match = RELAY_REGEX.search(w.infolist_string(infolist, "desc"))
            if match:
                if match.group("protocol") == "irc":
                    IRC_RELAYS += 1
        w.infolist_free(infolist)


w.hook_signal("relay_client_auth_ok", "relay_authed_cb", "")
w.hook_signal("relay_client_disconnected", "relay_discon", "")
w.hook_signal("*,irc_out_privmsg", "out_privmsg_cb", "")
relays_connected()
