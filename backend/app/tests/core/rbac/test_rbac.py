import pytest
from sqlmodel import Session, delete
from app.core.rbac.casbin import enforcer
from app.models.casbin_rule import CasbinRule
from app.core.db import engine

TEST_USERS = {
    "user1": "user:1",  # org1: org_admin, org2: org_reader
    "user2": "user:2",  # org1: org_manager
    "user3": "user:3",  # org2: org_admin
    "user4": "user:4",  # project1: project_admin, project2: project_reader
    "user5": "user:5",  # project3: project_manager
    "user6": "user:6",  # project4: project_admin
    "user7": "user:7",  # no roles
    "mixed": "user:8",  # org1: org_admin, org2: org_reader
    "reader": "user:9",  # project1: project_reader
    "admin": "user:10",  # project1: project_admin
}

TEST_ORGS = {"org1": "org:1", "org2": "org:2"}

TEST_PROJECTS = {
    "project1": "project:1",  # org1
    "project2": "project:2",  # org1
    "project3": "project:3",  # org2
    "project4": "project:4",  # org2
}


@pytest.fixture(scope="class", autouse=True)
def setup_casbin_rules(request):
    # Org roles
    enforcer.add_grouping_policy(TEST_USERS["user1"], "org_admin", TEST_ORGS["org1"])
    enforcer.add_grouping_policy(TEST_USERS["user1"], "org_reader", TEST_ORGS["org2"])
    enforcer.add_grouping_policy(TEST_USERS["user2"], "org_manager", TEST_ORGS["org1"])
    enforcer.add_grouping_policy(TEST_USERS["user3"], "org_admin", TEST_ORGS["org2"])
    enforcer.add_grouping_policy(TEST_USERS["mixed"], "org_admin", TEST_ORGS["org1"])
    enforcer.add_grouping_policy(TEST_USERS["mixed"], "org_reader", TEST_ORGS["org2"])

    # Project roles
    enforcer.add_named_grouping_policy(
        "g2", TEST_USERS["user4"], "project_admin", TEST_PROJECTS["project1"]
    )
    enforcer.add_named_grouping_policy(
        "g2", TEST_USERS["user4"], "project_reader", TEST_PROJECTS["project2"]
    )
    enforcer.add_named_grouping_policy(
        "g2", TEST_USERS["user5"], "project_manager", TEST_PROJECTS["project3"]
    )
    enforcer.add_named_grouping_policy(
        "g2", TEST_USERS["user6"], "project_admin", TEST_PROJECTS["project4"]
    )
    enforcer.add_named_grouping_policy(
        "g2", TEST_USERS["reader"], "project_reader", TEST_PROJECTS["project1"]
    )
    enforcer.add_named_grouping_policy(
        "g2", TEST_USERS["admin"], "project_admin", TEST_PROJECTS["project1"]
    )

    # Save and reload
    enforcer.save_policy()
    enforcer.load_policy()

    def teardown():
        with Session(engine) as session:
            stmt = delete(CasbinRule).where(CasbinRule.ptype.in_(["g", "g2", "g3"]))
            session.exec(stmt)
            session.commit()

    request.addfinalizer(teardown)


class TestRBAC:
    """Test suite for Role-Based Access Control (RBAC) functionality using Casbin.

    This class contains tests to verify proper enforcement of organization and project-level
    permissions, including inheritance between organization and project roles, cross-organization
    access restrictions, and multiple role scenarios.
    """

    def test_org_roles_access(self):
        assert (
            enforcer.enforce(
                TEST_USERS["user1"], TEST_ORGS["org1"], "", "org_data", "read"
            )
            is True
        )
        assert (
            enforcer.enforce(
                TEST_USERS["user1"], TEST_ORGS["org1"], "", "org_data", "write"
            )
            is True
        )
        assert (
            enforcer.enforce(
                TEST_USERS["user1"], TEST_ORGS["org1"], "", "org_data", "delete"
            )
            is True
        )

        assert (
            enforcer.enforce(
                TEST_USERS["user2"], TEST_ORGS["org1"], "", "org_data", "read"
            )
            is True
        )
        assert (
            enforcer.enforce(
                TEST_USERS["user2"], TEST_ORGS["org1"], "", "org_data", "write"
            )
            is True
        )
        assert (
            enforcer.enforce(
                TEST_USERS["user2"], TEST_ORGS["org1"], "", "org_data", "delete"
            )
            is False
        )

    def test_project_roles_access(self):
        assert (
            enforcer.enforce(
                TEST_USERS["user4"],
                TEST_ORGS["org1"],
                TEST_PROJECTS["project2"],
                "project_data",
                "read",
            )
            is True
        )
        assert (
            enforcer.enforce(
                TEST_USERS["user4"],
                TEST_ORGS["org1"],
                TEST_PROJECTS["project2"],
                "project_data",
                "write",
            )
            is False
        )

        assert (
            enforcer.enforce(
                TEST_USERS["user5"],
                TEST_ORGS["org2"],
                TEST_PROJECTS["project3"],
                "project_data",
                "write",
            )
            is True
        )
        assert (
            enforcer.enforce(
                TEST_USERS["user5"],
                TEST_ORGS["org2"],
                TEST_PROJECTS["project3"],
                "project_data",
                "read",
            )
            is True
        )

        assert (
            enforcer.enforce(
                TEST_USERS["user4"],
                TEST_ORGS["org1"],
                TEST_PROJECTS["project1"],
                "project_data",
                "delete",
            )
            is True
        )

    def test_org_roles_inherit_project_roles(self):
        assert (
            enforcer.enforce(
                TEST_USERS["user1"],
                TEST_ORGS["org1"],
                TEST_PROJECTS["project1"],
                "project_data",
                "read",
            )
            is True
        )
        assert (
            enforcer.enforce(
                TEST_USERS["user1"],
                TEST_ORGS["org1"],
                TEST_PROJECTS["project1"],
                "project_data",
                "delete",
            )
            is True
        )

        assert (
            enforcer.enforce(
                TEST_USERS["user2"],
                TEST_ORGS["org1"],
                TEST_PROJECTS["project1"],
                "project_data",
                "write",
            )
            is True
        )

    def test_cross_organization_access(self):
        assert (
            enforcer.enforce(
                TEST_USERS["user3"], TEST_ORGS["org2"], "", "org_data", "read"
            )
            is True
        )
        assert (
            enforcer.enforce(
                TEST_USERS["user3"],
                TEST_ORGS["org2"],
                TEST_PROJECTS["project4"],
                "project_data",
                "read",
            )
            is True
        )

    def test_invalid_access_across_orgs(self):
        assert (
            enforcer.enforce(
                TEST_USERS["user4"],
                TEST_ORGS["org2"],
                TEST_PROJECTS["project3"],
                "project_data",
                "read",
            )
            is False
        )
        assert (
            enforcer.enforce(
                TEST_USERS["user5"],
                TEST_ORGS["org1"],
                TEST_PROJECTS["project1"],
                "project_data",
                "write",
            )
            is False
        )

    def test_user_with_different_roles_across_orgs(self):
        assert (
            enforcer.enforce(
                TEST_USERS["mixed"], TEST_ORGS["org1"], "", "org_data", "delete"
            )
            is True
        )
        assert (
            enforcer.enforce(
                TEST_USERS["mixed"], TEST_ORGS["org2"], "", "org_data", "write"
            )
            is False
        )
        assert (
            enforcer.enforce(
                TEST_USERS["mixed"], TEST_ORGS["org2"], "", "org_data", "read"
            )
            is True
        )

    def test_multiple_users_same_project(self):
        assert (
            enforcer.enforce(
                TEST_USERS["reader"],
                TEST_ORGS["org1"],
                TEST_PROJECTS["project1"],
                "project_data",
                "read",
            )
            is True
        )
        assert (
            enforcer.enforce(
                TEST_USERS["reader"],
                TEST_ORGS["org1"],
                TEST_PROJECTS["project1"],
                "project_data",
                "delete",
            )
            is False
        )
        assert (
            enforcer.enforce(
                TEST_USERS["admin"],
                TEST_ORGS["org1"],
                TEST_PROJECTS["project1"],
                "project_data",
                "delete",
            )
            is True
        )

    def test_project_access_via_org_role_only(self):
        assert (
            enforcer.enforce(
                TEST_USERS["user2"],
                TEST_ORGS["org1"],
                TEST_PROJECTS["project1"],
                "project_data",
                "write",
            )
            is True
        )
