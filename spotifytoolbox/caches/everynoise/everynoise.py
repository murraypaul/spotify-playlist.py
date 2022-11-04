from spotifytoolbox import myglobals

from shutil import copyfile
import pickle
import requests
from lxml import html, etree
from urllib.parse import quote_plus

EveryNoiseArtistToGenreCache = {}
ConfigFolder = None

def init(CacheData):
    global ConfigFolder
    ConfigFolder = myglobals.ConfigFolder
    init_everynoise(myglobals.Args.everynoise_update)

def init_everynoise(update):
    if update:
        clear_everynoise_cache()
    else:
        init_everynoise_from_file()

def clear_everynoise_cache():
    global EveryNoiseArtistToGenreCache
    EveryNoiseArtistToGenreCache.clear()

def init_everynoise_from_file():
    global EveryNoiseArtistToGenreCache
    EveryNoiseArtistToGenreCache.clear()
    try:
        with open(ConfigFolder / 'everynoise.pickle','rb') as cachefile:
            EveryNoiseArtistToGenreCache = pickle.load(cachefile)
    except FileNotFoundError:
        return None

    print(f"Read {len(EveryNoiseArtistToGenreCache)} entries from everynoise cache file.")

def init_everynoise_to_file():
    try:
        copyfile(ConfigFolder / 'everynoise.pickle',ConfigFolder / 'everynoise.bak')
    except FileNotFoundError:
        pass
    try:
        with open(ConfigFolder / 'everynoise.pickle','wb') as cachefile:
            pickle.dump(EveryNoiseArtistToGenreCache,cachefile)

        print(f"Wrote {len(EveryNoiseArtistToGenreCache)} entries to everynoise cache file.")
    except:
        print("Error writing everynoise file, restoring backup")
        copyfile(ConfigFolder / 'everynoise.pickle',ConfigFolder / 'everynoise.txt')

def get_genres_for_artist(artistid):
    global EveryNoiseArtistToGenreCache
    if artistid in EveryNoiseArtistToGenreCache:
        return EveryNoiseArtistToGenreCache[artistid]
    url = 'https://everynoise.com/research.cgi?mode=name&name=' + quote_plus('spotify:artist:' + artistid)
    print(url)
    page = requests.get(url)
    tree = html.fromstring(page.content)
    genre_entries = tree.xpath('//div[@class="note"]/a')
    genres = []
    for genre_entry in genre_entries:
        href = genre_entry.get("href")
        if "mode=genre" in href:
            new_link = f"<a href='https://everynoise.com/research.cgi{href}'>{genre_entry.text_content().strip()}</a>";
            genres.append(new_link)
    print(f"Retrieved {len(genres)} for {artistid} from everynoise")
    EveryNoiseArtistToGenreCache[artistid] = genres
    init_everynoise_to_file()
    return genres

