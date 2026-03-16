-- ============================================================
-- automator — generic schema
-- ============================================================
-- 설계 원칙
-- ----------
-- 1. 플랫폼 독립 — platforms 테이블로 어떤 서비스든 추가 가능
-- 2. ENUM 없음   — 모든 도메인 값은 dimension_values 로 관리
--                  추가/변경 = INSERT, ALTER TABLE 불필요
-- 3. 차원 기반   — 지역/과목/학습형태/가격대 등 모두 dimensions 행
-- 4. 캠페인 단위 — 작업을 campaign 으로 묶어 재사용·비교 가능
-- 5. 패턴 분리   — spacing_rules 로 띄어쓰기 패턴을 DB 에서 관리
-- ============================================================

SET NAMES utf8mb4;
SET time_zone = '+09:00';

-- ------------------------------------------------------------
-- platforms
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS platforms (
    id          INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    name        VARCHAR(64)     NOT NULL,
    slug        VARCHAR(32)     NOT NULL,            -- 'naver_blog'
    base_url    VARCHAR(256)    NOT NULL DEFAULT '',
    status      VARCHAR(16)     NOT NULL DEFAULT 'active',
    created_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE KEY uq_slug (slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- accounts
-- 플랫폼별 계정 풀. extra JSON 으로 platform 마다 다른 필드 수용.
-- 예: {"blog_id":"rlawjddn","session_path":"sessions/a1.json","proxy":"1.2.3.4:8080"}
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS accounts (
    id              INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    platform_id     INT UNSIGNED    NOT NULL,
    username        VARCHAR(128)    NOT NULL,
    password_enc    VARCHAR(512)    NOT NULL DEFAULT '',
    extra           JSON                     DEFAULT NULL,
    last_used_at    DATETIME                 DEFAULT NULL,
    cooldown_days   TINYINT UNSIGNED NOT NULL DEFAULT 14,
    status          VARCHAR(16)     NOT NULL DEFAULT 'active',
    note            VARCHAR(256)    NOT NULL DEFAULT '',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE KEY uq_platform_user (platform_id, username),
    KEY idx_status (status),
    CONSTRAINT fk_account_platform FOREIGN KEY (platform_id) REFERENCES platforms (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- campaigns
-- 작업 묶음 단위. config JSON 으로 캠페인별 설정 자유 확장.
-- 예: {"batch_size":40,"paragraph_count":3}
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS campaigns (
    id          INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    platform_id INT UNSIGNED    NOT NULL,
    name        VARCHAR(128)    NOT NULL,
    description TEXT                     DEFAULT NULL,
    config      JSON                     DEFAULT NULL,
    status      VARCHAR(16)     NOT NULL DEFAULT 'active',
    created_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    KEY idx_platform (platform_id),
    KEY idx_status   (status),
    CONSTRAINT fk_campaign_platform FOREIGN KEY (platform_id) REFERENCES platforms (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- dimensions
-- 조합의 축 정의. 캠페인별로 자유롭게 추가.
-- sort_order 가 제목 조합 순서를 결정.
-- 예: 지역(0) + 과목(1) + 학습형태(2) → '강남 수학 과외'
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dimensions (
    id          INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    campaign_id INT UNSIGNED    NOT NULL,
    name        VARCHAR(64)     NOT NULL,   -- '과목'
    slug        VARCHAR(32)     NOT NULL,   -- 'subject'
    sort_order  SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    created_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE KEY uq_campaign_slug (campaign_id, slug),
    CONSTRAINT fk_dimension_campaign FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- dimension_values
-- 각 차원의 실제 값. 계층 구조 지원 (parent_id).
-- metadata JSON 으로 도메인 특화 속성 자유 확장.
-- 예: {"sido":"서울","sigungu":"강남구"}
-- value       = 접미사 포함 버전 ('강남구')
-- display_value = 접미사 제거 버전 ('강남')  — 빈 문자열이면 value 와 동일하게 취급
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dimension_values (
    id            INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    dimension_id  INT UNSIGNED    NOT NULL,
    parent_id     INT UNSIGNED             DEFAULT NULL,
    value         VARCHAR(128)    NOT NULL,
    display_value VARCHAR(128)    NOT NULL DEFAULT '',
    tier          TINYINT UNSIGNED NOT NULL DEFAULT 1,
    active        TINYINT(1)      NOT NULL DEFAULT 1,
    sort_order    SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    metadata      JSON                     DEFAULT NULL,
    created_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE KEY uq_dim_value (dimension_id, value),
    KEY idx_parent (parent_id),
    KEY idx_active (active),
    KEY idx_tier   (tier),
    CONSTRAINT fk_dv_dimension FOREIGN KEY (dimension_id) REFERENCES dimensions     (id),
    CONSTRAINT fk_dv_parent    FOREIGN KEY (parent_id)    REFERENCES dimension_values (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- spacing_rules
-- 차원 간 띄어쓰기 패턴을 DB 에서 관리.
-- pattern JSON: dimension slug → 뒤에 공백 여부 (0/1).
-- 예: {"region":0,"subject":0} → '강남수학과외'
--     {"region":1,"subject":0} → '강남 수학과외'
--     {"region":1,"subject":1} → '강남 수학 과외'
-- 마지막 차원의 값은 무시 (뒤에 아무것도 없으므로).
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS spacing_rules (
    id          INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    campaign_id INT UNSIGNED    NOT NULL,
    pattern     JSON            NOT NULL,
    description VARCHAR(128)    NOT NULL DEFAULT '',
    active      TINYINT(1)      NOT NULL DEFAULT 1,
    created_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    KEY idx_campaign (campaign_id),
    CONSTRAINT fk_spacing_campaign FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- campaign_selections
-- 캠페인별 선택된 dimension_values 목록.
-- seed 시 이 목록에 있는 값들만 카테시안 곱에 포함된다.
-- dimension 별로 덮어쓰기 방식 — select 명령 실행 시 해당 dimension 의
-- 기존 선택을 DELETE 후 INSERT 한다.
-- 비어있는 dimension 은 해당 차원의 전체 값을 사용한다.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS campaign_selections (
    id                 INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    campaign_id        INT UNSIGNED    NOT NULL,
    dimension_id       INT UNSIGNED    NOT NULL,
    dimension_value_id INT UNSIGNED    NOT NULL,
    created_at         DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE KEY uq_selection (campaign_id, dimension_value_id),
    KEY idx_campaign_dim (campaign_id, dimension_id),
    CONSTRAINT fk_sel_campaign FOREIGN KEY (campaign_id)        REFERENCES campaigns        (id),
    CONSTRAINT fk_sel_dim      FOREIGN KEY (dimension_id)       REFERENCES dimensions       (id),
    CONSTRAINT fk_sel_dv       FOREIGN KEY (dimension_value_id) REFERENCES dimension_values (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- combinations
-- 카테시안 곱의 결과 하나.
-- 어떤 dimension_values 조합을 어떤 spacing_rule 로 쓸지.
-- 실제 값 연결은 combination_values (다대다).
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS combinations (
    id               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    campaign_id      INT UNSIGNED    NOT NULL,
    spacing_rule_id  INT UNSIGNED             DEFAULT NULL,
    config           JSON                     DEFAULT NULL,
    -- 예: {"has_suffix":1} — display_value(0) vs value(1) 선택
    used_at          DATETIME                 DEFAULT NULL,
    created_at       DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    KEY idx_campaign (campaign_id),
    KEY idx_used_at  (used_at),
    CONSTRAINT fk_combo_campaign FOREIGN KEY (campaign_id)     REFERENCES campaigns     (id),
    CONSTRAINT fk_combo_spacing  FOREIGN KEY (spacing_rule_id) REFERENCES spacing_rules (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- combination_values
-- combinations × dimension_values 연결 테이블.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS combination_values (
    combination_id     BIGINT UNSIGNED NOT NULL,
    dimension_value_id INT UNSIGNED    NOT NULL,

    PRIMARY KEY (combination_id, dimension_value_id),
    KEY idx_dv (dimension_value_id),
    CONSTRAINT fk_cv_combination FOREIGN KEY (combination_id)     REFERENCES combinations    (id),
    CONSTRAINT fk_cv_dv          FOREIGN KEY (dimension_value_id) REFERENCES dimension_values (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- batches
-- 계정 1개에 할당된 작업 묶음.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS batches (
    id              INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    campaign_id     INT UNSIGNED    NOT NULL,
    account_id      INT UNSIGNED    NOT NULL,
    scheduled_at    DATETIME        NOT NULL,
    status          VARCHAR(16)     NOT NULL DEFAULT 'pending',
    worker_pid      INT                      DEFAULT NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at      DATETIME                 DEFAULT NULL,
    completed_at    DATETIME                 DEFAULT NULL,

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
-- 배치 안의 개별 실행 단위.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS batch_items (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    batch_id        INT UNSIGNED    NOT NULL,
    combination_id  BIGINT UNSIGNED NOT NULL,
    status          VARCHAR(16)     NOT NULL DEFAULT 'pending',
    result_url      VARCHAR(512)             DEFAULT NULL,
    error_message   TEXT                     DEFAULT NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at    DATETIME                 DEFAULT NULL,

    PRIMARY KEY (id),
    UNIQUE KEY uq_batch_combo (batch_id, combination_id),
    KEY idx_status      (status),
    KEY idx_combination (combination_id),
    CONSTRAINT fk_item_batch FOREIGN KEY (batch_id)       REFERENCES batches      (id),
    CONSTRAINT fk_item_combo FOREIGN KEY (combination_id) REFERENCES combinations (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
