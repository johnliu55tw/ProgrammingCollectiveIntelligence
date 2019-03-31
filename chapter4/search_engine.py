import re
import logging
import sqlite3
from urllib.parse import urljoin, urldefrag, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

IGNORE_WORDS = ['the', 'of', 'to', 'and', 'a', 'in', 'is', 'it']


class Crawler:

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


class Searcher(object):

    def __init__(self, dbname):
        self.con = sqlite3.connect(dbname)

    def __del__(self):
        self.con.close()

    def get_word_id(self, word):
        cur = self.con.cursor()
        cur.execute('SELECT rowid FROM wordlist WHERE word = ?', (word, ))
        row = cur.fetchone()

        return row[0]

    def gen_query(self, word_ids):
        tables = []
        columns = ['w0.urlid']
        clauses = []

        for idx, word_id in enumerate(word_ids):
            tables.append(f'wordlocation as w{idx}')
            columns.append(f'w{idx}.location')
            if idx == 0:
                clauses.append(f'w{idx}.wordid = {word_id}')
            else:
                clauses.append(f'w{idx}.wordid = {word_id} AND w{idx-1}.urlid = w{idx}.urlid')

        tables_string = ', '.join(tables)
        columns_string = ', '.join(columns)
        clauses_string = ' AND '.join(clauses)

        return f'SELECT {columns_string} FROM {tables_string} WHERE {clauses_string}'

    def get_match_rows(self, q):
        words = q.split(' ')
        word_ids = list(filter(None, (self.get_word_id(word) for word in words)))
        query = self.gen_query(word_ids)
        print(query)

        cur = self.con.cursor()
        cur.execute(query)

        rows = [row for row in cur]

        return (rows, word_ids)

    def get_match_rows_old(self, q):
        # Strings to build the query
        fieldlist = 'w0.urlid'
        tablelist = ''
        clauselist = ''
        wordids = []

        # Split the words by spaces
        words = q.split(' ')
        tablenumber = 0

        for word in words:
            # Get the word ID
            wordrow = self.con.execute(
                'SELECT rowid FROM wordlist WHERE word = ?', (word, )).fetchone()

            if wordrow is not None:
                wordid = wordrow[0]
                wordids.append(wordid)
                if tablenumber > 0:
                    tablelist += ','
                    clauselist += ' and '
                    clauselist += 'w%d.urlid=w%d.urlid and ' % (tablenumber-1, tablenumber)
                fieldlist += ',w%d.location' % tablenumber
                tablelist += 'wordlocation w%d' % tablenumber
                clauselist += 'w%d.wordid=%d' % (tablenumber, wordid)
                tablenumber += 1

        # Create the query from the separate parts
        fullquery = 'select %s from %s where %s' % (fieldlist, tablelist, clauselist)
        print(fullquery)
        cur = self.con.execute(fullquery)
        rows = [row for row in cur]

        return rows, wordids
