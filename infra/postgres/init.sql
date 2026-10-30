-- Create separate databases for HAPI FHIR and Keycloak
-- Called by postgres entrypoint via POSTGRES_MULTIPLE_DATABASES env trick

\connect postgres;

SELECT 'CREATE DATABASE hapi'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'hapi')\gexec

SELECT 'CREATE DATABASE keycloak'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'keycloak')\gexec

-- Grant access to the shared user
GRANT ALL PRIVILEGES ON DATABASE hapi TO current_user;
GRANT ALL PRIVILEGES ON DATABASE keycloak TO current_user;
