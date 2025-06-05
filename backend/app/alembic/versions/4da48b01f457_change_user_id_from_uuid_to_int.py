"""Change user_id from uuid to int

Revision ID: 4da48b01f457
Revises: 904ed70e7dab
Create Date: 2025-06-05 13:59:46.816459

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = '4da48b01f457'
down_revision = '904ed70e7dab'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # Drop foreign key constraints
    conn.execute(sa.text('ALTER TABLE document DROP CONSTRAINT document_owner_id_fkey;'))
    conn.execute(sa.text('ALTER TABLE collection DROP CONSTRAINT collection_owner_id_fkey;'))
    conn.execute(sa.text('ALTER TABLE projectuser DROP CONSTRAINT projectuser_user_id_fkey;'))
    conn.execute(sa.text('ALTER TABLE apikey DROP CONSTRAINT apikey_user_id_fkey;'))

    # Drop primary key constraint on "user" table
    conn.execute(sa.text('ALTER TABLE "user" DROP CONSTRAINT user_pkey;'))

    # Create mapping table from UUID to INT
    conn.execute(sa.text('''
        CREATE TABLE uuid_to_int_map (
            user_id_uuid UUID PRIMARY KEY,
            user_id_int INT GENERATED ALWAYS AS IDENTITY
        );
    '''))

    # Populate mapping table
    conn.execute(sa.text('INSERT INTO uuid_to_int_map (user_id_uuid) SELECT id FROM "user";'))

    # Add new_id to user table and populate it
    conn.execute(sa.text('ALTER TABLE "user" ADD COLUMN new_id INT;'))
    conn.execute(sa.text('''
        UPDATE "user" SET new_id = uuid_map.user_id_int
        FROM uuid_to_int_map uuid_map
        WHERE "user".id = uuid_map.user_id_uuid;
    '''))

    # document
    conn.execute(sa.text('ALTER TABLE document ADD COLUMN new_owner_id INT;'))
    conn.execute(sa.text('''
        UPDATE document SET new_owner_id = uuid_map.user_id_int
        FROM uuid_to_int_map uuid_map
        WHERE document.owner_id = uuid_map.user_id_uuid;
    '''))

    # collection
    conn.execute(sa.text('ALTER TABLE collection ADD COLUMN new_owner_id INT;'))
    conn.execute(sa.text('''
        UPDATE collection SET new_owner_id = uuid_map.user_id_int
        FROM uuid_to_int_map uuid_map
        WHERE collection.owner_id = uuid_map.user_id_uuid;
    '''))

    # projectuser
    conn.execute(sa.text('ALTER TABLE projectuser ADD COLUMN new_user_id INT;'))
    conn.execute(sa.text('''
        UPDATE projectuser SET new_user_id = uuid_map.user_id_int
        FROM uuid_to_int_map uuid_map
        WHERE projectuser.user_id = uuid_map.user_id_uuid;
    '''))

    # apikey
    conn.execute(sa.text('ALTER TABLE apikey ADD COLUMN new_user_id INT;'))
    conn.execute(sa.text('''
        UPDATE apikey SET new_user_id = uuid_map.user_id_int
        FROM uuid_to_int_map uuid_map
        WHERE apikey.user_id = uuid_map.user_id_uuid;
    '''))

    # Drop old columns and rename new ones
    conn.execute(sa.text('ALTER TABLE document DROP COLUMN owner_id;'))
    conn.execute(sa.text('ALTER TABLE document RENAME COLUMN new_owner_id TO owner_id;'))

    conn.execute(sa.text('ALTER TABLE collection DROP COLUMN owner_id;'))
    conn.execute(sa.text('ALTER TABLE collection RENAME COLUMN new_owner_id TO owner_id;'))

    conn.execute(sa.text('ALTER TABLE projectuser DROP COLUMN user_id;'))
    conn.execute(sa.text('ALTER TABLE projectuser RENAME COLUMN new_user_id TO user_id;'))

    conn.execute(sa.text('ALTER TABLE apikey DROP COLUMN user_id;'))
    conn.execute(sa.text('ALTER TABLE apikey RENAME COLUMN new_user_id TO user_id;'))

    conn.execute(sa.text('ALTER TABLE "user" DROP COLUMN id;'))
    conn.execute(sa.text('ALTER TABLE "user" RENAME COLUMN new_id TO id;'))

    # Re-add primary key
    conn.execute(sa.text('ALTER TABLE "user" ADD PRIMARY KEY (id);'))

    # Drop mapping table
    conn.execute(sa.text('DROP TABLE uuid_to_int_map;'))


def downgrade():
    pass
