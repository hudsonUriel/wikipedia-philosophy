"""
The Philosophy Game
~~~~~~~~~~~~~~~~~~~~~~~~~

Clicking on the first non-parenthesized, non-italicized link,
in the main text of a Wikipedia article, and then repeating
the process for subsequent articles, usually eventually gets
one to the Philosophy article. (See
https://en.wikipedia.org/wiki/Wikipedia:Getting_to_Philosophy
for more information)

The Philosophy Game, written in Python, lets you do the clicking
programmatically.

Basic usage:

    >>> from philosophy import *
    >>> game = PhilosophyGame('Python (programming language)')
    >>> for s in game.trace():
    ...     print(s)
    ...
    >>>

Handling errors:
    >>> from philosophy import *
    >>> game = PhilosophyGame('Python (programming language)')
    >>> try:
    ...     for s in game.trace():
    ...         print(s)
    ... except ConnectionError:
    ...     sys.exit('Network error, please check your connection')
    ... except MediaWikiError as e:
    ...     sys.exit('MediaWiki API error {1}: {2}'.format(e.errors['code'],
    ...                                                e.errors['info']))
    ... except LoopException:
    ...     sys.exit('Loop detected, exiting...')
    ... except InvalidPageNameError as e:
    ...     sys.exit(e)
    ... except LinkNotFoundError as e:
    ...     sys.exit(e)
"""

import requests
from requests.exceptions import ConnectionError
import lxml.html as lh
import json

class MediaWikiError(Exception):
    """
    Thrown when the MediaWiki API returns an error.
    """
    def __init__(self, message, errors):
        super(MediaWikiError, self).__init__(message)
        self.errors = errors

class LoopException(Exception):
    """
    Thrown when a loop is detected.
    """
    pass

class InvalidPageNameError(Exception):
    """
    Thrown when an invalid page name is
    passed to self.trace()
    """
    pass

class LinkNotFoundError(Exception):
    """
    Thrown when no appropriate link is found
    after parsing.
    """
    pass

class PhilosophyGame():
    """
    The main PhilosophyGame class.
    """
    url = 'https://en.wikipedia.org/w/api.php'
    headers = { 'User-Agent': 'The Philosophy Game/0.1' }
    def __init__(self, page=None):
        """
        Initialize object with initial page name to start with.

        Args:
            page: the initial page name to start with. (optional,
            defaults to a random page)

        Raises:
            InvalidPageNameError: if page is not a valid mainspace
            page name
        """
        if page is None:
            params = dict(action='query', list='random', rnlimit=1,
                        rnnamespace=0, format='json')
            response = requests.get(self.url, params=params,
                                headers=self.headers)
            self.page = json.loads(response.content)['query']['random'][0]['title']
        else:
            self.page = page

        if not PhilosophyGame.valid_page_name(self.page):
            raise InvalidPageNameError("Invalid page name '{0}'"
                    .format(self.page))
        self.link_count = 0
        self.visited = []

    @staticmethod
    def strip_parentheses(string):
        """
        Remove parentheses from a string, leaving
        parentheses between <tags> in place

        Args:
            string: the string to remove parentheses from
        Returns:
            the processed string after removal of parentheses
        """
        p = a = 0
        result = ''
        for c in string:
            # When outside of parentheses within <tags>
            if p < 1:
                if c == '<':
                    a += 1
                if c == '>':
                    a -= 1

            # When outside of <tags>
            if a < 1:
                if c == '(':
                    p += 1
                if p > 0:
                    result += ' '
                else:
                    result += c
                if c == ')':
                    p -= 1

            # When inside of <tags>
            else:
                result +=c

        return result

    @staticmethod
    def valid_page_name(page):
        """
        Checks for valid mainspace Wikipedia page name
        """
        return (page.find('(disambiguation)') == -1
            and page.find('File:') == -1
            and page.find('File talk') == -1
            and page.find('Wikipedia:') == -1
            and page.find('Wikipedia talk:') == -1
            and page.find('Project:') == -1
            and page.find('Project talk:') == -1
            and page.find('Portal:') == -1
            and page.find('Portal talk:') == -1
            and page.find('Special:') == -1
            and page.find('Help:') == -1
            and page.find('Help talk:') == -1
            and page.find('Template:') == -1
            and page.find('Template talk:') == -1
            and page.find('Talk:') == -1
            and page.find('Category:') == -1
            and page.find('Category talk:') == -1
            and page.find('Main Page') == -1)

    def trace(self, page=None):
        """
        Visit the first non-italicized, not-within-parentheses
            link of page recursively until the page 'Philosophy'
            is reached.

        Args:
            page: The Wikipedia page name to visit
            (optional, defaults to self.page)
        Returns:
            A generator with the page names generated in sequence
            in real time.
        Raises:
            MediaWikiError: if MediaWiki API responds with an error
            requests.exceptions.ConnectionError: if cannot initiate request
            LoopException: if a loop is detected
            InvalidPageNameError: if invalid page name is passed as argument
            LinkNotFoundError: if an appropraite link cannot be found for
            page
        """

        if page is None:
            page = self.page

        yield page
        if page == 'Philosophy':
            return
        if not PhilosophyGame.valid_page_name(page):
            raise InvalidPageNameError("Invalid page name '{0}'"
                    .format(page))
        params = dict(action='parse', page=page, prop='text',
                    section=0, format='json', redirects=1)

        response = requests.get(self.url, params=params, headers=self.headers)
        res_json = json.loads(response.content)

        if 'error' in res_json:
            raise MediaWikiError('MediaWiki error',
                {'code': res_json['error']['code'],
                'info': res_json['error']['info']})

        raw_html = res_json['parse']['text']['*'].encode('utf-8')
        html = lh.fromstring(raw_html)

        # This takes care of most MediaWiki templates,
        # images, red links, hatnotes, italicized text
        # and anything that's strictly not text-only
        for elm in html.cssselect('.reference,span,div,.thumb,'
                    + 'table,a.new,i,#coordinates'):
            elm.drop_tree()

        html = lh.fromstring(PhilosophyGame.strip_parentheses(
                    lh.tostring(html)))
        link_found = False
        for elm, attr, link, pos in html.iterlinks():
            # Because .iterlinks() picks up 'src' and the like too
            if attr != 'href':
                continue
            next_page = link

            # Must be a valid internal wikilink
            if next_page[:len('/wiki/')] != '/wiki/':
                continue

            # Extract the Wikipedia page name
            next_page = next_page[len('/wiki/'):]

            # Skip non-valid names
            if not PhilosophyGame.valid_page_name(next_page):
                continue

            # Links use an underscore ('_')
            # instead of a space (' '), this
            # fixes that
            next_page = next_page.replace('_', ' ')

            # Eliminate named anchor, if any
            pos = next_page.find('#')
            if pos != -1:
                next_page = next_page[:pos]

            # Detect loop
            if next_page in self.visited:
                raise LoopException('Loop detected')

            link_found = True
            self.link_count += 1
            self.visited.append(page)

            # Recursively yield
            for m in self.trace(next_page):
                yield m

            break
        if not link_found:
            raise LinkNotFoundError(('No appropriate link found in page {0}, ' +
                    'probably a disambiguation page').format(page))
