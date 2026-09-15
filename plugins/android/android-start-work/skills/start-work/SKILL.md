---
name: start-work
description: Jira 티켓 번호로 작업 시작 환경(Jira 상태·필드 + Git 브랜치)을 한 번에 세팅하는 skill. 티켓 summary·버전 조회 후 브랜치 prefix(feature/debt/QA/bugfix/hotfix)와 작업 유형(no-child/하위 작업)을 사용자에게 질문하고, Start Date·수정 버전·In Progress 상태를 Jira 에 반영한 뒤 네이밍 규칙대로 브랜치를 생성·push 합니다. generate-pr-auto(작업 종료/PR 생성)의 반대편(작업 시작점). "작업 시작해줘"·"start-work"·"CT-1234 작업 시작"·"브랜치 만들고 인프로그레스로 바꿔줘" 요청이나 `start-work 티켓키` 이름을 지정한 요청 시 사용.
---

# Teamblind Android — 작업 시작 (start-work)

`start-work <티켓키>` 를 지정해 요청하거나 "작업 시작해줘" 류 요청 시 자동 발동되는 스킬입니다. Jira 티켓 하나로 **작업 환경(Jira 상태·필드 + Git 브랜치)을 한 번에 세팅**합니다.

이 스킬은 **generate-pr-auto**(`android-pr-generation` 플러그인, 작업 종료/PR 생성)의 **반대편(작업 시작점)** 이며, 동일한 **브랜치 네이밍·버전 컨벤션**(`release/<version.name>`, prefix 화이트리스트, 티켓 키 추출)을 공유합니다. 컨벤션의 단일 출처는 generate-pr-auto 의 SKILL.md 이며, 이 문서는 시작 단계 고유의 규칙(브랜치 타입 결정·Jira 필드 세팅)만 정의합니다.

> 단계별 상세 실행 절차(정확한 bash/MCP 명령과 검증 로직)는 [references/workflow.md](references/workflow.md) 를 참조하세요. 이 문서는 그 절차가 따르는 컨벤션의 단일 출처(canonical)입니다.

---

실행 전에 [실행 환경 지침](references/execution-environment.md)을 읽고, 현재 환경에 맞는 도구·질문·스킬 참조 방식을 적용합니다.

## 입력

- **Jira 티켓 키** (예: `CT-5208`) — 인자(`start-work CT-5208`) 또는 발화에서 추출.
  - 매칭 정규식: `[A-Z]{2,}-\d+` (generate-pr-auto 의 **Jira 티켓 키 추출 규칙** 과 동일)
  - 추출 실패 시 사용자에게 직접 질문
- 추출/입력한 티켓 키는 **항상 사용자에게 한 번 확인**한 뒤 사용 (Jira·Git 양쪽을 변경하므로)

---

## 브랜치 타입 결정 (항상 사용자에게 질문)

작업 시작 시 **두 가지를 항상 사용자 질문으로 질문**합니다. 자동 추론하지 않습니다.

### 1. 브랜치 prefix 선택

`feature` / `debt` / `QA` / `bugfix` / `hotfix` 중 선택.

> prefix 선택지는 generate-pr-auto 의 **prefix → 제목 태그/라벨 매핑** 화이트리스트와 정합합니다. (`hotfix` 는 시작 단계에서 추가 허용)

### 2. 작업 유형 선택 — no-child(단독) vs 하위 작업

| 작업 유형 | 의미 | 분기 베이스 |
|---|---|---|
| **no-child (단독 작업)** | 하위 작업 없이 독립적으로 진행하는 작업 | `release/<version.name>` |
| **하위 작업** | 큰 단위 기능(부모 티켓)의 하위로 진행하는 작업 | **사용자에게 입력받은 베이스 브랜치** |

- **하위 작업** 선택 시 분기할 **베이스 브랜치를 사용자에게 입력**받습니다. 부모 티켓은 입력받은 베이스 브랜치에서 추출합니다.
  - 예: 베이스 `feature/TB-6056/root` 입력 → 부모 티켓 `TB-6056`
  - **입력 베이스가 존재하지 않으면(원격·로컬 모두)**:
    - 베이스가 **부모 root 형태(`<prefix>/<부모>/root`)면 → root 생성 플로우 제안** — "어떤 release 브랜치에서 만들지" 물어 root 를 생성한 뒤 그 위에 작업 브랜치를 만듭니다 (아래 **부모 root 신규 생성** 참조).
    - 그 외 임의 베이스면 → **skill 실행을 즉시 취소**하고 "베이스 브랜치가 존재하지 않으니 확인하세요"로 안내합니다 (잘못된 베이스로 브랜치/부모 티켓이 만들어지는 것을 방지).

#### 부모 root 신규 생성 (release 선택)

하위 작업의 베이스(부모 root `<prefix>/<부모>/root`)가 아직 없을 때, 중단 대신 생성할 수 있습니다.

- **어떤 release 브랜치에서 생성할지 항상 질문**합니다 (사용자 질문): `release/<version.name>`(기본) + 최근 `release/*` 후보 + "생성 안 함(중단)". 목록에 없으면 "기타"로 직접 입력.
- release 선택 시: 선택한 release 에서 `<prefix>/<부모>/root` 를 생성·push 한 뒤, 그 root 를 베이스로 작업 브랜치(`<prefix>/<부모>/<현재티켓>`)를 만듭니다.
- 모든 Git 변경은 **최종 확인(7단계) 이후**에 수행하며, 확인 요약에 "부모 root 를 어떤 release 에서 생성"을 명시합니다.
- **부모 티켓 세팅**: 부모가 이번에 처음 시작되는 것이므로 부모 티켓에 **담당자(본인)·상태 In Progress·Start Date(오늘)·수정 버전**을 설정합니다. 부모 상태 전이도 자식과 동일한 **멀티홉 도달 알고리즘**을 적용합니다.
- **자식 티켓**: 담당자(본인)·상태 In Progress 만 적용하고 **Start Date·수정 버전은 생략**합니다 (부모가 소유).
- **멱등** — 부모/자식 모두 이미 In Progress 면 전이 생략, 이미 할당돼 있으면 담당자 유지, 이미 채워진 필드는 건너뜀 (타 작업자 값 보존).
- "생성 안 함" 선택 시 즉시 중단.

#### Jira 부모 기반 베이스 추천 (subtask)

현재 티켓이 **Jira subtask**(또는 `parent` 가 있는 티켓)면, 베이스 입력 질문에 **부모 티켓 기반 추천 후보를 함께 제시**합니다 (사용자가 매번 베이스를 떠올리지 않아도 되도록).

- Jira 의 `parent.key` 를 부모 티켓으로 사용해 **추천 베이스 `<prefix>/<부모티켓>/root`** 와 **결과 브랜치 `<prefix>/<부모티켓>/<현재티켓>`** 을 산출
- **원격에 해당 root 가 없어도 추천 후보로 노출**합니다 (목록에서 바로 인지 가능하도록). 단, **추천이 존재 검증을 우회하지 않습니다** — 사용자가 미존재 베이스를 고르면 5단계 가드로 그대로 중단됩니다.
- 추천은 후보일 뿐이며, 사용자는 다른 베이스(예: 현재 체크아웃 브랜치)나 직접 입력(사용자 질문의 "기타")으로 변경할 수 있습니다.
- Jira `parent` 가 없으면 추천을 생략하고 베이스를 직접 입력받습니다.

---

## 브랜치 네이밍 규칙

| 작업 유형 | 브랜치명 | 베이스 |
|---|---|---|
| no-child (단독) | `<prefix>/<티켓>/no-child` | `release/<version.name>` |
| 하위 작업 | `<prefix>/<부모티켓>/<현재티켓>` | 사용자 입력 브랜치 |

- prefix: `feature` / `debt` / `QA` / `bugfix` / `hotfix`
- no-child 예: `feature/CT-5208/no-child`
- 하위 작업 예: `feature/TB-6056/CT-5208` (베이스 `feature/TB-6056/root` 입력 시 부모 `TB-6056` 추출)

> 브랜치 네이밍 패턴 전반(`<ticket>/root`·`/no-child` 등)은 generate-pr-auto 의 **브랜치 네이밍 컨벤션** 을 단일 출처로 따릅니다.

---

## 버전 조회 규칙

release 브랜치·수정 버전 값의 출처는 안드로이드 앱 레포의 `app/config/version.properties` 의 `version.name` 입니다 (generate-pr-auto 와 동일 출처).

```bash
VERSION=$(grep '^version.name' app/config/version.properties | cut -d= -f2 | tr -d ' ')   # 예: 3.88.0
```

- no-child 베이스 = `release/${VERSION}`
- Jira 수정 버전(Fix Version) = `${VERSION}`

---

## Jira 필드 업데이트 규칙

세팅 전 안전 장치(아래 **안전 장치**)로 사용자 최종 확인을 받은 뒤 적용합니다. **멱등성** — 이미 값이 세팅돼 있으면 건너뜁니다.

| 항목 | Jira 필드 | 값 | 비고 |
|---|---|---|---|
| 담당자 (Assignee) | `assignee` | 현재 사용자(본인) | **미할당일 때만** 본인 할당. 이미 할당돼 있으면 건드리지 않음 |
| Start Date | `customfield_10250` (date) | 오늘 날짜 `YYYY-MM-DD` | 대상 티켓은 **Start Date·수정 버전 소유 규칙** 참조 (CREATE_ROOT면 부모 티켓) |
| 수정 버전 (Fix Version) | `fixVersions` (array) | `[{ "name": "<version.name>" }]` | 프로젝트 등록 버전이어야 함(안전 장치). 대상 티켓은 **소유 규칙** 참조 |
| 상태 | (transition) | **In Progress(개발)** | transition 동적 조회 후 전이 |

### 담당자 할당 (미할당 시 본인)

- 현재 담당자가 **비어 있으면(`assignee == null`)** 현재 사용자(본인)를 담당자로 할당합니다.
- **이미 누군가 할당돼 있으면 건드리지 않습니다** — 본인이든 타인이든 기존 할당을 덮어쓰지 않음 (멱등 & 타인 작업 보존).
- "본인"은 하드코딩하지 않고 `atlassianUserInfo` 로 현재 사용자 `account_id` 를 조회해 사용합니다.

### Start Date·수정 버전 소유 규칙 (자식 vs 부모)

- **no-child(단독)**: 현재 티켓에 Start Date(오늘)·수정 버전 설정.
- **하위 작업 — root 가 이번 실행 전부터 이미 존재**: 현재(자식) 티켓 Start Date **생략**(부모에서 이미 설정됨), 수정 버전은 현재 티켓에 설정.
- **하위 작업 — root 를 이번 실행에서 신규 생성**(아래 **부모 root 신규 생성**): **부모 티켓**에 담당자(본인)·상태 In Progress·**Start Date·수정 버전**을 설정하고, **자식 티켓에서는 Start Date·수정 버전을 생략**합니다(자식엔 담당자·In Progress만). 시작일·버전은 부모/부모 root 가 소유.

### 상태 전이 (In Progress)

- transition id 는 현재 상태마다 다르므로 **하드코딩 금지** — `getTransitionsForJiraIssue` 로 조회해 `to` 상태가 **In Progress(개발)** (status id `3`) 인 transition 을 찾아 전이합니다.
- **멀티홉 주의** — 백로그(`진행결정이전`)에서는 In Progress 로 **직접 전이가 불가**하며 중간 상태를 거칩니다 (CT 프로젝트: `진행결정이전 → 진행결정완료 → In Progress(개발)`, 2홉). 매 홉마다 transition 을 재조회하며 In Progress 에 도달할 때까지 전진합니다 (종료 상태 `닫기`/`이슈아님` 으로 가는 전이는 선택 금지). 상세 알고리즘은 [workflow.md](references/workflow.md) 6·8단계 참조.
- 이미 In Progress 면 전이를 건너뜁니다 (멱등성).

---

## 안전 장치

- **최종 확인 1회 필수** — Jira(상태·필드)와 Git(브랜치)을 모두 변경하므로, 실행 직전 사용자 질문으로 최종 세팅 내용을 요약해 한 번 확인 후 진행합니다. 요약에 포함할 항목:
  - 브랜치명 / 베이스 브랜치 (**부모 root 신규 생성 시 어떤 release 에서 생성하는지 포함**)
  - Jira 변경: Start Date(설정/생략), 수정 버전, 상태 → In Progress
- **멱등성** — 이미 In Progress 거나 필드가 이미 세팅된 경우, **담당자가 이미 할당된 경우** 해당 항목을 건너뛰고, 재실행해도 안전하게 동작합니다 (브랜치가 이미 있으면 생성 대신 체크아웃).
- **수정 버전 미등록 경고** — `version.name` 이 Jira 프로젝트 버전 목록에 없으면 수정 버전 세팅을 건너뛰고 경고합니다 (없는 버전을 새로 만들지 않음).
- **하위 작업 베이스 미존재 시 처리** — 입력 베이스가 원격·로컬 어디에도 없을 때:
  - **부모 root 형태(`<prefix>/<부모>/root`)면 → release 선택 후 root 생성** (위 **부모 root 신규 생성**). 생성을 거절(생성 안 함)하면 중단.
  - **그 외 임의 베이스면 → 즉시 중단** ("베이스 브랜치가 존재하지 않으니 확인하세요"). 자동 추정·자동 생성 안 함.
  - 어느 경우든 검증·질문은 Jira·Git 변경 **전(7단계 확인 전)** 에 수행되어, 중단 시 부작용이 없습니다.

---

## 추가 동작

- **remote fetch 후 분기** — `origin/release/<version.name>`(또는 사용자 입력 베이스) 최신본을 fetch 한 뒤 그 기준으로 분기합니다 (stale 로컬 기준 분기 방지).
- **브랜치 push + upstream** — 생성·체크아웃 후 origin 에 push 하고 `-u` 로 upstream 을 설정합니다 (바로 PR 생성 가능).
- **부모 root 신규 생성(선택)** — 하위 작업의 부모 root 가 없을 때, 선택한 release 에서 root 를 먼저 만들어 push 한 뒤 그 위에 작업 브랜치를 생성합니다.
- **작업 시작 제안(선택)** — 환경 세팅 완료 후, 티켓 본문(description) 내용을 기반으로 **지금 바로 작업을 시작할지** 사용자 질문으로 물어봅니다. "예" 면 본문을 요구사항으로 구현을 진행하고, "아니오" 면 세팅만 하고 종료합니다 (자동 시작 금지 — 항상 동의 후 진행).

---

## 비범위 (제외)

- 작업 디렉토리(uncommitted 변경) 가드 — 이번 범위 제외

---

## 실행 절차

`start-work <티켓키>` 호출 또는 "작업 시작해줘" 요청 시 아래 0~10단계를 순서대로 수행합니다. **각 단계의 셸/MCP 사용 예시와 검증 로직은 [references/workflow.md](references/workflow.md) 를 참조하세요.**

| 단계 | 내용 |
|---|---|
| 0 | 도구 사전 준비 — 실행 환경에 따라 필요한 질문·조회·실행 기능의 가용성 확인 |
| 1 | 티켓 키 확정 — 인자/발화에서 추출 후 **사용자 확인** |
| 2 | 티켓 정보 조회 — summary·issuetype·상태 (`getJiraIssue`) |
| 3 | 버전 조회 — `app/config/version.properties` 의 `version.name` |
| 4 | **브랜치 타입 질문(사용자 질문)** — prefix + (no-child / 하위 작업), 하위 작업이면 베이스 입력 (**subtask면 Jira 부모 기반 `<prefix>/<부모>/root` 추천 후보 제시**) |
| 5 | 브랜치명·베이스 산출 — **브랜치 네이밍 규칙** 적용 (하위 작업이면 부모 티켓 추출). 베이스 미존재 시: **부모 root 형태면 release 선택 후 root 생성 / 그 외면 즉시 중단** |
| 6 | Jira 세팅 값 산출 — 담당자(미할당 시 본인)·Start Date(예외 규칙 반영)·수정 버전·In Progress transition 조회 |
| 7 | **최종 확인(사용자 질문)** — 브랜치/베이스/Jira 변경(담당자 포함) 요약 후 진행 여부 확인 |
| 8 | Jira 반영 — 자식: 담당자·상태(In Progress)(+ no-child/일반 하위는 Start Date·수정 버전). **CREATE_ROOT면 부모 티켓도 담당자·In Progress·Start Date·수정 버전 설정하고, 자식은 Start Date·수정 버전 생략** (멱등·멀티홉) |
| 9 | 브랜치 생성 — remote fetch → (CREATE_ROOT면 release 에서 부모 root 먼저 생성·push) → 베이스에서 분기·체크아웃 → origin push + upstream(`-u`) |
| 10 | **티켓 본문 기반 작업 시작 제안(사용자 질문)** — description 요약 후 "지금 작업 시작할까요?" → 예: 본문 기반 구현 진행 / 아니오: 세팅만 하고 종료 |

> 7단계 확인 없이는 Jira·Git 변경을 수행하지 않습니다. 8·9단계는 멱등하게 동작합니다. 10단계는 제안이며 사용자 동의 없이 코드 변경을 시작하지 않습니다.

---

## 발동 조건

이 스킬은 다음 질문/요청 시 자동 발동됩니다:

- "작업 시작해줘" / "이 티켓 작업 시작" / "CT-1234 작업 시작해"
- "브랜치 만들고 In Progress 로 바꿔줘" / "시작 세팅해줘"
- `start-work` 또는 `start-work <티켓키>` 명시 요청 시
- 작업 시작 시 브랜치 네이밍/베이스 결정/Jira 시작 세팅 관련 질문

## 설치 의존성

> 이 스킬은 브랜치 네이밍·버전·티켓 키 추출 컨벤션의 단일 출처(SSOT)를 `generate-pr-auto`(**android-pr-generation** 플러그인)에 위임합니다. **단독 설치 시 컨벤션 SSOT 가 비므로 `android-pr-generation` 과 함께 설치**하세요. (본 SKILL.md 는 시작 단계 고유 규칙은 자체 정의하므로, 미설치 시에도 동작은 하되 컨벤션 참조 링크가 비게 됩니다.)

## 관련 파일

- 단계별 상세 실행 절차: [references/workflow.md](references/workflow.md)
- 작업 종료/PR 생성(반대편 액션) + 컨벤션 SSOT: `generate-pr-auto` skill (`android-pr-generation` 플러그인)
- 버전 소스: `app/config/version.properties` (`version.name=*`)
