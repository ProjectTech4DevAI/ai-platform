-- UPGRADE: Create organizations table
CREATE TABLE organizations (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NULL
);

-- Add foreign keys to related tables (if they exist)
ALTER TABLE projects ADD COLUMN organization_id INT REFERENCES organizations(id) ON DELETE CASCADE;
ALTER TABLE credentials ADD COLUMN organization_id INT REFERENCES organizations(id) ON DELETE CASCADE;
