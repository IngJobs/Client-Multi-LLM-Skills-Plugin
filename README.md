# Client Multi LLM Skills

Client 팀(Android · Flutter · iOS · shared) 공용 Claude Code · Codex CLI · Gemini CLI 플러그인 저장소.

1. 각 팀이 `plugins/<platform>/`에서 플러그인을 관리합니다. 
2. 스킬 본문은 공유하고, `plugin-config.json` 하나에서 CLI별 매니페스트를 생성합니다. 
3. Claude와 Codex는 `.claude-plugin/marketplace.json` 카탈로그 하나를 사용합니다.

## 디렉토리 구조

```text
Client-Multi-LLM-Skills-Plugin/
├── marketplace-metadata.json         # 마켓플레이스 공통 정보 (수정 대상)
├── .claude-plugin/
│   └── marketplace.json              # 생성: Claude·Codex 공용 카탈로그
├── plugins/
│   └── android/                      # ios/·flutter/·shared/도 같은 구조로 추가
│       └── <plugin-name>/
│           ├── plugin-config.json    # 플러그인 공통 정보·CLI별 설정 (수정 대상)
│           ├── .claude-plugin/plugin.json  # 생성: Claude (수정 대상 X)
│           ├── .codex-plugin/plugin.json   # 생성: Codex (수정 대상 X)
│           ├── gemini-extension.json       # 생성: Gemini (수정 대상 X)
│           └── skills/
│               └── <skill-name>/
│                   ├── SKILL.md           # 공용 스킬 본문
│                   └── references/       # 필요 시 추가하는 참조 파일
│                       ├── execution-environment.md  # 실행 환경 지침
│                       └── workflow.md   # 상세 업무 절차
├── scripts/
│   ├── add_skill.py                  # 플러그인·스킬 골격 생성
│   └── generate_manifests.py         # 설정 → 매니페스트·카탈로그
├── tests/                           # 생성기·스킬 참조 링크 등 검증
└── README.md
```

`references/`와 그 안의 파일 구성은 예시이며, 모든 스킬의 필수 구조는 아닙니다. 스킬에 필요한 참조 파일만 추가합니다.

---

## 사용

사용할 CLI의 설치·로그인을 먼저 완료합니다.

```
아래 주소는 현재 origin인 `IngJobs/Client-Multi-LLM-Skills-Plugin` 기준입니다. 원격에 플러그인과 카탈로그가 반영된 뒤 사용할 수 있으며, 팀 저장소로 이전하면 등록 주소를 변경합니다. 마켓플레이스 이름은 저장소 이름과 별개인 `client-multi-llm-skills`입니다.
```

### Claude Code

Claude 대화창에서 실행합니다.

#### 1. 마켓플레이스 추가

```text
/plugin marketplace add IngJobs/Client-Multi-LLM-Skills-Plugin
```

#### 2. 플러그인 설치 / 업데이트

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

#### 1. 마켓플레이스 추가

```sh
codex plugin marketplace add https://github.com/IngJobs/Client-Multi-LLM-Skills-Plugin.git
```

#### 2. 플러그인 설치

```sh
codex plugin list
codex plugin add android-code-quality@client-multi-llm-skills
```

다른 플러그인을 설치하려면 `android-code-quality`를 해당 플러그인 이름으로 바꿉니다.

#### 3. 업데이트

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

---

## 플러그인·스킬 추가

플러그인·스킬 추가 및 수정에는 [shared-plugin-authoring 스킬](plugins/shared/shared-plugin-authoring/skills/shared-plugin-authoring/SKILL.md)을 사용합니다. 생성·본문 작성·패키징 설정·검증 절차를 담당합니다. 작업할 저장소를 clone하고 해당 저장소에서 CLI를 실행합니다. Python 3.9 이상이 필요하며 추가 패키지는 필요하지 않습니다.

| CLI | 호출 예시 |
| --- | --- |
| Claude Code | `/shared-plugin-authoring:shared-plugin-authoring shared에 새 플러그인을 만들어줘. 목적은 …` |
| Codex CLI | `$shared-plugin-authoring shared에 새 플러그인을 만들어줘. 목적은 …` |
| Gemini CLI | `shared-plugin-authoring 스킬로 shared에 새 플러그인을 만들어줘. 목적은 …` |

---

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

---

## 제거

```sh
claude plugin uninstall android-code-quality@client-multi-llm-skills
codex plugin remove android-code-quality@client-multi-llm-skills
gemini extensions uninstall android-code-quality
```

마켓플레이스 등록도 제거하려면 해당 CLI에서 `claude plugin marketplace remove client-multi-llm-skills` 또는 `codex plugin marketplace remove client-multi-llm-skills`를 실행합니다.

---

## 참고

- [원본 저장소](https://github.com/teamblind/client-claude-plugins)
- [Claude 플러그인](https://code.claude.com/docs/en/plugins) · [마켓플레이스](https://code.claude.com/docs/en/plugin-marketplaces)
- [Codex 플러그인](https://developers.openai.com/plugins/build/plugins)
- [Gemini 확장](https://geminicli.com/docs/extensions/reference/)

---

## 별첨: Python 파일 역할

| 파일 | 역할 |
| --- | --- |
| [scripts/add_skill.py](scripts/add_skill.py) | 새 스킬 골격을 만들고, 필요한 플러그인 설정·매니페스트·카탈로그를 생성합니다. |
| [scripts/generate_manifests.py](scripts/generate_manifests.py) | 공통 설정에서 CLI별 매니페스트와 공용 카탈로그를 생성합니다. `--check`로 파일 변경 없이 일치 여부를 검사합니다. |
| [tests/test_add_skill.py](tests/test_add_skill.py) | 스킬 생성, 기존 파일 보존, 잘못된 입력 및 생성 실패 처리를 검증합니다. |
| [tests/test_generate_manifests.py](tests/test_generate_manifests.py) | 공통·CLI별 설정 병합과 필드 유효성 검사를 검증합니다. |
| [tests/test_catalog.py](tests/test_catalog.py) | 카탈로그 생성, 대상 CLI 반영, 의존성·리소스 검사를 검증합니다. |
| [tests/test_skill_links.py](tests/test_skill_links.py) | 스킬 문서의 로컬 참조 링크가 실제 파일로 연결되는지 검사하며, 코드 예시의 링크는 제외합니다. |
