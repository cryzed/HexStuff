import hexchat
import hexstuff

__module_name__ = 'Greentext'
__module_version__ = '1.0'
__module_description__ = '''Checks the beginning of outgoing text for the ">"
character and automatically modifies the text to display as green, emulating
the behavior of popular imageboards. The script attempts to ignore emoticons
beginning with the ">" character.

Author: cryzed <cryzed@googlemail.com>'''

PREFERENCES_PREFIX = 'greentext'
PREFERENCES = {
    'ignore_emoticons': True
}

preferences = hexstuff.Preferences(PREFERENCES_PREFIX, PREFERENCES)


def send_message(word, word_eol, userdata):
    message = word_eol[0]
    if message.startswith('>') and not (preferences.ignore_emoticons and len(message) > 1 and message[1] != ' ' and not message[1].isalpha()):
        message = hexstuff.color_text(message, hexstuff.COLOR_GREEN)
        hexchat.command('PRIVMSG %s :%s' % (hexchat.get_info('channel'), message))
        hexchat.emit_print('Your Message', hexchat.get_info('nick'), message)
        return hexchat.EAT_HEXCHAT


def main():
    hexchat.hook_command('', send_message)


if __name__ == '__main__':
    main()
