#####################################################################################################
import os
import nltk 
from nltk.tokenize import sent_tokenize
#####################################################################################################

nltk.download('punkt')

def extract_sections(text):
    sections = []
    
    sentences = sent_tokenize(text)
    section = ""
    for sentence in sentences:
        if "Section" in sentence:
            sections.append(section)
            section = ""
        section += sentence + "\n"
    sections.append(section)
    return sections

def merge_sections(directory):
    merged_sections = []
    for filename in os.listdir(directory):
        if filename.endswith('.txt'):
            filepath = os.path.join(directory, filename)
            with open(filepath, 'r', encoding='utf-8') as file:
                text = file.read()
                sections = extract_sections(text)
                merged_sections.extend(sections)
    return merged_sections

def write_merged_sections(merged_sections, output_file):
    with open(output_file, 'w', encoding='utf-8') as file:
        for section in merged_sections:
            file.write(section + "\n\n")

#####################################################################################################