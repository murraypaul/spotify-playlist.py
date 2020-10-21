import argparse
import logging
import pprint
import csv
import time
from lxml import html, etree
import requests
import datetime
from collections import namedtuple
from collections.abc import Mapping
from shutil import copyfile
from sanitize_filename import sanitize
from pathlib import Path
import random
import pickle

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, quote_plus, unquote_plus, parse_qs
import pydnsbl

import json

import pylast

logger = logging.getLogger('myapp')
logging.basicConfig(level='INFO')

ConfigFolder = Path(".spotify-toolbox")

SpotifyAPI = None
Args = None

LastFMRecentTrackCache = None
LastFMRecentTrackCacheEntry = namedtuple("LastFMRecentTrackCacheEntry",["album","artist","track"])
SpotifyRecentTrackCache = None

SearchOverrides = []

TrackPlaylistCache = {}
PlaylistDetailsCache = {}

WebOutput = None

GenresGood = []
GenresBad = []

URLCache = {}
URLCacheTimeout = 24*60*60

SpotifyAlbumCache = {}
SpotifyAlbumCacheTimeout = 60*60

IPBlacklistChecker = pydnsbl.DNSBLIpChecker()
IPBlacklist = {}

Watchlist = []

def check_IP(ip):
    if ip not in IPBlacklist:
        print(f"Checking IP {ip}")
        result = IPBlacklistChecker.check(ip)
        print(f"Adding IP cache ({ip},{result.blacklisted})")
        IPBlacklist[ip] = result.blacklisted

    return IPBlacklist[ip] == False

def override_IP_block(ip,value):
    IPBlacklist[ip] = value

def read_URL(url):
    timenow = int(time.time())
    cacheEntry = URLCache.get(url,[-1,None])
    if cacheEntry[1] == None or cacheEntry[0] < timenow - URLCacheTimeout:
#        print(f"No or expired cache for {url}")
        page = requests.get(url)
        URLCache[url] = [timenow,page.content]
        data = html.fromstring(page.content)
        init_urlcache_to_file()
        return data
    else:
#        print(f"Retrieved {url} from cache")
        return html.fromstring(cacheEntry[1])

def read_SpotifyAlbum(id):
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

def get_args():
    parser = argparse.ArgumentParser(description='Spotify toolbox')
    cmdgroup = parser.add_mutually_exclusive_group(required=True)
    cmdgroup.add_argument('--create', required=False, action="store_true", help='Create playlist')
    cmdgroup.add_argument('--delete', required=False, action="store_true", help='Delete playlist')
    cmdgroup.add_argument('--set-description', required=False, action="store_true", help='Set description for playlist')
    cmdgroup.add_argument('--list', required=False, action="store_true", help='List items from playlist')
    cmdgroup.add_argument('--find', required=False, action="store_true", help='Search for album (requires --artist and --album, --track is optional)')
    cmdgroup.add_argument('--add', required=False, action="store_true", help='Add tracks to end of playlist (requires --artist and --album, --track is optiona)')
    cmdgroup.add_argument('--query', required=False, help='Query API information')
    cmdgroup.add_argument('--server', type=int, required=False, help='Start web server on specified port')
    cmdgroup.add_argument('--export', required=False, action="store_true", help='Export tracks to CSV file')

    creategroup = parser.add_mutually_exclusive_group(required=False)
    creategroup.add_argument('--file', required=False, help='Import tracks from csv file')
    creategroup.add_argument('--url', required=False, help='Import tracks from url')

    urltypegroup = parser.add_mutually_exclusive_group(required=False)
    urltypegroup.add_argument('--metalstorm-top', required=False, action="store_true", help='Url is MetalStorm Top-X list')
    urltypegroup.add_argument('--metalstorm-releases', required=False, action="store_true", help='Url is MetalStorm new releases list')
    urltypegroup.add_argument('--metalstorm-list', required=False, action="store_true", help='Url is MetalStorm user created list')

    parser.add_argument('--playlist', required=False, help='Only songs played from specified playlist')

    selectgroup = parser.add_mutually_exclusive_group(required=False)
    selectgroup.add_argument('--all', required=False, action="store_true", help='All tracks from playlist')
    selectgroup.add_argument('--recent', required=False, action="store_true", help='Only recently played tracks from playlist')
    selectgroup.add_argument('--first-albums', type=int, required=False, help='Only tracks from the first N albums on the playlist')
    selectgroup.add_argument('--recommendations', required=False, action="store_true", help='Recommended tracks')

    parser.add_argument('--artist', required=False )
    parser.add_argument('--album', required=False )
    parser.add_argument('--track_name', required=False )
    parser.add_argument('--genre', required=False )

    parser.add_argument('--dryrun', required=False, action="store_true", help='Do not change anything, just log what would happen')
    parser.add_argument('--interactive', required=False, action="store_true", help='Prompt for choice if there are duplicates found')
    parser.add_argument('--show-search-details', required=False, action="store_true", help='Show searches and raw results')
    parser.add_argument('--show-tracks', required=False, action="store_true", help='Show tracks when normally only albums would be shown')
    parser.add_argument('--show-playlist-membership', required=False, action="store_true", help='Show which playlists tracks belong to')
    parser.add_argument('--show-playlist-onlyowned', required=False, action="store_true", help='Only show playlist membership for playlists created by the user')
    parser.add_argument('--no-overrides', required=False, action="store_true", help='Do not use overrides file')

    marketgroup = parser.add_mutually_exclusive_group(required=False)
    marketgroup.add_argument('--no-market', required=False, action="store_true", help='Do not limit searches by user market')
    marketgroup.add_argument('--market', required=False, help='Specify market')

    parser.add_argument('--last-fm', required=False, action="store_true", help='Enable Last.FM integration')
    parser.add_argument('--last-fm-recent-count', type=int, default=-1, required=False, help='How many recent tracks to retrieve from Last.FM')

    parser.add_argument('--bandcamp', required=False, action="store_true", help='Enable bandcamp integration')

    parser.add_argument('--server-default-playlist', required=False, help='Default playlist to add tracks to')
    parser.add_argument('--server-blacklist', required=False, help='Check incoming IP addresses against blacklist')
    parser.add_argument('--server-whitelist-ip', required=False, help='Whitelist specified IP address')

    return parser.parse_args()

def name_matches(left,right):
    left = left.lower()
    right = right.lower()
    left = left.replace('&','and')
    right = right.replace('&','and')
    left = left.replace(':',' ')
    right = right.replace(':',' ')
    left = left.replace('-',' ')
    right = right.replace('-',' ')
    left = left.replace('  ',' ')
    right = right.replace('  ',' ')

    #    print("Comparing '%s' with '%s'" % (left, right))
    return left == right

def get_search_exact(track_name,artist,album):
    if Args.show_search_details:
        print("Searching for (%s;%s;%s)" % (track_name,artist,album))
    market = 'from_token'
    if Args.market:
        market = Args.market
    if track_name == '*':
        search_str = "artist:%s album:%s" % (artist, album)
        try:
            if Args.no_market:
                results = SpotifyAPI.search(search_str,type='album')
            else:
                results = SpotifyAPI.search(search_str,type='album',market=market)
        except spotipy.exceptions.SpotifyException:
            return []
        if Args.show_search_details:
            print("Search '%s' returned %d results" % (search_str, len(results['albums']['items'])))
        return results['albums']['items']
    else:
        search_str = "track:%s artist:%s album:%s" % (track_name, artist, album)
        try:
            if Args.no_market:
                results = SpotifyAPI.search(search_str,type='track')
            else:
                results = SpotifyAPI.search(search_str,type='track',market=market)
        except spotipy.exceptions.SpotifyException:
            return []
        if Args.show_search_details:
            print("Search '%s' returned %d results" % (search_str, len(results['tracks']['items'])))
        return results['tracks']['items']

def remove_punctuation(text):
    if "." in text:
        text = text.replace("."," ")
    return text

def remove_featuring(text):
    if "(feat" in text:
        text = text.partition("(feat")[0]
    if "(Feat" in text:
        text = text.partition("(Feat")[0]
    return text

def remove_brackets(text):
    if "(" in text:
        text = text.partition("(")[0]
    return text

def list_to_comma_separated_string(list,key):
    artists = ""
    artists_links = ""
    for artist in list:
        if artists != "":
            artists = artists + ", "
            artists_links = artists_links + ", "
        artists = artists + artist[key]
        if WebOutput != None and 'uri' in artist:
            artist_uri = artist['uri']
            artist_link = 'http://open.spotify.com/' + artist_uri[8:].replace(':','/')
            artists_links = artists_links + f"<a href='{artist_link}'><i class='fas fa-link'></i></a>{artist[key]}"
        else:
            artists_links = artists_links + artist[key]
    return artists, artists_links

def print_track(result,i,album=None):
    track_name = result['name']
    track_uri = result['uri']
    if track_uri != "":
        track_link = 'http://open.spotify.com/' + track_uri[8:].replace(':','/')
    else:
        track_link = None
    artists, artists_with_links = list_to_comma_separated_string(result['artists'],'name')
    if album == None:
        album = result['album']
    album_name = album['name']
    album_uri = album['uri'] if 'uri' in album else None
    album_link = album['link'] if 'link' in album else ""
    if album_uri != None:
        album_link = 'http://open.spotify.com/' + album_uri[8:].replace(':','/')
    duration_ms = result['duration_ms']
    duration_min = duration_ms / 60000
    duration_totalsec = duration_ms / 1000
    duration_sec = duration_totalsec % 60
    explicit = " "
    if result['explicit']:
        explicit = "Y"
    playcount = get_playcount_str(artists,album_name,track_name,result['uri'])
    popularity = -1
    if 'popularity' in result:
        popularity = result['popularity']
    playlists = []
    if TrackPlaylistCache != None and 'id' in result:
        playlist_ids = TrackPlaylistCache.get(result['id'],[])
        for playlist_id in playlist_ids:
            playlist = PlaylistDetailsCache[playlist_id]
            if Args.show_playlist_onlyowned == False or playlist['owner_id'] == SpotifyAPI.me()['id']:
                if WebOutput != None:
                    playlist_uri = playlist['uri']
                    playlist_link = 'http://open.spotify.com/' + playlist_uri[8:].replace(':','/')
                    playlists.append(f"<a href='{playlist_link}'><i class='fas fa-link'></i></a>{playlist['name']}")
                else:
                    playlists.append(playlist['name'])
    if WebOutput != None:
        WebOutput.wfile.write((f"<td class='track-number'>{i}</td>\n").encode("utf-8"))
        WebOutput.wfile.write((f"<td class='play-count'>{playcount}</td>\n").encode("utf-8"))
        if track_link != None:
            WebOutput.wfile.write((f"<td class='track-name'><a href='{track_link}'><i class='far fa-play-circle'></i></a>{track_name}</td>\n").encode("utf-8"))
        else:
            WebOutput.wfile.write((f"<td class='track-name'>{track_name}</td>\n").encode("utf-8"))
        WebOutput.wfile.write((f"<td class='artist'>{artists_with_links}</td>\n").encode("utf-8"))
        WebOutput.wfile.write((f"<td class='album'><a href='{album_link}'><i class='fas fa-link'></i></a>{album_name}</td>\n").encode("utf-8"))
        WebOutput.wfile.write((f"<td class='playlist'>").encode("utf-8"))
        for playlist in playlists:
            WebOutput.wfile.write((f"{playlist}<br/>").encode("utf-8"))
        WebOutput.wfile.write((f"</td>\n").encode("utf-8"))
        WebOutput.wfile.write((f"<td class='track-uri'>{result['uri']}</td>\n").encode("utf-8"))
    else:
        playlist = ""
        if len(playlists) > 0:
            playlist = playlists[0]
        if 0:
            print("* %s - %s" % (result['name'], artists))
        elif Args.show_playlist_membership:
            print("                 %02d: %3.3s %24.24s; %24.24s; %36.36s; %24.24s; %8.8s %1.1s %04.04s %02d/%02d %02d:%02d %02d %s" % (
                    i,
                    playcount,
                    track_name,
                    artists,
                    album_name,
                    playlist,
                    album['album_type'],
                    explicit,
                    album['release_date'][0:4] if album['release_date'] is not None else "",
                    result['track_number'],
                    album['total_tracks'] if 'total_tracks' in album else 0,
                    duration_min,
                    duration_sec,
                    popularity,
                    result['uri']
                    ))
            if len(playlists) > 1:
                for pi in range(1,len(playlists)):
                    print("                     %3.3s %24.24s  %24.24s  %36.36s  %24.24s" % (
                        "",
                        "",
                        "",
                        "",
                        playlists[pi]
                        ))
        else:
            print("                 %02d: %3.3s %48.48s; %26.26s; %36.36s; %8.8s %1.1s %04.04s %02d/%02d %02d:%02d %02d %s" % (
                    i,
                    playcount,
                    track_name,
                    artists,
                    album_name,
                    album['album_type'],
                    explicit,
                    album['release_date'][0:4] if album['release_date'] is not None else "",
                    result['track_number'],
                    album['total_tracks'] if 'total_tracks' in album else 0,
                    duration_min,
                    duration_sec,
                    popularity,
                    result['uri']
                    ))


def select_duplicate(results,track_name,artist_name,album_name,ask=True,start_count=0):
    if WebOutput == None:
        print("Results for              %24.24s; %24.24s; %48.48s" % (track_name, artist_name, album_name))
    for i in range(len(results)):
        result = results[i]
        if 'track' in result:
            result = result['track']
        if WebOutput != None:
            WebOutput.wfile.write(b"<tr>\n")
        print_track(result,start_count+i+1)
        if WebOutput != None:
            WebOutput.wfile.write(b"</tr>")
    if ask:
        try:
            choice = int(input("Enter choice: "))
            if choice > 0 and choice <= len(results):
                return [results[choice-1]]
        except ValueError:
            pass
    return []

def print_album(count,album,track_count=-1):
    artists = list_to_comma_separated_string(album['artists'],'name')[0]
    count_source = " "
    if track_count == -1:
        track_count = 0
        for i,track in enumerate(SpotifyAPI.album_tracks(album['id'])['items']):
            playcount_str = get_playcount_str(artists,album['name'],track['name'],track['uri'])
            if playcount_str != None and playcount_str != "   ":
                count_source = playcount_str[:1]
                track_count = track_count + 1

    print_album_details(
        count,
        artists,
        album['name'],
        album['album_type'],
        album['release_date'][0:4],
        album['total_tracks'] if 'total_tracks' in album else 0,
        track_count,
        album['uri'],
        count_source
        )


def print_album_details(count,artist,album,type,release_date,total_tracks,track_count,uri,count_source=" "):
    if track_count != None and track_count >= 0:
        print("                 %02d:    %24.24s; %48.48s; %12.12s %04.04s %1.1s%02d/%02d %s" % (
                count,
                artist,
                album,
                type,
                release_date,
                count_source,
                track_count,
                total_tracks,
                uri
                ))
    else:
        print("                 %02d:    %24.24s; %48.48s; %12.12s %04.04s    %02d %s" % (
                count,
                artist,
                album,
                type,
                release_date,
                total_tracks,
                uri
                ))

def select_duplicate_album(results,artist_name,album_name,ask=True):
    print("Results for          %24.24s; %48.48s" % (artist_name, album_name))
    for i in range(len(results)):
        album = results[i]
        print_album(i+1,album)
    if ask:
        try:
            choice = int(input("Enter choice: "))
            if choice > 0 and choice <= len(results):
                return [results[choice-1]]
        except ValueError:
            pass
    return []

def select_duplicate_artist(results,artist_name,ask=True):
    print("Results for          %24.24s" % (artist_name))
    for i in range(len(results)):
        artist = results[i]
        print("                 %02d: %24.24s; %02d %s" % (
                i+1,
                artist['name'],
                artist['popularity'],
                artist['uri']
                ))
    if ask:
        try:
            choice = int(input("Enter choice: "))
            if choice > 0 and choice <= len(results):
                return [results[choice-1]]
        except ValueError:
            pass
    return []

def is_selected_playlist(playlist,id_or_name=None):
    if not id_or_name:
        id_or_name = Args.playlist
    if playlist['name'] == id_or_name:
        return True
    if playlist['id'] == id_or_name:
        return True;
    else:
        return False

def get_playlist(playlist_id_or_name):
    try:
        playlist = SpotifyAPI.playlist(playlist_id_or_name)
        if playlist:
            return playlist
    except:
        pass

    user_id = SpotifyAPI.me()['id']
    playlists = SpotifyAPI.user_playlists(user_id)
    for playlist in playlists['items']:
        if is_selected_playlist(playlist,playlist_id_or_name):
            return playlist
    while playlists['next']:
        playlists = SpotifyAPI.next(playlists)
        for playlist in playlists['items']:
            if is_selected_playlist(playlist,playlist_id_or_name):
                return playlist
    return None

def process_tracks(tracks):
    show_tracks = []
    for entry in tracks:
        context = None
        if 'context' in entry:
            context = entry['context']
        show = Args.list
        if Args.playlist:
            if not context or context['type'] != 'playlist':
                show = False
            else:
                playlist = SpotifyAPI.playlist(context['uri'])
                if not is_selected_playlist(playlist):
                    show = False
                else:
                    if Args.delete:
                        tracks_to_remove = []
                        tracks_to_remove.append(entry['track']['id'])
                        if Args.dryrun:
                            print("Would remove tracks:")
                            pprint.pprint(tracks_to_remove)
                        else:
                            SpotifyAPI.user_playlist_remove_all_occurrences_of_tracks(SpotifyAPI.me()['id'],playlist['id'],tracks_to_remove)
        if show:
            show_tracks.append(entry)
    if Args.list and len(show_tracks) > 0:
        select_duplicate(show_tracks,'','','',False)


def process_first_albums(playlist):
    if playlist['tracks']['total'] > 0:
        new_album_count = 1
        tracks = SpotifyAPI.user_playlist_tracks(SpotifyAPI.me()['id'],playlist['id'],limit=50)
        firsttrack = tracks['items'][0]['track']
        album = firsttrack['album']
        first_album_tracks = []
        while True:
            for track in tracks['items']:
                if track['track']['album'] == album:
                    first_album_tracks.append(track)
                else:
                    if not Args.show_tracks:
                        print_album(new_album_count,album,len(first_album_tracks))
                    new_album_count = new_album_count + 1

                    if Args.delete:
                        tracks_to_remove = []
                        for remove_track in first_album_tracks:
                            tracks_to_remove.append(remove_track['track']['id'])
                            if Args.dryrun:
                                print_track(remove_track['track'],len(tracks_to_remove))
                        if Args.dryrun:
                             None
                        else:
                            SpotifyAPI.user_playlist_remove_all_occurrences_of_tracks(SpotifyAPI.me()['id'],playlist['id'],tracks_to_remove)
#                    elif Args.list:
#                        select_duplicate(first_album_tracks,'','','',False)

                    if new_album_count > Args.first_albums:
                        break;
                    album = track['track']['album']
                    if not Args.show_tracks:
                        first_album_tracks = []
                    first_album_tracks.append(track)

            if new_album_count > Args.first_albums:
                break;
            elif tracks['next']:
                tracks = SpotifyAPI.next(tracks)
            else:
                break;
        if Args.show_tracks:
            for i,track in enumerate(first_album_tracks):
                print_track(track['track'],i+1)

def get_results_for_track(track_name,artist,album,show_list,prompt_for_choice):
    search_str = "track:%s artist:%s album:%s" % (track_name, artist, album)

    results = get_search_exact(track_name,artist,album)
    result_count = len(results)

    # If not found, try various changes
    if result_count == 0:
        results_artist_punctuation = get_search_exact(track_name,remove_punctuation(artist),album)
        results.extend(results_artist_punctuation)

        results_track_featuring = get_search_exact(remove_featuring(track_name),artist,album)
        results.extend(results_track_featuring)

        results_all_brackets = get_search_exact(remove_brackets(track_name),remove_brackets(artist),remove_brackets(album))
        results.extend(results_all_brackets)

        result_count = len(results)

    # If there is a duplicate, skip non-playable tracks
    if result_count > 1:
        new_base = []
        for result in results:
            if result['is_playable'] == 'True':
                new_base.append(result)
        if len(new_base) > 0:
            results = new_base
            result_count = len(results)

    # If there is a duplicate, see if there is an obvious single match
    if result_count > 1:
        new_base = []
        for result in results:
#                    print("Track name is *%s*" % (result['name']))
            if result['name'] == track_name: #and result['artists']['name'] == artist and result['album']['name'] == album:
                new_base.append(result)
        if len(new_base) > 0:
            results = new_base
            result_count = len(results)

    # If there is a duplicate, prefer album tracks to singles
    if result_count > 1:
        new_base = []
        for result in results:
#                    print("Track name is *%s*" % (result['name']))
            if result['album']['album_type'] ==  'album':
                new_base.append(result)
        if len(new_base) == 1:
            results = new_base
            result_count = len(results)

    # If there is a duplicate, prefer exact match on album
    if result_count > 1:
        new_base = []
        for result in results:
            if result['album']['name'] == album:
                new_base.append(result)
        if len(new_base) == 1:
            results = new_base
            result_count = len(results)

    # If there is a duplicate, prefer non-censored
    if result_count > 1:
        new_base = []
        for result in results:
            if result['explicit'] == 'True':
                new_base.append(result)
        if len(new_base) == 1:
            results = new_base
            result_count = len(results)

    # If there is still a duplicate, prompt for a choice
    if show_list or (result_count > 1 and prompt_for_choice):
        results = select_duplicate(results,track_name,artist,album,prompt_for_choice)
        result_count = len(results)

    # If there is still a duplicate, pick the most popular, or the first in the list with the same popularity
    if result_count > 1:
        max_popular = -1
        best_result = []
        for result in results:
            if result['popularity'] > max_popular:
                best_result = result
                max_popular = result['popularity']
        new_base = []
        new_base.append(best_result)
        results = new_base
        result_count = 1

    return results

def get_results_for_album(artist,album,show_list,prompt_for_choice):
    # returns a list with an extra level of indirection,
    # so one list per album, not per track

    results = get_results_from_override_album(artist,album)
    if results == None: # override to skipped
        return []
    elif len(results) > 0 and len(results[0]) > 0 and len(results[0][1]) > 0:
        if show_list:
            for ai,albumdata in enumerate(results):
                albumuri = albumdata[0]
                tracks = albumdata[1]
                if Args.show_tracks:
                    for i,trackuri in enumerate(tracks):
                        track = SpotifyAPI.track(trackuri)
                        print_track(track,i+1)
                else:
                    album = read_SpotifyAlbum(albumuri) #SpotifyAPI.album(albumuri)
                    print_album(ai+1,album)
        return results

    results = get_search_exact('*',artist,album)
    result_count = len(results)

    # If not found, try various changes
    if result_count == 0:
        if remove_punctuation(artist) != artist:
            results_artist_punctuation = get_search_exact('*',remove_punctuation(artist),album)
            results.extend(results_artist_punctuation)

        if remove_brackets(artist) != artist or remove_brackets(album) != album:
            results_all_brackets = get_search_exact('*',remove_brackets(artist),remove_brackets(album))
            results.extend(results_all_brackets)

        result_count = len(results)

    # If there is a duplicate, see if there is an obvious single match
    if result_count > 1:
        new_base = []
        for result in results:
            if name_matches(result['name'], album):
                new_base.append(result)
        if len(new_base) > 0:
            results = new_base
            result_count = len(results)

    # If there is a duplicate, prefer album tracks to singles
    if result_count > 1:
        new_base = []
        for result in results:
            if result['album_type'] ==  'album':
                new_base.append(result)
        if len(new_base) == 1:
            results = new_base
            result_count = len(results)

    # Sometimes get actual exact duplicates, try to eliminate those
    if result_count > 1:
        new_base = []
        for result in results:
            found = False
            for existing in new_base:
                if not name_matches(existing['name'], result['name']):
                    continue
                if existing['album_type'] != result['album_type']:
                    continue
                if existing['release_date'] != result['release_date']:
                    if existing['release_date'][0:4] != result['release_date'][0:4]:
                        continue
                    # seen situation where album is listed twice, one as YYYY-01-01 and once as YYYY-MM-DD
#                    if existing['release_date'][6:10] != '01-01' and result['release_date'][6:10] != '01-01':
#                        continue
                    # release month and day just seems unreliable
                    # assume that same year means same albumt
                if existing['total_tracks'] != result['total_tracks']:
                    continue
                if len(existing['artists']) != len(result['artists']):
                    continue
                found = True
                for loop in range(len(existing['artists'])):
                    if not name_matches(existing['artists'][loop]['name'], result['artists'][loop]['name']):
                        found = False
                        break
            if not found:
                new_base.append(result)
        results = new_base
        result_count = len(results)

#    if result_count > 1:
#        pprint.pprint(results)

    # If there is still a duplicate, prompt for a choice, or pick first
    if result_count > 1 and prompt_for_choice:
        results = select_duplicate_album(results,artist,album,prompt_for_choice)
        result_count = len(results)


    if result_count > 1:
        results = [results[0]]
        result_count = len(results)

    if show_list and result_count:
        if Args.show_tracks:
            for i,track in enumerate(SpotifyAPI.album_tracks(results[0]['id'])['items']):
                print_track(track,i+1,results[0])
        else:
            print_album(1,results[0])

    track_results = []
    for album_result in results:
        tids = []
        tracks = SpotifyAPI.album_tracks(album_result['id'])
        for track in tracks['items']:
            tids.append(track['id'])
        while tracks['next']:
            tracks = SpotifyAPI.next(tracks)
            for track in tracks['items']:
                tids.append(track['id'])
        track_results.append(tids)
    return [track_results]

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

def find_album(artist,album):
    # GPM and Spotify handle multiple artists differently
    if "&" in artist:
        artist = artist.replace("&"," ")
    # Issue with searching for single-quote in title?
    if "'" in album:
        album = album.replace("'"," ")

    search_str = "album:%s artist:%s" % (album, artist)
    results=SpotifyAPI.search(search_str,type='album',market='from_token')
    results_base = results['albums']['items']
    result_count = len(results_base)

    print(result_count)
    # prefer albums to singles/eps
    if result_count > 1:
        new_base = []
        for result in results_base:
            if result['album_type'] ==  'album':
                new_base.append(result)
        if len(new_base) == 1:
            results_base = new_base
            result_count = len(results_base)

    # prefer exact match on name
    if result_count > 1:
        new_base = []
        for result in results_base:
            if result['name'].lower() ==  album.lower():
                new_base.append(result)
        if len(new_base) == 1:
            results_base = new_base
            result_count = len(results_base)

#    if show_details:
#        for item in results['albums']['items']:
#            pprint.pprint(item)

    if result_count == 1:
        return results_base['albums']['items'][0]
    elif result_count == 0:
        print("Not found")
        return None
    elif Args.add or Args.show_search_details or Args.interactive:
        return select_duplicate_album(results_base,artist,album,Args.interactive)
    else:
        print("Duplicates found")
        return None

def find_artist(artist,prompt_unique):
    # GPM and Spotify handle multiple artists differently
    if "&" in artist:
        artist = artist.replace("&"," ")

    search_str = "artist:%s" % (artist)
    results=SpotifyAPI.search(search_str,type='artist',market='from_token')
    results_base = results['artists']['items']
    result_count = len(results_base)

    # prefer exact match on name
    if result_count > 1:
        new_base = []
        for result in results_base:
            if result['name'].lower() ==  artist.lower():
                new_base.append(result)
        if len(new_base) == 1:
            results_base = new_base
            result_count = len(results_base)

    show = Args.add or Args.show_search_details
    prompt = result_count > 1 and prompt_unique
    if show or prompt:
        results_base = select_duplicate_artist(results_base,artist,prompt)
        result_count = len(results_base)
    
#    if show_details:
#        for item in results['artists']['items']:
#            pprint.pprint(item)

    if result_count == 1:
        return results['artists']['items'][0]
    elif result_count == 0:
        print("Not found")
        return None
    else:
        print("Duplicates found")
        return None

def add_album_to_playlist(album,playlist):
    tracks = SpotifyAPI.album_tracks(album['id'])
    track_ids = []
    for track in tracks['items']:
        track_ids.append(track['id'])
    while tracks['next']:
        tracks = SpotifyAPI.next(tracks)
        for track in tracks['items']:
            track_ids.append(track['id'])
    if Args.dryrun:
        print("Would add tracks:")
        pprint.pprint(track_ids)
    else:
        SpotifyAPI.user_playlist_add_tracks(SpotifyAPI.me()['id'],playlist['id'],track_ids)
    return len(track_ids)

def open_dataset_csv():
    csv_file = open( Args.file )
    csv_reader = csv.reader(csv_file,delimiter=',')
    return csv_reader

def open_dataset_html():
    page = requests.get(Args.url)
    tree = html.fromstring(page.content)
    return tree

def open_dataset():
    if Args.file:
        return open_dataset_csv()
    elif Args.url:
        return open_dataset_html()
    else:
        return None

def get_playlist_name_csv(data):
    playlist_name = Args.file
    if playlist_name[-4:] == '.csv':
        playlist_name = playlist_name[0:-4]
#    playlist_name = 'GPM: ' + playlist_name
    return playlist_name

def get_playlist_name_html_metalstorm_top(data):
    title = data.xpath('//*[@id="page-content"]/div[1]/text()')[0].strip()
    return 'MetalStorm: ' + title + ' (' + datetime.date.today().strftime("%Y-%m-%d") + ')'

def get_playlist_name_html_metalstorm_list(data):
    user = data.xpath('//*[@id="page-content"]/table/tr/td[2]/div[1]/table/tr/td[2]/a/text()')[0].strip()
    date = data.xpath('//*[@id="page-content"]/table/tr/td[2]/div[1]/table/tr/td[2]/span/text()')[0].strip()[2:]
    title = data.xpath('//*[@id="page-content"]/div[1]/text()')[0].strip()
    return 'MetalStorm: ' + user + ": " + title + ' (' + date + ')'

def get_playlist_name_html_metalstorm_releases(data):
    title = data.xpath('//*[@id="page-content"]/div[1]/text()')[0].strip()
    return 'MetalStorm: ' + title + ' (' + datetime.date.today().strftime("%Y-%m-%d") + ')'

def get_playlist_name(data):
    if Args.file:
        return get_playlist_name_csv(data)
    elif Args.metalstorm_top:
        return get_playlist_name_html_metalstorm_top(data).replace("  "," ")
    elif Args.metalstorm_list:
        return get_playlist_name_html_metalstorm_list(data).replace("  "," ")
    elif Args.metalstorm_releases:
        return get_playlist_name_html_metalstorm_releases(data).replace("  "," ")
    else:
        return None

def get_tracks_to_import_csv(data):
    tracks = []
    for row in data:
        if len(row) < 3:
            continue
        track_name = row[0]
        artist = row[1]
        album = row[2]
        track = [track_name, artist, album]
        tracks.append(track)
    return tracks

def get_tracks_to_import_html_metalstorm_top(data):
    artists = data.xpath('//*[@id="page-content"]/div[@class="cbox"]/table[@class="table table-compact table-striped"]/tr/td/b/a/text()')
    albums = data.xpath('//*[@id="page-content"]/div[@class="cbox"]/table[@class="table table-compact table-striped"]/tr/td/a/text()')
    if len(artists) != len(albums):
        print("Error parsing data")
        return []
    tracks = []
    for i in range(len(albums)):
        artist = artists[i]
        album = albums[i]
        track = ['*', artist, album]
        tracks.append(track)
    return tracks

def get_tracks_to_import_html_metalstorm_list(data):
    lines = data.xpath('//*[@id="page-content"]/table/tr/td/div/table/tr')

    tracks = []
    for line in lines:
        line_text = line.text_content().strip()
        if not " - " in line_text:
            continue

        line_text = line_text.partition(".")[2].strip()
        artist = line_text.partition(" - ")[0].strip()
        album = line_text.partition(" - ")[2].strip()
        album = album.partition("Style:")[0]
        print("(%s;%s)" % (artist, album))
        track = ['*', artist, album]
        tracks.append(track)

    return tracks

def get_tracks_to_import_html_metalstorm_releases(data):
    lines = data.xpath('//*[@id="page-content"]/div/div/table/tr/td/a')

    tracks = []
    for line in lines:
        line_text = line.text_content().strip()
#        print("%s" % line_text)
        if not " - " in line_text:
            continue

#        line_text = line_text.partition(".")[2].strip()
        artist = line_text.partition(" - ")[0].strip()
        album = line_text.partition(" - ")[2].strip()
        album = album.partition("Style:")[0]
        print("(%s;%s)" % (artist, album))
        track = ['*', artist, album]
        tracks.append(track)

    return tracks

def get_tracks_to_import_html_metalstorm_releases_extended(data):
    lines = data.xpath('//*[@id="page-content"]//div[@class="album-title"]/span')

    tracks = []
    i = 0
    while i < len(lines)-1:
        line_text = lines[i].text_content().strip()
        if not " - " in line_text:
            continue

        genre = []
        art = ""
        lines[i].make_links_absolute("http://www.metalstorm.net/")
        for link in lines[i].iterlinks():
            if "/album.php" in link[2]:
                data2 = read_URL(link[2])
                lines2 = data2.xpath('//*[@id="page-content"]/div[3]/div[1]/div/div[2]/table/tr[2]/td[2]/a/text()')
                for line2 in lines2:
                    genrename = line2.strip()
                    thisgenre = genrename
#                    if genrename in GenresGood:
#                        thisgenre = ['+',genrename]
#                    elif genrename in GenresBad:
#                        thisgenre = ['-',genrename]
#                    else:
#                        thisgenre = [' ',genrename]
                    genre.append(thisgenre)
                artlink = data2.xpath('//*[@id="page-content"]/div[3]/div[1]/div/div[1]/a/img/@src')
                if len(artlink) > 0:
                    art = "http://www.metalstorm.net" + artlink[0]

        artist = line_text.partition(" - ")[0].strip()
        album = line_text.partition(" - ")[2].strip()

        i = i + 1
        line_text = lines[i].text_content().strip()
        while line_text[-4:-2] != "20" and i < len(lines):
            i = i + 1
            line_text = lines[i].text_content().strip()

        release_date = line_text
        i = i + 1

#        print(f"Read {artist},{album},{release_date},{genre}")
#        print("(%s;%s)" % (artist, album))
        track = { 'track': '*', 'artist': artist, 'album': album, 'release_date': release_date, 'genres': genre, 'art': art }
        tracks.append(track)

    return tracks

def get_tracks_to_import(data):
    if Args.file:
        return get_tracks_to_import_csv(data)
    elif Args.metalstorm_top:
        return get_tracks_to_import_html_metalstorm_top(data)
    elif Args.metalstorm_list:
        return get_tracks_to_import_html_metalstorm_list(data)
    elif Args.metalstorm_releases:
        return get_tracks_to_import_html_metalstorm_releases(data)
    else:
        return None

def get_playlist_comments_html(data):
    comments = "Imported from " + Args.url + " on "+ datetime.date.today().strftime("%Y-%m-%d")
    return comments

def get_playlist_comments(data):
    if Args.url:
        return get_playlist_comments_html(data)
    else:
        return ""

def create_playlist():
    found = 0
    notfound = 0
    duplicate = 0
    notfound_list = []
    duplicate_list = []

    data = open_dataset()
    playlist_name = get_playlist_name(data)
    tracks_to_import = get_tracks_to_import(data)
    playlist_comments = get_playlist_comments(data)
    playlist_comments_extra = ""

    user = SpotifyAPI.me()['id']

    if not Args.dryrun:
        playlist = SpotifyAPI.user_playlist_create( user, playlist_name, public=False )
        playlist_id = playlist['id']

    for row in tracks_to_import:
        if len(row) < 3:
            continue

        track_name = row[0]
        artist = row[1]
        album = row[2]

        track_name_orig = track_name
        artist_orig = artist
        album_orig = album

        results = [[]]
        override_results = get_results_from_override(track_name,artist,album)
#        used_override = False
        if override_results == None:
            # overriden to skipped
            print("Search for (%s;%s;%s) skipped by override" % (track_name, artist, album))
            continue
        elif len(override_results) > 0 and len(override_results[0]) > 0 and len(override_results[0][1]) > 0:
            results = []
            for ai,albumdata in enumerate(override_results):
                albumuri = albumdata[0]
                tracks = albumdata[1]
                for i,trackuri in enumerate(tracks):
#                    track = SpotifyAPI.track(trackuri)
                    results.append(trackuri)
            results = [[results]]
#            pprint.pprint(results)
#            used_override = True

        result_count = len(results[0])
        actual_count = result_count
        if track_name == '*':
            actual_count = len(results[0])

        if actual_count > 0:
            print("Search for (%s;%s;%s) overridden with %d tracks" % (track_name, artist, album, len(results[0][0])))

        if actual_count == 0:
            # GPM and Spotify handle multiple artists differently
            if "&" in artist:
                artist = artist.replace("&"," ")
            # Issue with searching for single-quote in title?
            if "'" in track_name:
                track_name = track_name.replace("'"," ")
            if "'" in album:
                album = album.replace("'"," ")
            if "'" in artist:
                artist = artist.replace("'"," ")

    #        print("Searching for (%s;%s;%s)" % (track_name,artist,album))

            if track_name == '*':
                results = get_results_for_album(artist,album,False,Args.interactive)
            else:
                results = get_results_for_track(track_name,artist,album,False,Args.interactive)

        result_count = len(results)
        actual_count = result_count
        if track_name == '*':
            actual_count = len(results[0])

        if actual_count != 1:
            print("Search for (%s;%s;%s) returned %d values" % (track_name, artist, album, actual_count))
            if actual_count == 0:
                notfound = notfound + 1
                notfound_list.append("(%s;%s;%s)" % (track_name_orig, artist_orig, album_orig))
                if playlist_comments_extra != "":
                    playlist_comments_extra = playlist_comments_extra + ", "
                if track_name == '*':
                    playlist_comments_extra = playlist_comments_extra + "%s by %s" % (album_orig, artist_orig)
                else:
                    playlist_comments_extra = playlist_comments_extra + "%s from %s by %s" % (track_name_orig,album_orig,artist_orig)
                if Args.interactive:
                    input("Press any key to continue")
            else:
                results = [results[0]]
                actual_count = 1
                duplicate = duplicate + 1
                duplicate_list.append("(%s;%s;%s)" % (track_name_orig, artist_orig, album_orig))

        if actual_count == 1:
            found = found + 1
            tids = []
            if track_name == '*':
                results = results[0]
                for tids_for_album in results:
#                    print("(*;%s;%s) - added %02d tracks" % (artist, album, len(tids_for_album)))
                    if not Args.dryrun:
#                        print(f"Adding '{tids_for_album}'")
                        SpotifyAPI.user_playlist_add_tracks( user, playlist_id, tids_for_album )
                        time.sleep(0.1)
#                    elif used_override:
#                        print(f"Would have added '{tids_for_album}'")
            else:
                for track in results:
                    tids.append(track['id'])
#                print("(%s;%s;%s) - added %02d tracks" % (track_name, artist, album, len(tids)))
                if not Args.dryrun:
                    SpotifyAPI.user_playlist_add_tracks( user, playlist_id, tids )

        time.sleep(0.1)

    if playlist_comments != "":
        if playlist_comments_extra != "":
            playlist_comments = playlist_comments + ". Not found (%d) %s" % (notfound, playlist_comments_extra)
        print("Setting description to " + playlist_comments)
        if not Args.dryrun:
            SpotifyAPI.user_playlist_change_details(user,playlist_id,description=playlist_comments[0:300])

    print("%d found, %d not found, %d chosen on popularity" % (found, notfound, duplicate))

    if notfound > 0:
        print("Not found:")
        for item in notfound_list:
            print(item)

    if duplicate > 0:
        print("Popularity tie-breaker:")
        for item in duplicate_list:
            print(item)

def query_playlist():
    if not Args.playlist:
        return None

    user_id = SpotifyAPI.me()['id']
    playlist = get_playlist(Args.playlist)
    pprint.pprint(playlist)

def query_recent():
    if Args.last_fm:
        query_recent_lastfm()
    else:
        query_recent_spotify()

def query_recent_lastfm():
#            printable = f"{track.playback_date}\t{track.track}"
#            print(str(i + 1) + " " + printable)
#            pprint.pprint(track)
    print(f"Cached {len(LastFMRecentTrackCache)} unique tracks.")
#    pprint.pprint(LastFMRecentTrackCache)

def init_last_fm_recent_cache():
    global LastFMRecentTrackCache
    LastFMRecentTrackCache = {}
    orig_timestamp = None
    if Args.last_fm_recent_count > 0:
        recent_tracks = LastFMUser.get_recent_tracks(limit=Args.last_fm_recent_count)
    else:
        orig_timestamp = init_last_fm_recent_cache_from_file()
        recent_tracks = LastFMUser.get_recent_tracks(limit=None,time_from=orig_timestamp)
    print(f"Retrieved {len(recent_tracks)} from Last.FM")
    latest_timestamp = None
    for i, track in enumerate(recent_tracks):
#        pprint.pprint(track)
        if track == None or track.track == None or track.track.artist == None or track.track.artist.name == None or track.track.title == None:
            print(f"Error with track {i}.")
            pprint.pprint(track)
        else:
# Oldest scrobbles have no album details?
            if latest_timestamp == None:
                latest_timestamp = track.timestamp
            album = track.album
            if album == None:
                album = "";
            entry = LastFMRecentTrackCacheEntry(album=album.upper(),artist=track.track.artist.name.upper(),track=track.track.title.upper())
            if entry in LastFMRecentTrackCache:
                LastFMRecentTrackCache[entry] = LastFMRecentTrackCache[entry] + 1
            else:
                LastFMRecentTrackCache[entry] = 1
    if latest_timestamp == None:
        latest_timestamp = orig_timestamp
    if Args.last_fm_recent_count < 0 and len(recent_tracks) > 0:
#        print(f"New timestamp is {latest_timestamp}")
        init_last_fm_recent_cache_to_file(latest_timestamp)

def init_last_fm_recent_cache_from_file():
    last_timestamp = None
    try:
        with open(ConfigFolder / 'lastfm_cache.txt','r') as cachefile:
            last_timestamp = cachefile.readline().strip()
            while True:
                line = cachefile.readline()
                if not line:
                    break
                line = line.strip()
                data = line.split(';; ')
                if len(data) == 4:
                    entry = LastFMRecentTrackCacheEntry(album=data[0].upper(),artist=data[1].upper(),track=data[2].upper())
                    LastFMRecentTrackCache[entry] = (int)(data[3])
    except FileNotFoundError:
        return None

    print(f"Read {len(LastFMRecentTrackCache)} entries from LastFM cache file, last timestamp {last_timestamp}")

    if last_timestamp != None and last_timestamp != '':
        last_timestamp = (int)(last_timestamp) + 1
    return last_timestamp

def init_last_fm_recent_cache_to_file(timestamp):
    try:
        copyfile(ConfigFolder / 'lastfm_cache.txt',ConfigFolder / 'lastfm_cache.bak')
    except FileNotFoundError:
        pass
    try:
        with open(ConfigFolder / 'lastfm_cache.txt','w') as cachefile:
            cachefile.write(f"{timestamp}\n")
            for entry in LastFMRecentTrackCache:
                line = f"{entry.album};; {entry.artist};; {entry.track};; {LastFMRecentTrackCache[entry]}\n"
                cachefile.write(line)

        print(f"Wrote {len(LastFMRecentTrackCache)} entries to LastFM cache file")
    except:
        print("Error writing cache file, restoring backup")
        copyfile(ConfigFolder / 'lastfm_cache.bak',ConfigFolder / 'lastfm_cache.txt')

    return None

def init_spotify_recent_cache():
    global SpotifyRecentTrackCache
    SpotifyRecentTrackCache = {}
    tracks = SpotifyAPI.current_user_recently_played()
    for track in tracks['items']:
        uri = track['track']['uri']
        if uri in SpotifyRecentTrackCache:
            SpotifyRecentTrackCache[uri] = SpotifyRecentTrackCache[uri] + 1
        else:
            SpotifyRecentTrackCache[uri] = 1


def query_recent_spotify():
    print(f"Cached {len(SpotifyRecentTrackCache)} unique tracks.")
#    pprint.pprint(SpotifyRecentTrackCache)

def get_playcount_str(artist,album,track,uri):
    playcount = "   "
    if LastFMRecentTrackCache != None:
#        pprint.pprint(LastFMRecentTrackCache)
        entry = LastFMRecentTrackCacheEntry(album=album.upper(),artist=artist.upper(),track=track.upper())
#        print(f"Searching for ('{album.upper()}','{artist.upper()}','{track.upper()}')")
        count = LastFMRecentTrackCache.get(entry,-1)
        if count > 0:
#            print("Found")
            playcount = "L%2.0d" % (count)
        else: # Try with no album
            entry = LastFMRecentTrackCacheEntry(album='',artist=artist.upper(),track=track.upper())
#            print(f"Searching for ('{''}','{artist.upper()}','{track.upper()}')")
            count = LastFMRecentTrackCache.get(entry,-1)
            if count > 0:
#                print("Found")
                playcount = "L%2.0d" % (count)
    elif SpotifyRecentTrackCache != None:
        entry = uri
        if entry in SpotifyRecentTrackCache:
#            print(f"Found {entry} in cache")
            playcount = "S%2.0d" % (SpotifyRecentTrackCache[entry])
    return playcount

def init_search_overrides():
    try:
        with open(ConfigFolder / 'overrides.txt','r') as overridesfile:
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

def get_playlist_tracks(playlist_id):
    if playlist_id in PlaylistDetailsCache:
        return PlaylistDetailsCache['playlist_id']['tracks']
    else:
        playlist = SpotifyAPI.playlist(playlist_id)
        return playlist['tracks']

def init_playlist_cache_playlist_track(playlist,track):
    if 'track' in track:
        track = track['track']
    if 'id' in track:
        track_id = track['id']
        if track_id != None:
#            print(f"Adding track {track_id}")
            playlist_id = playlist['id']
            PlaylistDetailsCache[playlist_id]['tracks'].append(track_id)

def init_playlist_cache_playlist(playlist):
#    print(f"Processing playlist {playlist['name']}")
    if playlist['id'] in PlaylistDetailsCache:
        if playlist['snapshot_id'] != PlaylistDetailsCache[playlist['id']]['snapshot_id']:
            print(f"Cached data for playlist {playlist['name']} is out of date, refreshing")
#            init_playlist_cache_purge_tracklist_playlist(playlist['id'])
        else:
            PlaylistDetailsCache[playlist['id']]['active'] = True
#            print(f"Using cached data for playlist {playlist['name']}")
            return None

    PlaylistDetailsCache[playlist['id']] = { 'name': playlist['name'], 'uri': playlist['uri'], 'snapshot_id': playlist['snapshot_id'], 'owner_id': playlist['owner']['id'], 'tracks': [], 'active': True }

    user_id = SpotifyAPI.me()['id']
    if playlist['owner']['id'] != user_id:
        tracks = SpotifyAPI.playlist(playlist['id'])['tracks']['items']
    else:
        tracks = SpotifyAPI.user_playlist_tracks(user_id,playlist['id'],limit=50)['items']
    while tracks:
        for track in tracks:
            init_playlist_cache_playlist_track(playlist,track)
        if 'next' in tracks and tracks['next']:
            tracks = SpotifyAPI.next(tracks)['items']
        else:
            tracks = None

def init_playlist_cache_purge_tracklist_playlist(playlist_id):
    for track_id in TrackPlaylistCache:
        if playlist_id in TrackPlaylistCache[track_id]:
            TrackPlaylistCache[track_id].remove(playlist_id)

def init_playlist_cache_purge_tracklist():
    for playlist_id in PlaylistDetailsCache:
        init_playlist_cache_purge_tracklist_playlist(playlist_id)

def init_playlist_cache_process_playlist(playlist_id):
    if not PlaylistDetailsCache[playlist_id]['active']:
        print(f"Playlist {PlaylistDetailsCache[playlist_id]['name']} is no longer availble on Spotify, ignoring")
    else:
        for track_id in PlaylistDetailsCache[playlist_id]['tracks']:
            if track_id == None:
                continue
            elif track_id in TrackPlaylistCache:
                TrackPlaylistCache[track_id].append(playlist_id)
            else:
                TrackPlaylistCache[track_id] = [playlist_id]

def init_playlist_cache_process():
    for playlist_id in PlaylistDetailsCache:
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
    for playlist_id in PlaylistDetailsCache:
        if PlaylistDetailsCache[playlist_id]['owner_id'] != user_id and not PlaylistDetailsCache[playlist_id]['active']:
            playlist = SpotifyAPI.playlist(playlist_id)
            if playlist != None:
                init_playlist_cache_playlist(playlist)

    init_playlist_cache_process()

    init_playlist_cache_to_file()

def init_playlist_cache_from_file():
    try:
        with open(ConfigFolder / 'playlist_cache.add','r') as cachefile:
            for line in cachefile:
                line = line.strip()
                data = line.split(';; ')
                if len(data) >= 5:
                    PlaylistDetailsCache[data[0]] = { 'name': data[1], 'uri': data[2], 'snapshot_id': data[3], 'owner_id': data[4], 'tracks': [], 'active': False }
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
                    PlaylistDetailsCache[data[0]] = { 'name': data[1], 'uri': data[2], 'snapshot_id': data[3], 'owner_id': data[4], 'tracks': [], 'active': False }
                    for i in range(5,len(data)):
                        PlaylistDetailsCache[data[0]]['tracks'].append(data[i])
                else:
                    print(f"Error reading {data}")
    except FileNotFoundError:
        return None

    print(f"Read {len(PlaylistDetailsCache)} entries from playlist details cache file.")


def init_playlist_cache_to_file():
    try:
        copyfile(ConfigFolder / 'playlist_cache.txt',ConfigFolder / 'playlist_cache.bak')
    except FileNotFoundError:
        pass
    try:
        count = 0
        with open(ConfigFolder / 'playlist_cache.txt','w') as cachefile:
            for entry in PlaylistDetailsCache:
                playlist = PlaylistDetailsCache[entry]
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

def init_genre_cache_from_file():
    GenresGood.clear()
    GenresBad.clear()
    try:
        with open(ConfigFolder / 'genres.txt','r') as cachefile:
            for line in cachefile:
                line = line.strip()
                if len(line) > 2:
                    if line[0] == '+':
                        GenresGood.append(line[1:])
                    elif line[0] == '-':
                        GenresBad.append(line[1:])
    except FileNotFoundError:
        return None

    print(f"Read {len(GenresGood)+len(GenresBad)} entries from genre file.")

def init_genre_cache_to_file():
    try:
        copyfile(ConfigFolder / 'genres.txt',ConfigFolder / 'genres.bak')
    except FileNotFoundError:
        pass
    try:
        with open(ConfigFolder / 'genres.txt','w') as cachefile:
            for entry in GenresGood:
                line = f"+{entry}\n"
                cachefile.write(line)
            for entry in GenresBad:
                line = f"-{entry}\n"
                cachefile.write(line)

        print(f"Wrote {len(GenresGood)+len(GenresBad)} entries to genre file.")
    except:
        print("Error writing genre file, restoring backup")
        copyfile(ConfigFolder / 'genre.bak',ConfigFolder / 'genre.txt')

    return None

def init_watchlist_from_file():
    Watchlist.clear()
    try:
        with open(ConfigFolder / 'watchlist.txt','r') as cachefile:
            for line in cachefile:
                line = line.strip()
                data = line.split(';; ')
                if len(data) >= 6:
                    entry = { 'track': data[0], 'artist': data[1], 'album': data[2], 'release_date': data[3], 'genres': data[4].split(','), 'art': data[5], 'bandcamp_link': data[6] }
                    Watchlist.append(entry)
#                    pprint.pprint(entry)
    except FileNotFoundError:
        return None

    print(f"Read {len(Watchlist)} entries from watchlist file.")

def init_watchlist_to_file():
    try:
        copyfile(ConfigFolder / 'watchlist.txt',ConfigFolder / 'watchlist.bak')
    except FileNotFoundError:
        pass
    try:
        with open(ConfigFolder / 'watchlist.txt','w') as cachefile:
            for entry in Watchlist:
                line = f"{entry['track']};; {entry['artist']};; {entry['album']};; {entry['release_date']};; {','.join(entry['genres'])};; {entry['art']};; {entry['bandcamp_link']};; <end>\n"
                cachefile.write(line)

        print(f"Wrote {len(Watchlist)} entries to watchlist file.")
    except:
        print("Error writing watchlist file, restoring backup")
        copyfile(ConfigFolder / 'watchlist.bak',ConfigFolder / 'watchlist.txt')

    return None

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

def in_watchlist(first_arg,artist=None,album=None):
#    pprint.pprint(first_arg)
    entryIn = {}
    if isinstance(first_arg, Mapping):
        entryIn = first_arg
    else:
        entryIn = { 'track': first_arg, 'artist': artist, 'album': album }
    for entry in Watchlist:
        if entry['track'].lower() == entryIn['track'].lower() and entry['artist'].lower() == entryIn['artist'].lower() and entry['album'].lower() == entryIn['album'].lower():
            return entry
    return None

def add_to_watchlist(entry):
    Watchlist.append(entry)

def remove_from_watchlist(entryIn):
    entry = in_watchlist(entryIn)
    if entry:
        Watchlist.remove(entry)
        return True
    return False

def write_track_to_file(track,file,i):
    track_name = track['name']
    track_uri = track['uri']
    album_name = ""
    album_uri = ""
    artists = ""
    if track['album']:
        album_name = track['album']['name']
        album_uri = track['album']['uri']
        artists = list_to_comma_separated_string(track['album']['artists'],'name')[0]
    file.write(f'"{track_name}","{artists}","{album_name}",{i},"{track_uri}","{album_uri}"\n')

def export_playlist(playlist):
    user_id = SpotifyAPI.me()['id']

    file_name = playlist['name'] + ".csv"
    if Args.playlist and Args.file:
        file_name = Args.file
    file_name = sanitize(file_name)

    with open(file_name,"w") as outfile:
        i = 1
        tracks = SpotifyAPI.user_playlist_tracks(user_id,playlist['id'],limit=50)
        for track in tracks['items']:
            write_track_to_file(track['track'],outfile,i)
            i = i + 1
        while tracks['next']:
            tracks = SpotifyAPI.next(tracks)
            for track in tracks['items']:
                write_track_to_file(track['track'],outfile,i)
                i = i + 1

def export_playlists():
    user_id = SpotifyAPI.me()['id']

    playlists = SpotifyAPI.user_playlists(user_id)
    for playlist in playlists['items']:
        if is_selected_playlist(playlist) or not Args.playlist:
            export_playlist(playlist)
    while playlists['next']:
        playlists = SpotifyAPI.next(playlists)
        for playlist in playlists['items']:
            if is_selected_playlist(playlist) or not Args.playlist:
                export_playlist(playlist)

def recommend_from_playlist(playlist):
    my_tracks = []
    tracks = SpotifyAPI.user_playlist_tracks(SpotifyAPI.me()['id'],playlist['id'],limit=50)
    for track in tracks['items']:
        my_tracks.append(track)
    while tracks['next']:
        tracks = SpotifyAPI.next(tracks)
        for track in tracks['items']:
            my_tracks.append(track)

    total_tracks = len(my_tracks)

    recommended_tracks = {}

    for i in range(total_tracks*5):
        seed_tracks = list(my_tracks[i]['track']['id'] for i in random.sample(range(total_tracks),5))
        one_recommendation = SpotifyAPI.recommendations(seed_tracks=seed_tracks)
        time.sleep(0.1)
        for track in one_recommendation['tracks']:
            if track['id'] in recommended_tracks:
                recommended_tracks[track['id']][0] = recommended_tracks[track['id']][0] + 1
            else:
                recommended_tracks[track['id']] = [1, track]

    print("Recommendations:")
#    pprint.pprint(recommended_tracks)
    for track_id, info in sorted(recommended_tracks.items(), key=lambda item: -item[1][0]):
        print(f"{info[0]}: {info[1]['name']} from {info[1]['album']['name']}")

def main():
    global Args
    global SpotifyAPI
    Args = get_args()

    client_id = 'your-client-id'
    client_secret = 'your-client-secret'
    redirect_uri = 'http://localhost/'
    scope = "user-read-private user-library-read playlist-read-private playlist-modify-private user-read-recently-played"
    username = 'your-username'
    last_fm_client_id = 'your-last-fm-client-id'
    last_fm_client_secret = 'your-last-fm-client-secret'
    last_fm_username = 'your-last-fm-username'

    with open(ConfigFolder / 'credentials.txt','r') as credfile:
        client_id = credfile.readline().strip()
        client_secret = credfile.readline().strip()
        username = credfile.readline().strip()
        last_fm_client_id = credfile.readline().strip()
        last_fm_client_secret = credfile.readline().strip()
        last_fm_username = credfile.readline().strip()

    SpotifyAPI = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope,client_id=client_id,client_secret=client_secret,redirect_uri=redirect_uri,username=username))
    SpotifyAPI.trace = True
#    SpotifyAPI.trace = False

    user_id = SpotifyAPI.me()['id']

    if Args.show_playlist_membership:
        init_playlist_cache()

    init_spotify_recent_cache()

    init_genre_cache_from_file()

    init_watchlist_from_file()

    if Args.last_fm and last_fm_client_id != "" and last_fm_client_secret != "" and last_fm_username != "":
        global LastFM
        LastFM = pylast.LastFMNetwork(api_key=last_fm_client_id, api_secret=last_fm_client_secret, username=last_fm_username)
        global LastFMUser
        LastFMUser = LastFM.get_user(last_fm_username)
        init_last_fm_recent_cache()

    if not Args.no_overrides:
        init_search_overrides()

    if Args.create:
        create_playlist()
    elif Args.set_description:
        print("Setting playlist description")
        if Args.playlist:
            playlist = get_playlist(Args.playlist)
            if playlist:
                SpotifyAPI.user_playlist_change_details(user_id,playlist['id'],description=Args.set_description)
            else:
                print(f"Playlist {Args.playlist} not found")
    elif Args.find:
        if Args.artist and Args.album:
            if Args.track_name:
                print("Find track")
                album = get_results_for_track(Args.track_name,Args.artist,Args.album,True,False)
            else:
                print("Find album")
                album = get_results_for_album(Args.artist,Args.album,True,False)
    elif Args.add:
        if Args.playlist and Args.artist and Args.album:
            if Args.track_name:
                print("Add track (Not implemented)")
            else:
                print("Add album")
                album = find_album(Args.artist,Args.album)
                playlist = get_playlist(Args.playlist)
                if album and playlist:
                    add_album_to_playlist(album,playlist)
    elif Args.delete:
        if Args.playlist:
            if Args.first_albums:
                print("Deleting initial albums from playlist")
                playlist = get_playlist(Args.playlist)
                if playlist:
                    process_first_albums(playlist)
            elif Args.recent:
                tracks = SpotifyAPI.current_user_recently_played()
                process_tracks(tracks['items'])
                while tracks['next']:
                    tracks = SpotifyAPI.next(tracks)
                    process_tracks(tracks['items'])
            elif Args.all:
                playlist = get_playlist(Args.playlist)
                if playlist:
                    if Args.dryrun:
                        print("Would delete playlist %s (%s)" % (platlist['name'], playlist['id']))
                    else:
                        SpotifyAPI.user_playlist_unfollow(user_id,playlist['id'])
    elif Args.list:
            if Args.first_albums:
                playlist = get_playlist(Args.playlist)
                if playlist:
                    process_first_albums(playlist)
            elif Args.recent:
                tracks = SpotifyAPI.current_user_recently_played()
                process_tracks(tracks['items'])
                while tracks['next']:
                    tracks = SpotifyAPI.next(tracks)
                    process_tracks(tracks['items'])
            elif Args.all:
                playlist = get_playlist(Args.playlist)
                if playlist:
                    tracks = SpotifyAPI.user_playlist_tracks(SpotifyAPI.me()['id'],playlist['id'],limit=50)
                    select_duplicate(tracks['items'],'','','',False)
                    while tracks['next']:
                        tracks = SpotifyAPI.next(tracks)
                        select_duplicate(tracks['items'],'','','',False)
            elif Args.recommendations:
                if Args.artist:
                    if Args.album:
                        if Args.track_name:
                            track = get_results_for_track(Args.track_name,Args.artist,Args.album,False,Args.interactive)
                            if track and len(track) > 0:
                                tracks = SpotifyAPI.recommendations(seed_tracks=[track[0]['id']])
                                process_tracks(tracks['tracks'])
                    else:
                        artist = find_artist(Args.artist,True)
                        if artist:
                            tracks = SpotifyAPI.recommendations(seed_artists=[artist['id']])
                            process_tracks(tracks['tracks'])

                elif Args.genre:
                    tracks = SpotifyAPI.recommendations(seed_genres=[Args.genre])
                    process_tracks(tracks['tracks'])
                elif Args.playlist:
                    playlist = get_playlist(Args.playlist)
                    if playlist:
                        recommend_from_playlist(playlist)

    elif Args.export:
        export_playlists()
    elif Args.query:
        if Args.query == "recent":
            query_recent()
        elif Args.query == "playlist":
            query_playlist()
    elif Args.server:
        init_urlcache_from_file()
        if Args.server_whitelist_ip:
            override_IP_block(Args.server_whitelist_ip,False)
        with HTTPServer(('0.0.0.0', Args.server), web_server) as httpd:
            print(f"Running on port {Args.server}")
            httpd.serve_forever()


class web_server(BaseHTTPRequestHandler):
    def do_GET(self):
        if Args.server_blacklist and not check_IP(self.client_address[0]):
            print(f"Blacklisting request from {self.client_address[0]}")
            self.send_response(403)
            self.end_headers()
            return None

        global WebOutput
        WebOutput = self
        self.parsed_path = urlparse(self.path)
        params = parse_qs(self.parsed_path.query)

        pprint.pprint(self.parsed_path)

        if self.parsed_path.path == "/spotify-playlist.css":
            self.addCSS_from_file('spotify-playlist.css')
        elif 'app' not in params or params['app'][0] != 'spotify':
            self.do_GET_error()
        else:
            # Things that do not display playlist details
            if self.parsed_path.path == "/":
                self.do_GET_main_page()
            elif self.parsed_path.path == "/add_album_to_playlist":
                self.do_GET_add_album_to_playlist()
            elif self.parsed_path.path == "/tag_genre":
                self.do_GET_tag_genre()
            elif self.parsed_path.path == "/add_album_to_watchlist":
                self.do_GET_add_album_to_watchlist()
            elif self.parsed_path.path == "/remove_album_from_watchlist":
                self.do_GET_remove_album_from_watchlist()
            else:
                # Things that do
                init_playlist_cache()
                if Args.last_fm:
                    init_last_fm_recent_cache()
    #            else:
    #                init_spotify_recent_cache()

                if self.parsed_path.path == "/search":
                    self.do_GET_search()
                elif self.parsed_path.path == "/releases":
                    self.do_GET_releases()
                elif self.parsed_path.path == "/playlists":
                    self.do_GET_playlists()
                elif self.parsed_path.path == "/recent":
                    self.do_GET_recent()
                elif self.parsed_path.path == "/watchlist":
                    self.do_GET_watchlist()
                elif self.parsed_path.path == "/watchlist_match_only":
                    self.do_GET_watchlist(True,True)
                elif self.parsed_path.path == "/watchlist_no_match":
                    self.do_GET_watchlist(True,False)
                else:
                    self.do_GET_error()
        WebOutput = None

    def do_GET_error(self):
        self.send_response(404)
        self.end_headers()
        pprint.pprint(self.parsed_path)

    def addCSS(self):
        self.wfile.write(b"<link rel='stylesheet' href='spotify-playlist.css'>")

    def addCSS_from_file(self,file_name):
        self.send_response(200)
        self.send_header('Content-type', 'text/css; charset=UTF-8')
        self.end_headers()
        try:
            with open(file_name,'r') as cssfile:
                for line in cssfile:
                    self.wfile.write(line.encode("utf-8"))
        except:
            print(f"Error reading css file")
            pass

    def showMessage(self,params):
        if 'message' in params:
            for message in params['message']:
                if message[0:2] == "b'":
                    message = message[2:-1]
                self.wfile.write((f"<h3>{message}</h3>").encode("utf-8"))

    def addAlbum_Container_Start(self,album):
        self.wfile.write(b"<div class='album-container'>")
        if 'target' in album:
            self.wfile.write((f"<a id='{album['target']}'></a>").encode("utf-8"))
        elif 'id' in album:
            self.wfile.write((f"<a id='album_{album['id']}'></a>").encode("utf-8"))
        elif 'name' in album:
            self.wfile.write((f"<a id='album_{quote_plus(album['name'])}'></a>").encode("utf-8"))

    def addAlbum_Header_Start(self):
        self.wfile.write(b"<div class='album-header'>")

    def addAlbum_Header_End(self):
        self.wfile.write(b"</div>")

    def addAlbum_SubContainer_Start(self,album):
        self.wfile.write(b"<div class='album-subcontainer'>")

    def addAlbum_SubContainer_End(self):
        self.wfile.write(b"</div>")

    def addAlbum_Container_End(self):
        self.wfile.write(b"</div>")

        self.wfile.write(b"<div class='clear'/>")

    def addAlbum_Art(self,url):
        self.wfile.write(b"<div class='album-image'>")
        if url != "":
            self.wfile.write((f"<img src='{url}' width='100%' />").encode("utf-8"))
        self.wfile.write(b"</div>")

    def addAlbum_Details(self,release_date,genres):
        self.wfile.write(b"<div class='album-details'>")
        if release_date != "":
            self.wfile.write((f"<div>Release date: {release_date}</div>\n").encode("utf-8"))
        goodGenres = []
        badGenres = []
        untaggedGenres = []
        if len(genres) > 0 and genres[0].strip() != "":
            self.wfile.write((f"<div>Genre: ").encode("utf-8"))
            for genre in genres:
                if genre in GenresGood:
                    self.wfile.write((f"<span class='genre-good'>{genre}</span><br/>").encode("utf-8"))
                    goodGenres.append(genre)
                elif genre in GenresBad:
                    self.wfile.write((f"<span class='genre-bad'>{genre}</span><br/>").encode("utf-8"))
                    badGenres.append(genre)
                else:
                    self.wfile.write((f"<span class='genre-untagged'>{genre}</span><br/>").encode("utf-8"))
                    untaggedGenres.append(genre)

            self.wfile.write(b"</div>")
        self.wfile.write(b"</div>\n")

        return [goodGenres,badGenres,untaggedGenres]

    def addAlbum_Actions(self,album,goodGenres,badGenres,untaggedGenres):
        self.wfile.write(b"<div class='album-actions'>")

        if 'uri' in album:
            user_id = SpotifyAPI.me()['id']

            artists = list_to_comma_separated_string(album['artists'],'name')[0]

            if 'watchlist_entry' in album:
                self.wfile.write(b'<form action="/remove_album_from_watchlist">')
                self.wfile.write(b'<label for="remove_album_from_watchlist">Remove from watchlist:</label>')
                self.wfile.write(b"<input type='submit' value='Submit'>")
                self.wfile.write((f"<input type='hidden' name='app' value='spotify'</input>\n").encode("utf-8"))
                self.wfile.write((f"<input type='hidden' name='artist' value='{quote_plus(album['watchlist_entry']['artist'])}'</input>\n").encode("utf-8"))
                self.wfile.write((f"<input type='hidden' name='album' value='{quote_plus(album['watchlist_entry']['album'])}'</input>\n").encode("utf-8"))
                if 'return_target' in album:
                    self.wfile.write((f"<input type='hidden' name='return_target' value='{quote_plus(album['return_target'])}'</input>\n").encode("utf-8"))
                self.wfile.write((f"<input type='hidden' name='return' value='{self.parsed_path.path}'</input>\n").encode("utf-8"))
                self.wfile.write(b'</form>')
                self.wfile.write((f"<form action='/add_album_to_playlist'>\n").encode("utf-8"))
                self.wfile.write(b'<label for="playlist">Move from watchlist to playlist:</label>')
            else:
                self.wfile.write((f"<form action='/add_album_to_playlist'>\n").encode("utf-8"))
                self.wfile.write(b'<label for="playlist">Add album to playlist:</label>')
            self.wfile.write(b'<select name="playlist" id="playlist">\n')
            for playlist_id in PlaylistDetailsCache:
                entry = PlaylistDetailsCache[playlist_id]
                if entry['owner_id'] != user_id:
                    continue
                if entry['active'] != True:
                    continue
                selected = ""
                if Args.server_default_playlist == entry['name']:
                    selected = "selected"
                self.wfile.write((f"<option value='{playlist_id}' {selected}>{entry['name']}</option>\n").encode("utf-8"))
            self.wfile.write(b"</select>\n")
            self.wfile.write(b"<input type='submit' value='Submit'>")
            self.wfile.write((f"<input type='hidden' name='app' value='spotify'</input>\n").encode("utf-8"))
            self.wfile.write((f"<input type='hidden' name='album' value='{album['id']}'</input>\n").encode("utf-8"))
            if 'watchlist_entry' in album:
                self.wfile.write((f"<input type='hidden' name='watchlist_artist' value='{quote_plus(album['watchlist_entry']['artist'])}'</input>\n").encode("utf-8"))
                self.wfile.write((f"<input type='hidden' name='watchlist_album' value='{quote_plus(album['watchlist_entry']['album'])}'</input>\n").encode("utf-8"))
            if 'return_target' in album:
                self.wfile.write((f"<input type='hidden' name='return_target' value='{quote_plus(album['return_target'])}'</input>\n").encode("utf-8"))
            self.wfile.write((f"<input type='hidden' name='return' value='{self.parsed_path.path}'</input>\n").encode("utf-8"))
            self.wfile.write(b"</form>")
        else:
            if 'bandcamp_link' in album and album['bandcamp_link'] != "":
                bandcamplink = f"<div> Not found in Spotify</div><div>Found in Bandcamp: <a href='{album['bandcamp_link']}'>Open in Bandcamp</a></div>\n"
                self.wfile.write(bandcamplink.encode("utf-8"))
            else:
                bandcampsearch = quote_plus(f"{album['artist']} {album['name']}")
                bandcamplink = f"<div>Not found in Spotify: <a href='https://bandcamp.com/search?q={bandcampsearch}'>Search Bandcamp</a></div>\n"
                self.wfile.write(bandcamplink.encode("utf-8"))
            entry = { 'track': '*', 'artist': album['artist'], 'album': album['name'] }
            if 'watchlist_entry' in album:
                entry = { 'track': '*', 'artist': album['watchlist_entry']['artist'], 'album': album['watchlist_entry']['album'] }
            if in_watchlist(entry):
                self.wfile.write(b'<form action="/remove_album_from_watchlist">')
                self.wfile.write(b'<label for="remove_album_from_watchlist">Remove from watchlist:</label>')
                self.wfile.write(b"<input type='submit' value='Submit'>")
                self.wfile.write((f"<input type='hidden' name='app' value='spotify'</input>\n").encode("utf-8"))
                self.wfile.write((f"<input type='hidden' name='artist' value='{quote_plus(entry['artist'])}'</input>\n").encode("utf-8"))
                self.wfile.write((f"<input type='hidden' name='album' value='{quote_plus(entry['album'])}'</input>\n").encode("utf-8"))
                if 'return_target' in album:
                    self.wfile.write((f"<input type='hidden' name='return_target' value='{quote_plus(album['return_target'])}'</input>\n").encode("utf-8"))
                self.wfile.write((f"<input type='hidden' name='return' value='{self.parsed_path.path}'</input>\n").encode("utf-8"))
                self.wfile.write(b'</form>')
            else:
                genres = ",".join(album['genres'])
                self.wfile.write(b'<form action="/add_album_to_watchlist">')
                self.wfile.write(b'<label for="add_album_to_watchlist">Add to watchlist:</label>')
                self.wfile.write(b"<input type='submit' value='Submit'>")
                self.wfile.write((f"<input type='hidden' name='app' value='spotify'</input>\n").encode("utf-8"))
                self.wfile.write((f"<input type='hidden' name='artist' value='{quote_plus(album['artist'])}'</input>\n").encode("utf-8"))
                self.wfile.write((f"<input type='hidden' name='album' value='{quote_plus(album['name'])}'</input>\n").encode("utf-8"))
                self.wfile.write((f"<input type='hidden' name='release_date' value='{album['release_date']}'</input>\n").encode("utf-8"))
                self.wfile.write((f"<input type='hidden' name='genre' value='{genres}'</input>\n").encode("utf-8"))
                self.wfile.write((f"<input type='hidden' name='art' value='{album['art']}'</input>\n").encode("utf-8"))
                self.wfile.write((f"<input type='hidden' name='return' value='{self.parsed_path.path}'</input>\n").encode("utf-8"))
                self.wfile.write(b'</form>')

        if len(badGenres) + len(untaggedGenres) > 0:
            self.wfile.write((f"<form action='/tag_genre'>\n").encode("utf-8"))
            self.wfile.write(b'<label for="genre_good">Add genre to liked:</label>')
            self.wfile.write(b'<select name="tag_genre_good" id="tag_genre_good">\n')
            for genre in untaggedGenres:
                self.wfile.write((f"<option value='{genre}'>{genre}</option>\n").encode("utf-8"))
            for genre in badGenres:
                self.wfile.write((f"<option value='{genre}'>{genre}</option>\n").encode("utf-8"))
            self.wfile.write(b"</select>\n")
            self.wfile.write(b"<input type='submit' value='Submit'>")
            self.wfile.write((f"<input type='hidden' name='app' value='spotify'</input>\n").encode("utf-8"))
            self.wfile.write((f"<input type='hidden' name='return' value='{self.parsed_path.path}'</input>\n").encode("utf-8"))
            self.wfile.write(b"</form>")

        if len(badGenres) + len(goodGenres) > 0:
            self.wfile.write((f"<form action='/tag_genre'>\n").encode("utf-8"))
            self.wfile.write(b'<label for="genre_untagged">Remove tag from genre:</label>')
            self.wfile.write(b'<select name="tag_genre_untagged" id="tag_genre_untagged">\n')
            for genre in goodGenres:
                self.wfile.write((f"<option value='{genre}'>{genre}</option>\n").encode("utf-8"))
            for genre in badGenres:
                self.wfile.write((f"<option value='{genre}'>{genre}</option>\n").encode("utf-8"))
            self.wfile.write(b"</select>\n")
            self.wfile.write(b"<input type='submit' value='Submit'>")
            self.wfile.write((f"<input type='hidden' name='app' value='spotify'</input>\n").encode("utf-8"))
            self.wfile.write((f"<input type='hidden' name='return' value='{self.parsed_path.path}'</input>\n").encode("utf-8"))
            self.wfile.write(b"</form>")

        if len(goodGenres) + len(untaggedGenres) > 0:
            self.wfile.write((f"<form action='/tag_genre'>\n").encode("utf-8"))
            self.wfile.write(b'<label for="genre_bad">Add genre to disliked:</label>')
            self.wfile.write(b'<select name="tag_genre_bad" id="tag_genre_bad">\n')
            for genre in untaggedGenres:
                self.wfile.write((f"<option value='{genre}'>{genre}</option>\n").encode("utf-8"))
            for genre in goodGenres:
                self.wfile.write((f"<option value='{genre}'>{genre}</option>\n").encode("utf-8"))
            self.wfile.write(b"</select>\n")
            self.wfile.write(b"<input type='submit' value='Submit'>")
            self.wfile.write((f"<input type='hidden' name='app' value='spotify'</input>\n").encode("utf-8"))
            self.wfile.write((f"<input type='hidden' name='return' value='{self.parsed_path.path}'</input>\n").encode("utf-8"))
            self.wfile.write(b"</form>")

        self.wfile.write(b"</div>")

    def addAlbum_Tracklist(self,album):
        self.wfile.write(b"<div class='album-tracklist'>")
        self.wfile.write(b"<table>")
        for i,track in enumerate(SpotifyAPI.album_tracks(album['id'])['items']):
            self.wfile.write(b"<tr>")
            print_track(track,i+1,album)
            self.wfile.write(b"</tr>")
        self.wfile.write(b"</table>")

        self.wfile.write(b"</div>")

    def addMissingAlbum(self,album):
        album['name'] = album['album']

        track_list = []

        if Args.bandcamp:
            if 'bandcamp_link' not in album or album['bandcamp_link'] is None or album['bandcamp_link'] == "":
                album['bandcamp_link'] = ""
                data = read_URL(f"http://bandcamp.com/search?q={quote_plus(album['artist'])}")
                lines = data.xpath('//li[@class="searchresult band"]/div[@class="result-info"]/div[@class="itemurl"]/a/@href')
                if len(lines) > 0:
                    data2 = read_URL(lines[0])
                    lines2 = data2.xpath('//div[@id="discography"]/ul/li')
                    if len(lines2) > 0:
                        for line2 in lines2:
                            title = line2.xpath('.//div[@class="trackTitle"]/a')
                            if len(title) > 0 and title[0].text_content().strip().upper() == album['album'].strip().upper():
                                title[0].make_links_absolute(lines[0])
                                album['link'] = title[0].get("href")
                                album['bandcamp_link'] = album['link']
                    else:
                        lines2 = data2.xpath('//ol[@id="music-grid"]/li')
                        for line2 in lines2:
                            title = line2.xpath('.//p[@class="title"]')
                            link = line2.xpath('.//a/@href')
                            if len(title) > 0 and title[0].text_content().strip().upper() == album['album'].strip().upper():
                                line2[0].make_links_absolute(lines[0])
                                album['link'] = line2[0].get("href")
                                album['bandcamp_link'] = album['link']


            if album['bandcamp_link'] != "":
                data3 = read_URL(album['bandcamp_link'])
                if 'art' not in 'album' or album['art'] == '':
                    url = data3.xpath('.//div[@id="tralbumArt"]/a/img/@src')
                    if len(url) > 0:
                        album['art'] = url[0]
                lines3 = data3.xpath('//table[@id="track_table"]//tr')
                if len(lines3) > 0:
                    for i, line3 in enumerate(lines3):
                        track_number = line3.xpath('.//td[@class="track-number-col"]/div/text()')
                        track_title = line3.xpath('.//td[@class="title-col"]/div/a/span[@class="track-title"]/text()')
                        if len(track_number) > 0 and len(track_title) > 0:
                            track = { 'name': track_title[0], 'uri': "", 'explicit': False, 'artists': [{'name': album['artist'] }], 'duration_ms': 0, 'album' : album }
                            track_list.append( track )

        self.addAlbum_Container_Start(album)

        if 'art' in album:
            self.addAlbum_Art(album['art'])

        self.addAlbum_SubContainer_Start(album)

        self.addAlbum_Header_Start()
        goodGenres, badGenres, untaggedGenres = self.addAlbum_Details(album['release_date'],album['genres'])
        self.addAlbum_Actions(album,goodGenres,badGenres,untaggedGenres)
        self.addAlbum_Header_End()

        self.wfile.write(b"<div class='album-tracklist'>")
        self.wfile.write(b"<table>")
        for i,track in enumerate(track_list):
            self.wfile.write(b"<tr>")
            print_track(track,i+1,album)
            self.wfile.write(b"</tr>")
        self.wfile.write(b"</table>")

        self.wfile.write(b"</div>")

        self.addAlbum_SubContainer_End()

        self.addAlbum_Container_End()

    def chooseAlbumArt(self,images,target_width):
        best_error = 0
        best_url = ""
        for image in images:
            error = abs(image['width']-target_width)
            if best_url == "" or error < best_error:
                best_url = image['url']
                best_error = error
        return best_url

    def addAlbum(self,album,release_date='',genres=[]):
        self.addAlbum_Container_Start(album)
        if len(album['images']) > 0:
            self.addAlbum_Art(self.chooseAlbumArt(album['images'],300))

        self.addAlbum_SubContainer_Start(album)

        self.addAlbum_Header_Start()
        goodGenres, badGenres, untaggedGenres = self.addAlbum_Details(release_date,genres)
        self.addAlbum_Actions(album,goodGenres,badGenres,untaggedGenres)
        self.addAlbum_Header_End()

        self.addAlbum_Tracklist(album)

        self.addAlbum_SubContainer_End()

        self.addAlbum_Container_End()

    def getResults(self,track_name,artist,album):
        results = get_search_exact('*',artist,album)

        # If not found, try various changes
        if len(results) == 0:
            if remove_punctuation(artist) != artist:
                results_artist_punctuation = get_search_exact('*',remove_punctuation(artist),album)
                results.extend(results_artist_punctuation)

            if remove_brackets(artist) != artist or remove_brackets(album) != album:
                results_all_brackets = get_search_exact('*',remove_brackets(artist),remove_brackets(album))
                results.extend(results_all_brackets)

        return results

    def addRedirect(self,params,message):
        self.send_response(302)
        fragment = ""
        if 'return_target' in params:
            fragment = f"#{params['return_target'][0]}"
        elif 'album' in params:
            fragment = f"#album_{params['album'][0]}"
        target = "/"
        if 'return' in params:
            target = params['return'][0]

        redirect = f"{target}?app=spotify&message={message}{fragment}"
        print(f"Redirecting to {redirect}")
        self.send_header('Location', redirect)

    def addTopOfPage(self,subtitle=""):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=UTF-8')
        self.end_headers()
        self.wfile.write(b'<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">\n')
        self.wfile.write(b"<html>\n")
        self.wfile.write(b"<head>\n")
        self.addCSS()
        self.wfile.write(b"</head>\n")

        self.wfile.write(b"<body>\n")
        if len(subtitle) > 0:
            self.wfile.write((f"<h1><a href='/?app=spotify'>Spotify Toolbox</a> - {subtitle}</h1>\n").encode("utf-8"))
        else:
            self.wfile.write(b"<h1><a href='/?app=spotify'>Spotify Toolbox</a></h1>\n")

    def do_GET_main_page(self):
        self.addTopOfPage()

        self.wfile.write(b"<ul>\n")
        self.wfile.write(b'<li><a href="/search?app=spotify">Search</a></li>\n')
        self.wfile.write(b'<li><a href="/releases?app=spotify">MetalStorm New Releases</a></li>\n')
        self.wfile.write(b'<li><a href="/playlists?app=spotify">Playlists</a></li>\n')
        self.wfile.write(b'<li><a href="/recent?app=spotify">Recent Tracks</a></li>\n')
        self.wfile.write(b'<li><a href="/watchlist?app=spotify">Watchlist</a></li>\n')
        self.wfile.write(b'<li><a href="/watchlist_match_only?app=spotify">Watchlist (only matched)</a></li>\n')
        self.wfile.write(b'<li><a href="/watchlist_no_match?app=spotify">Watchlist (only unmatched)</a></li>\n')
        self.wfile.write(b"</ul>\n")

    def do_GET_search(self):
        self.addTopOfPage("Search")

        self.wfile.write(b'''
<div class="topnav">
  <div class="search-container">
    <form action="/search">
      <input type="text" placeholder="Search.." name="search">
      <input type="hidden" name="app" value="spotify"></input>
      <button type="submit"><i class="fa fa-search"></i></button>
    </form>
  </div>
</div>''')

        if self.parsed_path.query.startswith("search="):
            search_term = unquote_plus(self.parsed_path.query[7:])
            if " - " in search_term:
                data = search_term.split("-")
                artist = data[0].strip()
                album = data[1].strip()

                self.wfile.write((f"<h2>Results for {artist},{album}</h2>\n").encode("utf-8"))
                results = self.getResults('*',artist,album)

                for album in results:
                    self.wfile.write(b"<hr/>")
                    self.addAlbum(album)


        self.wfile.write(b"</body>\n")
        self.wfile.write(b"</html>")


    def do_GET_recent(self):
        self.addTopOfPage("Recent Tracks")

        params = parse_qs(self.parsed_path.query)

        self.showMessage(params)

        self.wfile.write(b"<div class='playlist-view'>")
        self.wfile.write(b"<div class='album-tracklist'>")
        self.wfile.write(b"<table>\n")
        i = 0
        tracks = SpotifyAPI.current_user_recently_played()
        select_duplicate(tracks['items'],'','','',False,i)
        i = i + len(tracks['items'])
        while tracks['next']:
            tracks = SpotifyAPI.next(tracks)
            select_duplicate(tracks['items'],'','','',False,i)
            i = i + len(tracks['items'])
        self.wfile.write(b"</table>")

        self.wfile.write(b"</div>")
        self.wfile.write(b"</div>")

        self.wfile.write(b"</body>\n")
        self.wfile.write(b"</html>")


    def do_GET_releases(self):
        self.addTopOfPage("MetalStorm New Releases")

        params = parse_qs(self.parsed_path.query)

        self.showMessage(params)

        data = read_URL("http://www.metalstorm.net/events/new_releases.php")
        tracks_to_import = get_tracks_to_import_html_metalstorm_releases_extended(data)

        last_release_date = ""
        for release in tracks_to_import:
            if release['release_date'] != last_release_date:
                self.wfile.write(b"<hr/>")
                self.wfile.write((f"<h2>Releases for {release['release_date']}</h2>\n").encode("utf-8"))
                self.wfile.write(b"<hr/>")
                last_release_date = release['release_date']
            self.wfile.write((f"<h3>Results for {release['artist']},{release['album']}</h3>\n").encode("utf-8"))
            results = self.getResults('*',release['artist'],release['album'])
            if len(results) == 0:
                self.addMissingAlbum(release)
            else:
                for album in results:
                    self.addAlbum(album,release['release_date'],release['genres'])

        self.wfile.write(b"</body>\n")
        self.wfile.write(b"</html>")

    def do_GET_watchlist(self,filter=False,matched_only=True):
        self.addTopOfPage("Watchlist")

        params = parse_qs(self.parsed_path.query)

        self.showMessage(params)

        last_target = 0
        for release in Watchlist:
            results = self.getResults('*',release['artist'],release['album'])
            if len(results) == 0:
                if not (filter and matched_only):
                    self.wfile.write(b"<hr/>")
                    self.wfile.write((f"<h2>Results for {release['artist']},{release['album']}</h2>\n").encode("utf-8"))
                    release['return_target'] = f"album_{last_target}"
                    last_target = last_target + 1
                    release['target'] = f"album_{last_target}"
                    self.addMissingAlbum(release)
#                    break
            else:
                if not (filter and not matched_only):
                    self.wfile.write(b"<hr/>")
                    self.wfile.write((f"<h2>Results for {release['artist']},{release['album']}</h2>\n").encode("utf-8"))
                    for album in results:
                        album['watchlist_entry'] = release
                        album['return_target'] = f"album_{last_target}"
                        last_target = last_target + 1
                        album['target'] = f"album_{last_target}"
                        self.addAlbum(album,release['release_date'],release['genres'])

        self.wfile.write(b"</body>\n")
        self.wfile.write(b"</html>")

        init_watchlist_to_file()

    def do_GET_add_album_to_playlist(self):
        params = parse_qs(self.parsed_path.query)

        message = ""
        if 'album' in params and 'playlist' in params:
            album = read_SpotifyAlbum(params['album'][0]) #SpotifyAPI.album(params['album'][0])
            playlist = SpotifyAPI.playlist(params['playlist'][0])

            count = add_album_to_playlist(album,playlist)

            message = f"Added {count} tracks to playlist {playlist['name']}."

            if 'watchlist_artist' in params and 'watchlist_album' in params:
                entry = {'track': '*', 'artist': params['watchlist_artist'][0], 'album': params['watchlist_album'][0] }
                if in_watchlist(entry):
                    init_watchlist_to_file()
                    if remove_from_watchlist(entry):
                        message = message + f"\nRemoved {entry['album']} by {entry['artist']} from watchlist."
                    else:
                        message = message + f"\nFailed to remove {entry['album']} by {entry['artist']} from watchlist."
        else:
            message = "Error in parameters"

        message = message.encode('latin-1','xmlcharrefreplace')
        message = quote_plus(message)

        self.addRedirect(params,message)

        self.end_headers()

    def do_GET_add_album_to_watchlist(self):
        params = parse_qs(self.parsed_path.query)

        if 'album' in params and 'artist' in params:
            entry = { 'track': '*', 'artist': unquote_plus(params['artist'][0]), 'album': unquote_plus(params['album'][0]), 'release_date': "", 'genres': {}, 'art': "" }
            if 'release_date' in params:
                entry['release_date'] = params['release_date'][0]
            if 'genre' in params:
                entry['genres'] = params['genre'][0].split(",")
            if 'art' in params:
                entry['art'] = params['art'][0]

            add_to_watchlist(entry)
            init_watchlist_to_file()

            message = f"Added {entry['artist']} - {entry['album']} to watchlist"
        else:
            message = "Error in parameters"

        message = message.encode('latin-1','xmlcharrefreplace')
        message = quote_plus(message)

        self.addRedirect(params,message)

        self.end_headers()

    def do_GET_remove_album_from_watchlist(self):
        params = parse_qs(self.parsed_path.query)

        message = ""
        if 'album' in params and 'artist' in params:
            entry = { 'track': '*', 'artist': unquote_plus(params['artist'][0]), 'album': unquote_plus(params['album'][0]), 'release_date': "", 'genres': {}, 'art': "" }
            if in_watchlist(entry):
                if remove_from_watchlist(entry):
                    init_watchlist_to_file()
                    message = f"Removed {entry['album']} by {entry['artist']} from watchlist."
                else:
                    message = f"Failed to remove {entry['album']} by {entry['artist']} from watchlist."
            else:
                message = f"{entry['artist']} - {entry['album']} not in watchlist"
        else:
            message = "Error in parameters"

        message = message.encode('latin-1','xmlcharrefreplace')
        message = quote_plus(message)

        self.addRedirect(params,message)

        self.end_headers()

    def do_GET_tag_genre(self):
        print("In do_GET_tag_genre")
        params = parse_qs(self.parsed_path.query)
#        pprint.pprint(params)
        message = ""
        if 'tag_genre_untagged' in params:
            tags = params['tag_genre_untagged']
            for tag in tags:
                if tag in GenresGood:
                    message = message + f"Removed Liked tag from genre {tag}. "
                    GenresGood.remove(tag)
                if tag in GenresBad:
                    message = message + f"Removed Disliked tag from genre {tag}. "
                    GenresBad.remove(tag)
        if 'tag_genre_good' in params:
            tags = params['tag_genre_good']
            for tag in tags:
                if tag in GenresBad:
                    message = message + f"Removed Disliked tag from genre {tag}. "
                    GenresBad.remove(tag)
                if tag not in GenresGood:
                    message = message + f"Added Liked tag to genre {tag}. "
                    GenresGood.append(tag)
        if 'tag_genre_bad' in params:
            tags = params['tag_genre_bad']
            for tag in tags:
                if tag in GenresGood:
                    message = message + f"Removed Liked tag from genre {tag}. "
                    GenresGood.remove(tag)
                if tag not in GenresBad:
                    message = message + f"Added Disliked tag to genre {tag}. "
                    GenresBad.append(tag)

        init_genre_cache_to_file()

        message = message.encode('latin-1','xmlcharrefreplace')
        message = quote_plus(message)

        self.addRedirect(params,message)

        self.end_headers()

    def do_GET_playlists_add_header(self):
        user_id = SpotifyAPI.me()['id']
        params = parse_qs(self.parsed_path.query)

        playlist_selected = ''
        if 'playlist' in params:
            playlist_selected = params['playlist'][0]

        self.addTopOfPage("Playlists")

        self.showMessage(params)

        self.wfile.write((f"<form action='/playlists'>\n").encode("utf-8"))
        self.wfile.write(b'<label for="playlist">Select playlist:</label>')
        self.wfile.write(b'<select name="playlist" id="playlist">\n')
        for playlist_id in PlaylistDetailsCache:
            entry = PlaylistDetailsCache[playlist_id]
            if entry['owner_id'] != user_id and entry['owner_id'] != 'spotify':
                continue
            if entry['active' ] == False:
                continue
            selected = ""
            if playlist_selected == playlist_id:
                selected = "selected"
            elif playlist_selected == "" and Args.server_default_playlist == entry['name']:
                selected = "selected"
            self.wfile.write((f"<option value='{playlist_id}' {selected}>{entry['name']}</option>\n").encode("utf-8"))
        self.wfile.write(b"</select>\n")
        self.wfile.write(b"<input type='submit' value='Submit'>")
        self.wfile.write((f"<input type='hidden' name='app' value='spotify'>\n").encode("utf-8"))
#        self.wfile.write((f"<input type='hidden' name='album' value='{album['id']}'</input>\n").encode("utf-8"))
#        self.wfile.write((f"<input type='hidden' name='return' value='{self.parsed_path.path}'</input>\n").encode("utf-8"))
        self.wfile.write(b"</form>\n")


    def do_GET_playlists(self):
        user_id = SpotifyAPI.me()['id']
        params = parse_qs(self.parsed_path.query)

        playlist = None
        if 'playlist' in params:
            playlist = SpotifyAPI.playlist(params['playlist'][0])
        if playlist == None:
            self.do_GET_playlists_add_header()
            return None

        if 'action' in params:
            action = params['action'][0]
            if action == 'delete-first-N' and 'firstN' in params:
                firstN = (int)(params['firstN'][0])
#                print(f"Would delete first {firstN} albums from playlist {playlist['name']}")

                message = ""
                if firstN > 0:
                    message = f"Removed albums from playlist {playlist['name']}<ul>"
                    new_album_count = 1
                    tracks = SpotifyAPI.user_playlist_tracks(user_id,playlist['id'],limit=50)
                    if len(tracks['items']) > 0:
                        firsttrack = tracks['items'][0]['track']
                        album = firsttrack['album']
                        first_album_tracks = []
                        while True:
                            for track in tracks['items']:
                                if track['track']['album'] == album:
                                    first_album_tracks.append(track)
                                else:
                                    message = message + f"<li>{album['name']} by {list_to_comma_separated_string(album['artists'],'name')[0]}</li>"
                                    new_album_count = new_album_count + 1

                                    tracks_to_remove = []
                                    for remove_track in first_album_tracks:
                                        tracks_to_remove.append(remove_track['track']['id'])
                                    SpotifyAPI.user_playlist_remove_all_occurrences_of_tracks(user_id,playlist['id'],tracks_to_remove)

                                    if new_album_count > firstN:
                                        break
                                    album = track['track']['album']
                                    first_album_tracks = []
                                    first_album_tracks.append(track)

                            if new_album_count > firstN:
                                break
                            elif tracks['next']:
                                tracks = SpotifyAPI.next(tracks)
                            else:
                                if len(first_album_tracks) > 0: # If playlist only has 1 album
                                    message = message + f"<li>{album['name']} by {list_to_comma_separated_string(album['artists'],'name')[0]}</li>"

                                    tracks_to_remove = []
                                    for remove_track in first_album_tracks:
                                        tracks_to_remove.append(remove_track['track']['id'])
                                    SpotifyAPI.user_playlist_remove_all_occurrences_of_tracks(user_id,playlist['id'],tracks_to_remove)
                                break
                message = message + "</ul>"            
                message = message.encode('latin-1','xmlcharrefreplace')
                message = quote_plus(message)

                print(message)
                self.send_response(302)
                self.send_header('Location', f"/playlists?app=spotify&playlist={playlist['id']}&message={message}")
                self.end_headers()
                return None

            elif action == 'duplicate':
                old_playlist = SpotifyAPI.playlist(params['playlist'][0])
                track_ids = []
                tracks = old_playlist['tracks']
                while tracks:
                    for track in tracks['items']:
                        track_ids.append(track['track']['id'])
                    if tracks['next']:
                        tracks = SpotifyAPI.next(tracks)
                    else:
                        tracks = None
                old_name = old_playlist['name']
                if len(old_name) > 12 and old_name[-12] == '(' and old_name[-1] == ')':
                    old_name = old_name[0:-13]
                playlist = SpotifyAPI.user_playlist_create( user_id, old_name + ' (' + datetime.date.today().strftime("%Y-%m-%d") + ')', public=False )
                playlist_id = playlist['id']
                SpotifyAPI.user_playlist_add_tracks( user_id, playlist_id, track_ids )

                message = f"Created playlist {playlist['name']} with {len(track_ids)} tracks."
                
                message = message.encode('latin-1','xmlcharrefreplace')
                message = quote_plus(message)

                print(message)
                self.send_response(302)
                self.send_header('Location', f"/playlists?app=spotify&playlist={playlist['id']}&message={message}")
                self.end_headers()
                return None

        self.do_GET_playlists_add_header()

        if playlist['owner']['id'] == user_id:
            self.wfile.write((f"<form action='/playlists'>\n").encode("utf-8"))
            self.wfile.write(b'<label for="playlist">Delete first albums from playlist:</label>')
            self.wfile.write((f"<input type='number' name='firstN' id='firstN' min='1'>\n").encode("utf-8"))
            self.wfile.write((f"<input type='hidden' name='app' value='spotify'>\n").encode("utf-8"))
            self.wfile.write((f"<input type='hidden' name='action' value='delete-first-N'>\n").encode("utf-8"))
            self.wfile.write((f"<input type='hidden' name='playlist' value='{playlist['id']}'>\n").encode("utf-8"))
    #                self.wfile.write((f"<input type='hidden' name='return' value='{self.parsed_path.path}'>\n").encode("utf-8"))
            self.wfile.write(b"<input type='submit' value='Submit'>")
            self.wfile.write(b"</form>\n")
        self.wfile.write((f"<form action='/playlists'>\n").encode("utf-8"))
        self.wfile.write(b'<label for="playlist">Duplicate playlist:</label>')
        self.wfile.write((f"<input type='hidden' name='app' value='spotify'>\n").encode("utf-8"))
        self.wfile.write((f"<input type='hidden' name='action' value='duplicate'>\n").encode("utf-8"))
        self.wfile.write((f"<input type='hidden' name='playlist' value='{playlist['id']}'>\n").encode("utf-8"))
#                self.wfile.write((f"<input type='hidden' name='return' value='{self.parsed_path.path}'>\n").encode("utf-8"))
        self.wfile.write(b"<input type='submit' value='Submit'>")
        self.wfile.write(b"</form>\n")


        self.wfile.write(b"<div class='playlist-view'>")
        self.wfile.write(b"<div class='playlist-description'>")
        self.wfile.write((f"{playlist['description']}").encode("utf-8"))
        self.wfile.write(b"</div>")
        self.wfile.write(b"<div class='album-tracklist'>")
        self.wfile.write(b"<table>\n")
        i = 0
        tracks = playlist['tracks']
#        tracks = SpotifyAPI.user_playlist_tracks(SpotifyAPI.me()['id'],playlist['id'],limit=50)
        select_duplicate(tracks['items'],'','','',False,i)
        i = i + len(tracks['items'])
        while tracks['next']:
            tracks = SpotifyAPI.next(tracks)
            select_duplicate(tracks['items'],'','','',False,i)
            i = i + len(tracks['items'])
        self.wfile.write(b"</table>")

        self.wfile.write(b"</div>")
        self.wfile.write(b"</div>")

        self.wfile.write(b"</body>\n")
        self.wfile.write(b"</html>")



if __name__ == '__main__':
    main()
