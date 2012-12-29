'''
Crawl a web page and output its sitemap as:
1. list of all pages with each page's static dependencies.
2. list of pages that the current page links to.

Limit crawl to a single domain.
'''

from models import Sitemap


if __name__ == '__main__':
#	domain = \
#		raw_input('Enter the base URL you want to crawl (include "http://"): ')
	domain = 'http://www.andreipetre.com/'
	
	print 'Crawling %s ...' % domain
	sitemap = Sitemap(domain)
	print 'Done.'
	print sitemap
