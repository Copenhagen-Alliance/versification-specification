import os
import re
import argparse
import xml.etree.ElementTree as ET
from string import Template
import json
import canons

# TODO: Enable unicode for output.  ñ.

ap = argparse.ArgumentParser(description='Create Versification File from USX Files - See https://github.com/Copenhagen-Alliance/versification-specification/')
ap.add_argument('-usx', help="directory containing USX 3.0 files.  required.", required=True)
ap.add_argument('-b', '--base', help="base versification, e.g. 'lxx'")
ap.add_argument('-m', '--mappings', help="directory containing versification mappings.", default='./mappings/')
ap.add_argument('-r', '--rules', help="rules file for mapping verses", default='./rules/rules.json')
args = ap.parse_args()

books = {}
versification = {}

if args.base:
	try:
		base_versification_file = args.mappings + args.base + '.json'
		base = open(base_versification_file,'r')
	except:
		print("Warning: Could not find "+base_versification_file)
		base = None

# Parse each USX file in the directory and put the document root into a dictionary, indexed
# by the book identifier.
#
# Each USX file should contain a book.  Can there be more than one? Each book should have a @code attribute
# that contains a Book Identifier (https://ubsicap.github.io/usfm/identification/books.html).

def parse_books(directory):
	for file in os.listdir(directory):
		if file.endswith(".usx"):
			root = ET.parse(directory+file)
			for book in root.iter('book'):
				book_identifier = book.get('code')
				if book_identifier in canons.book_ids and not book_identifier in canons.non_canonical_ids:
					books[book_identifier] = {}
					books[book_identifier]["root"] = root
					books[book_identifier]["file"] = file

# Partial Verses (segments)
#
# Let's be descriptive, not prescriptive.
# After splitting on "-", ",", anything non-numeric is a segment.
# If there's a segment, check to see if the bare form is used too.

def verse_exists(book, chapter, verse):
	t = Template(".//verse[@sid='$book $chapter:$verse']")
	query = t.substitute(book=book, chapter=chapter, verse=verse)
	return books[book]["root"].findall(query)


def partial(book, chapter, verse):
	verses = re.split(r'[\-,\,]',verse)
	for pv in verses:
		segment = re.findall(r'\D+',pv)
		if segment:
			numeric = re.findall(r'\d+',pv)[0]
			t = Template('$book $chapter:$verse')
			id = t.substitute(book=book, chapter=chapter, verse=numeric)
			if not id in versification["partialVerses"]:
				versification["partialVerses"][id]=[]
				if verse_exists(book, chapter, numeric):
					versification["partialVerses"][id].append('-')
			if segment:
					versification["partialVerses"][id].append(segment[0])


# Not all dictionaries will maintain order, but we sort by canonical book
# assuming that the order is stable.  If not, *shrug*, it's still usable.
#
# According to the spec:
#
#	 In USX 3.0 a <verse/> milestone is required at the start and
#    at the end of the verse text, with corresponding sid and eid
#    attributes. In previous versions of USX, only a <verse/> start
#    milestone was required.
#
# Let's assume we can rely at least on verse elements with sids, and
# parse those.

def max_verses():
	versification["maxVerses"] = {}
	versification["partialVerses"] = {}
	versification["excludedVerses"] = {}
	versification["addedVerses"] = {}
	for book in canons.book_ids:
		if book in books:
			root = books[book]["root"]
			max_verses = {}
			for verse in root.findall(".//verse[@sid]"):
				sid=verse.attrib["sid"]
				book, cv = sid.split()
				chapter,verse = cv.split(":")
				chapter = int(chapter)
				# see if there are partial verses
				partial(book, chapter, verse)
				# watch out for verses like "7-9" or "8,9" or "25a"
				verse = max(map(int, re.findall(r'\d+', verse)))
				if not chapter in max_verses:
					max_verses[chapter] = verse
				elif verse > max_verses[chapter]:
					max_verses[chapter] = verse

			if not book in versification["maxVerses"]:
				versification["maxVerses"][book] = []
			for i in sorted(max_verses):
				versification["maxVerses"][book].append(max_verses[i])

def mapped_verses():
	return

if args.base:
	versification['basedOn'] = args.base

parse_books(args.usx)
max_verses()
mapped_verses()
print(json.dumps(versification, indent=4))
