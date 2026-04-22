from __future__ import annotations

import os
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker


@lru_cache(maxsize=8)
def get_engine(database_url: str):
    url = make_url(database_url)
    if url.get_backend_name() == 'sqlite':
        database = url.database
        if database and database != ':memory:':
            os.makedirs(os.path.dirname(os.path.abspath(database)), exist_ok=True)
    return create_engine(database_url, pool_pre_ping=url.get_backend_name() != 'sqlite')


@lru_cache(maxsize=8)
def get_session_factory(database_url: str):
    return sessionmaker(bind=get_engine(database_url), expire_on_commit=False)
