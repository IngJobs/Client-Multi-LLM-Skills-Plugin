# 자동 PR 생성 — 상세 실행 절차

`generate-pr-auto` 스킬이 따르는 자동 PR 생성의 **단계별 실행 절차**입니다. 현재 브랜치 기준으로 베이스 브랜치를 자동 추론하고, Jira MCP로 티켓 정보를 조회하여, 팀 규격 PR 제목/본문을 생성한 뒤 사용자 확인을 거쳐 **Draft PR** 을 생성하고, 마지막에 review open 여부를 물어 Ready 로 전환합니다. **work**(작업용 PR)와 **complete**(QA 완료 → release 합류 PR) 두 intent 를 같은 절차에서 분기 처리합니다.

> 브랜치 네이밍·베이스 추론 규칙·PR 제목/본문 포맷·라벨 매핑 등 **컨벤션 정의는 `SKILL.md`** 를 단일 출처로 참조합니다. 이 문서는 그 컨벤션을 적용하는 정확한 bash/MCP/gh 명령과 검증 로직만 정의합니다.

---

## 목차

- **워크플로우 (0~16단계)** — 0 도구 사전 준비 · 1 현재 브랜치 감지 · 1.5 intent 판별 · 2 베이스 브랜치 결정 · 3 Jira 티켓 키 추출 · 4 Jira 정보 조회 · 5 PR 타입 결정 · 6 Diff 분석(work) · 7 PR 제목 생성 · 8 PR 본문 생성 · 9 파일 저장(work) · 10 마일스톤 설정 질문(work·complete) · 11 사용자 확인 후 Draft PR 생성 · 12 ScreenShot 업로드 확인 후 표 컨버팅(work) · 13 코드리뷰 수행 후 인라인 코멘트 게시(work) · 14 review open 질문 후 Ready 전환 · 15 임시 파일 정리(work) · 16 ScreenShot 표 재구성(재실행·후속 요청용)
- **품질 기준**
- **주의사항**

---

## 워크플로우

### 0단계 — 도구 사전 준비 (필수, 최우선 수행)

워크플로우 진행 중 도구 호출 시점에 `InputValidationError` 또는 턴 조기 종료가 발생하지 않도록, **반드시 1단계 시작 전에** 사용할 도구들의 스키마 가용성을 확인합니다.

**확인 절차**

1. 시스템 리마인더(`<system-reminder>`)에서 deferred tools 목록을 확인
2. 다음 도구가 deferred 상태(이름만 있고 스키마 미로드)라면 `ToolSearch` 로 일괄 스키마 로드:
   - `AskUserQuestion` — 10·11·12·13·14단계 사용자 확인용
   - `mcp__jira__get-jira-issue` — 4단계 Jira 조회용
   - `mcp__github__create_pull_request` — 11단계 PR 생성용 (대안: Bash `gh pr create`)
   - `mcp__github__get_pull_request_files`·`mcp__github__create_pull_request_review` — 13단계 코드리뷰 인라인 코멘트 게시용 (work 한정, 사용자가 리뷰·게시를 승인한 경우에만 사용)
3. 이미 즉시 사용 가능한 도구는 다시 로드할 필요 없음

**일괄 로드 호출 예시**

```
ToolSearch(query="select:AskUserQuestion,mcp__jira__get-jira-issue,mcp__github__create_pull_request,mcp__github__get_pull_request_files,mcp__github__create_pull_request_review", max_results=10)
```

> 13단계 게시 도구(`get_pull_request_files`·`create_pull_request_review`)는 work intent 에서만, 그리고 사용자가 13단계에서 리뷰·게시를 승인한 시점에 로드해도 됩니다. complete intent 는 13단계가 없으므로 불필요합니다.

**원칙**

- 0단계를 건너뛰면 사용자 확인 단계(11단계)에서 `AskUserQuestion` 호출 직전에 턴이 종료되어 워크플로우가 멈출 수 있습니다
- ToolSearch 결과의 `<functions>` 블록에 스키마가 표시되면 로드 완료. 이후 1단계로 진행
- 로드 실패 시 사용자에게 알리고 Bash + `gh` CLI 대안 경로로 진행 가능

### 1단계 — 현재 브랜치 감지

```bash
git rev-parse --abbrev-ref HEAD
```

### 1.5단계 — intent 판별 (work / complete)

`SKILL.md` 의 **PR intent 판별 규칙** 을 적용해 `INTENT` 변수를 `work` 또는 `complete` 로 확정합니다.

- `/generate-pr-auto complete` 인자 또는 "complete PR"·"QA 완료"·"릴리즈에 머지" 의도 → `INTENT=complete`
- 현재 브랜치가 `feature/<티켓>/root` 인데 의도가 모호 → `AskUserQuestion` 으로 work/complete 확인
- 그 외 → `INTENT=work` (기존 동작)

> 이후 2·5·6·8·9·12·13·15단계가 `INTENT` 에 따라 분기합니다(6·9·12·13·15는 work 한정이라 complete 는 건너뜀). 나머지 단계(0·1·1.5·3·4·7·10·11·14)는 공통입니다.

### 2단계 — 베이스 브랜치 결정

**`INTENT=complete`**: 추론을 생략하고 base 를 **현재 활성 release**(`version.properties` 의 `version.name`) 로 고정합니다.

```bash
VERSION=$(grep '^version.name' app/config/version.properties | cut -d= -f2 | tr -d ' ')  # 예: 3.86.0
BASE_BRANCH="release/${VERSION}"
git rev-parse --verify "origin/${BASE_BRANCH}"   # 존재 확인. 없으면 AskUserQuestion 으로 확인
```

> 이후 complete 의 본문(`${VERSION}`)·base(`${BASE_BRANCH}`) 슬롯은 여기서 정의한 변수를 사용합니다.

**`INTENT=work`**: 아래 **베이스 브랜치 추론 (네이밍 컨벤션 기반)** 절차를 그대로 수행합니다.

#### 베이스 브랜치 추론 (네이밍 컨벤션 기반, work)

브랜치 파싱(`prefix / middle / suffix` 분해), 베이스 후보 1·2순위 규칙, release 브랜치 산출(`app/config/version.properties` 의 `version.name` → `release/<version.name>`), prefix 화이트리스트는 모두 `SKILL.md` 의 **브랜치 네이밍 컨벤션** · **베이스 브랜치 추론 규칙** 을 단일 출처로 따릅니다. 이 단계는 그 규칙을 적용하는 **실행 절차**만 정의합니다.

**"실제 분기된 베이스" 자동 감지 로직 (화이트리스트 우선)**

`refs/remotes/origin/` 전체가 아닌, **SKILL.md 의 베이스 추론 규칙 표로 산출한 후보 화이트리스트**와 실제 원격 ref의 교집합 안에서만 merge-base 거리를 비교합니다. 형제 작업 브랜치가 우연히 더 가까운 ancestor로 잡히는 오탐을 차단하기 위함.

```bash
# 1) SKILL.md 의 베이스 추론 규칙 표에 따른 후보 화이트리스트 산출 (origin/<ref> 형태)
#    - prefix=QA|qa                                : feature/{middle}/root
#    - prefix=feature|debt|bugfix, suffix=root|no-child : release/<version.name>
WHITELIST=(origin/release/<version.name> origin/feature/<middle>/root ...)

# 2) 실제 원격 ref 와 교집합 → 자기 자신/HEAD 제외
ACTUAL=$(git for-each-ref --format='%(refname:short)' refs/remotes/origin/)
CANDIDATES=$(comm -12 \
  <(printf '%s\n' "${WHITELIST[@]}" | sort -u) \
  <(printf '%s\n' "$ACTUAL"        | sort -u) \
  | grep -vx "origin/<current>")

# 3) 교집합이 비면 거리 비교 건너뛰고 AskUserQuestion 폴백
[ -z "$CANDIDATES" ] && askUserBaseBranch

# 4) 화이트리스트 내에서만 merge-base 거리 비교, 최소 거리 ref 선택
for c in $CANDIDATES; do
  dist=$(git rev-list --count "$(git merge-base "$c" HEAD)"..HEAD)
done
```

**검증/폴백**

- 후보 존재 확인: `git rev-parse --verify origin/<후보>` (없으면 로컬 ref 도 시도)
- 1순위 미존재/실패 시 → 2순위로 폴백
- 둘 다 실패 시 → `AskUserQuestion` 으로 사용자에게 베이스 브랜치를 직접 묻기
- 최종 검증: `git merge-base <후보> HEAD` 결과가 비어있지 않은지 확인
- 인자(arg1)로 사용자가 베이스를 명시한 경우 자동 추론을 건너뛰고 그 값을 사용

### 3단계 — Jira 티켓 키 추출

`SKILL.md` 의 **Jira 티켓 키 추출 규칙**(매칭 정규식, 브랜치 이름 → 최근 커밋 메시지 순, 다중 매칭 시 마지막 우선)을 적용합니다.

- SKILL.md 규칙으로도 추출에 실패하면 사용자에게 티켓 키를 직접 묻기

### 4단계 — Jira 정보 조회

```
mcp__jira__get-jira-issue(issueKey="<티켓키>")
```

- 응답에서 `summary` (티켓 제목), `description` (티켓 본문), `issuetype` 추출
- 호출 실패해도 워크플로우는 계속 진행 (graceful degrade)
  - 제목은 마지막 커밋 메시지 첫 줄로 대체
  - Abstract 는 "Jira 티켓 조회 실패 — 커밋 메시지 기반 작업 맥락" 으로 fallback

### 5단계 — PR 타입 결정 (제목 태그 / GitHub 라벨 정규화)

**`INTENT=complete`**: prefix 매핑을 거치지 않고 고정값을 사용합니다.

- `TITLE_TAG = Complete`
- **라벨 부착** — `TYPE_COMPLETE`를 넣고, 11단계에서 그 외 `--label` 인자를 넣지 않습니다.

이 경우 아래 work 정규화 절차를 건너뛰고 7단계로 진행합니다.

**`INTENT=work`**: `SKILL.md` 의 **prefix → 제목 태그 / GitHub 라벨 매핑 표** 를 적용하되, **반드시 변수화 단계를 거칩니다**. 이후 워크플로우(7·8·11단계)는 prefix 원본이 아니라 이 변수들만을 사용합니다.

**필수 정규화 절차 (work)**

브랜치 prefix를 위 매핑 표로 조회해 다음 두 변수에 저장:

- `TITLE_TAG`: SKILL.md 표의 **제목 태그(PascalCase)** 값 — PR 제목 `[...]` 안에 들어감
- `TYPE_LABEL`: SKILL.md 표의 **GitHub 라벨(`TYPE_*` 형식)** 값 — `gh pr create --label` 로 부착

> **원칙**: 7단계 제목·8단계 본문 라벨 언급에는 `TITLE_TAG`, 11단계 `--label` 인자에는 `TYPE_LABEL` 을 사용합니다. prefix 원본(`debt`, `qa` 등 소문자)이나 구표기(`Dept` 등)를 슬롯에 그대로 흘려보내는 것은 금지.

prefix 가 화이트리스트(`feature`/`Feature`/`qa`/`QA`/`debt`/`Debt`/`bugfix`/`Bugfix`)에 없으면 사용자에게 질문 (`Feature` / `QA` / `Debt` / `Bugfix` / 기타 직접 입력) 후 동일하게 `TITLE_TAG` / `TYPE_LABEL` 양쪽에 정규화된 값을 저장.

### 6단계 — Diff 분석 (work 한정)

> **`INTENT=complete`**: 본문이 한 줄로 고정되어 diff 결과를 전혀 사용하지 않으므로 **이 단계(6)를 통째로 건너뛰고 7단계로 진행**합니다. 아래 diff 명령·변경 파일 분류·원인 추론 절차는 모두 `INTENT=work` 에만 적용됩니다.

```bash
git diff --stat <base>...HEAD
git diff --name-status <base>...HEAD
git log --oneline <base>..HEAD
```

변경 파일은 `SKILL.md` 의 **변경 파일 분류 기준** 에 따라 아키텍처 계층별로 분류합니다.
변경 유형도 인식: 기능 추가, 버그 수정, 리팩토링, UI/UX 개선, 이벤트 처리, 리소스 추가 등.

**Bugfix / QA / Hotfix 의 추가 단계 — 변경 전 코드 기반 원인 추론**

`TITLE_TAG` 가 `Bugfix` / `QA` / `Hotfix` 인 경우 8단계 Abstract 의 "원인" 칸을 채우기 위해 아래를 수행합니다.

```bash
git diff <base>...HEAD -- <변경 파일>
```

- 출력의 `-` (변경 전) 라인을 우선 분석하여 "버그를 일으킨 코드의 형태/조건" 을 추정 (예: null 체크 누락, off-by-one, 잘못된 분기, 누락된 dispose 등)
- `+` (변경 후) 라인은 해결방법 칸의 단서로만 활용 (원인 ≠ 변경 후)
- Jira `description` 에 원인 정보가 있으면 우선 채택하고, diff 추정 결과와 모순되면 사용자에게 확인 질문
- Jira 에 원인 정보가 부족하면 추정한 내용을 `**원인** (diff 기반 추정): ...` 형태로 명시한 초안 작성
- **인과 사슬 매핑** (SKILL.md 의 권장 구조): `-` 라인 분석 결과 → **잠재 결함**, 결함이 만든 상태/데이터 전파 → **하류 영향**, Jira 재현 조건 → **트리거** 에 대응시켜 초안 작성. **diff·Jira 에서 확인되지 않는 단계는 만들어 채우지 말고 생략** (권장 구조이므로 3단계 강제 아님)

### 7단계 — PR 제목 생성 (변수 슬롯 주입)

`SKILL.md` 의 **PR 제목 포맷** 을 변수 슬롯 형태로 적용:

```
[${TITLE_TAG}][${TICKET_KEY}] ${JIRA_SUMMARY}
```

- `TITLE_TAG`: 5단계에서 정규화된 PascalCase 제목 태그 (`Feature`/`QA`/`Debt`/`Bugfix`)
- `TICKET_KEY`: 3단계에서 추출한 티켓 키
- `JIRA_SUMMARY`: 4단계 Jira 조회 결과의 `summary`

> prefix 원본을 슬롯에 직접 사용하지 말 것. 반드시 `TITLE_TAG` 변수를 경유.

Jira 제목 조회 실패 시 `JIRA_SUMMARY` 슬롯에 마지막 커밋 메시지 첫 줄을 대입합니다.

### 8단계 — PR 본문 생성

**`INTENT=complete`**: 4섹션 포맷을 쓰지 않고 **한 줄** 본문만 생성합니다. 아래 9단계(파일 저장)·자체 검증 체크리스트를 건너뛰고 10단계(마일스톤 설정 질문)로 진행합니다.

```
${TICKET_KEY} QA 완료 후 ${VERSION} 으로 머지하는 PR입니다
(티켓 없으면: QA 완료 후 ${VERSION} 으로 머지하는 PR입니다)
```

**`INTENT=work`**: `SKILL.md` 의 **PR 본문 4섹션 포맷**, **Branch 작성 규칙**, **Abstract 작성 규칙**, **"주요 변경사항" 작성 규칙**, **공통 작성 규칙** 을 **그대로** 적용합니다.

**Branch 섹션 슬롯 주입 (work)**

```
${CURRENT_BRANCH}
```

- `CURRENT_BRANCH`(1단계)에서 확정한 변수를 그대로 사용합니다
- **백틱 등 부호 없이 평문 한 줄**로 출력합니다 (코드 스팬 안에서는 Jira autolink 가 걸리지 않음 — SKILL.md **Branch 작성 규칙** 참조)

**Abstract 구조 적용 (work)**

- `TITLE_TAG` ∈ {`Bugfix`, `QA`, `Hotfix`} → SKILL.md 의 **Bugfix / QA / Hotfix 추가 규칙** 적용 (현상/원인/해결방법 필수)
- 그 외 (`Feature`/`Debt` 등) → SKILL.md 의 **Feature / Debt 권장 구조**(배경/목표/방식) 적용 — 배경 설명이 필요한 규모면 라벨 구조, 한두 문장으로 끝나는 단순 작업이면 단락 서술

**본문 작성 후 자체 검증 체크리스트** (work 한정, 작성 직후 9단계 파일 저장 전 반드시 수행):

1. **라벨 표기 일관성**: 본문에 라벨/prefix 언급이 있다면 모두 5단계 `TITLE_TAG` 값과 동일한 표기인지 확인. prefix 원본(`debt`, `qa`, `bugfix` 등)이나 구표기(`Dept`)가 본문에 남아있으면 `TITLE_TAG` 값으로 치환.
2. **카테고리 적합성**: `### <카테고리>` 항목이 SKILL.md 의 카테고리 정의(코드 변경 성격: UI/UX 개선, 핵심 기능 구현, 이벤트 처리, 리소스, 버그 수정, 리팩토링, 테스트 자원 추가 등)에 부합하는지 확인. **메타 정보(검증 항목, 정리 계획, 작업 일정 등)는 카테고리로 만들지 않고 Abstract 단락에 흡수**.
3. **Abstract 인용 점검**: Abstract 첫 문장이 Jira 티켓 제목(`summary`)을 거의 그대로 인용하지 않았는지 확인. 키워드 중복이 있으면 작업 의도/맥락 중심으로 표현 재작성.
4. **4섹션 외 섹션 부재**: Branch / Abstract / Description / ScreenShot 이외의 최상위 섹션(`# <name>`)이 추가되지 않았는지 확인. Branch 줄이 **head 브랜치명 평문 한 줄**인지(백틱·티켓 키·base 브랜치 미포함) 함께 점검.
5. **Bugfix/QA/Hotfix Abstract 3요소 점검** (`TITLE_TAG` ∈ {`Bugfix`, `QA`, `Hotfix`} 일 때만): Abstract 단락에 `**현상**` / `**원인**` / `**해결방법**` 세 bold 라벨이 모두 존재하는지 확인. 원인을 비워두지 않았는지, Jira 정보 부족 시 `**원인** (diff 기반 추정): ...` 형태로 명시했는지 점검. 추가로 (a) 인과 사슬 단계(잠재 결함/하류 영향/트리거)를 사용했다면 각 단계가 diff·Jira 근거 기반인지 — 확인되지 않은 단계를 만들어 채우지 않았는지, (b) 상위 라인(한 줄 요약·단계 본문)에 고유명사가 없고 코드 식별자/구체 값이 하위 들여쓰기 bullet 로 격리되었는지 점검.
6. **Feature/Debt Abstract 구조 점검** (`TITLE_TAG` ∈ {`Feature`, `Debt`} 이고 라벨 구조를 사용한 경우만): `**배경**` / `**목표**` / `**방식**` 라벨 사용, 각 라벨 뒤 빈 줄, `- 요약:` bullet 시작, 고유명사 하위 bullet 격리를 점검. 권장 구조이므로 미사용(짧은 단순 작업의 단락 서술)도 허용.

### 9단계 — 파일 저장 (work 한정)

> `INTENT=complete` 는 본문이 한 줄이므로 이 단계를 건너뛰고 `gh pr create --body` 로 직접 전달합니다.

프로젝트 루트에 다음 이름으로 저장(커밋 체인지에 등록 하지 않음):

```
PR_DESCRIPTION_<티켓키>.md
```

### 10단계 — 마일스톤 설정 질문 (work·complete 공통)

11단계 사용자 확인 **전에** 수행합니다. PR 에 GitHub 마일스톤을 부착할지 결정합니다.

**1. 설정 여부 질문 (`AskUserQuestion`)**

> "PR 에 마일스톤을 설정할까요?"
>
> - **예** — 레포의 열린 마일스톤 목록에서 선택
> - **아니오** — 마일스톤 없이 진행

**2-a. "예" 선택 시 — 열린 마일스톤 목록 조회 후 선택**

```bash
# 열린(open) 마일스톤 목록 조회 (마감일 오름차순)
gh api "repos/{owner}/{repo}/milestones?state=open&sort=due_on&direction=asc" --jq '.[].title'
```

- 조회된 마일스톤 title 들을 `AskUserQuestion` 옵션으로 제시해 하나를 선택받고 `MILESTONE` 변수에 기록합니다 (목록에 없는 값은 "기타"로 직접 입력 가능).
- **목록이 비어 있으면**(열린 마일스톤 없음) 그 사실을 안내하고 마일스톤 없이 진행합니다 — **마일스톤을 새로 만들지 않습니다**.
- 조회 실패(권한/네트워크) 시에도 그 사실을 안내하고 마일스톤 없이 진행합니다 (PR 생성 자체는 계속).

**2-b. "아니오" 선택 시**

`MILESTONE` 미설정 상태로 11단계로 진행합니다.

### 11단계 — 사용자 확인 후 Draft PR 생성

**필수**: 외부 시스템에 영향을 주는 액션이므로 반드시 `AskUserQuestion` 으로 사용자 확인을 받습니다.

질문 예시:
> "PR 정보가 준비되었습니다. 
> - 제목: `[QA][TB-9807] 게시글 상세 메시지 보내기 버튼 UI 개선`
> - 베이스: `feature/TB-6056/root`
> - 헤드: `QA/TB-6056/TB-9807`
> - 마일스톤: `3.88.0` (10단계에서 선택한 경우에만 표기)
>
> 세부 사항은 `PR_DESCRIPTION_<*>.md` 에서 확인 가능합니다.
> 
> 지금 Draft PR을 생성할까요?"

**승인 시 — work (항상 `--draft` + 기본 Assignee/Label)**:

```bash
gh pr create \
  --draft \
  --title "[${TITLE_TAG}][${TICKET_KEY}] ${JIRA_SUMMARY}" \
  --body-file PR_DESCRIPTION_${TICKET_KEY}.md \
  --base ${BASE_BRANCH} \
  --head ${CURRENT_BRANCH} \
  --assignee @me \
  --label "${TYPE_LABEL}" \
  --label "PRIORITY_LOW" \
  --label "RISK_HIGH(ApproveCount >= 2)"
```

**승인 시 — complete (한 줄 본문 직접 전달, `TYPE_COMPLETE` 라벨만, md 파일 없음)**:

티켓 유/무에 따라 제목·본문이 달라집니다(`${BASE_BRANCH}`·`${VERSION}` 은 2단계에서 정의).

```bash
# 티켓 있음
gh pr create \
  --draft \
  --title "[Complete][${TICKET_KEY}] ${JIRA_SUMMARY}" \
  --body "${TICKET_KEY} QA 완료 후 ${VERSION} 으로 머지하는 PR입니다" \
  --base "${BASE_BRANCH}" \
  --head ${CURRENT_BRANCH} \
  --assignee @me \
  --label "TYPE_COMPLETE"

# 티켓 없음 (제목 태그에서 티켓 제거, 본문 선행 ${TICKET_KEY} 제거)
gh pr create \
  --draft \
  --title "[Complete] ${JIRA_SUMMARY}" \
  --body "QA 완료 후 ${VERSION} 으로 머지하는 PR입니다" \
  --base "${BASE_BRANCH}" \
  --head ${CURRENT_BRANCH} \
  --assignee @me \
  --label "TYPE_COMPLETE"
```

> **complete 는 `--label "TYPE_COMPLETE"` 하나만 넣고 그 외(`PRIORITY_*`·`RISK_*`·`SkipUnitTest` 등) `--label` 인자는 넣지 않습니다.** 본문은 `--body-file` 대신 `--body` 로 한 줄을 직접 전달하며 `PR_DESCRIPTION_*.md` 파일을 만들지 않습니다.
>
> work 의 타입 라벨(`--label "${TYPE_LABEL}"`)은 5단계에서 결정한 `TYPE_대문자` 형식의 GitHub 라벨을 사용합니다(`TYPE_FEATURE`/`TYPE_QA`/`TYPE_DEBT`/`TYPE_BUGFIX`). 제목 태그(`TITLE_TAG`)와 GitHub 라벨(`TYPE_LABEL`)을 혼동하지 말 것.

**마일스톤 부착 (10단계에서 선택한 경우, work/complete 공통)**

- 10단계에서 `MILESTONE` 이 결정된 경우 위 work/complete `gh pr create` 명령에 `--milestone "${MILESTONE}"` 인자를 추가합니다. 미설정이면 인자 자체를 넣지 않습니다.
- MCP `mcp__github__create_pull_request` 는 마일스톤 인자를 지원하지 않으므로, 마일스톤 부착 시에는 Bash `gh pr create` 경로를 사용합니다.
- 마일스톤 부착 실패 시(미존재·권한 등) 해당 인자만 제외하고 PR 생성은 계속 진행하며 사용자에게 경고합니다 (라벨 누락 정책과 동일).

**기본 Assignee / Label 규칙**

기본 Assignee / Label 값과 override·라벨 누락 정책은 `SKILL.md` 의 **기본 적용 옵션** 을 단일 출처로 따릅니다. 위 `gh pr create` 명령의 `--assignee` / `--label` 인자가 그 기본값을 반영합니다.

- `RISK_HIGH(ApproveCount >= 2)` 등 공백·괄호가 포함된 라벨명은 `--label` 인자에 반드시 따옴표를 사용

**거부 시**: (work) 생성된 마크다운 파일 경로 안내 / (complete) 준비한 제목·본문·명령 안내 후 종료.

**`gh` CLI 미설치/미인증 시**: 에러 메시지 안내 후 종료. PR 자동 생성을 시도하지 않음.

### 12단계 — ScreenShot 업로드 확인 후 표 컨버팅 (work 한정)

Draft PR 생성 성공 직후, **13단계(코드리뷰) 전에** 수행합니다. `INTENT=complete` 는 이 단계가 없습니다.

**1. 업로드 확인 질문 (`AskUserQuestion`)**

프로젝트 루트의 untracked 미디어를 먼저 탐지해 질문에 함께 나열합니다:

```bash
# core.quotepath=false: 한글 파일명 이스케이프 방지 / "?$: 공백 포함 파일명의 따옴표 감싸기 대응
git -c core.quotepath=false status --porcelain | grep '^??' | grep -iE '\.(png|jpe?g|webp|gif|webm|mp4|mov)"?$'
```

질문 예시:

> "Draft PR이 생성되었습니다: <PR URL>
> PR 본문(웹)에 스크린샷 이미지 혹은 동영상을 업로드(드래그앤드롭)하시면 표로 컨버팅해 드립니다.
> (루트에서 감지된 미디어: Screen_recording_….webm, 스크린샷 ….png)
> 업로드 하셨나요?"
>
> - **예, 컨버팅해주세요** — 본문의 미디어 링크를 표로 재구성
> - **아니오** — 그대로 review open 질문으로 진행

**2-a. "예" 선택 시 — 표 컨버팅**

16단계의 절차(본문 파싱 → 표 생성 → 본문 재조립 → `gh pr edit`)를 수행합니다. 단, **이 답변을 적용 승인으로 간주**하므로 16단계 5번의 별도 적용 확인 질문은 생략합니다.

- 컨버팅 완료/실패와 무관하게 이어서 13단계(코드리뷰)로 진행
- 본문에서 미디어 링크를 찾지 못한 경우(업로드 미완료 등): "링크를 찾지 못했습니다 — 업로드 완료 후 'ScreenShot 표 정리해줘' 로 다시 요청 가능" 안내 후 13단계로 진행

**2-b. "아니오" 선택 시**

컨버팅 없이 13단계로 진행합니다. 14단계 종료 안내에 "나중에 업로드한 뒤 'ScreenShot 표 정리해줘' 라고 요청하면 표로 재구성됩니다(16단계)" 한 줄을 포함합니다.

### 13단계 — 코드리뷰 수행 후 인라인 코멘트 게시 (work 한정)

Draft PR 생성(필요 시 12단계 ScreenShot 컨버팅) 직후, **14단계(review open 질문) 전에** 수행합니다. `INTENT=complete` 는 이 단계가 없습니다. 11단계에서 확보한 PR 번호/URL 을 사용합니다.

이 단계의 게시는 **외부 시스템 쓰기**이므로, 아래 **두 번의 `AskUserQuestion` 승인**(리뷰 수행 여부 + 게시 직전 확인) 없이는 절대 게시하지 않습니다.

**1. 리뷰 수행 여부 질문 (`AskUserQuestion`)**

> "Draft PR이 생성되었습니다: <PR URL>
> 지금 코드리뷰를 수행하고 결과를 PR 인라인 코멘트로 달아 드릴까요?"
>
> - **예, 리뷰해주세요** — `review-pr` 실행 후 게시 절차로 진행
> - **아니오** — 코드리뷰 없이 14단계(review open 질문)로 진행

"아니오" 선택 시 곧바로 14단계로 진행합니다.

**2. `review-pr` 실행 (read-only 리포트 생성)**

`Skill` 도구로 `review-pr` 을 PR 번호와 함께 호출합니다:

```
Skill(skill="review-pr", args="<PR번호>")
```

- 산출물은 **로컬 리포트 `pr_<PR번호>_code_review.md` 하나뿐**입니다(`../review-pr/SKILL.md` 의 "외부 변경 금지" 원칙). `review-pr` 은 어떤 경우에도 GitHub 에 게시하지 않습니다.
- 게시 책임은 본 스킬(`generate-pr-auto`)에만 있습니다. 아래 3~4번에서 이 리포트를 읽어 게시합니다.
- `review-pr` 실행이 실패하거나 리포트가 생성되지 않으면: 사유를 안내하고 게시 없이 14단계로 진행합니다.

**3. 리포트 미리보기 + 게시 확인 질문 (`AskUserQuestion`)**

생성된 `pr_<PR번호>_code_review.md` 를 읽어 **종합 점수·관점별 점수표·주요 finding 개수(P0/P1)** 를 요약해 보여준 뒤 게시 여부를 확인합니다:

> "코드리뷰가 완료되었습니다 (종합 X.X/10, P0 a건 · P1 b건).
> 이 리뷰 결과를 PR 인라인 코멘트로 게시할까요?"
>
> - **예, 게시해주세요** — 4번으로 진행
> - **아니오** — 로컬 리포트 경로(`pr_<PR번호>_code_review.md`)만 안내하고 14단계로 진행

**4. 리포트 → 인라인 코멘트 변환 후 게시 ("예" 선택 시)**

**4-1. PR 메타·변경 라인 확보**

```bash
# owner/repo 확보 (PR 번호는 11단계에서 이미 확보)
gh repo view --json owner,name
```

```
# 변경 파일과 patch(diff hunk) 목록 확보 — 인라인 가능 라인 판정용
mcp__github__get_pull_request_files(owner=<owner>, repo=<repo>, pullNumber=<PR번호>)
```

**4-2. finding 파싱·매핑**

리포트의 각 finding 4부 구조에서 `**위치**: \`<파일경로:라인>\`` 과 `[P0]/[P1]/[P2] <제목>` 을 파싱합니다(포맷은 `../review-pr/SKILL.md` 의 finding 구조가 단일 출처).

- **인라인 가능** (해당 `파일경로` 가 변경 파일이고 `라인` 이 그 파일 diff hunk 에 포함됨) → `comments[]` 에 누적:
  - `{path: "<파일경로>", line: <라인>, body: "[P0] <제목>\n\n<문제 요약>\n\n<해결방법 요약>\n\n---\n_Generated by Claude's code review skill_"}`
  - `body` 는 한국어 유지, 코드 스니펫은 영어. 리포트 본문에서 핵심만 발췌(전체 4부 구조를 그대로 붙이지 말 것).
  - 각 인라인 코멘트 말미에는 AI 생성 출처 푸터 `\n\n---\n_Generated by Claude's code review skill_` 를 반드시 붙입니다(게시 작성자가 사람 계정으로 표시되므로 출처를 명시).
- **인라인 불가** (라인이 diff 밖이거나 파일:라인 파싱 실패) → 리뷰 `body`(요약 코멘트)의 "인라인 불가 항목" 목록으로 모읍니다.

**4-3. 단일 호출로 게시**

```
mcp__github__create_pull_request_review(
  owner=<owner>,
  repo=<repo>,
  pull_number=<PR번호>,
  event="COMMENT",            # ← 고정. APPROVE/REQUEST_CHANGES 금지(PR 상태 변경 안 함)
  body="<종합 점수·관점별 점수표 요약 + 인라인 불가 항목 목록>\n\n---\n_Generated by Claude's code review skill_",
  comments=[ /* 4-2 에서 누적한 {path, line, body} 배열 */ ]
)
```

- **`event="COMMENT"` 를 반드시 사용**합니다. `APPROVE`/`REQUEST_CHANGES` 는 PR 상태를 바꾸므로 절대 사용하지 않습니다(`review-pr` 의 "상태 변경 금지" 철학 계승).
- 게시 성공 시: **게시된 인라인 코멘트 수 + 요약에 포함된 인라인 불가 수 + PR URL** 을 안내합니다.

**4-4. 실패 처리**

- `create_pull_request_review` 가 실패(라인 매핑 오류·권한 등)하면, 폴백으로 전체 리포트를 일반 코멘트 1건으로 게시할지 제안합니다:

```bash
gh pr comment <PR번호> --body-file pr_<PR번호>_code_review.md
```

- 폴백도 거부/실패하면 로컬 리포트 경로만 안내합니다.
- 게시 성공·실패·폴백과 무관하게 **이어서 14단계(review open 질문)로 진행**합니다.

### 14단계 — review open 여부 질문 후 Ready 전환 (work / complete 공통)

Draft PR 생성에 성공한 직후 수행합니다. `gh pr create` 가 출력한 PR URL/번호를 확보해 둡니다.

**`AskUserQuestion` 질문 예시**

> "Draft PR이 생성되었습니다: <PR URL>
> 지금 review 를 open(Ready for review) 할까요?"
>
> - **지금 open** — Draft 를 해제하고 리뷰어 알림을 보냄
> - **Draft 유지** — 그대로 두고 종료 (나중에 직접 open)

**"지금 open" 선택 시**:

```bash
gh pr ready <PR번호>     # 또는 gh pr ready <PR URL>
```

- 안전을 위해 생성 결과의 PR 번호/URL 을 명시해 호출합니다.
- 전환 성공 후 "review open 완료" 와 PR URL 을 안내.

**"Draft 유지" 선택 시**: Draft 상태 PR URL 만 안내하고 종료.

**`gh pr ready` 실패 시**: 에러 메시지와 함께 "PR 은 Draft 로 생성되어 있으니 GitHub 에서 직접 Ready 전환 가능" 안내.

### 15단계 — 임시 파일 정리 (work 한정)

> `INTENT=complete` 는 임시 파일을 만들지 않으므로 이 단계가 없습니다.

`PR_DESCRIPTION_${TICKET_KEY}.md` 가 PR 본문에 정상 반영된 후 삭제합니다.

- 삭제 직전 사용자에게 안내 (또는 유지 옵션 제공)
- PR 생성에 실패한 경우 삭제하지 않고 보존

### 16단계 — ScreenShot 표 재구성 (재실행·후속 요청용, work PR 한정)

**12단계에서 수행하는 표 컨버팅의 단독 실행 버전**입니다. 12단계에서 "아니오" 를 선택한 뒤 늦게 업로드했거나, 업로드 미완료 재시도, 추가 미디어를 기존 표에 병합할 때 **"ScreenShot 표 정리해줘" 류 요청만으로 단독 수행**합니다 (0~15단계 선행 불필요). 미디어 링크 인식 패턴(4종)·표 변환 규칙은 `SKILL.md` 의 **ScreenShot 작성 규칙 (표 변환)** 을 단일 출처로 따릅니다.

전제: 게시자가 PR 본문(웹)에 미디어 파일을 드래그앤드롭해 두어, 본문에 `[파일명](https://github.com/user-attachments/assets/<uuid>)` 류 링크가 존재하는 상태.

**1. 대상 PR 식별**

사용자가 PR 번호/URL 을 제공하면 그 값을, 없으면 현재 브랜치의 PR 을 사용합니다:

```bash
gh pr view --json number,url,body          # 현재 브랜치 PR
gh pr view <PR번호|URL> --json number,url,body
```

- PR 미존재 시: "현재 브랜치에 연결된 PR 이 없습니다" 안내 후 종료

**2. 본문 파싱 (미디어 링크 수집)**

- `# ScreenShot(Optional)` 섹션 **안팎의 모든 미디어 링크**(SKILL.md 인식 패턴 4종)를 수집합니다 — 드래그앤드롭 위치가 다른 섹션이어도 수거
- **이미 ScreenShot 표 셀(`<img>`/`<video>`)에 들어 있는 URL 은 수집에서 제외**합니다 (재실행 멱등성 — 같은 요청을 반복해도 표가 중복 생성되지 않아야 함)
- 파일명을 알 수 없는 bare URL 은 `AskUserQuestion` 으로 파일명과 이미지/비디오 여부를 확인
- 수집 0건이면: "본문에서 미디어 링크를 찾지 못했습니다. PR 본문에 드래그앤드롭으로 올린 뒤 다시 요청해주세요" 안내 후 종료

**3. 표 생성**

SKILL.md **표 변환 규칙** 을 적용합니다. ScreenShot 섹션에 기존 표가 있으면 **기존 열 + 신규 미디어를 병합한 단일 표**로 갱신합니다.

**4. 본문 재조립**

- 재조립의 기반은 **직전에 읽은 최신 본문** — `SKILL.md` 의 **PR 본문 수정 공통 원칙** 준수 (과거 생성본·로컬 사본 재사용 금지)
- ScreenShot 섹션 내용을 표로 교체 (placeholder `_게시자 직접 등록_` 제거)
- 수거한 원본 링크 라인(`[파일명](url)`·`<img ...>` 등)은 본문에서 제거
- **다른 섹션(Branch / Abstract / Description)은 한 글자도 변경하지 않고 그대로 보존**

**5. 사용자 확인 후 적용**

변경될 ScreenShot 섹션 미리보기를 보여주고 `AskUserQuestion` 으로 확인을 받습니다 (외부 시스템에 영향을 주는 액션). 승인 시 **본문을 다시 읽어 재조립한 뒤** 적용합니다 (읽기-수정 사이에 웹에서 본문이 바뀌었을 경우의 변경 유실 방지):

```bash
gh pr view <PR번호> --json body            # 승인 직후 재읽기
# 재조립 결과를 임시 파일로 저장 후:
gh pr edit <PR번호> --body-file PR_BODY_<PR번호>.md
```

**6. 마무리**

- 완료 후 PR URL 안내
- 임시 본문 파일(`PR_BODY_<PR번호>.md`)은 반영 확인 후 삭제 (적용 실패 시 보존)

**폴백/예외**

- `gh pr edit` 실패(권한/네트워크): 재조립 본문 파일 경로를 안내하고 GitHub 웹에서 수동 붙여넣기 안내 (파일 보존)
- complete intent PR(한 줄 본문)·Sync PR 본문: 표 재구성 대상이 아님 — 요청 시 그 사실을 안내

---

## 품질 기준

- 모든 변경 파일이 올바른 계층에 분류되었는지 확인
- 커밋 메시지와 코드 변경이 일치하는지 검증
- (work) PR 본문 4섹션 최상위 구조(Branch / Abstract / Description / ScreenShot)는 항상 유지
- (work) Optional 섹션(ScreenShot)이 비어 있을 경우 `SKILL.md` 의 placeholder(`_게시자 직접 등록_`)를 그대로 유지 — 미디어 미첨부 시에만 해당하며, 16단계 표 재구성 시에는 `SKILL.md` 의 **ScreenShot 작성 규칙 (표 변환)** 을 준수
- (12·16단계) 표 재구성은 ScreenShot 섹션과 수거한 미디어 링크 라인만 변경 — **다른 섹션(Branch / Abstract / Description)은 무변경**, 재실행 시 표 중복 생성 금지(멱등성), 재조립은 직전에 읽은 실제 본문 기반(`SKILL.md` 공통 원칙)
- (complete) 본문은 한 줄 머지 사유만. 4섹션 포맷·`PR_DESCRIPTION_*.md` 파일 생성 금지(`--body` 직접 전달)
- (complete) **`TYPE_COMPLETE` 하나만 부착** — `gh pr create` 에 `--label "TYPE_COMPLETE"` 만 넣고 그 외 라벨은 넣지 않음
- (work·complete) 마일스톤은 10단계에서 사용자가 설정을 선택한 경우에만 부착 — 레포의 **열린 마일스톤 목록에서 선택**하며, 없는 마일스톤을 새로 만들지 않음
- 항상 Draft PR로 생성 (`--draft` 플래그 누락 금지) 후, review open 여부를 별도 `AskUserQuestion` 으로 물어 `gh pr ready` 로만 Draft 해제
- (work) 기본 Assignee(`@me`) / Label(타입 `TYPE_*`, `PRIORITY_LOW`, `RISK_HIGH(ApproveCount >= 2)`) 항상 포함 (사용자 override 시 제외). complete 는 Assignee(`@me`) + `TYPE_COMPLETE` 라벨만 부착

## 주의사항

- **PR 본문을 수정하는 모든 작업(전면 업데이트·부분 수정·12/16단계 일체)은 `SKILL.md` 의 "PR 본문 수정 공통 원칙" 을 따를 것**
- 본문 유실 사고 시 GitHub GraphQL `PullRequest.userContentEdits` (본문 편집 이력)로 이전 버전 복구 가능
- **0단계(도구 사전 준비) 누락 금지** — 1단계 시작 전 반드시 deferred 도구 스키마 로드 확인
- `gh pr create` 실행 전 사용자 확인 필수, **생성은 항상 `--draft`** — review open 은 생성 후 별도 질문으로만 진행
- `gh pr ready` 는 사용자가 "지금 open" 을 선택한 경우에만 실행 (자동 open 금지)
- Jira 조회 실패 시에도 워크플로우는 멈추지 않고 fallback 으로 진행
- (work) prefix 가 화이트리스트(`feature`/`Feature`/`qa`/`QA`/`debt`/`Debt`/`bugfix`/`Bugfix`)에 없으면 사용자에게 PR 타입을 묻기
- 인자로 베이스가 명시되면 자동 추론을 건너뛸 것
- complete intent 의 base 는 `release/<version.name>` 고정 (merge-base 추론 생략)
