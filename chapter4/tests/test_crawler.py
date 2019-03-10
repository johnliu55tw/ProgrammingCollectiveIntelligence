import unittest
from unittest import mock

from bs4 import BeautifulSoup as BS

import crawler

recursive_html_data = """
<body>
  <div>
    <p>Hello</p>
    <a href="abc.com">Some Link</a>
    <div>
      <p>World!</p>
      <p>FooBar</p>
    </div>
  </div>
</body>
"""

link_html_data = """
<body>
  <div>
    <p>Hello</p>
    <a href="https://wut.com">The First Link</a>
    <a href="ftp://not-valid.com">This is FTP link</a>
    <a href="http://only-http.com">The Second Link</a>
    <div>
      <a href="https://deep.com">The Deep Link</a>
    </div>
  <div>
<body>
"""


class WordsFromTextTestCase(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_simple(self):
        data = "This is a all lower words sentence."
        words = crawler.words_from_text(data)

        self.assertEqual(
            words,
            ['this', 'all', 'lower', 'words', 'sentence'])

    def test_separate_by_not_word_character(self):
        data = "This is fully-functional machine^name$money"
        words = crawler.words_from_text(data)

        self.assertEqual(
            words,
            ['this', 'fully', 'functional', 'machine', 'name', 'money'])

    def test_customize_ignore_words(self):
        data = "john is a handsome guy"
        words = crawler.words_from_text(data, ignore_words=['handsome'])

        self.assertEqual(
            words,
            ['john', 'is', 'a', 'guy'])


class GetTextOnlyTestCase(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_return_string_value(self):
        fake_soup = BS("<p>Hello World!</p>", 'html.parser')

        r = crawler.get_text_only(fake_soup)

        self.assertEqual(r, 'Hello World!')

    def test_will_strip_string_value(self):
        fake_soup = BS("<p>\t   Hello World!\n</p>", 'html.parser')

        r = crawler.get_text_only(fake_soup)

        self.assertEqual(r, 'Hello World!')

    def test_recusive_get_text_if_string_is_none(self):
        fake_soup = BS(recursive_html_data, 'html.parser')

        r = crawler.get_text_only(fake_soup)

        self.assertEqual(r, 'Hello\nSome Link\nWorld!\nFooBar')


class IsValidLinkTestCase(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_quote_is_invalid(self):
        self.assertFalse(crawler.is_valid_link("https://some.com/this_contains'"))

    def test_scheme_http(self):
        self.assertTrue(crawler.is_valid_link("http://some.com/foo"))

    def test_scheme_https(self):
        self.assertTrue(crawler.is_valid_link("https://some.com/foo"))

    def test_scheme_ftp_is_invalid(self):
        self.assertFalse(crawler.is_valid_link("ftp://some.com/foo"))


class CrawlerTestCase(unittest.TestCase):

    def setUp(self):
        self.fake_index = mock.MagicMock(spec=crawler.SqliteIndex)
        self.crawler = crawler.Crawler(self.fake_index)

    def tearDown(self):
        pass

    def test_del_method(self):
        self.crawler.__del__()

        self.fake_index.close.assert_called()

    @mock.patch('crawler.requests')
    def test_get_content_returns_soup(self, m_requests):
        m_requests.get().content = recursive_html_data

        soup = self.crawler.get_content('https://some.url.com', timeout=5)

        self.assertIsInstance(soup, BS)

    @mock.patch('crawler.requests')
    def test_get_content_pass_timeout(self, m_requests):
        m_requests.get().content = recursive_html_data

        self.crawler.get_content('https://some.url.com', timeout=5.5)

        m_requests.get.assert_called_with('https://some.url.com', timeout=5.5)

    @mock.patch('crawler.requests')
    def test_get_content_raise_from_raise_for_status(self, m_requests):
        m_requests.get().raise_for_status.side_effect = NotImplementedError('Fake Error')

        with self.assertRaises(NotImplementedError):
            self.crawler.get_content('https://some.url.com', timeout=5.5)

    def test_get_valid_links_return_type(self):
        link_info = self.crawler.get_valid_links(
            'https://this.com',
            BS(link_html_data, 'html.parser'))

        self.assertIsInstance(link_info, list)
        self.assertIsInstance(link_info[0], tuple)

    def test_get_valid_link_with_data(self):
        link_info = self.crawler.get_valid_links(
            'https://this.com',
            BS(link_html_data, 'html.parser'))

        self.assertEqual(link_info[0], ('The First Link', 'https://wut.com'))
        self.assertEqual(link_info[1], ('The Second Link', 'http://only-http.com'))
        self.assertEqual(link_info[2], ('The Deep Link', 'https://deep.com'))

    @mock.patch('crawler.get_text_only')
    @mock.patch('crawler.words_from_text')
    def test_get_words(self, m_words_from_text, m_get_text_only):
        fake_soup = mock.MagicMock(spec=BS)

        result = self.crawler.get_words(fake_soup)

        m_get_text_only.assert_called_with(fake_soup)
        m_words_from_text.assert_called_with(m_get_text_only.return_value)
        self.assertEqual(result, m_words_from_text.return_value)

    @mock.patch.object(crawler.Crawler, 'get_words')
    def test_do_index(self, m_get_words):
        fake_url = 'https://some-fake-url.com/foo/bar'
        fake_soup = mock.MagicMock(spec=BS)

        self.crawler.do_index(fake_url, fake_soup)

        self.crawler.index.add_index.assert_called_with(
            fake_url,
            self.crawler.get_words.return_value)

    @mock.patch.object(crawler.Crawler, 'get_content')
    @mock.patch.object(crawler.Crawler, 'do_index')
    @mock.patch.object(crawler.Crawler, 'get_valid_links')
    def test_crawl_with_depth_1(self, m_get_valid_links, m_do_index, m_get_content):
        self.crawler.index.is_indexed.return_value = False
        self.crawler.get_valid_links.return_value = [('Crawled Link', 'https://crawled-link.com')]
        urls = ['https://fake-1.com/', 'https://fake-2.com/foo/bar']

        self.crawler.crawl(urls, depth=1)

        self.crawler.do_index.assert_has_calls(
            [mock.call(urls[0], m_get_content.return_value),
             mock.call(urls[1], m_get_content.return_value)],
            any_order=True)

    @mock.patch.object(crawler.Crawler, 'get_content')
    @mock.patch.object(crawler.Crawler, 'do_index')
    @mock.patch.object(crawler.Crawler, 'get_valid_links')
    def test_crawl_with_depth_2(self, m_get_valid_links, m_do_index, m_get_content):
        self.crawler.index.is_indexed.return_value = False
        self.crawler.get_valid_links.return_value = [('Crawled Link', 'https://crawled-link.com')]
        urls = ['https://fake-1.com/', 'https://fake-2.com/foo/bar']

        self.crawler.crawl(urls, depth=2)

        self.crawler.do_index.assert_has_calls(
            [mock.call(urls[0], m_get_content.return_value),
             mock.call(urls[1], m_get_content.return_value),
             mock.call('https://crawled-link.com', m_get_content.return_value)],
            any_order=True)

    @mock.patch.object(crawler.Crawler, 'get_content')
    @mock.patch.object(crawler.Crawler, 'do_index')
    @mock.patch.object(crawler.Crawler, 'get_valid_links')
    def test_crawl_will_ignore_indexed_url(self, m_get_valid_links, m_do_index, m_get_content):
        self.crawler.index.is_indexed.side_effect = [False, True]
        url = 'https://fake-1.com/'
        urls = [url, url]

        self.crawler.crawl(urls, depth=1)

        self.crawler.do_index.assert_called_once_with(url, m_get_content.return_value)

        print(self.crawler.do_index.calls)


class SqliteIndexTestCase(unittest.TestCase):

    def setUp(self):
        self.memory_index = crawler.SqliteIndex(':memory:')

    def tearDown(self):
        pass

    @mock.patch('crawler.sqlite3')
    def test_init(self, m_sqlite3):
        index = crawler.SqliteIndex('/path/to/the/sqlite/db')

        self.assertIsInstance(index, crawler.SqliteIndex)
        m_sqlite3.connect.assert_called_with('/path/to/the/sqlite/db')

    @mock.patch('crawler.sqlite3')
    @mock.patch.object(crawler.SqliteIndex, 'init_database')
    def test_init_will_call_init_database(self, m_init_database, m_sqlite3):
        index = crawler.SqliteIndex('/path/to/the/sqlite/db')

        index.init_database.assert_called()

    @mock.patch('crawler.sqlite3')
    @mock.patch.object(crawler.SqliteIndex, 'init_database')
    def test_init_when_init_database_is_false(self, m_init_database, m_sqlite3):
        index = crawler.SqliteIndex('/path/to/the/sqlite/db', init_database=False)

        index.init_database.assert_not_called()

    @mock.patch('crawler.sqlite3')
    def test_close(self, m_sqlite3):
        index = crawler.SqliteIndex('/path/to/the/sqlite/db')

        index.close()
        m_sqlite3.connect().close.assert_called()

    def test_init_database(self):
        # Using the conn object to inspect the database
        cur = self.memory_index.conn.cursor()
        cur.execute("SELECT name FROM sqlite_master "
                    "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")
        table_names = [row[0] for row in cur.fetchall()]
        self.assertIn('url_list', table_names)
        self.assertIn('word_list', table_names)
        self.assertIn('word_location', table_names)
        self.assertIn('link', table_names)
        self.assertIn('link_words', table_names)

    def test_get_entry_id_not_existed_will_be_added(self):
        the_word = 'python'
        row_id = self.memory_index.get_entry_id('word_list', 'word', the_word)

        self.assertEqual(row_id, 1)

        cur = self.memory_index.conn.cursor()
        cur.execute("SELECT word FROM word_list WHERE word = 'python'")
        words = [row[0] for row in cur.fetchall()]
        self.assertEqual(len(words), 1)
        self.assertEqual(words[0], 'python')

    def test_get_entry_id_create_if_not_exist_set_false(self):
        the_word = 'python'
        with self.assertRaises(ValueError):
            self.memory_index.get_entry_id(
                'word_list', 'word', the_word, create_if_not_exist=False)

    def test_add_index_new_url(self):
        the_url = 'https://some.url.com/foo/bar'
        the_words = ['foo', 'bar', 'python', 'nah']
        self.memory_index.add_index(the_url, the_words)

        cur = self.memory_index.conn.cursor()
        # Assert TABLE url_list contains the URL
        cur.execute('SELECT url FROM url_list')
        urls = [row[0] for row in cur.fetchall()]
        self.assertEqual(len(urls), 1)
        self.assertEqual(urls[0], the_url)
        # Assert TABLE word_list contains all the words
        cur.execute('SELECT word FROM word_list')
        words = [row[0] for row in cur.fetchall()]
        self.assertCountEqual(words, the_words)
        # Assert TABLE word_location contains the index information
        cur.execute('SELECT url_id, word_id, location FROM word_location')
        rows = cur.fetchall()
        self.assertCountEqual([(1, 1, 0), (1, 2, 1), (1, 3, 2), (1, 4, 3)], rows)

    def test_add_index_duplicated_url_will_be_ignored(self):
        the_url = 'https://some.url.com/foo/bar'
        first_words = ['foo', 'bar', 'python', 'nah']
        second_words = ['shouldnotexists', 'thisoneeither']
        self.memory_index.add_index(the_url, first_words)
        self.memory_index.add_index(the_url, second_words)

        cur = self.memory_index.conn.cursor()
        # Assert TABLE word_list contains ONLY the first set of words
        cur.execute('SELECT word FROM word_list')
        words = [row[0] for row in cur.fetchall()]
        self.assertCountEqual(words, first_words)
        # Assert TABLE word_location contains ONLY the first set of index
        cur.execute('SELECT url_id, word_id, location FROM word_location')
        rows = cur.fetchall()
        self.assertCountEqual([(1, 1, 0), (1, 2, 1), (1, 3, 2), (1, 4, 3)], rows)

    def test_add_link_ref(self):
        the_url_from = 'https://some.url.com/foo/bar'
        the_url_to = 'https://another.url.com/bar/nah'
        link_words = ['the', 'link', 'to', 'other']

        self.memory_index.add_link_ref(the_url_from, the_url_to, link_words)

        cur = self.memory_index.conn.cursor()
        # Assert link words are stored in TABLE word_list
        cur.execute('SELECT word FROM word_list')
        words = [row[0] for row in cur.fetchall()]
        self.assertCountEqual(words, link_words)
        # Assert the link are stored in TABLE url_list
        cur.execute('SELECT url FROM url_list')
        urls = [row[0] for row in cur.fetchall()]
        self.assertEqual(len(urls), 2)
        self.assertEqual(urls[0], the_url_from)
        self.assertEqual(urls[1], the_url_to)
        # Assert link ref is stored in TABLE link
        cur.execute('SELECT from_id, to_id FROM link')
        rows = cur.fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual((1, 2), rows[0])
        # Assert words to the link are stored in TABLE link_words
        cur.execute('SELECT link_id, word_id FROM link_words')
        rows = cur.fetchall()
        self.assertEqual(len(rows), 4)
        self.assertCountEqual([(1, 1), (1, 2), (1, 3), (1, 4)], rows)
