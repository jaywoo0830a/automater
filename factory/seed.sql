-- ============================================================
-- seed.sql — 초기 데이터 (네이버 블로그 캠페인)
-- ============================================================

SET NAMES utf8mb4;
SET time_zone = '+09:00';
SET FOREIGN_KEY_CHECKS = 0;

-- ------------------------------------------------------------
-- 1. platform
-- ------------------------------------------------------------
INSERT IGNORE INTO platforms (id, name, slug, base_url) VALUES
(1, 'Naver Blog', 'naver_blog', 'https://blog.naver.com');

-- ------------------------------------------------------------
-- 2. campaign
-- ------------------------------------------------------------
INSERT IGNORE INTO campaigns (id, platform_id, name, description, config) VALUES
(1, 1, '서울·경기남부 학원·과외 마케팅',
 '서울 25구 + 경기남부 19시군 × 국영수 × 과외/학원',
 JSON_OBJECT(
     'batch_size',       40,
     'paragraph_count',  3,
     'cooldown_days',    14
 ));

-- ------------------------------------------------------------
-- 3. dimensions  (sort_order = 제목 조합 순서)
-- ------------------------------------------------------------
INSERT IGNORE INTO dimensions (id, campaign_id, name, slug, sort_order) VALUES
(1, 1, '지역',     'region',        0),
(2, 1, '과목',     'subject',       1),
(3, 1, '학습형태', 'learning_type', 2);

-- ------------------------------------------------------------
-- 4. spacing_rules
--    pattern JSON: dimension slug → 뒤에 공백 여부
-- ------------------------------------------------------------
INSERT IGNORE INTO spacing_rules (campaign_id, pattern, description) VALUES
(1, JSON_OBJECT('region',0,'subject',0,'learning_type',0), '전체 붙임: 강남수학과외'),
(1, JSON_OBJECT('region',1,'subject',0,'learning_type',0), '지역만 띔: 강남 수학과외'),
(1, JSON_OBJECT('region',1,'subject',1,'learning_type',0), '전체 띔: 강남 수학 과외');

-- ------------------------------------------------------------
-- 5. dimension_values — 과목 (dimension_id=2)
-- ------------------------------------------------------------
INSERT IGNORE INTO dimension_values (dimension_id, value, display_value, sort_order) VALUES
(2, '국어', '국어', 1),
(2, '영어', '영어', 2),
(2, '수학', '수학', 3);

-- ------------------------------------------------------------
-- 6. dimension_values — 학습형태 (dimension_id=3)
-- ------------------------------------------------------------
INSERT IGNORE INTO dimension_values (dimension_id, value, display_value, sort_order) VALUES
(3, '과외', '과외', 1),
(3, '학원', '학원', 2);

-- ------------------------------------------------------------
-- 7. dimension_values — 지역 Tier 1: 서울 25구 (dimension_id=1)
--    value = 접미사 포함('강남구'), display_value = 접미사 제거('강남')
--    metadata: sido, 필요 시 확장
-- ------------------------------------------------------------
INSERT IGNORE INTO dimension_values
    (dimension_id, value, display_value, tier, sort_order, metadata)
VALUES
-- 서울
(1,'강남구','강남',1,101,JSON_OBJECT('sido','서울')),
(1,'강동구','강동',1,102,JSON_OBJECT('sido','서울')),
(1,'강북구','강북',1,103,JSON_OBJECT('sido','서울')),
(1,'강서구','강서',1,104,JSON_OBJECT('sido','서울')),
(1,'관악구','관악',1,105,JSON_OBJECT('sido','서울')),
(1,'광진구','광진',1,106,JSON_OBJECT('sido','서울')),
(1,'구로구','구로',1,107,JSON_OBJECT('sido','서울')),
(1,'금천구','금천',1,108,JSON_OBJECT('sido','서울')),
(1,'노원구','노원',1,109,JSON_OBJECT('sido','서울')),
(1,'도봉구','도봉',1,110,JSON_OBJECT('sido','서울')),
(1,'동대문구','동대문',1,111,JSON_OBJECT('sido','서울')),
(1,'동작구','동작',1,112,JSON_OBJECT('sido','서울')),
(1,'마포구','마포',1,113,JSON_OBJECT('sido','서울')),
(1,'서대문구','서대문',1,114,JSON_OBJECT('sido','서울')),
(1,'서초구','서초',1,115,JSON_OBJECT('sido','서울')),
(1,'성동구','성동',1,116,JSON_OBJECT('sido','서울')),
(1,'성북구','성북',1,117,JSON_OBJECT('sido','서울')),
(1,'송파구','송파',1,118,JSON_OBJECT('sido','서울')),
(1,'양천구','양천',1,119,JSON_OBJECT('sido','서울')),
(1,'영등포구','영등포',1,120,JSON_OBJECT('sido','서울')),
(1,'용산구','용산',1,121,JSON_OBJECT('sido','서울')),
(1,'은평구','은평',1,122,JSON_OBJECT('sido','서울')),
(1,'종로구','종로',1,123,JSON_OBJECT('sido','서울')),
(1,'중구','중',  1,124,JSON_OBJECT('sido','서울')),
(1,'중랑구','중랑',1,125,JSON_OBJECT('sido','서울')),
-- 경기 남부
(1,'수원시','수원',1,201,JSON_OBJECT('sido','경기')),
(1,'성남시','성남',1,202,JSON_OBJECT('sido','경기')),
(1,'용인시','용인',1,203,JSON_OBJECT('sido','경기')),
(1,'안양시','안양',1,204,JSON_OBJECT('sido','경기')),
(1,'안산시','안산',1,205,JSON_OBJECT('sido','경기')),
(1,'화성시','화성',1,206,JSON_OBJECT('sido','경기')),
(1,'광명시','광명',1,207,JSON_OBJECT('sido','경기')),
(1,'평택시','평택',1,208,JSON_OBJECT('sido','경기')),
(1,'과천시','과천',1,209,JSON_OBJECT('sido','경기')),
(1,'의왕시','의왕',1,210,JSON_OBJECT('sido','경기')),
(1,'군포시','군포',1,211,JSON_OBJECT('sido','경기')),
(1,'하남시','하남',1,212,JSON_OBJECT('sido','경기')),
(1,'오산시','오산',1,213,JSON_OBJECT('sido','경기')),
(1,'시흥시','시흥',1,214,JSON_OBJECT('sido','경기')),
(1,'안성시','안성',1,215,JSON_OBJECT('sido','경기')),
(1,'광주시','광주',1,216,JSON_OBJECT('sido','경기')),
(1,'이천시','이천',1,217,JSON_OBJECT('sido','경기')),
(1,'여주시','여주',1,218,JSON_OBJECT('sido','경기')),
(1,'양평군','양평',1,219,JSON_OBJECT('sido','경기'));

-- ------------------------------------------------------------
-- 8. dimension_values — 지역 Tier 2: 핵심 동면읍 (시군구당 2개, 총 88개)
--    parent_id = Tier 1 시군구의 id (INSERT ... SELECT 로 참조)
-- ------------------------------------------------------------
INSERT IGNORE INTO dimension_values
    (dimension_id, parent_id, value, display_value, tier, sort_order, metadata)
SELECT 1, p.id, '대치동', '대치', 2, 1, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '강남구'
UNION ALL
SELECT 1, p.id, '압구정동', '압구정', 2, 2, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '강남구'
UNION ALL
SELECT 1, p.id, '천호동', '천호', 2, 3, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '강동구'
UNION ALL
SELECT 1, p.id, '길동', '길동', 2, 4, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '강동구'
UNION ALL
SELECT 1, p.id, '미아동', '미아', 2, 5, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '강북구'
UNION ALL
SELECT 1, p.id, '수유동', '수유', 2, 6, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '강북구'
UNION ALL
SELECT 1, p.id, '화곡동', '화곡', 2, 7, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '강서구'
UNION ALL
SELECT 1, p.id, '마곡동', '마곡', 2, 8, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '강서구'
UNION ALL
SELECT 1, p.id, '신림동', '신림', 2, 9, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '관악구'
UNION ALL
SELECT 1, p.id, '봉천동', '봉천', 2, 10, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '관악구'
UNION ALL
SELECT 1, p.id, '화양동', '화양', 2, 11, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '광진구'
UNION ALL
SELECT 1, p.id, '구의동', '구의', 2, 12, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '광진구'
UNION ALL
SELECT 1, p.id, '구로동', '구로', 2, 13, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '구로구'
UNION ALL
SELECT 1, p.id, '신도림동', '신도림', 2, 14, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '구로구'
UNION ALL
SELECT 1, p.id, '가산동', '가산', 2, 15, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '금천구'
UNION ALL
SELECT 1, p.id, '시흥동', '시흥', 2, 16, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '금천구'
UNION ALL
SELECT 1, p.id, '상계동', '상계', 2, 17, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '노원구'
UNION ALL
SELECT 1, p.id, '중계동', '중계', 2, 18, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '노원구'
UNION ALL
SELECT 1, p.id, '쌍문동', '쌍문', 2, 19, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '도봉구'
UNION ALL
SELECT 1, p.id, '창동', '창동', 2, 20, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '도봉구'
UNION ALL
SELECT 1, p.id, '전농동', '전농', 2, 21, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '동대문구'
UNION ALL
SELECT 1, p.id, '휘경동', '휘경', 2, 22, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '동대문구'
UNION ALL
SELECT 1, p.id, '노량진동', '노량진', 2, 23, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '동작구'
UNION ALL
SELECT 1, p.id, '사당동', '사당', 2, 24, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '동작구'
UNION ALL
SELECT 1, p.id, '합정동', '합정', 2, 25, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '마포구'
UNION ALL
SELECT 1, p.id, '상암동', '상암', 2, 26, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '마포구'
UNION ALL
SELECT 1, p.id, '홍제동', '홍제', 2, 27, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '서대문구'
UNION ALL
SELECT 1, p.id, '신촌동', '신촌', 2, 28, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '서대문구'
UNION ALL
SELECT 1, p.id, '서초동', '서초', 2, 29, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '서초구'
UNION ALL
SELECT 1, p.id, '반포동', '반포', 2, 30, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '서초구'
UNION ALL
SELECT 1, p.id, '왕십리동', '왕십리', 2, 31, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '성동구'
UNION ALL
SELECT 1, p.id, '성수동', '성수', 2, 32, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '성동구'
UNION ALL
SELECT 1, p.id, '길음동', '길음', 2, 33, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '성북구'
UNION ALL
SELECT 1, p.id, '돈암동', '돈암', 2, 34, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '성북구'
UNION ALL
SELECT 1, p.id, '잠실동', '잠실', 2, 35, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '송파구'
UNION ALL
SELECT 1, p.id, '문정동', '문정', 2, 36, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '송파구'
UNION ALL
SELECT 1, p.id, '목동', '목동', 2, 37, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '양천구'
UNION ALL
SELECT 1, p.id, '신정동', '신정', 2, 38, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '양천구'
UNION ALL
SELECT 1, p.id, '여의도동', '여의도', 2, 39, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '영등포구'
UNION ALL
SELECT 1, p.id, '영등포동', '영등포', 2, 40, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '영등포구'
UNION ALL
SELECT 1, p.id, '이태원동', '이태원', 2, 41, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '용산구'
UNION ALL
SELECT 1, p.id, '한남동', '한남', 2, 42, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '용산구'
UNION ALL
SELECT 1, p.id, '불광동', '불광', 2, 43, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '은평구'
UNION ALL
SELECT 1, p.id, '응암동', '응암', 2, 44, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '은평구'
UNION ALL
SELECT 1, p.id, '혜화동', '혜화', 2, 45, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '종로구'
UNION ALL
SELECT 1, p.id, '청운동', '청운', 2, 46, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '종로구'
UNION ALL
SELECT 1, p.id, '명동', '명동', 2, 47, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '중구'
UNION ALL
SELECT 1, p.id, '을지로동', '을지로', 2, 48, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '중구'
UNION ALL
SELECT 1, p.id, '면목동', '면목', 2, 49, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '중랑구'
UNION ALL
SELECT 1, p.id, '묵동', '묵동', 2, 50, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '중랑구'
UNION ALL
SELECT 1, p.id, '영통동', '영통', 2, 51, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '수원시'
UNION ALL
SELECT 1, p.id, '인계동', '인계', 2, 52, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '수원시'
UNION ALL
SELECT 1, p.id, '분당동', '분당', 2, 53, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '성남시'
UNION ALL
SELECT 1, p.id, '수정동', '수정', 2, 54, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '성남시'
UNION ALL
SELECT 1, p.id, '수지동', '수지', 2, 55, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '용인시'
UNION ALL
SELECT 1, p.id, '기흥동', '기흥', 2, 56, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '용인시'
UNION ALL
SELECT 1, p.id, '평촌동', '평촌', 2, 57, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '안양시'
UNION ALL
SELECT 1, p.id, '범계동', '범계', 2, 58, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '안양시'
UNION ALL
SELECT 1, p.id, '고잔동', '고잔', 2, 59, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '안산시'
UNION ALL
SELECT 1, p.id, '선부동', '선부', 2, 60, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '안산시'
UNION ALL
SELECT 1, p.id, '동탄동', '동탄', 2, 61, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '화성시'
UNION ALL
SELECT 1, p.id, '병점동', '병점', 2, 62, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '화성시'
UNION ALL
SELECT 1, p.id, '철산동', '철산', 2, 63, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '광명시'
UNION ALL
SELECT 1, p.id, '광명동', '광명', 2, 64, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '광명시'
UNION ALL
SELECT 1, p.id, '평택동', '평택', 2, 65, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '평택시'
UNION ALL
SELECT 1, p.id, '비전동', '비전', 2, 66, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '평택시'
UNION ALL
SELECT 1, p.id, '별양동', '별양', 2, 67, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '과천시'
UNION ALL
SELECT 1, p.id, '중앙동', '중앙', 2, 68, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '과천시'
UNION ALL
SELECT 1, p.id, '내손동', '내손', 2, 69, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '의왕시'
UNION ALL
SELECT 1, p.id, '오전동', '오전', 2, 70, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '의왕시'
UNION ALL
SELECT 1, p.id, '산본동', '산본', 2, 71, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '군포시'
UNION ALL
SELECT 1, p.id, '당동', '당동', 2, 72, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '군포시'
UNION ALL
SELECT 1, p.id, '미사동', '미사', 2, 73, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '하남시'
UNION ALL
SELECT 1, p.id, '풍산동', '풍산', 2, 74, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '하남시'
UNION ALL
SELECT 1, p.id, '오산동', '오산', 2, 75, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '오산시'
UNION ALL
SELECT 1, p.id, '세마동', '세마', 2, 76, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '오산시'
UNION ALL
SELECT 1, p.id, '정왕동', '정왕', 2, 77, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '시흥시'
UNION ALL
SELECT 1, p.id, '능곡동', '능곡', 2, 78, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '시흥시'
UNION ALL
SELECT 1, p.id, '안성동', '안성', 2, 79, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '안성시'
UNION ALL
SELECT 1, p.id, '공도읍', '공도', 2, 80, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '안성시'
UNION ALL
SELECT 1, p.id, '경안동', '경안', 2, 81, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '광주시'
UNION ALL
SELECT 1, p.id, '오포읍', '오포', 2, 82, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '광주시'
UNION ALL
SELECT 1, p.id, '창전동', '창전', 2, 83, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '이천시'
UNION ALL
SELECT 1, p.id, '부발읍', '부발', 2, 84, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '이천시'
UNION ALL
SELECT 1, p.id, '여흥동', '여흥', 2, 85, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '여주시'
UNION ALL
SELECT 1, p.id, '흥천면', '흥천', 2, 86, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '여주시'
UNION ALL
SELECT 1, p.id, '양평읍', '양평', 2, 87, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '양평군'
UNION ALL
SELECT 1, p.id, '용문면', '용문', 2, 88, NULL
    FROM dimension_values p
    WHERE p.dimension_id = 1 AND p.value = '양평군';

SET FOREIGN_KEY_CHECKS = 1;
