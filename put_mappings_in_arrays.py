import json

file_path = "versification-mappings/standard-mappings/vul.json"

with open(file_path, "r") as read_file:
    versification_json = json.load(read_file)

#for field in versification_json:
#    mapped_verses = versification_json[field]["mappedVerses"]    
#    for mapping_key in mapped_verses:
#        mapped_verses[mapping_key] = [mapped_verses[mapping_key]]
#    versification_json[field]["mappedVerses"] = mapped_verses
    
mapped_verses = versification_json["mappedVerses"]
for mapping_key in mapped_verses:
    mapped_verses[mapping_key] = [mapped_verses[mapping_key]]
versification_json["mappedVerses"] = mapped_verses

with open(file_path, "w") as write_file:
    json.dump(versification_json, write_file, indent=2)