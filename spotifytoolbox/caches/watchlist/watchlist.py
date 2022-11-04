from spotifytoolbox import myglobals

from shutil import copyfile
from collections.abc import Mapping

Watchlist_ = []

ConfigFolder = None

def init(CacheData):
    global ConfigFolder
    ConfigFolder = myglobals.ConfigFolder
    init_watchlist_from_file()

def update():
    init_watchlist_to_file()

def Watchlist():
    return Watchlist_

def init_watchlist_from_file():
    Watchlist_.clear()
    try:
        with open(ConfigFolder / 'watchlist.txt','r') as cachefile:
            for line in cachefile:
                line = line.strip()
                data = line.split(';; ')
                if len(data) >= 6:
                    entry = { 'track': data[0], 'artist': data[1], 'album': data[2], 'release_date': data[3], 'genres': data[4].split(','), 'art': data[5], 'bandcamp_link': data[6] }
                    Watchlist_.append(entry)
#                    pprint.pprint(entry)
    except FileNotFoundError:
        print("Error reading Watchlist file")
        return None

    print(f"Read {len(Watchlist_)} entries from Watchlist file.")

def init_watchlist_to_file():
    try:
        copyfile(ConfigFolder / 'watchlist.txt',ConfigFolder / 'watchlist.bak')
    except FileNotFoundError:
        pass
    try:
        with open(ConfigFolder / 'watchlist.txt','w') as cachefile:
            for entry in Watchlist_:
                line = f"{entry['track']};; {entry['artist']};; {entry['album']};; {entry['release_date']};; {','.join(entry['genres'])};; {entry['art']};; {entry['bandcamp_link']};; <end>\n"
                cachefile.write(line)

        print(f"Wrote {len(Watchlist_)} entries to Watchlist file.")
    except:
        print("Error writing Watchlist file, restoring backup")
        copyfile(ConfigFolder / 'watchlist.bak',ConfigFolder / 'watchlist.txt')

    return None

def is_in(first_arg,artist=None,album=None):
#    pprint.pprint(first_arg)
    entryIn = {}
    if isinstance(first_arg, Mapping):
        entryIn = first_arg
    else:
        entryIn = { 'track': first_arg, 'artist': artist, 'album': album }
    for entry in Watchlist_:
        if entry['track'].lower() == entryIn['track'].lower() and entry['artist'].lower() == entryIn['artist'].lower() and entry['album'].lower() == entryIn['album'].lower():
            return entry
    return None

def add(entry):
    Watchlist_.append(entry)

def remove(entryIn):
    entry = is_in(entryIn)
    if entry:
        Watchlist_.remove(entry)
        return True
    return False

