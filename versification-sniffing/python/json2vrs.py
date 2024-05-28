import os
import argparse
from string import Template
import json
import canons

from inspect import currentframe
import logging
logging.basicConfig(filename='debug.log',level=logging.DEBUG, format='%(asctime)s\t%(message)s')

ap = argparse.ArgumentParser(description='Convert Versification from JSON to Paratext VRS - See https://github.com/Copenhagen-Alliance/versification-specification/')
ap.add_argument('-j', '--json', help="Name of the .json file", required=True)
args = ap.parse_args()


if args.json:
    try:
        fp = open(args.json, "r")
        base = json.load(fp)
    except Exception as exc:
        print(exc)
        base = None

print("# Versification for " + base["shortname"])
print("#")

print("# Maximum Verses per Chapter")
for key in base["maxVerses"].keys():
	print(key, end=" ")
	i=1
	chapter_lengths = base["maxVerses"][key]
	for i in range(0, len(chapter_lengths)):
		if i < len(chapter_lengths) - 1:
			print(str(i+1)+":"+str(chapter_lengths[i]), end=" ")
		else:
			print(str(i+1)+":"+str(chapter_lengths[i]))

print("# Excluded Verses")
for item in base["excludedVerses"]:
	print("-"+item)

print("# Verse Segments (aka Partial Verses)")
for key in base["partialVerses"].keys():
	print("*"+",".join([key]+base["partialVerses"][key]))

print("# Verse Mappings")
for key in base["verseMappings"].keys():
	print(key + " = " + base["verseMappings"][key])
