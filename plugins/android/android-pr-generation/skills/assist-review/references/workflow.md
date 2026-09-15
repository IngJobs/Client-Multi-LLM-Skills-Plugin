# 리뷰어 보조 — 상세 실행 절차

`assist-review` 스킬이 따르는 **단계별 실행 절차**입니다. PR 정보를 수집하고, 격리 워크트리를 만들고, PR 변경 구간에 경계 주석을, 논리 단위마다 마커를 심고, 읽는 순서를 안내한 뒤 사용자의 요청을 기다리다가, `마무리` 시점에 코멘트를 수확해 확인을 받고 인라인 코멘트로 게시하고 워크트리를 제거합니다.

> 컨셉·AI 발화 경계·마커/경계 포맷·진행 방식·게시 규칙은 모두 **[`SKILL.md`](../SKILL.md)** 를 단일 출처로 참조합니다. 이 문서는 그 규칙을 적용하는 정확한 `gh`/`git` 명령과 상태 관리만 정의합니다. **여기서 포맷을 다시 정의하지 않습니다.**

---

## 핵심 원칙 — 격리 모델

- **원본 리포는 읽기만 합니다.** 쓰기는 전부 `~/claude-review/<repo>/pr-<N>/` 워크트리 안에서만 일어납니다.
- 워크트리는 **PR head 에 detached HEAD** 로 만듭니다. 로컬 브랜치가 생기지 않으므로 실수로 push 할 대상 자체가 없고, 정리 후 잔여물이 0입니다.
- HEAD 가 PR head 이므로 **`git diff` = AI 가 심은 것 + 사용자가 쓴 것** 입니다. 이 성질이 수확의 근거이자, IDE 변경 내비게이션이 마커 사이를 건너뛰게 만드는 장치입니다.
- 마커·경계는 워크트리에만 존재하므로 **커밋할 이유가 없습니다.** 워크트리 제거 = 소멸입니다.

아래에서 쓰는 변수:

```bash
REPO=$(gh repo view --json name -q .name)      # 예: android_v2
OWNER=$(gh repo view --json owner -q .owner.login)
ROOT=$(git rev-parse --show-toplevel)           # 원본 리포 루트
WT="$HOME/claude-review/$REPO/pr-<N>"           # 워크트리
DRAFT="$HOME/claude-review/$REPO/pr-<N>-draft.md"
```

---

## 워크플로우

### 0단계 — 도구 사전 준비

```bash
gh auth status
git rev-parse --show-toplevel   # 대상 리포 루트
git status --short              # 원본 트리 상태 스냅샷 (마지막에 동일해야 함)
```

- `gh` 미설치/미인증이면 안내하고 **중단**합니다.
- 현재 위치가 리뷰 대상 리포가 아니면 중단하고 이동을 안내합니다.
- `git status --short` 결과를 기록해 둡니다. **5단계 종료 시 이것과 같아야** 원본 무손상이 증명됩니다. dirty 한 파일이 이미 있어도 그대로 두고 건드리지 않습니다.
- 사용자 질문과 필요한 조회 기능은 [실행 환경 지침](execution-environment.md)에 따라 준비합니다.

### 0.5단계 — 질문 재료 SSOT 로드

`review-pr` 과 같은 SSOT를 읽되 **용도가 다릅니다.** 컨벤션 위반을 판정하기 위해서가 아니라 `[확인 필요]` **질문의 재료**로만 씁니다(SKILL.md `프로젝트 컨벤션(SSOT) 사용 방침`).

실행 환경의 스킬 참조 절차로 `android-arch-patterns`·`android-code-quality`·`android-data-models`의 실제 본문을 읽습니다. 대상 저장소의 프로젝트 지침도 적용 범위에 맞게 확인합니다. 읽은 경로 또는 미설치·발견 실패·접근 거부 사유를 기록합니다.

없으면 질문의 폭이 좁아질 뿐이며 **워크플로우는 멈추지 않습니다.**

### 1단계 — PR 정보 수집

```bash
gh pr view <N> --json title,body,author,headRefName,baseRefName,files,additions,deletions,changedFiles,commits
gh pr diff <N> --name-only            # 마커 대상 판별용
gh api user -q .login                 # 본인 계정 (셀프리뷰 판별)
```

- `commits` 는 논리 단위 분할의 **1차 후보**입니다(SKILL.md `논리 단위 분할`).
- `author` 가 본인이면 **셀프리뷰는 이 스킬의 범위 밖**임을 알리고 계속할지 확인합니다.
- `body` 가 비어 있으면 커밋 메시지·연결 티켓으로 의도를 추정하고, 추정임을 밝힙니다.

### 2단계 — 격리 워크트리 생성

**먼저 2.5단계(재개 감지)로 경로 존재 여부를 확인합니다.** 이미 있으면 새로 만들지 않습니다.

```bash
mkdir -p "$HOME/claude-review/$REPO"

git fetch origin "pull/<N>/head"                       # 포크 PR 도 동일하게 동작
HEAD_SHA=$(git rev-parse FETCH_HEAD)

BASE_REF=$(gh pr view <N> --json baseRefName -q .baseRefName)
git fetch origin "$BASE_REF"
BASE_SHA=$(git merge-base FETCH_HEAD "$HEAD_SHA")      # 경계 주석 계산용

git worktree add --detach "$WT" "$HEAD_SHA"
```

- `--detach` 는 **필수**입니다. 로컬 브랜치를 만들지 않아 push 대상이 없고, 정리 후 잔여 브랜치가 남지 않습니다.
- HEAD 가 PR head 이므로 생성 직후 `git -C "$WT" diff` 는 **비어 있어야** 합니다. 비어 있지 않으면 잘못 만든 것입니다.
- `$BASE_SHA` 는 3단계 경계 주석 계산에, `$HEAD_SHA` 는 게시 시 `commit_id` 에 씁니다. 세션이 끊겨도 복구할 수 있게 워크트리 **밖**에 남깁니다:

```bash
printf '%s\n%s\n' "$HEAD_SHA" "$BASE_SHA" > "$HOME/claude-review/$REPO/pr-<N>.sha"
```

- Gradle 동기화용 로컬 설정을 복사합니다(있을 때만, gitignore 대상이라 diff 를 더럽히지 않습니다):

```bash
[ -f "$ROOT/local.properties" ] && cp "$ROOT/local.properties" "$WT/local.properties"
```

- 경로를 안내하고, macOS 라면 IDE 로 열어줄지 **묻고 나서** 실행합니다:

```bash
open -na "Android Studio" --args "$WT"
```

> 리포에 post-checkout 훅이 있으면 워크트리에서 실패 메시지를 낼 수 있습니다(`.git` 이 디렉터리가 아니라 파일이라서). 워크트리 생성 자체는 성공하므로 무시하고 진행합니다.

### 2.5단계 — 재개 감지

워크트리 생성 **전에** 실행합니다. 경로가 이미 있으면 마커를 다시 심지 않고 이어갑니다.

```bash
[ -d "$WT" ] && echo "기존 워크트리 있음"

# 게시·경계 계산 기준 복구
read HEAD_SHA BASE_SHA < <(tr '\n' ' ' < "$HOME/claude-review/$REPO/pr-<N>.sha")
# 파일이 없으면: HEAD_SHA=$(gh pr view <N> --json headRefOid -q .headRefOid)

# 심어둔 마커의 위치·번호 (지도 재구성용)
grep -rno "TODO(review [0-9]*/[0-9]*[^)]*)" "$WT" | sort -t: -k1,1
```

- 마커에서 지도를 복원해 **다시 출력**하는 것으로 끝입니다.
- **진행 상태는 추적하지 않습니다**(SKILL.md `재개`).
- 워크트리는 있는데 마커가 0개면 3단계부터 다시 합니다.
- 워크트리 경로는 있는데 `git worktree list` 에 없으면(수동 삭제 흔적) `git worktree prune` 후 새로 만듭니다.

### 3단계 — 경계 주석 + 마커 삽입, 지도 출력

**3-1. PR 변경 구간에 경계 주석을 두릅니다.**

`$BASE_SHA`↔`$HEAD_SHA` diff 의 hunk 를 PR head 좌표로 읽어, 각 구간을 감쌉니다. 포맷은 SKILL.md `PR 변경 구간 경계 주석`.

```bash
git -C "$WT" diff -U0 "$BASE_SHA" "$HEAD_SHA"   # @@ -a,b +c,d @@ 의 +c,d 가 head 좌표
```

- **파일마다 아래에서 위로 삽입**합니다. 그래야 앞서 삽입한 줄 때문에 좌표가 밀리지 않습니다.
- 3줄 이내로 붙어 있는 hunk 는 하나로 병합해 감쌉니다(경계 수 절감).
- `d == 0` 인 hunk 는 순수 삭제이므로 한 줄짜리 표시만 넣습니다.
- 들여쓰기는 감싸는 첫 줄에 맞춥니다.

**3-2. 논리 단위를 정하고 마커를 심습니다.**

1. `gh pr diff <N>` 과 커밋 단위를 근거로 논리 단위 m 개를 만듭니다(SKILL.md `논리 단위 분할`). **m > 20 이면 3지선다를 사용자 질문으로 먼저 묻습니다.**
2. 단위마다 대표 지점 1곳 + 참조 지점 0곳 이상을 정합니다. 대표는 그 단위의 의도가 가장 잘 드러나는 곳입니다.
3. **워크트리 안의 파일에만** 마커를 넣습니다. 위치는 그 단위 **경계 주석의 바로 위**입니다. 마커 불가 파일은 `[마커 없음]` 채팅 전용 단위로 남깁니다.
4. 참조 마커의 `— 본문 <파일>:<라인>` 은 **모든 삽입이 끝난 뒤** 실제 라인으로 채웁니다. 같은 파일명이 여러 모듈에 있으면 모듈 경로까지 적습니다.

**3-3. 삽입 검증:**

```bash
grep -rno "TODO(review [0-9]*/[0-9]*[^)]*)" "$WT" | wc -l   # 대표+참조 총합과 일치
grep -rn "\[변경사항 요약\]" "$WT" | wc -l                   # 대표 마커 수 = m - (마커 없음 단위 수)
git -C "$WT" diff --shortstat                                # 삽입분만 (삭제 0줄이어야 함)
git -C "$ROOT" status --short                                # 0단계 스냅샷과 동일
```

삽입분 외 변경이 없는지 직접 확인합니다:

```bash
git -C "$WT" diff | grep "^[+-]" | grep -vE "^(\+\+\+|---)" \
  | grep -v "PR 변경\|삭제됨\|TODO(review \|\[변경사항 요약\]\|\[확인 필요\]"
# 출력이 비어야 정상
```

**3-4. 지도 출력.** 포맷은 SKILL.md `지도 — 읽는 순서`. **`코멘트 남기는 법` 블록을 빠뜨리지 않습니다** — 이게 없으면 리뷰어는 마커를 읽고도 자기 판단을 어디에 어떻게 남기는지 알 수 없습니다. 재개(2.5단계)로 지도를 다시 낼 때도 함께 냅니다.

### 4단계 — 사용자 주도 읽기 (요청 대기)

지도를 출력한 뒤 **AI 는 물러납니다.** 명령 형식·`더 설명` 누적 단계는 SKILL.md `진행 방식` 을 따릅니다.

- **먼저 말을 걸지 않습니다.** 진행 상황을 캐묻거나 다음 단위를 밀지 않습니다.
- `지적 <n> <내용>` 처리: 해당 단위 대표 지점 **위에 주석 한 줄**을 넣습니다. 사용자가 직접 쓰는 것과 형태가 같아야 수확 경로가 하나로 유지됩니다.
- `더 설명` 1차·2차에서 워크트리 파일을 읽는 것은 자유지만, **읽은 내용으로 판정하지 않습니다.**
- 다른 주제로 샜다가 돌아왔을 때 사용자가 위치를 잃었으면, "대기 중" 이라고 참조하지 말고 **지도를 다시 출력합니다.**
- 5단계로 넘어가는 트리거는 **사용자의 `마무리`** 뿐입니다.

### 5단계 — 수확 · 확인 · 게시 · 정리

**5-1. 수확.** 근거는 `git diff` 입니다. HEAD 가 PR head 이므로 추가된 줄 = AI 삽입분 + 사용자가 쓴 것이고, PR 작성자가 원래 써둔 주석은 커밋돼 있어 섞이지 않습니다.

```bash
git -C "$WT" diff -U0 | awk '
/^diff --git/ { f=$3; sub("^a/","",f) }
/^@@/ { match($0, /-[0-9]+/); a=substr($0, RSTART+1, RLENGTH-1); next }
/^\+/ && !/^\+\+\+/ {
  l=substr($0,2)
  if (l ~ /TODO\(review |\[변경사항 요약\]|\[확인 필요\]|PR 변경 시작|PR 변경 끝|삭제됨/) next
  printf "%s|%d|%s\n", f, a+1, l
}'
```

| 추가된 줄 | 분류 |
|---|---|
| `TODO(review …)` · `[변경사항 요약]` · `[확인 필요]` · `PR 변경 시작/끝` · `삭제됨` | AI 삽입분 — 수확 대상 아님 |
| 그 밖의 주석 줄 | **코멘트** |
| 주석이 아닌 추가·삭제 | 코드 수정 — 코멘트로 취급하지 않고 사용자에게 알림 |

**앵커 계산**: 순수 삽입 hunk 헤더 `@@ -a,0 +c,n @@` 는 원본 a 행 **뒤에** 끼워 넣었다는 뜻이므로 앵커는 `a+1` 입니다. 범위 접두가 있으면(`// 3 …`) `a+1 … a+3` 입니다. 연속된 주석 줄은 한 코멘트로 묶고, 본문에서 주석 접두와 범위 숫자는 걷어냅니다.

**5-2. 인라인 가능 여부 검증.**

```bash
gh pr diff <N> | awk '
/^diff --git/ { f=$3; sub("^a/","",f) }
/^@@/ { match($0, /\+[0-9]+/); n=substr($0, RSTART+1, RLENGTH-1); next }
/^\+/ && !/^\+\+\+/ { print f":"n; n++; next }
/^-/ && !/^---/ { next }
{ n++ }' > /tmp/pr-<N>-changed.txt
```

앵커가 이 집합 밖이면 **버리지 말고**: 범위 안에 변경 라인이 있으면 그 라인으로 좁히고, 없으면 앞뒤로 가장 가까운 변경 라인을 찾아 함께 제시합니다. 그마저 없으면 "인라인 불가" 로 분리합니다.

**5-3. 확인.** 게시 직전 형태로 목록을 보여주고 승인을 받습니다(SKILL.md `1. 수확 후 확인받기`). **확인 없이 게시하지 않습니다.**

**5-4. 게시.** 하나의 리뷰로 묶어 올립니다. JSON 을 워크트리 **밖**에 만들어 `--input` 으로 넘깁니다.

```bash
cat > "$HOME/claude-review/$REPO/pr-<N>-review.json" <<'JSON'
{
  "commit_id": "<HEAD_SHA>",
  "event": "COMMENT",
  "comments": [
    { "path": "feature-home/src/main/java/.../HomeTopBarState.kt",
      "start_line": 38, "start_side": "RIGHT", "line": 39, "side": "RIGHT",
      "body": "스크롤 복원 조건이 id 에만 걸려 있어서 목록만 갱신되는 경우를 못 잡습니다." },
    { "path": "domain-search/src/main/java/.../SearchDao.kt",
      "line": 16, "side": "RIGHT",
      "body": "네이밍 변경이 필요할 것 같습니다." }
  ]
}
JSON

gh api "repos/$OWNER/$REPO/pulls/<N>/reviews" -X POST \
  --input "$HOME/claude-review/$REPO/pr-<N>-review.json"
```

- 한 줄 코멘트는 `line` + `side` 만, 범위 코멘트는 `start_line`·`start_side` 를 함께 넣습니다.
- `event` 는 **항상 `COMMENT`** 입니다. `APPROVE`·`REQUEST_CHANGES` 는 쓰지 않습니다(SKILL.md `외부 변경 규칙`).
- **GitHub 은 코멘트 하나라도 잘못되면 리뷰 전체를 거부합니다.** 그래서 5-2 검증을 먼저 통과시킵니다.
- 게시 후 응답의 `html_url` 을 사용자에게 안내하고, JSON 파일은 지웁니다.

**5-5. 정리.**

- **전부 게시했으면 초안 파일을 만들지 않습니다.** 게시된 것이 정본입니다.
- **게시하지 않았거나 일부만 게시했으면** 남은 것(인라인 불가 건 포함)만 담아 `$DRAFT` 에 씁니다.
- 워크트리 제거를 **확인받고** 실행합니다. 마커 때문에 dirty 하므로 `--force` 가 필요합니다.

```bash
git -C "$ROOT" worktree remove "$WT" --force
git -C "$ROOT" worktree prune
rm -f "$HOME/claude-review/$REPO/pr-<N>.sha"
git -C "$ROOT" worktree list          # 해당 경로가 사라졌는지
git -C "$ROOT" status --short         # 0단계 스냅샷과 동일한지
git -C "$ROOT" branch --list "*pr-<N>*"   # 비어야 함
```

- 사용자가 "나중에 이어서" 를 택하면 제거하지 않고 **워크트리 경로를 안내하며** 끝냅니다.

---

## 자체 검증 체크리스트 (종료 전 반드시 수행)

하나라도 통과하지 못하면 바로잡은 뒤 다시 점검합니다.

1. **원본 무손상**: `git -C "$ROOT" status --short` 가 0단계 스냅샷과 동일한가. 마커가 원본 경로에 하나도 없는가.
2. **금지 동작 0건**: commit·push·`APPROVE`·`REQUEST_CHANGES` 를 일절 수행하지 않았는가.
3. **잔여물 0**: 워크트리 제거 후 `git worktree list` 에 경로가 없고, PR 용 로컬 브랜치가 생기지 않았는가.
4. **게시 확인**: 게시 전에 목록을 보여주고 승인을 받았는가. 승인 없이 올린 코멘트가 없는가.
5. **발화 경계**: 마커의 모든 `확인 필요` 가 물음표로 끝나는가. 판정 서술·점수·등급이 하나도 없는가.
6. **코멘트 무단 작성 금지**: 사용자가 쓰지도 말하지도 않은 내용을 워크트리 주석이나 게시 본문에 넣지 않았는가.
7. **수확 누락 없음**: diff 의 추가 줄 중 AI 삽입분이 아닌 것을 빠짐없이 분류했는가. 앵커를 PR head 기준으로 환산했고, 변경 라인 밖 앵커는 버리지 않고 가까운 라인을 제안했는가.
8. **초안 처리**: 전부 게시했으면 초안을 남기지 않았는가. 일부만 게시했으면 남은 것만 담아 초안을 남겼는가.
9. **단위 커버리지**: `(n/m)` 이 1부터 m 까지 빠짐없이 존재하는가. 마커 불가 단위가 지도에서 누락되지 않았는가.
10. **진행을 밀지 않았는가**: 지도를 출력한 뒤 사용자 요청 없이 다음 단위를 꺼내거나 진행 상황을 캐묻지 않았는가. `마무리` 없이 5단계로 넘어가지 않았는가.

---

## 핵심 준수사항 (요약 — 상세는 0~5단계·SKILL.md)

- **원본 리포에 쓰기 금지** — 마커도 초안도 원본 경로에 남기지 않습니다.
- **커밋·푸시·판정 금지** — 바깥에 만드는 변경은 사용자 확인을 거친 인라인 코멘트 게시 하나뿐입니다.
- **판정은 사용자 몫** — AI 는 변경사항 요약과 열린 질문까지. 규칙 충돌 시 SKILL.md 가 우선합니다.
