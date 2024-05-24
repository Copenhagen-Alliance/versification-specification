'''use mmethods in usx2versification to inlcude multiple input formats'''
import os
import re
import logging
import subprocess
import csv
import argparse
from lxml import etree
from string import Template
import json
import canons

logging.basicConfig(filename='debug2.log',level=logging.DEBUG, format='%(asctime)s\t%(message)s')

logging.info("------------------------------------------")

class Sniffer(object):
	'''Versification identification logics irrespective of input format'''
	def __init__(self, books, outdir='../../data/output/', vrs=False,
		mappings='../../versification-mappings/standard-mappings',
		rules='../rules/merged_rules.json'):
		super(Sniffer, self).__init__()
		self.books = {}
		self.versification = {}
		self.verse_index = {}
		self.args = { "outdir": outdir, "vrs": vrs, "mappings":mappings, "rules":rules}
		self.sid_template = Template('$book $chapter:$verse')
		self.bcv_pattern = r'((\w+)\.(\d+)\:(\d+)\.?(\d+)?\*?(\d+)?)'
		self.factor_pattern = r'\*?(\d+)'

		# make sure all chapters are int and verses are str
		for b in books:
			self.books[b] = {}
			for c in books[b]:
				self.books[b][int(c)] = {}
				for v in books[b][c]:
					self.books[b][int(c)][str(v)] = books[b][c][v] 
		#make sure output path is present
		if not os.path.isdir(outdir):
			os.mrdir(outdir)


	def sniff(self, name=None):
		'''Takes the book dictionary and applies versification mappings and rules to create a versifcation json output'''
		if name is None:
			name = "custom_versification"
		self.versification['shortname'] = name
		self.max_verses()
		self.mapped_verses()
		for key in self.versification["partialVerses"].keys():
			self.versification["partialVerses"][key].sort()
		outfile = self.args["outdir"]+name+".json"
		with open(outfile, 'w') as otf:
			json.dump(self.versification, otf, indent=4, ensure_ascii=False)

	def max_verses(self):
		self.versification["maxVerses"] = {}
		self.versification["partialVerses"] = {}
		self.versification["verseMappings"] = {}
		self.versification["excludedVerses"] = {}
		self.versification["unexcludedVerses"] = {}
		for book in canons.book_ids:
			if book in self.books:
				max_verses = {}
				for chapter in self.books[book]:
					chapter = int(chapter)
					for verse in self.books[book][chapter]:
						self.partial(book, chapter, verse)
						verse_num = max(map(int, re.findall(r'\d+', verse)))
						if not chapter in max_verses:
							max_verses[chapter] = verse_num
						elif verse_num > max_verses[chapter]:
							max_verses[chapter] = verse_num
				if not book in self.versification["maxVerses"]:
					self.versification["maxVerses"][book] = []
				for i in sorted(max_verses):
					self.versification["maxVerses"][book].append(max_verses[i])

	def partial(self, book, chapter, verse):
		verses = re.split(r'[\-,\,]',verse)
		for pv in verses:
				segment = re.findall(r'\D+',pv)
				if segment:
						numeric = re.findall(r'\d+',pv)[0]
						id = self.sid_template.substitute(book=book, chapter=chapter, verse=verse)
						if not id in self.versification["partialVerses"]:
								self.versification["partialVerses"][id]=[]
								if self.find_verse(book,chapter,numeric) is not None:
										self.versification["partialVerses"][id].append('-')
						if segment:
										self.versification["partialVerses"][id].append(segment[0])

	def mapped_verses(self):
		with open(self.args["rules"]) as r:
			rules = json.load(r)
			for rule in rules:
				logging.info("-------------------------")
				logging.info("Rule: " + rule["name"])
				from_column = self.map_from(rule)
				if from_column is not None:
					to_column = self.map_to(rule)
					if from_column != to_column:
						self.create_mappings(rule, from_column, to_column)

	def do_test(self, parsed_test) -> bool:
		logging.info("do_test()")

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


		if not self.book_exists(left["book"]):
			logging.info(left["book"]+" not found in books")
			return False
		elif not self.chapter_exists(left["book"], left["chapter"]):
			logging.info("Chapter "+str(left["chapter"])+" not found in "+left["book"])
			return False
		else:
			logging.info(left["book"]+" found in books")

		if op == "=" and keyword == "Last":
			if not self.is_last_in_chapter(left["book"], left["chapter"], left["verse"]):
				return False
		elif op == "=" and keyword == "Exist":
			if self.find_verse(left["book"],left["chapter"],left["verse"]) is None:
				return False
		elif op == "=" and keyword == "NotExist":
			if self.find_verse(left["book"],left["chapter"],left["verse"]) is not None:
				return False

		elif op == "<" and 'chapter' in right:
			if self.has_more_words(left, right):
				return False
		elif op == ">"  and 'chapter' in right:
			if self.has_fewer_words(left, right):
				return False
		else:
			logging.info("Error in test!  (not implemented?)")
			return False

		return True

	def create_sid(self, bb, cc, vv):
		return self.sid_template.substitute(book=bb, chapter=cc, verse=vv)

	def find_verse(self, bb, cc, vv):
		cc = int(cc)
		vv = str(vv)
		if bb not in self.books or cc not in self.books[bb] or vv not in self.books[bb][cc]:
			return None
		return self.books[bb][cc][vv]


	def is_last_in_chapter(self, book, chapter, verse):
		logging.info("is_last_in_chapter()")
		logging.info(self.create_sid(book,chapter,verse) + " => " + str(self.versification["maxVerses"][book][chapter-1]))

		if verse == self.versification["maxVerses"][book][chapter-1]:
			logging.info("Last in chapter")
			return True
		else:
			logging.info("Not last in chapter")
			return False


	def has_more_words(self, ref, comparison):
		ref_string = self.find_verse(ref["book"], ref["chapter"],ref["verse"])
		comparison_string = self.find_verse(comparison["book"], comparison["chapter"], comparison["verse"])
		logging.info("has_more_words()")
		logging.info(ref)
		logging.info(comparison)
		logging.info(ref_string)
		logging.info(comparison_string)
		logging.info(len(ref_string) > len(comparison_string))
		ref_factor = ref["factor"] if "factor" in ref else 1
		comparison_factor = comparison["factor"] if "factor" in comparison else 1
		return len(ref_string)*ref_factor > len(comparison_string)*comparison_factor

	def has_fewer_words(self, ref, comparison):
		return self.has_more_words(comparison, ref)

	def book_exists(self, book):
		return book in self.versification["maxVerses"]

	def chapter_exists(self, book, chapter):
		return self.book_exists(book) and chapter <= len(self.versification["maxVerses"][book])

	def map_from(self, rule) -> int:
		"""
		Which column are we mapping from?

		c - the column that passes all of the tests
		None - no column passed all of the tests
		"""
		tests = rule["tests"]
		for column in range(0, len(tests)):
			if self.all_tests_pass(tests[column]):
				return column

		return None

	def all_tests_pass(self, tests) -> bool:
		for test in tests:
			pt = self.parse_test(test)
			if self.do_test(pt) is False:
				logging.info("do_test() returns " + "False")
				return False

		logging.info("do_test() returns " + "True")
		return True

	def parse_test(self, test) -> dict:
		d = {}

		t = re.compile('([<=>])')
		triple = t.split(test)
		if len(triple) != 3:
			logging.info("ERROR: Does not parse: " +test)
		else:
			d['left'] = {}
			d['left']['text'] = triple[0]
			d['left']['parsed'] = self.parse_ref(triple[0])
			d['op'] = triple[1]
			d['right'] = {}
			d['right']['text'] = triple[2]
			d['right']['parsed'] = self.parse_ref(triple[2])
			return d

	def parse_ref(self, ref):
		m = re.search(self.bcv_pattern, ref)
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

	def map_to(self, rule:dict) -> int:
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
		return to

	def create_mappings(self, rule:dict, from_column:int, to_column:int) -> None:
		logging.info("create_mappings(), rule="+rule["name"])
		logging.info("Map from column " + str(from_column) + " to column " + str(to_column))
		for r in rule["ranges"]:
			for k in r.keys():
				if max(from_column, to_column) <= len(r[k])-1:
					frum = r[k][from_column].upper().replace("."," ", 1)
					to = r[k][to_column].upper().replace("."," ", 1)
					logging.info(frum + " : " + to)
					if frum != to and to != "NOVERSE":
						self.versification["verseMappings"][frum] = to
				else:
					logging.info("### Error: missing column in mapping")


class InputParser(object):
	"""Base class InputParser"""
	def __init__(self):
		super(InputParser, self).__init__()
		self.verse_list = []
		self.books = {}

	def read_files():
		'''to be implemented in child classes'''
		pass

	def verse_list2dict(self, verses=None):
		'''input: a list of <book, chapter, verse_number, verse_text> dicts or tuples'''
		if verses is None:
			 verses = self.verse_list
		books = {}
		for row in verses:
			if isinstance(row, list) or isinstance(row, tuple):
				verse = {}
				verse['book'] = row[0]
				verse['chapter'] = row[1]
				verse['verse_num'] = row[2]
				verse['verse_text'] = row[3]
			else:
				verse = row
			verse['verse_num'] = str(verse['verse_num'])
			if verse['book'] not in books:
				books[verse['book']] = {}
			if verse['chapter'] not in books[verse['book']]:
				books[verse['book']][verse['chapter']] = {}
			if verse['verse_num'] in books[verse['book']][verse['chapter']]:
				raise Exception("%s already present", verse)
			books[verse['book']][verse['chapter']][verse['verse_num']] = verse['verse_text']
		return books



class USX_parser(InputParser):
	"""Logics related to converting USX files to a verse_list/book dictionary, required by Sniffer"""
	def __init__(self):
		super(USX_parser, self).__init__()
		self.input_path = None
		self.verse_index = {}

	def read_files(self, input_path):
		if not input_path.endswith("/"):
			input_path += "/"
		self.input_path = input_path
		books = {}
		for file in sorted(os.listdir(input_path)):
			if file.endswith(".usx"):
				root = etree.parse(input_path+file)
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
						self.verse_index[sid] = {}
						self.verse_index[sid]["start"] = verse
					elif eid is not None:
						if not eid in self.verse_index:
							self.verse_index[eid] = {}
						self.verse_index[eid]["end"] = verse
				logging.info("Book: " + book_identifier + " (" + file + ")")    
		for ref in self.verse_index:
			bbb, cv = ref.split()
			ccc,vvv = cv.split(":")
			ccc = int(ccc)
			if bbb not in self.books:
				self.books[bbb] = {}
			if ccc not in self.books[bbb]:
				self.books[bbb][ccc] = {}
			self.books[bbb][ccc][vvv] = self.verse_to_string(bbb, ccc, vvv)

	def find_verse(self, book, chapter, verse):
		sid=self.create_sid(book, chapter, verse)
		return (self.verse_index[sid]["start"] if sid in self.verse_index else None)

	def verse_to_string(self, book, chapter, v):
		verse = self.find_verse(book, chapter, v)
		if verse is None:
			return ""
		s = verse.tail
		if s is None:
			return ""
		e = verse

		while True:
			e = e.getnext()
			if e is None:
				s = s + self.get_rest_of_verse(verse)
				logging.warning("Verse " + self.create_sid(book, chapter, v) + " spans paragraph boundaries - don't trust this result yet!")
				break
			if e.tag == "verse":
				break
			if e.text:
				s = s + e.text
			if e.tail:
				s = s + e.tail
		return " ".join(s.split())

	def create_sid(self, book, chapter, verse):
		sid_template = Template('$book $chapter:$verse')
		return sid_template.substitute(book=book, chapter=chapter, verse=verse)

	def get_rest_of_verse(self, start_verse):
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

	def get_name(self, path=None):
		if path is None:
			path=self.input_path
		return path.split('/')[-2]



class USFM_parser(InputParser):
	"""Logics related to converting USFM files to a verse_list/book dictionary, required by Sniffer
	Requires node library usfm-grammar installed"""
	def __init__(self):
		super(USFM_parser, self).__init__()
		self.input_path = None

	def read_files(self, input_path):
		if not input_path.endswith("/"):
			input_path += "/"
		self.input_path = input_path
		for file in sorted(os.listdir(input_path)):
			if file.endswith(".usfm"):
				process = subprocess.Popen(['/usr/bin/usfm-grammar --level=relaxed --filter=scripture '+input_path+file],
									 stdout=subprocess.PIPE,
									 stderr=subprocess.PIPE,
									 shell=True)
				stdout, stderr = process.communicate()
				if stderr:
					raise Exception(stderr.decode('utf-8'))
				usfm_json = json.loads(stdout.decode('utf-8'))
				book_code = usfm_json['book']['bookCode']
				for chap in usfm_json['chapters']:
					chapter_num = chap['chapterNumber']
					for content in chap['contents']:
						if "verseNumber" in content:
							verse_num = content['verseNumber']
							verse_text = content['verseText']
							self.verse_list.append((book_code, chapter_num, verse_num, verse_text))
				logging.info("Processed file:%s", file)
		self.books = self.verse_list2dict()


class CSV_parser(InputParser):
	"""Logics related to converting CSV files to a verse_list/book dictionary, required by Sniffer.
	CSV files expected with a header and following fields:'Book', 'Chapter', 'Verse', 'Text'"""
	def __init__(self):
		super(CSV_parser, self).__init__()
		self.input_path = None
		self.bookpattern = re.compile(r"[\w\d]\w\w")
		self.chapterPattern = re.compile(r"\d+")

	def read_files(self, input_path):
		if not input_path.endswith("/"):
			input_path += "/"
		self.input_path = input_path
		for file in sorted(os.listdir(input_path)):
			if file.endswith(".csv") or file.endswith('.tsv'):
				with open(input_path+file, newline='') as csvfile:
					reader = csv.DictReader(csvfile, fieldnames=['Book', 'Chapter', 'Verse', 'Text'])
					next(reader, None)  # skip the headers
					for row in reader:
						if not re.match(self.bookpattern, row['Book']):
							raise Exception("Not the expected pattern for value 'Book' in row:%s",row)
						if not re.match(self.chapterPattern, row['Chapter']):
							raise Exception("Not the expected pattern for value 'Chapter' in row:%s",row)
						self.verse_list.append((row['Book'].upper(), row['Chapter'], row['Verse'], row['Text']))
				logging.info("Processed file:%s", file)
		self.books = self.verse_list2dict()

input1 = [
	{"book":"GEN", "chapter":1, "verse_num":1, "verse_text":"Sample text"},
	{"book":"GEN", "chapter":1, "verse_num":2, "verse_text":"Sample text"},
	{"book":"GEN", "chapter":1, "verse_num":3, "verse_text":"Sample text"},
	{"book":"GEN", "chapter":1, "verse_num":4, "verse_text":"Sample text"},
	{"book":"GEN", "chapter":1, "verse_num":5, "verse_text":"Sample text"},
	{"book":"GEN", "chapter":1, "verse_num":6, "verse_text":"Sample text"},
	{"book":"GEN", "chapter":1, "verse_num":7, "verse_text":"Sample text"},
	{"book":"GEN", "chapter":1, "verse_num":8, "verse_text":"Sample text"},
	{"book":"GEN", "chapter":1, "verse_num":9, "verse_text":"Sample text"},
	{"book":"GEN", "chapter":1, "verse_num":10, "verse_text":"Sample text"},
	{"book":"GEN", "chapter":1, "verse_num":11, "verse_text":"Sample text"},
	{"book":"GEN", "chapter":1, "verse_num":12, "verse_text":"Sample text"},
	{"book":"GEN", "chapter":1, "verse_num":13, "verse_text":"Sample text"},
	{"book":"GEN", "chapter":1, "verse_num":14, "verse_text":"Sample text"},
	{"book":"GEN", "chapter":1, "verse_num":15, "verse_text":"Sample text"}
]

input2 = [
	["GEN", 1, 1, "Sample text"],
	["GEN", 1, 2, "Sample text"],
	["GEN", 1, "2a", "Sample text"],
	["GEN", 1, "2b", "Sample text"],
	["GEN", 1, 3, "Sample text"],
	["GEN", 1, 4, "Sample text"],
	["GEN", 1, 5, "Sample text"],
	["GEN", 1, 6, "Sample text"],
	["GEN", 1, 7, "Sample text"],
	["GEN", 1, 8, "Sample text"],
	["GEN", 1, 9, "Sample text"],
	["GEN", 1, 10, "Sample text"],
	["GEN", 1, 11, "Sample text"],
	["GEN", 1, 12, "Sample text"],
	["GEN", 1, 13, "Sample text"],
	["GEN", 1, 14, "Sample text"],
	["GEN", 1, 15, "Sample text"],
	["REV", 1, 13, "Sample text"],
	["REV", 1, 14, "Sample text"],
	["REV", 1, 15, "Sample text"],
	["REV", 1, 16, "Sample text"],
	["REV", 1, 17, "Sample text"],
	["REV", 1, "18-20", "Sample text"]
]

# parser = InputParser()
# books = parser.verse_list2dict(input2)
# print(books)
# sniffer_obj = Sniffer(books)
# sniffer_obj.sniff(name="custom_versification")

if __name__ == '__main__':
	ap = argparse.ArgumentParser(description='Create Versification File from USX Files - See https://github.com/Copenhagen-Alliance/versification-specification/')
	ap.add_argument('-n', '--name', help="Short name of the text e.g. 'NRSVUK' or 'ESV', should be same as input directory name", required=True)
	ap.add_argument('-f','--format', help="Input file format. Any one of usx, usfm, csv", required=True)
	ap.add_argument('-i', '--indir', help="path containing input files directory", default="../../data/")
	ap.add_argument('-o', '--outdir', help="Directory for output", default='../../data/output/')
	ap.add_argument('-m', '--mappings', help="Directory containing versification mappings.", default='../../versification-mappings/standard-mappings')
	ap.add_argument('-r', '--rules', help="Merged rules file for mapping verses", default='../rules/merged_rules.json')
	ap.add_argument('-v', '--vrs', help="Generate versification in addition to .json", default=False)
	args = ap.parse_args()

	if args.format.lower() == 'usx':
	 	parser = USX_parser()
	elif args.format.lower() == 'usfm':
	 	parser = USFM_parser()
	elif args.format.lower() == 'csv':
		parser = CSV_parser()
	else:
		raise Exception("Unsupported format:%s", args.format)

	input_path = args.indir + args.name
	parser.read_files(input_path=input_path)
	books = parser.books
	sniffer_obj = Sniffer(books, outdir=args.outdir, vrs=args.vrs, mappings=args.mappings, rules=args.rules)
	sniffer_obj.sniff(args.name)

