import json
import re
from typing import List, Dict, Any
import google.generativeai as genai

class TimelineEngine:
    """사건 기록으로부터 일자별 사실관계 및 쟁점을 추출하여 인터랙티브 타임라인으로 시각화하는 엔진"""

    EXTRACTION_PROMPT = """당신은 20년 경력의 대한민국 수석 법률분석관입니다.
제공된 [사건 기록/증거 자료/상담 내용]에서 법적 분쟁의 핵심 사실관계를 발생 일자 순(연대기순)으로 추출하여,
반드시 유효한 JSON 배열(Array) 형식만 응답하십시오.

[출력 JSON 형식]:
[
  {
    "date": "YYYY.MM.DD 또는 YYYY년 M월경",
    "actor": "행위 주체 (예: 피고, 원고, 팀장 김OO 등)",
    "title": "사건 핵심 요약 (20자 이내)",
    "content": "구체적 행위 및 발언, 피해 사실관계 서술 (1~2문장)",
    "evidence": "관련 증거 (예: 카카오톡 대화, 통화 녹취록, 진단서, 계약서 등 / 없으면 '증거 미확보')",
    "legal_issue": "법적 평가 및 쟁점 (예: 근로기준법 제76조의2 위반, 소멸시효 기산점 등)",
    "level": "critical" // "normal" (통상 경위), "warning" (갈등 시작/경고), "critical" (핵심 위법행위/처분/소송제기)
  }
]

[지침]:
1. 시간 순서대로 정렬하여 추출하십시오.
2. 사실관계에 명시되지 않은 허위 날짜나 사건을 날조하지 마십시오. 날짜가 불명확하면 '2024년 3월경' 등으로 표기하십시오.
3. 코드 블록(```json ... ```) 또는 순수 JSON 배열만 출력하십시오. 설명 문구를 붙이지 마십시오.

[사건 내용]:
"""

    @classmethod
    def extract_events_from_text(cls, model_name: str, text: str) -> List[Dict[str, Any]]:
        """Gemini 모델을 호출하여 텍스트에서 구조화된 연대기 JSON 추출"""
        if not text or not text.strip():
            return []

        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(cls.EXTRACTION_PROMPT + text)
            raw_text = response.text.strip()

            # 마크다운 json 블록 추출
            json_match = re.search(r'```(?:json)?\s*(\[\s*\{.*?\}\s*\])\s*```', raw_text, re.DOTALL)
            if json_match:
                raw_json = json_match.group(1)
            else:
                raw_json = raw_text

            events = json.loads(raw_json)
            if isinstance(events, list):
                return events
            return []
        except Exception as e:
            print(f"[타임라인 추출 오류]: {e}")
            return []

    @staticmethod
    def render_timeline_html(events: List[Dict[str, Any]]) -> str:
        """
        추출된 사건 연대기를 Generative UI 스타일의 인터랙티브 수직 타임라인 HTML로 렌더링
        """
        if not events:
            return """
            <div style="padding: 24px; text-align: center; color: #64748b; background: #f8fafc; border-radius: 12px; border: 1px dashed #cbd5e1;">
                <p style="font-size: 15px; margin: 0; font-weight: 500;">📅 추출된 사실관계 타임라인 데이터가 없습니다.</p>
                <p style="font-size: 13px; margin: 6px 0 0 0; color: #94a3b8;">사건 상담을 진행하거나 사건 파일을 업로드한 후 '타임라인 자동 추출'을 실행해 주세요.</p>
            </div>
            """

        items_html = []
        for idx, ev in enumerate(events):
            date_str = ev.get("date", "일자 미상")
            actor = ev.get("actor", "당사자")
            title = ev.get("title", f"사건 경위 {idx+1}")
            content = ev.get("content", "")
            evidence = ev.get("evidence", "증거 미확보")
            legal_issue = ev.get("legal_issue", "")
            level = ev.get("level", "normal").lower()

            # 레벨별 색상 테마
            if level == "critical":
                badge_bg = "#fee2e2"
                badge_color = "#dc2626"
                node_color = "#ef4444"
                border_color = "#fca5a5"
                level_label = "🚨 핵심 위법/처분"
            elif level == "warning":
                badge_bg = "#fef3c7"
                badge_color = "#d97706"
                node_color = "#f59e0b"
                border_color = "#fcd34d"
                level_label = "⚠️ 갈등·주의"
            else:
                badge_bg = "#e0f2fe"
                badge_color = "#0284c7"
                node_color = "#38bdf8"
                border_color = "#bae6fd"
                level_label = "ℹ️ 일반 경위"

            item_str = f"""
            <div class="timeline-item" style="position: relative; padding-left: 36px; margin-bottom: 24px;">
                <!-- 타임라인 노드 아이콘 -->
                <div style="position: absolute; left: 0; top: 4px; width: 18px; height: 18px; border-radius: 50%; background: #ffffff; border: 4px solid {node_color}; box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.15); z-index: 2;"></div>
                
                <!-- 카드 본문 -->
                <div style="background: #ffffff; border: 1px solid {border_color}; border-radius: 12px; padding: 16px 20px; box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04); transition: transform 0.15s ease, box-shadow 0.15s ease;">
                    <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; margin-bottom: 8px;">
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <span style="font-size: 14px; font-weight: 700; color: #0f172a; background: #f1f5f9; padding: 4px 10px; border-radius: 6px; font-family: monospace;">
                                📅 {date_str}
                            </span>
                            <span style="font-size: 13px; font-weight: 600; color: #334155;">
                                👤 {actor}
                            </span>
                        </div>
                        <span style="font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 12px; background: {badge_bg}; color: {badge_color};">
                            {level_label}
                        </span>
                    </div>

                    <h4 style="margin: 0 0 8px 0; font-size: 15px; font-weight: 700; color: #1e293b;">
                        {title}
                    </h4>

                    <p style="margin: 0 0 12px 0; font-size: 13.5px; line-height: 1.6; color: #475569;">
                        {content}
                    </p>

                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 8px; padding-top: 10px; border-top: 1px dashed #e2e8f0; font-size: 12.5px;">
                        <div style="color: #64748b;">
                            <strong style="color: #0369a1;">📁 입증 증거:</strong> {evidence}
                        </div>
                        {f'<div style="color: #64748b;"><strong style="color: #b91c1c;">⚖️ 법적 쟁점:</strong> {legal_issue}</div>' if legal_issue else ''}
                    </div>
                </div>
            </div>
            """
            items_html.append(item_str)

        full_html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Pretendard', sans-serif; max-width: 900px; margin: 0 auto; padding: 10px 4px;">
            <div style="position: relative; border-left: 2px solid #e2e8f0; margin-left: 8px; padding-top: 8px;">
                {"".join(items_html)}
            </div>
        </div>
        """
        return full_html
