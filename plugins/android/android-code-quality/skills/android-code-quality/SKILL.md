---
name: android-code-quality
description: Teamblind Android 코드 품질 가이드라인·베스트 프랙티스(참조용 지식 — 코드를 직접 생성하지 않음). "UseCase 네이밍 규칙 뭐야?"·"Compose 최적화 어떻게 해?"·"runSuspendCatching 언제 써?"·"상태 관리/UiState 설계 원칙"·"테스트 어떻게 설계해?" 같은 규칙·방법 질문 시 자동 발동. 파일 수정·테스트 생성·런타임 측정은 이 스킬의 범위가 아님.
---

<!-- Source: teamblind/client-claude-plugins @ e709a21
Path: plugins/android/android-code-quality/skills/android-code-quality/SKILL.md
PoC copy: 원본 규칙 유지, 발견 설명 및 실행 범위만 조정. -->

# Android 코드 품질 가이드라인

PR 리뷰 피드백을 반영한 코드 품질 베스트 프랙티스입니다.

## 사용 범위

팀 Android 규칙에 관한 질문에 관련 절과 예시로 답합니다. Claude에서는 `/android-code-quality:android-code-quality`, Codex에서는 `$android-code-quality`, Gemini에서는 “android-code-quality 스킬로 UseCase 네이밍 규칙을 설명해 줘”처럼 요청합니다.
답변에는 질문과 관련된 규칙과 예시를 골라 제시하고, 전체 체크리스트를 매번 반복하지 않습니다.
이 스킬은 참조용 지식이며 파일·Jira·Git을 변경하지 않습니다. 다른 스킬 설치나 MCP 연결 없이 사용할 수 있습니다. 아래 내용은 원본 커밋 기준 팀 규칙이며 프로젝트의 명시적 지침과 충돌하면 충돌을 알리고 프로젝트 지침을 따릅니다.

---

## Clean Architecture 베스트 프랙티스

### UseCase 설계 원칙

```kotlin
// ✅ 좋은 예: 단일 책임, 명확한 네이밍
interface ShouldShowRecruitTabTooltipUseCase : UseCase<EmptyUseCaseParam, Boolean>

interface GetArticleDetailUseCase : UseCase<ArticleIdParam, ArticleDetailVO>

// ❌ 나쁜 예: 모호한 이름
interface ArticleHelper  // 역할 불명확
interface DoSomethingUseCase  // 행위 불명확
```

**원칙:**
- **단일 책임**: UseCase는 하나의 명확한 비즈니스 동작만 수행
- **행위 중심 네이밍**: `ShouldShow[Feature]UseCase`, `Get[Entity]UseCase` 등
- **UseCase 통합**: 유사한 동작은 하나의 UseCase로 통합
- **Domain Layer 배치**: 비즈니스 로직은 domain 레이어에 배치

---

## 상태 관리 패턴

### UiState 패턴

```kotlin
// ✅ 좋은 예: 통합된 UiState + Computed Property
@Stable
data class FeatureUiState(
    val isVisible: Boolean,
    val shouldShowContent: Boolean,
    val position: Offset,
    val data: FeatureData? = null,
    val error: String? = null,
) : UiState {
    // 조건부 로직을 UiState 내부로 캡슐화
    val shouldDisplay: Boolean
        get() = isVisible && shouldShowContent

    val hasData: Boolean
        get() = data != null && error == null
}

// ❌ 나쁜 예: 분산된 상태
class FeatureViewModel {
    private val _isVisible = MutableStateFlow(false)
    private val _shouldShowContent = MutableStateFlow(false)
    private val _position = MutableStateFlow(Offset.Zero)
    // 상태가 분산되어 관리 어려움
}
```

### @Stable 어노테이션 적용 규칙

Compose 컴파일러는 외부 모듈에서 임포트된 클래스를 **unstable**로 추론합니다. 이를 방지하려면 아래 규칙을 따릅니다.

| 클래스 종류 | 조치 | 이유 |
|------------|------|------|
| 공용 UiState (`blind-common`, `blind-common-ui`, `ui/*-common`, `feature-common-*`) | `@Stable` 추가 | 외부 모듈에서 unstable로 인식됨 (프로퍼티 구성 무관) |
| feature 전용 UiState — `List`/`Map`/`Set` 프로퍼티 포함 | 프로퍼티 타입을 `ImmutableList`/`ImmutableMap`/`ImmutableSet`으로 변경 | 근본 원인 수정, 컴파일러가 직접 stable 추론 가능 |
| feature 전용 UiState — 인터페이스/추상 클래스 프로퍼티 포함, 또는 sealed interface 선언 | `internal` + `@Stable` 추가 | 타입 변경으로 해결 불가, `@Stable`로 컴파일러에 명시 |
| feature 전용 UiState — Primitive/String/enum/Stable 프로퍼티만 | `internal` 추가 | 컴파일러가 stable 자동 추론 → @Stable 불필요 |
| Domain VO / Entity | 손대지 않음 | 레이어 역할 위반, Compose 의존성 금지 |
| `enum class` | 손대지 않음 | primitive 취급됨 |

```kotlin
// ✅ List → ImmutableList 타입 변경 (근본 수정, @Stable 불필요)
internal data class FeedUiState(
    val items: ImmutableList<FeedItemUiState>,  // stable 자동 추론
    val tags: ImmutableList<String>,
)

// ✅ 인터페이스 프로퍼티 → @Stable 필요 (타입 변경으로 해결 불가)
@Stable
internal data class PlayerUiState(
    val current: MediaUiState,  // interface 타입
)

// ✅ sealed interface 자체에도 @Stable 필요 (인터페이스는 항상 unstable)
@Stable
internal sealed interface ScreenUiState : UiState {
    data class Success(val items: ImmutableList<ItemUiState>) : ScreenUiState
    data object Loading : ScreenUiState
}

// ✅ 공용 모듈 — @Stable 필수 (프로퍼티가 단순해도 외부 모듈이면 필요)
@Stable
data class FeedItemUiState(...) : UiState

// ❌ List에 @Stable로 때우는 것은 컴파일러를 속이는 임시방편
@Stable  // 근본 원인 미해결
internal data class FeedUiState(
    val items: List<FeedItemUiState>,  // 런타임에 MutableList일 수 있음
)

// ❌ 공용 모듈에 @Stable 없음 → 외부 Composable에서 recomposition 최적화 불가
data class FeedItemUiState(...) : UiState
```

### @Stable 적용 금지 케이스

`@Stable`은 성능 힌트가 아닌 **개발자의 명시적 계약**이다.
계약이 위반되면 recomposition 최적화 실패가 아닌 **stale UI 버그** — 변경됐지만 Compose가 감지하지 못해 화면이 갱신되지 않음 — 가 발생한다.

적용 전 항상 먼저 확인:

> **"이 클래스의 프로퍼티가 변경될 때, 항상 새 인스턴스가 생성되는가?"**
>
> Yes → `@Stable` 안전
>
> No (같은 인스턴스를 유지한 채 내부 상태가 바뀔 수 있음) → `@Stable` 위험

**패턴 A: 내부 상태가 가변인 interface/abstract 타입**

interface나 abstract class는 구현체의 내부 상태 변이를 컴파일러가 추론할 수 없다.
특히 내부적으로 상태를 관리하는 인터페이스가 프로퍼티로 들어올 때 위험하다.

```kotlin
// 예시: CoroutineScope는 interface이며 구현체의 내부 상태 변이를 컴파일러가 보장하지 못함
// → 코루틴 실행(부작용)의 수단이기도 하여 @Stable의 "읽기 전용 데이터" 원칙에 위배
// ❌ @Stable 금지
@Stable
data class SomeUiState(
    val scope: CoroutineScope,  // interface 타입 — 구현체 안정성 컴파일러 미보장
)

// ✅ @Stable 없이 두거나, 내부상태가 가변인 프로퍼티를 UiState에서 제거
data class SomeUiState(
    val scope: CoroutineScope,
)
```

**판단 기준:** "이 interface/abstract 타입의 구현체가 같은 참조를 유지한 채 내부 상태를 변경할 수 있는가?"
→ Yes → `@Stable` 금지

**패턴 B: 외부 라이브러리의 가변 객체**

외부 라이브러리(Google Ads SDK, Media SDK 등)의 타입은 내부 구현을 알 수 없다.
생성 후 읽기 전용임이 문서·코드로 보장되지 않는 한, 내부 상태가 변이될 수 있다고 가정해야 한다.

```kotlin
// 예시: Google Ads SDK의 MediaContent는 비디오 재생 상태를 내부적으로 변경
// NativeCustomFormatAd는 광고 로드·표시 상태를 관리
// → 같은 객체 참조를 유지한 채 내부 상태가 변할 수 있음
// ❌ @Stable 금지 — stale 광고 UI 버그 발생 가능
@Stable
sealed interface ExitAdUiState {
    data class VideoAd(
        val mediaContent: MediaContent,
        val nativeAd: NativeCustomFormatAd?,
    ) : ExitAdUiState
}

// ✅ @Stable 없이 둔다 — recomposition 과다(비효율)가 stale UI(버그)보다 안전
sealed interface ExitAdUiState {
    data class VideoAd(
        val mediaContent: MediaContent,
        val nativeAd: NativeCustomFormatAd?,
    ) : ExitAdUiState
}
```

**판단 기준:** "이 외부 타입이 같은 참조를 유지한 채 내부 상태를 변경할 가능성이 있는가?"
→ 불확실하거나 Yes → `@Stable` 금지

### StateFlow 업데이트

```kotlin
// ✅ 권장: .update {} 사용
_uiState.update { currentState ->
    currentState.copy(shouldShowContent = true)
}

// ❌ 피할 것: 직접 .value 할당
_uiState.value = _uiState.value.copy(shouldShowContent = true)
```

### Lifecycle-aware 수집

```kotlin
// ✅ 권장: collectAsStateWithLifecycle()
@Composable
fun FeatureScreen(viewModel: FeatureViewModel = hiltViewModel()) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    // ...
}

// ❌ 피할 것: collectAsState() - 라이프사이클 비반영으로 불필요한 수집 지속 가능
val uiState by viewModel.uiState.collectAsState()
```

---

## Hilt 의존성 주입 최적화

### UseCase 스코프

```kotlin
// ✅ 올바른 스코프: UseCase는 스코프 없음
@InstallIn(ViewModelComponent::class)
@Module
abstract class UseCaseModule {
    @Binds  // 스코프 어노테이션 없음!
    abstract fun bindFeatureUseCase(
        impl: FeatureUseCaseImpl
    ): FeatureUseCase
}

// ✅ Repository는 Singleton
@InstallIn(SingletonComponent::class)
@Module
abstract class RepositoryModule {
    @Singleton
    @Binds
    abstract fun bindFeatureRepository(
        impl: FeatureRepositoryImpl
    ): FeatureRepository
}

// ❌ 잘못된 예: UseCase에 스코프 적용
@ViewModelScoped  // 불필요!
@Binds
abstract fun bindFeatureUseCase(impl: FeatureUseCaseImpl): FeatureUseCase
```

---

## Jetpack Compose 최적화

### Conditional Modifier

```kotlin
// ✅ 권장: .then() 패턴
Modifier
    .fillMaxWidth()
    .then(
        if (condition) Modifier.padding(16.dp)
        else Modifier.padding(8.dp)
    )

// ❌ 피할 것: .let { } 패턴
Modifier.let { modifier ->
    if (condition) modifier.padding(16.dp)
    else modifier.padding(8.dp)
}
```

### 텍스트 측정 캐싱

```kotlin
// ✅ 권장: remember로 캐싱
@Composable
fun OptimizedText(text: String, style: TextStyle) {
    val textMeasurer = rememberTextMeasurer()
    val measuredText = remember(text, style) {
        textMeasurer.measure(text, style = style)
    }
    // measuredText 사용
}

// ❌ 피할 것: 매번 재측정
@Composable
fun UnoptimizedText(text: String, style: TextStyle) {
    val textMeasurer = rememberTextMeasurer()
    val measuredText = textMeasurer.measure(text, style = style)  // 매 recomposition마다 실행
}
```

### Strong Skipping Mode (Compose Compiler 2.0+)

```kotlin
// ✅ 권장: 상태 값만 key로 사용
val state = remember(
    stateValue1,
    stateValue2,
) {
    SomeState(
        value1 = stateValue1,
        value2 = stateValue2,
        callback = callback,  // 람다는 key에서 제외 (자동 처리)
    )
}

// ⚠️ 불필요: 람다를 key에 포함
val state = remember(
    stateValue1,
    callback,  // Strong Skipping Mode에서 자동 처리됨
) { ... }
```

**핵심 원리:**
- 람다는 자동으로 `remember(캡처된 값들) { ... }`로 변환됨
- 캡처된 값이 변경될 때만 람다가 재생성됨
- `remember` key에 람다 콜백을 포함할 필요 없음

---

## 에러 핸들링

### runSuspendCatching 패턴

suspend 함수 호출 시 반드시 `runSuspendCatching`을 사용합니다. `runCatching`은 `CancellationException`까지 잡아서 코루틴 취소가 전파되지 않는 버그를 유발합니다.

```kotlin
// ✅ 권장: runSuspendCatching으로 에러 처리 (CancellationException 자동 re-throw)
fun loadData() {
    viewModelScope.launch {
        runSuspendCatching {
            businessUseCase(param)
        }.onSuccess { result ->
            _uiState.update { it.copy(data = result, error = null) }
        }.onFailure { exception ->
            _uiState.update { it.copy(error = exception.message) }
        }
    }
}

// ✅ 권장: sideEffect 채널 + finally가 필요한 경우 .also{} 사용
fun refreshData() {
    viewModelScope.launch {
        runSuspendCatching {
            _uiState.update { it.copy(isLoading = true) }
            val result = businessUseCase(param)
            _uiState.update { it.copy(data = result) }
        }.onFailure { error ->
            sideEffectChannel.send(SideEffect.Error(error))
        }.also {
            _uiState.update { it.copy(isLoading = false) }
        }
    }
}

// ❌ 피할 것: runCatching (CancellationException을 잡아버림)
runCatching { suspendFunction() }

// ❌ 피할 것: try-catch로 Exception/Throwable 직접 캐치
try {
    suspendFunction()
} catch (e: Exception) {
    // CancellationException도 잡힘 → sideEffect 채널 collect 코루틴 사망 가능
}
```

> `runSuspendCatching`은 `blind-common/.../extensions/ResultExtension.kt`에 정의되어 있습니다.

### 시간 의존적 로직

```kotlin
// ✅ 권장: Clock 주입으로 테스트 용이성 확보
class TimeBasedUseCaseImpl @Inject constructor(
    private val dataStore: DataStore,
    private val clock: Clock = Clock.systemDefaultZone()
) : TimeBasedUseCase {

    override suspend fun invoke(param: UseCaseParam): Boolean {
        val lastTimestamp = dataStore.getLong(KEY_TIMESTAMP, 0)
        val currentTime = clock.millis()
        val diff = currentTime - lastTimestamp

        // 시계 역행 대응
        if (diff < 0) return true

        return diff > THRESHOLD_INTERVAL
    }
}
```

---

## 테스트 설계

### 단위 테스트 작성 원칙

단위 테스트는 필수 요소가 아닙니다. 커버리지 수치가 아니라 회귀 방지 가치를 기준으로 작성 여부를 판단합니다.

- **작성 권장**: 분기·계산·상태 전이가 복잡한 로직, 수정 시 실수하기 쉬운 케이스, 회귀 비용이 큰 비즈니스 규칙
- **생략 가능**: 단순 위임만 하는 UseCase, 단순 매핑·포워딩 등 실패할 여지가 거의 없는 코드
- 커버리지 수치(예: 80%) 자체를 목표로 삼지 않습니다

---

## 상수 관리

### 매직 넘버 분리

```kotlin
// ✅ 권장: 상수로 분리
object TooltipConstants {
    val DEFAULT_PADDING = 16.dp
    val ARROW_SIZE = 8.dp
    const val SHOW_INTERVAL_MILLIS = 7 * 24 * 60 * 60 * 1000L  // 1주일
}

// ❌ 피할 것: 하드코딩
Box(modifier = Modifier.padding(16.dp))  // 매직 넘버
```

### 빌드 타입별 설정

```kotlin
// ✅ 권장: DI로 환경별 값 주입
@Module
@InstallIn(SingletonComponent::class)
object ConfigModule {

    @Provides
    @Named("tooltip_interval")
    fun provideTooltipInterval(): Long {
        return if (BuildConfig.DEBUG) {
            10 * 60 * 1000L  // QA: 10분
        } else {
            7 * 24 * 60 * 60 * 1000L  // Prod: 1주일
        }
    }
}
```

---

## 접근성

```kotlin
// ✅ 권장: Semantics 추가
@Composable
fun AccessibleTooltip(
    contentDescription: String,
    onDismiss: () -> Unit
) {
    Box(
        modifier = Modifier
            .clickable { onDismiss() }
            .semantics {
                this.contentDescription = contentDescription
                role = Role.Button
            }
    ) {
        // 툴팁 내용
    }
}
```

---

## 리소스 관리

### 국제화

```kotlin
// ✅ 권장: 영어 기본, 한국어 별도
// values/strings.xml (기본 - 영어)
<string name="feature_title">Feature Title</string>

// values-ko/strings.xml (한국어)
<string name="feature_title">기능 제목</string>
```

---

## 코드 리뷰 체크리스트

### 아키텍처
- [ ] UseCase에 스코프 어노테이션이 없는가?
- [ ] Repository 구현체가 `internal`인가?
- [ ] ViewModel에 `@HiltViewModel`이 있는가?

### 상태 관리
- [ ] 분산된 상태가 UiState로 통합되었는가?
- [ ] `.update {}`를 사용하는가?
- [ ] `collectAsStateWithLifecycle()`을 사용하는가?

### Compose
- [ ] Conditional modifier에 `.then()` 패턴을 사용하는가?
- [ ] 비용이 큰 연산이 `remember`로 캐싱되었는가?
- [ ] UiState sealed interface에 `@Stable`이 있는가?
- [ ] 공용 모듈(`blind-common`, `blind-common-ui`, `ui/*-common`, `feature-common-*`)의 UiState에 `@Stable`이 있는가?
- [ ] feature 전용 UiState가 `internal`로 선언되어 외부 노출이 방지되었는가?

### 코드 품질
- [ ] 매직 넘버가 상수로 분리되었는가?
- [ ] 에러 핸들링에 `runSuspendCatching`을 사용하는가? (`runCatching` 사용 금지)
- [ ] 접근성 semantics가 추가되었는가?

### 레드 플래그 (즉시 수정 필요)
- [ ] UseCase에 `@Singleton` 또는 `@ViewModelScoped`
- [ ] `.value =` 직접 할당
- [ ] `collectAsState()` 사용
- [ ] `.let { }`으로 conditional modifier
- [ ] 하드코딩된 시간 간격, 패딩 값
- [ ] "같은 참조를 유지한 채 내부 상태가 변할 수 있는" 프로퍼티를 가진 클래스에 `@Stable`이 붙어있지 않은가?
      (예: 외부 SDK 가변 타입, 내부 상태를 관리하는 interface 타입)
