import os
from casbin import Enforcer
from casbin_sqlalchemy_adapter import Adapter
from app.core.db import engine
from fastapi.concurrency import run_in_threadpool

config_path = os.path.join(os.path.dirname(__file__), "rbac_model.conf")

adapter = Adapter(engine)
enforcer = Enforcer(config_path, adapter)
enforcer.enable_auto_save(True)

async def load_policy():
    await run_in_threadpool(enforcer.load_policy)