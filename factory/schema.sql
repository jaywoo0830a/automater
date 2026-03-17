-- ============================================================
-- automator — schema v2
-- ============================================================
-- 설계 원칙
-- ----------
-- 1. 플랫폼 독립     — platforms 테이블로 어떤 서비스든 추가 가능
-- 2. 키워드 마스터   — keyword_categories / keywords 는 캠페인 독립
--                      지역·과목 등 마스터 데이터를 한 번만 저장하고
--                      여러 캠페인이 재사용한다 (campaign_id 없음)
-- 3. 캠페인-슬롯     — campaign_slots 가 캠페인과 카테고리를 연결하고
--                      sort_order 로 제목 조합 순서를 결정한다
-- 4. 선택 필터       — campaign_keyword_picks 로 이번 seed 에 포함할
--                      키워드를 원본 변경 없이 제어한다
-- 5. 패턴 분리       — spacing_rules 로 띄어쓰기 패턴을 DB 에서 관리
-- ============================================================

SET NAMES utf8mb4;
SET time_zone = '+09:00';

-- ------------------------------------------------------------
-- platforms
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS platforms (
    id         INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    name       VARCHAR(64)   NOT NULL,
    slug       VARCHAR(32)   NOT NULL,   -- 'naver_blog'
    base_url   VARCHAR(256)  NOT NULL DEFAULT '',
    status     VARCHAR(16)   NOT NULL DEFAULT 'active',
    created_at DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE KEY uq_slug (slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- accounts
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS accounts (
    id            INT UNSIGNED     NOT NULL AUTO_INCREMENT,
    platform_id   INT UNSIGNED     NOT NULL,
    username      VARCHAR(128)     NOT NULL,
    password_enc  VARCHAR(512)     NOT NULL DEFAULT '',
    extra         JSON                      DEFAULT NULL,
    last_used_at  DATETIME                  DEFAULT NULL,
    cooldown_days TINYINT UNSIGNED NOT NULL DEFAULT 14,
    status        VARCHAR(16)      NOT NULL DEFAULT 'active',
    note          VARCHAR(256)     NOT NULL DEFAULT '',
    created_at    DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE KEY uq_platform_user (platform_id, username),
    KEY idx_status (status),
    CONSTRAINT fk_account_platform FOREIGN KEY (platform_id) REFERENCES platforms (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- keyword_categories
-- 키워드의 종류. 캠페인에 종속되지 않는 마스터 테이블.
-- 예: 지역(region), 과목(subject), 학습형태(learning_type), 대상(target_audience)
-- 여러 캠페인이 같은 카테고리를 공유한다.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS keyword_categories (
    id         INT UNSIGNED NOT NULL AUTO_INCREMENT,
    name       VARCHAR(64)  NOT NULL,   -- '지역'
    slug       VARCHAR(32)  NOT NULL,   -- 'region'
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE KEY uq_slug (slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- keywords
-- 각 카테고리의 실제 키워드 값. 캠페인과 무관한 마스터 데이터.
-- parent_id 자기참조로 계층 구조 지원 (시도 → 시군구 → 읍면동).
-- value         = 접미사 포함 ('강남구')
-- display_value = 접미사 제거 ('강남')  — 비어있으면 value 와 동일
-- metadata JSON — 지역: {lat, lng, edu_index, area_type}
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS keywords (
    id            INT UNSIGNED     NOT NULL AUTO_INCREMENT,
    category_id   INT UNSIGNED     NOT NULL,
    parent_id     INT UNSIGNED              DEFAULT NULL,
    value         VARCHAR(128)     NOT NULL,
    display_value VARCHAR(128)     NOT NULL DEFAULT '',
    tier          TINYINT UNSIGNED NOT NULL DEFAULT 1,
    active        TINYINT(1)       NOT NULL DEFAULT 1,
    sort_order    SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    metadata      JSON                      DEFAULT NULL,
    created_at    DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE KEY uq_cat_value (category_id, value),
    KEY idx_parent    (parent_id),
    KEY idx_active    (active),
    KEY idx_tier      (tier),
    KEY idx_category  (category_id),
    CONSTRAINT fk_kw_category FOREIGN KEY (category_id) REFERENCES keyword_categories (id),
    CONSTRAINT fk_kw_parent   FOREIGN KEY (parent_id)   REFERENCES keywords           (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- campaigns
-- 작업 묶음. title_template 과 config 로 캠페인별 규칙 정의.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS campaigns (
    id             INT UNSIGNED NOT NULL AUTO_INCREMENT,
    platform_id    INT UNSIGNED NOT NULL,
    name           VARCHAR(128) NOT NULL,
    description    TEXT                  DEFAULT NULL,
    title_template VARCHAR(256) NOT NULL DEFAULT '',
    config         JSON                  DEFAULT NULL,
    status         VARCHAR(16)  NOT NULL DEFAULT 'active',
    created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    KEY idx_platform (platform_id),
    KEY idx_status   (status),
    CONSTRAINT fk_campaign_platform FOREIGN KEY (platform_id) REFERENCES platforms (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- campaign_slots
-- 캠페인이 어떤 keyword_category 를 어떤 순서로 사용하는지 선언.
-- sort_order 가 제목 조합 순서를 결정한다.
-- 예: (campaign_id=1, category_id=1, sort_order=0)  → 지역 먼저
--     (campaign_id=1, category_id=2, sort_order=1)  → 과목 두 번째
-- 같은 카테고리(지역)를 여러 캠페인이 동시에 참조 가능.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS campaign_slots (
    campaign_id INT UNSIGNED     NOT NULL,
    category_id INT UNSIGNED     NOT NULL,
    sort_order  SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    created_at  DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (campaign_id, category_id),
    KEY idx_sort (campaign_id, sort_order),
    CONSTRAINT fk_slot_campaign FOREIGN KEY (campaign_id) REFERENCES campaigns          (id),
    CONSTRAINT fk_slot_category FOREIGN KEY (category_id) REFERENCES keyword_categories (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- spacing_rules
-- 카테고리 간 띄어쓰기 패턴. pattern JSON:
--   {slug: 뒤에_공백(0/1), ...}
-- 예: {"region":1,"subject":1,"learning_type":0} → '강남 수학 과외'
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS spacing_rules (
    id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
    campaign_id INT UNSIGNED NOT NULL,
    pattern     JSON         NOT NULL,
    description VARCHAR(128) NOT NULL DEFAULT '',
    active      TINYINT(1)   NOT NULL DEFAULT 1,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    KEY idx_campaign (campaign_id),
    CONSTRAINT fk_spacing_campaign FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- campaign_keyword_picks
-- 이번 seed 에 포함할 키워드를 원본(keywords) 변경 없이 제어.
-- 특정 category 에 picks 가 없으면 해당 카테고리의 전체 active
-- 키워드를 조합에 포함한다.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS campaign_keyword_picks (
    id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
    campaign_id INT UNSIGNED NOT NULL,
    category_id INT UNSIGNED NOT NULL,
    keyword_id  INT UNSIGNED NOT NULL,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE KEY uq_pick (campaign_id, keyword_id),
    KEY idx_campaign_cat (campaign_id, category_id),
    CONSTRAINT fk_pick_campaign FOREIGN KEY (campaign_id) REFERENCES campaigns          (id),
    CONSTRAINT fk_pick_category FOREIGN KEY (category_id) REFERENCES keyword_categories (id),
    CONSTRAINT fk_pick_keyword  FOREIGN KEY (keyword_id)  REFERENCES keywords           (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- combinations
-- 카테시안 곱의 결과 하나. 실제 키워드 연결은 combination_keywords.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS combinations (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    campaign_id     INT UNSIGNED    NOT NULL,
    spacing_rule_id INT UNSIGNED             DEFAULT NULL,
    config          JSON                     DEFAULT NULL,
    -- {"has_suffix":1} — display_value(0) vs value(1) 선택
    used_at         DATETIME                 DEFAULT NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    KEY idx_campaign (campaign_id),
    KEY idx_used_at  (used_at),
    CONSTRAINT fk_combo_campaign FOREIGN KEY (campaign_id)     REFERENCES campaigns     (id),
    CONSTRAINT fk_combo_spacing  FOREIGN KEY (spacing_rule_id) REFERENCES spacing_rules (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- combination_keywords
-- combinations × keywords M:N 연결 테이블.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS combination_keywords (
    combination_id BIGINT UNSIGNED NOT NULL,
    keyword_id     INT UNSIGNED    NOT NULL,

    PRIMARY KEY (combination_id, keyword_id),
    KEY idx_kw (keyword_id),
    CONSTRAINT fk_ck_combination FOREIGN KEY (combination_id) REFERENCES combinations (id),
    CONSTRAINT fk_ck_keyword     FOREIGN KEY (keyword_id)     REFERENCES keywords     (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- batches
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS batches (
    id           INT UNSIGNED NOT NULL AUTO_INCREMENT,
    campaign_id  INT UNSIGNED NOT NULL,
    account_id   INT UNSIGNED NOT NULL,
    scheduled_at DATETIME     NOT NULL,
    status       VARCHAR(16)  NOT NULL DEFAULT 'pending',
    worker_pid   INT                   DEFAULT NULL,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at   DATETIME              DEFAULT NULL,
    completed_at DATETIME              DEFAULT NULL,

    PRIMARY KEY (id),
    KEY idx_status    (status),
    KEY idx_account   (account_id),
    KEY idx_campaign  (campaign_id),
    KEY idx_scheduled (scheduled_at),
    CONSTRAINT fk_batch_campaign FOREIGN KEY (campaign_id) REFERENCES campaigns (id),
    CONSTRAINT fk_batch_account  FOREIGN KEY (account_id)  REFERENCES accounts  (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- batch_items
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS batch_items (
    id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    batch_id       INT UNSIGNED    NOT NULL,
    combination_id BIGINT UNSIGNED NOT NULL,
    status         VARCHAR(16)     NOT NULL DEFAULT 'pending',
    result_url     VARCHAR(512)             DEFAULT NULL,
    error_message  TEXT                     DEFAULT NULL,
    created_at     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at   DATETIME                 DEFAULT NULL,

    PRIMARY KEY (id),
    UNIQUE KEY uq_batch_combo (batch_id, combination_id),
    KEY idx_status      (status),
    KEY idx_combination (combination_id),
    CONSTRAINT fk_item_batch FOREIGN KEY (batch_id)       REFERENCES batches      (id),
    CONSTRAINT fk_item_combo FOREIGN KEY (combination_id) REFERENCES combinations (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
