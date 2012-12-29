from collections import deque
from copy import copy
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
		
		self.__internal_links = []
		self.__external_links = []
		domain_netloc = urlsplit(domain)[1]
		for match in HtmlHrefAttrRegex.finditer(content):
			href = match.group('href').lower()
			
			scheme, netloc, path, _, _ = urlsplit(href)
			# external URLs
			if len(netloc) > 0 and netloc != domain_netloc:
				self.__external_links.append( \
								urlunsplit((scheme, netloc, path, '', '')))
				continue
			
			# filter out useless URLs
			if scheme in ('mailto', 'tel', 'javascript'):
				continue
			
			href = urlunsplit(('', '', '/%s' % path.strip('/'), '', ''))
			
			# ignore links to self
			if href == self.__url:
				continue
			
			if match.group('tag').lower() == 'a':
				# TODO: need to check resource type, e.g. pdf, zip, webpage
				self.__internal_links.append(href)
			else:
				self.__assets.append(href)
		
		self.__assets = tuple(set(self.__assets))
		self.__internal_links = tuple(set(self.__internal_links))
		self.__external_links = tuple(set(self.__external_links))
	
	@property
	def title(self):
		return self.__title
	
	@property
	def url(self):
		return self.__url
	
	@property
	def assets(self):
		return copy(self.__assets)
	
	@property
	def links(self):
		return copy(self.__internal_links + self.__external_links)
	
	@property
	def internal_links(self):
		return copy(self.__internal_links)
	
	@property
	def external_links(self):
		return copy(self.__external_links)


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
		s = ['Sitemap for %s:\n' % self.__domain]
		
		for page in self.__pages.itervalues():
			s.append('\t-> %s (%s)\n' % (page.title, page.url))
			
			s.append('\t   Static assets:\n')
			assets = page.assets
			if len(assets) > 0:
				for asset in page.assets:
					s.append('\t\t%s\n' % asset)
			else:
				s.append('\t\tNone.\n')
			
			s.append('\t   Links:\n')
			links = page.links
			if len(links) > 0:
				for link in links:
					s.append('\t\t%s\n' % link)
			else:
				s.append('\t\tNone.\n')
		
		return ''.join(s)
	
	def __crawl(self):
		urls_to_check = deque(['/'])
		while True:
			try:
				url = urls_to_check.popleft()
			except:
				break
			
			response = requests.get( \
						urljoin(self.__domain, url, allow_fragments=False))
			try:
				response.raise_for_status()
				assert response.status_code == 200
				assert 'html' in response.headers.get('content-type') 
			except:
				continue
			
			try:			
				page = self.__create_page_for(url, response.text)
				
				for link in page.internal_links:
					try:
						assert link not in self.__pages \
							and link not in urls_to_check
						urls_to_check.append(link)
					except AssertionError:
						pass
			except errors.PageExistsError:
				pass
	
	def __create_page_for(self, url, content):
		if url in self.__pages:
			raise errors.PageExistsError()
		
		page = Page(self.__domain, url, content)
		self.__pages[url] = page
		
		return page
