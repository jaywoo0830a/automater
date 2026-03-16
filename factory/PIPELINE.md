# 네이버 블로그 대량 포스팅 파이프라인

## 개요

지역 × 과목 × 학습형태의 모든 조합을 계정 풀에 분배해 병렬로 예약 발행하는 시스템이다.
한 사이클이 끝나면 2주 쿨다운 후 동일한 흐름을 반복한다.

---

## 전체 흐름

```
[준비] DB 초기화 → seed
         ↓
[1단계] ComboGenerator   조합 생성
         ↓
[2단계] BatchDispatcher  계정에 배치 할당
         ↓
[3단계] FactoryRunner    병렬 실행
         ↓
[대기] 2주 쿨다운
         ↓
[반복] 다음 사이클
```

---

## 단계별 상세

### 준비 — DB 초기화 및 seed

```bash
bash ./run/factory.sh db-up    # MySQL 컨테이너 시작
bash ./run/factory.sh seed     # 조합 테이블 채우기
```

`docker-entrypoint-initdb.d/` 에 의해 컨테이너 최초 기동 시 `schema.sql` → `seed.sql` 순서로 자동 실행된다.

**seed.sql 이 채우는 데이터:**

| 테이블 | 내용 |
|---|---|
| `platforms` | Naver Blog 1건 |
| `campaigns` | 서울·경기남부 학원·과외 마케팅 1건 |
| `dimensions` | 지역(sort 0) / 과목(sort 1) / 학습형태(sort 2) |
| `spacing_rules` | 3가지 띄어쓰기 패턴 |
| `dimension_values` | 지역 Tier1 44개(서울 25구 + 경기남부 19시군) + Tier2 88개(핵심 동면읍) / 과목 3개(국영수) / 학습형태 2개(과외·학원) |

---

### 1단계 — 조합 생성 (`ComboGenerator`)

```bash
bash ./run/factory.sh seed
```

**동작:**

1. `dimensions` 에서 sort_order 순으로 차원 목록 조회
2. 각 차원의 활성 `dimension_values` 조회
3. `spacing_rules` 에서 활성 패턴 조회
4. 카테시안 곱 계산

```
지역(132개) × 과목(3개) × 학습형태(2개) × 띄어쓰기(3패턴) × 접미사(2가지)
= 132 × 3 × 2 × 3 × 2 = 4,752개
```

5. `combinations` + `combination_values` 에 `INSERT IGNORE` (멱등 — 재실행 안전)

**생성되는 제목 예시 (군포시 + 수학 + 과외):**

| 패턴 | 접미사 없음 | 접미사 있음 |
|---|---|---|
| `(0,0)` 전체 붙임 | `군포수학과외` | `군포시수학과외` |
| `(1,0)` 지역만 띔 | `군포 수학과외` | `군포시 수학과외` |
| `(1,1)` 전체 띔 | `군포 수학 과외` | `군포시 수학 과외` |

---

### 2단계 — 배치 할당 (`BatchDispatcher`)

```bash
bash ./run/factory.sh dispatch [--schedule-at "2026-03-25 09:00"]
```

**동작:**

1. `accounts` 에서 가용 계정 조회

   ```
   조건: status = 'active'
         AND (last_used_at IS NULL OR last_used_at + cooldown_days < NOW())
   정렬: last_used_at ASC (오래된 것 먼저)
   ```

2. `combinations` 에서 `used_at IS NULL` 인 미사용 조합 조회 (id ASC)

3. 조합을 **40개씩** 청크로 분할

4. 청크 하나 + 계정 하나 = 배치 1개 생성

   - `batches` 에 INSERT (status = `pending`)
   - `batch_items` 에 40개 INSERT
   - 계정 `last_used_at` 업데이트, `status` → `cooling`
   - 조합 `used_at` 업데이트

5. 배치 간 예약 시각은 **10분씩 스태거** (스팸 탐지 우회)

   ```
   1번 배치: schedule_base (예: 09:00)
   2번 배치: 09:10
   3번 배치: 09:20
   ...
   ```

**계정 가용 여부 판단:**

```
last_used_at = None          → 신규 계정, 즉시 가용
last_used_at + 14일 < 현재  → 쿨다운 만료, 가용
last_used_at + 14일 ≥ 현재  → 쿨다운 중, 스킵
```

---

### 3단계 — 병렬 실행 (`FactoryRunner`)

```bash
bash ./run/factory.sh run [--workers 5] [--dry-run]
```

**동작:**

1. `pending` 상태인 배치 수 조회
2. `multiprocessing.Pool(workers)` 로 워커 병렬 실행
3. 각 워커가 배치 하나를 클레임 (`status` → `running`, `worker_pid` 기록)
4. 배치 안의 `batch_items` 를 순서대로 실행

**워커 내부 흐름 (배치 1개):**

```
Playwright 브라우저 실행
    ↓
세션 파일로 자동 로그인
    ↓
batch_items 반복 (최대 40개):
    ├── TitleOption 생성  (combination → 제목 문자열)
    ├── ContentOption 생성 (paragraph_prompt 포함)
    ├── SEOOption 적용     (키워드·글자 수·톤 제어)
    ├── MetaOption 생성    (scheduled_at = batches.scheduled_at)
    └── NaverBlogJob.run(editor)
            ├── Gemini API → 단락 생성
            ├── SmartEditorOne → 에디터 조작
            └── 예약 발행 설정 → "발행하기" 클릭
    ↓
batch_items.status → done / failed
batch_items.result_url 기록
    ↓
batches.status → done / failed
    ↓
세션 파일 저장 (로그인 상태 유지)
```

**dry-run 모드:**
`--dry-run` 플래그를 주면 발행 팝오버가 열리지만 "발행하기" 버튼을 누르지 않는다.
테스트 및 UI 흐름 검증용.

---

## 상태 확인

```bash
bash ./run/factory.sh status
```

출력 예시:

```
=== Factory Status ===

Batches:
  pending   : 80
  running   : 5
  done      : 35
  failed    : 0

Combinations: 4752 total, 3960 pending

Accounts:
  active    : 15
  cooling   : 5
  disabled  : 0
```

---

## 데이터베이스 상태 전이

### `batches.status`

```
pending → running → done
                 ↘ failed
```

### `accounts.status`

```
active → cooling  (dispatch 후)
cooling → active  (2주 후 자동 전환 — 다음 dispatch 시 cooldown 만료 확인)
active → disabled (수동)
```

### `batch_items.status`

```
pending → done    (발행 성공)
        ↘ failed  (브라우저/에디터 오류)
```

---

## 핵심 수치 요약

| 항목 | 값 | 위치 |
|---|---|---|
| 배치당 포스팅 수 | 40개 | `dispatcher.py::BATCH_SIZE` |
| 배치 간 예약 간격 | 10분 | `dispatcher.py::SCHEDULE_JITTER_MINUTES` |
| 계정 쿨다운 | 14일 | `schema.sql::accounts.cooldown_days` |
| 지역 Tier1 | 44개 | `seed.sql` |
| 지역 Tier2 | 88개 | `seed.sql` |
| 과목 | 3개 (국영수) | `seed.sql` |
| 학습형태 | 2개 (과외·학원) | `seed.sql` |
| 띄어쓰기 패턴 | 3가지 | `seed.sql::spacing_rules` |
| 총 조합 | 4,752개 | `132 × 3 × 2 × 3 × 2` |
| 필요 계정 | 최소 119개 | `4,752 ÷ 40` |

---

## 빠른 시작

```bash
# 1. 초기 환경 설정 (최초 1회)
bash ./run/init.sh
cp .env.example .env
cp factory/.env.example factory/.env

# 2. DB 시작 및 데이터 준비
bash ./run/factory.sh db-up
bash ./run/factory.sh seed

# 3. 계정 등록 (accounts 테이블에 INSERT)
# → 별도 계정 등록 스크립트 필요 (현재 수동)

# 4. 배치 할당
bash ./run/factory.sh dispatch --schedule-at "2026-03-25 09:00"

# 5. 실행 (dry-run 먼저 권장)
bash ./run/factory.sh run --workers 5 --dry-run
bash ./run/factory.sh run --workers 5

# 6. 상황 확인
bash ./run/factory.sh status
```
