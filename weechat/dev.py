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

dev.py: script developer helper stuff

"""

# pylint: disable=W0603

try:
    import weechat as w
except ImportError:
    import sys
    print("Load this script from WeeChat.")
    sys.exit()

from typing import Callable, Dict, Tuple # pylint: disable=unused-import

SCRIPT_NAME = "dev"
SCRIPT_AUTHOR = "Samuel Hoffman <sam@gentoo.party>"
SCRIPT_VERSION = "1"
SCRIPT_LICENSE = "MIT"
SCRIPT_DESC = "Developer helper stuff."

w.register(SCRIPT_NAME, SCRIPT_AUTHOR, SCRIPT_VERSION,
           SCRIPT_LICENSE, SCRIPT_DESC, "", "")

EVENTS = {} # type: Dict[str, Callable]
SIG = {} # type: Dict[str, int]

def hook(command: str, nargs: int) -> Callable:
    """ decorator for hooking a function to a sub command """
    global EVENTS, SIG
    def ev_dec(func):
        """ the actual decorator """
        EVENTS[command] = func
        SIG[command] = nargs
        def wrapper(*args, **kwargs):
            """ wrapped function """
            return func(*args, **kwargs)
        return wrapper
    return ev_dec

def dev_cmd_cb(data, buf, args):
    """ callback for when the /infolist command is issued within WeeChat """
    args = args.split()

    if len(args) > 1:
        command = args.pop(0).lower()

        if command in EVENTS:
            if len(args) < SIG[command]:
                w.prnt('', f"not enough arguments for {command}")
                return w.WEECHAT_RC_ERROR
            elif len(args) > SIG[command]:
                w.prnt('', f"too many arguments for {command}")
                return w.WEECHAT_RC_ERROR

            EVENTS[command](*args)
            return w.WEECHAT_RC_OK

    return w.WEECHAT_RC_OK

@hook("free", 1)
def dev_free(ptr):
    """ free an infolist """
    w.infolist_free(ptr)
    w.prnt("", f"attempted to free infolist {ptr}")


@hook("fields", 1)
def dev_fields(ptr):
    """ list fields of an infolist """
    fields = w.infolist_fields(ptr)

    if not fields:
        w.prnt("", f"no fields for infolist {ptr}, maybe you need to move the cursor")
        return

    w.prnt("", f"fields for infolist {ptr}: {fields}")


@hook("reset", 1)
def dev_reset(ptr):
    """ reset cursor on an infolist """
    w.infolist_reset_item_cursor(ptr)
    w.prnt('', f"attempted to reset cursor for infolist {ptr}")


@hook("next", 1)
def dev_next(ptr):
    """ next an infolist """
    if w.infolist_next(ptr):
        w.prnt("", f"cursor moved to next item for infolist {ptr}")
    else:
        w.prnt("", f"cursor reached end of infolist {ptr}")


@hook("prev", 1)
def dev_pev(ptr):
    """ prev an infolist """
    if w.infolist_prev(ptr):
        w.prnt("", f"cursor moved to previous item for infolist {ptr}")
    else:
        w.prnt("", f"cursor reached beginning of infolist {ptr}")


@hook("integer", 2)
def dev_integer(ptr, field):
    """ /dev integer [ptr] [field] - get integer value """
    w.prnt("", f"infolist {ptr} field {field}: int {w.infolist_integer(ptr, field)}")


@hook("string", 2)
def dev_string(ptr, field):
    """ get string value from infolist """
    w.prnt("", f"infolist {ptr} field {field}: str {w.infolist_string(ptr, field)}")

@hook("pointer", 2)
def dev_pointer(ptr, field):
    """ get pointer value from infolist """
    w.prnt("", f"infolist {ptr} field {field}: ptr {w.infolist_pointer(ptr, field)}")

@hook("time", 2)
def dev_time(ptr, field):
    """ get time value from infolist """
    w.prnt("", f"infolist {ptr} field {field}: time {w.infolist_time(ptr, field)}")

@hook("get", 1)
def dev_get(name):
    """ get an infolist by name """
    infolist = w.infolist_get(name, "", "")
    if infolist:
        w.prnt("", f"got infolist {name}: {infolist}")
    else:
        w.prnt("", f"error occured getting infolist {name}")

@hook("iter", 1)
def dev_iter(ptr):
    """ iterate all fields of all items of an infolist pointer """
    buf = w.buffer_new(f"infolist {ptr}", "", "", "", "")

    infos = [] # type: List[Dict[str, Tuple]]

    while w.infolist_next(ptr):

        this = {}
        for field in w.infolist_fields(ptr).split(","):
            ftype, name = field.split(":", 1)
            if ftype == "i":
                this[name] = ftype, f"{w.color('*lightgreen') + str(w.infolist_integer(ptr, name))}"
            elif ftype == "s":
                this[name] = ftype, w.color('*214') + f"{w.infolist_string(ptr, name)!r}"
            elif ftype == "p":
                this[name] = ftype, f"{w.color('*yellow') + w.infolist_pointer(ptr, name)}"
            elif ftype == "t":
                this[name] = ftype, f"{w.color('magenta') + w.infolist_time(ptr, name)}"
            else:
                this[name] = "(not available in scripting API)"

        infos.append(this)

    for item in infos:

        pad = 0
        for key in item:
            if len(key) > pad:
                pad = len(key)

        for name, (ftype, value) in item.items():

            w.prnt(buf, w.color('blue') + f"{name: <{pad}}" + w.color('reset') +
                   f" = ({ftype}) {value}")

        w.prnt(buf, f"{w.color('red')}---")


    w.buffer_set(buf, "title", f"infolist {ptr}, iterated {len(infos)} item(s)")


w.hook_command("infolist",

               "manipulate infolists in weechat's memory. arbitrarily acting upon infolists in"
               " WeeChat's memory that you did not allocate yourself could be potentially"
               " dangerous. proceed with caution",

               "[free|fields|reset|next|prev [ptr]]"
               " | [integer|string|pointer|time|iter [ptr] [field]"
               " | get [infolist]",

               "   free: free an infolist pointer\n"
               " fields: list all fields of an infolist pointer\n"
               "  reset: reset the cursor for an infolist pointer\n"
               "integer: get a integer value from an infolist\n"
               " string: get a string value from an infolist\n"
               "pointer: get a pointer value from an infolist\n"
               "   time: get a time value from an infolist\n"
               "   iter: print all fields of all items from an infolist\n"
               "    get: get an infolist by name\n"
               "\n"
               "see <https://weechat.org/files/doc/stable/weechat_plugin_api.en.html#infolists>",

               "free || fields || reset || integer || string || pointer || buffer || time || iter"
               " || get %(infolists)",
               "dev_cmd_cb", "")
