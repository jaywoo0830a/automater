-- ============================================================
-- seed_regions.sql — 서울·경기 지역 데이터
--
-- 계층 구조
--   Tier 1  시군구   서울 25구 + 경기 주요 시군 (ALL)
--   Tier 2  동면읍   edu_index >= 4 인 시군구당 대표 2개
--
-- metadata JSON
--   sido        STRING  시도 ('서울', '경기')
--   lat / lng   FLOAT   중심 좌표 (WGS84)
--   population  INT     인구 (만명, 2023 추정)
--   edu_index   INT     교육열 지수 1~5 (학원·과외 수요)
--   area_type   STRING  지역 유형
-- ============================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================
-- Tier 1 — 시군구
-- ============================================================
INSERT IGNORE INTO keywords
    (category_id, value, display_value, tier, sort_order, metadata)
VALUES

-- ── 서울 강남권 (edu 5) ─────────────────────────────────────
(1,'강남구','강남',  1,101,JSON_OBJECT('sido','서울','lat',37.5172,'lng',127.0473,'population',54,'edu_index',5,'area_type','강남권')),
(1,'서초구','서초',  1,102,JSON_OBJECT('sido','서울','lat',37.4837,'lng',127.0324,'population',43,'edu_index',5,'area_type','강남권')),
(1,'송파구','송파',  1,103,JSON_OBJECT('sido','서울','lat',37.5145,'lng',127.1059,'population',67,'edu_index',5,'area_type','강남권')),
(1,'양천구','양천',  1,104,JSON_OBJECT('sido','서울','lat',37.5170,'lng',126.8667,'population',47,'edu_index',5,'area_type','서남권')),

-- ── 서울 edu 4 ──────────────────────────────────────────────
(1,'강동구','강동',  1,105,JSON_OBJECT('sido','서울','lat',37.5301,'lng',127.1238,'population',46,'edu_index',4,'area_type','강남권')),
(1,'노원구','노원',  1,106,JSON_OBJECT('sido','서울','lat',37.6542,'lng',127.0568,'population',53,'edu_index',4,'area_type','동북권')),
(1,'성동구','성동',  1,107,JSON_OBJECT('sido','서울','lat',37.5633,'lng',127.0371,'population',30,'edu_index',4,'area_type','동북권')),
(1,'광진구','광진',  1,108,JSON_OBJECT('sido','서울','lat',37.5387,'lng',127.0823,'population',35,'edu_index',4,'area_type','동북권')),
(1,'동작구','동작',  1,109,JSON_OBJECT('sido','서울','lat',37.5124,'lng',126.9393,'population',40,'edu_index',4,'area_type','서남권')),
(1,'용산구','용산',  1,110,JSON_OBJECT('sido','서울','lat',37.5326,'lng',126.9904,'population',23,'edu_index',4,'area_type','도심권')),

-- ── 서울 edu 3 ──────────────────────────────────────────────
(1,'마포구','마포',  1,111,JSON_OBJECT('sido','서울','lat',37.5665,'lng',126.9010,'population',37,'edu_index',3,'area_type','서북권')),
(1,'은평구','은평',  1,112,JSON_OBJECT('sido','서울','lat',37.6176,'lng',126.9227,'population',48,'edu_index',3,'area_type','서북권')),
(1,'서대문구','서대문',1,113,JSON_OBJECT('sido','서울','lat',37.5791,'lng',126.9368,'population',32,'edu_index',3,'area_type','서북권')),
(1,'종로구','종로',  1,114,JSON_OBJECT('sido','서울','lat',37.5735,'lng',126.9790,'population',15,'edu_index',3,'area_type','도심권')),
(1,'중구','중',      1,115,JSON_OBJECT('sido','서울','lat',37.5640,'lng',126.9975,'population',13,'edu_index',3,'area_type','도심권')),
(1,'성북구','성북',  1,116,JSON_OBJECT('sido','서울','lat',37.5894,'lng',127.0167,'population',44,'edu_index',3,'area_type','동북권')),
(1,'강북구','강북',  1,117,JSON_OBJECT('sido','서울','lat',37.6396,'lng',127.0255,'population',31,'edu_index',3,'area_type','동북권')),
(1,'도봉구','도봉',  1,118,JSON_OBJECT('sido','서울','lat',37.6688,'lng',127.0471,'population',33,'edu_index',3,'area_type','동북권')),
(1,'중랑구','중랑',  1,119,JSON_OBJECT('sido','서울','lat',37.6063,'lng',127.0927,'population',40,'edu_index',3,'area_type','동북권')),
(1,'동대문구','동대문',1,120,JSON_OBJECT('sido','서울','lat',37.5744,'lng',127.0403,'population',35,'edu_index',3,'area_type','동북권')),
(1,'영등포구','영등포',1,121,JSON_OBJECT('sido','서울','lat',37.5263,'lng',126.8963,'population',40,'edu_index',3,'area_type','서남권')),
(1,'강서구','강서',  1,122,JSON_OBJECT('sido','서울','lat',37.5509,'lng',126.8496,'population',60,'edu_index',3,'area_type','서남권')),
(1,'구로구','구로',  1,123,JSON_OBJECT('sido','서울','lat',37.4955,'lng',126.8875,'population',42,'edu_index',3,'area_type','서남권')),
(1,'금천구','금천',  1,124,JSON_OBJECT('sido','서울','lat',37.4600,'lng',126.9001,'population',24,'edu_index',3,'area_type','서남권')),
(1,'관악구','관악',  1,125,JSON_OBJECT('sido','서울','lat',37.4784,'lng',126.9516,'population',50,'edu_index',3,'area_type','서남권')),

-- ── 경기 edu 5 ──────────────────────────────────────────────
(1,'성남시','성남',  1,201,JSON_OBJECT('sido','경기','lat',37.4201,'lng',127.1268,'population', 93,'edu_index',5,'area_type','경기핵심')),
(1,'과천시','과천',  1,202,JSON_OBJECT('sido','경기','lat',37.4292,'lng',126.9878,'population',  8,'edu_index',5,'area_type','경기핵심')),

-- ── 경기 edu 4 ──────────────────────────────────────────────
(1,'수원시','수원',  1,203,JSON_OBJECT('sido','경기','lat',37.2636,'lng',127.0286,'population',119,'edu_index',4,'area_type','경기핵심')),
(1,'용인시','용인',  1,204,JSON_OBJECT('sido','경기','lat',37.2411,'lng',127.1776,'population',108,'edu_index',4,'area_type','경기핵심')),
(1,'안양시','안양',  1,205,JSON_OBJECT('sido','경기','lat',37.3943,'lng',126.9568,'population', 57,'edu_index',4,'area_type','경기핵심')),
(1,'고양시','고양',  1,206,JSON_OBJECT('sido','경기','lat',37.6584,'lng',126.8320,'population',107,'edu_index',4,'area_type','경기핵심')),
(1,'광명시','광명',  1,207,JSON_OBJECT('sido','경기','lat',37.4784,'lng',126.8644,'population', 30,'edu_index',4,'area_type','경기주요')),
(1,'의왕시','의왕',  1,208,JSON_OBJECT('sido','경기','lat',37.3449,'lng',126.9688,'population', 16,'edu_index',4,'area_type','경기주요')),
(1,'군포시','군포',  1,209,JSON_OBJECT('sido','경기','lat',37.3615,'lng',126.9352,'population', 28,'edu_index',4,'area_type','경기주요')),
(1,'하남시','하남',  1,210,JSON_OBJECT('sido','경기','lat',37.5396,'lng',127.2148,'population', 28,'edu_index',4,'area_type','경기주요')),
(1,'구리시','구리',  1,211,JSON_OBJECT('sido','경기','lat',37.5943,'lng',127.1296,'population', 19,'edu_index',4,'area_type','경기주요')),
(1,'남양주시','남양주',1,212,JSON_OBJECT('sido','경기','lat',37.6360,'lng',127.2163,'population', 73,'edu_index',4,'area_type','경기주요')),

-- ── 경기 edu 3 ──────────────────────────────────────────────
(1,'안산시','안산',  1,213,JSON_OBJECT('sido','경기','lat',37.3219,'lng',126.8309,'population', 65,'edu_index',3,'area_type','경기주요')),
(1,'화성시','화성',  1,214,JSON_OBJECT('sido','경기','lat',37.1997,'lng',126.8312,'population', 87,'edu_index',3,'area_type','경기주요')),
(1,'평택시','평택',  1,215,JSON_OBJECT('sido','경기','lat',36.9921,'lng',127.1128,'population', 58,'edu_index',3,'area_type','경기주요')),
(1,'파주시','파주',  1,216,JSON_OBJECT('sido','경기','lat',37.7600,'lng',126.7800,'population', 48,'edu_index',3,'area_type','경기주요')),
(1,'의정부시','의정부',1,217,JSON_OBJECT('sido','경기','lat',37.7382,'lng',127.0437,'population', 45,'edu_index',3,'area_type','경기주요')),
(1,'시흥시','시흥',  1,218,JSON_OBJECT('sido','경기','lat',37.3800,'lng',126.8029,'population', 52,'edu_index',3,'area_type','경기일반')),
(1,'부천시','부천',  1,219,JSON_OBJECT('sido','경기','lat',37.5034,'lng',126.7660,'population', 82,'edu_index',3,'area_type','경기주요')),
(1,'광주시','광주',  1,220,JSON_OBJECT('sido','경기','lat',37.4296,'lng',127.2559,'population', 38,'edu_index',3,'area_type','경기일반')),
(1,'양주시','양주',  1,221,JSON_OBJECT('sido','경기','lat',37.7850,'lng',127.0456,'population', 24,'edu_index',2,'area_type','경기일반')),
(1,'오산시','오산',  1,222,JSON_OBJECT('sido','경기','lat',37.1498,'lng',127.0778,'population', 22,'edu_index',3,'area_type','경기일반')),
(1,'이천시','이천',  1,223,JSON_OBJECT('sido','경기','lat',37.2791,'lng',127.4415,'population', 23,'edu_index',2,'area_type','경기일반')),
(1,'안성시','안성',  1,224,JSON_OBJECT('sido','경기','lat',37.0078,'lng',127.2797,'population', 19,'edu_index',2,'area_type','경기일반')),
(1,'여주시','여주',  1,225,JSON_OBJECT('sido','경기','lat',37.2982,'lng',127.6374,'population', 11,'edu_index',2,'area_type','경기일반')),
(1,'양평군','양평',  1,226,JSON_OBJECT('sido','경기','lat',37.4914,'lng',127.4874,'population', 12,'edu_index',2,'area_type','경기일반')),
(1,'가평군','가평',  1,227,JSON_OBJECT('sido','경기','lat',37.8315,'lng',127.5106,'population',  7,'edu_index',1,'area_type','경기일반')),
(1,'포천시','포천',  1,228,JSON_OBJECT('sido','경기','lat',37.8946,'lng',127.2003,'population', 15,'edu_index',2,'area_type','경기일반')),
(1,'동두천시','동두천',1,229,JSON_OBJECT('sido','경기','lat',37.9036,'lng',127.0601,'population',  9,'edu_index',2,'area_type','경기일반')),
(1,'연천군','연천',  1,230,JSON_OBJECT('sido','경기','lat',38.0961,'lng',127.0749,'population',  5,'edu_index',1,'area_type','경기일반'));

-- ============================================================
-- Tier 2 — edu_index >= 4 인 시군구의 대표 동 2개
-- ============================================================
INSERT IGNORE INTO keywords
    (category_id, parent_id, value, display_value, tier, sort_order, metadata)

-- ── 강남구 (edu 5) ──────────────────────────────────────────
SELECT 1,p.id,'대치동',  '대치',  2,1,JSON_OBJECT('lat',37.4942,'lng',127.0617,'edu_index',5) FROM keywords p WHERE p.category_id=1 AND p.value='강남구' UNION ALL
SELECT 1,p.id,'역삼동',  '역삼',  2,2,JSON_OBJECT('lat',37.5007,'lng',127.0367,'edu_index',5) FROM keywords p WHERE p.category_id=1 AND p.value='강남구' UNION ALL

-- ── 서초구 (edu 5) ──────────────────────────────────────────
SELECT 1,p.id,'반포동',  '반포',  2,1,JSON_OBJECT('lat',37.5044,'lng',126.9998,'edu_index',5) FROM keywords p WHERE p.category_id=1 AND p.value='서초구' UNION ALL
SELECT 1,p.id,'방배동',  '방배',  2,2,JSON_OBJECT('lat',37.4813,'lng',126.9997,'edu_index',4) FROM keywords p WHERE p.category_id=1 AND p.value='서초구' UNION ALL

-- ── 송파구 (edu 5) ──────────────────────────────────────────
SELECT 1,p.id,'잠실동',  '잠실',  2,1,JSON_OBJECT('lat',37.5133,'lng',127.1000,'edu_index',5) FROM keywords p WHERE p.category_id=1 AND p.value='송파구' UNION ALL
SELECT 1,p.id,'문정동',  '문정',  2,2,JSON_OBJECT('lat',37.4924,'lng',127.1239,'edu_index',4) FROM keywords p WHERE p.category_id=1 AND p.value='송파구' UNION ALL

-- ── 양천구 (edu 5) ──────────────────────────────────────────
SELECT 1,p.id,'목동',    '목동',  2,1,JSON_OBJECT('lat',37.5267,'lng',126.8746,'edu_index',5) FROM keywords p WHERE p.category_id=1 AND p.value='양천구' UNION ALL
SELECT 1,p.id,'신정동',  '신정',  2,2,JSON_OBJECT('lat',37.5195,'lng',126.8671,'edu_index',4) FROM keywords p WHERE p.category_id=1 AND p.value='양천구' UNION ALL

-- ── 강동구 (edu 4) ──────────────────────────────────────────
SELECT 1,p.id,'천호동',  '천호',  2,1,JSON_OBJECT('lat',37.5381,'lng',127.1240,'edu_index',4) FROM keywords p WHERE p.category_id=1 AND p.value='강동구' UNION ALL
SELECT 1,p.id,'길동',    '길동',  2,2,JSON_OBJECT('lat',37.5409,'lng',127.1427,'edu_index',4) FROM keywords p WHERE p.category_id=1 AND p.value='강동구' UNION ALL

-- ── 노원구 (edu 4) ──────────────────────────────────────────
SELECT 1,p.id,'중계동',  '중계',  2,1,JSON_OBJECT('lat',37.6444,'lng',127.0748,'edu_index',5) FROM keywords p WHERE p.category_id=1 AND p.value='노원구' UNION ALL
SELECT 1,p.id,'상계동',  '상계',  2,2,JSON_OBJECT('lat',37.6553,'lng',127.0634,'edu_index',4) FROM keywords p WHERE p.category_id=1 AND p.value='노원구' UNION ALL

-- ── 성동구 (edu 4) ──────────────────────────────────────────
SELECT 1,p.id,'왕십리동','왕십리',2,1,JSON_OBJECT('lat',37.5617,'lng',127.0366,'edu_index',4) FROM keywords p WHERE p.category_id=1 AND p.value='성동구' UNION ALL
SELECT 1,p.id,'행당동',  '행당',  2,2,JSON_OBJECT('lat',37.5581,'lng',127.0358,'edu_index',4) FROM keywords p WHERE p.category_id=1 AND p.value='성동구' UNION ALL

-- ── 광진구 (edu 4) ──────────────────────────────────────────
SELECT 1,p.id,'화양동',  '화양',  2,1,JSON_OBJECT('lat',37.5432,'lng',127.0726,'edu_index',4) FROM keywords p WHERE p.category_id=1 AND p.value='광진구' UNION ALL
SELECT 1,p.id,'구의동',  '구의',  2,2,JSON_OBJECT('lat',37.5444,'lng',127.0943,'edu_index',4) FROM keywords p WHERE p.category_id=1 AND p.value='광진구' UNION ALL

-- ── 동작구 (edu 4) ──────────────────────────────────────────
SELECT 1,p.id,'사당동',  '사당',  2,1,JSON_OBJECT('lat',37.4762,'lng',126.9814,'edu_index',4) FROM keywords p WHERE p.category_id=1 AND p.value='동작구' UNION ALL
SELECT 1,p.id,'노량진동','노량진',2,2,JSON_OBJECT('lat',37.5131,'lng',126.9425,'edu_index',4) FROM keywords p WHERE p.category_id=1 AND p.value='동작구' UNION ALL

-- ── 용산구 (edu 4) ──────────────────────────────────────────
SELECT 1,p.id,'한남동',  '한남',  2,1,JSON_OBJECT('lat',37.5347,'lng',127.0005,'edu_index',4) FROM keywords p WHERE p.category_id=1 AND p.value='용산구' UNION ALL
SELECT 1,p.id,'이태원동','이태원',2,2,JSON_OBJECT('lat',37.5344,'lng',126.9942,'edu_index',3) FROM keywords p WHERE p.category_id=1 AND p.value='용산구' UNION ALL

-- ── 성남시 (edu 5) ──────────────────────────────────────────
SELECT 1,p.id,'분당동',  '분당',  2,1,JSON_OBJECT('lat',37.3795,'lng',127.1162,'edu_index',5) FROM keywords p WHERE p.category_id=1 AND p.value='성남시' UNION ALL
SELECT 1,p.id,'정자동',  '정자',  2,2,JSON_OBJECT('lat',37.3600,'lng',127.1055,'edu_index',5) FROM keywords p WHERE p.category_id=1 AND p.value='성남시' UNION ALL

-- ── 과천시 (edu 5) ──────────────────────────────────────────
SELECT 1,p.id,'별양동',  '별양',  2,1,JSON_OBJECT('lat',37.4333,'lng',126.9877,'edu_index',5) FROM keywords p WHERE p.category_id=1 AND p.value='과천시' UNION ALL
SELECT 1,p.id,'중앙동',  '중앙',  2,2,JSON_OBJECT('lat',37.4279,'lng',126.9877,'edu_index',5) FROM keywords p WHERE p.category_id=1 AND p.value='과천시' UNION ALL

-- ── 수원시 (edu 4) ──────────────────────────────────────────
SELECT 1,p.id,'영통동',  '영통',  2,1,JSON_OBJECT('lat',37.2636,'lng',127.0457,'edu_index',4) FROM keywords p WHERE p.category_id=1 AND p.value='수원시' UNION ALL
SELECT 1,p.id,'인계동',  '인계',  2,2,JSON_OBJECT('lat',37.2629,'lng',127.0311,'edu_index',4) FROM keywords p WHERE p.category_id=1 AND p.value='수원시' UNION ALL

-- ── 용인시 (edu 4) ──────────────────────────────────────────
SELECT 1,p.id,'풍덕천동','풍덕천',2,1,JSON_OBJECT('lat',37.3219,'lng',127.0979,'edu_index',5) FROM keywords p WHERE p.category_id=1 AND p.value='용인시' UNION ALL
SELECT 1,p.id,'동천동',  '동천',  2,2,JSON_OBJECT('lat',37.3468,'lng',127.1073,'edu_index',5) FROM keywords p WHERE p.category_id=1 AND p.value='용인시' UNION ALL

-- ── 안양시 (edu 4) ──────────────────────────────────────────
SELECT 1,p.id,'평촌동',  '평촌',  2,1,JSON_OBJECT('lat',37.3901,'lng',126.9527,'edu_index',5) FROM keywords p WHERE p.category_id=1 AND p.value='안양시' UNION ALL
SELECT 1,p.id,'호계동',  '호계',  2,2,JSON_OBJECT('lat',37.3760,'lng',126.9469,'edu_index',4) FROM keywords p WHERE p.category_id=1 AND p.value='안양시' UNION ALL

-- ── 고양시 (edu 4) ──────────────────────────────────────────
SELECT 1,p.id,'마두동',  '마두',  2,1,JSON_OBJECT('lat',37.6562,'lng',126.7734,'edu_index',4) FROM keywords p WHERE p.category_id=1 AND p.value='고양시' UNION ALL
SELECT 1,p.id,'정발산동','정발산',2,2,JSON_OBJECT('lat',37.6621,'lng',126.7763,'edu_index',4) FROM keywords p WHERE p.category_id=1 AND p.value='고양시' UNION ALL

-- ── 광명시 (edu 4) ──────────────────────────────────────────
SELECT 1,p.id,'철산동',  '철산',  2,1,JSON_OBJECT('lat',37.4784,'lng',126.8644,'edu_index',4) FROM keywords p WHERE p.category_id=1 AND p.value='광명시' UNION ALL
SELECT 1,p.id,'하안동',  '하안',  2,2,JSON_OBJECT('lat',37.4652,'lng',126.8643,'edu_index',4) FROM keywords p WHERE p.category_id=1 AND p.value='광명시' UNION ALL

-- ── 의왕시 (edu 4) ──────────────────────────────────────────
SELECT 1,p.id,'내손동',  '내손',  2,1,JSON_OBJECT('lat',37.3638,'lng',126.9683,'edu_index',4) FROM keywords p WHERE p.category_id=1 AND p.value='의왕시' UNION ALL
SELECT 1,p.id,'오전동',  '오전',  2,2,JSON_OBJECT('lat',37.3469,'lng',126.9605,'edu_index',4) FROM keywords p WHERE p.category_id=1 AND p.value='의왕시' UNION ALL

-- ── 군포시 (edu 4) ──────────────────────────────────────────
SELECT 1,p.id,'산본동',  '산본',  2,1,JSON_OBJECT('lat',37.3604,'lng',126.9312,'edu_index',4) FROM keywords p WHERE p.category_id=1 AND p.value='군포시' UNION ALL
SELECT 1,p.id,'금정동',  '금정',  2,2,JSON_OBJECT('lat',37.3615,'lng',126.9352,'edu_index',4) FROM keywords p WHERE p.category_id=1 AND p.value='군포시' UNION ALL

-- ── 하남시 (edu 4) ──────────────────────────────────────────
SELECT 1,p.id,'미사동',  '미사',  2,1,JSON_OBJECT('lat',37.5596,'lng',127.2148,'edu_index',4) FROM keywords p WHERE p.category_id=1 AND p.value='하남시' UNION ALL
SELECT 1,p.id,'위례동',  '위례',  2,2,JSON_OBJECT('lat',37.4776,'lng',127.1469,'edu_index',4) FROM keywords p WHERE p.category_id=1 AND p.value='하남시' UNION ALL

-- ── 구리시 (edu 4) ──────────────────────────────────────────
SELECT 1,p.id,'인창동',  '인창',  2,1,JSON_OBJECT('lat',37.5943,'lng',127.1296,'edu_index',4) FROM keywords p WHERE p.category_id=1 AND p.value='구리시' UNION ALL
SELECT 1,p.id,'교문동',  '교문',  2,2,JSON_OBJECT('lat',37.5883,'lng',127.1365,'edu_index',4) FROM keywords p WHERE p.category_id=1 AND p.value='구리시' UNION ALL

-- ── 남양주시 (edu 4) ────────────────────────────────────────
SELECT 1,p.id,'다산동',  '다산',  2,1,JSON_OBJECT('lat',37.6012,'lng',127.1990,'edu_index',4) FROM keywords p WHERE p.category_id=1 AND p.value='남양주시' UNION ALL
SELECT 1,p.id,'별내동',  '별내',  2,2,JSON_OBJECT('lat',37.6437,'lng',127.1551,'edu_index',4) FROM keywords p WHERE p.category_id=1 AND p.value='남양주시';

SET FOREIGN_KEY_CHECKS = 1;
