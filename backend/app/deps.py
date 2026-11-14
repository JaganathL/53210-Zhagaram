import logging
from functools import lru_cache

from .bootstrap import bootstrap
from .config import get_settings
from .storage import JsonStore, MongoStore, Store

log = logging.getLogger(__name__)


@lru_cache
def get_store() -> Store:
    settings = get_settings()
    if settings.use_mongo:
        if not settings.mongo_uri:
            raise RuntimeError("STORAGE=mongo requires MONGO_URI")
        store: Store = MongoStore.connect(settings.mongo_uri, settings.mongo_db)
        log.info("Using MongoDB database '%s'", settings.mongo_db)
    else:
        store = JsonStore(settings.data_dir)
        log.warning("MONGO_URI not set: using local JSON store in %s", settings.data_dir)
    bootstrap(store, settings)
    return store
