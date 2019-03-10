import re
import logging
import sqlite3
from urllib.parse import urljoin, urldefrag, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

IGNORE_WORDS = ['the', 'of', 'to', 'and', 'a', 'in', 'is', 'it']


def words_from_text(text, ignore_words=IGNORE_WORDS):
    ignore_words = set(ignore_words)
    splitter = re.compile(r'\W+')
    words = (s.lower() for s in splitter.split(text) if s != '')
    no_ignore_words = filter(lambda x: x not in ignore_words, words)
    return list(no_ignore_words)


def get_text_only(soup):
    s = soup.string
    if s is not None:
        return s.strip()
    else:
        res_text = ''
        for child in soup.children:
            sub_text = get_text_only(child)
            res_text += sub_text + '\n' if sub_text else ''

        return res_text.strip()


def is_valid_link(url):
    return "'" not in url and urlparse(url).scheme in ('http', 'https')


class SqliteIndex:

    def __init__(self, db_name, init_database=True):
        self.conn = sqlite3.connect(db_name)

        if init_database:
            self.init_database()

    def close(self):
        self.conn.close()

    def init_database(self):
        cur = self.conn.cursor()
        cur.execute('CREATE TABLE url_list(url)')
        cur.execute('CREATE TABLE word_list(word)')
        cur.execute('CREATE TABLE word_location(url_id, word_id, location)')
        cur.execute('CREATE TABLE link(from_id INTEGER, to_id INTEGER)')
        cur.execute('CREATE TABLE link_words(word_id, link_id)')
        cur.execute('CREATE INDEX word_idx ON word_list(word)')
        cur.execute('CREATE INDEX url_idx ON url_list(url)')
        cur.execute('CREATE INDEX word_url_idx ON word_location(word_id)')
        cur.execute('CREATE INDEX url_to_idx ON link(to_id)')
        cur.execute('CREATE INDEX url_from_idx ON link(from_id)')
        self.conn.commit()

    def get_entry_id(self, table, column, value, create_if_not_exist=True):
        cur = self.conn.cursor()
        cur.execute(f'SELECT rowid FROM {table} WHERE {column} = ?', (value, ))
        result = cur.fetchone()

        if result is not None:
            return result[0]
        elif create_if_not_exist:
            cur.execute(f'INSERT INTO {table}({column}) VALUES (?)', (value, ))
            self.conn.commit()
            return cur.lastrowid
        else:
            raise ValueError(f'{value} not exists in {table}.{column}')

    def is_indexed(self, url):
        # The url is in TABLE url_list
        cur = self.conn.cursor()
        cur.execute('SELECT rowid FROM url_list WHERE url = ?', (url, ))
        result = cur.fetchone()
        if result is None:
            return False

        # TABLE word_location contains information of this URL
        # The URL could be added by add_link_ref method, not add_index.
        url_id = result[0]
        cur.execute('SELECT * FROM word_location WHERE url_id = ?', (url_id, ))
        if cur.fetchone() is None:
            return False

        return True

    def add_index(self, url, words):
        if self.is_indexed(url):
            return

        logger.info(f'Adding index for {url}')

        url_id = self.get_entry_id('url_list', 'url', url)
        cur = self.conn.cursor()

        for idx, word in enumerate(words):
            word_id = self.get_entry_id('word_list', 'word', word)
            cur.execute('INSERT INTO word_location(url_id, word_id, location) '
                        'VALUES (?, ?, ?)', (url_id, word_id, idx))

        self.conn.commit()

    def add_link_ref(self, url_from, url_to, link_words):
        from_id = self.get_entry_id('url_list', 'url', url_from)
        to_id = self.get_entry_id('url_list', 'url', url_to)

        if from_id == to_id:
            return

        cur = self.conn.cursor()
        cur.execute('INSERT INTO link(from_id, to_id) VALUES (?, ?)', (from_id, to_id))

        link_id = cur.lastrowid
        for word in link_words:
            word_id = self.get_entry_id('word_list', 'word', word)
            cur.execute('INSERT INTO link_words(link_id, word_id) VALUES (?, ?)',
                        (link_id, word_id))

        self.conn.commit()


class Crawler(object):

    def __init__(self, index):
        self.index = index

    def __del__(self):
        self.index.close()

    def get_content(self, url, timeout):
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f'Failed to get {url}: {e}')
            raise
        else:
            return BeautifulSoup(resp.content, 'html.parser')

    def get_words(self, soup):
        return words_from_text(get_text_only(soup))

    def get_valid_links(self, url, soup):
        links = soup('a')
        link_infos = ((get_text_only(link), urldefrag(urljoin(url, link['href']))[0])
                      for link in links if 'href' in link.attrs)
        clean_links = filter(lambda link_info: is_valid_link(link_info[1]), link_infos)

        return list(clean_links)

    def do_index(self, url, soup):
        try:
            words = self.get_words(soup)
        except Exception as e:
            logger.error(f'Failed to parse content into words: {e}')
            raise

        try:
            self.index.add_index(url, words)
        except Exception as e:
            logger.error(f'Failed to add index into database: {e}')
            raise

        logger.debug(f'Finished indexing {url}')

    def do_link_ref(self, this_url, link_url, link_text):
        link_words = words_from_text(link_text)
        self.index.add_link_ref(this_url, link_url, link_words)

    def crawl(self, urls, depth=2, timeout=3.0):
        next_urls = set()
        not_indexed_url = (url for url in urls if self.index.is_indexed(url) is False)

        for url in not_indexed_url:
            try:
                logger.info(f'Indexing {url}')
                soup = self.get_content(url, timeout=timeout)
                self.do_index(url, soup)
            except Exception as e:
                logger.warning(f'Cannot indexing {url}: {e}. Skipped.')
                continue
            else:
                for link_text, link_url in self.get_valid_links(url, soup):
                    self.do_link_ref(url, link_url, link_text)
                    next_urls.add(link_url)

        depth -= 1
        if depth == 0:
            return
        else:
            self.crawl(next_urls, depth, timeout)
