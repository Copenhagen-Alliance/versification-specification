import os
import re
import argparse
from lxml import etree
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

# Helper functions

def create_sid(book, chapter, verse):
	sid_template = Template('$book $chapter:$verse')
	return sid_template.substitute(book=book, chapter=chapter, verse=verse)

# start_miletone is an element like <verse sid="Gen 1:1"/>
# TODO: Make this work when a verse spans paragraph or other elements.

def verse_to_string(book, chapter, v):
	verse = find_verse(book, chapter, v)[0]
	if verse is None:
		return ""
	s = verse.tail
	e = verse
	while True:
		e = e.getnext()
		if e is None:
			break
		if e.tag == "verse":
			break
		if e.text:
			s = s + e.text
		if e.tail:
			s = s + e.tail
	return " ".join(s.split())

# Parse each USX file in the directory and put the document root into a dictionary, indexed
# by the book identifier.
#
# Each USX file should contain a book.  Can there be more than one? Each book should have a @code attribute
# that contains a Book Identifier (https://ubsicap.github.io/usfm/identification/books.html).

def parse_books(directory):
	for file in os.listdir(directory):
		if file.endswith(".usx"):
			root = etree.parse(directory+file)
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

def find_verse(book, chapter, verse):
	t = Template(".//verse[@sid='$sid']")
	query = t.substitute(sid=create_sid(book, chapter, verse))
	logging.info(query)
	return books[book]["root"].findall(query)

def partial(book, chapter, verse):
	verses = re.split(r'[\-,\,]',verse)
	for pv in verses:
		segment = re.findall(r'\D+',pv)
		if segment:
			numeric = re.findall(r'\d+',pv)[0]
			id = create_sid(book, chapter, numeric)
			if not id in versification["partialVerses"]:
				versification["partialVerses"][id]=[]
				if find_verse(book, chapter, numeric):
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


def is_last_in_chapter(book, chapter, verse):
	logging.info("is_last_in_chapter()")

	if not book in books:
		return False

	this_verse = find_verse(book, chapter, verse)
	next_verse = find_verse(book, chapter, int(verse)+1)
	logging.info("this, next: " + create_sid(book,chapter,verse) + '\t' + create_sid(book,chapter,int(verse)+1))
	logging.info(this_verse)
	logging.info(next_verse)

	if this_verse and not next_verse:
			logging.info("Last in chapter")
			return True
	else:
			logging.info("Not last in chapter")
			return False


def has_more_words(ref, comparison):
	ref_string = verse_to_string(ref["book"], ref["chapter"], ref["verse"])
	comparison_string = verse_to_string(comparison["book"], comparison["chapter"], comparison["verse"])
	logging.info("has_more_words()")
	logging.info(ref_string)
	logging.info(comparison_string)
	logging.info(len(ref_string) > len(comparison_string))
	return len(ref_string) > len(comparison_string)

def has_fewer_words(ref, comparison):
	has_more_words(comparison, ref)

def mappings(rule):
	pass

# Go through the tests.  If they all evaluate to true, execute the rule.
# If any one evaluates to false or is not yet implemented, return None.
# Else, return a dict with mappings for the rule.

def create_mapping(rule):
	source = rule["source_reference"]
	source_sid = create_sid(source["book"], source["chapter"], source["verse"])
	standard = rule["standard_reference"]
	standard_sid = create_sid(standard["book"], standard["chapter"], standard["verse"])

	logging.info("create_mapping()")
	logging.info({ source_sid : standard_sid })
	return { source_sid : standard_sid }

def do_rule(rule):
	logging.info(rule)
	mappings = {}
	for test in rule["tests"]:
		comparator = test["comparator"]
		compare_type = test["compare_type"]
		logging.info(comparator + compare_type)

		ref = test["base_reference"]
		compare = test["compare_reference"]

		if comparator=="EqualTo" and compare_type == "Last":
			if not is_last_in_chapter(ref["book"], chapter=ref["chapter"], verse=ref["verse"]):
				return None
		elif comparator=="GreaterThan" and compare_type == "Reference":
			if has_fewer_words(ref, compare):
				return None
		else:
			logging.info("Not implemented: " + comparator +"\t" + compare_type)
			return None

	return create_mapping(rule)


def mapped_verses():
	actions = []
	mapping = {}
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

		if mapping:
			logging.info("Mapping:")
			logging.info(mapping)

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
