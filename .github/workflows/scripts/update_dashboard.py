"""
포트나이트 커뮤니티 동향 자동 수집 & 대시보드 HTML 업데이트 스크립트
매일 GitHub Actions에서 실행됩니다.
"""

import anthropic
import json
import re
import os
from datetime import datetime, timezone, timedelta

# ── 설정 ──────────────────────────────────────────────────────────────────────
KST = timezone(timedelta(hours=9))
TODAY = datetime.now(KST).strftime("%Y년 %m월 %d일")
TODAY_SHORT = datetime.now(KST).strftime("%Y.%m.%d")

SEARCH_QUERIES = [
    "포트나이트 커뮤니티 반응 최신",
    "포트나이트 에픽게임즈 이슈 오늘",
    "Fortnite Google Play 반응 2026",
]

ANALYSIS_PROMPT = f"""포트나이트 커뮤니티 동향 분석 전문가로서, 위에서 검색된 최신 정보를 바탕으로 {TODAY} 기준 리포트를 작성하세요. 각 섹션은 3~4문장 이내로 작성하세요.

[배경 정보]
• 3/19 구글플레이 복귀(5년7개월만) — 챕터7 시즌2 쇼다운, 진영선택(파운데이션vs얼음왕)
• 구글-에픽 합의: 수수료 30%→20%, 에픽 2032년까지 구글 공개비난 자제
• 브이벅스 가격 인상 / 4월 세이브더월드 무료화 / 4/9 아레나 모드
• 3/24 에픽 직원 1,000명(전체 20%) 해고 — "이용률 감소로 지출>수입"
• 모드 3종 종료: 발리스틱·페스티벌배틀스테이지(4/16), 로켓레이싱(10월)
• DC·에펨코리아는 크롤링 차단으로 직접수집 불가

아래 형식으로 작성하세요:

### 📌 오늘의 핵심 동향
### 💬 채널별 반응 요약
### 📈 트렌드 분석
### ⚠️ 리스크 & 기회 요소
### 🔮 내일 주목할 점

---
응답 마지막에 JSON 추가 (마크다운 없이):
<<<JSON>>>
{{"sentiment":{{"positive":40,"neutral":30,"negative":30}},"keywords":[{{"word":"키워드1","heat":"hot"}},{{"word":"키워드2","heat":"hot"}},{{"word":"키워드3","heat":"warm"}},{{"word":"키워드4","heat":"warm"}},{{"word":"키워드5","heat":"cool"}}],"issues":[{{"type":"neg","title":"제목","desc":"설명"}},{{"type":"warn","title":"제목","desc":"설명"}},{{"type":"pos","title":"제목","desc":"설명"}}],"issueCount":3}}
<<<ENDJSON>>>"""


def search_and_analyze():
    """Claude API로 웹 검색 + 분석을 수행합니다."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    print(f"[{TODAY}] 검색 및 분석 시작...")

    # 검색 쿼리를 프롬프트에 포함
    search_context = "\n".join([f"- {q}" for q in SEARCH_QUERIES])
    full_prompt = f"다음 주제들에 대해 최신 정보를 검색하고 분석해주세요:\n{search_context}\n\n{ANALYSIS_PROMPT}"

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": full_prompt}]
    )

    # 텍스트 블록 추출
    full_text = "\n".join(
        block.text for block in response.content
        if hasattr(block, "text")
    )

    print(f"응답 수신 완료 ({len(full_text)} chars)")
    return full_text


def parse_response(full_text):
    """응답에서 리포트 텍스트와 JSON 데이터를 분리합니다."""
    json_data = None
    report_text = full_text

    match = re.search(r'<<<JSON>>>([\s\S]*?)<<<ENDJSON>>>', full_text)
    if match:
        try:
            json_data = json.loads(match.group(1).strip())
            report_text = full_text.replace(match.group(0), "").strip()
            print("JSON 파싱 성공:", json_data)
        except json.JSONDecodeError as e:
            print(f"JSON 파싱 실패: {e}")

    # 기본값 설정
    if not json_data:
        json_data = {
            "sentiment": {"positive": 40, "neutral": 35, "negative": 25},
            "keywords": [
                {"word": "구글플레이 복귀", "heat": "hot"},
                {"word": "에픽 해고", "heat": "hot"},
                {"word": "브이벅스 인상", "heat": "warm"},
                {"word": "챕터7 시즌2", "heat": "warm"},
                {"word": "아레나 모드", "heat": "cool"},
            ],
            "issues": [
                {"type": "neg", "title": "대규모 구조조정", "desc": "직원 1,000명 해고, 이용률 감소 공식 인정"},
                {"type": "warn", "title": "브이벅스 가격 인상", "desc": "수수료 인하에도 가격 올려 유저 불만"},
                {"type": "pos", "title": "구글플레이 복귀", "desc": "안드로이드 접근성 개선, 신규 유입 기대"},
            ],
            "issueCount": 3
        }

    return report_text, json_data


def render_report_html(report_text):
    """마크다운 텍스트를 HTML로 변환합니다."""
    html = '<div class="rpt">'
    lines = report_text.split('\n')
    in_list = False

    for line in lines:
        line = line.strip()
        if not line:
            if in_list:
                html += '</ul>'
                in_list = False
            html += '<br>'
            continue

        if line.startswith('### '):
            if in_list:
                html += '</ul>'
                in_list = False
            html += f'<h3>{line[4:]}</h3>'
        elif line.startswith('- ') or line.startswith('• '):
            if not in_list:
                html += '<ul>'
                in_list = True
            content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', line[2:])
            html += f'<li>{content}</li>'
        else:
            if in_list:
                html += '</ul>'
                in_list = False
            content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', line)
            html += f'<p>{content}</p>'

    if in_list:
        html += '</ul>'
    html += '</div>'
    return html


def update_html(report_text, json_data):
    """index.html에 새로운 리포트와 데이터를 주입합니다."""
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()

    report_html = render_report_html(report_text)
    sentiment = json_data.get("sentiment", {})
    keywords = json_data.get("keywords", [])
    issues = json_data.get("issues", [])
    issue_count = json_data.get("issueCount", len(issues))

    pos = sentiment.get("positive", 0)
    neu = sentiment.get("neutral", 0)
    neg = sentiment.get("negative", 0)

    heat_label = {"hot": "🔴 HOT", "warm": "🟡 WARM", "cool": "⚪ COOL"}
    heat_class = {"hot": "heat-hot", "warm": "heat-warm", "cool": "heat-cool"}

    keywords_html = "\n".join([
        f'''<div class="keyword-item">
          <div class="keyword-rank">{i+1}</div>
          <div class="keyword-word">{k["word"]}</div>
          <div class="keyword-heat {heat_class.get(k["heat"], "heat-cool")}">{heat_label.get(k["heat"], k["heat"])}</div>
        </div>'''
        for i, k in enumerate(keywords)
    ])

    issues_html = "\n".join([
        f'''<div class="issue-card {iss.get("type","")}">
          <div class="issue-title">{iss["title"]}</div>
          <div class="issue-desc">{iss["desc"]}</div>
        </div>'''
        for iss in issues
    ])

    # ── HTML 내 자동 업데이트 영역 교체 ──────────────────────────
    # 1) 리포트 본문
    html = re.sub(
        r'(<!-- AUTO:REPORT_START -->)[\s\S]*?(<!-- AUTO:REPORT_END -->)',
        f'<!-- AUTO:REPORT_START -->\n{report_html}\n<!-- AUTO:REPORT_END -->',
        html
    )

    # 2) 감성 수치
    html = re.sub(r'(id="pctPos">)[^<]*(</span>)', f'\\g<1>{pos}%\\2', html)
    html = re.sub(r'(id="pctNeu">)[^<]*(</span>)', f'\\g<1>{neu}%\\2', html)
    html = re.sub(r'(id="pctNeg">)[^<]*(</span>)', f'\\g<1>{neg}%\\2', html)
    html = re.sub(r'(id="barPos"[^>]*style=")[^"]*(")', f'\\g<1>width:{pos}%\\2', html)
    html = re.sub(r'(id="barNeu"[^>]*style=")[^"]*(")', f'\\g<1>width:{neu}%\\2', html)
    html = re.sub(r'(id="barNeg"[^>]*style=")[^"]*(")', f'\\g<1>width:{neg}%\\2', html)

    # 3) 키워드 목록
    html = re.sub(
        r'(<!-- AUTO:KEYWORDS_START -->)[\s\S]*?(<!-- AUTO:KEYWORDS_END -->)',
        f'<!-- AUTO:KEYWORDS_START -->\n{keywords_html}\n<!-- AUTO:KEYWORDS_END -->',
        html
    )

    # 4) 이슈 목록
    html = re.sub(
        r'(<!-- AUTO:ISSUES_START -->)[\s\S]*?(<!-- AUTO:ISSUES_END -->)',
        f'<!-- AUTO:ISSUES_START -->\n{issues_html}\n<!-- AUTO:ISSUES_END -->',
        html
    )

    # 5) 마지막 업데이트 시각 & 이슈 카운트
    html = re.sub(r'(id="statLastRun">)[^<]*(</div>)', f'\\g<1>{TODAY_SHORT}\\2', html)
    html = re.sub(r'(id="statLastDate">)[^<]*(</div>)', f'\\g<1>자동 업데이트\\2', html)
    html = re.sub(r'(id="statIssues">)[^<]*(</div>)', f'\\g<1>{issue_count}\\2', html)
    html = re.sub(r'(id="reportTimestamp">)[^<]*(</div>)', f'\\g<1>{TODAY} 자동분석\\2', html)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"index.html 업데이트 완료!")


if __name__ == "__main__":
    full_text = search_and_analyze()
    report_text, json_data = parse_response(full_text)
    update_html(report_text, json_data)
    print("✅ 완료!")
