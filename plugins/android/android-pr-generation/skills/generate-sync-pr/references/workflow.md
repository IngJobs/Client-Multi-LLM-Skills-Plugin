# Sync PR 자동 생성 — 상세 실행 절차

`generate-sync-pr` 스킬이 따르는 **단계별 실행 절차**입니다. release 버전을 타겟 브랜치로 동기화하는 sync 브랜치를 만들고, 타겟을 머지해 충돌을 감지한 뒤, 사용자 확인을 거쳐 **Draft PR** 을 생성하고 review open 여부를 묻습니다.

> 브랜치 슬러그·제목 포맷·라벨 세트·충돌 라벨 분기 등 **컨벤션 정의는 `SKILL.md`** 를 단일 출처로 참조합니다. 이 문서는 그 컨벤션을 적용하는 정확한 bash/MCP/gh 명령과 검증 로직만 정의합니다.

---

## 목차

- **0단계 — 도구 사전 준비**
- **1~8단계 — Sync 워크플로우**
- **품질 기준 / 주의사항**

---

### 0단계 — 도구 사전 준비

[실행 환경 지침](execution-environment.md)에 따라 사용자 질문, Git/gh 실행과 GitHub PR 생성 기능의 가용성을 확인합니다. 지금 필요한 기능만 준비하며, 선택적 단계의 도구는 그 단계를 선택했을 때 확인합니다.

PR 생성에는 기존 `gh` 경로를 사용할 수 있습니다. GitHub MCP를 사용할 경우 실제 스키마에서 같은 기능을 확인합니다.

## 1단계 — 소스 버전·타겟 결정 (인자 우선, 대화형 폴백)

```
인자 형식: sync <버전> into <타겟>
  예) sync 3.86.0 into master
      sync 3.87.0 into TB-8906   (feature/TB-8906/root 의미)
      sync 3.86.0 into 3.87.0    (release/3.87.0 의미)
```

- **소스 버전**: 인자에 있으면 사용, 없으면 `app/config/version.properties` 의 `version.name` 으로 추론.
- **타겟**: 인자에 있으면 사용, 없으면 사용자 질문으로 (master / 다음 release / feature root) 선택.
- 타겟 해석:
  - `master` → base `master`
  - `<버전>` 형태(예: `3.87.0`) → base `release/3.87.0`
  - `<티켓>`(예: `TB-8906`) 또는 `<티켓> root` → base `feature/<티켓>/root`

## 2단계 — head/base 슬러그 산출

`SKILL.md` 의 **타겟 → 브랜치 슬러그 매핑** 표를 적용합니다.

| 타겟 | base | head |
|---|---|---|
| master | `master` | `sync/<버전>-into-master` |
| 다음 release | `release/<다음버전>` | `sync/<버전>-into-<다음버전>` |
| feature root | `feature/<티켓>/root` | `sync/<버전>-into-<티켓>-root` |
| feature root (티켓 강조) | `feature/<티켓>/root` | `sync/<티켓>/<버전>-into-root` |

```bash
git rev-parse --verify origin/release/<버전>   # 소스 존재 확인
git rev-parse --verify origin/<base>            # 타겟 존재 확인
```

- 둘 중 하나라도 없으면 사용자 질문으로 정정.

## 3단계 — 소스에서 sync 브랜치 생성

먼저 작업트리가 클린한지 확인합니다. 변경이 남아 있으면 checkout 이 실패하거나 미커밋 변경이 sync 브랜치로 섞일 수 있으므로 중단하고 사용자에게 안내합니다.

```bash
[ -n "$(git status --porcelain)" ] && { echo "작업트리에 미커밋 변경 존재 — 정리 후 재시도"; exit 1; }
git fetch origin
git checkout -b "<head 슬러그>" "origin/release/<버전>"
```

## 4단계 — 타겟 머지 + 충돌 감지 (라벨 분기)

소스 기반 sync 브랜치에 타겟을 머지하여 충돌 여부를 판정합니다.

```bash
git merge --no-ff "origin/<base>"
echo "exit=$?"
git ls-files -u   # 비어있지 않으면 충돌
```

- **충돌 없음** (머지 성공) → 타입 `TYPE_SYNC(Conflict 없음)` + 리스크 `RISK_LOW(ApproveCount >= 1)`
- **충돌 발생** → 타입 `TYPE_SYNC(Conflict 발생. 관련 작업자에게 멘션 필수)` + 리스크 `RISK_HIGH(ApproveCount >= 2)`
  - 사용자에게 충돌 파일을 안내하고 **직접 해결을 요청**합니다. 해결·커밋 완료를 확인하기 전에는 5단계(push)로 진행하지 않습니다.
  - 자동으로 `git merge --abort` 하지 않습니다(컨벤션상 충돌 해결 커밋을 sync 브랜치에 남김).

## 5단계 — push

```bash
git push -u origin "<head 슬러그>"
```

## 6단계 — 제목 생성 (본문 비움)

```
제목: [Sync] <버전> into <타겟표시>
      (티켓 동반 시 [Sync][<티켓>] <버전> into <타겟표시>)
본문: (비움)
```

- `<타겟표시>` 는 사용자가 인지하는 명칭(`master`, `3.87.0`, `TB-9759` 등)을 사용.

## 7단계 — 사용자 확인 후 Draft PR 생성

**필수**: 외부 시스템에 영향을 주므로 반드시 사용자 질문으로 확인합니다.

질문 예시:
> "Sync PR 정보가 준비되었습니다.
> - 제목: `[Sync] 3.86.0 into master`
> - base: `master` / head: `sync/3.86.0-into-master`
> - 충돌: 없음 → 라벨 `TYPE_SYNC(Conflict 없음)`
>
> 지금 Draft PR을 생성할까요?"

**승인 시 (`--draft` 로 생성, 본문 비움)**:

```bash
gh pr create \
  --draft \
  --title "[Sync] ${VERSION} into ${TARGET_DISPLAY}" \
  --body "" \
  --base "${BASE_BRANCH}" \
  --head "${HEAD_BRANCH}" \
  --assignee @me \
  --label "TYPE_SYNC(Conflict 없음)" \
  --label "PRIORITY_LOW" \
  --label "RISK_LOW(ApproveCount >= 1)" \
  --label "SkipUnitTest"
```

- **충돌이 있었던 경우** 라벨 두 개를 변경: 타입 라벨 → `"TYPE_SYNC(Conflict 발생. 관련 작업자에게 멘션 필수)"`, 리스크 라벨 → `"RISK_HIGH(ApproveCount >= 2)"`.
- 항상 `--draft` 로 생성.
- 공백·괄호 포함 라벨은 따옴표 필수.

**거부 시**: push 된 sync 브랜치 이름과 준비한 명령을 안내하고 종료.

## 8단계 — review open 여부 질문 후 Ready 전환

Draft PR 생성에 성공한 직후 수행합니다. `gh pr create` 가 출력한 PR URL/번호를 확보해 둡니다.

**사용자 확인 질문 예시**

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

---

## 품질 기준

- PR 생성 전 사용자 확인 필수
- 항상 **`--draft` 로 생성**한 뒤, review open 여부를 별도 사용자 질문으로 물어 `gh pr ready` 로만 Draft 해제
- 기본 Assignee(`@me`)·라벨 세트를 항상 포함 (사용자 override 시 제외)
- 충돌 미해결 상태로 push/PR 생성 금지. 충돌 라벨이 실제 머지 결과와 일치하는지 확인
- 본문은 비움 (제목으로 의미 충분)

## 주의사항

- **0단계(도구 사전 준비)** — 실행에 필요한 기능의 가용성을 확인하고, 선택적 기능은 해당 단계에서 확인합니다.
- `gh pr create` 실행 전 사용자 확인 필수, **생성은 항상 `--draft`** — review open 은 생성 후 별도 질문으로만 진행
- `gh pr ready` 는 사용자가 "지금 open" 을 선택한 경우에만 실행 (자동 open 금지)
- 라벨명에 공백·괄호가 포함되므로 `--label` 인자에 반드시 따옴표 사용
- `gh` CLI 미설치/미인증 시 에러 안내 후 종료 (이미 push 된 브랜치가 있으면 그 이름도 안내)
