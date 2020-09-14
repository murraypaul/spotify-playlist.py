import argparse
import logging
import pprint
import csv
import time
from lxml import html
import requests
import datetime

import spotipy
from spotipy.oauth2 import SpotifyOAuth

logger = logging.getLogger('myapp')
logging.basicConfig(level='INFO')

# todo: move this to a file
search_overrides = []
search_overrides.append(['*','Virgin Steele','The Marriage Of Heaven And Hell Part I','spotify:album:75zT3lRU2so7sR1iV7FvlC'])
search_overrides.append(['*','Virgin Steele','The Marriage Of Heaven And Hell Part II',None])
search_overrides.append(['*','Virgin Steele','The House Of Atreus Act I','spotify:album:47CVkzdB6oe4SH1OlPljD3'])
search_overrides.append(['*','Virgin Steele','The House Of Atreus Act II',None])
search_overrides.append(['*','Trans-Siberian Orchestra','Beethoven\'s Last Night','0ycODecqUKRS9bOA7Vd5Bi'])
search_overrides.append(['*','Hollenthon','With Vilest Of Worms To Dwell','1x1WyZKLLmnsMvYBXyYzly'])
search_overrides.append(['*','Lingua Mortis Orchestra','LMO [Collaboration]','5cviB09AYOXN94iX5bfqvD'])
search_overrides.append(['*','Haggard','Tales Of Ithiria','0fkDg8LzxG1hJnI3y8gXSp'])
search_overrides.append(['*','Angtoria','God Has A Plan For Us All','5ibOK7Gvow4tl1RKSxvPeg'])
search_overrides.append(['*','Trans-Siberian Orchestra','Christmas Eve And Other Stories','6QNuH4X7k9Fxsk3lRLOaiT'])
search_overrides.append(['*','Autumn','Summer\'s End','3jb8MMM31N7BgzLlBTy3Mp'])
search_overrides.append(['*','Virgin Steele','Visions Of Eden - The Lilith Project - A Barbaric Romantic Movie Of The Mind','1thBfia8rDix2nqSLvZpL0'])
search_overrides.append(['*','Grai','Our Native Land (О Земле Родной)','spotify:album:4YG5Q9sIKKdydW4izAShkQ'])
search_overrides.append(['*','Wuthering Heights','Far From The Madding Crowd','6XrWjvxsxAgmeIKbG8kZE4'])
search_overrides.append(['*','Wuthering Heights','The Shadow Cabinet','7pCdMyoHEukSMz0KcCk65v'])
search_overrides.append(['*','Arkona','Во Славу Великим!','spotify:album:3p8efk357mZuEhywLUZaIs'])
search_overrides.append(['*','Echo Of Dalriada','Jégbontó','3oYnpsZG6kgnJIHf8Y659H'])
search_overrides.append(['*','Arkona','От Сердца К Небу','0wAVmgGOw38yNExVldmpo2'])
search_overrides.append(['*','Finntroll','Jaktens Tid','3ZcHD4xbp1Z7K4NlWXWsyj'])
search_overrides.append(['*','Vintersorg','Till Fjälls','spotify:album:1gYjbJwJvwQmkTIqu7IRW7'])
search_overrides.append(['*','Arkona','Гой, Роде, Гой!','2pfdwYocdXcQ8kHtvetBdS'])
search_overrides.append(['*','Mithotyn','In The Sign Of The Ravens','spotify:album:10k00ITqgk2owR0qnkfBAr'])
search_overrides.append(['*','October Falls','A Collapse Of Faith','2o0mJTwA5MzfNoIs3uhnLj'])
search_overrides.append(['*','Myrath','Hope','2X5X8ZiawaGsvaKY7tCPv4'])
search_overrides.append(['*','Alkonost','Na Kryliah Zova (On The Wings Of The Call)','2Jlkqwou9sMCgbFbseaFWG'])
search_overrides.append(['*','October Falls','The Womb Of Primordial Nature','6ymPvAMU3aan53EknAxsyn'])
search_overrides.append(['*','Dirge','Elysian Magnetic Fields','2LBaJLHP3merdxzmtExlG6'])
search_overrides.append(['*','Slugdge','Gastronomicon','1GFWIo6uEnUSG0j715TUVB'])
search_overrides.append(['*','Neurosis','The Eye Of Every Storm','1td0hx7C7mdZGvekzMD1CL'])
search_overrides.append(['*','Slugdge','Dim & Slimeridden Kingdoms','1VigQgC3VjE1mkFFVOg82b'])
search_overrides.append(['*','Cult Of Luna','Mariner [Collaboration]','7s8GMmLooF7H6awoTjbl4Z'])
search_overrides.append(['*','Down','Down III: Over The Under','spotify:album:5zaQlZSl4g1J6XSSvRfl8o'])
search_overrides.append(['*','Celestial Season','Solar Lovers','7MG7nO24dMamoUYpLBXqt6'])
search_overrides.append(['*','Sahg','I','spotify:album:23XR3CMdcApNstjMmpQf33'])
search_overrides.append(['*','New Keepers Of The Water Towers','The Cosmic Child','spotify:album:02QQMpi3AG7s5TvFyvJiV2'])
search_overrides.append(['*','Sleep','Jerusalem','spotify:album:1u49hpxNCoTCWmJa1NXUZl'])
search_overrides.append(['*','Tony MacAlpine','Maximum Security','33AKOG3u4OHhcYZA8ufuCi'])
search_overrides.append(['*','Saturnus','Veronika Decides To Die','spotify:album:5Jxf2vLZ8JdNco7lAM9S4c'])
search_overrides.append(['*','Shape Of Despair','Angels Of Distress','5eHLW4hwMsIjP9QyXx5ntw'])
search_overrides.append(['*','Yearning','Evershade','5eVhNri7dTCrUvdZsGGoj9'])
search_overrides.append(['*','Shape Of Despair','Illusion\'s Play','6QbxDIN3CbEMZQeQKNREVX'])
search_overrides.append(['*','Pagan Altar','The Lords Of Hypocrisy','0mXHFpxeJyJ4aQOC77bsZL'])
search_overrides.append(['*','Rapture','Futile','5orWqamKeISvdEqAdAoGoI'])
search_overrides.append(['*','Kypck','Черно','spotify:album:4cXWTx8DJhzJ3uUJ9Esi0z'])
search_overrides.append(['*','Dissection','Storm Of The Light\'s Bane','6xg1LH1tG9LfStZwv5zdV7'])
search_overrides.append(['*','Helloween','Keeper Of The Seven Keys Part II','spotify:album:0C00ibrtAGw59osJUg5qOO'])
search_overrides.append(['*','Helloween','Keeper Of The Seven Keys Part I','spotify:album:2UHFdmz05GmEY0J0ZbuMBp'])
search_overrides.append(['*','Porcupine Tree','Fear Of A Blank Planet','1uekrPEWOwluQckDtkGAYM'])
search_overrides.append(['*','Carcass','Heartwork','1xCzBTTovIpL3iMKvTM4JK'])
search_overrides.append(['*','Pain Of Salvation','The Perfect Element, Part I','spotify:album:0yqtdNIwsXSZHL7A0QNBBb'])
search_overrides.append(['*','Dismember','Like An Ever Flowing Stream','4i9cuK7MNbTVvezlFujln7'])
search_overrides.append(['*','Caladan Brood','Echoes Of Battle','1frb56r2K4Trem7czARB1s'])
search_overrides.append(['*','Accept','Restless And Wild','0xym0raBJhG64y1Oc179TX'])
search_overrides.append(['*','Soundgarden','Badmotorfinger','spotify:album:2W6MaUiInBkna5DfBES4E3'])
search_overrides.append(['*','Soundgarden','Superunknown','spotify:album:4K8bxkPDa5HENw0TK7WxJh'])
search_overrides.append(['*','Devin Townsend','Ocean Machine: Biomech','spotify:album:7hjBb9Z7o4KO5AMYi5xm66'])
search_overrides.append(['*','Carcass','Necroticism: Descanting The Insalubrious','3Tl1dAwNcRO1W6lMlpx0e3'])
search_overrides.append(['*','Artillery','By Inheritance','0ck8S9IR41yWj50zvt8gbx'])
search_overrides.append(['*','Eternal Tears Of Sorrow','A Virgin And A Whore','3jP2LK5eNSqMqqKhond11q'])
search_overrides.append(['*','Avantasia','The Metal Opera Part I','spotify:album:2HA77HLuzBmzeJp0Hc4YFO'])
search_overrides.append(['*','Katatonia','Viva Emptiness: Anti-Utopian MMXIII Edition','spotify:album:5Ej2wlQwy5c6jTH5DmuDDg'])
search_overrides.append(['*','Blindead','Affliction XXIX II MXMVI','spotify:album:2hNcO6iygItuqaSVLVVSmW'])
search_overrides.append(['*','Ancient Bards','The Alliance Of The Kings - The Black Crystal Sword Saga Part 1','spotify:album:46E2l00AyGutAu8IOHstsb'])
search_overrides.append(['*','Cult Of Fire','मृत्यु का तापसी अनुध्यान','spotify:album:6mhIhyGBRzGEnjKJTzhprL'])
search_overrides.append(['*','Oathbreaker','Eros​ | ​Anteros','spotify:album:42lF4VUn5wSf3BmRpq7jd8'])
search_overrides.append(['*','Decapitated','Winds Of Creation','41SlpwhUgcgshKaZQULVgX'])
search_overrides.append(['*','Nightwish','Century Child','spotify:album:44kzDmMHJn474wrwDd3pCi'])
search_overrides.append(['*','Blood Stain Child','εpsilon','spotify:album:4TQyTokknRMto3WhTdodZK'])
search_overrides.append(['*','Heavenwood','The Tarot Of The Bohemians: Part 1','spotify:album:53ulXwa47kJJTV70tjlAxU'])
search_overrides.append(['*','The Algorithm','Brute Force: Overclock DLC','spotify:album:5JRbR8GX8qw2rUIym6aacv'])
search_overrides.append(['*','Ulver','ATGCLVLSSCAP','spotify:album:60YalK9oRFXskrRyMicOqN'])
search_overrides.append(['*','Celldweller','Transmissions: Vol. 03','spotify:album:7DVcVdk2fKm6rq1veQtR1L'])
search_overrides.append(['*','Drowning Pool','Hellelujuah','spotify:album:7Mid85e4WO4f9GCP3Xjz8K'])
search_overrides.append(['*','Jesu','30 Seconds To The Decline Of Planet Earth','spotify:album:15Xz6NpKJRg2htJjEPUM5U'])
search_overrides.append(['*','Master Boot Record','Virus​.​DOS','spotify:album:6ElO2C628e79gXaKtlp5WD'])
search_overrides.append(['*','Violet Cold','Sommermorgen (Pt. III) - Nostalgia','spotify:album:1oPojPaIKWjq73PlOXa66N'])
search_overrides.append(['*','Harm\'s Way','Posthuman','spotify:album:1RIr3dLd64m8fh23p2gm9L'])
search_overrides.append(['*','Dagon','Back To The Sea','6sgw9sA44BKrKnvp9Z8Z2y'])
search_overrides.append(['*','Antlers','Beneath.Below.Behold.','spotify:album:64EdL7U6VaEdK58t18KolQ'])
search_overrides.append(['*','Violet Cold','Sommermorgen (Pt. II) - Joy','spotify:album:7DvRTjqgeqpDQVtDa7tATR'])
search_overrides.append(['*','Nydvind','Tetramental I: Seas Of Oblivion','spotify:album:7FHMtQtBoMAcdeVLK4oicV'])
search_overrides.append(['*','Gloryhammer','Space 1992: Rise Of The Chaos Wizards','spotify:album:2amXcrKAK1D5OD6LKn4X10'])
search_overrides.append(['*','Extrovert','Восхождение / Ascension','spotify:album:5mmt0xzSflxqhW7TTSOVtu'])
search_overrides.append(['*','Gotsu Totsu Kotsu','因果応報','spotify:album:1PaPbI4O2NsmEbnFjKUOtF'])
search_overrides.append(['*','Tengger Cavalry','Blood Sacrifice Shaman [2015 Edition]','spotify:album:0bakW1fPnzx5hupZdBNVDx'])
search_overrides.append(['*','Periphery','Juggernaut: Alpha & Omega',['spotify:album:5oF7PocZron3xn8Pxhofgx','spotify:album:2vUuAbaoqFPcbp851dRXFt']])
search_overrides.append(['*','Periphery','Periphery II: This Time It\'s Personal','spotify:album:5ebIq78IE2Pi9vyJOaYL4A'])
search_overrides.append(['*','Kalevala','Кудель Белоснежного Льна','spotify:album:79RXmB7Uk3nM09FhCPm2rJ'])
search_overrides.append(['*','Kalevala','Кукушкины дети','spotify:album:5UQuAwobie2PrdQZE5THHL'])



def get_args():
    parser = argparse.ArgumentParser(description='Spotify toolbox')
    cmdgroup = parser.add_mutually_exclusive_group(required=True)
    cmdgroup.add_argument('--create', required=False, action="store_true", help='Create playlist')
    cmdgroup.add_argument('--delete', required=False, action="store_true", help='Delete playlist')
    cmdgroup.add_argument('--set-description', required=False, action="store_true", help='Set description for playlist')
    cmdgroup.add_argument('--list', required=False, action="store_true", help='List items from playlist')
    cmdgroup.add_argument('--find', required=False, action="store_true", help='Search for album (requires --artist and --album, --track is optional)')
    cmdgroup.add_argument('--add', required=False, action="store_true", help='Add tracks to end of playlist (requires --artist and --album, --track is optiona)')

    creategroup = parser.add_mutually_exclusive_group(required=False)
    creategroup.add_argument('--file', required=False, help='Import tracks from csv file')
    creategroup.add_argument('--url', required=False, help='Import tracks from url')

    urltypegroup = parser.add_mutually_exclusive_group(required=False)
    urltypegroup.add_argument('--metalstorm-top', required=False, action="store_true", help='Url is MetalStorm Top-X list')
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

    marketgroup = parser.add_mutually_exclusive_group(required=False)
    marketgroup.add_argument('--no-market', required=False, action="store_true", help='Do not limit searches by user market')
    marketgroup.add_argument('--market', required=False, help='Specify market')

    return parser.parse_args()

def validate_search_overrides():
    for override in search_overrides:
        if len (override) != 4:
            pprint.pprint(override)

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

def get_search_exact(sp,args,track_name,artist,album):
    if args.show_search_details:
        print("Searching for (%s;%s;%s)" % (track_name,artist,album))
    market = 'from_token'
    if args.market:
        market = args.market
    if track_name == '*':
        search_str = "artist:%s album:%s" % (artist, album)
        try:
            if args.no_market:
                results = sp.search(search_str,type='album')
            else:
                results = sp.search(search_str,type='album',market=market)
        except spotipy.exceptions.SpotifyException:
            return []
        if args.show_search_details:
            print("Search '%s' returned %d results" % (search_str, len(results['albums']['items'])))
        return results['albums']['items']
    else:
        search_str = "track:%s artist:%s album:%s" % (track_name, artist, album)
        try:
            if args.no_market:
                results = sp.search(search_str,type='track')
            else:
                results = sp.search(search_str,type='track',market=market)
        except spotipy.exceptions.SpotifyException:
            return []
        if args.show_search_details:
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

def print_track(sp,args,result,i):
    artists = "";
    for artist in result['artists']:
        if len(artists) > 0:
            artists = artists + ", "
        artists = artists + artist['name']
    album = result['album']
    duration_ms = result['duration_ms']
    duration_min = duration_ms / 60000
    duration_totalsec = duration_ms / 1000
    duration_sec = duration_totalsec % 60
    explicit = " "
    if result['explicit']:
        explicit = "Y"
    if 0:
        print("* %s - %s" % (result['name'], artists))
    else:
        print("                 %02d: %24.24s; %24.24s; %48.48s; %12.12s %1.1s %04.04s %02d/%02d %02d:%02d %02d %s" % (
                i,
                result['name'],
                artists,
                album['name'],
                album['album_type'],
                explicit,
                album['release_date'][0:4],
                result['track_number'],
                album['total_tracks'],
                duration_min,
                duration_sec,
                result['popularity'],
                result['uri']
                ))


def select_duplicate(sp,args,results,track_name,artist_name,album_name,ask=True):
    print("Results for          %24.24s; %24.24s; %48.48s" % (track_name, artist_name, album_name))
    for i in range(len(results)):
        result = results[i]
        if 'track' in result:
            result = result['track']
            print_track(sp,args,result,i+1)
    if ask:
        try:
            choice = int(input("Enter choice: "))
            if choice > 0 and choice <= len(results):
                return [results[choice-1]]
        except ValueError:
            pass
    return []

def print_album(sp,args,count,album,track_count=-1):
    artists = "";
    for artist in album['artists']:
        if len(artists) > 0:
            artists = artists + ", "
        artists = artists + artist['name']
    print_album_details(sp,args,
        count,
        artists,
        album['name'],
        album['album_type'],
        album['release_date'][0:4],
        album['total_tracks'],
        track_count,
        album['uri']
        )


def print_album_details(sp,args,count,artist,album,type,release_date,total_tracks,track_count,uri):
    if track_count != None and track_count >= 0:
        print("                 %02d: %24.24s; %48.48s; %12.12s %04.04s %02d/%02d %s" % (
                count,
                artist,
                album,
                type,
                release_date,
                track_count,
                total_tracks,
                uri
                ))
    else:
        print("                 %02d: %24.24s; %48.48s; %12.12s %04.04s    %02d %s" % (
                count,
                artist,
                album,
                type,
                release_date,
                total_tracks,
                uri
                ))

def select_duplicate_album(sp,args,results,artist_name,album_name,ask=True):
    print("Results for          %24.24s; %48.48s" % (artist_name, album_name))
    for i in range(len(results)):
        album = results[i]
        print_album(sp,args,i+1,album)
    if ask:
        try:
            choice = int(input("Enter choice: "))
            if choice > 0 and choice <= len(results):
                return [results[choice-1]]
        except ValueError:
            pass
    return []

def select_duplicate_artist(sp,args,results,artist_name,ask=True):
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

def process_tracks(sp,args,tracks):
    show_tracks = []
    for entry in tracks:
        context = None
        if 'context' in entry:
            context = entry['context']
        show = args.list
        if args.playlist:
            if not context or context['type'] != 'playlist':
                show = False
            else:
                playlist = sp.playlist(context['uri'])
                if args.playlist != playlist['name']:
                    show = False
                else:
                    if args.delete:
                        tracks_to_remove = []
                        tracks_to_remove.append(entry['track']['id'])
                        if args.dryrun:
                            print("Would remove tracks:")
                            pprint.pprint(tracks_to_remove)
                        else:
                            sp.user_playlist_remove_all_occurrences_of_tracks(sp.me()['id'],playlist['id'],tracks_to_remove)
        if show:
            show_tracks.append(entry)
    if args.list and len(show_tracks) > 0:
        select_duplicate(sp,args,show_tracks,'','','',False)


def process_first_albums(sp,args,playlists):
    for playlist in playlists:
        if args.playlist == playlist['name']:
            if playlist['tracks']['total'] > 0:
                new_album_count = 1
                tracks = sp.user_playlist_tracks(sp.me()['id'],playlist['id'],limit=50)
                firsttrack = tracks['items'][0]['track']
                album = firsttrack['album']
                first_album_tracks = []
                while True:
                    for track in tracks['items']:
                        if track['track']['album'] == album:
                            first_album_tracks.append(track)
                        else:
                            print_album(sp,args,new_album_count,album,len(first_album_tracks))
                            new_album_count = new_album_count + 1

                            if args.delete:
                                tracks_to_remove = []
                                for remove_track in first_album_tracks:
                                    tracks_to_remove.append(remove_track['track']['id'])
                                    if args.dryrun:
                                        print_track(sp,args,remove_track['track'],len(tracks_to_remove))
                                if args.dryrun:
                                     None
                                else:
                                    sp.user_playlist_remove_all_occurrences_of_tracks(sp.me()['id'],playlist['id'],tracks_to_remove)
#                            elif args.list:
#                                select_duplicate(sp,args,first_album_tracks,'','','',False)

                            if new_album_count > args.first_albums:
                                break;
                            album = track['track']['album']
                            first_album_tracks = []
                            first_album_tracks.append(track)

                    if new_album_count > args.first_albums:
                        break;
                    elif tracks['next']:
                        tracks = sp.next(tracks)
                    else:
                        break;


def get_results_for_track(sp,args,track_name,artist,album,show_list,prompt_for_choice):
    search_str = "track:%s artist:%s album:%s" % (track_name, artist, album)

    results = get_search_exact(sp,args,track_name,artist,album)
    result_count = len(results)

    # If not found, try various changes
    if result_count == 0:
        results_artist_punctuation = get_search_exact(sp,args,track_name,remove_punctuation(artist),album)
        results.extend(results_artist_punctuation)

        results_track_featuring = get_search_exact(sp,args,remove_featuring(track_name),artist,album)
        results.extend(results_track_featuring)

        results_all_brackets = get_search_exact(sp,args,remove_brackets(track_name),remove_brackets(artist),remove_brackets(album))
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
        results = select_duplicate(sp,args,results,track_name,artist,album,prompt_for_choice)
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

def get_results_for_album(sp,args,artist,album,show_list,prompt_for_choice):
    # returns a list with an extra level of indirection,
    # so one list per album, not per track

    results = get_search_exact(sp,args,'*',artist,album)
    result_count = len(results)

    # If not found, try various changes
    if result_count == 0:
        if remove_punctuation(artist) != artist:
            results_artist_punctuation = get_search_exact(sp,args,'*',remove_punctuation(artist),album)
            results.extend(results_artist_punctuation)

        if remove_brackets(artist) != artist or remove_brackets(album) != album:
            results_all_brackets = get_search_exact(sp,args,'*',remove_brackets(artist),remove_brackets(album))
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
    if show_list or (result_count > 1 and prompt_for_choice):
        results = select_duplicate_album(sp,args,results,artist,album,prompt_for_choice)
        result_count = len(results)

    if result_count > 1:
        results = [results[0]]
    track_results = []
    for album_result in results:
        tids = []
        tracks = sp.album_tracks(album_result['id'])
        for track in tracks['items']:
            tids.append(track['id'])
        while tracks['next']:
            tracks = sp.next(tracks)
            for track in tracks['items']:
                tids.append(track['id'])
        track_results.append(tids)
    return [track_results]

def get_results_from_override_album(sp,args,artist,album):
    uri = None
    found = False
    for entry in search_overrides:
#        if entry[0] == '*' and entry[1] == artist:
#            print("Found matching artist %s. Attempting to match '%s' and '%s'" % (artist, album, entry[2]))
        if entry[0] == '*' and entry[1] == artist and entry[2] == album:
            found = True
            uri_or_uris = entry[3]
            break

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
    tids = []
    try:
        for uri in uris:
            tracks = sp.album_tracks(uri)
            for track in tracks['items']:
                tids.append(track['id'])
            while tracks['next']:
                tracks = sp.next(tracks)
                for track in tracks['items']:
                    tids.append(track['id'])
        track_results.append(tids)
    except spotipy.exceptions.SpotifyException:
        pass
    return [track_results]

def get_results_from_override(sp,args,track_name,artist,album):
    if track_name == '*':
        return get_results_from_override_album(sp,args,artist,album)
    else:
        return []

def find_album(sp,args,artist,album):
    # GPM and Spotify handle multiple artists differently
    if "&" in artist:
        artist = artist.replace("&"," ")
    # Issue with searching for single-quote in title?
    if "'" in album:
        album = album.replace("'"," ")

    search_str = "album:%s artist:%s" % (album, artist)
    results=sp.search(search_str,type='album',market='from_token')
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
    elif args.add or args.show_search_details or args.interactive:
        return select_duplicate_album(sp,args,results_base,artist,album,args.interactive)
    else:
        print("Duplicates found")
        return None

def find_artist(sp,args,artist,prompt_unique):
    # GPM and Spotify handle multiple artists differently
    if "&" in artist:
        artist = artist.replace("&"," ")

    search_str = "artist:%s" % (artist)
    results=sp.search(search_str,type='artist',market='from_token')
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

    show = args.add or args.show_search_details
    prompt = result_count > 1 and prompt_unique
    if show or prompt:
        results_base = select_duplicate_artist(sp,args,results_base,artist,prompt)
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

def process_playlists_add_album(sp,args,playlists,album):
    tracks = sp.album_tracks(album['id'])
    track_ids = []
    for track in tracks['items']:
        track_ids.append(track['id'])
    while tracks['next']:
        tracks = sp.next(tracks)
        for track in tracks['items']:
            track_ids.append(track['id'])
    for playlist in playlists:
        if args.playlist == playlist['name']:
            if args.dryrun:
                print("Would add tracks:")
                pprint.pprint(track_ids)
            else:
                sp.user_playlist_add_tracks(sp.me()['id'],playlist['id'],track_ids)

def open_dataset_csv(args):
    csv_file = open( args.file )
    csv_reader = csv.reader(csv_file,delimiter=',')
    return csv_reader

def open_dataset_html(args):
    page = requests.get(args.url)
    tree = html.fromstring(page.content)
    return tree

def open_dataset(args):
    if args.file:
        return open_dataset_csv(args)
    elif args.metalstorm_top or args.metalstorm_list:
        return open_dataset_html(args)
    else:
        return None

def get_playlist_name_csv(data,args):
    playlist_name = args.file
    if playlist_name[-4] == '.csv':
        playlist_name = playlist_name[0:-4]
    playlist_name = 'GPM: ' + playlist_name
    return playlist_name

def get_playlist_name_html_metalstorm_top(data,args):
    title = data.xpath('//*[@id="page-content"]/div[1]/text()')[0].strip()
    return 'MetalStorm: ' + title + ' (' + datetime.date.today().strftime("%Y-%m-%d") + ')'

def get_playlist_name_html_metalstorm_list(data,args): 
    user = data.xpath('//*[@id="page-content"]/table/tr/td[2]/div[1]/table/tr/td[2]/a/text()')[0].strip()
    date = data.xpath('//*[@id="page-content"]/table/tr/td[2]/div[1]/table/tr/td[2]/span/text()')[0].strip()[2:]
    title = data.xpath('//*[@id="page-content"]/div[1]/text()')[0].strip()
    return 'MetalStorm: ' + user + ": " + title + ' (' + date + ')'

def get_playlist_name(data,args):
    if args.file:
        return get_playlist_name_csv(data,args)
    elif args.metalstorm_top:
        return get_playlist_name_html_metalstorm_top(data,args)
    elif args.metalstorm_list:
        return get_playlist_name_html_metalstorm_list(data,args)
    else:
        return None

def get_tracks_to_import_csv(data,args):
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

def get_tracks_to_import_html_metalstorm_top(data,args):
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

def get_tracks_to_import_html_metalstorm_list(data,args):
    artists = data.xpath('//*[@id="page-content"]/table/tr/td/div/table/tr/td[3]/b/a/text()')
    albums = data.xpath('//*[@id="page-content"]/table/tr/td/div/table/tr/td[3]/a/text()')
    lines = data.xpath('//*[@id="page-content"]/table/tr/td/div/table/tr')

    tracks = []
    for line in lines:
        line_text = line.text_content().strip()
        if not " - " in line_text:
            continue

#        print(line.text_content().strip())
        line_text = line_text.partition(".")[2].strip()
        artist = line_text.partition(" - ")[0].strip()
        album = line_text.partition(" - ")[2].strip()
        album = album.partition("Style:")[0]
        print("(%s;%s)" % (artist, album))
        track = ['*', artist, album]
        tracks.append(track)

    return tracks

def get_tracks_to_import(data,args):
    if args.file:
        return get_tracks_to_import_csv(data,args)
    elif args.metalstorm_top:
        return get_tracks_to_import_html_metalstorm_top(data,args)
    elif args.metalstorm_list:
        return get_tracks_to_import_html_metalstorm_list(data,args)
    else:
        return None

def get_playlist_comments_html(data,args):
    comments = "Imported from " + args.url + " on "+ datetime.date.today().strftime("%Y-%m-%d")
    return comments

def get_playlist_comments(data,args):
    if args.url:
        return get_playlist_comments_html(data,args)
    else:
        return ""

def create_playlist(sp,args):
    found = 0
    notfound = 0
    duplicate = 0
    notfound_list = []
    duplicate_list = []

    data = open_dataset(args)
    playlist_name = get_playlist_name(data,args)
    tracks_to_import = get_tracks_to_import(data,args)
    playlist_comments = get_playlist_comments(data,args)
    playlist_comments_extra = ""

    user = sp.me()['id']

    if not args.dryrun:
        playlist = sp.user_playlist_create( user, playlist_name, public=False )
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

        results = get_results_from_override(sp,args,track_name,artist,album)
        if results == None:
            # overriden to skipped
            print("Search for (%s;%s;%s) skipped by override" % (track_name, artist, album))
            continue

        result_count = len(results)
        actual_count = result_count
        if track_name == '*':
            actual_count = len(results[0])

        if actual_count > 0:
            print("Search for (%s;%s;%s) overridden" % (track_name, artist, album))

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
                results = get_results_for_album(sp,args,artist,album,False,args.interactive)
            else:
                results = get_results_for_track(sp,args,track_name,artist,album,False,args.interactive)

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
                if args.interactive:
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
                    if not args.dryrun:
                        sp.user_playlist_add_tracks( user, playlist_id, tids_for_album )
                        time.sleep(0.1)
            else:
                for track in results:
                    tids.append(track['id'])
#                print("(%s;%s;%s) - added %02d tracks" % (track_name, artist, album, len(tids)))
                if not args.dryrun:
                    sp.user_playlist_add_tracks( user, playlist_id, tids )

        time.sleep(0.1)

    if playlist_comments != "":
        if playlist_comments_extra != "":
            playlist_comments = playlist_comments + ". Not found (%d) %s" % (notfound, playlist_comments_extra)
        print("Setting description to " + playlist_comments)
        if not args.dryrun:
            sp.user_playlist_change_details(user,playlist_id,description=playlist_comments[0:300])

    print("%d found, %d not found, %d chosen on popularity" % (found, notfound, duplicate))

    if notfound > 0:
        print("Not found:")
        for item in notfound_list:
            print(item)

    if duplicate > 0:
        print("Popularity tie-breaker:")
        for item in duplicate_list:
            print(item)


def main():
    args = get_args()

    validate_search_overrides()

    client_id = 'your-client-id'
    client_secret = 'your-client-secret'
    redirect_uri = 'http://localhost/'
    scope = "user-read-private user-library-read playlist-read-private playlist-modify-private user-read-recently-played"
    username = 'your-username'

    with open('credentials.txt','r') as credfile:
        client_id = credfile.readline().strip()
        client_secret = credfile.readline().strip()
        username = credfile.readline().strip()

    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope,client_id=client_id,client_secret=client_secret,redirect_uri=redirect_uri,username=username))
#    sp.trace = True
    sp.trace = False

    user_id = sp.me()['id']

    if args.create:
        create_playlist(sp,args)
    elif args.set_description:
        print("Setting playlist description")
        if args.playlist:
            playlists = sp.user_playlists(user_id)
            for playlist in playlists['items']:
                if playlist['name'] == args.playlist:
                    sp.user_playlist_change_details(user_id,playlist['id'],description=args.set_description)
            while playlists['next']:
                playlists = sp.next(playlists)
                for playlist in playlists['items']:
                    if playlist['name'] == args.playlist:
                        sp.user_playlist_change_details(user_id,playlist['id'],description=args.set_description)
    elif args.find:
        if args.artist and args.album:
            if args.track_name:
                print("Find track")
                album = get_results_for_track(sp,args,args.track_name,args.artist,args.album,True,False)
            else:
                print("Find album")
                album = get_results_for_album(sp,args,args.artist,args.album,True,False)
    elif args.add:
        if args.playlist and args.artist and args.album:
            if args.track_name:
                print("Add track (Not implemented)")
#                track = find_track(sp,args.track_name,args.artist,args.album)
#                if track:
#                    playlists = sp.user_playlists(user_id)
#                    process_playlists_add_track(playlists['items'],sp,args,track)
#                    while playlists['next']:
#                        playlists = sp.next(playlists)
#                        process_playlists_add_track(playlists['items'],sp,args,track)
            else:
                print("Add album")
                album = find_album(sp,args,args.artist,args.album)
                if album:
                    playlists = sp.user_playlists(user_id)
                    process_playlists_add_album(sp,args,playlists['items'],album)
                    while playlists['next']:
                        playlists = sp.next(playlists)
                        process_playlists_add_album(sp,args,playlists['items'],album)
    elif args.delete:
        if args.playlist:
            if args.first_albums:
                print("Deleting initial albums from playlist")
                playlists = sp.user_playlists(user_id)
                process_first_albums(sp,args,playlists['items'])
#                while playlists['next']:
#                    playlists = sp.next(playlists)
#                    process_first_albums(playlists['items'],sp,args)
            elif args.recent:
                tracks = sp.current_user_recently_played()
                process_tracks(sp,args,tracks['items'])
                while tracks['next']:
                    tracks = sp.next(tracks)
                    process_tracks(sp,args,tracks['items'])
            elif args.all:
                playlists = sp.user_playlists(user_id)
                for playlist in playlists['items']:
                    if playlist['name'] == args.playlist:
                        if args.dryrun:
                            print("Would delete playlist %s (%s)" % (platlist['name'], playlist['id']))
                        else:
                            sp.user_playlist_unfollow(user_id,playlist['id'])
                while playlists['next']:
                    playlists = sp.next(playlists)
                    for playlist in playlists['items']:
                        if playlist['name'] == args.playlist:
                            if args.dryrun:
                                print("Would delete playlist %s (%s)" % (platlist['name'], playlist['id']))
                            else:
                                sp.user_playlist_unfollow(user_id,playlist['id'])
    elif args.list:
            if args.first_albums:
                playlists = sp.user_playlists(user_id)
                process_first_albums(sp,args,playlists['items'])
#                while playlists['next']:
#                    playlists = sp.next(playlists)
#                    process_first_albums(playlists['items'],sp,args)
            elif args.recent:
                tracks = sp.current_user_recently_played()
                process_tracks(sp,args,tracks['items'])
                while tracks['next']:
                    tracks = sp.next(tracks)
                    process_tracks(sp,args,tracks['items'])
            elif args.all:
                playlists = sp.user_playlists(user_id)
                for playlist in playlists['items']:
                    if playlist['name'] == args.playlist:
                        tracks = sp.user_playlist_tracks(sp.me()['id'],playlist['id'],limit=50)
                        select_duplicate(sp,args,tracks['items'],'','','',False)
                        while tracks['next']:
                            tracks = sp.next(tracks)
                            select_duplicate(sp,args,tracks['items'],'','','',False)
                while playlists['next']:
                    playlists = sp.next(playlists)
                    for playlist in playlists['items']:
                        if playlist['name'] == args.playlist:
                            tracks = sp.user_playlist_tracks(sp.me()['id'],playlist['id'],limit=50)
                            select_duplicate(sp,args,tracks['items'],'','','',False)
                            while tracks['next']:
                                tracks = sp.next(tracks)
                                select_duplicate(sp,args,tracks['items'],'','','',False)
            elif args.recommendations:
                if args.artist:
                    if args.album:
                        if args.track_name:
                            track = get_results_for_track(sp,args,args.track_name,args.artist,args.album,False,args.interactive)
                            if track and len(track) > 0:
                                tracks = sp.recommendations(seed_tracks=[track[0]['id']])
                                process_tracks(sp,args,tracks['tracks'])
                    else:
                        artist = find_artist(sp,args,args.artist,True)
                        if artist:
                            tracks = sp.recommendations(seed_artists=[artist['id']])
                            process_tracks(sp,args,tracks['tracks'])

                elif args.genre:
                    tracks = sp.recommendations(seed_genres=args.genre)
                    process_tracks(sp,args,tracks['tracks'])

if __name__ == '__main__':
    main()
