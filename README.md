# Client Multi LLM Skills

Client 팀(Android · Flutter · iOS · shared) 공용 Claude Code · Codex CLI · Gemini CLI 플러그인 저장소.

각 팀이 `plugins/<platform>/`에서 플러그인을 관리합니다. 스킬 본문은 공유하고, `plugin-config.json` 하나에서 CLI별 매니페스트를 생성합니다. Claude와 Codex는 `.claude-plugin/marketplace.json` 카탈로그 하나를 사용합니다.

## 디렉토리 구조

```text
Client-Multi-LLM-Skills-Plugin/
├── marketplace-metadata.json         # 마켓플레이스 공통 정보 (수정 대상)
├── .claude-plugin/
│   └── marketplace.json              # 생성: Claude·Codex 공용 카탈로그
├── plugins/
│   └── android/                      # ios/·flutter/·shared/도 같은 구조로 추가
│       └── android-code-quality/
│           ├── plugin-config.json    # 플러그인 공통 정보·CLI별 설정 (수정 대상)
│           ├── .claude-plugin/plugin.json  # 생성: Claude (수정 대상 X)
│           ├── .codex-plugin/plugin.json   # 생성: Codex (수정 대상 X)
│           ├── gemini-extension.json       # 생성: Gemini (수정 대상 X)
│           └── skills/
│               └── android-code-quality/SKILL.md  # 공용 스킬 본문
├── scripts/
│   ├── add_skill.py                  # 플러그인·스킬 골격 생성
│   └── generate_manifests.py         # 설정 → 매니페스트·카탈로그
└── README.md
```

## 사용

사용할 CLI의 설치·로그인을 먼저 완료합니다. Claude와 Codex 사용자는 **원격 마켓플레이스 등록 → 플러그인 설치 → 마켓플레이스·플러그인 업데이트** 순서로 사용하며, 저장소를 직접 clone하거나 Python을 설치할 필요가 없습니다.

Private 저장소이므로 사전에 `gh auth login` 또는 Git 자격증명 설정을 완료하고 저장소 읽기 권한을 확보해야 합니다.

아래 주소는 현재 origin인 `IngJobs/Client-Multi-LLM-Skills-Plugin` 기준입니다. 원격에 플러그인과 카탈로그가 반영된 뒤 사용할 수 있으며, 팀 저장소로 이전하면 등록 주소를 변경합니다. 마켓플레이스 이름은 저장소 이름과 별개인 `client-multi-llm-skills`입니다.

### Claude Code

Claude 대화창에서 실행합니다.

#### 마켓플레이스 추가

```text
/plugin marketplace add IngJobs/Client-Multi-LLM-Skills-Plugin
```

#### 플러그인 설치 / 업데이트

```text
/plugin
/plugin install <plugin-name>@client-multi-llm-skills
/plugin marketplace update client-multi-llm-skills
/plugin update <plugin-name>@client-multi-llm-skills
```

`/plugin`은 플러그인을 탐색·관리하는 인터랙티브 UI입니다. `<plugin-name>`에는 설치할 플러그인 이름을 넣습니다. 현재 제공하는 플러그인의 설치 예시는 다음과 같습니다.

```text
/plugin install android-code-quality@client-multi-llm-skills
```

설치·업데이트 후 새 Claude 세션에서 `/android-code-quality:android-code-quality UseCase 네이밍 규칙을 설명해 줘`로 사용합니다.

### Codex CLI

터미널에서 실행합니다. 실행 디렉토리는 이 저장소일 필요가 없습니다.

#### 마켓플레이스 추가

```sh
codex plugin marketplace add https://github.com/IngJobs/Client-Multi-LLM-Skills-Plugin.git
```

#### 플러그인 설치

```sh
codex plugin list
codex plugin add android-code-quality@client-multi-llm-skills
```

다른 플러그인을 설치하려면 `android-code-quality`를 해당 플러그인 이름으로 바꿉니다.

#### 업데이트

원격 마켓플레이스를 갱신한 뒤 해당 플러그인을 다시 설치합니다.

```sh
codex plugin marketplace upgrade client-multi-llm-skills
codex plugin add android-code-quality@client-multi-llm-skills
```

설치·업데이트 후 새 Codex 세션에서 `$android-code-quality UseCase 네이밍 규칙을 설명해 줘`로 사용합니다.

### Gemini CLI

Gemini는 이 공용 마켓플레이스를 사용하지 않습니다. 현재 다중 플러그인 구조에서는 원격 저장소를 clone한 뒤 각 플러그인 폴더를 확장으로 설치합니다. Claude·Codex와 같은 마켓플레이스 배포 경로는 제공하지 않습니다.

```sh
git clone https://github.com/IngJobs/Client-Multi-LLM-Skills-Plugin.git
cd Client-Multi-LLM-Skills-Plugin
gemini extensions install "$PWD/plugins/android/android-code-quality"
gemini skills list
```

프로젝트 지침을 `AGENTS.md`로 통일하려면 사용자 설정 `~/.gemini/settings.json`의 기존 설정을 유지하면서 아래 항목을 추가합니다. 다른 프로젝트에도 적용되는 사용자 전역 설정입니다. [설정 안내](https://agents.md/#how-do-i-configure-gemini-cli)

```json
{
  "context": {
    "fileName": "AGENTS.md"
  }
}
```

업데이트는 clone한 저장소에서 실행합니다.

```sh
git pull
gemini extensions update android-code-quality
```

새 세션에서 `android-code-quality 스킬로 UseCase 네이밍 규칙을 설명해 줘`라고 요청합니다.

### 스킬 호출 검증 상태 (2026-09-11)

CLI별 호출 방법은 위 사용 안내에서 관리하고, 공용 `SKILL.md` 본문에는 포함하지 않습니다. 공통 질문인 “UseCase 네이밍 규칙을 두 문장으로 설명해 줘”와 실제 읽은 파일 경로·사용 범위 첫 문장을 확인했습니다.

| CLI | 검증 결과 |
| --- | --- |
| Claude | 로컬 플러그인을 `--plugin-dir`로 지정하여 스킬 발견·슬래시 명령 호출·수정된 본문 읽기·답변을 확인했습니다. |
| Codex | 설치된 플러그인의 활성 상태를 확인했습니다. 수정된 본문은 임시 작업공간의 `.agents/skills/`에 연결하여 `$android-code-quality` 호출·파일 읽기·답변을 확인했습니다. 이번 검증은 수정본의 마켓플레이스 배포·재설치 검증을 포함하지 않습니다. |
| Gemini | 기존 설치 확장의 목록에서 스킬 발견을 확인했습니다. 모델 호출은 인증 단계에서 `IneligibleTierError` / `UNSUPPORTED_CLIENT`로 실패하여 수정된 본문 로딩·명시 호출의 완료 여부는 미검증입니다. |

플러그인별 `plugin-config.json`의 `targets`와 `dependencies`를 확인하고, 의존 플러그인이 있으면 해당 의존성부터 설치합니다. 현재 지식형 스킬에는 MCP가 필요하지 않습니다. MCP를 사용하는 스킬은 해당 CLI에서도 별도 연결·인증이 필요합니다. 원본과 이 저장소에서 같은 이름의 플러그인을 중복 활성화하지 않습니다.

## 플러그인·스킬 추가

플러그인 작성자는 저장소를 clone한 뒤 **저장소 루트의 터미널에서** 아래 명령을 실행합니다. Python 3.9 이상이 필요하며 추가 패키지는 필요하지 않습니다.

1. 자기 팀의 플랫폼과 플러그인·스킬 이름으로 아래 생성 명령을 실행합니다.
2. 생성된 `skills/<skill>/SKILL.md`에 지침을 작성하고 필요한 참조 파일을 추가합니다.
3. `plugin-config.json`에서 설명·작성자·버전·대상 CLI를 확인합니다. 설정을 수정했다면 매니페스트를 재생성합니다.
4. 생성 결과를 검사하고 본문·설정·생성 파일을 함께 PR에 포함합니다.

```sh
# 새 플러그인과 첫 스킬 생성 (기존 플러그인 이름이면 스킬만 추가)
python3 scripts/add_skill.py \
  --platform android \
  --plugin android-example \
  --skill example-guide \
  --description "예시 기능의 규칙을 질문할 때 사용하는 가이드"

# plugin-config.json 수정·저장 후 실행
python3 scripts/generate_manifests.py

# 생성 파일과 설정의 일치 여부 확인 (파일 변경 없음)
python3 scripts/generate_manifests.py --check
```

`add_skill.py`는 새 플러그인의 `plugin-config.json`, 기본 세 CLI 매니페스트와 카탈로그까지 생성합니다. 생성된 스킬은 작성용 템플릿이므로 본문을 채워야 합니다. 기존 플러그인의 설정과 스킬은 덮어쓰지 않습니다.

마켓플레이스 정보는 `marketplace-metadata.json`, 플러그인 정보는 `plugin-config.json`에서 수정합니다. **생성된 매니페스트·카탈로그는 직접 수정하지 않습니다.** 파일 저장만으로 자동 갱신되지 않으며, 배포할 때는 해당 플러그인의 버전을 올리고 생성 명령을 실행합니다.

스킬 본문과 참조 파일을 공유하는 구조이며, 생성기가 Claude 전용 도구·명령·에이전트를 다른 CLI 형식으로 변환하지는 않습니다. 이식이 필요한 플러그인은 `targets`에 현재 지원하는 CLI만 지정합니다.

## 설정 관리

| 설정 | 역할 |
| --- | --- |
| `name`, `version`, `description`, `author`, `keywords` | 공통 정보. `author`는 `{ "name": "TeamBlind Android" }` 형태 |
| `claude`, `codex`, `gemini` | 각 CLI에만 전달할 매니페스트 설정. 생략 또는 빈 객체 가능 |
| `targets` | 생성할 CLI 목록. 생략하면 세 CLI 모두 포함 |
| `dependencies` | 필요한 플러그인 이름 배열. CLI별로 다르면 선택한 모든 CLI를 키로 하는 객체로 지정 |
| `resources` | 스크립트 등 별도 구성 파일의 플러그인 기준 상대 경로 배열 |

CLI별 객체는 공통 설정에 병합하며, 배열·일반 값은 교체하고 `null`은 필드를 제거합니다. `name`·`version`은 공통 설정에서만 지정합니다. 예를 들어 Codex 표시 정보는 `codex.interface`에 작성합니다.

생성기는 의존성의 누락·순환·대상 CLI 불일치를 검사합니다. Claude 매니페스트에는 의존성을 기록하지만, Codex·Gemini에서 자동 설치를 가정하지 않습니다. 공용 카탈로그에는 Claude 또는 Codex 대상 플러그인이 함께 표시되므로 `targets`는 접근 제한이 아닙니다. 매니페스트 생성만으로 실제 동작 호환성이 검증되지는 않습니다.

## 제거

```sh
claude plugin uninstall android-code-quality@client-multi-llm-skills
codex plugin remove android-code-quality@client-multi-llm-skills
gemini extensions uninstall android-code-quality
```

마켓플레이스 등록도 제거하려면 해당 CLI에서 `claude plugin marketplace remove client-multi-llm-skills` 또는 `codex plugin marketplace remove client-multi-llm-skills`를 실행합니다.

## 참고

- [원본 저장소](https://github.com/teamblind/client-claude-plugins)
- [Claude 플러그인](https://code.claude.com/docs/en/plugins) · [마켓플레이스](https://code.claude.com/docs/en/plugin-marketplaces)
- [Codex 플러그인](https://developers.openai.com/plugins/build/plugins)
- [Gemini 확장](https://geminicli.com/docs/extensions/reference/)
