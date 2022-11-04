from spotifytoolbox import myglobals

from shutil import copyfile

TrackPlaylistCache = {}
PlaylistDetailsCache_ = {}

CachedData = None
SpotifyAPI = None
ConfigFolder = None

def init(CachedData_):
    global CachedData
    global SpotifyAPI
    global ConfigFolder
    CachedData = CachedData_
    SpotifyAPI = myglobals.SpotifyAPI
    ConfigFolder = myglobals.ConfigFolder
    init_playlist_cache()

def PlaylistDetailsCache():
    return PlaylistDetailsCache_

def init_playlist_cache_playlist_track(playlist,track):
    if 'track' in track:
        track = track['track']
    if 'id' in track:
        track_id = track['id']
        if track_id != None:
#            print(f"Adding track {track_id}")
            playlist_id = playlist['id']
            PlaylistDetailsCache_[playlist_id]['tracks'].append(track_id)

def init_playlist_cache_playlist(playlist):
#    print(f"Processing playlist {playlist['name']}")
    if playlist['id'] in PlaylistDetailsCache_:
        if playlist['snapshot_id'] != PlaylistDetailsCache_[playlist['id']]['snapshot_id']:
            print(f"Cached data for playlist {playlist['name']} is out of date, refreshing")
#            init_playlist_cache_purge_tracklist_playlist(playlist['id'])
        else:
            PlaylistDetailsCache_[playlist['id']]['active'] = True
#            print(f"Using cached data for playlist {playlist['name']}")
            return None

    PlaylistDetailsCache_[playlist['id']] = { 'name': playlist['name'], 'uri': playlist['uri'], 'snapshot_id': playlist['snapshot_id'], 'owner_id': playlist['owner']['id'], 'tracks': [], 'active': True }

    user_id = SpotifyAPI.me()['id']
    if playlist['owner']['id'] != user_id:
        tracks = { 'items': SpotifyAPI.playlist(playlist['id'])['tracks'] }
    else:
        tracks = SpotifyAPI.user_playlist_tracks(user_id,playlist['id'],limit=50)
    while tracks:
        for track in tracks['items']:
            init_playlist_cache_playlist_track(playlist,track)
        if 'next' in tracks and tracks['next']:
            tracks = SpotifyAPI.next(tracks)
        else:
            tracks = None

def init_playlist_cache_purge_tracklist_playlist(playlist_id):
    for track_id in TrackPlaylistCache:
        if playlist_id in TrackPlaylistCache[track_id]:
            TrackPlaylistCache[track_id][:] = [pid for pid in TrackPlaylistCache[track_id] if pid != playlist_id]

def init_playlist_cache_purge_tracklist():
    for playlist_id in PlaylistDetailsCache_:
        init_playlist_cache_purge_tracklist_playlist(playlist_id)

def init_playlist_cache_process_playlist(playlist_id):
    if not PlaylistDetailsCache_[playlist_id]['active']:
        print(f"Playlist {PlaylistDetailsCache_[playlist_id]['name']} is no longer availble on Spotify, ignoring")
    else:
#        count = 0
        for track_id in PlaylistDetailsCache_[playlist_id]['tracks']:
            if track_id == None:
                continue
            elif track_id in TrackPlaylistCache:
                TrackPlaylistCache[track_id].append(playlist_id)
            else:
                TrackPlaylistCache[track_id] = [playlist_id]
#            count = count + 1
#        print(f"Added playlist {playlist_id}:{PlaylistDetailsCache_[playlist_id]['name']} to {count} tracks")

def init_playlist_cache_process():
    for playlist_id in PlaylistDetailsCache_:
        init_playlist_cache_process_playlist(playlist_id)

def init_playlist_cache():
    init_playlist_cache_purge_tracklist()

    init_playlist_cache_from_file()

    user_id = SpotifyAPI.me()['id']
    playlists = SpotifyAPI.user_playlists(user_id)
    for playlist in playlists['items']:
        init_playlist_cache_playlist(playlist)
    while playlists['next']:
        playlists = SpotifyAPI.next(playlists)
        for playlist in playlists['items']:
            init_playlist_cache_playlist(playlist)

    # Might have special non-user playlists
    for playlist_id in PlaylistDetailsCache_:
        if PlaylistDetailsCache_[playlist_id]['owner_id'] != user_id and not PlaylistDetailsCache_[playlist_id]['active']:
            playlist = SpotifyAPI.playlist(playlist_id)
            if playlist != None:
                init_playlist_cache_playlist(playlist)
                init_playlist_cache_to_file()

    init_playlist_cache_process()

    init_playlist_cache_to_file()

def init_playlist_cache_from_file():
    try:
        with open(ConfigFolder / 'playlist_cache.add','r') as cachefile:
            for line in cachefile:
                line = line.strip()
                data = line.split(';; ')
                if len(data) >= 5:
                    PlaylistDetailsCache_[data[0]] = { 'name': data[1], 'uri': data[2], 'snapshot_id': data[3], 'owner_id': data[4], 'tracks': [], 'active': False }
                else:
                    print(f"Error reading {data}")
    except FileNotFoundError:
        pass

    try:
        with open(ConfigFolder / 'playlist_cache.txt','r') as cachefile:
            for line in cachefile:
                line = line.strip()
                data = line.split(';; ')
                if len(data) >= 5:
                    PlaylistDetailsCache_[data[0]] = { 'name': data[1], 'uri': data[2], 'snapshot_id': data[3], 'owner_id': data[4], 'tracks': [], 'active': False }
                    for i in range(5,len(data)):
                        PlaylistDetailsCache_[data[0]]['tracks'].append(data[i])
                else:
                    print(f"Error reading {data}")
    except FileNotFoundError:
        return None

    print(f"Read {len(PlaylistDetailsCache_)} entries from playlist details cache file.")

def init_playlist_cache_to_file():
    try:
        copyfile(ConfigFolder / 'playlist_cache.txt',ConfigFolder / 'playlist_cache.bak')
    except FileNotFoundError:
        pass
    try:
        count = 0
        with open(ConfigFolder / 'playlist_cache.txt','w') as cachefile:
            for entry in PlaylistDetailsCache_:
                playlist = PlaylistDetailsCache_[entry]
                if not playlist['active']:
                    continue
                line = f"{entry};; {playlist['name']};; {playlist['uri']};; {playlist['snapshot_id']};; {playlist['owner_id']}"
                for track in playlist['tracks']:
                    line = line + f";; {track}"
                line = line + "\n"
                cachefile.write(line)
                count = count + 1

        print(f"Wrote {count} entries to playlist details cache file.")
    except:
        print("Error writing playlist details cache file, restoring backup")
        copyfile(ConfigFolder / 'playlist_cache.bak',ConfigFolder / 'playlist_cache.txt')

    return None

def get_playlist_tracks(playlist_id):
    if playlist_id in PlaylistDetailsCache_:
        return PlaylistDetailsCache_['playlist_id']['tracks']
    else:
        playlist = SpotifyAPI.playlist(playlist_id)
        return playlist['tracks']

def get_playlists_for_single(result):
    playlists = []
    if TrackPlaylistCache != None and 'id' in result:
        playlist_ids = TrackPlaylistCache.get(result['id'],[])
        for playlist_id in playlist_ids:
            playlist = PlaylistDetailsCache_[playlist_id]
            if CachedData['Args'].show_playlist_onlyowned == False or playlist['owner_id'] == SpotifyAPI.me()['id']:
                if 'WebOutput' in CachedData and CachedData['WebOutput'] != None:
                    playlist_uri = playlist['uri']
                    playlist_link = 'http://open.spotify.com/' + playlist_uri[8:].replace(':','/')
                    playlists.append(f"<a href='{playlist_link}'><i class='fas fa-link'></i></a>{playlist['name']}")
                else:
                    playlists.append(playlist['name'])
    return playlists

