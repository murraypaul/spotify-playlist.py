from spotifytoolbox import myglobals

SearchOverrides = []

def init(CacheData):
    global SearchOverrides
    try:
        with open(myglobals.ConfigFolder / 'overrides.txt','r') as overridesfile:
            for line in overridesfile:
                line = line.strip()
                data = line.split(';; ')
                if len(data) >= 4:
                    track = data[0]
                    artist = data[1]
                    album = data[2]
                    uris = []
                    for i in range(3,len(data)):
                        if data[i] == "!None":
                            uris = None
                            break
                        else:
                            uris.append(data[i])
                    SearchOverrides.append([track,artist,album,uris])
    except FileNotFoundError:
        return None
    print(f"Read {len(SearchOverrides)} overrides from file")

# Returns list of albums, each with their tracks
#   [ [album_uri_1,[track_uri_1_1, track_uri_1_2,...]],
#     [album_uri_2,[track_uri_2_1, track_uri_2_2,...]] ]
def get_results_from_override_album(artist,album):
    uri = None
    found = False
    for entry in SearchOverrides:
#        if entry[0] == '*' and entry[1] == artist:
#            print("Found matching artist %s. Attempting to match '%s' and '%s'" % (artist, album, entry[2]))
        if entry[0] == '*' and entry[1] == artist and entry[2] == album:
            found = True
            uri_or_uris = entry[3]
            break

#    if found:
#        print(f"Override for {artist},{album} found. Result = {uri_or_uris}")
#    else:
#        print(f"Override for {artist},{album} not found.")

    # no ovverride
    if not found:
        return [[]]
    # override to skipped
    if uri_or_uris == None:
        return None

    uris = uri_or_uris
    if not isinstance(uri_or_uris,list):
        uris = [uri_or_uris]

    track_results = []
    try:
        for uri in uris:
            tracks = SpotifyAPI.album_tracks(uri)
            tids = []
            for track in tracks['items']:
                tids.append(track['id'])
            while tracks['next']:
                tracks = SpotifyAPI.next(tracks)
                for track in tracks['items']:
                    tids.append(track['id'])
            track_results.append([uri,tids])
    except spotipy.exceptions.SpotifyException:
        pass
    return track_results

def get_results_from_override(track_name,artist,album):
    if track_name == '*':
        return get_results_from_override_album(artist,album)
    else:
        return []

