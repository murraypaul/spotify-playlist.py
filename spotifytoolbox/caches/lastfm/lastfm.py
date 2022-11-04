from spotifytoolbox import myglobals

import pylast
from collections import namedtuple
from shutil import copyfile

LastFM = None
LastFMUser = None
LastFMRecentTrackCache = None
LastFMRecentTrackCacheEntry = namedtuple("LastFMRecentTrackCacheEntry",["album","artist","track"])
LastFMRecentCount = -1
ConfigFolder = None

def init(CacheData):
    init_(CacheData['last_fm_client_id'], CacheData['last_fm_client_secret'], CacheData['last_fm_username'], myglobals.Args.last_fm_recent_count, myglobals.ConfigFolder)

def init_(last_fm_client_id,last_fm_client_secret,last_fm_username,last_fm_recent_count,config_folder):
    global LastFM, LastFMUser, LastFMRecentCount, ConfigFolder
    global ConfigFolder
    LastFM = pylast.LastFMNetwork(api_key=last_fm_client_id, api_secret=last_fm_client_secret, username=last_fm_username)
    LastFMUser = LastFM.get_user(last_fm_username)
    LastFMRecentCount = last_fm_recent_count
    ConfigFolder = config_folder
    print(f"ConfigFolder = {ConfigFolder}")
    init_recent_cache()

def query_recent():
#            printable = f"{track.playback_date}\t{track.track}"
#            print(str(i + 1) + " " + printable)
#            pprint.pprint(track)
    print(f"Cached {len(LastFMRecentTrackCache)} unique tracks.")
#    pprint.pprint(LastFMRecentTrackCache)

def init_recent_cache():
    global LastFMRecentTrackCache
    LastFMRecentTrackCache = {}
    orig_timestamp = None
    try:
        if LastFMRecentCount > 0:
            recent_tracks = LastFMUser.get_recent_tracks(limit=Args.last_fm_recent_count)
        else:
            orig_timestamp = init_recent_cache_from_file()
            recent_tracks = LastFMUser.get_recent_tracks(limit=None,time_from=orig_timestamp)
        print(f"Retrieved {len(recent_tracks)} from Last.FM")
        latest_timestamp = None
        for i, track in enumerate(recent_tracks):
    #        pprint.pprint(track)
            if track == None or track.track == None or track.track.artist == None or track.track.artist.name == None or track.track.title == None:
                print(f"Error with track {i}.")
                pprint.pprint(track)
            else:
    # Oldest scrobbles have no album details?
                if latest_timestamp == None:
                    latest_timestamp = track.timestamp
                album = track.album
                if album == None:
                    album = "";
                entry = LastFMRecentTrackCacheEntry(album=album.upper(),artist=track.track.artist.name.upper(),track=track.track.title.upper())
                if entry in LastFMRecentTrackCache:
                    LastFMRecentTrackCache[entry] = LastFMRecentTrackCache[entry] + 1
                else:
                    LastFMRecentTrackCache[entry] = 1
        if latest_timestamp == None:
            latest_timestamp = orig_timestamp
        if LastFMRecentCount < 0 and len(recent_tracks) > 0:
    #        print(f"New timestamp is {latest_timestamp}")
            init_recent_cache_to_file(latest_timestamp)
    except pylast.MalformedResponseError:
        pass

def init_recent_cache_from_file():
    last_timestamp = None
    try:
        with open(ConfigFolder / 'lastfm_cache.txt','r') as cachefile:
            last_timestamp = cachefile.readline().strip()
            while True:
                line = cachefile.readline()
                if not line:
                    break
                line = line.strip()
                data = line.split(';; ')
                if len(data) == 4:
                    entry = LastFMRecentTrackCacheEntry(album=data[0].upper(),artist=data[1].upper(),track=data[2].upper())
                    LastFMRecentTrackCache[entry] = (int)(data[3])
    except FileNotFoundError:
        return None

    print(f"Read {len(LastFMRecentTrackCache)} entries from LastFM cache file, last timestamp {last_timestamp}")

    if last_timestamp != None and last_timestamp != '':
        last_timestamp = (int)(last_timestamp) + 1
    return last_timestamp

def init_recent_cache_to_file(timestamp):
    try:
        copyfile(ConfigFolder / 'lastfm_cache.txt',ConfigFolder / 'lastfm_cache.bak')
    except FileNotFoundError:
        pass
    try:
        with open(ConfigFolder / 'lastfm_cache.txt','w') as cachefile:
            cachefile.write(f"{timestamp}\n")
            for entry in LastFMRecentTrackCache:
                line = f"{entry.album};; {entry.artist};; {entry.track};; {LastFMRecentTrackCache[entry]}\n"
                cachefile.write(line)

        print(f"Wrote {len(LastFMRecentTrackCache)} entries to LastFM cache file")
    except:
        print("Error writing cache file, restoring backup")
        copyfile(ConfigFolder / 'lastfm_cache.bak',ConfigFolder / 'lastfm_cache.txt')

    return None

def get_playcount_str(artist,album,track,uri):
    if LastFMRecentTrackCache != None:
#        pprint.pprint(LastFMRecentTrackCache)
        entry = LastFMRecentTrackCacheEntry(album=album.upper(),artist=artist.upper(),track=track.upper())
#        print(f"Searching for ('{album.upper()}','{artist.upper()}','{track.upper()}')")
        count = LastFMRecentTrackCache.get(entry,-1)
        if count > 0:
#            print("Found")
            return "L%2.0d" % (count)
        else: # Try with no album
            entry = LastFMRecentTrackCacheEntry(album='',artist=artist.upper(),track=track.upper())
#            print(f"Searching for ('{''}','{artist.upper()}','{track.upper()}')")
            count = LastFMRecentTrackCache.get(entry,-1)
            if count > 0:
#                print("Found")
                return "L%2.0d" % (count)
    return None

