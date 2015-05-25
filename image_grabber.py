import concurrent.futures
import functools
import os
import queue
import traceback

import hexchat
import hexstuff

hexstuff.extend_module_search_path('image_grabber')
import bs4
import requests


__module_name__ = 'Image Grabber'
__module_version__ = '1.0.0'
__module_description__ = '''Attempts to automatically download images linked in
a channel or private message and saves them to the HexChat application data
directory. Successfully downloaded links will be colored green, others red.

Author: cryzed <cryzed@googlemail.com>'''

HOOK_PRINT_EVENTS = (
    'Channel Action', 'Channel Action Hilight', 'Channel Message',
    'Channel Msg Hilight', 'Private Action', 'Private Action to Dialog',
    'Private Message', 'Private Message to Dialog'
)
ILLEGAL_WINDOWS_FILENAME_CHARACTERS = '\/:*?"<>|'
REQUEST_CHUNK_SIZE = 1048576
OUTPUT_QUEUE_INTERVAL = 1000
PREFERENCES_PREFIX = 'image_grabber'
PREFERENCES = {
    'path': os.path.join(os.path.expanduser('~'), 'Image Grabber'),
    'file_exists_mode': 'rename',
    'save_by_nickname': True,
    'download_threads': 5,
    'user_agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:38.0) Gecko/20100101 Firefox/38.0',
    'request_timeout': 10,
    'debug': False
}

preferences = hexstuff.Preferences(PREFERENCES_PREFIX, PREFERENCES)
emitting = False
output_queue = queue.Queue()
thread_pool_executor = concurrent.futures.ThreadPoolExecutor(preferences.download_threads)


def safeguard(function):

    @functools.wraps(function)
    def wrapped_function(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except Exception as exception:
            if preferences.debug:
                traceback_string = ''.join(traceback.format_exception(
                    type(exception),
                    exception,
                    exception.__traceback__
                ))
                output_queue.put(lambda: hexchat.prnt(traceback_string))

    return wrapped_function


def get_valid_windows_filename(string_, replacement=''):
    return ''.join(
        replacement if character in ILLEGAL_WINDOWS_FILENAME_CHARACTERS
        else character for character in string_
    )


def download_response(response, filename):
    if preferences.file_exists_mode == 'skip' and os.path.exists(filename):
        return

    if preferences.file_exists_mode == 'rename':
        number = 2
        original_filename = filename
        while os.path.exists(filename):
            root, tail = os.path.splitext(original_filename)
            filename = ''.join((root, '_', str(number), tail))
            number += 1

    with open(filename, 'wb') as file:
        for chunk in response.iter_content(REQUEST_CHUNK_SIZE):
            file.write(chunk)


def match_imgur(url):
    return url.startswith('http://imgur.com/') or url.startswith('https://imgur.com/')


def download_imgur(url, path):
    session = requests.Session()
    session.headers = {'User-Agent': preferences.user_agent}

    response = session.get(url, timeout=preferences.request_timeout)
    response.raise_for_status()
    soup = bs4.BeautifulSoup(response.text)

    image_urls = set()
    for meta in soup('meta', property='og:image'):
        image_url = meta['content'].rsplit('?', 1)[0]
        if image_url in image_urls:
            continue

        image_urls.add(image_url)

    multiple_images = len(image_urls) > 1
    if multiple_images:
        album_id = url.rsplit('/', 1)[1].rsplit('#', 1)[0]
        path = os.path.join(path, album_id)
        if not os.path.exists(path):
            os.mkdir(path)

    for image_url in image_urls:
        filename = os.path.join(path, image_url.rsplit('/', 1)[1])
        if multiple_images and os.path.exists(filename):
            continue

        response = session.get(meta['content'], stream=True, timeout=preferences.request_timeout)
        download_response(response, filename)


SITE_HANDLERS = (
    (match_imgur, download_imgur),
)


@safeguard
def process_text_event(data, context):
    parts = data[1].split(' ')
    handlers = []
    responses = []
    for index, part in enumerate(parts):
        part = hexchat.strip(part).strip(',')
        if not part.startswith('http://') and not part.startswith('https://'):
            continue

        matched = False
        for match, download in SITE_HANDLERS:
            if match(part):
                parts[index] = hexstuff.color_text(part, hexstuff.COLOR_GREEN)
                handlers.append((download, part))
                matched = True
        if matched:
            continue

        try:
            response = requests.get(
                part,
                headers={'User-Agent': preferences.user_agent},
                stream=True,
                timeout=preferences.request_timeout
            )
            response.raise_for_status()
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            parts[index] = hexstuff.color_text(part, hexstuff.COLOR_LIGHT_RED)
            continue
        except requests.exceptions.HTTPError:
            response.close()
            parts[index] = hexstuff.color_text(part, hexstuff.COLOR_LIGHT_RED)
            continue

        if not response.headers.get('content-type', '').lower().startswith('image/'):
            response.close()
            continue

        parts[index] = hexstuff.color_text(part, hexstuff.COLOR_GREEN)
        responses.append(response)

    if not responses and not handlers:
        return

    message = ' '.join(parts)
    output_queue.put(lambda: context.emit_print('Generic Message', 'Image Grabber:', message))

    channel = context.get_info('channel')
    download_path = os.path.join(
        preferences.path,
        get_valid_windows_filename(context.get_info('network')),
        get_valid_windows_filename(channel)
    )

    if preferences.save_by_nickname and channel.startswith('#'):
        download_path = os.path.join(download_path, hexchat.strip(data[0]))

    if not os.path.exists(download_path):
        os.makedirs(download_path)

    for response in responses:
        filename = get_valid_windows_filename(response.url.rsplit('/', 1)[1])
        download_response(response, os.path.join(download_path, filename))

    for download, url in handlers:
        download(url, download_path)


def print_event_callback(word, word_eol, event_name):
    global emitting

    if emitting:
        return hexchat.EAT_NONE

    message = word[1]
    if 'http://' in message or 'https://' in message:
        thread_pool_executor.submit(
            process_text_event,
            word,
            hexchat.get_context()
        )

    emitting = True
    hexchat.emit_print(event_name, *word)
    emitting = False
    return hexchat.EAT_HEXCHAT


def output_queue_callback(userdata):
    global emitting

    emitting = True
    while True:
        try:
            function = output_queue.get_nowait()
        except queue.Empty:
            break

        function()
    emitting = False

    return True


def unload_callback(userdata):
    thread_pool_executor.shutdown()


def main():
    for event_name in HOOK_PRINT_EVENTS:
        hexchat.hook_print(event_name, print_event_callback, event_name)

    hexchat.hook_timer(OUTPUT_QUEUE_INTERVAL, output_queue_callback)
    hexchat.hook_unload(unload_callback)


if __name__ == '__main__':
    main()
