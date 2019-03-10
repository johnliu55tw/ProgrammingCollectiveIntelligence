import re
import logging
import sqlite3
from urllib.parse import urljoin, urldefrag, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

IGNORE_WORDS = ['the', 'of', 'to', 'and', 'a', 'in', 'is', 'it']


class CrawlerOld:

    def __init__(self, db_name):
        self.conn = sqlite3.connect(db_name)

    def __del__(self):
        self.conn.close()

    def get_entry_id(self, table, field, value, create_new=True):
        cur = self.conn.cursor()
        cur.execute(f'SELECT rowid FROM {table} WHERE {field} = ?', (value, ))
        result = cur.fetchone()

        if result is not None:
            return result[0]
        elif create_new:
            cur.execute(f'INSERT INTO {table}({field}) VALUES (?)', (value, ))
            self.conn.commit()
            return cur.lastrowid
        else:
            raise ValueError(f'{value} not exists in {table}:{field}')

    def add_to_index(self, url, soup):
        if self.is_indexed(url):
            return

        logger.info(f'Indexing {url}')

        # Get individual words
        text = self.get_text_only(soup)
        words = self.separate_words(text)

        # Get the URL id
        url_id = self.get_entry_id('url_list', 'url', url)

        # Link each word to this url
        cur = self.conn.cursor()
        for idx, word in enumerate(words):
            if word in IGNORE_WORDS:
                continue
            word_id = self.get_entry_id('word_list', 'word', word)
            cur.execute('INSERT INTO word_location(url_id, word_id, location) '
                        'VALUES (?, ?, ?)', (url_id, word_id, idx))
        self.conn.commit()

    def get_text_only(self, soup):
        s = soup.string
        if s is not None:
            return s.strip()
        else:
            result_text = ''
            for tag in soup.contents:
                sub_text = self.get_text_only(tag)
                result_text += sub_text + '\n'
            return result_text

    def separate_words(self, text):
        splitter = re.compile(r'\W+')
        return [s.lower() for s in splitter.split(text) if s != '']

    def is_indexed(self, url):
        cur = self.conn.cursor()
        result = cur.execute('SELECT rowid FROM url_list WHERE url = ?', (url, )).fetchone()

        if result is None:
            return False
        else:
            # Ensure that it's actually been crawled
            url_id = result[0]
            cur.execute('SELECT * FROM word_location WHERE url_id = ?', (url_id, ))
            if cur.fetchone() is not None:
                return True
            else:
                logger.warning(f'{url} in url_list but word_location has no data!')

    def add_link_ref(self, url_from, url_to, link_text):
        words = self.separate_words(link_text)
        from_id = self.get_entry_id('url_list', 'url', url_from)
        to_id = self.get_entry_id('url_list', 'url', url_to)

        if from_id == to_id:
            return

        cur = self.conn.cursor()
        cur.execute('INSERT INTO link(from_id, to_id) VALUES (?, ?)', (from_id, to_id))

        link_id = cur.lastrowid
        for word in words:
            if word in IGNORE_WORDS:
                continue
            word_id = self.get_entry_id('word_list', 'word', word)
            cur.execute('INSERT INTO link_words(link_id, word_id) VALUES (?, ?)',
                        (link_id, word_id))

        self.conn.commit()

    def crawl(self, pages, depth=2, request_timeout=3.0):
        for i in range(depth):
            new_pages = set()
            for page in pages:
                logger.info(f'Crawling {page}')
                try:
                    resp = requests.get(page, timeout=request_timeout)
                    resp.raise_for_status()
                except Exception as e:
                    logger.warning(f'Cannot open {page}: {e}')
                    continue
                else:
                    soup = BeautifulSoup(resp.content, 'html.parser')
                    self.add_to_index(page, soup)

                links = soup('a')
                parsed_links = ((link, urldefrag(urljoin(page, link['href']))[0])
                                for link in links if 'href' in link.attrs)
                for link, url in parsed_links:
                    if "'" in url:
                        logger.warning(f'Single quote in url: {url}')
                        continue

                    if urlparse(url).scheme in ('http', 'https') and not self.is_indexed(url):
                        new_pages.add(url)

                    self.add_link_ref(page, url, self.get_text_only(link))

                self.conn.commit()

            pages = new_pages

    def create_index_tables(self):
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
