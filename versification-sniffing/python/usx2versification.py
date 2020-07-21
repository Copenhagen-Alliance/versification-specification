import os
import re
import argparse
from lxml import etree
from string import Template
import json
import canons

from inspect import currentframe
import logging
logging.basicConfig(filename='debug.log',level=logging.DEBUG, format='%(asctime)s\t%(message)s')

ap = argparse.ArgumentParser(description='Create Versification File from USX Files - See https://github.com/Copenhagen-Alliance/versification-specification/')
ap.add_argument('-n', '--name', help="Short name of the text, e.g. 'NRSVUK' or 'ESV'", required=True)
ap.add_argument('-usx', help="directory containing USX 3.0 files", default="./usx/")
ap.add_argument('-b', '--base', help="base versification, e.g. 'lxx'")
ap.add_argument('-m', '--mappings', help="directory containing versification mappings.", default='./mappings/')
ap.add_argument('-r', '--rules', help="merged rules file for mapping verses", default='./rules/merged_rules.json')
args = ap.parse_args()

logging.info("------------------------------------------")
logging.info("Directory: " + args.name)

books = {}
versification = {}

# XPath does not seem to index attributes in lxml and Etree, so let's create an index to use instead.
verse_index = {}

if args.base:
        try:
                base_versification_file = args.mappings + args.base + '.json'
                fp = open(base_versification_file, "r")
                base = json.load(fp)
        except Exception as exc:
                print(exc)
                base = None

# Helper functions

def get_linenumber():
    cf = currentframe()
    return cf.f_back.f_lineno

def create_sid(book, chapter, verse):
        sid_template = Template('$book $chapter:$verse')
        return sid_template.substitute(book=book, chapter=chapter, verse=verse)


def get_rest_of_verse(start_verse):
        """
        OK, you got to the end of the paragraph and didn't find the ending verse.
        A verse element is always the child of a para element, so keep looking at para
        elements until you find the end verse.
        """

        para = start_verse.getparent().getnext()
        if para is None:
                return ""

        s = ""
        while para is not None:
                if para.text is not None:
                    s = s + para.text
                for child in para:
                        if child.tag == "verse":
                                return s
                        if child.text:
                                s = s + child.text
                        if child.tail:
                                s = s + child.tail
                para = para.getnext()

def verse_to_string(book, chapter, v):
        verse = find_verse(book, chapter, v)
        if verse is None:
                return ""
        s = verse.tail
        e = verse
        if s is not None:
            while True:
                    e = e.getnext()
                    if e is None:
                            s = s + get_rest_of_verse(verse)
                            logging.warning("Verse " + create_sid(book, chapter, v) + " spans paragraph boundaries - don't trust this result yet!")
                            break
                    if e.tag == "verse":
                            break
                    if e.text:
                            s = s + e.text
                    if e.tail:
                            s = s + e.tail
            return " ".join(s.split())
        else:
            return None

def parse_books(directory):
        """
        Parse each USX file in the directory and put the document root into a dictionary, indexed
        by the book identifier.

        Each USX file should contain a book.  Can there be more than one? Each book should have a @code attribute
        that contains a Book Identifier (https://ubsicap.github.io/usfm/identification/books.html).
        """

        for file in sorted(os.listdir(directory)):
                if file.endswith(".usx"):
                        root = etree.parse(directory+file)
                        for book in root.iter('book'):
                                book_identifier = book.get('code')
                                if book_identifier in canons.book_ids and not book_identifier in canons.non_canonical_ids:
                                        books[book_identifier] = {}
                                        books[book_identifier]["root"] = root
                                        books[book_identifier]["file"] = file
                        for verse in root.iter('verse'):
                                attribs = verse.attrib
                                sid = attribs["sid"] if "sid" in attribs else None
                                eid = attribs["eid"] if "eid" in attribs else None
                                if sid is not None:
                                        verse_index[sid] = {}
                                        verse_index[sid]["start"] = verse
                                elif eid is not None:
                                        if not eid in verse_index:
                                                verse_index[eid] = {}
                                        verse_index[eid]["end"] = verse
                        logging.info("Book: " + book_identifier + " (" + file + ")")

def find_verse(book, chapter, verse):
        sid=create_sid(book, chapter, verse)
        return (verse_index[sid]["start"] if sid in verse_index else None)

def partial(book, chapter, verse):
        """
        Partial Verses (segments)

        Let's be descriptive, not prescriptive.
        After splitting on "-", ",", anything non-numeric is a segment.
        If there's a segment, check to see if the bare form is used too.
        """

        verses = re.split(r'[\-,\,]',verse)
        for pv in verses:
                segment = re.findall(r'\D+',pv)
                if segment:
                        numeric = re.findall(r'\d+',pv)[0]
                        id = create_sid(book, chapter, numeric)
                        if not id in versification["partialVerses"]:
                                versification["partialVerses"][id]=[]
                                if find_verse(book, chapter,numeric) is not None:
                                        versification["partialVerses"][id].append('-')
                        if segment:
                                        versification["partialVerses"][id].append(segment[0])


def max_verses():
        """
        Not all dictionaries will maintain order, but we sort by canonical book
        assuming that the order is stable.  If not, *shrug*, it's still usable.

        According to the spec:

        In USX 3.0 a <verse/> milestone is required at the start and
        at the end of the verse text, with corresponding sid and eid
        attributes. In previous versions of USX, only a <verse/> start
        milestone was required.

        Let's assume we can rely at least on verse elements with sids, and
        parse those.

        """
        versification["maxVerses"] = {}
        versification["partialVerses"] = {}
        versification["verseMappings"] = {}
        versification["excludedVerses"] = {}
        versification["unexcludedVerses"] = {}
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

        if not book in versification["maxVerses"]:
                logging.warning(book + " not found!")
                return False
        elif chapter > len(versification["maxVerses"][book]):
                logging.warning(str(chapter) + " not found in " + book)
                return

        logging.info(create_sid(book,chapter,verse) + " => " + str(versification["maxVerses"][book][chapter-1]))

        if verse == versification["maxVerses"][book][chapter-1]:
                logging.info("Last in chapter")
                return True
        else:
                logging.info("Not last in chapter")
                return False


def has_more_words(ref, comparison):
        ref_string = verse_to_string(ref["book"], ref["chapter"], ref["verse"])
        comparison_string = verse_to_string(comparison["book"], comparison["chapter"], comparison["verse"])
        logging.info("has_more_words()")
        logging.info(ref)
        logging.info(comparison)
        logging.info(ref_string)
        logging.info(comparison_string)
        logging.info(len(ref_string) > len(comparison_string))
        ref_factor = ref["factor"] if "factor" in ref else 1
        comparison_factor = comparison["factor"] if "factor" in comparison else 1
        return len(ref_string)*ref_factor > len(comparison_string)*comparison_factor

def has_fewer_words(ref, comparison):
        has_more_words(comparison, ref)

def do_test(parsed_test) -> bool:
        logging.info(parsed_test)

        left = parsed_test['left']['parsed']
        right = parsed_test['right']['parsed']
        op = parsed_test['op']


        if "keyword" in right:
                keyword = right["keyword"]
        else:
                keyword = None

        logging.info(left)
        logging.info(op)
        logging.info(right)

        if op == "=" and keyword == "Last":
                if not is_last_in_chapter(left["book"], left["chapter"], left["verse"]):
                        return False
        elif op == "=" and keyword == "Exist":
                if find_verse(left["book"], left["chapter"], left["verse"]) is None:
                        return False
        elif op == "=" and keyword == "NotExist":
                if find_verse(left["book"], left["chapter"], left["verse"]) is not None:
                        return False

        elif op == "<" and 'chapter' in right:
                if has_more_words(left, right):
                        return False
        elif op == ">"  and 'chapter' in right:
                if has_fewer_words(left, right):
                        return False
        else:
                logging.info("Error in test!  (not implemented?)")
                return False

        return True


bcv_pattern = r'((\w+)\.(\d+)\:(\d+)\.?(\d+)?\*?(\d+)?)'
factor_pattern = r'\*?(\d+)'

def parse_ref(ref):
        """
        TODO: Add words
        TODO: Add factor_pattern
        """
        m = re.search(bcv_pattern, ref)
        if m is None:
                return { 'keyword': ref.strip() }
        else:
                d = { 'book': m[2].upper(), 'chapter': int(m[3]), 'verse': int(m[4]) }
                if m[5] is not None:
                        d['words'] = int(m[5])
                if m[6] is not None:
                        d['factor'] = int(m[6])
                if d['book'] not in canons.book_ids:
                        logging.info('ERROR: '+d['book'] + " is not a valid USFM book name")

                return d

def parse_test(test) -> dict:
        d = {}

        t = re.compile('([<=>])')
        triple = t.split(test)
        if len(triple) != 3:
                logging.info("ERROR: Does not parse: " +test)
        else:
                d['left'] = {}
                d['left']['text'] = triple[0]
                d['left']['parsed'] = parse_ref(triple[0])
                d['op'] = triple[1]
                d['right'] = {}
                d['right']['text'] = triple[2]
                d['right']['parsed'] = parse_ref(triple[2])
                return d


def map_from(rule) -> int:
        """
        Which column are we mapping from?

        c - the column that passes all of the tests
        None - no column passed all of the tests
        """
        tests = rule["tests"]
        for c in range(0, len(tests)):
                for test in tests[c]:
                        pt = parse_test(test)
                        if do_test(pt) is False:
                                continue

                return c

        logging.info("map_from(): no set of tests matches!")
        return None


def map_to(rule:dict) -> int:
        """
        Which column should we map to?

        "Hebrew" - if there is a Hebrew source, always map to that.
        "Greek" - if there is a straightforward Greek source, but not a Hebrew one,
                  use the Greek source
        None - couldn't find a Hebrew or Greek source. Nothing to map onto.
        """
        to = None
        name = rule["name"]
        columns = rule["columns"]
        for c in range(0, len(columns)):
                if "Hebrew" in columns[c]:
                        return c
                elif "Greek" in columns[c]:
                        to = c
                        continue

        return to

def create_mappings(rule:dict, from_column:int, to_column:int) -> None:
        logging.info("Map from column " + str(from_column) + " to column " + str(to_column))
        for r in rule["ranges"]:
                for k in r.keys():
                        frum = r[k][from_column].upper().replace("."," ", 1)
                        to = r[k][to_column].upper().replace("."," ", 1)
                        logging.info(frum + " : " + to)
                        if frum != to and to != "NOVERSE":
                                versification["verseMappings"][frum] = to

def mapped_verses():
        """
        Map from whatever this text is onto:
        (1) Hebrew, if present,
        (2) Greek, if there is no Hebrew

        TODO: DAG, ESG, etc. are not separate books in this scheme.  Requires
        careful handling.
        https://ubsicap.github.io/usx/vocabularies.html#usx-vocab-bookcode
        """
        with open(args.rules) as r:
                rules = json.load(r)
                for rule in rules:
                        logging.info("-------------------------")
                        logging.info("Rule: " + rule["name"])
                        from_column = map_from(rule)
                        if from_column is None:
                                continue
                        else:
                                to_column = map_to(rule)
                                if from_column != to_column:
                                        create_mappings(rule, from_column, to_column)

                                # TODO - check to see if base mapping exists


versification["shortname"] = args.name
if args.base:
	versification['basedOn'] = args.base
	logging.info('Base versification: '+ args.base)

parse_books(args.usx+args.name+"/")
max_verses()
mapped_verses()

"""
Sort verse segments - alphabetical order, not order of first encounter.
"""
for key in versification["partialVerses"].keys():
        versification["partialVerses"][key].sort()

print(json.dumps(versification, indent=4, ensure_ascii=False))
