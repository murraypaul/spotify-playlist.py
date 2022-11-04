from spotifytoolbox import myglobals

def list_to_comma_separated_string(list,key):
    artists = ""
    artists_links = ""
    for artist in list:
        if artists != "":
            artists = artists + ", "
            artists_links = artists_links + ", "
        artists = artists + artist[key]
        if myglobals.WebOutput != None and 'uri' in artist:
            artist_uri = artist['uri']
            artist_link = 'http://open.spotify.com/' + artist_uri[8:].replace(':','/')
            artist_name = artist[key]
            if 'id' in artist:
                artist_name = f"<a href='/show_artist?artistid={artist['id']}&app=spotify'>{artist_name}</a>"
            artists_links = artists_links + f"<a href='{artist_link}'><i class='fas fa-link'></i></a>{artist_name}"
        else:
            artists_links = artists_links + artist[key]
    return artists, artists_links

