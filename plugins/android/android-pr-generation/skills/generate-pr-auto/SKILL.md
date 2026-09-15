---
name: generate-pr-auto
description: 현재 브랜치 기준으로 베이스를 추론하고 Jira 티켓을 연동해 팀 규격 Draft PR을 자동 생성(work). QA 완료된 feature/티켓/root 를 release 로 합류시키는 Complete PR(complete intent)도 동일 흐름으로 생성. PR 본문에 드래그앤드롭으로 올라간 미디어 링크를 ScreenShot 섹션 표로 재구성하는 기능 포함. 생성 전 마일스톤 설정 여부를 질문해 선택 시 GitHub 마일스톤을 부착하는 절차 포함. Teamblind Android PR 컨벤션(브랜치 네이밍·베이스 추론·제목/본문 포맷·라벨 매핑·작성 규칙)도 정의. "현재 브랜치 PR 만들어줘"·"draft PR 생성"·"complete PR 만들어줘"·"QA 끝났으니 릴리즈에 머지"·"ScreenShot 표 정리해줘"·"스크린샷 표로 재구성" 요청이나 PR 컨벤션 관련 질문 시 사용.
---

# Teamblind Android — 자동 PR 생성

`generate-pr-auto` 를 지정해 요청하거나 "현재 브랜치 PR 만들어줘" 류 요청 시 자동 발동되는 스킬입니다. 자동 PR 생성에 필요한 **팀 컨벤션·포맷**(이 문서)과 **실행 절차**를 정의합니다.

이 스킬은 두 가지 **intent** 를 다룹니다:
- **work** (기본) — 현재 작업 브랜치 기준으로 베이스를 추론하고 4섹션 본문의 작업용 PR 생성
- **complete** — QA 완료된 `feature/<티켓>/root` 를 `release/<버전>` 으로 합류시키는 Complete PR 생성

두 intent 는 **진입점(현재 브랜치)·베이스·Jira 조회·도구 준비·생성 절차를 공유**하며, 제목 태그·라벨·본문 형식만 분기합니다. Sync PR(release 를 다른 브랜치로 동기화)은 git 상태를 변경하는 별개 액션이므로 [generate-sync-pr](../generate-sync-pr/SKILL.md) 스킬을 사용하세요.

> 단계별 상세 실행 절차(정확한 bash/MCP/gh 명령과 검증 로직)는 [references/workflow.md](references/workflow.md) 를 참조하세요. 이 문서는 그 절차가 따르는 컨벤션의 단일 출처(canonical)입니다.

---

실행 전에 [실행 환경 지침](references/execution-environment.md)을 읽고, 현재 환경에 맞는 도구·질문·스킬 참조 방식을 적용합니다.

## PR intent 판별 규칙 (work / complete)

| 입력/상태 | intent |
|---|---|
| `generate-pr-auto complete` 인자, 또는 "complete PR"·"QA 완료"·"릴리즈에 머지" 의도 | **complete** |
| 현재 브랜치가 `feature/<티켓>/root` 인데 의도가 모호 | 사용자 질문으로 work/complete 확인 |
| 그 외 (기본) | **work** |

> intent 결정 후, **work 와 complete 의 차이는 아래 "Complete intent 분기" 표에 정의된 항목(베이스 결정·제목 태그·타입 라벨·본문)뿐**입니다. 나머지 절차(도구 준비·Jira 조회·사용자 확인 후 생성·Draft→Ready)는 공통입니다.

### Complete intent 분기

| 항목 | work (기본) | complete |
|---|---|---|
| 진입점(head) | 현재 작업 브랜치 | 현재 `feature/<티켓>/root` |
| base | 베이스 추론 규칙(merge-base) | `release/<version.name>` (feature/root 의 2순위와 동일) |
| 제목 태그 (`TITLE_TAG`) | `Feature`/`QA`/`Debt`/`Bugfix` | `Complete` |
| 라벨 | `TYPE_*` + `PRIORITY_LOW` + `RISK_HIGH(ApproveCount >= 2)` 부착 | **`TYPE_COMPLETE` 하나만 부착** (그 외 라벨 없음) |
| 본문 | 4섹션 고정 포맷 (`PR_DESCRIPTION_*.md` 파일 경유) | **한 줄**: `<티켓키> QA 완료 후 <버전> 으로 머지하는 PR입니다` (티켓 없으면 `QA 완료 후 <버전> 으로 머지하는 PR입니다`). **md 파일을 만들지 않고 `--body` 로 직접 전달** |

- complete 의 base 는 별도 추론 없이 **현재 활성 release**(`app/config/version.properties` 의 `version.name`) → `release/<version.name>` 로 고정합니다(아래 **베이스 브랜치 추론 규칙** 의 feature/root 2순위 산출식 재사용).
- **complete 는 `TYPE_COMPLETE` 라벨 하나만 부착합니다** — `gh pr create` 에 `--label "TYPE_COMPLETE"` 만 넣고 그 외(`PRIORITY_*`·`RISK_*`·`SkipUnitTest` 등) `--label` 인자는 넣지 않습니다.
- **complete 본문은 PR 본문 md 파일(`PR_DESCRIPTION_*.md`)을 만들지 않고** 한 줄 문자열을 `--body` 로 직접 전달합니다. 4섹션 포맷도 사용하지 않습니다.
- 제목은 `[Complete][<티켓키>] <Jira summary>` (티켓 없으면 `[Complete] <제목>`).

#### Complete 예시

- 제목 `[Complete][TB-9812] [Android] [KR Only] 인증 단계 추가` / base `release/3.86.0` / head `feature/TB-9812/root`
- 본문 `TB-9812 QA 완료 후 3.86.0 으로 머지하는 PR입니다`

---

## 브랜치 네이밍 컨벤션

| 패턴 | 의미 | 예시 |
|---|---|---|
| `feature/<ticket>/root` | 큰 단위 기능의 루트 브랜치 | `feature/TB-6056/root` |
| `feature/<ticket>/root/<sub>` | root의 하위 작업 | `feature/CT-4688/root/public-room-search` |
| `feature/<ticket>/no-child` | 단독 기능 브랜치 (하위 없음) | `feature/CT-3580/no-child` |
| `feature/<ticket>/no-child/<sub>` | no-child의 하위 변형 | `feature/CT-3580/no-child/module` |
| `feature/<ticket>/<기타>` | root 하위에서 분기된 일반 작업 | `feature/TB-6056/article-detail` |
| `qa/<root-ticket>/<qa-ticket>` 또는 `QA/<root-ticket>/<qa-ticket>` | QA 분기 (root 브랜치에서 나온 검증 작업) | `QA/TB-6056/TB-9807` |
| `debt/<ticket>/<suffix>` 또는 `Debt/<ticket>/<suffix>` | Debt(기술부채) 작업 | `debt/CT-5121/no-child` |
| `bugfix/<ticket>/<suffix>` 또는 `Bugfix/<ticket>/<suffix>` | 버그 수정 작업 | `bugfix/TB-9738/no-child` |

### 브랜치 파싱 규칙

- `/` 로 split → `prefix / middle / suffix` 3개 파트
- suffix 는 middle 바로 뒤 **첫 세그먼트 하나**만 본다. 그 뒤는 무시
  - 예: `feature/CT-4688/root/public-room-search` → suffix = `root`

---

## 베이스 브랜치 추론 규칙

release 브랜치 이름은 `app/config/version.properties` 의 `version.name` 값을 기반으로 산출 (`release/<version.name>`, 예: `release/3.85.0`).

| 현재 브랜치 (prefix / suffix) | 1순위 후보 | 2순위 후보 |
|---|---|---|
| prefix=`QA` 또는 `qa` | 브랜치가 실제 분기된 베이스 | `feature/{middle}/root` |
| prefix=`feature` 또는 `Feature`, suffix=`root` | 브랜치가 실제 분기된 베이스 | `release/<version.name>` |
| prefix=`feature` 또는 `Feature`, suffix=`no-child` | 브랜치가 실제 분기된 베이스 | `release/<version.name>` |
| prefix=`debt` 또는 `Debt`, suffix=`root` | 브랜치가 실제 분기된 베이스 | `release/<version.name>` |
| prefix=`debt` 또는 `Debt`, suffix=`no-child` | 브랜치가 실제 분기된 베이스 | `release/<version.name>` |
| prefix=`bugfix` 또는 `Bugfix`, suffix=`root` | 브랜치가 실제 분기된 베이스 | `release/<version.name>` |
| prefix=`bugfix` 또는 `Bugfix`, suffix=`no-child` | 브랜치가 실제 분기된 베이스 | `release/<version.name>` |

> *"실제 분기된 베이스"* 는 원격 브랜치 후보 중 HEAD 와 가장 가까운 merge-base 를 가진 브랜치를 의미합니다.

> prefix 가 위 화이트리스트(`feature`/`Feature`/`qa`/`QA`/`debt`/`Debt`/`bugfix`/`Bugfix`)에 없으면 사용자에게 베이스를 직접 묻습니다.

> 사용자가 인자로 베이스를 명시한 경우(`generate-pr-auto <base>`) 자동 추론을 건너뜁니다.

---

## Jira 티켓 키 추출 규칙

- 매칭 정규식: `[A-Z]{2,}-\d+` (TB-, CT- 등 다양한 프로젝트 키 지원)
- 브랜치 이름 → 실패 시 최근 커밋 메시지 순으로 매칭
- 여러 개 매칭 시 가장 마지막(suffix 쪽) 우선

---

## PR 제목 포맷

```
[Feature/QA/Debt/Bugfix][<티켓키>] <Jira 티켓 제목>
```

### prefix → 제목 태그 / GitHub 라벨 매핑

| prefix | 제목 태그 (PascalCase) | GitHub 라벨 (TYPE_* 형식) |
|---|---|---|
| `feature` / `Feature` | `Feature` | `TYPE_FEATURE` |
| `qa` / `QA` | `QA` | `TYPE_QA` |
| `debt` / `Debt` | `Debt` | `TYPE_DEBT` |
| `bugfix` / `Bugfix` | `Bugfix` | `TYPE_BUGFIX` |

> **제목 태그**는 PR 제목 `[...]` 안에 들어가는 PascalCase 값,
> **GitHub 라벨**은 `gh pr create --label` 로 부착하는 `TYPE_대문자` 형식의 실제 레포 라벨입니다.

### 예시

- `[QA][TB-9807] 게시글 상세 메시지 보내기 버튼 UI 개선` (라벨: `TYPE_QA`)
- `[Feature][CT-4688] Public room 검색 기능 추가` (라벨: `TYPE_FEATURE`)
- `[Debt][CT-5121] no-child 모듈 분리` (라벨: `TYPE_DEBT`)
- `[Bugfix][TB-9738] 스크롤아웃 배너 광고 단말 폭 비율 보정` (라벨: `TYPE_BUGFIX`)

> Jira 조회 실패 시 마지막 커밋 메시지 첫 줄을 제목으로 사용합니다.

---

## PR 본문 포맷 (4섹션 고정)

섹션 순서/이름/Optional 표기는 변경하지 않습니다.

```markdown
# Branch
<head 브랜치>

# Abstract
<아래 Abstract 작성 규칙 적용 — Feature/Debt 는 배경/목표/방식 권장 구조, Bugfix/QA/Hotfix 는 현상/원인/해결방법 필수>

# Description

## 주요 변경사항

### <카테고리 1>
- ...
- ...

### <카테고리 2>
- ...

# ScreenShot(Optional)
_게시자 직접 등록_
```

### Branch 작성 규칙

- **head(현재) 브랜치명만 평문 한 줄**로 출력합니다 — 티켓 키·base 브랜치 등 다른 요소는 넣지 않습니다
- **백틱(코드 스팬) 등 부호로 감싸지 않습니다** — 코드 스팬 안에서는 GitHub 의 Jira autolink 가 동작하지 않으므로, 평문으로 두어 브랜치명 속 티켓 키에 Jira 링크가 걸리게 합니다

#### Branch 예시

```markdown
# Branch
QA/TB-6056/TB-9807
```

### Abstract 작성 규칙

- 작업의 **목적과 맥락**만 짧게 서술 (구현 세부는 Description 에 위임)
- **Jira 티켓 제목을 그대로 인용하지 말 것** (예: "Jira 티켓 X에 대응하여..." 금지)
- 작업 결과물의 성격(임시/검증/실험 등)은 명시. "검증 완료 후 제거 예정" 등의 정리 계획도 포함

**구조 규칙** (배경/목표/방식 · 현상/원인/해결방법 — 요소 라벨 공통):

- 각 요소는 **"한 줄 요약 + 하위 들여쓰기 bullet"** 구조로 작성 — 한 줄 요약이 본질을 즉시 전달하고, 세부는 하위 bullet 로 내림
- **상위 라인(한 줄 요약·인과 단계 본문)에는 고유명사 금지** — 클래스/메서드/파일명/구체 값 등 코드 식별자는 **하위 들여쓰기 bullet 로 격리**합니다. 본문 호흡이 짧아져 리뷰어가 요소를 건너뛰며 스캔할 수 있게 하기 위함

#### Feature / Debt 권장 구조

`TITLE_TAG` 가 `Feature`, `Debt` 등(Bugfix/QA/Hotfix 제외)인 경우 아래 3요소 구조를 **권장**합니다. 한두 문장으로 끝나는 단순 작업은 2-3문장 단락 서술을 허용합니다 (단락이 길어지면 나눠 작성).

- **배경**: 작업이 필요해진 맥락 (상위 작업/마이그레이션/요구 변경 등)
- **목표**: 이 PR 이 달성하려는 결과
- **방식**: 구현 접근의 핵심 (세부 변경은 Description 의 주요 변경사항에 위임)

출력 포맷 (권장 형태):

```markdown
# Abstract

**배경**

- 요약: <작업이 필요해진 맥락 한 줄 — 고유명사 없이>
  - 관련 작업: <상위 작업/마이그레이션 맥락>

**목표**

- 요약: <PR 이 달성하려는 결과 한 줄>

**방식**

- 요약: <구현 접근의 핵심 한 줄 — 고유명사 없이>
  - `클래스/모듈`: <구체 대응 내용>
```

#### Bugfix / QA / Hotfix 추가 규칙

PR 제목 prefix(`TITLE_TAG`) 가 `Bugfix`, `QA`, `Hotfix` 인 경우 Abstract 에 아래 세 요소를 **반드시** 포함합니다 (`Feature`/`Debt` 는 위 **권장 구조** 적용).

- **현상**: 사용자/QA 관점에서 관찰된 잘못된 동작 (재현 조건, 영향 범위)
- **원인**: 근본 원인. **자동 도구는 diff 의 변경 전(before) 코드를 기반으로 추론** 하여 초안 작성
- **해결방법**: 무엇을 어떻게 변경하여 원인을 제거했는지

**원인의 인과 사슬 구조 (권장)**:

원인은 한 줄 요약(구조적 결함의 본질)으로 시작한 뒤, 아래 3단계 인과 사슬로 전개하는 것을 권장합니다.

1. **잠재 결함** — 코드 구조 문제 격리
2. **하류 영향** — 결함이 어떤 문제를 만들어내는지
3. **트리거** — 문제가 버그를 어떤 식으로 표면화시켰는지

> **권장 구조이며 고정이 아닙니다.** 각 단계는 diff·Jira 에서 실제 확인된 경우에만 사용합니다. 확인되지 않은 단계는 만들어 채우지 말고 **생략하거나 자유 단락으로 작성**합니다 (예: 인과 단계가 2개 이하로 끝나는 단순 결함은 해당 단계 생략).

출력 포맷 (인과 사슬 적용 시 권장 형태):

```markdown
# Abstract

**현상**

- 요약: <관찰된 잘못된 동작 한 줄 요약 — 고유명사 없이>
    - 재현 조건: <...>
    - 영향 범위: <...>

**원인**

- 요약: <구조적 결함의 본질 한 줄 요약 — 고유명사 없이>
  1. **잠재 결함** — <코드 구조 문제>
     - `클래스/메서드`: <구체 값/조건>
  2. **하류 영향** — <결함이 만들어내는 문제>
     - `식별자`: <구체 값>
  3. **트리거** — <버그가 표면화된 경로>
     - <재현 시퀀스/입력 값>

**해결방법**

- 요약: <변경의 핵심 한 줄 요약>
  - <세부 변경 1>
  - <세부 변경 2>
```

> Jira 티켓에 현상/원인 정보가 부족한 경우 도구는 원인 칸을 비워두지 말고 한 줄 요약 자리에 `**원인** (diff 기반 추정): ...` 형태로 추정임을 명시한 초안을 채워 넣고, 작성자가 확인·보정합니다.

### "주요 변경사항" 작성 규칙

- 카테고리는 `### <카테고리명>` H3 헤더로 구분 (`- **카테고리**: ...` 단일 라인 금지)
- 각 카테고리 하위에 변경 내용을 bullet으로 나열
- 카테고리 예시: `UI/UX 개선`, `핵심 기능 구현`, `이벤트 처리`, `리소스`, `버그 수정`, `리팩토링`, `테스트 자원 추가` 등 (작업 성격에 맞게 선택)
- **카테고리는 "코드 변경의 성격" 만 분류**. 검증 절차/정리 계획/작업 일정/리뷰 메모 같은 **메타 정보는 카테고리로 만들지 않고 Abstract 단락에 흡수**합니다.
  - ❌ 금지 예시: `### 검증 항목`, `### 정리 계획`, `### 작업 일정`, `### 리뷰 메모`
  - ✅ 허용 예시: `### 핵심 기능 구현`, `### 버그 수정`, `### 리팩토링`, `### 테스트 자원 추가`
- 변경 없는 카테고리는 출력하지 않음
- **"상세 변경 파일" 섹션은 작성하지 않음** (계층별 파일 나열 금지 — 가독성 저하)

### ScreenShot 작성 규칙 (표 변환)

PR **생성 시점**에는 placeholder(`_게시자 직접 등록_`)를 그대로 둡니다. GitHub 는 PR 본문 첨부(user-attachments)용 공식 업로드 API 를 제공하지 않으므로, 첨부는 아래 **2단계 플로우**로 처리합니다:

1. **업로드 (게시자, 수동 1회)**: Draft PR 생성 후 GitHub 웹에서 PR 본문에 미디어 파일을 드래그앤드롭 — GitHub 가 `[파일명](https://github.com/user-attachments/assets/<uuid>)` 형태의 링크로 변환해 저장
2. **표 재구성 (자동)**: Draft PR 생성 직후 업로드 여부를 질문(workflow.md 12단계)하고, "예" 선택 시 본문의 미디어 링크를 아래 규칙의 표로 컨버팅. 이후 추가 업로드·재시도는 "ScreenShot 표 정리해줘" 요청으로 재실행 (workflow.md 16단계)

#### 미디어 링크 인식 패턴 (4종)

| 패턴 | 형태 | 파일명 출처 |
|---|---|---|
| 링크 | `[파일명](https://github.com/user-attachments/assets/<uuid>)` — 동영상 드롭 시 기본 형태 | 링크 텍스트 |
| 이미지 마크다운 | `![파일명](https://github.com/user-attachments/assets/<uuid>)` | 링크 텍스트 |
| HTML `<img>` | `<img width="..." height="..." alt="파일명" src="https://github.com/user-attachments/assets/<uuid>" />` — 최근 GitHub 는 이미지 드롭 시 이 형태를 삽입 | `alt` 속성 |
| bare URL | `https://github.com/user-attachments/assets/<uuid>` 단독 라인 | 없음 → 사용자에게 질문 |

#### 표 변환 규칙

1. **헤더 행** = `*파일의 이름*` (원본 파일명, 이탤릭) — 아래 셀과 1:1 대응
2. **열 개수 = 미디어 개수에 비례** — 이미지만 / 비디오만 / 혼합 모두 동일 패턴의 **단일 표**
3. 셀 태그는 **파일명 확장자**로 판별 (user-attachments URL 에는 확장자가 없으므로 URL 로 판별하지 말 것):
   - `png` / `jpg` / `jpeg` / `gif` / `webp` → `<img src="URL">`
   - `webm` / `mp4` / `mov` → `<video src="URL"></video>`
4. **`<image>` 태그 사용 금지** — GitHub sanitizer 가 제거하므로 표준 `<img>` 만 사용
5. 파일명에 `|` 가 포함되면 `\|` 로 이스케이프

#### 출력 예시 (이미지 + 동영상 혼합)

```markdown
# ScreenShot(Optional)

| *스크린샷 2026-06-11 13.09.08.png* | *Screen_recording_20260610_165430.webm* |
|-|-|
| <img src="https://github.com/user-attachments/assets/aaaa-..."> | <video src="https://github.com/user-attachments/assets/231b98dd-..."></video> |
```

> user-attachments URL 은 `<img>`·`<video>` 모두 PR 본문에서 인라인 렌더링됩니다. complete intent / Sync PR 본문은 표 변환 대상이 아닙니다.

### 공통 작성 규칙

- 모든 PR 본문은 한국어 (기술 용어/클래스명/파일명은 영어 유지)
- **보고서 톤의 명사형 종결**을 기본으로 사용 — bullet/카테고리 항목은 "~ 수정", "~ 추가", "~ 분리" 처럼 명사로 끊어 작성
  - ✅ `- 베이스 브랜치 화이트리스트 도입`
  - ❌ `- 베이스 브랜치 화이트리스트를 도입했습니다`
- **고유명사 사용은 작업 설명에 꼭 필요한 경우에만** — 클래스/메서드/파일/모듈/티켓키 등 식별이 필요한 경우에만 명시. 단순 장식이나 컨텍스트 채우기 용도의 고유명사 나열 금지
- 변경 의도(why)와 구현 방식(how)을 함께 서술해 리뷰어가 맥락을 파악하기 쉽게 작성

### PR 본문 수정 공통 원칙 (생성 이후 모든 수정에 적용)

생성 이후의 PR 본문은 **사용자가 웹에서 수시로 직접 수정하는 공유 문서**입니다. 스킬이 만든 초안과 현재 본문은 다를 수 있다고 항상 가정하고, 본문을 수정하는 모든 작업(전면 업데이트·부분 수정·ScreenShot 표 재구성 등 일체)은 아래 원칙을 따릅니다.

1. **수정 직전 실제 본문 필수 재읽기** — 반드시 `gh pr view --json body` 로 현재 본문을 읽고, **그 본문만을 기반으로** 재조립합니다. 과거 생성본(`PR_DESCRIPTION_*.md`)·이전 재조립 파일·기억하고 있는 본문으로 어떤 섹션도 재구성하지 않습니다 (사용자의 웹 수정분이 유실됨)
2. **요청 범위 밖 보존** — 사용자가 요청한 변경 범위 밖의 내용(사용자가 추가한 단락·링크·첨부·서식 변경 포함)은 **한 글자도 지우거나 고치지 않고** 그대로 보존합니다
3. **전면 재작성 시 사용자 추가분 확인** — "본문 전면 업데이트" 요청이어도, 현재 본문에 스킬이 생성하지 않은 사용자 추가분이 감지되면 해당 부분을 인용해 보존/대체 여부를 사용자 질문으로 확인한 뒤 진행합니다

---

## 기본 적용 옵션 (Draft PR 생성 시 자동 부착)

| 항목 | work | complete |
|---|---|---|
| PR 상태 | **Draft 로 생성** 후 review open 여부 질문(Draft→Ready) | 동일|
| Assignee | `@me` (PR 작성자 본인) | `@me` |
| Label (타입) | `TYPE_FEATURE` / `TYPE_QA` / `TYPE_DEBT` / `TYPE_BUGFIX` (브랜치 prefix 기반 자동 결정) | `TYPE_COMPLETE`|
| Label (우선순위) | `PRIORITY_LOW` | **부착 안 함** |
| Label (리스크) | `RISK_HIGH(ApproveCount >= 2)` | **부착 안 함** |
| Milestone | 기본 미부착 — 생성 전(10단계) 질문 후 **설정 선택 시에만** 열린 마일스톤 목록에서 선택해 `--milestone` 부착 | 동일 |
| 본문 파일 | `PR_DESCRIPTION_*.md` 생성 후 `--body-file` | **생성 안 함** (`--body` 한 줄 직접) |

- work 의 타입 라벨은 위 "prefix → GitHub 라벨" 매핑 표에 따라 자동 부착
- **complete 는 `TYPE_COMPLETE` 하나만 부착** — `gh pr create` 에 `--label "TYPE_COMPLETE"` 만 넣고 그 외 라벨은 넣지 않음
- **마일스톤은 기본 미부착** — PR 생성 전(10단계) 사용자가 설정을 선택한 경우에만 레포의 **열린 마일스톤 목록**에서 선택받아 부착합니다 (없는 마일스톤을 새로 만들지 않음, work/complete 공통)
- 사용자가 명시적으로 다른 값을 지정한 경우에만 override
- (work) 레포지토리에 해당 라벨이 없으면 해당 라벨만 누락하고 PR 생성은 계속 진행 (Assignee 는 항상 포함)
- (work) 라벨명에 공백·괄호가 포함되므로 `gh pr create --label` 인자에 반드시 따옴표를 사용

### Draft → Ready 플로우 (work / complete 공통)

PR은 항상 `--draft` 로 생성합니다(리뷰어 자동 알림 방지). 생성 직후 사용자 질문으로 "지금 review 를 open(Ready for review) 할까요?" 를 물어:
- **지금 open** → `gh pr ready <PR번호>` 로 Draft 해제
- **Draft 유지** → PR 링크만 안내하고 종료 (기존 work 동작과 동일)

---

## 변경 파일 분류 기준

PR 본문 "주요 변경사항" 작성 시 변경 파일을 다음 아키텍처 계층으로 분류해 카테고리를 도출합니다:

- **Domain**: `domain-*`, `domain/*`
- **Data**: `data-*`, `data/*`
- **Feature**: `feature-*`, `ui/*`
- **Core/Common**: `core/*`, `shared/*`, `blind-common*`, `test-common`
- **US Market**: `blind-us/*`
- **Resources**: `*/res/*`, drawable/strings/colors/layouts 등

---

## 실행 절차

`generate-pr-auto` 호출 또는 "현재 브랜치 PR 만들어줘" 요청 시 아래 0~16단계를 순서대로 수행합니다. **각 단계의 정확한 bash/MCP/gh 명령과 검증 로직은 [references/workflow.md](references/workflow.md) 를 참조하세요.**

| 단계 | 내용 |
|---|---|
| 0 | 도구 사전 준비 — 실행 환경에 따라 필요한 질문·조회·실행 기능의 가용성 확인 |
| 1 | 현재 브랜치 감지 (`git rev-parse --abbrev-ref HEAD`) |
| 1.5 | **intent 판별** — 위 **PR intent 판별 규칙** 으로 work / complete 결정 |
| 2 | 베이스 브랜치 결정 — work: **베이스 추론 규칙**(merge-base) / complete: `release/<version.name>` 고정 |
| 3 | Jira 티켓 키 추출 — 위 **Jira 티켓 키 추출 규칙** |
| 4 | Jira 정보 조회 (`getJiraIssue`) — 실패 시 커밋 메시지로 graceful degrade |
| 5 | PR 타입 결정 — work: **prefix → 제목 태그/라벨 매핑** / complete: `TITLE_TAG=Complete` |
| 6 | (work 만) Diff 분석 (`git diff --stat`·`--name-status`, `git log`) — 위 **변경 파일 분류 기준** — complete 는 이 단계를 건너뛰고 7단계로 |
| 7 | PR 제목 생성 — 위 **PR 제목 포맷** (complete 는 `[Complete][<티켓>] <summary>`) |
| 8 | PR 본문 생성 — work: **4섹션 포맷** / complete: **한 줄 본문(md 파일 미생성)** |
| 9 | (work 만) `PR_DESCRIPTION_<티켓키>.md` 파일 저장 — complete 는 파일 생성 안 함 |
| 10 | **마일스톤 설정 여부 질문(사용자 질문)** — 예: 열린 마일스톤 목록 조회 후 선택 → 11단계에서 `--milestone` 부착 / 아니오: 생략 (work/complete 공통) |
| 11 | **사용자 확인(사용자 질문) 후** `gh pr create --draft` 로 Draft PR 생성 — work: 라벨 부착 / complete: `--label "TYPE_COMPLETE"` 만, `--body` 한 줄 직접 |
| 12 | (work 만) **ScreenShot 업로드 확인(사용자 질문)** — "PR 본문에 스크린샷/동영상을 업로드하시면 표로 컨버팅해 드립니다. 업로드 하셨나요?" → 예: 본문 미디어 링크를 표로 컨버팅(`gh pr edit`) 후 13단계로 / 아니오: 그대로 13단계로 |
| 13 | (work 만) **코드리뷰 수행 여부 질문(사용자 질문)** → 예: `review-pr` 실행(로컬 리포트 `pr_<N>_code_review.md`) → 리포트 미리보기 후 **게시 확인(사용자 질문)** → finding 을 `path:line` 인라인 코멘트로 게시 → 14단계로 / 아니오: 바로 14단계로 — complete 는 이 단계 없음 (게시 도구·`event=COMMENT` 고정·실패 처리 상세는 [workflow.md](references/workflow.md) 13단계 정본 참조) |
| 14 | **review open 여부 질문(사용자 질문)** → open 선택 시 `gh pr ready <PR번호>` (work/complete 공통) |
| 15 | (work 만) 임시 `PR_DESCRIPTION_*.md` 정리 — complete 는 해당 없음 |
| 16 | **(재실행·후속 요청용)** ScreenShot 표 재구성 — 12에서 "아니오" 후 늦은 업로드·재시도·추가 병합 시 "ScreenShot 표 정리해줘" 요청으로 단독 수행 (`gh pr view` → `gh pr edit`) |

> 11단계는 외부 시스템에 영향을 주므로 사용자 확인 없이는 절대 PR을 생성하지 않으며, PR은 항상 `--draft` 로 생성합니다. Draft 해제(14단계)는 사용자가 "지금 open" 을 선택한 경우에만 수행합니다.
>
> 13단계의 인라인 코멘트 게시도 외부 시스템 쓰기이므로, **리뷰 수행 여부 질문과 게시 직전 확인** 두 번의 사용자 질문 승인 없이는 절대 게시하지 않습니다. 게시는 `event=COMMENT` 로만 수행하며 PR 을 `APPROVE`/`REQUEST_CHANGES` 로 바꾸지 않습니다. `review-pr` 스킬 자체는 어떤 경우에도 게시하지 않으며(read-only), 게시 책임은 본 스킬에만 있습니다.
>
> 13단계(코드리뷰)는 **work intent 한정**입니다. complete intent 와 Sync PR(별도 스킬 [generate-sync-pr](../generate-sync-pr/SKILL.md))에는 이 단계가 **적용되지 않습니다** — 둘 다 코드 변경 리뷰 대상이 아니므로 Draft 생성 후 바로 review open 질문으로 진행합니다.

---

## 발동 조건

이 스킬은 다음 질문/요청 시 자동 발동됩니다:

- "현재 브랜치 PR 만들어줘"
- "draft PR 생성해줘"
- "complete PR 만들어줘" / "QA 끝났으니 릴리즈에 머지 PR" (complete intent)
- "ScreenShot 표 정리해줘" / "스크린샷 표로 재구성" (PR 본문 미디어 링크 → 표 변환, 16단계)
- "(PR 생성 직후) 코드리뷰해서 PR에 코멘트 달아줘" / "(생성 흐름 안에서) 리뷰 결과 인라인 코멘트로 게시" (Draft 생성 후 `review-pr` 실행 → 인라인 코멘트 게시, 13단계) — **이미 존재하는 PR 만 단독 리뷰**하려면 본 스킬이 아니라 [`review-pr <PR번호>`](../review-pr/SKILL.md) 사용
- `generate-pr-auto` 또는 `generate-pr-auto complete` 명시 요청 시
- 베이스 브랜치 자동 추론 / 네이밍 컨벤션 관련 질문
- PR 제목/본문 포맷, 라벨 매핑 관련 질문

## 관련 파일

- 단계별 상세 실행 절차: [references/workflow.md](references/workflow.md)
- Sync PR 생성(별개 액션): [generate-sync-pr](../generate-sync-pr/SKILL.md)
- 버전 소스: `app/config/version.properties` (`version.name=*`)
