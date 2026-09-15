# 작업 시작 (start-work) — 상세 실행 절차

`start-work` 스킬이 따르는 **단계별 실행 절차**입니다. Jira 티켓 하나로 티켓 정보·버전을 조회하고, 브랜치 타입을 사용자에게 질문한 뒤, 사용자 최종 확인을 거쳐 **Jira 필드(Start Date·수정 버전·In Progress)** 를 반영하고 **Git 브랜치를 생성·push** 합니다.

> 브랜치 네이밍·버전 컨벤션·티켓 키 추출 규칙 등 **컨벤션 정의는 `SKILL.md`**(및 generate-pr-auto SKILL.md)를 단일 출처로 참조합니다. 이 문서는 그 컨벤션을 적용하는 정확한 bash/MCP 명령과 검증 로직만 정의합니다.

> MCP 호출 예시는 [실행 환경 지침](execution-environment.md)에 따라 실제 연결의 스키마로 대응합니다.

---

## 목차

- **워크플로우 (0~10단계)** — 0 도구 사전 준비 · 1 티켓 키 확정 · 2 티켓 정보 조회 · 3 버전 조회 · 4 브랜치 타입 질문 · 5 브랜치명·베이스 산출 · 6 Jira 세팅 값 산출 · 7 최종 확인 · 8 Jira 반영 · 9 브랜치 생성·push · 10 티켓 본문 기반 작업 시작 제안
- **품질 기준**
- **주의사항**

---

## 워크플로우

### 0단계 — 도구 사전 준비

[실행 환경 지침](execution-environment.md)에 따라 사용자 질문, 파일 읽기·Git 실행, Jira 이슈/현재 사용자 조회·필드 수정·전이 조회/실행 기능의 가용성을 확인합니다. 지금 필요한 기능만 준비하며, 선택적 단계의 도구는 그 단계를 선택했을 때 확인합니다.

### 1단계 — 티켓 키 확정

- 인자(`start-work CT-5208`) → 발화에서 정규식 `[A-Z]{2,}-\d+` 로 추출 (다중 매칭 시 마지막 우선, generate-pr-auto **티켓 키 추출 규칙** 과 동일)
- 추출 실패 시 사용자 질문(또는 직접 질문)으로 티켓 키 입력받기
- 추출/입력값을 **반드시 사용자에게 확인** — Jira·Git 양쪽을 변경하므로 잘못된 키로 진행 방지

### 2단계 — 티켓 정보 조회

```
getJiraIssue(cloudId="teamblind.atlassian.net", issueIdOrKey="<티켓키>",
  fields=["summary","issuetype","status","assignee","parent"], responseContentFormat="markdown")
```

- `summary`(티켓 제목)·`issuetype`·`status`(현재 상태)·`assignee`(현재 담당자)·`parent`(부모 티켓, subtask 일 때) 추출
- `issuetype.subtask == true` 또는 `parent` 가 있으면 4단계에서 **부모 기반 베이스 추천** 에 사용 (`parent.key` = 부모 티켓 키)
- 조회 실패 시: 티켓 키/권한 확인을 사용자에게 안내하고 중단 (start-work 는 Jira 변경이 핵심이므로 graceful degrade 하지 않음)
- 현재 `status` 가 이미 **In Progress(개발)** 면 8단계 상태 전이를 건너뛸 대상으로 기록 (멱등성)
- `assignee` 가 `null` 이면 6단계에서 본인 할당 대상으로, 이미 할당돼 있으면 담당자 변경을 건너뛸 대상으로 기록 (멱등성)

### 3단계 — 버전 조회

안드로이드 앱 레포 루트에서 `version.name` 을 읽습니다.

```bash
VERSION=$(grep '^version.name' app/config/version.properties | cut -d= -f2 | tr -d ' ')   # 예: 3.88.0
```

- 파일/키 미발견 시 사용자에게 버전을 직접 확인 (release 베이스·수정 버전 산출에 필수)

### 4단계 — 브랜치 타입 질문 (사용자 질문, 항상 수행)

자동 추론하지 않고 **항상** 다음을 질문합니다 (호스트가 허용하면 질문을 묶되 실제 질문 수·선택지 제한을 따름):

1. **prefix**: `feature` / `debt` / `QA` / `bugfix` / `hotfix`
2. **작업 유형**: `no-child(단독 작업)` / `하위 작업`

`하위 작업` 선택 시 **베이스 브랜치를 추가로 입력**받습니다. (예: `feature/TB-6056/root`)

- 베이스 입력값은 실재 여부를 검증(5단계)하며, 부모 티켓을 여기서 추출합니다.

**부모 기반 베이스 추천 (Jira subtask일 때)** — `SKILL.md` 의 **Jira 부모 기반 베이스 추천(subtask)** 규칙 적용:

- 2단계에서 `issuetype.subtask == true` 또는 `parent` 가 있으면, 베이스 입력 질문의 사용자 질문 **옵션에 부모 기반 추천 후보를 포함**합니다:
  - 추천 베이스: `<prefix>/${PARENT_KEY}/root` (`PARENT_KEY` = `parent.key`)
  - 옵션 설명에 **결과 브랜치 `<prefix>/${PARENT_KEY}/<티켓키>`** 를 함께 표기
- **원격에 root 가 없어도 추천 후보로 노출**하되, 옵션 설명에 원격 존재 여부(`git ls-remote --heads origin <후보>`)를 표시하고 "미존재 시 선택하면 5단계에서 중단됨"을 명시 — **추천이 존재 검증을 우회하지 않음**
- 함께 제시할 다른 후보(선택): 현재 체크아웃 브랜치가 `*/root` 면 후보로 추가. 그 외는 "기타"(자동 제공)로 직접 입력
- `prefix` 와 추천을 함께 보여주려면, prefix 질문을 먼저 받아 확정한 뒤 베이스 질문에서 추천을 구성합니다 (prefix 가 추천 베이스/결과 브랜치에 들어가므로)
- Jira `parent` 가 없으면 추천 생략, 베이스 직접 입력

### 5단계 — 브랜치명·베이스 산출

`SKILL.md` 의 **브랜치 네이밍 규칙** 을 적용합니다.

**no-child (단독)**

```
BRANCH="<prefix>/<티켓키>/no-child"
BASE_BRANCH="release/${VERSION}"
```

**하위 작업**

```
BASE_BRANCH="<사용자 입력 베이스>"
PARENT_TICKET=$(echo "$BASE_BRANCH" | cut -d/ -f2 | grep -oE '[A-Z]{2,}-[0-9]+')   # 베이스의 middle 세그먼트에서 부모 티켓 추출
BRANCH="<prefix>/${PARENT_TICKET}/<티켓키>"
```

> 부모 티켓은 베이스 브랜치의 **구조적 위치(`<prefix>/<부모티켓>/...` 의 middle 세그먼트)** 에서 추출합니다. 자유 텍스트에서 키를 뽑는 generate-pr-auto 의 "다중 매칭 시 마지막 우선" 규칙과는 별개입니다 (베이스명에 다른 티켓 키가 섞여 있어도 middle 세그먼트가 부모).

**베이스 존재 검증** (remote 우선):

```bash
git fetch origin
git rev-parse --verify "origin/${BASE_BRANCH}" 2>/dev/null \
  || git rev-parse --verify "${BASE_BRANCH}" 2>/dev/null   # 원격에 없으면 로컬도 확인
```

**하위 작업 — 입력 베이스가 미존재할 때 (원격·로컬 모두 없음)**: 베이스 형태에 따라 분기합니다.

- **베이스가 부모 root 형태(`<prefix>/<부모티켓>/root`, suffix == `root`)면 → root 생성 플로우 제안 (즉시 중단 아님)**:
  - 사용자 질문으로 **어떤 release 브랜치에서 root 를 생성할지** 묻습니다. 후보 = `release/${VERSION}`(기본) + 최근 `release/*` 브랜치 몇 개 + "생성 안 함(중단)". (목록에 없으면 "기타"로 직접 입력)

    ```bash
    # release 후보 나열 (최근 갱신 순 상위 몇 개)
    git for-each-ref --sort=-committerdate --count=8 --format='%(refname:short)' 'refs/remotes/origin/release/*' | sed 's#origin/##'
    ```

  - release 선택 시: **실제 생성은 9단계**에서 수행하도록 결정만 기록합니다 — `CREATE_ROOT=true`, `ROOT_NAME=<BASE_BRANCH>`, `ROOT_FROM=release/<선택값>`. 이후 `BASE_BRANCH` 는 "생성될 root" 로 간주하고 정상 진행 (6·7단계로).
  - **"생성 안 함" 선택 시 → 즉시 중단(abort)** (아래 일반 중단과 동일 메시지).
- **그 외(부모 root 형태가 아닌 임의 베이스)가 미존재면 → 즉시 중단(abort)**: 임의 브랜치는 자동 생성하지 않습니다. **이후 단계(Jira 변경·브랜치 생성)를 일절 수행하지 않고** 다음 메시지로 안내:
  > "베이스 브랜치 `<BASE_BRANCH>` 가 존재하지 않습니다. 베이스 브랜치를 확인해 주세요."
  - 이 시점은 아직 어떤 Jira·Git 변경도 일어나기 전(6~9단계 이전)이므로, 중단해도 부작용이 남지 않습니다.
  - 재시도하려면 올바른 베이스로 `start-work` 를 다시 호출하도록 안내 (자동으로 다른 베이스를 추정하지 않음).
- **no-child** 의 `origin/release/${VERSION}` 미존재 시: 버전/릴리즈 브랜치 존재를 사용자에게 확인 후 진행 여부 결정 (즉시 중단은 아님 — 버전 오타/패치 가능성)
- 동일명 브랜치가 이미 존재(로컬/원격)하면 9단계에서 생성 대신 체크아웃으로 처리 (멱등성)

### 6단계 — Jira 세팅 값 산출

다음 값들을 준비합니다 (적용은 8단계).

**(a) 담당자 (Assignee)** — `assignee`

- 2단계 `assignee` 가 `null`(미할당)일 때만 본인 할당 대상으로 준비. 이미 할당돼 있으면(본인/타인 무관) **건너뜀** (기존 할당 보존, 멱등성).
- "본인"은 하드코딩하지 않고 현재 사용자 `account_id` 를 조회:

```
atlassianUserInfo()
# 응답 account_id 를 8단계 assignee 값으로 사용
```

**(b) Start Date** — `customfield_10250`, `YYYY-MM-DD` (오늘 날짜는 환경 현재 날짜, `date +%F`)

대상 티켓은 작업 유형·root 상황에 따라 달라집니다:

- **no-child(단독)**: 현재 티켓 Start Date = 오늘 날짜
- **하위 작업 — root 가 이번 실행 전부터 이미 존재**: 현재(자식) 티켓 Start Date **생략** (부모 작업에서 이미 시작일 설정됨), 부모 티켓 미터치

```bash
git rev-parse --verify "origin/<prefix>/${PARENT_TICKET}/root" 2>/dev/null \
  || git rev-parse --verify "<prefix>/${PARENT_TICKET}/root" 2>/dev/null
# 성공(=root 사전 존재)이고 CREATE_ROOT != true 이면 자식 Start Date 생략
```

- **하위 작업 — `CREATE_ROOT=true`(root 를 이번 실행에서 신규 생성)**: **부모 티켓(`PARENT_TICKET`)에 Start Date = 오늘 날짜를 설정**하고, **현재(자식) 티켓 Start Date 는 생략**합니다 (시작일은 부모/부모 root 가 소유). 부모 적용은 8단계 (c).

**(c) 수정 버전 (Fix Version)** — `fixVersions`, 값 `${VERSION}` (예: `3.88.0`)

대상 티켓 규칙 (Start Date 와 동일한 소유 모델):

- **no-child** / **하위 작업 — root 사전 존재**: 현재 티켓 `fixVersions = [{name: ${VERSION}}]`
- **하위 작업 — `CREATE_ROOT=true`**: **부모 티켓에 수정 버전 설정**(8단계 (c)), **현재(자식) 티켓은 생략**

**등록 확인** (대상 티켓 공통): 해당 버전이 Jira 프로젝트 버전 목록에 있어야 세팅 가능. 등록 여부 전용 조회 1회:

```
getJiraIssue(cloudId="teamblind.atlassian.net", issueIdOrKey="<티켓키>",
  fields=["fixVersions"], expand="editmeta")
# 응답 editmeta.fields.fixVersions.allowedValues 에서 name == ${VERSION} 존재 여부 확인
```

- 미등록 시: 세팅을 건너뛰고 경고 (없는 버전을 새로 만들지 않음 — `SKILL.md` 안전 장치)
- (조회 생략 시 폴백) 8단계 `editJiraIssue` 가 미등록 버전으로 거부되면 그 항목만 실패 처리하고 "수정 버전 미등록" 경고 — 나머지 진행

**(d) 상태 전이 (In Progress) — 멀티홉 주의**

- 2단계에서 현재 상태가 이미 In Progress(개발)면 전이 생략 (멱등성)
- **In Progress(개발)(status id `3`)는 현재 상태에서 한 번에 도달하지 못할 수 있습니다.** CT 프로젝트는 **백로그에서 개발까지 2홉**입니다:
  - `진행결정이전(10000)` --[`진행결정 완료`]--> `진행결정완료(1)` --[`개발 시작`]--> `In Progress(개발)(3)`
  - transition id·이름은 프로젝트/현재 상태마다 다르므로 **하드코딩 금지** — 매 홉마다 `getTransitionsForJiraIssue` 로 재조회합니다.

**도달 알고리즘 (최대 3홉, 매 홉 재조회)**

```
반복 (현재 status.id != "3", 최대 3회):
  T = getTransitionsForJiraIssue(...).transitions
  1) T 중 to.id == "3" 가 있으면 그 transition 실행 → 완료
  2) 없으면 "전진" transition 하나를 골라 실행하고 다시 조회:
     - 절대 고르지 말 것: to.statusCategory.key == "done"(닫기·이슈아님 등 종료) / to.id 가 현재와 같은 Backlog 되돌리기
     - 우선 고를 것: to.statusCategory.key == "indeterminate"(진행 중) 또는 이름이 "진행결정 완료"/"개발 시작" 처럼 개발로 전진하는 transition
  3) 전진 후보가 0개거나 2개 이상이라 모호하면 → 자동 진행 금지, 사용자에게 선택/스킵 확인
```

- 위 루프로도 In Progress 에 못 닿으면(워크플로우 제약) 경고하고 상태 전이만 건너뜀 — 필드·브랜치 생성은 계속 진행
- 6단계에서는 첫 조회로 "직접 도달 가능 / 멀티홉 필요"를 판별만 하고, 실제 전이 실행은 7단계 확인 후 8단계에서 수행
- **`CREATE_ROOT=true` 면 담당자·상태(In Progress) 적용 대상이 자식·부모 둘 다**입니다 — 부모는 8단계 (c) 에서 동일한 도달 알고리즘으로 전이하고 미할당 시 본인 할당 (Start Date·수정 버전은 부모만)

### 7단계 — 최종 확인 (사용자 질문, 필수)

Jira·Git 을 변경하기 직전, 세팅 내용을 요약해 **한 번** 확인받습니다.

질문 예시:

> "작업 시작 세팅을 진행할까요?
> - 브랜치: `feature/CT-5208/no-child` (베이스 `release/3.88.0`)
> - Jira `CT-5208`:
>   - 담당자 → 본인(미할당 시)
>   - Start Date → 2026-06-18
>   - 수정 버전 → 3.88.0
>   - 상태 → In Progress(개발)"
>
> - **진행** / **취소**

- **`CREATE_ROOT=true`(부모 root 신규 생성) 인 경우 요약에 명시**:
  - "부모 root `<ROOT_NAME>` 를 `<ROOT_FROM>` 에서 생성 후 그 위에 작업 브랜치 생성" — release 출처를 반드시 보여줍니다.
  - **부모 티켓(`PARENT_TICKET`)**: 담당자(본인)·상태 In Progress·Start Date·수정 버전 설정
  - **자식 티켓(`<티켓키>`)**: 담당자(본인)·상태 In Progress (Start Date·수정 버전은 생략 — 부모가 소유)
- 멱등으로 건너뛸 항목은 요약에 명시 (예: "담당자: 이미 할당됨 → 유지", "Start Date: 부모 root 존재 → 자식 생략 / CREATE_ROOT → 부모에 설정", "상태: 이미 In Progress → 유지", "수정 버전: 프로젝트 미등록 → 건너뜀(경고)")
- **취소** 선택 시 아무것도 변경하지 않고 종료

### 8단계 — Jira 반영 (멱등 적용)

**(a) 현재(자식/단독) 티켓 필드 수정** — 담당자·Start Date·수정 버전을 한 번에 set (각 값은 6단계 산출 결과; 생략 대상은 fields 에서 제외):

```
editJiraIssue(cloudId="teamblind.atlassian.net", issueIdOrKey="<티켓키>",
  fields={
    "assignee": { "accountId": "<본인 account_id>" }, // 미할당일 때만. 이미 할당돼 있으면 키 제외
    "customfield_10250": "2026-06-18",            // Start Date (생략 대상이면 키 제외 — CREATE_ROOT면 자식은 생략)
    "fixVersions": [ { "name": "3.88.0" } ]        // 미등록/CREATE_ROOT(자식 생략)이면 키 제외
  })
```

> `CREATE_ROOT=true` 면 현재(자식) 티켓의 `customfield_10250`·`fixVersions` 는 **둘 다 키에서 제외**합니다 (담당자·상태 전이는 자식에 그대로 적용). 이 두 필드는 아래 (c) 에서 부모 티켓에 설정합니다.

**(b) 상태 전이** — 6단계 **도달 알고리즘**대로 In Progress(개발)까지 **멀티홉**으로 전이 (이미 In Progress 면 생략). 각 홉은 transition 실행 → 재조회 순으로:

```
# 예: 백로그에서 시작하는 CT 티켓 (2홉)
transitionJiraIssue(... transition={ "id": "<진행결정 완료 id>" })   # 1홉: 10000 → 1
# getTransitionsForJiraIssue 재조회 → to.id == "3" transition 확인
transitionJiraIssue(... transition={ "id": "<개발 시작 id>" })       # 2홉: 1 → 3 (In Progress)
```

- transition id 는 매 홉 재조회로 확보 (하드코딩 금지) — 위 id 는 예시값
- 각 호출 실패는 개별적으로 처리하고 사용자에게 어떤 항목이 반영/실패했는지 보고
- `fixVersions` 는 `set` 연산(배열 통째 교체)이므로 기존 값 보존이 필요하면 기존 + 신규를 합쳐 전달 (단독 작업 시작 시점에는 보통 비어 있음)

**(c) 부모 티켓 세팅 — `CREATE_ROOT=true` 일 때만** (root 를 이번 실행에서 신규 생성한 경우):

부모 root 가 처음 생성되므로, 부모 티켓(`PARENT_TICKET`)도 **시작 상태로 세팅**합니다 — **담당자(본인)·상태 In Progress·Start Date·수정 버전** (자식 티켓에서는 Start Date·수정 버전을 (a) 에서 생략).

```
# 1) 부모 현재값 확인 (멱등 판정용)
getJiraIssue(... issueIdOrKey="${PARENT_TICKET}",
  fields=["customfield_10250","fixVersions","assignee","status"])
# 2) 필드 set — 비어 있는 항목만 (기존 값 클로버 방지)
editJiraIssue(... issueIdOrKey="${PARENT_TICKET}",
  fields={
    "assignee": { "accountId": "<본인 account_id>" }, // 부모 assignee == null 일 때만
    "customfield_10250": "2026-06-18",          // 부모 Start Date 가 비어 있을 때만
    "fixVersions": [ { "name": "${VERSION}" } ]  // 부모 fixVersions 가 비어 있을 때만 (등록 버전 확인 동일 적용)
  })
# 3) 부모 상태 전이 — In Progress(개발) 까지 (b) 의 멀티홉 도달 알고리즘 동일 적용 (이미 In Progress 면 생략)
getTransitionsForJiraIssue(... issueIdOrKey="${PARENT_TICKET}")  # 매 홉 재조회
transitionJiraIssue(... issueIdOrKey="${PARENT_TICKET}", transition={ "id": "<...>" })
```

- 부모도 **미할당일 때만 본인 할당**, **이미 In Progress 면 전이 생략**, **이미 채워진 필드는 건너뜀** (멱등, 타 작업자 값 보존).
- 부모 상태 전이는 (b) 와 동일하게 **멀티홉·매 홉 재조회**(`닫기`/`이슈아님` 등 종료 전이 금지).
- `CREATE_ROOT` 이 아니면 이 블록(c)을 수행하지 않습니다.

### 9단계 — 브랜치 생성·push

remote 최신본 기준으로 분기 → 체크아웃 → origin push + upstream 설정.

```bash
git fetch origin
```

**(선행) 부모 root 신규 생성 — `CREATE_ROOT=true` 인 경우에만** (5단계에서 결정, 7단계에서 확인됨):

지정한 release 에서 부모 root 를 먼저 만들어 push 한 뒤, 그 root 를 베이스로 자식 브랜치를 만듭니다.

```bash
# ROOT_NAME = <prefix>/<부모티켓>/root , ROOT_FROM = release/<선택값>
if ! git rev-parse --verify "origin/${ROOT_NAME}" >/dev/null 2>&1; then   # 다시 한 번 미존재 확인(레이스 방지)
  git checkout -b "${ROOT_NAME}" --no-track "origin/${ROOT_FROM}"
  git push -u origin "${ROOT_NAME}"
fi
BASE_BRANCH="${ROOT_NAME}"   # 이후 자식 브랜치의 베이스로 사용
```

- root 생성 후에는 `origin/${ROOT_NAME}` 이 존재하므로 아래 자식 브랜치 분기가 정상 동작합니다.
- `CREATE_ROOT` 이 아니면 이 블록을 건너뜁니다.

**작업(자식/단독) 브랜치 생성·push**:

```bash
# 멱등성 — root 와 동일하게 origin/<BRANCH>(리모트) 기준으로 기존 여부 판별
if git rev-parse --verify "origin/<BRANCH>" >/dev/null 2>&1; then
  git checkout "<BRANCH>"                                       # 원격에 이미 있음 → 로컬 체크아웃(없으면 origin/<BRANCH> 트래킹 생성)
else
  git checkout -b "<BRANCH>" --no-track "origin/<BASE_BRANCH>"   # stale 로컬 방지: origin/ 기준 분기 (CREATE_ROOT 면 BASE_BRANCH=ROOT_NAME)
  git push -u origin "<BRANCH>"                                 # 신규일 때만 push — upstream 을 origin/<BRANCH> 로 설정
fi                                                              # --no-track: upstream 이 베이스로 잡히지 않게
```

> `--no-track` 없이 `origin/<base>` 에서 분기하면 git 이 upstream 을 `origin/<base>` 로 자동 설정합니다. `git push -u` 가 이후 자기 브랜치로 교정하지만, 혼동을 막기 위해 생성 시 `--no-track` 으로 시작하는 것을 권장합니다.

- `origin/<BASE_BRANCH>` 가 없고 로컬에만 있으면 로컬 베이스로 폴백하되 경고
- push 실패(권한/네트워크) 시: 로컬 브랜치는 생성된 상태이므로 그 사실과 함께 수동 push 안내
- 완료 후 브랜치명·베이스·반영된 Jira 변경 요약을 안내 (이어서 10단계 또는 `generate-pr-auto` 로 PR 생성 가능)

### 10단계 — 티켓 본문 기반 작업 시작 제안 (사용자 질문)

환경 세팅(브랜치 + Jira)이 끝난 직후, **티켓 본문(description) 내용을 기반으로 실제 작업을 바로 시작할지** 물어봅니다. (환경만 세팅하고 끝낼 수도 있으므로 항상 질문 — 자동 시작 금지)

**1. 티켓 본문 확보**

2단계에서 `description` 을 받지 않았다면 여기서 조회합니다:

```
getJiraIssue(cloudId="teamblind.atlassian.net", issueIdOrKey="<티켓키>",
  fields=["summary","description"], responseContentFormat="markdown")
```

- 본문이 비어 있으면(설명 없음) 그 사실을 알리고, summary 만으로 진행할지 묻습니다.

**2. 작업 시작 여부 질문 (사용자 질문)**

본문을 1~3줄로 요약해 보여준 뒤 질문합니다:

> "환경 세팅 완료 — `<BRANCH>` 로 체크아웃됨.
> 티켓 본문 요약: <description 핵심 1~3줄>
> 이 내용을 기반으로 지금 작업을 시작할까요?"
>
> - **예, 작업 시작** — 티켓 본문 기반으로 구현 진행
> - **아니오 (여기까지)** — 환경 세팅만 하고 종료

**3-a. "예" 선택 시 — 작업 시작**

- 생성된 작업 브랜치(`<BRANCH>`)에 체크아웃된 상태에서 시작합니다 (9단계에서 이미 체크아웃됨).
- 티켓 `description` 을 요구사항으로 삼아 구현을 진행합니다. 작업 성격에 따라 적절한 개발 스킬을 사용합니다 (예: 설계가 필요하면 brainstorming, 구현은 TDD 등 — 프로젝트 규약 우선).
- 본문이 모호하거나 의사결정이 필요하면 먼저 사용자에게 확인한 뒤 진행합니다.

**3-b. "아니오" 선택 시**

- 환경 세팅 요약만 안내하고 종료합니다. 나중에 "작업 시작해줘" 또는 직접 구현 요청으로 이어갈 수 있음을 한 줄로 안내합니다.

> 이 단계는 **제안**이며, 어떤 경우에도 사용자 동의 없이 코드 변경을 시작하지 않습니다.

---

## 품질 기준

- 티켓 키는 사용할 때 반드시 사용자 확인을 거친다 (Jira·Git 변경 대상)
- 브랜치 prefix·작업 유형은 **항상 질문** — 자동 추론 금지
- 7단계 최종 확인 없이는 Jira·Git 을 변경하지 않는다
- **하위 작업 입력 베이스가 미존재할 때**: 부모 root 형태면 **release 선택 후 root 생성**(거절 시 중단), 그 외 임의 베이스는 **즉시 중단(abort)** — 어느 경우든 Jira·Git 변경 전에 판단하며 다른 베이스를 자동 추정하지 않는다
- **부모 root 신규 생성은 항상 어떤 release 에서 만들지 질문**하고, 실제 생성은 7단계 확인 후 9단계에서 수행한다 (root → 자식 순서)
- **부모 root 신규 생성(CREATE_ROOT) 시 부모 티켓도 담당자(본인)·In Progress·Start Date·수정 버전 설정**(멱등·멀티홉 전이), **자식 티켓은 담당자·In Progress 만**(Start Date·수정 버전 생략)
- 모든 변경은 **멱등** — 이미 In Progress·이미 세팅된 필드·이미 할당된 담당자·이미 존재하는 브랜치는 건너뛰고 재실행해도 안전
- 담당자는 **미할당일 때만 본인 할당** — 기존 할당(본인/타인)은 덮어쓰지 않는다
- 분기는 항상 **remote(`origin/`) 최신본 기준** (stale 로컬 기준 분기 금지)
- 브랜치 생성 후 `-u` 로 upstream 설정 (바로 PR 생성 가능)
- 없는 수정 버전은 새로 만들지 않고 경고만 한다

## 주의사항

- **0단계(도구 사전 준비)** — 실행에 필요한 기능의 가용성을 확인하고, 선택적 기능은 해당 단계에서 확인합니다.
- Jira transition id 는 현재 상태마다 다르므로 **하드코딩 금지** — 항상 `getTransitionsForJiraIssue` 로 동적 조회
- Start Date·수정 버전 **소유 규칙**을 빠뜨리지 말 것: 하위 작업은 자식 Start Date 생략(부모 소유), `root` 사전 존재 시 부모 미터치 / **CREATE_ROOT 시 Start Date·수정 버전을 부모 티켓에 설정하고 자식은 둘 다 생략**
- `fixVersions` 는 배열 set 연산임에 유의 (기존 값 보존 필요 시 합쳐 전달)
- 담당자 할당은 `assignee == null` 인 경우에만 — 본인 account_id 는 `atlassianUserInfo` 로 동적 조회(하드코딩 금지)
- 작업 디렉토리(uncommitted) 가드는 **이번 범위 제외** (비범위)
- 종료 후 후속 작업은 `generate-pr-auto` skill(`android-pr-generation` 플러그인)로 연결 (작업 시작 ↔ 종료 한 쌍)
