-- ============================================================
-- seed.sql — 초기 데이터
-- ============================================================

SET NAMES utf8mb4;
SET time_zone = '+09:00';
SET FOREIGN_KEY_CHECKS = 0;

-- 1. platform
INSERT IGNORE INTO platforms (id, name, slug, base_url) VALUES
(1, 'Naver Blog', 'naver_blog', 'https://blog.naver.com');

-- ------------------------------------------------------------
-- 2. keyword_categories — 캠페인 독립 마스터
-- ------------------------------------------------------------
INSERT IGNORE INTO keyword_categories (id, name, slug) VALUES
(1, '지역',     'region'),
(2, '과목',     'subject'),
(3, '학습형태', 'learning_type'),
(4, '대상',     'target_audience');

-- ------------------------------------------------------------
-- 3. keywords — 과목 (category_id=2)
-- ------------------------------------------------------------
INSERT IGNORE INTO keywords (category_id, value, display_value, sort_order) VALUES
(2, '국어', '국어', 1),
(2, '영어', '영어', 2),
(2, '수학', '수학', 3);

-- ------------------------------------------------------------
-- 4. keywords — 학습형태 (category_id=3)
-- ------------------------------------------------------------
INSERT IGNORE INTO keywords (category_id, value, display_value, sort_order) VALUES
(3, '과외', '과외', 1),
(3, '학원', '학원', 2);

-- ------------------------------------------------------------
-- 5. campaigns
-- ------------------------------------------------------------
INSERT IGNORE INTO campaigns (id, platform_id, name, description, title_template, config) VALUES
(1, 1, '서울·경기남부 학원·과외 마케팅',
 '서울 25구 + 경기남부 × 국영수 × 과외/학원',
 '{region} {subject} {learning_type} {salt}',
 JSON_OBJECT('batch_size',40,'paragraph_count',3,'cooldown_days',14));

-- ------------------------------------------------------------
-- 6. campaign_slots — 캠페인이 어떤 카테고리를 어떤 순서로 쓸지
-- ------------------------------------------------------------
INSERT IGNORE INTO campaign_slots (campaign_id, category_id, sort_order) VALUES
(1, 1, 0),   -- 캠페인1 → 지역 먼저
(1, 2, 1),   -- 캠페인1 → 과목 두 번째
(1, 3, 2);   -- 캠페인1 → 학습형태 세 번째

-- ------------------------------------------------------------
-- 7. spacing_rules
-- ------------------------------------------------------------
INSERT IGNORE INTO spacing_rules (campaign_id, pattern, description) VALUES
(1, JSON_OBJECT('region',0,'subject',0,'learning_type',0), '전체 붙임: 강남수학과외'),
(1, JSON_OBJECT('region',1,'subject',0,'learning_type',0), '지역만 띔: 강남 수학과외'),
(1, JSON_OBJECT('region',1,'subject',1,'learning_type',0), '전체 띔: 강남 수학 과외');

SET FOREIGN_KEY_CHECKS = 1;

-- ------------------------------------------------------------
-- 지역 데이터 (Tier 0~2) — 자동 생성
-- python scripts/build_region_seed.py --all
-- mysql ... automator < factory/seed_regions.sql
-- ------------------------------------------------------------
