import re
from urlparse import urlsplit, urlunsplit, urljoin

import requests

import errors


# regex
HtmlTitleTagRegex = re.compile(r'<title>(?P<title>.+)</title>', re.IGNORECASE)
HtmlHrefAttrRegex = re.compile( \
			r'<(?P<tag>[a-z]+)[^<]*href="(?P<href>[^ ]+)".*>', re.IGNORECASE)
HtmlSrcAttrRegex = re.compile( \
			r'<(?P<tag>[a-z]+)[^<]*src="(?P<src>[^ ]+)".*>', re.IGNORECASE)


class Page(object):
	'''
	Page of a website.
	'''
	def __init__(self, domain, url, content):
		super(Page, self).__init__()
		
		domain = domain.strip().lower() # just to be safe
		
		self.__url = url
		
		match = HtmlTitleTagRegex.search(content)
		self.__title = match.group('title').strip() if match is not None \
						else 'No title'
		
		self.__assets = []
		for match in HtmlSrcAttrRegex.finditer(content):
			self.__assets.append(match.group('src').strip().lower())
		
		self.__links_to = []
		domain_netloc = urlsplit(domain)[1]
		for match in HtmlHrefAttrRegex.finditer(content):
			href = match.group('href').lower()
			
			_, netloc, path, query, fragment = urlsplit(href)
			# ignore external URLs
			if len(netloc) > 0 and netloc != domain_netloc:
				continue
			
			href = urlunsplit(('', '', '/%s' % path.strip('/'), \
							query, fragment))
			
			# ignore links to self
			if href == self.__url:
				continue
			
			if match.group('tag').lower() == 'a':
				# TODO: need to check resource type, e.g. pdf, zip, webpage
				self.__links_to.append(href)
			else:
				self.__assets.append(href)
		
		self.__assets = frozenset(self.__assets)
		self.__links_to = frozenset(self.__links_to)
	
	@property
	def title(self):
		return self.__title
	
	@property
	def url(self):
		return self.__url
	
	@property
	def assets(self):
		return tuple(self.__assets)
	
	@property
	def links_to(self):
		return tuple(self.__links_to)


class Sitemap(object):
	'''
	Website's sitemap.
	'''
	def __init__(self, domain):
		super(Sitemap, self).__init__()
		
		arr = urlsplit(domain)
		if len(arr[0]) == 0:
			raise TypeError('Domain name must include "http(s)://".')
		self.__domain = '%s://%s' % (arr[0], arr[1])
		self.__pages = {} # {url: Page}
		
		self.__crawl()
	
	def __str__(self):
		s = ['Sitemap for %s:\n' % self.domain]
		
		for page in self.pages.itervalues():
			s.append('\t-> %s (%s)\n' % (page.title, page.url))
			
			s.append('\t   Static assets:\n')
			assets = page.assets
			if len(assets) > 0:
				for asset in page.assets:
					s.append('\t\t%s\n' % asset)
			else:
				s.append('\t\tNone.\n')
			
			s.append('\t   Links:\n')
			links = page.links_to
			if len(links) > 0:
				for link in links:
					s.append('\t\t%s\n' % link)
			else:
				s.append('\t\tNone.\n')
		
		return ''.join(s)
	
	@property
	def domain(self):
		return self.__domain
	
	@property
	def pages(self):
		return self.__pages
	
	def __crawl(self):
		urls_to_check = ['/']
		while True:
			try:
				url = urls_to_check.pop()
				print 'Checking %s' % url
			except:
				break
			
			response = requests.get( \
							urljoin(self.domain, url, allow_fragments=True))
			try:
				response.raise_for_status()
				assert response.status_code == 200
				assert 'html' in response.headers.get('content-type') 
			except:
				continue
			
			html = response.text
			
			try:			
				page = self.__create_page_for(url, html)
				
				for link_to in page.links_to:
					try:
						assert not self.__has_crawled_url(link_to)
						urls_to_check.append(link_to)
					except AssertionError:
						pass
			except errors.PageExistsError:
				pass
	
	def __create_page_for(self, url, content):
		if self.__has_crawled_url(url):
			raise errors.PageExistsError()
		
		page = Page(self.domain, url, content)
		self.pages[url] = page
		
		return page
	
	def __has_crawled_url(self, url):
		return url in self.pages
