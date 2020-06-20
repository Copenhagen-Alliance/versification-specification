import shutil
import urllib.request

tvtms_url = "https://raw.githubusercontent.com/tyndale/STEPBible-Data/master/TVTMS%20-%20Tyndale%20Versification%20Traditions%20with%20Methodology%20for%20Standardisation%20for%20Eng%2BHeb%2BLat%2BGrk%2BOthers%20-%20TyndaleHouse.com%20STEPBible.org%20CC%20BY-NC.txt"

with urllib.request.urlopen(tvtms_url) as response:
	with open('tvtms.tsv', 'wb') as otf:
		shutil.copyfileobj(response, otf)


def read_until_string(inf, s):
	for line in inf:
		if line.startswith(s):
			return(line)

# Return the lines found in the next rule
# or None if there are no more

def next_rule(inf):
	rule_text = []
	first = read_until_string(inf, '$')
	if first is None:
		return None
	first = first.rstrip().lstrip('$')
	rule_text.append(first.split('\t'))
	for line in inf:
		if line.startswith('\n'):
			return rule_text
		rule_text.append(line.rstrip().split('\t'))
	

# Convert rule to dict

def convert_rule(rule):
	return { "name" : rule[0][0], "columns" : rule[0][1:] }

# Extract the condensed data

with open('tvtms.tsv', 'r') as inf:
	with open('condensed.tsv', 'w') as otf:
		read_until_string(inf, "#DataStart(Condensed)")
		read_until_string(inf, "=======")

		for line in inf:
			if line.startswith("#DataEnd(Condensed)"):
				otf.close()
				print(line)
				break

			otf.write(line)

# convert to rules file

rules = []

with open('condensed.tsv', 'r') as inf:
	with open('tvtms_rules.json','w') as otf:
		while True:
			rule = next_rule(inf)
			if rule is None:
				break
			rules.append(convert_rule(rule))

print(rules)
