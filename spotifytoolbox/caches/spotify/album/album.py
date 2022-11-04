from spotifytoolbox import myglobals

import time

SpotifyAPI = None

SpotifyAlbumCache = {}
SpotifyAlbumCacheTimeout = 60*60

def init(CacheData):
    global SpotifyAPI
    SpotifyAPI = myglobals.SpotifyAPI

def update():
    return False

def get_by_id(id):
    timenow = int(time.time())
    cacheEntry = SpotifyAlbumCache.get(id,[-1,None])
    if cacheEntry[1] == None or cacheEntry[0] < timenow - SpotifyAlbumCacheTimeout:
#        print(f"No or expired cache for {id}")
        album = SpotifyAPI.album(id)
        SpotifyAlbumCache[id] = [timenow,album]
        time.sleep(0.1)
        return album
    else:
#        print(f"Retrieved {id} from cache")
        return cacheEntry[1]

