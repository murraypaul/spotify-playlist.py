# spotify-playlist.py
Python script to perform various useful playlist-related functions on Spotify

Created purely for my own use, but might be of interest to others

# Setup

To use, you need to create an application on the Spotify Developers Dashboard: https://developer.spotify.com/dashboard/applications
Set the redirect url to http://localhost, and make a note of the client ID and secret.

You will need to update the script at the start of the main function to include your client id, client secret and username, or create a file called credentials.txt which contains that information.

For Last.FM integration you will need to do the same for their API.

This script relies on Spotipy to do all of the real work, get it from: https://github.com/plamere/spotipy

Last.FM integration is handled by: https://github.com/pylast/pylast

# Main functions

## Search

You can search for an album or track with eg:

    python spotify-playlist.pl --find --artist Nirvana --album Nevermind
  
If there are multiple results, they will be displayed. The final column is the Spotify URI for the album, which uniquely identifies it.

    Find album
    Results for                           Nirvana;                                        Nevermind
                     01:                  Nirvana;                       Nevermind (Deluxe Edition);        album 1991 40 spotify:album:2uEf3r9i2bnxwJQsxQ0xQ7
                     02:                  Nirvana;                           Nevermind (Remastered);        album 1991 13 spotify:album:2UJcKiJxNryhL050F5Z1Fk
                     03:                  Nirvana;                 Nevermind (Super Deluxe Edition);        album 1991 70 spotify:album:6vZC2UHmEM0vhwVGceVVi2

## Add items to playlists

You can add an album to a playlist with:

    python spotify-playlist.pl --add --artist Nirvana --album Nevermind --playlist <playlist name>
 
If you add --interactive then the script will prompt when there are duplicated to allow you which one to add.

If you add --dryrun then the script will not actually add anything, just say what would be added.

## Overrides

If a search returns duplicates or does not find the correct album, you can manually add a search override to select the correct result.

This is mainly useful if you are automatically creating playlists from files or URLs.

Add a line to overrides.txt in this format:

    *;; Virgin Steele;; The House Of Atreus Act I;; spotify:album:47CVkzdB6oe4SH1OlPljD3
    *;; Virgin Steele;; The House Of Atreus Act II';; !None
    *;; Periphery;; Juggernaut: Alpha & Omega,spotify:album:5oF7PocZron3xn8Pxhofgx;; spotify:album:2vUuAbaoqFPcbp851dRXFt
    *;; Periphery;; Periphery II: This Time It\'s Personal;; spotify:album:5ebIq78IE2Pi9vyJOaYL4A

The first line maps input artist and album names to a Spotify album URI.

The second line says not to map this line, but it ignore it. (In this case because the first line is a double album with both parts.)

The third line maps a single set of artist and album name inputs to two Spotify album URIs.

The fourth line shows that if the input contains quote characters you have to escape them.

## Recommendations

You can get recommendations based on an artist or track with eg:

    python spotify-playlist.py --list --recommendations --artist Nirvana --album Nevermind --track "Smells like teen spirit"

    Results for                                  ;                         ;
                     01:               Can't Stop;    Red Hot Chili Peppers;                      By the Way (Deluxe Edition);        ALBUM   2002 07/00 04:29 81 spotify:track:3ZOEytgrvLwQaqXreDs2Jx
                     02: The Number of the Beast ;              Iron Maiden;          The Number of the Beast (2015 Remaster);        ALBUM   1982 05/00 04:50 68 spotify:track:3nlGByvetDcS1uomAoiBmy
                     03:                Bombtrack; Rage Against The Machine; Rage Against The Machine - XX (20th Anniversary ;        ALBUM Y 1992 01/00 04:03 66 spotify:track:2rBHnIxbhkMGLpqmsNX91M
                     04:                    Today;    The Smashing Pumpkins; (Rotten Apples) The Smashing Pumpkins Greatest H;        ALBUM   2001 05/00 03:22 58 spotify:track:1XPta4VLT78HQnVFd1hlsK
                     05:           Clint Eastwood;                 Gorillaz;                                         Gorillaz;        ALBUM Y 2001 05/00 05:40 70 spotify:track:7yMiX7n9SBvadzox8T5jzT
                     06:                  Breathe;              The Prodigy;           The Fat of the Land - Expanded Edition;        ALBUM   1997 02/00 05:34 67 spotify:track:5oPUBUzrAnwvlmMzl1VW7Y
                     07:                 Fly Away;            Lenny Kravitz;                                                5;        ALBUM   1998 08/00 03:41 71 spotify:track:1OxcIUqVmVYxT6427tbhDW
                     08:             Like a Stone;               Audioslave;                                       Audioslave;        ALBUM   2002 05/00 04:53 46 spotify:track:2xt2piJx6jlFkjS77YiqpL
                     09:           Coming for You;            The Offspring;                                   Coming for You;        ALBUM Y 2015 01/00 03:49 57 spotify:track:1SZoPX6yKcuejHQ49DtDxr
                     10:            Enter Sandman;                Metallica;                                        Metallica;        ALBUM   1991 01/00 05:31 79 spotify:track:5sICkBXVmaCQk5aISGR3x1
                     11:   1979 - Remastered 2012;    The Smashing Pumpkins; Mellon Collie And The Infinite Sadness (Deluxe E;        ALBUM   1995 05/00 04:26 76 spotify:track:5QLHGv0DfpeXLNFo7SFEy1
                     12:          Come As You Are;                  Nirvana;                       Nevermind (Deluxe Edition);        ALBUM   1991 03/00 03:38 78 spotify:track:0MKGH8UMfCnq5w7nG06oM5
                     13: Holiday / Boulevard of B;                Green Day;                                   American Idiot;        ALBUM Y 2004 03/00 08:13 71 spotify:track:0MsrWnxQZxPAcov7c74sSo
                     14:      Killing In The Name; Rage Against The Machine; Rage Against The Machine - XX (20th Anniversary ;        ALBUM Y 1992 02/00 05:13 79 spotify:track:59WN2psjkt1tyaxjspN8fp
                     15: London Calling - Remaste;                The Clash;                      London Calling (Remastered);        ALBUM   1979 01/00 03:20 74 spotify:track:5jzma6gCzYtKB1DbEwFZKH
                     16:              Break Stuff;              Limp Bizkit;                                Significant Other;        ALBUM Y 1999 04/00 02:46 73 spotify:track:5cZqsjVs6MevCnAkasbEOX
                     17:                     Walk;                  Pantera;                          Vulgar Display of Power;        ALBUM Y 1992 03/00 05:15 74 spotify:track:7fcfNW0XxTWlwVlftzfDOR
                     18:            The Bad Touch;          Bloodhound Gang;                               Hooray For Boobies;        ALBUM Y 1999 10/00 04:20 72 spotify:track:5EYdTPdJD74r9EVZBztqGG
                     19: Are You Gonna Be My Girl;                      Jet;                                         Get Born;        ALBUM   2003 02/00 03:33 76 spotify:track:305WCRhhS10XUcH6AEwZk6
                     20:             Pet Sematary;                  Ramones;                                      Brain Drain;        ALBUM   1989 07/00 03:30 50 spotify:track:2PN0JeaGtkHrlcmwZFWzBM

## List recently played items
You can show recently played tracks with:

    python spotify-playlist.pl --list --recent

You can show recently played tracks from a specific playlist with:

    python spotify-playlist.pl --list --recent --playlist <playlist name>

## List items from playlists

You can show all tracks on a playlist with:

    python spotify-playlist.pl --list --all --playlist <playlist name>
    
You can show the only tracks on the first N albums on a playlist with:

    python spotify-playlist.pl --list --first_albums N --playlist <playlist name> --show_tracks   

You can show just the album detais for the first N albums on a playlist with:

    python spotify-playlist.pl --list --first_albums N --playlist <playlist name>

## Playcounts

By default track listings will show playcounts from Spotify's recently played tracks data.
This will only ever include the 50 most recently played tracks.

By adding --last-fm to a command, and entering Last.FM api details in credentials.txt, you
can instead use Last.FM scrobbling data.

By default all scrobbled data will be loaded the first time you use the --last-fm option,
and will then be cached in a local file. Subsequent calls will only load scrobbled since the
previous call. This means that the very first time you run the script with the --last-fm 
option, expect it to take several minutes to load, if you have a large Last.FM history.

If you do not want this behaviour, you can instead say to just load the most recent X scrobbles
with --last-fm-recent-count X. These will not be cached, but reloaded each time.

Playcounts will be shown between the track number and the track title, and show L for Last.FM
scrobble data or S for Spotify recent tracks data.

eg.

                     01:      Right Next Door To Hell;            Guns N' Roses;                              Use Your Illusion I;        album Y 1991 01/16 03:02 -1 spotify:track:5YXvG4PL4Wisyx2ScUxVFF
                     02:                Dust N' Bones;            Guns N' Roses;                              Use Your Illusion I;        album Y 1991 02/16 04:58 -1 spotify:track:4vtXsXvSYaTfKQ0dJXbJGu
                     03: L 1         Live And Let Die;            Guns N' Roses;                              Use Your Illusion I;        album   1991 03/16 03:02 -1 spotify:track:0rFWuqFgHAfuzE8uSB9TWR

                     01: S 1                   S.O.Y.;                 Alkymist;                                        Sanctuary;        album   2020 03/08 01:41 08 spotify:track:27VSW6dfReqd3YISUeVZFU
                     02: S 1                 The Dead;                 Alkymist;                                        Sanctuary;        album   2020 02/08 06:08 12 spotify:track:1VVGWpCKVgWMzM1C73mG64
                     03: S 1                   Oethon;                 Alkymist;                                        Sanctuary;        album   2020 01/08 07:03 11 spotify:track:69R9bNNCMKu89siZSYgqfG
                 
## Playlist membership

By adding the --show-playlist-membership parameter to a command, any track listing will show which of your user playlists any track already belongs to.

The first time you use the flag the script has to load all of your user playlist data from Spotify, which will take a while.

It is then cached locally to a file, and playlists data is only requeried when it changes in Spotify.

## Remove items from playlists

You can remove tracks on the first N albums on a playlist with:

    python spotify-playlist.pl --delete --first_albums N --playlist <playlist name>

You can remove recently played tracks from a specific playlist with:

    python spotify-playlist.pl --delete --recent --playlist <playlist name>

## Create playlists

You can create a playlist from a CSV file with:

    python spotify-playlist.pl --create --file <file.csv> 
    
The CSV file is expected to be in the format Track, Artist, Album, * (further columns are ignored), with no header row.

The playlist name is taken from the file name.

Spotify allows duplicate playlist names, so if you run the same command multiple times you will get multiple playlists with the same name.

You can set the description for a playlist with:

    python spotify-playlist.pl --set-description <desc> --playlist <playlist name>

## Export playlists

You can export all playlists to separate CSV files, named after the playlists, with:

    python spotify-playlist.pl --export

You can export a single playlist to a CSV file named after the playlist with:

    python spotify-playlist.pl --export --playlist <playlist name>

You can export a single playlist to a CSV file with a given file name with:

    python spotify-playlist.pl --export --playlist <playlist name> --file <file name>
    
The export format is Track, Artist, Album, Sequence, Track URI, Album URI.
This format is suitable for re-importing with the --create function.

