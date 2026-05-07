from __future__ import annotations

from pathlib import Path

from sqlalchemy.engine import make_url


DATA_ROOT_DIRNAME = '.aitrade'
SQLITE_FILENAME = 'trades.sqlite3'
LOG_DIRNAME = 'logs'
BACKTEST_DATA_DIRNAME = 'backtest-data'
FREQTRADE_USER_DATA_DIRNAME = 'freqtrade-user-data'


def resolve_aitrade_home() -> Path:
    return Path.home() / DATA_ROOT_DIRNAME


def resolve_default_data_root_dir() -> str:
    return normalize_filesystem_path(str(resolve_aitrade_home()))


def resolve_data_root_dir(data_root_dir: str | None = None) -> str:
    return normalize_filesystem_path(data_root_dir or resolve_default_data_root_dir())


def resolve_sqlite_path(data_root_dir: str | None = None) -> str:
    root = Path(resolve_data_root_dir(data_root_dir))
    return str((root / SQLITE_FILENAME).resolve())


def resolve_backtest_data_dir(data_root_dir: str | None = None) -> str:
    root = Path(resolve_data_root_dir(data_root_dir))
    return str((root / BACKTEST_DATA_DIRNAME).resolve())


def resolve_freqtrade_user_data_dir(data_root_dir: str | None = None) -> str:
    root = Path(resolve_data_root_dir(data_root_dir))
    return str((root / FREQTRADE_USER_DATA_DIRNAME).resolve())


def resolve_log_dir(data_root_dir: str | None = None) -> str:
    root = Path(resolve_data_root_dir(data_root_dir))
    return str((root / LOG_DIRNAME).resolve())


def resolve_default_backtest_data_dir() -> str:
    return resolve_backtest_data_dir()


def resolve_default_freqtrade_user_data_dir() -> str:
    return resolve_freqtrade_user_data_dir()


def resolve_default_log_dir() -> str:
    return resolve_log_dir()


def resolve_default_sqlite_path() -> str:
    return resolve_sqlite_path()


def build_managed_data_paths(data_root_dir: str | None = None) -> dict[str, str]:
    root = resolve_data_root_dir(data_root_dir)
    return {
        'dataRootDir': root,
        'databaseUrl': build_sqlite_database_url(resolve_sqlite_path(root)),
        'appLogDir': resolve_log_dir(root),
        'backtestDataDir': resolve_backtest_data_dir(root),
        'freqtradeUserDataDir': resolve_freqtrade_user_data_dir(root),
    }


def normalize_filesystem_path(value: str) -> str:
    path = Path(str(value).strip()).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    else:
        path = path.resolve()
    return str(path)


def build_sqlite_database_url(database_path: str) -> str:
    normalized_path = normalize_filesystem_path(database_path)
    return f'sqlite:///{normalized_path}'


def normalize_database_url(value: str) -> str:
    text = str(value).strip()
    if not text:
        return text
    if '://' not in text:
        return build_sqlite_database_url(text)

    url = make_url(text)
    if url.get_backend_name() != 'sqlite':
        return text

    database = url.database
    if not database or database == ':memory:':
        return text
    normalized_database = normalize_filesystem_path(database)
    return url.set(database=normalized_database).render_as_string(hide_password=False)


def extract_sqlite_database_path(value: str) -> str | None:
    text = str(value).strip()
    if not text:
        return None
    if '://' not in text:
        return normalize_filesystem_path(text)
    url = make_url(text)
    if url.get_backend_name() != 'sqlite':
        return None
    database = url.database
    if not database or database == ':memory:':
        return None
    return normalize_filesystem_path(database)


def infer_data_root_dir_from_leaf_paths(log_dir: str, backtest_data_dir: str, freqtrade_user_data_dir: str) -> str | None:
    log_path = Path(normalize_filesystem_path(log_dir))
    backtest_path = Path(normalize_filesystem_path(backtest_data_dir))
    user_data_path = Path(normalize_filesystem_path(freqtrade_user_data_dir))
    if log_path.name != LOG_DIRNAME:
        return None
    if backtest_path.name != BACKTEST_DATA_DIRNAME:
        return None
    if user_data_path.name != FREQTRADE_USER_DATA_DIRNAME:
        return None
    candidates = {log_path.parent.resolve(), backtest_path.parent.resolve(), user_data_path.parent.resolve()}
    if len(candidates) != 1:
        return None
    return str(candidates.pop())


def infer_data_root_dir(database_url: str, log_dir: str, backtest_data_dir: str, freqtrade_user_data_dir: str) -> str | None:
    sqlite_path = extract_sqlite_database_path(database_url)
    if sqlite_path is None:
        return None
    sqlite_file = Path(sqlite_path)
    if sqlite_file.name != SQLITE_FILENAME:
        return None
    leaf_root = infer_data_root_dir_from_leaf_paths(log_dir, backtest_data_dir, freqtrade_user_data_dir)
    if leaf_root is None:
        return None
    if Path(leaf_root).resolve() != sqlite_file.parent.resolve():
        return None
    return leaf_root
