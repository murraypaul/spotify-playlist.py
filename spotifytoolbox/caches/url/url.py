from spotifytoolbox import myglobals

import time
from lxml import html, etree
import requests
import pickle
from shutil import copyfile

URLCache = {}
URLCacheTimeout = 24*60*60

ConfigFolder = None

def init(CacheData):
    global ConfigFolder
    ConfigFolder = myglobals.ConfigFolder
    init_urlcache_from_file()

def update():
    init_urlcache_to_file()

def init_urlcache_from_file():
    global URLCache
    URLCache.clear()
    try:
        with open(ConfigFolder / 'urlcache.pickle','rb') as cachefile:
            newURLCache = pickle.load(cachefile)
    except FileNotFoundError:
        return None

    timenow = int(time.time())
    for key, value in newURLCache.items():
        if value[0] < timenow - URLCacheTimeout:
            value[1] = None

    URLCache = { key: value for key, value in newURLCache.items() if value is not None }

    print(f"Read {len(URLCache)} entries from URL cache file, expired {len(newURLCache)-len(URLCache)} extries.")

def init_urlcache_to_file():
    try:
        copyfile(ConfigFolder / 'urlcache.pickle',ConfigFolder / 'urlcache.bak')
    except FileNotFoundError:
        pass
    try:
        with open(ConfigFolder / 'urlcache.pickle','wb') as cachefile:
            pickle.dump(URLCache,cachefile)

        print(f"Wrote {len(URLCache)} entries to URL cache file.")
    except:
        print("Error writing URL cache file, restoring backup")
        copyfile(ConfigFolder / 'urlcache.pickle',ConfigFolder / 'urlcache.txt')

def read_URL(url,cacheTimeout=URLCacheTimeout):
    timenow = int(time.time())
    cacheEntry = URLCache.get(url,[-1,None])
    if cacheEntry[1] == None or cacheEntry[0] < timenow - cacheTimeout:
#        print(f"No or expired cache for {url}")
        page = requests.get(url)
        URLCache[url] = [timenow,page.content]
        data = html.fromstring(page.content)
        init_urlcache_to_file()
        return data
    else:
#        print(f"Retrieved {url} from cache")
        return html.fromstring(cacheEntry[1])


