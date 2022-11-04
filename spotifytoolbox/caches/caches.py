from spotifytoolbox import myglobals

from spotifytoolbox.caches import playlist
from spotifytoolbox.caches import spotify
from spotifytoolbox.caches.spotify import recent
from spotifytoolbox.caches.spotify import album
from spotifytoolbox.caches import genre
from spotifytoolbox.caches import watchlist
from spotifytoolbox.caches import lastfm
from spotifytoolbox.caches import search_overrides
from spotifytoolbox.caches import everynoise

def init( CacheData ):
    Args = myglobals.Args

    if Args.show_playlist_membership:
        playlist.init( CacheData )

    spotify.recent.init( CacheData )
    spotify.album.init( CacheData )

    genre.init( CacheData )

    watchlist.init( CacheData )

    if Args.last_fm and CacheData['last_fm_client_id'] != "" and CacheData['last_fm_client_secret'] != "" and CacheData['last_fm_username'] != "":
        lastfm.init( CacheData )

    if not Args.no_overrides:
        search_overrides.init( CacheData )

    if Args.everynoise:
        everynoise.init( CacheData )


