from collections import deque, OrderedDict
from copy import copy
import re
from urlparse import urlsplit, urlunsplit, urljoin

import requests
import logging

import errors


# regex
HtmlTitleTagRegex = re.compile(r'<title>(?P<title>.+)</title>', \
                            re.IGNORECASE | re.DOTALL)
HtmlHrefAttrRegex = re.compile( \
            r'<(?P<tag>[a-z]+)(?: rel=[\'"](?P<rel>[^\'"]+)[\'"])?[^<]* href=[\'"](?P<href>[^\'"]+)[\'"][^>]*>(?:<span [^>]*>(?:</span>)?)*(?P<text>[^<]*)', re.IGNORECASE)
HtmlSrcAttrRegex = re.compile( \
            r'<(?P<tag>[a-z]+)[^<]* src=[\'"](?P<src>[^\'"]+)[\'"][^>]*>', re.IGNORECASE)
HtmlActionAttrRegex = re.compile( \
            r'<(?P<tag>[a-z]+)[^<]* (?:form)?action=[\'"](?P<action>[^\'"]+)[\'"][^>]*>', re.IGNORECASE)


class Page(object):
    '''
    Page of a website.
    '''
    def __init__(self, domain, url, content):
        '''
        @param domain: (str) base domain.
        @param url: (str) page's url without the domain.
        @param content: (str) HTML content of the page.
        '''
        super(Page, self).__init__()
        
        domain = domain.strip().lower() # just to be safe
        
        self.__url = url
        
        # find the page's title
        match = HtmlTitleTagRegex.search(content)
        self.__title = match.group('title').strip() if match is not None \
                        else 'No title'
        
        # find assets
        self.__assets = []
        for match in HtmlSrcAttrRegex.finditer(content):
            self.__assets.append(match.group('src').strip())
        
        # find form actions
        self.__actions = []
        for match in HtmlActionAttrRegex.finditer(content):
            self.__actions.append(match.group('action').strip())

        # find links
        self.__internal_links = []
        self.__external_links = []
        self.__other_links = []
        domain_netloc = urlsplit(domain)[1]
        for match in HtmlHrefAttrRegex.finditer(content):
            href = match.group('href')
            text = match.group('text')

            # filter out in-page references
            if len(href) == 0 or href[0] == '#':
                continue

            scheme, netloc, path, _, _ = urlsplit(href)
            # check for external URLs
            if len(netloc) > 0 and netloc != domain_netloc:
                href = urlunsplit((scheme, netloc, path, '', ''))
                if match.group('tag').lower() == 'a':
                    self.__external_links.append((href, text))
                elif match.group('tag').lower() == 'link' and match.group('rel').lower() == 'stylesheet':
                    self.__assets.append(href)
                else:
                    self.__other_links.append((href, match.group('rel')))
                continue
            
            # filter out useless URLs
            if scheme in ('mailto', 'tel', 'javascript') or len(path) == 0:
                continue

            if path[0] != '/':
                logging.warn("Unsupported relative path (%s) at %s", path, url)

            # create absolute path ignoring query & fragment parameters
            href = urlunsplit(('', '', '/%s' % path.lstrip('/'), '', ''))
            
            # ignore links to self
            if href == self.__url:
                continue
            
            if match.group('tag').lower() == 'a':
                self.__internal_links.append((href, text))
            elif match.group('tag').lower() == 'link' and match.group('rel').lower() == 'stylesheet':
                self.__assets.append(href)
            else:
                self.__other_links.append((href, match.group('rel')))

        # remove duplicates & make read-only
        self.__assets = tuple(OrderedDict.fromkeys(self.__assets).keys())
        self.__actions = tuple(OrderedDict.fromkeys(self.__actions).keys())
        self.__internal_links = tuple(OrderedDict.fromkeys(self.__internal_links).keys())
        self.__external_links = tuple(OrderedDict.fromkeys(self.__external_links).keys())
        self.__other_links = tuple(OrderedDict.fromkeys(self.__other_links).keys())

    @property
    def title(self):
        '''
        Get the page's title.
        
        @return: (str).
        '''
        return self.__title
    
    @property
    def url(self):
        '''
        Get the page's URL. Does not include the domain name.
        
        @return: (str).
        '''
        return self.__url
    
    @property
    def assets(self):
        '''
        Get the page's static assets.
        
        @return: (tuple).
        '''
        return copy(self.__assets)
    
    @property
    def actions(self):
        '''
        Get the page's form actions.

        @return: (tuple).
        '''
        return copy(self.__actions)

    @property
    def links(self):
        '''
        Get the page's links (internal & external).
        
        @return: (tuple).
        '''
        return copy(self.__internal_links + self.__external_links)
    
    @property
    def internal_links(self):
        '''
        Get the page's internal links.
        
        @return: (tuple).
        '''
        return copy(self.__internal_links)
    
    @property
    def external_links(self):
        '''
        Get the page's external links.
        
        @return: (tuple).
        '''
        return copy(self.__external_links)

    @property
    def other_links(self):
        '''
        Get the page's other (non-<a>) links.

        @return: (tuple).
        '''
        return copy(self.__other_links)


class Sitemap(object):
    '''
    Website's sitemap.
    '''
    def __init__(self, domain):
        '''
        @param domain: (str).
        '''
        super(Sitemap, self).__init__()
        
        arr = urlsplit(domain)
        if len(arr[0]) == 0:
            raise TypeError('Domain name must include "http(s)://".')
        self.__domain = '%s://%s' % (arr[0], arr[1])
        self.__pages = OrderedDict() # {url: Page}
        
        self.__crawl()
    
    def __str__(self):
        '''
        To string method.
        
        @return: (str).
        '''
        s = ['Sitemap for %s:\n' % self.__domain.encode('utf-8')]
        
        for page in self.__pages.itervalues():
            s.append('\t-> %s (%s)\n' % (page.title.encode('utf-8'), page.url.encode('utf-8')))
            
            s.append('\t   Static assets:\n')
            assets = page.assets
            if len(assets) > 0:
                for asset in assets:
                    s.append('\t\t%s\n' % asset.encode('utf-8'))
            else:
                s.append('\t\tNone.\n')

            s.append('\t   Links:\n')
            links = page.links
            if len(links) > 0:
                for (link, text) in sorted(links):
                    s.append('\t\t%s - %s\n' % (link.encode('utf-8'), text.encode('utf-8')))
            else:
                s.append('\t\tNone.\n')

            actions = page.actions
            if len(actions) > 0:
                s.append('\t   Form actions:\n')
                for action in actions:
                    s.append('\t\t%s\n' % action.encode('utf-8'))

            other_links = page.other_links
            if len(other_links) > 0:
                s.append('\t   Other links:\n')
                for (link,rel) in other_links:
                    if rel is None:
                        s.append('\t\t%s\n' % link.encode('utf-8'))
                    else:
                        s.append('\t\t[rel=%s] %s\n' % (rel.encode('utf-8'), link.encode('utf-8')))

        return ''.join(s)
    
    def __crawl(self):
        '''
        Crawl the given domain and create the sitemap.
        '''
        urls_to_check = deque(['/'])
        while True:
            try:
                url = urls_to_check.popleft()
            except:
                break # no more URLs to check
            
            response = requests.get( \
                        urljoin(self.__domain, url, allow_fragments=False))
            try:
                response.raise_for_status()
                assert response.status_code == 200
                if 'video' in response.headers.get('content-type'):
                    continue
                # only crawl HTML pages
                assert 'html' in response.headers.get('content-type') 
            except:
                logging.exception("Error getting %s", url)
                continue
            
            try:
                page = self.__create_page_for(url, response.text)
                
                for (link, text) in page.internal_links:
                    try:
                        # ignore URLs already crawled or already in queue
                        assert link not in self.__pages \
                            and link not in urls_to_check
                        urls_to_check.append(link)
                    except AssertionError:
                        pass
            except errors.PageExistsError:
                pass
    
    def __create_page_for(self, url, content):
        '''
        Create a page for an URL.
        
        @param url: (str) page's URL.
        @param content: (str) page's HTML content.
        @return: (Page).
        @raise PageExistsError: if a page already exists for the same URL.
        '''
        if url in self.__pages:
            raise errors.PageExistsError()
        
        page = Page(self.__domain, url, content)
        self.__pages[url] = page
        
        return page
