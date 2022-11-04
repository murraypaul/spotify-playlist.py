from spotifytoolbox import myglobals

from shutil import copyfile

GenresGood_ = []
GenresBad_ = []

ConfigFolder = None

def init(CacheData):
    global ConfigFolder
    ConfigFolder = myglobals.ConfigFolder
    init_genre_cache_from_file()

def update():
    init_genre_cache_to_file()

def init_genre_cache_from_file():
    GenresGood_.clear()
    GenresBad_.clear()
    try:
        with open(ConfigFolder / 'genres.txt','r') as cachefile:
            for line in cachefile:
                line = line.strip()
                if len(line) > 2:
                    if line[0] == '+':
                        GenresGood_.append(line[1:])
                    elif line[0] == '-':
                        GenresBad_.append(line[1:])
    except FileNotFoundError:
        return None

    print(f"Read {len(GenresGood_)+len(GenresBad_)} entries from genre file.")

def init_genre_cache_to_file():
    try:
        copyfile(ConfigFolder / 'genres.txt',ConfigFolder / 'genres.bak')
    except FileNotFoundError:
        pass
    try:
        with open(ConfigFolder / 'genres.txt','w') as cachefile:
            for entry in GenresGood_:
                line = f"+{entry}\n"
                cachefile.write(line)
            for entry in GenresBad_:
                line = f"-{entry}\n"
                cachefile.write(line)

        print(f"Wrote {len(GenresGood_)+len(GenresBad_)} entries to genre file.")
    except:
        print("Error writing genre file, restoring backup")
        copyfile(ConfigFolder / 'genre.bak',ConfigFolder / 'genre.txt')

    return None

def GenresGood():
    return GenresGood_

def GenresBad():
    return GenresBad_
