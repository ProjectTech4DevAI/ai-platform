import os
from casbin import Enforcer
from casbin_sqlalchemy_adapter import Adapter
from app.core.db import engine
from fastapi.concurrency import run_in_threadpool
from fastapi import HTTPException, status

config_path = os.path.join(os.path.dirname(__file__), "rbac_model.conf")

adapter = Adapter(engine)
enforcer = Enforcer(config_path, adapter)
enforcer.enable_auto_save(True)


async def load_policy():
    await run_in_threadpool(enforcer.load_policy)


def casbin_enforce(sub: str, obj: str, act: str, org: str= None, proj: str = None):
    """Enforces Casbin RBAC rules based on org-level and project-level roles."""
    
    if not enforcer.enforce(sub, org, proj, obj, act):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to perform this action.",
        )
