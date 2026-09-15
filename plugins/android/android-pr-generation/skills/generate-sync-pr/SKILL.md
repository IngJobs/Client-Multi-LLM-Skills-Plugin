---
name: generate-sync-pr
description: Teamblind Android 의 Sync PR(특정 release 버전을 master/다음 release/feature root 로 동기화)을 자동 생성. 소스에서 sync 브랜치 생성·타겟 머지·충돌 감지·라벨 결정까지 수행. Sync PR의 브랜치 슬러그·제목·충돌 라벨 컨벤션도 정의. "sync PR 만들어줘"·"3.86.0 master 로 sync"·"릴리즈 sync" 요청이나 sync 컨벤션 질문 시 사용.
---

# Teamblind Android — Sync PR 자동 생성

`generate-sync-pr` 를 지정해 요청하거나 "sync PR 만들어줘" 류 요청 시 발동되는 스킬입니다. 특정 release 버전을 다른 브랜치(`master` / 다음 release / `feature/*/root`)로 동기화하는 **Sync PR** 을 만듭니다.

> 단계별 상세 실행 절차(정확한 bash/MCP/gh 명령과 검증 로직)는 [references/workflow.md](references/workflow.md) 를 참조하세요. 이 문서는 그 절차가 따르는 컨벤션의 단일 출처(canonical)입니다.

실행 전에 [실행 환경 지침](references/execution-environment.md)을 읽고, 현재 환경에 맞는 도구·질문·스킬 참조 방식을 적용합니다.

## generate-pr-auto 와의 차이 (왜 별도 스킬인가)

작업용/Complete PR을 만드는 [generate-pr-auto](../generate-pr-auto/SKILL.md) 는 **현재 브랜치를 읽어** PR을 생성하는 읽기전용 흐름입니다. 반면 Sync PR은 현재 브랜치와 무관하게 **새 sync 브랜치를 생성하고 타겟을 머지(git 상태 변경)** 한 뒤, **충돌 발생 여부로 라벨이 갈리는** 별개 액션입니다. Jira 조회·본문도 없습니다. 이 본질적 차이 때문에 별도 스킬로 둡니다.

> **Draft → Ready 플로우**: PR을 먼저 `--draft` 로 생성합니다(리뷰어 자동 알림 방지). 생성 직후 사용자 질문으로 "지금 review 를 open(Ready for review) 할까요?" 를 물어, open 선택 시 `gh pr ready <PR번호>` 로 Draft 를 해제합니다. Draft 유지 선택 시 PR 링크만 안내하고 종료합니다.

> **코드리뷰 자동 게시는 해당 없음**: Sync PR 은 브랜치 간 머지 동기화일 뿐 코드 변경 리뷰 대상이 아니므로, [generate-pr-auto](../generate-pr-auto/SKILL.md) 의 코드리뷰 수행·인라인 코멘트 자동 게시(13단계)를 **수행하지 않습니다**. Draft 생성(7단계) 후 곧바로 review open 질문(8단계)으로만 진행합니다.

---

## Sync PR 컨벤션

| 항목 | 규칙 |
|---|---|
| head | `sync/<버전>-into-<타겟슬러그>` (티켓 동반 시 `sync/<티켓>/<버전>-into-root`) |
| base | 타겟 브랜치: `master` / `release/<다음버전>` / `feature/<티켓>/root` |
| 제목 | `[Sync] <버전> into <타겟>` (티켓 시 `[Sync][<티켓>] <버전> into <타겟>`) |
| 본문 | **비움** |
| PR 상태 | **Draft 로 생성** 후 review open 여부 질문 |
| Assignee | `@me` |
| Label | `SkipUnitTest`, `PRIORITY_LOW`, + 충돌 여부에 따른 리스크/타입 라벨(아래) |

### 충돌 여부에 따른 라벨 분기 (필수)

소스 release 에서 만든 sync 브랜치에 타겟을 머지할 때 **충돌 발생 여부로 타입 라벨과 리스크 라벨이 함께 갈립니다.**

| 충돌 | 타입 라벨 | 리스크 라벨 |
|---|---|---|
| 없음 | `TYPE_SYNC(Conflict 없음)` | `RISK_LOW(ApproveCount >= 1)` |
| 발생 | `TYPE_SYNC(Conflict 발생. 관련 작업자에게 멘션 필수)` | `RISK_HIGH(ApproveCount >= 2)` |

### 타겟 → 브랜치 슬러그 매핑

| 타겟 종류 | base 브랜치 | head 슬러그 예시 |
|---|---|---|
| master | `master` | `sync/3.86.0-into-master` |
| 다음 release | `release/3.87.0` | `sync/3.86.0-into-3.87.0` |
| feature root | `feature/TB-9759/root` | `sync/3.86.0-into-TB-9759-root` |
| feature root (티켓 동반) | `feature/TB-8906/root` | `sync/TB-8906/3.87.0-into-root` |

- 소스 버전은 인자 우선, 누락 시 `app/config/version.properties` 의 `version.name` 으로 추론.
- 타겟은 인자 우선, 누락 시 사용자 질문으로 (master / 다음 release / feature root) 선택.
- **본문은 비웁니다.** 제목만으로 의미가 충분한 운영 PR입니다.
- `PRIORITY_RIGHT_NOW` 등 우선순위 상향은 운영자 수동 판단이므로 자동 부착하지 않습니다.

---

## 기본 적용 옵션

| 항목 | 기본값 |
|---|---|
| PR 상태 | **Draft 로 생성** → review open 질문 |
| Assignee | `@me` |
| 타입 라벨 | `TYPE_SYNC(Conflict 없음)` / 충돌 시 `TYPE_SYNC(Conflict 발생. 관련 작업자에게 멘션 필수)` |
| 우선순위 라벨 | `PRIORITY_LOW` |
| 리스크 라벨 | 충돌 없음: `RISK_LOW(ApproveCount >= 1)` / 충돌 발생: `RISK_HIGH(ApproveCount >= 2)` |
| 공통 라벨 | `SkipUnitTest` |

- 라벨명에 공백·괄호가 포함되므로 `gh pr create --label` 인자에 반드시 따옴표를 사용합니다.
- 레포지토리에 해당 라벨이 없으면 해당 라벨만 누락하고 PR 생성은 계속 진행 (Assignee 는 항상 포함).
- 사용자가 명시적으로 다른 값을 지정한 경우에만 override.

---

## 실행 절차 (요약)

`generate-sync-pr` 호출 시 아래 순서로 수행합니다. **각 단계의 정확한 bash/MCP/gh 명령과 검증 로직은 [references/workflow.md](references/workflow.md) 를 참조하세요.**

| 단계 | 내용 |
|---|---|
| 0 | 도구 사전 준비 — 실행 환경에 따라 필요한 질문·조회·실행 기능의 가용성 확인 |
| 1 | 소스 버전·타겟 결정 (인자 우선, 대화형 폴백) |
| 2 | head/base 슬러그 산출 |
| 3 | 소스에서 sync 브랜치 생성 |
| 4 | 타겟 머지 + 충돌 감지 → TYPE_SYNC 라벨 결정 |
| 5 | push |
| 6 | 제목 생성 (본문 비움) |
| 7 | **사용자 확인(사용자 질문) 후** `gh pr create --draft` |
| 8 | review open 여부 질문 → open 선택 시 `gh pr ready <PR번호>` |

> 충돌이 미해결인 상태로는 push/PR 생성을 진행하지 않습니다.

---

## 발동 조건

- "sync PR 만들어줘" / "3.86.0 master 로 sync" / "릴리즈 sync PR"
- `generate-sync-pr` 명시 요청 시
- Sync PR 컨벤션(브랜치 슬러그, 충돌 라벨, 제목 포맷) 관련 질문

## 관련 파일

- 단계별 상세 실행 절차: [references/workflow.md](references/workflow.md)
- 작업용/Complete Draft PR 생성(다른 흐름): [generate-pr-auto](../generate-pr-auto/SKILL.md)
- 버전 소스: `app/config/version.properties` (`version.name=*`)
