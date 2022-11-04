from spotifytoolbox import myglobals

import spotipy

SpotifyRecentTrackCache = None

def init( CacheData ):
    global SpotifyRecentTrackCache
    SpotifyRecentTrackCache = {}
    tracks = myglobals.SpotifyAPI.current_user_recently_played()
    for track in tracks['items']:
        uri = track['track']['uri']
        if uri in SpotifyRecentTrackCache:
            SpotifyRecentTrackCache[uri] = SpotifyRecentTrackCache[uri] + 1
        else:
            SpotifyRecentTrackCache[uri] = 1


def query_recent():
    print(f"Cached {len(SpotifyRecentTrackCache)} unique tracks.")
#    pprint.pprint(SpotifyRecentTrackCache)

def get_playcount_str(artist,album,track,uri):
    playcount = "   "
    if SpotifyRecentTrackCache != None:
        entry = uri
        if entry in SpotifyRecentTrackCache:
#            print(f"Found {entry} in cache")
            playcount = "S%2.0d" % (SpotifyRecentTrackCache[entry])
    return playcount

