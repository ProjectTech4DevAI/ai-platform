-- UPGRADE: Create credentials table
CREATE TABLE credentials (
    id SERIAL PRIMARY KEY,
    organization_id INT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    project_id INT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR NOT NULL UNIQUE,
    secrets JSON NOT NULL,
    email VARCHAR(255) NOT NULL,
    token UUID UNIQUE DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NULL
);

-- Create indexes for organization_id and project_id
CREATE INDEX ix_credentials_organization_id ON credentials(organization_id);
CREATE INDEX ix_credentials_project_id ON credentials(project_id);
