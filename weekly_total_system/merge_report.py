#####################################################################################################
import os
import nltk 
from nltk.tokenize import sent_tokenize
#####################################################################################################

nltk.download('punkt')

# 주간 보고서 파일이 있는 디렉토리 경로
directory = '/path/to/weekly_reports/'

# 각 섹션별로 텍스트를 추출하는 함수
def extract_sections(text):
    sections = []
    # 보고서를 섹션으로 나누는 방법에 따라 수정할 수 있음
    # 예를 들어, 보고서의 섹션을 제목 또는 특정 키워드로 구분할 수 있음
    # 여기서는 문장 단위로 섹션을 나눔    
    sentences = sent_tokenize(text)
    section = ""
    for sentence in sentences:
        if "Section" in sentence: # 섹션 시작을 나타내는 키워드에 따라 수정
            sections.append(section)
            section = ""
        section += sentence + "\n"
    sections.append(section)
    return sections

# 모든 보고서의 섹션을 하나의 리스트로 병합하는 함수
def merge_sections(directory):
    merged_sections = []
    for filename in os.listdir(directory):
        if filename.endswith('.txt'): # 주간 보고서 파일 확장자에 맞게 수정
            filepath = os.path.join(directory, filename)
            with open(filepath, 'r', encoding='utf-8') as file:
                text = file.read()
                sections = extract_sections(text)
                merged_sections.extend(sections)
    return merged_sections

# 병합된 섹션을 하나의 파일에 작성하는 함수
def write_merged_sections(merged_sections, output_file):
    with open(output_file, 'w', encoding='utf-8') as file:
        for section in merged_sections:
            file.write(section + "\n\n")

# 메인 함수
def main():
    merged_sections = merge_sections(directory)
    output_file = '/path/to/merged_sections.txt'  # 병합된 섹션을 저장할 파일 경로
    write_merged_sections(merged_sections, output_file)
    print("주간 보고서 섹션이 성공적으로 병합되었습니다!")

if __name__ == "__main__":
    main()
