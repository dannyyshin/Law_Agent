import io
import re
from typing import Dict, List, Optional
import docx
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

# 실무 표준 서면 서식 유형
DOCUMENT_TEMPLATES = {
    "민사 소장": {
        "description": "손해배상, 대여금, 부당이득반환 등 민사소송 제기를 위한 정식 소장",
        "system_instruction": """대한민국 법원 민사소송 표준 양식에 맞추어 전문적이고 정밀한 [소장]을 작성하십시오.
반드시 아래의 법원 제출용 표준 필수 항목 구조를 완벽하게 준수하여 작성해야 합니다:

1. 표제: [소   장]
2. 당사자 표시: 원고(성명, 주민등록번호 또는 생년월일, 주소, 연락처) / 피고(성명, 주소)
3. 사건명: (예: 손해배상(기), 부당이득반환청구의 소 등)
4. [청구취지]:
   - '1. 피고는 원고에게 금 OOO원 및 이에 대하여 ... 다 갚는 날까지 연 12%의 각 비율로 계산한 돈을 지급하라.'
   - '2. 소송비용은 피고가 부담한다.'
   - '3. 제1항은 가집행할 수 있다.'
   - '라는 판결을 구합니다.' 형식 엄수
5. [청구원인]:
   - 1. 당사자들의 지위 및 관계
   - 2. 이 사건 사실관계의 경위 (일자별 구체적 행위 적시)
   - 3. 피고의 법적 책임 발생 (관련 법령 및 대법원 판례 법리 원용)
   - 4. 손해액(또는 청구금액)의 산정
   - 5. 소결론
6. [입증방법]: (갑 제1호증부터 순차적 기재)
7. [첨부서류]: 위 입증방법 각 1통, 소장 부본, 송달료 납부서 등
8. 작성일자, 원고 서명 날인란, 제출 관할법원 (예: 서울중앙지방법원 귀중)
"""
    },
    "민사 준비서면": {
        "description": "재판 변론 기일에 앞서 상대방 주장 반박 및 추가 주장·증거를 제출하는 준비서면",
        "system_instruction": """대한민국 법원 민사소송 표준 [준비서면]을 작성하십시오.
반드시 아래의 표준 항목을 준수하십시오:

1. 표제: [준 비 서 면]
2. 사건정보: 사건번호(202O가합/가단 OOO호), 사건명, 원고, 피고
3. 표어: '위 사건에 관하여 [원고/피고]는 다음과 같이 변론을 준비합니다.'
4. [상대방 주장의 요지 및 이에 대한 반박]:
   - 상대방(원고/피고)의 부당한 주장 요약
   - 사실과 다른 점 및 법리적 오류 조목조목 논파
5. [[원고/피고] 주장의 정당성]:
   - 대법원 판례 및 법률 조항에 따른 권리 성립 논증
6. [추가 입증계획]:
   - 서증 추가 제출(갑/을 제O호증) 또는 증인신문 신청 계획
7. [결론]:
   - '따라서 원고의 청구를 인용(또는 피고의 청구를 기각)하여 주시기 바랍니다.'
8. 작성일자, 대리인/당사자 서명 날인, 관할법원 귀중
"""
    },
    "고용노동부 진정서": {
        "description": "임금체불, 직장 내 괴롭힘, 부당징계 등 근로기준법 위반 행위 노동청 진정서",
        "system_instruction": """고용노동부 지방고용노동청에 제출하는 [진정서]를 작성하십시오.
근로기준법 및 노동관계법령 위반 사실을 명확히 적시하십시오:

1. 표제: [진 정 서]
2. [진정인]: 성명, 주민등록번호, 주소, 연락처
3. [피진정인(사업주)]: 회사명(상호), 대표자명, 사업장 소재지, 전화번호, 상시근로자 수
4. [진정취지]:
   - (예: 피진정인의 근로기준법 제76조의2 직장 내 괴롭힘 금지 위반 및 제36조 금품청산 위반에 대하여 철저히 조사하여 시정명령 및 처벌하여 주시기 바랍니다.)
5. [진정이유]:
   - 가. 진정인의 입사일, 담당직무, 근로계약 내용
   - 나. 피진정인의 법 위반 사실관계 (날짜, 시간, 장소, 가해자, 구체적 발언/행위, 피해 상황)
   - 다. 진정인이 입은 피해 및 요구사항
6. [증거자료]: 녹취록, 메시지(카카오톡/이메일) 캡처, 진단서, 출퇴근 기록 등
7. 작성일자, 진정인 서명 날인, 관할 지방고용노동청 귀중
"""
    },
    "노동위원회 부당해고 구제신청서": {
        "description": "지방노동위원회(지노위)에 부당해고·부당전직·부당대기발령 판정을 구하는 정식 구제신청서",
        "system_instruction": """노동위원회법 및 근로기준법 규정에 따른 지방노동위원회 [부당해고등 구제신청서]를 작성하십시오:

1. 표제: [부당해고 등 구제신청서]
2. [신청인]: 성명, 주민등록번호, 주소, 전화번호
3. [피신청인]: 회사명, 대표자 성명, 사업장 주소, 상시근로자 수
4. [신청취지]:
   - '1. 피신청인이 OOOO년 OO월 OO일 신청인에 대하여 행한 해고(또는 징계처분)는 부당함을 인정한다.'
   - '2. 피신청인은 신청인을 원직에 복직시키고, 해고기간 동안 정상적으로 근로하였더라면 받을 수 있었던 임금상당액을 지급하여야 한다.'
   - '라는 판정을 구합니다.'
5. [신청이유]:
   - 1. 당사자 관계 (근로관계 성립)
   - 2. 해고에 이르게 된 경위
   - 3. 이 사건 해고의 부당성:
        (1) 정당한 사유의 부존재 (근로기준법 제23조 제1항 위반)
        (2) 서면통지의무 위반 등 절차적 하자 (근로기준법 제27조 위반)
        (3) 양정의 과다 (비례의 원칙, 형평의 원칙 위반)
   - 4. 결론
6. [입증방법]: 신청인 제출 증빙자료 목록
7. 작성일자, 신청인 서명, 관할 지방노동위원회 귀중
"""
    },
    "채권가압류신청서": {
        "description": "본안소송 전 채무자의 예금채권, 급여, 임대차보증금 등을 동결하기 위한 보전처분 신청서",
        "system_instruction": """대한민국 법원 민사집행 표준 [채권가압류신청서]를 작성하십시오:

1. 표제: [채권가압류신청서]
2. 당사자 표시:
   - 채권자: 성명, 주민등록번호, 주소, 연락처
   - 채무자: 성명, 주민등록번호, 주소
   - 제3채무자: (예: 주식회사 OO은행 등 법인명, 대표자, 본점 소재지)
3. [청구채권의 표시]: 금 OOO원 (피보전권리: 손해배상청구권 또는 대여금반환청구권)
4. [가압류할 채권의 표시]: 별지 목록 기재와 같음
5. [신청취지]:
   - '1. 채무자의 제3채무자에 대한 별지 기재 채권을 가압류한다.'
   - '2. 제3채무자는 채무자에게 위 채권에 관한 지급을 하여서는 아니 된다.'
   - '3. 채무자는 위 채권의 처분과 영수를 하여서는 아니 된다.'
   - '라는 재판을 구합니다.'
6. [신청이유]:
   - 1. 피보전권리의 존재 (기초 원인사실 및 채권 발생 근거)
   - 2. 보전의 필요성 (채무자의 재산은닉 또는 무자력 우려, 긴급성 소명)
   - 3. 담보제공 (서울보증보험 공탁보증보험증권 제출 허가 신청)
7. [소명방법]: 소명자료 목록
8. [별지]: 가압류할 채권의 표시
9. 작성일자, 채권자 서명 날인, 관할법원 귀중
"""
    }
}

class LegalDrafter:
    """실무 법률 서면 생성 및 Microsoft Word(.docx) 서식 변환기"""

    @staticmethod
    def get_template_names() -> List[str]:
        return list(DOCUMENT_TEMPLATES.keys())

    @staticmethod
    def get_template_info(doc_type: str) -> Dict[str, str]:
        return DOCUMENT_TEMPLATES.get(doc_type, {})

    @staticmethod
    def build_draft_prompt(doc_type: str, case_facts: str, case_laws: str, user_demands: str) -> str:
        """사건 정보와 법령/판례를 결합한 실무 드래프팅 프롬프트 조립"""
        tmpl = DOCUMENT_TEMPLATES.get(doc_type, DOCUMENT_TEMPLATES["민사 소장"])
        
        prompt = f"""당신은 20년 경력의 대한민국 수석 변호사이자 법률문서 전문 작성관입니다.
아래 제공된 [사건 사실관계], [적용 법령 및 대법원 판례], [의뢰인의 청구/요구사항]을 철저히 분석하여,
실제 법원 및 노동위원회/노동청에 즉시 제출 가능한 최고 수준의 완성도 높은 '{doc_type}'을 작성해 주십시오.

{tmpl['system_instruction']}

[의뢰인 요구사항]:
{user_demands if user_demands else "제공된 사실관계에 입각하여 법적으로 인정 가능한 최대 범위의 청구 구성"}

[사건 사실관계 및 증거 요약]:
{case_facts}

[관련 법령 및 대법원 판례 자료]:
{case_laws if case_laws else "대한민국 현행 법령 및 확립된 대법원 판례 법리를 직접 적용하여 인용할 것"}

[작성 지침]:
- 마크다운 문법(#, ##, **)을 활용하여 시각적으로 정갈하게 구성하십시오.
- 허위 사실을 창작하지 말고, 사실관계에 명시된 일시, 인명, 금액, 행위를 정확히 반영하십시오.
- 법리적 요건사실(권리발생요건)을 철저히 갖추고 대법원 판례 선고번호를 정확히 원용하십시오.
- 금액 계산, 지연손해금(소송촉진특례법 연 12% 등), 소송비용 부담 조항을 누락 없이 포함하십시오.
"""
        return prompt

    @staticmethod
    def export_to_docx(document_text: str, doc_title: str = "법률서면") -> io.BytesIO:
        """
        마크다운 형식의 법률 서면을 대한민국 표준 공문서/소송서면 규격의 .docx 파일로 생성
        """
        doc = docx.Document()

        # 여백 설정: A4 표준 (위 25mm, 아래 25mm, 좌 25mm, 우 25mm)
        sections = doc.sections
        for section in sections:
            section.top_margin = Inches(0.98)
            section.bottom_margin = Inches(0.98)
            section.left_margin = Inches(0.98)
            section.right_margin = Inches(0.98)

        # 기본 스타일 폰트 설정
        style = doc.styles['Normal']
        font = style.font
        font.name = 'Malgun Gothic'
        font.size = Pt(10.5)
        font.color.rgb = RGBColor(0x22, 0x22, 0x22)
        style.paragraph_format.line_spacing = 1.35
        style.paragraph_format.space_after = Pt(4)

        # 문서 제목 헤더 추가
        title_p = doc.add_paragraph()
        title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_run = title_p.add_run(doc_title)
        title_run.font.name = 'Malgun Gothic'
        title_run.font.size = Pt(18)
        title_run.font.bold = True
        title_run.font.color.rgb = RGBColor(0x0f, 0x17, 0x2a) # Dark slate
        title_p.paragraph_format.space_before = Pt(10)
        title_p.paragraph_format.space_after = Pt(20)

        # 본문 줄 단위 파싱 및 스타일링 적용
        lines = document_text.split('\n')
        for line in lines:
            line_str = line.strip()
            if not line_str:
                doc.add_paragraph()
                continue

            # 대제목 (# 또는 [소 장] 등)
            if line_str.startswith('# ') or line_str in [f"[{doc_title}]", f"[{doc_title.replace(' ', '')}]"]:
                text_clean = line_str.lstrip('# ').strip()
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                r = p.add_run(text_clean)
                r.font.name = 'Malgun Gothic'
                r.font.size = Pt(16)
                r.font.bold = True
                p.paragraph_format.space_before = Pt(14)
                p.paragraph_format.space_after = Pt(10)

            # 중제목 (## 또는 1. 청구취지 등)
            elif line_str.startswith('## ') or re.match(r'^[\[【][^\]】]+[\]】]', line_str):
                text_clean = line_str.lstrip('# ').strip()
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                r = p.add_run(text_clean)
                r.font.name = 'Malgun Gothic'
                r.font.size = Pt(13)
                r.font.bold = True
                r.font.color.rgb = RGBColor(0x1e, 0x3a, 0x8a) # Navy
                p.paragraph_format.space_before = Pt(12)
                p.paragraph_format.space_after = Pt(6)

            # 소제목 (### 또는 가. 나. 다. 등)
            elif line_str.startswith('### '):
                text_clean = line_str.lstrip('# ').strip()
                p = doc.add_paragraph()
                r = p.add_run(text_clean)
                r.font.name = 'Malgun Gothic'
                r.font.size = Pt(11.5)
                r.font.bold = True
                p.paragraph_format.space_before = Pt(8)
                p.paragraph_format.space_after = Pt(4)

            # 일반 본문 문단
            else:
                p = doc.add_paragraph()
                # 불릿 기호 처리
                if line_str.startswith('- ') or line_str.startswith('* '):
                    p.paragraph_format.left_indent = Inches(0.2)
                    line_str = "• " + line_str[2:]
                elif re.match(r'^\d+\.\s', line_str):
                    p.paragraph_format.left_indent = Inches(0.15)

                # 볼드 구문 (**text**) 분해 처리
                parts = re.split(r'(\*\*[^*]+\*\*)', line_str)
                for part in parts:
                    if part.startswith('**') and part.endswith('**'):
                        r = p.add_run(part[2:-2])
                        r.font.name = 'Malgun Gothic'
                        r.font.bold = True
                    else:
                        r = p.add_run(part)
                        r.font.name = 'Malgun Gothic'

        # 메모리 버퍼에 저장 후 반환
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer
