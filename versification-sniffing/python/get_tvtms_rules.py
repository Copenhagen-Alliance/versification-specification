import json
import shutil
import urllib.request


"""
    Best visual representation of the TVTMS data is in this spreadsheet:

    https://docs.google.com/spreadsheets/d/1mxUu7HJ5DScA7wOQLd-qFUMuG_MHnWjM6KxJ79qQs9Q/edit#gid=1869211794
"""

def read_until_string(inf, s):
        for line in inf:
                if line.startswith(s):
                        return(line)

def next_rule(inf) -> list:
        """ Returns the lines found in the next rule or None if there are no more """
        rule_text = []
        first = read_until_string(inf, '$')
        if first is None:
                return None
        first = first.rstrip().lstrip('$')
        rule_text.append(first.split('\t'))
        for line in inf:
                if line.startswith('\n'):
                        return rule_text
                if line.strip() != "":
                        rule_text.append(line.rstrip().split('\t'))

def transpose(rows: list) -> list:
        """ Converts columns to rows. Removes empty strings. """
        ncols = len(rows[0])
        return [[ r[i] for r in rows if i < len(r) if r[i]] for i in range(0, ncols) ]


def merge_columns(rule: dict) -> dict:
        """
        Eliminate duplicate rules.  Several columns can have the same tests; if so, they
        will also have the same references. Merge columns that have the same rules so
        that the merged columns each uniquely identify a partition in the versification space.
        """
        ncols = len(rule["columns"])

        categorized = []
        column_numbers = []
        merged = []
        tests = []
        ranges = []
        
        for i in range(0, ncols):
                """ If this column has not been categorized yet, create a column for it """
                if rule["columns"][i] not in categorized:
                        categorized.append(rule["columns"][i])
                        column_numbers.append(i)
                        merged.append( [ rule["columns"][i] ] )
                        tests.append(rule["tests"][i])

                """ If other columns have the same tests, merge them in. """
                for j in range(i+1, ncols):
                        if rule["columns"][j] not in categorized and rule["tests"][i] == rule["tests"][j]:
                                categorized.append(rule["columns"][j])
                                merged[-1].append(rule["columns"][j])

        """ Filter ranges """
        for r in rule["ranges"]:
                for k in r.keys():
                        d = {}
                        d[k] = [ r[k][i] for i in range(0, len(r[k])) if i in column_numbers]
                        """
                        for i in column_numbers:
                                if i in r[k]:
                                        d[k].append(r[k][i])
                        """
                        ranges.append(d)
                                        
                                
        d = {
                "name": rule["name"],
                "columns": merged,
                "tests": tests,
                "ranges": ranges
        }
        return d

def convert_rule(rule: list) -> dict:
        d = {   
                "name" : rule[0][0], 
                "columns" : rule[0][1:],
                "tests" : transpose([row[1:] for row in rule if row[0].startswith("TEST")]),
                "ranges" : [ { row[0]: row[1:] } for row in rule if row[0] != rule[0][0] if not row[0].startswith("TEST") ]
        }
        return d


""" Get the TVTMS file in TSV format  """

tvtms_url = "https://raw.githubusercontent.com/tyndale/STEPBible-Data/master/TVTMS%20-%20Tyndale%20Versification%20Traditions%20with%20Methodology%20for%20Standardisation%20for%20Eng%2BHeb%2BLat%2BGrk%2BOthers%20-%20TyndaleHouse.com%20STEPBible.org%20CC%20BY-NC.txt"

with urllib.request.urlopen(tvtms_url) as response:
        with open('tvtms.tsv', 'wb') as otf:
                shutil.copyfileobj(response, otf)


""" Extract the condensed data """

with open('tvtms.tsv', 'r') as inf:
        with open('condensed.tsv', 'w') as otf:
                read_until_string(inf, "#DataStart(Condensed)")
                read_until_string(inf, "=======")

                for line in inf:
                        if line.startswith("#DataEnd(Condensed)"):
                                otf.close()
                                break

                        otf.write(line)

""" Convert to JSON """

condensed_rules = []
merged_rules = []

with open('condensed.tsv', 'r') as inf:
        while True:
                rule = next_rule(inf)
                if rule is None:
                        break
                condensed = convert_rule(rule)
                merged = merge_columns(condensed)
                condensed_rules.append(condensed)
                merged_rules.append(merged)

with open('condensed_rules.json','w') as otf:
    json.dump(condensed_rules, otf, ensure_ascii=False, indent=4)

with open('merged_rules.json','w') as otf:
    json.dump(merged_rules, otf, ensure_ascii=False, indent=4)

