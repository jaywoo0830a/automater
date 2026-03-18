"""
factory/db.py
--------------
SQLAlchemy 2.0 엔진 및 세션 팩토리.

권장 사용 패턴 (공식 문서 기준):

    # 엔진 생성 (모듈 스코프)
    engine = get_engine()

    # 트랜잭션 블록
    with Session(engine) as session, session.begin():
        session.add(obj)
        # begin() 블록 종료 시 자동 commit, 예외 시 자동 rollback

참고: https://docs.sqlalchemy.org/en/20/orm/session_basics.html
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


def build_mysql_url() -> str:
    """DB_* 환경변수로 MySQL+PyMySQL 접속 URL 생성."""
    host     = os.environ.get("DB_HOST",     "127.0.0.1")
    port     = os.environ.get("DB_PORT",     "3306")
    database = os.environ.get("DB_NAME",     "automator")
    user     = os.environ.get("DB_USER",     "automator")
    password = os.environ.get("DB_PASSWORD", "automatorpass")
    return (
        f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
        "?charset=utf8mb4"
    )


def get_engine(url: str | None = None, **kwargs) -> Engine:
    """
    SQLAlchemy Engine 생성.

    Args:
        url:    접속 URL. 없으면 DB_* 환경변수로 MySQL URL 생성.
        kwargs: create_engine() 에 전달할 추가 인자.
    """
    if url is None:
        url = build_mysql_url()
    return create_engine(url, pool_pre_ping=True, **kwargs)


# 애플리케이션에서 사용할 세션 팩토리.
# get_engine() 호출 전에 configure() 로 엔진을 주입한다.
#
# 사용 예:
#   SessionFactory = sessionmaker(get_engine())
#   with SessionFactory() as session, session.begin():
#       session.add(obj)
SessionFactory = sessionmaker
