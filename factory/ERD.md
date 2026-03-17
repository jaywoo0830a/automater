# automator DB 설계 해설서

## 이 문서의 목적

이 시스템의 DB는 **"지역 × 과목 × 학습형태 조합을 자동으로 블로그에 포스팅한다"** 는 목적 하나를 위해 설계되었다. 그런데 단순히 테이블 몇 개로 끝내지 않고 꽤 복잡한 구조를 택했다. 왜 그랬는지, 그리고 자주 쓰는 SQL 패턴은 무엇인지를 이 문서에서 설명한다.

---

## 1. 관계 유형 먼저 이해하기

### 1:N — 버스와 좌석

버스 한 대에 좌석이 여러 개 있다. 좌석은 딱 한 대의 버스에만 속한다. 이것이 1:N이다.

```
버스 (1) ──────── 좌석 (N)
  id=7               seat_number=1, bus_id=7
                     seat_number=2, bus_id=7
                     seat_number=3, bus_id=7
```

DB에서는 **N쪽 테이블에 1쪽의 id를 외래키로 넣는다.**

```sql
-- 버스 테이블 (1쪽)
CREATE TABLE buses (id INT PRIMARY KEY, route VARCHAR(10));

-- 좌석 테이블 (N쪽) — bus_id 가 FK
CREATE TABLE seats (id INT PRIMARY KEY, bus_id INT, seat_number INT,
    FOREIGN KEY (bus_id) REFERENCES buses(id));
```

이 시스템에서 1:N 관계 예시:
- `platforms` → `accounts` : 네이버라는 플랫폼에 계정이 여러 개
- `campaigns` → `dimensions` : 하나의 캠페인에 차원(지역·과목·학습형태)이 여러 개
- `batches` → `batch_items` : 하나의 배치 안에 포스팅 작업이 여러 개

---

### M:N — 학생과 수업

한 학생이 수업을 여러 개 들을 수 있다. 한 수업에 학생이 여러 명 있다. 이것이 M:N이다.

M:N은 직접 연결할 수 없어서 **중간에 연결 테이블(관계 테이블)** 을 만든다.

```
학생 (M) ──── 수강신청 (연결) ──── 수업 (N)
  id=1           student_id=1          id=101
  id=2           class_id=101          id=102
                 student_id=1
                 class_id=102
                 student_id=2
                 class_id=101
```

```sql
-- 연결 테이블
CREATE TABLE enrollments (
    student_id INT,
    class_id   INT,
    PRIMARY KEY (student_id, class_id)  -- 복합 PK로 중복 방지
);
```

이 시스템에서 M:N 관계:
- `combinations` × `dimension_values` → `combination_values` 연결 테이블

---

## 2. 테이블별 설계 이유

### platforms — 왜 필요한가?

지금은 네이버 블로그만 지원하지만 나중에 티스토리·워드프레스·인스타그램을 추가할 수 있다. 플랫폼을 테이블로 분리해두면 `accounts.platform_id`만 바꾸면 되고 코드를 건드릴 필요가 없다.

```
platforms
  id=1  name='Naver Blog'   slug='naver_blog'
  id=2  name='Tistory'      slug='tistory'       ← 나중에 추가
```

**관계:** platforms → accounts (1:N)
하나의 플랫폼에 계정이 여러 개 속한다.

---

### accounts — 계정 풀

여러 네이버 계정을 돌아가며 쓰는 구조다. 계정마다 마지막 사용 시각(`last_used_at`)과 쿨다운(`cooldown_days`)을 관리한다.

`extra JSON` 컬럼이 중요하다. 네이버는 `blog_id`와 `session_path`가 필요하고, 다른 플랫폼은 다른 필드가 필요할 수 있다. JSON으로 두면 플랫폼마다 다른 속성을 `ALTER TABLE` 없이 수용할 수 있다.

```sql
extra = '{"blog_id": "rlawjddn", "session_path": "sessions/a1.json", "proxy": "1.2.3.4:8080"}'
```

**관계:** accounts → batches (1:N)
한 계정이 여러 배치를 처리한다.

---

### campaigns — 작업의 단위

캠페인은 **"무엇을 위해 포스팅하는가"** 를 정의하는 묶음이다.

- `서울·경기남부 학원·과외 마케팅` — 학원/과외 캠페인
- `원주 성인 영어회화` — 전혀 다른 구조의 캠페인

두 캠페인은 차원 구성이 완전히 다르지만 **같은 테이블 구조를 공유한다.** 이것이 이 설계의 핵심이다.

`title_template`은 조합의 값을 제목으로 변환하는 규칙이다.

```
title_template = '{region} {subject} {learning_type} {salt}'
→ '강남 수학 과외 강력 추천'

title_template = '{region} {target_audience} {subject} {salt}'
→ '원주 성인 영어회화 추천'
```

**관계:** campaigns → dimensions (1:N), campaigns → batches (1:N)

---

### dimensions + dimension_values — 이 설계의 핵심

**가장 중요한 설계 결정이다.** 처음에는 이렇게 만들고 싶어진다:

```sql
-- ❌ 나쁜 방법
CREATE TABLE combinations (
    region        VARCHAR(64),
    subject       VARCHAR(64),
    learning_type VARCHAR(64)
);
```

이 구조의 문제: `원주 성인 영어회화` 캠페인을 추가하려면 컬럼을 바꿔야 한다. `target_audience` 컬럼을 `ALTER TABLE`로 추가해야 하고, 기존 데이터가 영향을 받는다.

대신 **차원을 행(row)으로 관리한다:**

```sql
-- ✅ 좋은 방법
dimensions (캠페인의 축 정의)
  id=1  campaign_id=1  slug='region'         sort_order=0
  id=2  campaign_id=1  slug='subject'        sort_order=1
  id=3  campaign_id=1  slug='learning_type'  sort_order=2

dimension_values (각 축의 실제 값)
  id=101  dimension_id=1  value='강남구'
  id=102  dimension_id=1  value='서초구'
  id=201  dimension_id=2  value='수학'
  id=202  dimension_id=2  value='영어'
  id=301  dimension_id=3  value='과외'
  id=302  dimension_id=3  value='학원'
```

새 캠페인을 추가할 때 `ALTER TABLE`이 전혀 필요 없다. `INSERT`만 하면 된다.

#### dimension_values의 계층 구조 (parent_id)

`dimension_values`는 자기 자신을 참조하는 재귀 구조다. 행정구역 계층을 표현하기 위해서다.

```
Tier 0  서울특별시 (parent_id=NULL)
  Tier 1  강남구 (parent_id → 서울특별시)
    Tier 2  대치동 (parent_id → 강남구)
    Tier 2  역삼동 (parent_id → 강남구)
  Tier 1  서초구 (parent_id → 서울특별시)
    Tier 2  반포동 (parent_id → 서초구)
```

이 구조로 "서울 강남구에 속한 동만 가져와" 같은 쿼리가 가능하다.

---

### spacing_rules — 띄어쓰기도 데이터다

`강남수학과외`, `강남 수학과외`, `강남 수학 과외` — 어떤 패턴이 SEO에 유리한지는 시기마다 다르다. 이것을 코드에 하드코딩하면 바꿀 때마다 배포가 필요하다.

DB에 JSON으로 관리하면 INSERT 한 줄로 새 패턴을 추가할 수 있다.

```json
{"region": 1, "subject": 1, "learning_type": 0}
→ '강남 수학 과외' (마지막 차원 뒤 공백은 무시)
```

**관계:** campaigns → spacing_rules (1:N)
하나의 캠페인에 여러 띄어쓰기 패턴을 등록하고, 조합 생성 시 모든 패턴에 대해 곱한다.

---

### combinations + combination_values — M:N의 실체

**combinations**는 카테시안 곱의 결과 하나다.

```
강남구 × 수학 × 과외 × [지역만 띔] × [접미사 있음]
→ combination id=5001
```

이 조합이 `dimension_value` 여러 개와 연결된다. 바로 M:N 관계다.

```
combination_values (연결 테이블)
  combination_id=5001  dimension_value_id=101  (강남구)
  combination_id=5001  dimension_value_id=201  (수학)
  combination_id=5001  dimension_value_id=301  (과외)
```

왜 `combinations` 테이블에 값을 직접 안 넣었는가? 차원 수가 캠페인마다 다르기 때문이다. 학원/과외는 3차원, 원주 성인 영어는 3차원이지만 구성이 다르고, 미래의 캠페인은 5차원일 수 있다. 연결 테이블을 쓰면 차원 수에 관계없이 동일한 구조로 처리된다.

---

### campaign_selections — 일부만 선택하기

전체 지역이 44개인데 이번 주는 강남·서초·송파만 작업하고 싶다. 그렇다고 `dimension_values`를 지우면 나중에 복원해야 한다.

`campaign_selections`는 **"이 캠페인에서 이번 시딩에 포함할 값"** 을 별도로 관리한다. `seed` 명령 실행 시 이 테이블을 읽어 카테시안 곱 범위를 결정한다.

```sql
-- 강남구·서초구만 선택
INSERT INTO campaign_selections (campaign_id, dimension_id, dimension_value_id)
VALUES (1, 1, 101),   -- 강남구
       (1, 1, 102);   -- 서초구
```

빈 dimension은 해당 차원의 전체 값을 사용한다는 뜻이다.

---

### batches + batch_items — 실행 계획

`batches`는 **"계정 A가 2024-01-15 10:00에 조합 40개를 처리한다"** 는 실행 계획이다.

`batch_items`는 그 안의 개별 포스팅 작업이다. 각 아이템은 `combination_id`를 참조해서 어떤 키워드로 포스팅할지 알 수 있다.

상태 흐름:
```
batch_items.status:  pending → (실행 중) → done
                                         → failed
```

실패한 아이템만 재실행하거나, 어떤 조합이 가장 많이 실패하는지 분석하는 게 이 구조로 가능하다.

---

## 3. 전체 ERD 요약

```
platforms ──(1:N)──► accounts
     │
     └──(1:N)──► campaigns ──(1:N)──► dimensions ──(1:N)──► dimension_values
                     │                                              │ (자기참조: parent_id)
                     ├──(1:N)──► spacing_rules                     │
                     │                                              │
                     ├──(1:N)──► campaign_selections ───────────────┘
                     │
                     └──(1:N)──► combinations ──(M:N via combination_values)──► dimension_values
                                     │
                     ┌───(1:N)──► batches ──(1:N)──► batch_items
                     │               │
                  accounts           └──(1:N)──► batch_items
```

---

## 4. 자주 쓰는 SQL 패턴

### 4-1. 사용 가능한 계정 조회 (쿨다운 필터)

```sql
-- 마지막 사용 후 cooldown_days 가 지난 계정만 반환
SELECT a.id, a.username, a.extra
FROM   accounts a
WHERE  a.platform_id = 1
  AND  a.status      = 'active'
  AND  (
      a.last_used_at IS NULL
      OR  a.last_used_at < NOW() - INTERVAL a.cooldown_days DAY
  )
ORDER BY a.last_used_at ASC NULLS FIRST, a.id ASC;
```

**패턴:** NULL이 있는 날짜 비교는 `IS NULL` 먼저 처리한다. `last_used_at IS NULL`은 한 번도 안 쓴 계정이므로 가장 우선순위가 높다.

---

### 4-2. 조합의 실제 키워드 조회

```sql
-- combination_id=5001 의 모든 차원값을 순서대로 가져오기
SELECT d.slug, d.sort_order,
       dv.value, dv.display_value,
       dv.metadata->>'$.lat' AS lat,
       dv.metadata->>'$.lng' AS lng
FROM   combination_values cv
JOIN   dimension_values   dv ON dv.id = cv.dimension_value_id
JOIN   dimensions         d  ON d.id  = dv.dimension_id
WHERE  cv.combination_id = 5001
ORDER BY d.sort_order;

-- 결과:
-- slug='region',        sort_order=0, value='강남구', display_value='강남'
-- slug='subject',       sort_order=1, value='수학',   display_value='수학'
-- slug='learning_type', sort_order=2, value='과외',   display_value='과외'
```

**패턴:** `combination_values`(연결 테이블) → `dimension_values` → `dimensions` 순으로 JOIN한다. `ORDER BY d.sort_order`로 제목 조합 순서를 보장한다.

---

### 4-3. 미사용 조합 조회 (다음 배치 대상)

```sql
-- 아직 한 번도 포스팅 안 한 조합
SELECT c.id, c.spacing_rule_id, c.config
FROM   combinations c
WHERE  c.campaign_id = 1
  AND  c.used_at     IS NULL
ORDER BY c.id ASC
LIMIT 40;   -- batch_size
```

**패턴:** `used_at IS NULL`이 핵심 필터다. 포스팅 완료 후 `UPDATE combinations SET used_at = NOW()` 로 마킹한다.

---

### 4-4. 배치 진행률 확인

```sql
-- 배치별 완료/실패/대기 현황
SELECT b.id AS batch_id,
       a.username,
       b.scheduled_at,
       SUM(CASE WHEN bi.status = 'done'    THEN 1 ELSE 0 END) AS done,
       SUM(CASE WHEN bi.status = 'failed'  THEN 1 ELSE 0 END) AS failed,
       SUM(CASE WHEN bi.status = 'pending' THEN 1 ELSE 0 END) AS pending,
       COUNT(*) AS total
FROM   batches    b
JOIN   accounts   a  ON a.id  = b.account_id
JOIN   batch_items bi ON bi.batch_id = b.id
WHERE  b.campaign_id = 1
GROUP BY b.id, a.username, b.scheduled_at
ORDER BY b.scheduled_at DESC;
```

**패턴:** `SUM(CASE WHEN ... THEN 1 ELSE 0 END)` — 조건별 카운트를 한 쿼리로 처리하는 피벗 패턴이다.

---

### 4-5. 지역 계층 조회 (재귀 CTE)

```sql
-- 서울특별시 하위의 모든 시군구·동 조회
WITH RECURSIVE region_tree AS (
    -- 시작점: 서울특별시
    SELECT id, value, display_value, tier, parent_id, 0 AS depth
    FROM   dimension_values
    WHERE  dimension_id = 1 AND value = '서울특별시'

    UNION ALL

    -- 재귀: 자식 노드
    SELECT dv.id, dv.value, dv.display_value, dv.tier, dv.parent_id, rt.depth + 1
    FROM   dimension_values dv
    JOIN   region_tree rt ON rt.id = dv.parent_id
)
SELECT * FROM region_tree ORDER BY depth, display_value;
```

**패턴:** `WITH RECURSIVE`는 계층 데이터 탐색의 표준 패턴이다. `depth`를 추가해서 몇 단계 깊이인지 추적한다.

---

### 4-6. 교육열 높은 지역 우선 선택

```sql
-- edu_index 4 이상인 시군구만 campaign_selections에 등록
INSERT IGNORE INTO campaign_selections
    (campaign_id, dimension_id, dimension_value_id)
SELECT 1, d.id, dv.id
FROM   dimension_values dv
JOIN   dimensions d ON d.id = dv.dimension_id
WHERE  d.campaign_id = 1
  AND  d.slug        = 'region'
  AND  dv.tier       = 1          -- 시군구 레벨만
  AND  JSON_EXTRACT(dv.metadata, '$.edu_index') >= 4;
```

**패턴:** `JSON_EXTRACT`로 JSON 컬럼 안의 특정 키를 필터 조건으로 쓴다. `INSERT IGNORE`는 이미 있는 행을 에러 없이 건너뛴다.

---

### 4-7. 캠페인별 포스팅 성과 요약

```sql
-- 캠페인별 전체 조합 수, 사용된 수, 남은 수
SELECT camp.name,
       COUNT(c.id)                                          AS total_combos,
       SUM(CASE WHEN c.used_at IS NOT NULL THEN 1 ELSE 0 END) AS used,
       SUM(CASE WHEN c.used_at IS NULL     THEN 1 ELSE 0 END) AS remaining,
       ROUND(
           SUM(CASE WHEN c.used_at IS NOT NULL THEN 1 ELSE 0 END)
           / COUNT(c.id) * 100, 1
       )                                                    AS progress_pct
FROM   campaigns camp
JOIN   combinations c ON c.campaign_id = camp.id
GROUP BY camp.id, camp.name
ORDER BY camp.id;
```

---

### 4-8. 실패한 아이템 재시도 대상 조회

```sql
-- 실패한 batch_items 와 그 조합의 키워드를 함께 조회
SELECT bi.id AS item_id,
       bi.error_message,
       GROUP_CONCAT(
           dv.display_value ORDER BY d.sort_order SEPARATOR ' '
       ) AS keyword
FROM   batch_items bi
JOIN   combinations     c  ON c.id  = bi.combination_id
JOIN   combination_values cv ON cv.combination_id = c.id
JOIN   dimension_values   dv ON dv.id = cv.dimension_value_id
JOIN   dimensions         d  ON d.id  = dv.dimension_id
WHERE  bi.status = 'failed'
GROUP BY bi.id, bi.error_message
ORDER BY bi.id;
```

**패턴:** `GROUP_CONCAT(... ORDER BY ... SEPARATOR ' ')`는 여러 행의 값을 하나의 문자열로 합친다. 조합의 키워드를 한 컬럼으로 보여줄 때 유용하다.

---

## 5. 설계 원칙 요약

| 원칙 | 내용 | 대안 대비 장점 |
|---|---|---|
| ENUM 없음 | 모든 값은 dimension_values 행 | ALTER TABLE 없이 값 추가 가능 |
| 차원 기반 | 컬럼이 아닌 행으로 차원 정의 | 캠페인마다 다른 차원 구조 지원 |
| JSON 확장 | extra / metadata / config 컬럼 | 스키마 변경 없이 속성 추가 |
| 계층 구조 | parent_id 자기참조 | 시도→시군구→동 무한 깊이 지원 |
| 상태 머신 | status 컬럼 + 타임스탬프 | 진행률 추적·재시도·감사 로그 |
| 연결 테이블 | combination_values | M:N을 명시적으로 표현 |
