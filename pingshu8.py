#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: Seaky
# @Date:   2019/6/12 13:27


import argparse
import copy
import math
import os
import re
from pathlib import Path
from urllib import parse

import requests
from bs4 import BeautifulSoup
from mutagen.easyid3 import EasyID3

# pip install requests beautifulsoup4 mutagen
# python pingshu8.py --url http://www.pingshu8.com/musiclist/mmc_198_1171_1.htm

HOST = 'http://www.pingshu8.com'

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36'}


class Album:
    def __init__(self, url, overwrite=False, limit=10000):
        self.album_url = self.fullurl(url)
        self.overwrite = overwrite
        self.limit = limit
        self.tracks = []
        self.ss = requests.session()
        self.ss.headers = headers

    @staticmethod
    def fullurl(url):
        if not url.startswith('http://'):
            url = HOST + url
        return url

    @staticmethod
    def zfill(name, n=3):
        ks = name.split('.')
        if len(ks) > 1 and ks[0].isdigit():
            ks[0] = ks[0].zfill(n)
            if ks[0] == ks[1]:
                ks = ks[1:]
        return '.'.join(ks)

    def fetch(self, url):
        raw = self.ss.get(url, headers=headers).content
        m = re.search('charset=\W*(?P<charset>\w+)', raw[:200].decode(errors='ignore'))
        charset = m.groupdict().get('charset', 'utf-8')
        if charset == 'gb2312':
            charset = 'cp936'
        return raw.decode(encoding=charset)

    def parse(self, url=None):
        content = self.fetch(url or self.album_url)
        soup = BeautifulSoup(content, 'html.parser')
        if not hasattr(self, 'album_name'):
            self.album_name = soup.find('div', align="left").h1.text
            self.length = int(re.search('(\d+)', str(soup.find(string=re.compile('共有')).string)).group(1))
            print('album: {}, tracks: {}'.format(self.album_name, self.length))
        self.tracks.extend([{'url': self.fullurl(x.a['href'].replace('/play_', '/down_')),
                             'name': x.text} for x in soup('li', class_='a1')])
        next = soup.find('a', string='下一页')
        if len(self.tracks) < self.limit and next:
            return self.parse(url=self.fullurl(soup.find('a', string='下一页')['href']))
        n = math.ceil(math.log(self.length, 10))
        for x in self.tracks:
            x['name'] = self.zfill(x['name'], n)
        return True

    def download(self):
        for x in self.tracks:
            try:
                self._download(x)
            except Exception as e:
                print('download {} fail, {}'.format(x['name'], e))

    def _download(self, track):
        content = self.fetch(track['url'])
        url1 = HOST + parse.unquote(parse.unquote(re.search('(pingshu://\S+)', content).group(1)))[12:-7]
        hd = copy.deepcopy(headers)
        hd['Referer'] = HOST
        resp = self.ss.get(url1, headers=hd, allow_redirects=False)
        raw_file_url = resp.headers['Location']
        # convert hex string to utf-8
        file_url = parse.quote(bytes.fromhex(''.join([hex(ord(x)).replace('0x', '') for x in raw_file_url])),
                               safe=':/?=&')
        folder = Path(self.album_name)
        folder.mkdir(exist_ok=True)
        filepath = folder / (track['name'] + '.mp3')
        if not filepath.exists() or os.path.getsize(str(filepath)) == 0 or self.overwrite:
            open(str(filepath), 'wb').write(self.ss.get(file_url, headers=hd).content)
            msg = 'download {}.'.format(str(filepath))
            try:
                tags = EasyID3(str(filepath))
                tags['album'] = self.album_name
                tags['title'] = track['name']
                tags['artist'] = 'www.pingshu8.com'
                tags['genre'] = ''
                tags.save()
                msg += ' retag it.'
            except Exception as e:
                msg += 'retag fail, {}'.format(e)
            print(msg)
        else:
            print('skip {}.'.format(str(filepath)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True, help='album url')
    parser.add_argument('--limit', type=int, default=10000, help='download limit')
    parser.add_argument('--overwrite', action="store_true", help='overwrite')
    args = parser.parse_args()

    ab = Album(url=args.url, overwrite=args.overwrite, limit=args.limit)
    ab.parse() and ab.download()
