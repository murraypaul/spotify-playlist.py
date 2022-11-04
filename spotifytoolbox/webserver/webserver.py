from spotifytoolbox import myglobals
from spotifytoolbox import caches

from spotifytoolbox.utils import *

from spotifytoolbox.search import get_search_exact
from spotifytoolbox.actions import add_album_to_playlist

from spotifytoolbox import output

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
import base64
import unidecode
import subprocess
from sorcery import dict_of

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, quote_plus, unquote_plus, parse_qs, quote
import pydnsbl

import json

IPBlacklistChecker = pydnsbl.DNSBLIpChecker()
IPBlacklist = {}

CSSFile = "spotify-playlist.css"

ExternalBrowser = "lynx -source"

CacheData = None
Args = None
SpotifyAPI = None

def run(CacheData_):
    global Args
    global CacheData
    global SpotifyAPI
    CacheData = CacheData_
    Args = myglobals.Args
    SpotifyAPI = myglobals.SpotifyAPI
    caches.url.init(CacheData)
    if Args.server_whitelist_ip:
        override_IP_block(Args.server_whitelist_ip,False)
    with HTTPServer(('0.0.0.0', Args.server), web_server) as httpd:
        print(f"Running on port {Args.server}")
        httpd.serve_forever()

def check_IP(ip):
    if ip not in IPBlacklist:
        print(f"Checking IP {ip}")
        result = IPBlacklistChecker.check(ip)
        print(f"Adding IP cache ({ip},{result.blacklisted})")
        IPBlacklist[ip] = result.blacklisted

    return IPBlacklist[ip] == False

def override_IP_block(ip,value):
    IPBlacklist[ip] = value

class web_server(BaseHTTPRequestHandler):
    def WebOutput():
        return myglobals.WebOutput

    def do_GET(self):
        if Args.server_blacklist and not check_IP(self.client_address[0]):
            print(f"Blacklisting request from {self.client_address[0]}")
            self.send_response(403)
            self.end_headers()
            return None

        myglobals.WebOutput = self
        self.parsed_path = urlparse(self.path)
        params = parse_qs(self.parsed_path.query)

        pprint.pprint(self.parsed_path)

        if self.parsed_path.path == "/" + CSSFile:
            self.addCSS_from_file(CSSFile)
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
                caches.playlist.init(CacheData)
                if Args.last_fm:
                    caches.lastfm.init_recent_cache()
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
                elif self.parsed_path.path == "/current":
                    self.do_GET_current()
                elif self.parsed_path.path == "/watchlist":
                    self.do_GET_watchlist()
                elif self.parsed_path.path == "/watchlist_match_only":
                    self.do_GET_watchlist(True,True)
                elif self.parsed_path.path == "/watchlist_no_match":
                    self.do_GET_watchlist(True,False)
                elif self.parsed_path.path == "/show_album":
                    self.do_GET_show_album()
                elif self.parsed_path.path == "/show_artist":
                    self.do_GET_show_artist()
                else:
                    self.do_GET_error()
        myglobals.WebOutput = None

    def do_GET_error(self):
        self.send_response(404)
        self.end_headers()
        pprint.pprint(self.parsed_path)

    def addCSS(self):
        self.wfile.write((f"<link rel='stylesheet' href='{CSSFile}'>").encode("utf-8"))

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

    def getAlbumTarget(self,album):
        if 'target' in album:
            return "album_" + album['target']
        elif 'id' in album:
            return "album_" + album['id']
        elif 'name' in album:
            return "album_" + quote_plus(album['name'])
        else:
            return "album_Unknown"

    def addAlbum_Container_Start(self,album):
        self.wfile.write(b"<div class='album-container'>")
        self.wfile.write((f"<a id='{self.getAlbumTarget(album)}'></a>").encode("utf-8"))

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

    def addAlbum_Details(self,release_date,genres,show_top_link=None):
        self.wfile.write(b"<div class='album-details'>")
        if show_top_link != None:
            self.wfile.write(show_top_link)
        if release_date != "":
            self.wfile.write((f"<div>Release date: {release_date}</div>\n").encode("utf-8"))
        goodGenres = []
        badGenres = []
        untaggedGenres = []
        if len(genres) > 0 and genres[0].strip() != "":
            self.wfile.write((f"<div>Genre: ").encode("utf-8"))
            for genre in genres:
                if genre in caches.genre.GenresGood():
                    self.wfile.write((f"<span class='genre-good'>{genre}</span><br/>").encode("utf-8"))
                    goodGenres.append(genre)
                elif genre in caches.genre.GenresBad():
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
            PlaylistDetailsCache = caches.playlist.PlaylistDetailsCache()
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
            if caches.watchlist.is_in(entry):
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
            self.wfile.write((f"<input type='hidden' name='return_target' value='{self.getAlbumTarget(album)}'</input>\n").encode("utf-8"))
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
            self.wfile.write((f"<input type='hidden' name='return_target' value='{self.getAlbumTarget(album)}'</input>\n").encode("utf-8"))
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
            self.wfile.write((f"<input type='hidden' name='return_target' value='{self.getAlbumTarget(album)}'</input>\n").encode("utf-8"))
            self.wfile.write((f"<input type='hidden' name='return' value='{self.parsed_path.path}'</input>\n").encode("utf-8"))
            self.wfile.write(b"</form>")

        self.wfile.write(b"</div>")

    def addAlbum_Tracklist(self,album):
        self.wfile.write(b"<div class='album-tracklist'>")
        self.wfile.write(b"<table>")
        for i,track in enumerate(SpotifyAPI.album_tracks(album['id'])['items']):
            self.wfile.write(b"<tr>")
            output.print_track(track,i+1,album)
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
            output.print_track(track,i+1,album)
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

    def addAlbum(self,album,release_date='',genres=[],showname=False,showartist=False):
        show_top_link = None
        if showname:
            if showartist:
                artists, artists_with_links = list_to_comma_separated_string(album['artists'],'name')
                show_top_link = f"<h2>{album['name']} by {artists_with_links}</h2>\n".encode("utf-8")
                artistid = album['artists'][0]['id']
                if Args.everynoise:
                    everynoisegenres = caches.everynoise.get_genres_for_artist(artistid)
                    if everynoisegenres != None:
                        aslist = ",".join(everynoisegenres)
                        aslink = f"<h3>{aslist}</h3>\n".encode("utf-8")
                        show_top_link = show_top_link + aslink
            else:
                show_top_link = f"<h2>{album['name']}</h2>\n".encode("utf-8")
            self.wfile.write(show_top_link)

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

    def filter_results(self,results,artist,album):
#        return [results[0]]


        result_count = len(results)

        if result_count > 1:
            new_base = []
            for result in results:
                if name_matches(result['artists'][0]['name'], artist):
                    new_base.append(result)
            if len(new_base) > 0:
                results = new_base
                result_count = len(results)

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

        return results


    def getResults(self,track_name,artist,album,free_text=''):
        results = get_search_exact('*',artist,album,free_text)
        if free_text == '':
            results = self.filter_results(results,artist,album);

        # If not found, try various changes
        if len(results) == 0 and free_text == '':
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
        self.wfile.write(b'<li><a href="/current?app=spotify">Currently Playing</a></li>\n')
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

        params = parse_qs(self.parsed_path.query)

        if 'search' in params:
            search_term = params['search'][0]
            if " - " in search_term:
                data = search_term.split("-")
                artist = data[0].strip()
                album = data[1].strip()

                self.wfile.write((f"<h2>Results for {artist},{album}</h2>\n").encode("utf-8"))
                results = self.getResults('*',artist,album)

                for album in results:
                    self.wfile.write(b"<hr/>")
                    self.addAlbum(album)
            else:
                data = search_term

                self.wfile.write((f"<h2>Results for {search_term}</h2>\n").encode("utf-8"))
                results = self.getResults('*','*','*',search_term)

                for album in results:
                    self.wfile.write(b"<hr/>")
                    self.addAlbum(album)


        self.wfile.write(b"</body>\n")
        self.wfile.write(b"</html>")

    def do_GET_show_album(self):
        params = parse_qs(self.parsed_path.query)

        if 'albumid' in params:
            album = caches.spotify.album.get_by_id(params['albumid'][0])
            self.addTopOfPage(f"Album - {album['name']}")

        self.addAlbum(album, showname=True, showartist=True)

        self.wfile.write(b"</body>\n")
        self.wfile.write(b"</html>")

    def do_GET_show_artist(self):
        params = parse_qs(self.parsed_path.query)

        if 'artistid' in params:
            artist = SpotifyAPI.artist(params['artistid'][0])
            self.addTopOfPage(f"Artist - {artist['name']}")

            if Args.everynoise:
                everynoisegenres = caches.everynoise.get_genres_for_artist(params['artistid'][0])
                if everynoisegenres != None:
                    aslist = ",".join(everynoisegenres)
                    aslink = f"<h3>{aslist}</h3>\n".encode("utf-8")
                    self.wfile.write(aslink)

            albums = []
            results = SpotifyAPI.artist_albums(params['artistid'][0], album_type='album')
            albums.extend(results['items'])
            while results['next']:
                results = SpotifyAPI.next(results)
                albums.extend(results['items'])

            for album in albums:
                self.addAlbum(album, showname=True)

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

    def do_GET_current(self):
        self.addTopOfPage("Currently Playing")

        params = parse_qs(self.parsed_path.query)

        self.showMessage(params)

        track_entry = SpotifyAPI.currently_playing()
#        print(json.dumps(track_entry,indent=4))
        if track_entry != None and track_entry['item'] != None:
            track = track_entry['item']
            self.wfile.write(b"<div class='playlist-view'><div class='album-tracklist'>")
            self.wfile.write(b"<table>")
            self.wfile.write(b"<tr>")
            output.print_track(track,track['track_number'],track['album'])
            self.wfile.write(b"</tr>")
            self.wfile.write(b"</table>")
            self.wfile.write(b"</div></div>")

            if track_entry['context'] and track_entry['context']['type'] and track_entry['context']['type'] == 'playlist':
                playlist = SpotifyAPI.playlist(track_entry['context']['uri'])
                self.wfile.write((f"Playing from playlist <a href='/playlists?app=spotify&playlist={playlist['id']}'>{playlist['name']}</a>").encode("utf-8"))

            if track['album']:
                self.addAlbum(track['album'])

        self.wfile.write(b"</body>\n")
        self.wfile.write(b"</html>")


    def do_GET_releases(self):
        self.addTopOfPage("MetalStorm New Releases")

        params = parse_qs(self.parsed_path.query)

        self.showMessage(params)

# Do not cache the recent releases page, we expect it to change frequently
#        data = read_URL("http://www.metalstorm.net/events/new_releases.php")
#        page = requests.get("http://www.metalstorm.net/events/new_releases.php")
#        data = html.fromstring(page.content)
# Do cache it, but refresh more frequently
        data = read_URL("http://www.metalstorm.net/events/new_releases.php",60*60)

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
        for release in caches.watchlist.Watchlist():
            results = self.getResults('*',release['artist'],release['album'])
            if len(results) == 0:
                if not (filter and matched_only):
                    self.wfile.write(b"<hr/>")
                    self.wfile.write((f"<h2>Results for {release['artist']},{release['album']}</h2>\n").encode("utf-8"))
                    release['return_target'] = f"album_{last_target}"
                    last_target = last_target + 1
                    release['target'] = f"album_{last_target}"
                    self.addMissingAlbum(release)
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

        caches.watchlist.update()

    def do_GET_add_album_to_playlist(self):
        params = parse_qs(self.parsed_path.query)

        message = ""
        if 'album' in params and 'playlist' in params:
            album = caches.spotify.album.get_by_id(params['album'][0]) #SpotifyAPI.album(params['album'][0])
            playlist = SpotifyAPI.playlist(params['playlist'][0])

            count = add_album_to_playlist(album,playlist)

            message = f"Added {count} tracks to playlist {playlist['name']}."

            if 'watchlist_artist' in params and 'watchlist_album' in params:
                artist = unquote_plus( params['watchlist_artist'][0] )
                album = unquote_plus( params['watchlist_album'][0] )
                entry = {'track': '*', 'artist': artist, 'album': album }
                if caches.watchlist.is_in(entry):
                    if caches.watchlist.remove(entry):
                        message = message + f"\nRemoved {entry['album']} by {entry['artist']} from watchlist."
                        caches.watchlist.update()
                    else:
                        message = message + f"\nFailed to remove {entry['album']} by {entry['artist']} from watchlist."
                else:
                    message = message + f"\nError: {entry['album']} by {entry['artist']} not found in watchlist."
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

            caches.watchlist.add(entry)
            caches.watchlist.update()

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
            if caches.watchlist.is_in(entry):
                if caches.watchlist.remove(entry):
                    message = f"Removed {entry['album']} by {entry['artist']} from watchlist."
                    caches.watchlist.update()
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
                if tag in caches.genre.GenresGood():
                    message = message + f"Removed Liked tag from genre {tag}. "
                    caches.genre.GenresGood().remove(tag)
                if tag in caches.genre.GenresBad():
                    message = message + f"Removed Disliked tag from genre {tag}. "
                    caches.genre.GenresBad().remove(tag)
        if 'tag_genre_good' in params:
            tags = params['tag_genre_good']
            for tag in tags:
                if tag in caches.genre.GenresBad():
                    message = message + f"Removed Disliked tag from genre {tag}. "
                    caches.genre.GenresBad().remove(tag)
                if tag not in caches.genre.GenresGood():
                    message = message + f"Added Liked tag to genre {tag}. "
                    caches.genre.GenresGood().append(tag)
        if 'tag_genre_bad' in params:
            tags = params['tag_genre_bad']
            for tag in tags:
                if tag in caches.genre.GenresGood():
                    message = message + f"Removed Liked tag from genre {tag}. "
                    caches.genre.GenresGood().remove(tag)
                if tag not in caches.genre.GenresBad():
                    message = message + f"Added Disliked tag to genre {tag}. "
                    caches.genre.GenresBad().append(tag)

        caches.genre.update()

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
        self.wfile.write(b'<label for="playlist">Select user playlist:</label>')
        self.wfile.write(b'<select name="playlist" id="playlist">\n')
        for playlist_id in PlaylistDetailsCache:
            entry = PlaylistDetailsCache[playlist_id]
            if entry['owner_id'] != user_id:
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
        self.wfile.write(b"</form>\n")

        self.wfile.write((f"<form action='/playlists'>\n").encode("utf-8"))
        self.wfile.write(b'<label for="playlist">Select system playlist:</label>')
        self.wfile.write(b'<select name="playlist" id="playlist">\n')
        for playlist_id in PlaylistDetailsCache:
            entry = PlaylistDetailsCache[playlist_id]
            if entry['owner_id'] != 'spotify':
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
