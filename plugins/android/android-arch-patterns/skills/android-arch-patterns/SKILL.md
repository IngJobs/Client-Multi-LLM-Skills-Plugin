---
name: android-arch-patterns
description: Teamblind Android Clean Architecture 고급 패턴 설계 가이드(참조용 지식 — 코드를 직접 생성하지 않음). "여러 UseCase 어떻게 합성/조합해?"·"Global Event System 어떻게 써?"·"DataStore 패턴 알려줘"·"Multi-Source 데이터 접근 어떻게 설계해?"·"Behavior 패턴이 뭐야?" 같은 아키텍처 설계 방법·패턴 질문 시 자동 발동. 실제 모듈/UseCase 생성은 create-module·create-usecase, 준수 검증은 check-arch, 피드 프레임워크(@UniversalItem·FeedLazyColumn·새 피드 아이템 추가)는 android-feed-development, 이벤트 로깅·임프레션 트래킹(Timberjack·서버 드리븐 logging·Modifier.impression)은 android-event-logging(클라 이벤트 Scheme 생성은 create-event-scheme), 화면 이동(Path·NavGraphProvider·새 화면 추가·딥링크)은 android-navigation(화면 라우트 뼈대 생성은 create-nav-screen)를 사용.
---

# Android 고급 아키텍처 패턴

## UseCase 조합 패턴

복잡한 비즈니스 로직은 여러 UseCase를 조합하여 구현합니다. UseCase 내에서 다른 UseCase를 호출하여 단일 책임 원칙을 유지하면서도 복잡한 기능을 구현할 수 있습니다.

```kotlin
// 하위 레벨 UseCase들
interface FilterArticleUseCase : UseCase<ArticleEntity, Boolean>
interface EnrichArticleUseCase : UseCase<ArticleEntity, EnrichedData>

// 상위 레벨 UseCase에서 다른 UseCase들을 조합
class GetArticleListUseCaseImpl @Inject constructor(
    private val articleRepository: ArticleRepository,
    private val filterArticleUseCase: FilterArticleUseCase,
    private val enrichArticleUseCase: EnrichArticleUseCase,
    @DefaultDispatcher private val defaultDispatcher: CoroutineDispatcher,
) : GetArticleListUseCase {

    override suspend fun invoke(param: EmptyUseCaseParam): List<ArticleVO> =
        withContext(defaultDispatcher) {
            val articles = articleRepository.getArticles()
            articles
                .filter { filterArticleUseCase(it) }  // 다른 UseCase 호출
                .map { entity ->
                    val enrichedData = enrichArticleUseCase(entity)  // 다른 UseCase 호출
                    entity.toVO(enrichedData)
                }
                .sortedByDescending { it.publishedAt }
        }
}
```

### UseCase 조합 원칙
- 별도의 Behavior 인터페이스를 만들지 않고 UseCase로 통합
- 각 UseCase는 단일 책임을 가지며, 조합을 통해 복잡한 로직 구현
- 상위 UseCase가 하위 UseCase들을 의존성 주입받아 호출
- 테스트 시 각 UseCase를 독립적으로 모킹 가능

---

## Global Event System

기능 간 통신을 위한 글로벌 이벤트 시스템입니다.

### Event 정의
```kotlin
sealed interface ArticleGlobalEvent {
    data object CommentWritten : ArticleGlobalEvent
    data class ArticleUpdated(val articleId: String) : ArticleGlobalEvent
    data class ArticleDeleted(val articleId: String) : ArticleGlobalEvent
}
```

### Repository에서 이벤트 스트림 제공
```kotlin
interface ArticleRepository {
    suspend fun sendArticleGlobalEvent(event: ArticleGlobalEvent)
    fun getArticleGlobalEvent(): Flow<ArticleGlobalEvent>
}

internal class ArticleRepositoryImpl @Inject constructor() : ArticleRepository {
    private val _globalEvents = MutableSharedFlow<ArticleGlobalEvent>()

    override suspend fun sendArticleGlobalEvent(event: ArticleGlobalEvent) {
        _globalEvents.emit(event)
    }

    override fun getArticleGlobalEvent(): Flow<ArticleGlobalEvent> = _globalEvents.asSharedFlow()
}
```

### 다른 기능에서 이벤트 구독
```kotlin
@HiltViewModel
class OtherFeatureViewModel @Inject constructor(
    private val articleRepository: ArticleRepository
) : ViewModel() {
    init {
        viewModelScope.launch {
            articleRepository.getArticleGlobalEvent().collect { event ->
                when (event) {
                    is ArticleGlobalEvent.ArticleUpdated -> refreshArticle(event.articleId)
                    is ArticleGlobalEvent.CommentWritten -> refreshComments()
                    else -> {}
                }
            }
        }
    }
}
```

---

## DataStore 패턴

중간 데이터 계층으로 캐싱 및 상태 관리를 담당합니다.

### DataStore 인터페이스
```kotlin
interface ArticleDataStore {
    suspend fun saveArticles(articles: List<ArticleEntity>)
    suspend fun getArticles(): List<ArticleEntity>
    suspend fun clearArticles()
    suspend fun saveProfileSelectionTooltipShown()
    suspend fun hasProfileSelectionTooltipShown(): Boolean
}
```

### Repository에서 DataStore 사용
```kotlin
internal class ArticleRepositoryImpl @Inject constructor(
    private val articleService: V3ArticleService,
    private val articleDataStore: ArticleDataStore
) : ArticleRepository {
    override suspend fun refreshArticles(): List<ArticleVO> {
        val articles = articleService.getArticles()
        articleDataStore.saveArticles(articles) // 캐싱
        return articles.map { it.toVO() }
    }

    override suspend fun getArticles(): List<ArticleVO> {
        return articleDataStore.getArticles().map { it.toVO() }
    }
}
```

---

## Multi-Source Data Access

Local, Remote, Store 패턴을 활용한 다중 소스 데이터 접근입니다.

### 데이터 소스 인터페이스 정의

```kotlin
// data/[feature]/datasource/local: 로컬 데이터 소스
interface ArticleLocalDataSource {
    suspend fun getArticles(): List<ArticleEntity>
    suspend fun saveArticles(articles: List<ArticleEntity>)
    suspend fun deleteArticle(articleId: String)
}

// data/[feature]/datasource/remote: 원격 데이터 소스
interface ArticleRemoteDataSource {
    suspend fun fetchArticles(): List<ArticleEntity>
    suspend fun fetchArticleById(id: String): ArticleEntity
}

// data/[feature]/datasource/store: 인메모리 스토어
interface ArticleStore {
    fun observeArticles(): Flow<List<ArticleEntity>>
    suspend fun updateArticles(articles: List<ArticleEntity>)
}
```

### Repository에서 통합 관리
```kotlin
internal class ArticleRepositoryImpl @Inject constructor(
    private val localDataSource: ArticleLocalDataSource,
    private val remoteDataSource: ArticleRemoteDataSource,
    private val articleStore: ArticleStore
) : ArticleRepository {

    override suspend fun refreshArticles(): List<ArticleVO> {
        // Remote -> Local -> Store 순으로 데이터 흐름
        val articles = remoteDataSource.fetchArticles()
        localDataSource.saveArticles(articles)
        articleStore.updateArticles(articles)
        return articles.map { it.toVO() }
    }

    override fun observeArticles(): Flow<List<ArticleVO>> {
        return articleStore.observeArticles().map { articles ->
            articles.map { it.toVO() }
        }
    }

    override suspend fun getArticlesWithFallback(): List<ArticleVO> {
        return try {
            refreshArticles()
        } catch (e: Exception) {
            // 네트워크 실패 시 로컬 캐시 반환
            localDataSource.getArticles().map { it.toVO() }
        }
    }
}
```

---

## Behavior 패턴

Redux 기반 상태 관리와 다중 스토어 조정을 위한 Behavior 패턴입니다.

```kotlin
class FeedArticleItemReduxBehaviorImpl @Inject constructor(
    private val feedArticleItemStore: FeedArticleItemStore,
    private val followChannelStore: FollowChannelStore,
    private val getAlterFollowedGlobalEventUseCase: GetAlterFollowedGlobalEventForFeedArticleUseCase,
    @DefaultDispatcher private val defaultDispatcher: CoroutineDispatcher,
) : FeedArticleItemReduxBehavior {

    private var unSubscribeFeedArticleItemStore: StoreSubscription? = null
    private var unSubscribeFollowChannelStore: StoreSubscription? = null
    private var jobOfObservingAlterFollowedGlobalEvent: Job? = null

    // 다중 Redux 스토어와 글로벌 이벤트 구독
    override fun startBehavior(state: MutableStateFlow<GetFeedListUseCaseState>) {
        // 아티클 좋아요/북마크 스토어 구독
        unSubscribeFeedArticleItemStore = feedArticleItemStore.safeSubscribe {
            state.updateValue { updateFeedArticleLikes(it, feedArticleItemStore.state.likes) }
            state.updateValue { updateFeedArticleBookmarks(it, feedArticleItemStore.state.bookmarks) }
        }

        // 채널 팔로우 스토어 구독
        unSubscribeFollowChannelStore = followChannelStore.safeSubscribe {
            state.updateValue {
                updateFeedArticleFollows(it, followChannelStore.state.follows)
            }
        }

        // 크로스 기능 업데이트를 위한 글로벌 이벤트 리스닝
        jobOfObservingAlterFollowedGlobalEvent = CoroutineScope(defaultDispatcher).launchSafely {
            getAlterFollowedGlobalEventUseCase().collect { event ->
                state.updateValue { feedItem ->
                    feedItem.map {
                        if (it is FeedArticleUiState && it.header.alterAlias == event.alterAlias) {
                            it.copy(header = it.header.copy(isFollowingAlter = event.isFollow))
                        } else it
                    }
                }
            }
        }
    }

    // 구독 및 작업 정리
    override fun stopBehavior() {
        unSubscribeFeedArticleItemStore?.invoke()
        unSubscribeFollowChannelStore?.invoke()
        jobOfObservingAlterFollowedGlobalEvent?.cancel()
    }
}
```

---

## 패키지 구조

```
domain/[feature]/
├── di/                    # Hilt 모듈 (UseCaseModule)
├── usecase/              # UseCase 인터페이스 & 구현체
├── behavior/            # Behavior 패턴 (Redux 조정)
└── validator/           # 데이터 검증

data/[feature]/
├── di/                    # Hilt 모듈 (RepositoryModule)
├── entity/               # API 응답 Entity
├── repository/           # Repository 인터페이스 & 구현체 (internal)
├── vo/                  # Value Objects
├── event/               # 이벤트 모델 (Global Event System)
├── service/             # Retrofit Service 인터페이스
├── data/
│   └── body/            # API Request Body
├── datasource/
│   ├── local/           # Local 데이터 소스 (Multi-Source)
│   ├── remote/          # Remote 데이터 소스 (Multi-Source)
│   └── store/           # DataStore (캐싱/상태관리)
└── mapper/              # 데이터 변환

ui/[feature]/
├── uistate/             # UI State 모델
├── viewmodel/           # ViewModel
└── ui/                  # Compose UI
```

---

## 체크리스트

### 고급 패턴 적용 시
- [ ] UseCase 조합: 복잡한 로직을 여러 UseCase로 분리했는가?
- [ ] Global Events: 기능 간 통신이 필요한 경우 이벤트 시스템을 사용했는가?
- [ ] DataStore: 캐싱이 필요한 경우 DataStore 패턴을 적용했는가?
- [ ] Multi-Source: 오프라인 지원이 필요한 경우 Local/Remote/Store를 분리했는가?
- [ ] Behavior: Redux 스토어 조정이 필요한 경우 Behavior 패턴을 사용했는가?
