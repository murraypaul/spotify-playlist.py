from spotifytoolbox import myglobals

def add_album_to_playlist(album,playlist):
    return add_album_to_playlist_byid(album['id'],playlist)

def add_album_to_playlist_byid(albumid,playlist):
    tracks = myglobals.SpotifyAPI.album_tracks(albumid)
    track_ids = []
    for track in tracks['items']:
        track_ids.append(track['id'])
    while tracks['next']:
        tracks = myglobals.SpotifyAPI.next(tracks)
        for track in tracks['items']:
            track_ids.append(track['id'])
    if myglobals.Args.dryrun:
        print("Would add tracks:")
        pprint.pprint(track_ids)
    else:
        myglobals.SpotifyAPI.user_playlist_add_tracks(myglobals.SpotifyAPI.me()['id'],playlist['id'],track_ids)
    return len(track_ids)

