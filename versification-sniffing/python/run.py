if __name__ == '__main__':
	'''
 	ap = argparse.ArgumentParser(description='Create Versification File from USX Files - See https://github.com/Copenhagen-Alliance/versification-specification/')
	ap.add_argument('-n', '--name', help="Short name of the text e.g. 'NRSVUK' or 'ESV', should be same as input directory name", required=True)
	ap.add_argument('-f','--format', help="Input file format. Any one of usx, usfm, csv", required=True)
	ap.add_argument('-i', '--indir', help="path containing input files directory", default="../../data/")
	ap.add_argument('-o', '--outdir', help="Directory for output", default='../../data/output/')
	ap.add_argument('-m', '--mappings', help="Directory containing versification mappings.", default='../../versification-mappings/standard-mappings')
	ap.add_argument('-r', '--rules', help="Merged rules file for mapping verses", default='../rules/merged_rules.json')
	ap.add_argument('-v', '--vrs', help="Generate versification in addition to .json", default=False)
	args = ap.parse_args()
 	'''

    #python script_name.py -n "ESV" -f "usx" -i "../../data/input/" -o "../../data/output/" -m "../../versification-mappings/standard-mappings" -r "../rules/merged_rules.json" -v True
 
    
    name = "BSB"
	format = "tsv"
	indir = "data/input/"
	outdir = "data/output/"
	mappings = "versification-mappings/standard-mappings/"
	rules = "versification-sniffing/rules/merged_rules.json"
	vrs = True

	if format.lower() == 'usx':
		parser = USX_parser()
	elif format.lower() == 'usfm':
		parser = USFM_parser()
	elif format.lower() == 'csv':
		parser = CSV_parser()
	else:
		raise Exception("Unsupported format:%s", format)

	input_path = indir + name
	parser.read_files(input_path=input_path)
	books = parser.books
	sniffer_obj = Sniffer(books, outdir=outdir, vrs=vrs, mappings=mappings, rules=rules)
	sniffer_obj.sniff(name)