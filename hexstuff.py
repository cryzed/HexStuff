import hexchat

import json
import os
import sys


BOLD_BYTE = '\x02'
COLOR_BYTE = '\x03'
BEEP_BYTE = '\x07'
HIDDEN_BYTE = '\x10'
ORIGINAL_ATTRIBUTES_BYTE = '\x17'
REVERSE_COLOR_BYTE = '\x26'
ITALICS_BYTE = '\x35'
UNDERLINE_BYTE = '\x37'

COLOR_WHITE = '00'
COLOR_BLACK = '01'
COLOR_BLUE = '02'
COLOR_GREEN = '03'
COLOR_LIGHT_RED = '04'
COLOR_BROWN = '05'
COLOR_PURPLE = '06'
COLOR_ORANGE = '07'
COLOR_YELLOW = '08'
COLOR_LIGHT_GREEN = '09'
COLOR_CYAN = '10'
COLOR_LIGHT_CYAN = '11'
COLOR_LIGHT_BLUE = '12'
COLOR_PINK = '13'
COLOR_GREY = '14'
COLOR_LIGHT_GREY = '15'


def bold_text(text):
    return ''.join((BOLD_BYTE, text, BOLD_BYTE))


def color_text(text, color):
    return ''.join((COLOR_BYTE, color, text, COLOR_BYTE))


def hide_text(text):
    return ''.join((HIDDEN_BYTE, text, HIDDEN_BYTE))


def original_attributes_text(text):
    return ''.join((ORIGINAL_ATTRIBUTES_BYTE, text, ORIGINAL_ATTRIBUTES_BYTE))


def reverse_color_text(text):
    return ''.join((REVERSE_COLOR_BYTE, text, REVERSE_COLOR_BYTE))


def italics_text(text):
    return ''.join((ITALICS_BYTE, text, ITALICS_BYTE))


def underline_text(text):
    return ''.join((UNDERLINE_BYTE, text, UNDERLINE_BYTE))


class Preferences:
    _initialized = False

    def __init__(self, prefix, defaults, write_defaults=True):
        self.prefix = prefix
        self.defaults = defaults
        self._initialized = True

        if write_defaults:
            for name, default in defaults.items():
                key = '_'.join((prefix, name))
                if hexchat.get_pluginpref(key) is None:
                    hexchat.set_pluginpref(key, json.dumps(default))

    def __getattr__(self, name):
        value = hexchat.get_pluginpref('_'.join((self.prefix, name)))

        if value is None:
            return self.defaults[name]

        # HexChat attempts to automatically convert strings to integers
        return json.loads(str(value))

    def __setattr__(self, name, value):
        if not self._initialized:
            object.__setattr__(self, name, value)
        else:
            hexchat.set_pluginpref('_'.join((self.prefix, name)), json.dumps(value))


def extend_module_search_path(name=None):
    site_packages_path = os.path.join(hexchat.get_info('configdir'), 'addons', 'site-packages')
    if name:
        site_packages_path = os.path.join(site_packages_path, name)

    sys.path.insert(0, site_packages_path)
