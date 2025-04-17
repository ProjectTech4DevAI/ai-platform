import os
import json
import logging

from sqlmodel import Session
from sqlalchemy.sql import text

from app.core.db import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def update_policies(session: Session) -> None:
    """
    Update Casbin policies from the local JSON file.
    This deletes all existing 'p' policies and inserts new ones.
    """
    file_path = os.path.join(os.path.dirname(__file__), "rbac_policies.json")
    try:
        with open(file_path) as f:
            data = json.load(f)
    except FileNotFoundError:
        raise ValueError(f"Policy file not found: {file_path}")

    conn = session.connection()

    try:
        # Clear existing policies
        logger.info("Deleting existing Casbin policies")
        conn.execute(text("DELETE FROM casbin_rule WHERE ptype = 'p'"))

        # Insert new policies
        for policy in data.get("permissions", []):
            role = policy.get("role")
            resource = policy.get("resource")
            actions = policy.get("actions")

            if not role or not resource or not isinstance(actions, list):
                raise ValueError(f"Invalid policy entry: {policy}")

            for action in actions:
                conn.execute(
                    text(
                        """
                        INSERT INTO casbin_rule (ptype, v0, v1, v2)
                        VALUES (:ptype, :v0, :v1, :v2)
                    """
                    ),
                    {"ptype": "p", "v0": role, "v1": resource, "v2": action},
                )

        session.commit()
        logger.info("Casbin policies updated successfully.")

    except Exception as e:
        logger.error(f"Error updating Casbin policies: {e}")
        session.rollback()
        raise


def main() -> None:
    logger.info("Starting Casbin policy update")
    with Session(engine) as session:
        update_policies(session)
    logger.info("Casbin policy update finished")


if __name__ == "__main__":
    main()
