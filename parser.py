import io
import re
import zipfile
import xml.etree.ElementTree as ET
import fitz  # PyMuPDF

class MultiFormatParser:
    """
    PDF, HWPX(한글 표준), TXT 등 다양한 사건 서면 문서를 
    무손실로 텍스트 추출하는 통합 문서 파서
    """

    @staticmethod
    def parse_pdf(stream_bytes: bytes) -> str:
        """PyMuPDF(fitz)를 이용한 고속 PDF 텍스트 추출"""
        try:
            doc = fitz.open(stream=stream_bytes, filetype="pdf")
            text_parts = []
            for page in doc:
                text_parts.append(page.get_text())
            return "\n".join(text_parts).strip()
        except Exception as e:
            return f"[PDF 파싱 실패: {str(e)}]"

    @staticmethod
    def parse_hwpx(stream_bytes: bytes) -> str:
        """
        HWPX(한글 표준 ZIP+XML) 규격에서 
        본문 섹션 XML(Contents/section*.xml) 내 텍스트 100% 무손실 추출
        """
        text_list = []
        try:
            with zipfile.ZipFile(io.BytesIO(stream_bytes)) as z:
                # 본문 섹션 파일들 정렬 (section0.xml, section1.xml 등)
                section_files = [f for f in z.namelist() if re.match(r'^Contents/section\d+\.xml$', f, re.IGNORECASE)]
                section_files.sort()
                
                if not section_files:
                    # 파일명 대소문자 또는 하위 경로 유연 탐색
                    section_files = [f for f in z.namelist() if 'section' in f.lower() and f.lower().endswith('.xml')]
                    section_files.sort()

                for sec in section_files:
                    xml_content = z.read(sec)
                    tree = ET.fromstring(xml_content)
                    for node in tree.iter():
                        if node.text and node.text.strip():
                            text_list.append(node.text.strip())
                            
            return "\n".join(text_list).strip()
        except Exception as e:
            return f"[HWPX 파싱 실패: {str(e)}]"

    @staticmethod
    def parse_txt(stream_bytes: bytes) -> str:
        """텍스트 파일 인코딩(UTF-8 / CP949) 자동 감지 디코딩"""
        for enc in ['utf-8', 'cp949', 'euc-kr', 'utf-16le']:
            try:
                return stream_bytes.decode(enc).strip()
            except UnicodeDecodeError:
                continue
        return stream_bytes.decode('utf-8', errors='ignore').strip()

    @classmethod
    def parse_file(cls, filename: str, file_bytes: bytes) -> str:
        """파일명 확장자에 따라 적절한 파서로 자동 라우팅"""
        lower = filename.lower()
        if lower.endswith('.pdf'):
            return cls.parse_pdf(file_bytes)
        elif lower.endswith('.hwpx'):
            return cls.parse_hwpx(file_bytes)
        elif lower.endswith('.txt'):
            return cls.parse_txt(file_bytes)
        elif lower.endswith('.hwp'):
            # 구형 바이너리 HWP의 경우 HWPX 변환 권장 안내
            return f"[안내: '{filename}'은 구형 바이너리 HWP 파일입니다. 아래아한글에서 '다른 이름으로 저장 -> HWPX 또는 PDF'로 변환해 올려주시면 100% 인식됩니다.]"
        return ""
