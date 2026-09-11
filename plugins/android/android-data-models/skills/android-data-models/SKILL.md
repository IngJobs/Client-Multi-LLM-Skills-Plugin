---
name: android-data-models
description: Teamblind Android 데이터 모델 아키텍처 설계 가이드(참조용 지식 — 코드를 직접 생성하지 않음). "UiState 어떻게 설계해?"·"VO와 Entity 차이가 뭐야?"·"Entity→VO→UiState 변환 패턴 알려줘"·"Room Entity/Request Body 어떻게 나눠?" 같은 모델 타입별 역할·변환 패턴 질문 시 자동 발동.
---

# Android 데이터 모델 아키텍처

## 모델 타입별 역할과 계층 분리

프로젝트는 Clean Architecture 원칙에 따라 계층별로 서로 다른 데이터 모델을 사용합니다.

### 데이터 변환 흐름
```
API Response → Entity → VO → UiState
     ↓           ↓      ↓       ↓
Network    Data Layer Domain  UI Layer
```

---

## 1. Entity (네트워크 응답 모델)

**위치**: `data-*` 모듈의 `entity` 패키지
**용도**: API 응답 데이터를 담는 불변 데이터 구조
**계층**: Data Layer에서 사용

```kotlin
// core.foundation.data.Entity 인터페이스 구현
internal data class FeedRealTimeTrendingArticleEntity(
    @SerializedName("type")
    val type: String,
    @SerializedName("channel")
    val channel: FeedRealTimeTrendingArticleChannelEntity,
    @SerializedName("followButton")
    val followButton: ChannelFollowButtonEntity,
) : Entity

// VO 변환 함수 제공
internal fun FeedRealTimeTrendingArticleEntity.toVO() = FeedRealTimeTrendingArticleVO(
    type = FeedRealTimeTrendingArticleType.from(type),
    channel = channel.toVO(),
    followButton = followButton.toVO(),
)
```

---

## 2. VO (Value Object)

**위치**: `data-*` 모듈의 `vo` 패키지
**용도**: 비즈니스 로직에서 사용하는 도메인 모델
**계층**: Domain, Data Layer에서 사용

```kotlin
// core.foundation.vo.VO 인터페이스 구현
data class FeedRealTimeTrendingArticleVO(
    val type: FeedRealTimeTrendingArticleType,
    val channel: FeedRealTimeTrendingArticleChannelVO,
    val followButton: ChannelFollowButtonVO,
    val member: FeedRealTimeTrendingArticleMemberVO,
    val content: FeedRealTimeTrendingArticleContentVO,
    val logging: LoggingVO,
) : VO
```

---

## 3. UiState

**위치**: `ui-*` 모듈의 `uistate` 패키지
**용도**: UI 화면 표시를 위한 상태 모델
**계층**: Presentation Layer (Feature)에서 사용

```kotlin
// core.foundation.uistate.UiState 인터페이스 구현
@Stable
internal sealed interface RealTimeTrendingArticleUiState : UiState {
    val common: Common

    data class NormalUiState(
        override val common: Common,
    ) : RealTimeTrendingArticleUiState

    data class ImageUiState(
        override val common: Common,
        val images: ImmutableList<String>,
    ) : RealTimeTrendingArticleUiState
}

// VO에서 UiState로 변환
internal fun FeedRealTimeTrendingArticleVO.toUiState(): RealTimeTrendingArticleUiState {
    return if (content.images.isNotEmpty()) {
        RealTimeTrendingArticleUiState.ImageUiState(
            common = createCommon(),
            images = content.images.toImmutableList(),
        )
    } else {
        RealTimeTrendingArticleUiState.NormalUiState(
            common = createCommon(),
        )
    }
}
```

---

## 4. Room Entity

**위치**: `data-*` 모듈 또는 전용 모듈의 entity 패키지
**용도**: 로컬 데이터베이스 저장을 위한 모델
**계층**: Data Layer (Local Storage)에서 사용

```kotlin
@Entity(tableName = BigBannerEntity.TABLE)
data class BigBannerEntity(
    @PrimaryKey
    @SerializedName("id")
    val id: Int,

    @ColumnInfo(name = Column.TITLE)
    @SerializedName("title")
    val title: String? = null,

    @Embedded
    @SerializedName("label")
    val label: Label?,
) {
    companion object {
        const val TABLE = "big_banner"

        object Column {
            const val TITLE = "title"
        }
    }

    data class Label(
        @ColumnInfo(name = "label_text")
        val text: String?,
        @ColumnInfo(name = "label_color")
        val color: String?,
    )
}
```

---

## 5. API Request Body Models

**위치**: `data-*` 모듈의 `data/body` 패키지
**용도**: API 요청 전송용 모델
**계층**: Network Layer에서 사용

```kotlin
internal data class WritingChannelsBody(
    @SerializedName("offset")
    val offset: Int = 0,
    @SerializedName("currentChannelId")
    val currentChannelId: String? = null,
    @SerializedName("editingChannelId")
    val editingChannelId: String? = null,
)

// 사용 예시
interface ArticleService {
    @POST("v3/channels/writing")
    suspend fun getWritingChannels(@Body body: WritingChannelsBody): WritingChannelsResponse
}
```

---

## 6. Event Models

**위치**: `data-*` 모듈의 `event` 패키지
**용도**: 상태 전파 및 글로벌 이벤트 처리
**계층**: Data Layer에서 정의, 모든 계층에서 사용

```kotlin
sealed interface ArticleGlobalEvent {
    data object CommentWritten : ArticleGlobalEvent
    data class ArticleUpdated(val articleId: String) : ArticleGlobalEvent
    data class ArticleDeleted(val articleId: String) : ArticleGlobalEvent
}
```

---

## 변환 함수 컨벤션

### Entity → VO 변환
```kotlin
// internal 접근 제한자 사용
internal fun ArticleEntity.toVO(): ArticleVO = ArticleVO(
    id = this.id,
    title = this.title,
    content = this.content ?: "",  // null 처리
    createdAt = this.createdAt.toLocalDateTime(),
)

// 리스트 변환
internal fun List<ArticleEntity>.toVOList(): List<ArticleVO> = map { it.toVO() }
```

### VO → UiState 변환
```kotlin
internal fun ArticleVO.toUiState(): ArticleUiState = ArticleUiState(
    id = this.id,
    displayTitle = this.title,
    formattedDate = this.createdAt.format(DateTimeFormatter.ofPattern("yyyy.MM.dd")),
    isBookmarked = false,  // UI 전용 상태
)
```

---

## 네이밍 컨벤션

| 타입 | 접미사 | 예시 |
|------|--------|------|
| Entity (API) | `Entity` | `ArticleEntity`, `UserEntity` |
| VO | `VO` | `ArticleVO`, `UserVO` |
| UiState | `UiState` | `ArticleUiState`, `UserUiState` |
| Room Entity | `Entity` | `CachedArticleEntity` |
| Request Body | `Body` | `CreateArticleBody`, `LoginBody` |
| Event | `Event` | `ArticleGlobalEvent`, `UserEvent` |

---

## 패키지 구조

```
domain-[feature]/
├── di/              # Hilt 모듈 (UseCaseModule)
└── usecase/         # UseCase 인터페이스 & 구현체

ui-[feature]/
├── uistate/         # UI State 모델
├── viewmodel/       # ViewModel
└── ui/              # Compose UI

data-[feature]/
├── di/              # Hilt 모듈 (RepositoryModule)
├── entity/          # API 응답 Entity
├── vo/              # Value Objects
├── event/           # 이벤트 모델
├── repository/      # Repository 인터페이스 & 구현체 (internal)
├── data/body/       # API Request Body
├── service/         # Retrofit Service
├── mapper/          # 데이터 변환
└── entity/ (Room)   # Room Entity (로컬 DB)
```

---

## 어노테이션 가이드라인

### 네트워크 모델 (Gson)
```kotlin
data class NetworkModel(
    @SerializedName("api_field_name")  // JSON 필드명과 다를 때
    val kotlinFieldName: String,

    @SerializedName("optional_field")
    val optionalField: String? = null,  // nullable + 기본값
)
```

### Room 모델
```kotlin
@Entity(
    tableName = "articles",
    indices = [Index(value = ["article_id"], unique = true)]
)
data class RoomArticleEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,

    @ColumnInfo(name = "article_id")
    val articleId: String,

    @ColumnInfo(name = "created_at")
    val createdAt: Long,

    @Embedded(prefix = "author_")
    val author: AuthorEntity?,
)
```

### Compose 최적화
```kotlin
// ImmutableList 사용 시 자동으로 stable 추론
data class ListUiState(
    val items: ImmutableList<ItemUiState>  // @Stable 불필요
)

// Sealed interface는 명시적 @Stable 필요
@Stable
sealed interface ComplexUiState : UiState {
    data class Success(val data: Data) : ComplexUiState
    data class Error(val message: String) : ComplexUiState
    data object Loading : ComplexUiState
}

// 완전히 불변인 객체
@Immutable
data class ImmutableData(
    val id: String,
    val count: Int,
    val name: String,
)
```

### @Stable 사용 가이드라인

**외부 의존 가능 모듈 (`blind-common`, `blind-common-ui`, `ui/*-common`, `feature-common-*`) — 프로퍼티 구성과 무관하게 `@Stable` 필수:**
- Compose 컴파일러는 외부 모듈 클래스 내부를 분석하지 못하므로 기본 unstable 처리
- 프로퍼티가 단순 primitive/String이어도 `@Stable` 명시 필요

**예외 — 아래 패턴의 프로퍼티를 포함하면 공용 모듈이어도 `@Stable` 적용 금지:**

같은 인스턴스 참조를 유지한 채 내부 상태가 변할 수 있는 타입이 프로퍼티로 포함된 경우.
`@Stable` 계약 위반 시 recomposition 최적화 실패가 아닌 **stale UI 버그**가 발생한다.

- 내부 상태를 관리하는 interface/abstract 타입 (예: `CoroutineScope`)
- 외부 라이브러리의 가변 객체로 생성 후 읽기 전용 보장이 불확실한 타입
  (예: Google Ads SDK의 `MediaContent`, `NativeCustomFormatAd`)

판단 기준: "같은 참조를 유지한 채 내부 상태가 변할 수 있는가?"
→ 불확실하거나 Yes → `@Stable` 금지

**feature 내부 모듈 — 프로퍼티 구성에 따라 `@Stable` 필요 여부 판단:**

`@Stable` 필요:
- 인터페이스 또는 추상 클래스를 **프로퍼티**로 가질 때
- UiState 자체가 `interface`로 선언된 경우 (sealed interface 포함)

`@Stable` 불필요:
- 모든 프로퍼티가 Primitive, String, enum, 또는 이미 Stable한 객체로만 이루어진 단순 data class
- `List`/`Map`/`Set` 프로퍼티를 `ImmutableList`/`PersistentList` 등 불변 컬렉션으로 변경한 경우

**확인 방법:**
```bash
./gradlew assembleDebug -PcomposeCompilerReports=true
# build/compose_compiler/ 에서 stability 확인
```

---

## 체크리스트

### 새로운 기능 구현 시
- [ ] **Entity**: API 응답 구조에 맞는 Entity 클래스 작성
- [ ] **VO**: 비즈니스 로직에 필요한 VO 클래스 작성
- [ ] **UiState**: UI 표시를 위한 UiState 클래스 작성
- [ ] **변환 함수**: Entity → VO → UiState 변환 함수 구현
- [ ] **Room Entity**: 로컬 저장이 필요한 경우 Room Entity 작성
- [ ] **Request Body**: API 요청이 필요한 경우 Body 모델 작성

### 베스트 프랙티스
- [ ] 모든 데이터 모델은 불변(immutable) 객체로 설계
- [ ] 변환 함수는 `internal` 접근 제한자 사용
- [ ] 외부 의존 가능 모듈(`blind-common`, `blind-common-ui`, `ui/*-common`, `feature-common-*`)의 UiState에 `@Stable` 적용
      (단, 같은 참조를 유지한 채 내부 상태가 변할 수 있는 프로퍼티 포함 시 제외)
- [ ] sealed interface의 `@Stable`은 선언부에만 적용하고 구현체(data class/object)에는 중복 적용하지 않음
- [ ] feature 내부 UiState의 `List`/`Map`/`Set` 프로퍼티는 `ImmutableList`/`ImmutableMap`/`ImmutableSet`으로 타입 변경 (근본 수정)
- [ ] feature 내부 UiState의 인터페이스/추상 클래스 프로퍼티, 또는 sealed interface 선언 시 `@Stable` 추가
- [ ] 컬렉션은 `ImmutableList` 사용하여 성능 최적화
- [ ] Null 처리는 변환 함수에서 기본값으로 변환
