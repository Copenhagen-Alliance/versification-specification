import os
import re
import argparse
import xml.etree.ElementTree as ET
from string import Template
import json
import canons

import logging
logging.basicConfig(filename='debug.log',level=logging.DEBUG, format='%(asctime)s\t%(message)s')

ap = argparse.ArgumentParser(description='Create Versification File from USX Files - See https://github.com/Copenhagen-Alliance/versification-specification/')
ap.add_argument('-n', '--name', help="Short name of the text, e.g. 'NRSVUK' or 'ESV'", required=True)
ap.add_argument('-usx', help="directory containing USX 3.0 files", default="./usx/")
ap.add_argument('-b', '--base', help="base versification, e.g. 'lxx'")
ap.add_argument('-m', '--mappings', help="directory containing versification mappings.", default='./mappings/')
ap.add_argument('-r', '--rules', help="rules file for mapping verses", default='./rules/rules.json')
args = ap.parse_args()

logging.info("------------------------------------------")
logging.info(args.name)

books = {}
versification = {}

if args.base:
	try:
		base_versification_file = args.mappings + args.base + '.json'
		fp = open(base_versification_file, "r")
		base = json.load(fp)
	except Exception as exc:
		print(exc)
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

# TODO: Test assumption that tests are combined with an implicit AND
# TODO: See if I can reconstruct nrsv.json mappings with NRSV and no base
# TODO: See if I can create nrsv.json mappings with NRSV and eng.json as base

def is_last_in_chapter(book, chapter, verse):
	logging.info("is_last_in_chapter()")

	if not book in books:
		return False

	t = Template('$book $chapter:$verse')
	this_verse = t.substitute(book=book, chapter=chapter, verse=verse)
	next_verse = t.substitute(book=book, chapter=chapter, verse=int(verse)+1)
	logging.info("this, next = " + this_verse + "\t" + next_verse)

	root = books[book]["root"]
	this_found = root.findall(".//verse[@sid='"+this_verse+"']")
	next_found = root.findall(".//verse[@sid='"+next_verse+"']")
	if this_found and not next_found:
			logging.info("Last in chapter")
			return True
	else:
			logging.info("Not last in chapter")
			return False


def has_more_words():
	pass

def has_fewer_words():
	pass

def mappings(rule):
	pass

# Go through the tests.  If they all evaluate to true, execute the rule.
# If any one evaluates to false or is not yet implemented, return None.
# Else, return a dict with mappings for the rule.

def do_rule(rule):
	logging.info(rule)
	mappings = {}
	for test in rule["tests"]:
		comparator = test["comparator"]
		compare_type = test["compare_type"]
		if comparator=="EqualTo" and compare_type == "Last":
			base_reference = test["base_reference"]
			if is_last_in_chapter(base_reference["book"], chapter=base_reference["chapter"], verse=base_reference["verse"]):
				continue
			else:
				return None
		else:
			logging.info("Not implemented: " + comparator +"\t" + compare_type)
			return None

def mapped_verses():
	actions = []
	with open(args.rules) as r:
		rules = json.load(r)
		for rule in rules["rules"]:
			mapping = {}
			action = rule["action"]
			if not action in actions:
				actions.append(action)

			if rule["action"] == "Keep verse":
				# Just keep it.  Do nothing.
				continue
			elif rule["action"] == "Merged with":
				mapping = do_rule(rule)
				continue
			elif rule["action"] == "Renumber verse":
				# Also used for splitting or creating subverses
				mapping = do_rule(rule)
				continue
			elif rule["action"] == "Empty verse":
				# = Excluded verse.
				continue
			else:
				logging.warning("!!! Unexpected action in rule: " + rule["action"]+ " !!!")

		logging.info("Actions found in " + args.rules)
		for action in actions:
			logging.info("\t"+action)

versification["shortname"] = args.name
if args.base:
	versification['basedOn'] = args.base
	logging.info('Base versification: '+ args.base)

parse_books(args.usx+args.name+"/")
max_verses()
mapped_verses()
print(json.dumps(versification, indent=4, ensure_ascii=False))
