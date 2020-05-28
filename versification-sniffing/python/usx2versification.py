import os
import re
import argparse
import xml.etree.ElementTree as ET
import json
import canons

ap = argparse.ArgumentParser(description='Create Versification File from Directory of USX 3.0 Files')
ap.add_argument('directory')
# TODO: Add
# (1)  base versification (required?) and
# (2) segment markers (defaults to -, a, b, c)
args = ap.parse_args()

books = {}
versification = {}

# Parse each USX file in the directory and put the document root into a dictionary, indexed
# by the book identifier.
#
# Each USX file should contain a book.  Can there be more than one? Each book should have a @code attribute
# that contains a Book Identifier (https://ubsicap.github.io/usfm/identification/books.html).

def parse_books(directory):
	for file in os.listdir(directory):
		if file.endswith(".usx"):
			root = ET.parse(args.directory+file)
			for book in root.iter('book'):
				book_identifier = book.get('code')
				if book_identifier in canons.book_ids and not book_identifier in canons.non_canonical_ids:
					books[book_identifier] = {}
					books[book_identifier]["root"] = root
					books[book_identifier]["file"] = file

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
	for book in canons.book_ids:
		if book in books:
			root = books[book]["root"]
			max_verses = {}
			for verse in root.findall(".//verse[@sid]"):
				sid=verse.attrib["sid"]
				book, cv = sid.split()
				chapter,verse = cv.split(":")
				chapter = int(chapter)
				partial = re.findall(r'\d+[a-z]', verse)
				# watch out for verses like "7-9" or "8,9" or "25a"
				verse = max(map(int, re.findall(r'\d+', verse)))
				if not chapter in max_verses:
					max_verses[chapter] = verse
				elif verse > max_verses[chapter]:
					max_verses[chapter] = verse

#				if partial:
#					id = book + " " + str(chapter) + ":" + re.findall(r'\d+', partial)
#					if not id in versification["partialVerses"]:
#						versification["partialVerses"][id]=[]
#					versification["partialVerses"][id].append(partial)

			if not book in versification["maxVerses"]:
				versification["maxVerses"][book] = []
			for i in sorted(max_verses):
				versification["maxVerses"][book].append(max_verses[i])

def mapped_verses():
	return

parse_books(args.directory)
max_verses()
mapped_verses()
print(json.dumps(versification, indent=4))
