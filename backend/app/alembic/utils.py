import json
import os
from sqlalchemy.sql import text
from sqlalchemy.engine import Connection


def update_casbin_policies(conn: Connection, file_path: str):
    """
    Update Casbin policies from a JSON file and insert into the casbin_rule table.
    Warning : This will delete all the existing policies
    """
    try:
        with open(file_path) as f:
            data = json.load(f)
    except FileNotFoundError:
        raise ValueError(f"Policy file not found: {file_path}")

    # Clear all existing policies
    conn.execute(text("DELETE FROM casbin_rule WHERE ptype = 'p'"))

    for policy in data.get("permissions", []):
        try:
            role = policy["role"]
            resource = policy["resource"]
            actions = policy["actions"]
        except KeyError as e:
            raise ValueError(f"Missing required field in policy: {str(e)}")

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
