"""
포트나이트 커뮤니티 동향 자동 수집 & 대시보드 HTML 업데이트 스크립트
매일 GitHub Actions에서 실행됩니다.
"""

import anthropic
import json
import re
import os
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
TODAY = datetime.now(KST).strftime("%Y년 %m월 %d일")
TODAY_SHORT = datetime.now(KST).strftime("%Y.%m.%d")

SEARCH_QUERIES = [
    "포트나이트 커뮤니티 반응 최신",
    "포트나이트 에픽게임즈 뉴스 오늘",
    "포트나이트 구글플레이 유저 반응",
]

ANALYSIS_PROMPT = f"""당신은 포트나이트 게임 커뮤니티 동향 분석 전문가입니다.
모든 내용을 반드시 한국어로만 작성하세요. 영어 문장을 절대 사용하지 마세요.

오늘 날짜: {TODAY}
위에서 웹 검색한 최신 정보를 바탕으로, 오늘 날짜 기준 가장 새로운 이슈와 반응을 중심으로 리포트를 작성하세요.
각 섹션은 3~4문장 이내로 간결하게 작성하세요.

[배경 정보]
- 3/19 구글플레이 복귀(5년7개월만) - 챕터7 시즌2 쇼다운, 진영선택(파운데이션vs얼음왕)
- 구글-에픽 합의: 수수료 30%->20%, 에픽 2032년까지 구글 공개비난 자제
- 브이벅스 가격 인상 / 4월 세이브더월드 무료화 / 4/9 아레나 모드
- 3/24 에픽 직원 1,000명(전체 20%) 해고
- 모드 3종 종료: 발리스틱/페스티벌배틀스테이지(4/16), 로켓레이싱(10월)
- DC/에펨코리아는 크롤링 차단으로 직접수집 불가

다음 형식으로 한국어로만 작성하세요:

### 오늘의 핵심 동향
### 채널별 반응 요약
### 트렌드 분석
### 리스크 와 기회 요소
### 내일 주목할 점

리포트 작성 후 아래 형식으로 JSON을 출력하세요.
JSONSTART 와 JSONEND 사이에 JSON만 넣으세요.
키워드와 이슈 제목/설명도 반드시 한국어로 작성하세요:

JSONSTART
{"sentiment":{"positive":40,"neutral":30,"negative":30},"keywords":[{"word":"한국어키워드1","heat":"hot"},{"word":"한국어키워드2","heat":"hot"},{"word":"한국어키워드3","heat":"warm"},{"word":"한국어키워드4","heat":"warm"},{"word":"한국어키워드5","heat":"cool"}],"issues":[{"type":"neg","title":"한국어제목","desc":"한국어설명"},{"type":"warn","title":"한국어제목","desc":"한국어설명"},{"type":"pos","title":"한국어제목","desc":"한국어설명"}],"issueCount":3}
JSONEND"""


def search_and_analyze():
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    print(f"[{TODAY}] 검색 및 분석 시작...")

    search_context = "\n".join([f"- {q}" for q in SEARCH_QUERIES])
    full_prompt = f"다음 주제들에 대해 최신 정보를 검색하고 분석해주세요:\n{search_context}\n\n{ANALYSIS_PROMPT}"

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": full_prompt}]
    )

    full_text = "\n".join(
        block.text for block in response.content
        if hasattr(block, "text")
    )

    print(f"응답 수신 완료 ({len(full_text)} chars)")
    return full_text


def parse_response(full_text):
    json_data = None
    report_text = full_text

    match = re.search(r'JSONSTART\s*([\s\S]*?)\s*JSONEND', full_text)
    if not match:
        match = re.search(r'<<<JSON>>>\s*([\s\S]*?)\s*<<<ENDJSON>>>', full_text)
    if not match:
        match = re.search(r'(\{"sentiment"[\s\S]*?\})\s*$', full_text)

    if match:
        try:
            raw = match.group(1).strip()
            json_data = json.loads(raw)
            report_text = full_text[:match.start()].strip()
            report_text = re.sub(r'\n---\s*$', '', report_text).strip()
            print("JSON 파싱 성공")
        except json.JSONDecodeError as e:
            print(f"JSON 파싱 실패: {e}")
            report_text = full_text[:match.start()].strip()

    if not json_data:
        print("JSON 없음 - 기본값 사용")
        json_data = {
            "sentiment": {"positive": 35, "neutral": 30, "negative": 35},
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
    html = '<div class="rpt">'
    lines = report_text.split('\n')
    in_list = False

    for line in lines:
        line = line.strip()
        if not line or line == '---':
            if in_list:
                html += '</ul>'
                in_list = False
            continue

        if line.startswith('### '):
            if in_list:
                html += '</ul>'
                in_list = False
            html += f'<h3>{line[4:]}</h3>'
        elif line.startswith('- ') or line.startswith('* '):
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

    heat_label = {"hot": "HOT", "warm": "WARM", "cool": "COOL"}
    heat_class = {"hot": "heat-hot", "warm": "heat-warm", "cool": "heat-cool"}

    keywords_html = "\n".join([
        f'<div class="keyword-item"><div class="keyword-rank">{i+1}</div>'
        f'<div class="keyword-word">{k["word"]}</div>'
        f'<div class="keyword-heat {heat_class.get(k["heat"], "heat-cool")}">'
        f'{heat_label.get(k["heat"], k["heat"])}</div></div>'
        for i, k in enumerate(keywords)
    ])

    issues_html = "\n".join([
        f'<div class="issue-card {iss.get("type","")}">'
        f'<div class="issue-title">{iss["title"]}</div>'
        f'<div class="issue-desc">{iss["desc"]}</div></div>'
        for iss in issues
    ])

    html = re.sub(
        r'<!-- AUTO:REPORT_START -->[\s\S]*?<!-- AUTO:REPORT_END -->',
        f'<!-- AUTO:REPORT_START -->\n{report_html}\n<!-- AUTO:REPORT_END -->',
        html
    )
    html = re.sub(r'(id="pctPos">)[^<]*(</span>)', f'\\g<1>{pos}%\\2', html)
    html = re.sub(r'(id="pctNeu">)[^<]*(</span>)', f'\\g<1>{neu}%\\2', html)
    html = re.sub(r'(id="pctNeg">)[^<]*(</span>)', f'\\g<1>{neg}%\\2', html)
    html = re.sub(r'(id="barPos"[^>]*style=")[^"]*(")', f'\\g<1>width:{pos}%\\2', html)
    html = re.sub(r'(id="barNeu"[^>]*style=")[^"]*(")', f'\\g<1>width:{neu}%\\2', html)
    html = re.sub(r'(id="barNeg"[^>]*style=")[^"]*(")', f'\\g<1>width:{neg}%\\2', html)
    html = re.sub(
        r'<!-- AUTO:KEYWORDS_START -->[\s\S]*?<!-- AUTO:KEYWORDS_END -->',
        f'<!-- AUTO:KEYWORDS_START -->\n{keywords_html}\n<!-- AUTO:KEYWORDS_END -->',
        html
    )
    html = re.sub(
        r'<!-- AUTO:ISSUES_START -->[\s\S]*?<!-- AUTO:ISSUES_END -->',
        f'<!-- AUTO:ISSUES_START -->\n{issues_html}\n<!-- AUTO:ISSUES_END -->',
        html
    )
    html = re.sub(r'(id="statLastRun">)[^<]*(</div>)', f'\\g<1>{TODAY_SHORT}\\2', html)
    html = re.sub(r'(id="statLastDate">)[^<]*(</div>)', f'\\g<1>자동 업데이트\\2', html)
    html = re.sub(r'(id="statIssues">)[^<]*(</div>)', f'\\g<1>{issue_count}\\2', html)
    html = re.sub(r'(id="reportTimestamp">)[^<]*(</div>)', f'\\g<1>{TODAY} 자동분석\\2', html)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"완료! ({TODAY_SHORT})")


if __name__ == "__main__":
    full_text = search_and_analyze()
    report_text, json_data = parse_response(full_text)
    update_html(report_text, json_data)
