import os
from collections import defaultdict
import urllib
from io import open
from similar_text import similar_text
from zhconv import convert
import re


NETEASE_LYRIC_SEARCH_API = "http://music.163.com/api/search/get/web?s=%s&offset=0&limit=50&total=true&type=1"
NETEASE_LYRIC_DOWNLOAD_API = "http://music.163.com/api/song/lyric?os=pc&id=%s&lv=-1&kv=0&tv=-1"
QUERY_SLEEP_TIME = 0.1 # How long to sleep before firing off each API request.
LYRICS_PATH = Prefs['lyric_path']
ENABLE_DEBUG = Prefs['show_debug_info']
USE_ITUNES_NAME_STYLE = Prefs['itunes_name_style']

def download_lyric(track_id): 
    url = NETEASE_LYRIC_DOWNLOAD_API % str(track_id)
    headers = {'content-type': 'application/json; charset=utf-8'}

    if ENABLE_DEBUG: Log("download url: " + url)
    try:
        response = JSON.ObjectFromURL(url, sleep=QUERY_SLEEP_TIME, cacheTime=CACHE_1MONTH, headers=headers)
        if ENABLE_DEBUG: Log("download response: " + str(response))
        if isinstance(response, dict):
            return response['lrc']['lyric']
    except:
        Log('Error fetching Json.')
        return None


def search_lyric(artist, album, title):
    if not title:
        return list()

    url = NETEASE_LYRIC_SEARCH_API % urllib.quote(title)
    headers = {'content-type': 'application/json; charset=utf-8'}
    if ENABLE_DEBUG: Log("search url: " + url)
    if ENABLE_DEBUG: Log("title: " + title)
    if ENABLE_DEBUG: Log("album: " + album)
    if ENABLE_DEBUG: Log("artist: " + artist)
    try:
        response = JSON.ObjectFromURL(url, sleep=QUERY_SLEEP_TIME, cacheTime=CACHE_1MONTH, headers=headers)
        if ENABLE_DEBUG: Log('search response: ' + str(response))
        if response.has_key('error'):
            return list()            
        else:
            if ENABLE_DEBUG: Log('song info:' + str(response['result']['songs']))
            song_array = response['result']['songs']
            exactly_macth_res = list()
            partially_match_res = list()
            if len(song_array) == 0:
                return list()
            for song in song_array:
                title_lower = title.lower()
                result_title_lower = song['name'].lower()
                if ENABLE_DEBUG: Log("result_title_lower :" + result_title_lower)
                if title_lower == result_title_lower:
                    exactly_macth_res.append(song)
                elif title_lower in result_title_lower or result_title_lower in title_lower or similar_text(result_title_lower, title_lower) > 90:
                    partially_match_res.append(song)
            
            song_array = exactly_macth_res if len(exactly_macth_res) != 0 else partially_match_res
            if ENABLE_DEBUG: Log("song_arr: " + str(song_array))

            all_foundings = list()
            for song in song_array:
                info_dict = dict()
                info_dict['id'] = song['id']
                info_dict['artist'] = song['artists'][0]['name']
                info_dict['album'] = song['album']['name']
                info_dict['title'] = song['name']

                if ENABLE_DEBUG: Log("song info_dict :" + str(info_dict))
                max_rate = 0
                for one_artist in song['artists']:
                    score = similar_text(artist, one_artist['name'])
                    if score > max_rate:
                        max_rate = score
                        info_dict['artist'] = one_artist['name']

                all_foundings.append(info_dict)

            all_foundings = sorted(all_foundings, key=lambda x: compare(artist, album, title, x['artist'], x['album'], x['title']), reverse = True)
            return all_foundings
    except Exception as e:
        Log('Error searching track: %s' % title)
        Log('Error message: %s' % str(e))
        return list()

def compare(artist, album, title, fetched_artist, fetched_album, fetched_title):
    if ENABLE_DEBUG: Log("fetched_title: " + fetched_title)
    if ENABLE_DEBUG: Log("fetched_artist: " + fetched_artist)
    if ENABLE_DEBUG: Log("fetched_album: " + fetched_album)

    score_artist = similar_text(artist, fetched_artist)
    score_title = similar_text(title, fetched_title)
    score_album = similar_text(album, fetched_album)
    return score_artist + score_title + score_album
    

class NeteaseMusicLyricFindAlbumAgent(Agent.Album):
    name = 'NeteaseMusicLyricFind'
    languages = [Locale.Language.NoLanguage]
    primary_provider = True
    # accepts_from = ['com.plexapp.agents.localmedia','com.plexapp.agents.lyricfind']
    # contributes_to = ['com.plexapp.agents.plexmusic', 'com.plexapp.agents.localmedia', 'com.plexapp.agents.lastfm', 'com.plexapp.agents.naver_music']

    def search(self, results, media, lang, manual=False, tree=None):
        results.add(SearchResult(id = 'null', score = 100))
    
    def update(self, metadata, media, lang):
        valid_keys = defaultdict(list)
        path = None
        for index, track in enumerate(media.children):
            track_key = track.guid or index
            track_key = track_key.split('/')[-1]
            for item in track.items:
                for part in item.parts:
                    try:
                        filename = part.file
                        path = os.path.dirname(filename)
                        (file_root, _) = os.path.splitext(filename)
            
                        path_files = {}
                        for p in os.listdir(path):
                            path_files[p.lower()] = p
                                
                        meta_info_from_path = filename[:-4].split(os.path.sep)
                        artist = convert(meta_info_from_path[-3].decode('utf-8'), 'zh-cn').encode('utf-8')
                        album = convert(meta_info_from_path[-2].decode('utf-8'), 'zh-cn').encode('utf-8')
                        title = convert(meta_info_from_path[-1].decode('utf-8'), 'zh-cn').encode('utf-8')
                        if USE_ITUNES_NAME_STYLE:
                            title = re.sub(r'(^[1-9]+\s)|(^[1-9]+-[1-9]+\s)', '', title)

                        lrcfilename = artist + '_' + album + '_' + title + '.lrc'
                        lrcfilename = os.path.join(LYRICS_PATH, lrcfilename).replace(" ", "")
                        if ENABLE_DEBUG: Log("file_name: " + lrcfilename)
                        
                        if not os.path.exists(lrcfilename):
                            query = search_lyric(artist, album, title)
                            if ENABLE_DEBUG: Log('Query %s' % query)
                            lyric = download_lyric(query[0]['id']) if len(query) > 0 else None
                            if ENABLE_DEBUG: Log('Lyric %s' % lyric)
                            if lyric is not None:
                                with open(lrcfilename,'w+',encoding='utf8') as f:
                                    f.write(lyric)
                                    f.close()
                                metadata.tracks[track_key].lyrics[lrcfilename] = Proxy.LocalFile(lrcfilename, format='lrc')
                                valid_keys[track_key].append(lrcfilename)
                        else:
                            metadata.tracks[track_key].lyrics[lrcfilename] = Proxy.LocalFile(lrcfilename, format='lrc')
                            valid_keys[track_key].append(lrcfilename)
                    except Exception as e:
                        Log('Error %s ' %  e)
                    
        for key in metadata.tracks:
            metadata.tracks[key].lyrics.validate_keys(valid_keys[key])
