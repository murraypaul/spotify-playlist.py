from spotifytoolbox import myglobals

from spotifytoolbox import caches
from spotifytoolbox import webserver

from spotifytoolbox.utils import list_to_comma_separated_string

from spotifytoolbox import output

import argparse
import logging
import pprint
import csv
import time
import datetime
from collections import namedtuple
from shutil import copyfile
from sanitize_filename import sanitize
import random
import pickle
import base64
import unidecode
import subprocess
from sorcery import dict_of

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from urllib.parse import urlparse, quote_plus, unquote_plus, parse_qs, quote

import pydnsbl

import json

logger = logging.getLogger('myapp')
logging.basicConfig(level='INFO')

ConfigFolder = myglobals.ConfigFolder

IPBlacklistChecker = pydnsbl.DNSBLIpChecker()
IPBlacklist = {}

ExternalBrowser = "lynx -source"

def check_IP(ip):
    if ip not in IPBlacklist:
        print(f"Checking IP {ip}")
        result = IPBlacklistChecker.check(ip)
        print(f"Adding IP cache ({ip},{result.blacklisted})")
        IPBlacklist[ip] = result.blacklisted

    return IPBlacklist[ip] == False

def override_IP_block(ip,value):
    IPBlacklist[ip] = value

def get_args():
    parser = argparse.ArgumentParser(description='Spotify toolbox')
    cmdgroup = parser.add_mutually_exclusive_group(required=True)
    cmdgroup.add_argument('--create', required=False, action="store_true", help='Create playlist')
    cmdgroup.add_argument('--delete', required=False, action="store_true", help='Delete playlist')
    cmdgroup.add_argument('--set-description', required=False, action="store_true", help='Set description for playlist')
    cmdgroup.add_argument('--set-image', required=False, action="store_true", help='Set cover image for playlist')
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
    urltypegroup.add_argument('--metalstorm-notmetal', required=False, action="store_true", help='Url is MetalStorm This Isn\'t Metal! list')
    urltypegroup.add_argument('--aoty-top', required=False, action="store_true", help='Url is Album of the Year top list')
    urltypegroup.add_argument('--aoty-recent', required=False, action="store_true", help='Url is Album of the Year recent list')
    urltypegroup.add_argument('--aoty-list', required=False, action="store_true", help='Url is Album of the Year list page')
    urltypegroup.add_argument('--sputnik-top', required=False, action="store_true", help='Url is Sputnik Music top list')
    urltypegroup.add_argument('--sputnik-recent', required=False, action="store_true", help='Url is Sputnik Music recent list')

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
    parser.add_argument('--public', required=False, action="store_true", help='Create playlists with the public flag set')
    parser.add_argument('--limit-count', required=False, type=int, help='Only add the first X items to the playlist')

    marketgroup = parser.add_mutually_exclusive_group(required=False)
    marketgroup.add_argument('--no-market', required=False, action="store_true", help='Do not limit searches by user market')
    marketgroup.add_argument('--market', required=False, help='Specify market')

    parser.add_argument('--last-fm', required=False, action="store_true", help='Enable Last.FM integration')
    parser.add_argument('--last-fm-recent-count', type=int, default=-1, required=False, help='How many recent tracks to retrieve from Last.FM')

    parser.add_argument('--bandcamp', required=False, action="store_true", help='Enable bandcamp integration')

    parser.add_argument('--everynoise', required=False, action="store_true", help='Enable everynoise integration')
    parser.add_argument('--everynoise-update', required=False, action="store_true", help='Update everynoise cached data')

    parser.add_argument('--server-default-playlist', required=False, help='Default playlist to add tracks to')
    parser.add_argument('--server-blacklist', required=False, help='Check incoming IP addresses against blacklist')
    parser.add_argument('--server-whitelist-ip', required=False, help='Whitelist specified IP address')

    return parser.parse_args()

def get_search_exact_filter_results(results,artist_in,album_in,removeaccents=False):
    newresults = {}
    newresults['albums'] = {}
    newresults['albums']['items'] = []

    artist = artist_in
    album = album_in

    if removeaccents:
        artist = unidecode.unidecode(artist)
        album = unidecode.unidecode(album)

    if 'albums' in results and 'items' in results['albums'] and len(results['albums']['items']) > 0:
        for result in results['albums']['items']:
            artist_match = False
            album_match = False

            artists, artists_with_links = list_to_comma_separated_string(result['artists'],'name')

            a_album = result['name']
            if removeaccents:
                a_album = unidecode.unidecode(a_album)

            if a_album.lower() in album.lower() or album.lower() in a_album.lower():
#                print("Matched albums %s and %s [artists %s]" % (a_album,album,artists))
                album_match = True

            if album_match:
                for a_artist in result['artists']:
                    a_artist_name = a_artist['name']
                    if removeaccents:
                        a_artist_name = unidecode.unidecode(a_artist_name)
                    if a_artist_name.lower() == artist.lower() or a_artist_name.lower() in artist.lower() or artist.lower() in a_artist_name.lower():
#                        print("Matched artists %s and %s" % (a_artist_name,artist))
                        artist_match = True
                        break
#                    else:
#                        print("Artists '%s' and '%s' do not match" % (a_artist_name.lower(),artist.lower()))

            if artist_match and album_match:
#                print("Found match '%s' by '%s'" %(a_album,a_artist_name))
                newresults['albums']['items'].append(result)

    if len(newresults['albums']['items']) > 0:
        return newresults
    elif removeaccents == False:
        return get_search_exact_filter_results(results,artist_in,album_in,True)
    else:
        return newresults

def get_search_exact_with_fallback(artist,album):
#    print("Searching for %s, %s" % (artist,album))
    market = 'from_token'
    if Args.market:
        market = Args.market

    s_artist = quote(artist)
    s_album = album #quote(album)
    q = "album:%s artist:%s" % (s_album,s_artist)
#    print(q)
    if Args.no_market:
        results = SpotifyAPI.search(q=q,type='album')
    else:
        results = SpotifyAPI.search(q=q,type='album',market=market)

    results = get_search_exact_filter_results(results,artist,album)

    if 'albums' in results and 'items' in results['albums'] and len(results['albums']['items']) > 0:
        return results

#    print("Not found, falling back")
    q = "%s artist:%s" % (s_album,s_artist)
#    print(q)
    if Args.no_market:
        results = SpotifyAPI.search(q=q,type='album')
    else:
        results = SpotifyAPI.search(q=q,type='album',market=market)

    results = get_search_exact_filter_results(results,artist,album)

    if 'albums' in results and 'items' in results['albums'] and len(results['albums']['items']) > 0:
        return results

#    print("Not found, falling back further")
    q = "album:%s" % (s_album)
#    print(q)
    if Args.no_market:
        results = SpotifyAPI.search(q=q,type='album')
    else:
        results = SpotifyAPI.search(q=q,type='album',market=market)

    results = get_search_exact_filter_results(results,artist,album)

    if 'albums' in results and 'items' in results['albums'] and len(results['albums']['items']) > 0:
        return results

#    print("Not found, falling back even further")
    q = "artist:%s" % (s_artist)
#    print(q)
    if Args.no_market:
        results = SpotifyAPI.search(q=q,type='album')
    else:
        results = SpotifyAPI.search(q=q,type='album',market=market)

    results = get_search_exact_filter_results(results,artist,album)

    if 'albums' in results and 'items' in results['albums'] and len(results['albums']['items']) > 0:
        return results

#    print("Not found, falling back even even further")
    q = "%s %s" % (s_album,s_artist)
#    print(q)
#    results = get_search_exact('','','',q)
    if Args.no_market:
        results = SpotifyAPI.search(q=q,type='album')
    else:
        results = SpotifyAPI.search(q=q,type='album',market=market)

    results = get_search_exact_filter_results(results,artist,album)

    if 'albums' in results and 'items' in results['albums'] and len(results['albums']['items']) > 0:
        return results

#    print("Not found, falling back almost all the way")
    q = "%s" % (s_album)
#    print(q)
#    results = get_search_exact('','','',q)
    if Args.no_market:
        results = SpotifyAPI.search(q=q,type='album')
    else:
        results = SpotifyAPI.search(q=q,type='album',market=market)

    results = get_search_exact_filter_results(results,artist,album)

    if 'albums' in results and 'items' in results['albums'] and len(results['albums']['items']) > 0:
        return results

#    print("Not found, falling back all the way")
    q = "%s" % (s_artist)
#    print(q)
#    results = get_search_exact('','','',q)
    if Args.no_market:
        results = SpotifyAPI.search(q=q,type='album')
    else:
        results = SpotifyAPI.search(q=q,type='album',market=market)

    results = get_search_exact_filter_results(results,artist,album)

    return results

def get_search_exact(track_name,artist,album,free_text=''):
    if Args.show_search_details:
        print("Searching for (%s;%s;%s)" % (track_name,artist,album))
    market = 'from_token'
    if Args.market:
        market = Args.market
    if free_text != '':
        search_str = free_text
        try:
            if Args.no_market:
                results = SpotifyAPI.search(search_str,type='artist,album')
            else:
                results = SpotifyAPI.search(search_str,type='artist,album',market=market)
        except spotipy.exceptions.SpotifyException:
            return []
        if Args.show_search_details:
            print("Search '%s' returned %d results" % (search_str, len(results['albums']['items'])))
        return results['albums']['items']
    elif track_name == '*':
        search_str = "artist:%s album:%s" % (artist, album)
        try:
            results = get_search_exact_with_fallback(artist,album)
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
    my_album_link = album_name
    if album != None and 'id' in album and album['id'] != None:
        my_album_link = f"<a href='/show_album?albumid={album['id']}&app=spotify'>{album_name}</a>"
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
    playlists = caches.playlist.get_playlists_for_single(result)

    if myglobals.WebOutput != None:
        myglobals.WebOutput.wfile.write((f"<td class='track-number'>{i}</td>\n").encode("utf-8"))
        myglobals.WebOutput.wfile.write((f"<td class='play-count'>{playcount}</td>\n").encode("utf-8"))
        if track_link != None:
            myglobals.WebOutput.wfile.write((f"<td class='track-name'><a href='{track_link}'><i class='far fa-play-circle'></i></a>{track_name}</td>\n").encode("utf-8"))
        else:
            myglobals.WebOutput.wfile.write((f"<td class='track-name'>{track_name}</td>\n").encode("utf-8"))
        myglobals.WebOutput.wfile.write((f"<td class='artist'>{artists_with_links}</td>\n").encode("utf-8"))
        myglobals.WebOutput.wfile.write((f"<td class='album'><a href='{album_link}'><i class='fas fa-link'></i></a>{my_album_link}</td>\n").encode("utf-8"))
        if len(playlists) > 0:
            myglobals.WebOutput.wfile.write((f"<td class='playlist-present'>").encode("utf-8"))
        else:
            myglobals.WebOutput.wfile.write((f"<td class='playlist-absent'>").encode("utf-8"))
        for playlist in playlists:
            myglobals.WebOutput.wfile.write((f"{playlist}<br/>").encode("utf-8"))
        myglobals.WebOutput.wfile.write((f"</td>\n").encode("utf-8"))
        myglobals.WebOutput.wfile.write((f"<td class='track-uri'>{result['uri']}</td>\n").encode("utf-8"))
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
    if myglobals.WebOutput == None:
        print("Results for              %24.24s; %24.24s; %48.48s" % (track_name, artist_name, album_name))
    for i in range(len(results)):
        result = results[i]
        if 'track' in result:
            result = result['track']
        if myglobals.WebOutput != None:
            myglobals.WebOutput.wfile.write(b"<tr>\n")
        print_track(result,start_count+i+1)
        if myglobals.WebOutput != None:
            myglobals.WebOutput.wfile.write(b"</tr>")
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

    results = caches.search_overrides.get_results_from_override_album(artist,album)
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
                    album = caches.spotify.album.get_by_id(albumuri) #SpotifyAPI.album(albumuri)
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

def open_dataset_csv():
    csv_file = open( Args.file )
    csv_reader = csv.reader(csv_file,delimiter=',')
    return csv_reader

def open_dataset_html_external():
    p = subprocess.Popen(ExternalBrowser + " " + Args.url,stdout=subprocess.PIPE, shell=True)
    (output,err) = p.communicate()
    status = p.wait()
    if status == 0:
        page_content = output
        tree = html.fromstring(page_content)
    else:
        tree = None
    return tree

def open_dataset_html():
    if Args.aoty_recent or Args.aoty_top or Args.aoty_list:
        tree = open_dataset_html_external()
    else:
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

def get_playlist_name_html_metalstorm_notmetal(data):
    title = data.xpath('//*[@id="page-content"]/div[1]/text()')[0].strip()
    return 'MetalStorm: ' + title

def get_playlist_name_html_aoty(data):
    title = data.xpath('//*[@id="centerContent"]//h1[@class="headline"]/text()')[0].strip()
    return 'AotY: ' + title + ' (' + datetime.date.today().strftime("%Y-%m-%d") + ')'

def get_playlist_name_html_sputnik_top(data):
    title = data.xpath('//h1[@class="brighttext"]/strong/text()')[0].strip()
    return 'Sputnik: ' + title + ' (' + datetime.date.today().strftime("%Y-%m-%d") + ')'

def get_playlist_name_html_sputnik_recent(data):
    title = data.xpath('//*[@id="genreselect"]/option[@selected]/text()')[0].strip()
    return 'Sputnik Recent Releases: ' + title + ' (' + datetime.date.today().strftime("%Y-%m-%d") + ')'

def get_playlist_name(data):
    if Args.file:
        return get_playlist_name_csv(data)
    elif Args.metalstorm_top:
        return get_playlist_name_html_metalstorm_top(data).replace("  "," ")
    elif Args.metalstorm_list:
        return get_playlist_name_html_metalstorm_list(data).replace("  "," ")
    elif Args.metalstorm_releases:
        return get_playlist_name_html_metalstorm_releases(data).replace("  "," ")
    elif Args.metalstorm_notmetal:
        return get_playlist_name_html_metalstorm_notmetal(data).replace("  "," ")
    elif Args.aoty_top or Args.aoty_recent or Args.aoty_list:
        return get_playlist_name_html_aoty(data).replace("  "," ")
    elif Args.sputnik_top:
        return get_playlist_name_html_sputnik_top(data).replace("  "," ")
    elif Args.sputnik_recent:
        return get_playlist_name_html_sputnik_recent(data).replace("  "," ")
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

def get_tracks_to_import_html_metalstorm_notmetal_spotifyonly(data):
    lines = data.xpath('//*[@id="page-content"]/div/div/div/a')

    tracks = []
    for line in lines:
        href = line.get("href")
        if not "https://open.spotify.com/album" in href:
            continue

        albumid = href.rpartition("/")[2].strip()
#        print("(%s;%s)" % (href,albumid))
        track = [albumid]
        tracks.append(track)

    return tracks

def get_tracks_to_import_html_metalstorm_notmetal(data):
    lines = data.xpath('//*[@id="page-content"]/div/div/div[@class="right-col"]')
    print(f"Read {len(lines)} lines")

    tracks = []
    currenturi = ""
    currentartist = ""
    currentalbum = ""
    for line in lines[0].getchildren():
        text = line.text_content().strip()
        if len(text) == 0:
            continue;
#        print(etree.tostring(line))
        if line.find('img') != None:
#            print("found img")
            # new album? (eg Jan 2019)
            line_text = line.find("font").text_content().strip()
            if ' -' in line_text:
                if currentartist != "" and currentalbum != "":
                    print("(%s;%s;%s)" % (currenturi, currentartist, currentalbum))
                    if currenturi != "":
                        track = ['spotify:album:' + currenturi, currentartist, currentalbum]
                    else:
                        track = ['*', currentartist, currentalbum]
                    tracks.append(track)
                currentartist = line_text.partition(" - ")[0].strip()
                currentalbum = line_text.partition(" - ")[2].strip()
                currenturi = ""
        elif line.tag == 'font':
#            print("found font")
            # new album? (eg Feb 2019)
            line_text = line.text_content().strip()
#            print(f"{line_text}")
            if ' -' in line_text:
                if currentartist != "" and currentalbum != "":
                    print("(%s;%s;%s)" % (currenturi, currentartist, currentalbum))
                    if currenturi != "":
                        track = ['spotify:album:' + currenturi, currentartist, currentalbum]
                    else:
                        track = ['*', currentartist, currentalbum]
                    tracks.append(track)
                currentartist = line_text.partition(" - ")[0].strip()
                currentalbum = line_text.partition(" - ")[2].strip()
                currenturi = ""
        else:
            href = line.get("href")
            if href != None:
#                print("found href")
                if "https://open.spotify.com/album" in href:
                     currenturi = href.rpartition("/")[2].strip()

    if currentartist != "" and currentalbum != "":
        if currenturi != "":
            track = ['spotify:album:' + currenturi, currentartist, currentalbum]
        else:
            track = ['*', currentartist, currentalbum]
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
                data2 = caches.url.read_URL(link[2])
                lines2 = data2.xpath('//*[@id="page-content"]/div[3]/div[1]/div/div[2]/table/tr[2]/td[2]/a/text()')
                for line2 in lines2:
                    genrename = line2.strip()
                    thisgenre = genrename
#                    if genrename in GenresGood():
#                        thisgenre = ['+',genrename]
#                    elif genrename in GenresBad():
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

def get_tracks_to_import_html_aoty_list(data):
    lines = data.xpath('//*[@class="albumListTitle"]/span/a')

    tracks = []
    for line in lines:
        line_text = line.text_content().strip()
#        print("%s" % line_text)
        if not " - " in line_text:
            continue

#        line_text = line_text.partition(".")[2].strip()
        artist = line_text.partition(" - ")[0].strip()
        album = line_text.partition(" - ")[2].strip()
#        album = album.partition("Style:")[0]
#        print("(%s;%s)" % (artist, album))
        track = ['*', artist, album]
        tracks.append(track)

    return tracks

def get_tracks_to_import_html_aoty_recent(data):
    artists = data.xpath('//div[@class="artistTitle"]/text()')
    albums = data.xpath('//div[@class="albumTitle"]/text()')
    print("Found %d,%d" % (len(artists), len(albums)))
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

def get_tracks_to_import_html_sputnik_top(data):
    artists = data.xpath('//tr[@class="alt1"]/td/font[1]/b/text()')
    albums = data.xpath('//tr[@class="alt1"]/td/font[2]/text()')
    print("Found %d,%d" % (len(artists), len(albums)))
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

def get_tracks_to_import_html_sputnik_recent(data):
    artists = data.xpath('//table[@class="alt1"]//font/b/text()')
    albums = data.xpath('//table[@class="alt1"]//font/font/text()')
    print("Found %d,%d" % (len(artists), len(albums)))
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

def get_tracks_to_import(data):
    if Args.file:
        return get_tracks_to_import_csv(data)
    elif Args.metalstorm_top:
        return get_tracks_to_import_html_metalstorm_top(data)
    elif Args.metalstorm_list:
        return get_tracks_to_import_html_metalstorm_list(data)
    elif Args.metalstorm_releases:
        return get_tracks_to_import_html_metalstorm_releases(data)
    elif Args.metalstorm_notmetal:
        return get_tracks_to_import_html_metalstorm_notmetal(data)
    elif Args.aoty_top or Args.aoty_list:
        return get_tracks_to_import_html_aoty_list(data)
    elif Args.aoty_recent:
        return get_tracks_to_import_html_aoty_recent(data)
    elif Args.sputnik_top:
        return get_tracks_to_import_html_sputnik_top(data)
    elif Args.sputnik_recent:
        return get_tracks_to_import_html_sputnik_recent(data)
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
        playlist = SpotifyAPI.user_playlist_create( user, playlist_name, public=Args.public )
        playlist_id = playlist['id']
        print(f"Created playlist: {playlist_id}")

    for row in tracks_to_import:
        if Args.limit_count and Args.limit_count <= found + notfound:
            break
        if len(row) == 1:
# spotify album id
            album = caches.spotify.album.get_by_id("spotify:album:" + row[0])
            if not Args.dryrun:
                count = add_album_to_playlist(album,playlist)
                print(f"Added {count} tracks to playlist {playlist['name']}.")
            continue
        elif len(row) == 2:
# [spotify album id or ' ', list of alternative urls]
            if row[0] == ' ':
                notfound = notfound + 1
                print(f"Not found: {row[1]}")
                if playlist_comments_extra != "":
                    playlist_comments_extra = playlist_comments_extra + ", "
                if len(row[1]) == 0:
                    playlist_comments_extra = playlist_comments_extra + row[1][0]
                else:
                    playlist_comments_extra = playlist_comments_extra + "("
                    for url in row[1]:
                        playlist_comments_extra = playlist_comments_extra + url + " "
                    playlist_comments_extra = playlist_comments_extra + ")"
            else:
                album = caches.spotify.album.get_by_id("spotify:album:" + row[0])
                if not Args.dryrun:
                    count = add_album_to_playlist(album,playlist)
                    print(f"Added {count} tracks to playlist {playlist['name']}.")
                continue;
        elif len(row) < 3:
            continue
# [trackname or '*',artist,album]

        track_name = row[0]
        artist = row[1]
        album = row[2]

        print(f"Trying ({track_name},{artist},{album}")

        track_name_orig = track_name
        artist_orig = artist
        album_orig = album

        results = [[]]
        if track_name.startswith('spotify:album:'):
            if not Args.dryrun:
                add_album_to_playlist_byid(track_name,playlist)
            found = found + 1
        else:
            override_results = caches.search_overrides.get_results_from_override(track_name,artist,album)
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
#                if "'" in track_name:
#                    track_name = track_name.replace("'"," ")
#                if "'" in album:
#                    album = album.replace("'"," ")
#                if "'" in artist:
#                    artist = artist.replace("'"," ")

                if track_name == '*':
                    results = get_results_for_album(artist,album,False,Args.interactive)
                else:
                    results = get_results_for_track(track_name,artist,album,False,Args.interactive)

            result_count = len(results)
            actual_count = result_count
            if track_name == '*' or track_name.startswith('spotify:album:'):
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
                        if not Args.dryrun:
                            SpotifyAPI.user_playlist_add_tracks( user, playlist_id, tids_for_album )
                            time.sleep(0.1)
                else:
                    for track in results:
                        tids.append(track['id'])
                    if not Args.dryrun:
                        SpotifyAPI.user_playlist_add_tracks( user, playlist_id, tids )

        time.sleep(0.1)

    if playlist_comments != "":
        if playlist_comments_extra != "":
            playlist_comments = playlist_comments + ". Not found (%d/%d) %s" % (notfound, found+notfound, playlist_comments_extra)
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


def get_playcount_str(artist,album,track,uri):
    playcount = "   "
    if Args.last_fm:
        last_fm_playcount = caches.lastfm.get_playcount_str(artist,album,track,uri)
        if last_fm_playcount != None:
            return last_fm_playcount
    return caches.spotify_recent.get_playcount_str(artist,album,track,uri)

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
    myglobals.Args = get_args()
    Args = myglobals.Args

    client_id = 'your-client-id'
    client_secret = 'your-client-secret'
    redirect_uri = 'http://localhost/'
    scope = "user-read-private user-library-read playlist-read-private playlist-modify-private playlist-modify-public user-read-currently-playing user-read-recently-played ugc-image-upload"
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

    myglobals.SpotifyAPI = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope,client_id=client_id,client_secret=client_secret,redirect_uri=redirect_uri,username=username,open_browser=False))
    SpotifyAPI = myglobals.SpotifyAPI
    SpotifyAPI.trace = True
#    SpotifyAPI.trace = False

    user_id = SpotifyAPI.me()['id']

    CacheData = dict_of(client_id,client_secret,username,last_fm_client_id,last_fm_client_secret,last_fm_username)

    caches.init(CacheData)

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
    elif Args.set_image:
        print("Setting playlist image")
        if Args.playlist and Args.file:
            playlist = get_playlist(Args.playlist)
            if playlist:
                with open(Args.file,"rb") as image_file:
                    imgbase64 = base64.b64encode(image_file.read())
                SpotifyAPI.playlist_upload_cover_image(playlist['id'],imgbase64)
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
        webserver.run(CacheData)


if __name__ == '__main__':
    main()
