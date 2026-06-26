-- ============================================================
-- Production Schema Fix: LV_ProcessPolicies_DB
-- Run this once against the production PostgreSQL database.
-- All statements are safe (IF NOT EXISTS / IF EXISTS).
-- ============================================================

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- PP_AllowedEmails
-- ============================================================
CREATE TABLE IF NOT EXISTS "PP_AllowedEmails" (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) NOT NULL UNIQUE,
    assigned_role VARCHAR(50) NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_pp_allowedemails_email ON "PP_AllowedEmails" (email);

-- ============================================================
-- PP_Users
-- ============================================================
CREATE TABLE IF NOT EXISTS "PP_Users" (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    password_hash TEXT,
    email VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) NOT NULL,
    role_group VARCHAR(50) NOT NULL,
    is_phone_verified BOOLEAN DEFAULT FALSE,
    phone VARCHAR(20) NOT NULL,
    refresh_token TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_pp_users_email ON "PP_Users" (email);

-- Add unique constraints if they don't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_pp_user_email_role_group'
    ) THEN
        ALTER TABLE "PP_Users" ADD CONSTRAINT uq_pp_user_email_role_group UNIQUE (email, role_group);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_pp_user_phone_role_group'
    ) THEN
        ALTER TABLE "PP_Users" ADD CONSTRAINT uq_pp_user_phone_role_group UNIQUE (phone, role_group);
    END IF;
END $$;

-- Add missing columns to existing PP_Users table
ALTER TABLE "PP_Users" ADD COLUMN IF NOT EXISTS password_hash TEXT;
ALTER TABLE "PP_Users" ADD COLUMN IF NOT EXISTS full_name VARCHAR(255);
ALTER TABLE "PP_Users" ADD COLUMN IF NOT EXISTS is_phone_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE "PP_Users" ADD COLUMN IF NOT EXISTS phone VARCHAR(20);
ALTER TABLE "PP_Users" ADD COLUMN IF NOT EXISTS refresh_token TEXT;
ALTER TABLE "PP_Users" ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW();

-- ============================================================
-- PP_Policies
-- ============================================================
CREATE TABLE IF NOT EXISTS "PP_Policies" (
    id SERIAL PRIMARY KEY,
    name VARCHAR,
    category VARCHAR,
    description TEXT,
    document_url VARCHAR,
    document_key VARCHAR,
    is_active BOOLEAN DEFAULT TRUE,
    submitted_by_role VARCHAR(20) DEFAULT 'admin',
    is_accepted BOOLEAN DEFAULT TRUE
);

-- Add missing columns to existing PP_Policies table
ALTER TABLE "PP_Policies" ADD COLUMN IF NOT EXISTS document_key VARCHAR;
ALTER TABLE "PP_Policies" ADD COLUMN IF NOT EXISTS submitted_by_role VARCHAR(20) DEFAULT 'admin';
ALTER TABLE "PP_Policies" ADD COLUMN IF NOT EXISTS is_accepted BOOLEAN DEFAULT TRUE;

-- ============================================================
-- PP_PolicyLimitations
-- ============================================================
CREATE TABLE IF NOT EXISTS "PP_PolicyLimitations" (
    id SERIAL PRIMARY KEY,
    policy_id INTEGER NOT NULL REFERENCES "PP_Policies"(id) ON DELETE CASCADE,
    title VARCHAR,
    description TEXT,
    is_enabled BOOLEAN DEFAULT TRUE
);

-- ============================================================
-- PP_PolicyRequests
-- ============================================================
CREATE TABLE IF NOT EXISTS "PP_PolicyRequests" (
    id SERIAL PRIMARY KEY,
    policy_id INTEGER REFERENCES "PP_Policies"(id) ON DELETE SET NULL,
    action VARCHAR(20) DEFAULT 'create',
    name VARCHAR,
    category VARCHAR,
    description TEXT,
    is_active BOOLEAN,
    requested_by VARCHAR NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    admin_note TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    reviewed_at TIMESTAMP
);

-- ============================================================
-- PP_LimitationRequests
-- ============================================================
CREATE TABLE IF NOT EXISTS "PP_LimitationRequests" (
    id SERIAL PRIMARY KEY,
    action VARCHAR(20) NOT NULL,
    policy_id INTEGER REFERENCES "PP_Policies"(id) ON DELETE CASCADE,
    limitation_id INTEGER,
    title VARCHAR,
    description TEXT,
    is_enabled BOOLEAN,
    requested_by VARCHAR NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    admin_note TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    reviewed_at TIMESTAMP
);

-- ============================================================
-- PP_PolicyReviews
-- ============================================================
CREATE TABLE IF NOT EXISTS "PP_PolicyReviews" (
    id SERIAL PRIMARY KEY,
    policy_id INTEGER NOT NULL REFERENCES "PP_Policies"(id) ON DELETE CASCADE,
    reviewed_by VARCHAR NOT NULL,
    review TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'open',
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- PP_Locations
-- ============================================================
CREATE TABLE IF NOT EXISTS "PP_Locations" (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    state VARCHAR NOT NULL,
    city VARCHAR NOT NULL,
    locality VARCHAR,
    pincode VARCHAR,
    latitude VARCHAR,
    longitude VARCHAR,
    search_vector TSVECTOR
);

-- Add missing columns to existing PP_Locations table
ALTER TABLE "PP_Locations" ADD COLUMN IF NOT EXISTS locality VARCHAR;
ALTER TABLE "PP_Locations" ADD COLUMN IF NOT EXISTS pincode VARCHAR;
ALTER TABLE "PP_Locations" ADD COLUMN IF NOT EXISTS latitude VARCHAR;
ALTER TABLE "PP_Locations" ADD COLUMN IF NOT EXISTS longitude VARCHAR;
ALTER TABLE "PP_Locations" ADD COLUMN IF NOT EXISTS search_vector TSVECTOR;

-- ============================================================
-- PP_States
-- ============================================================
CREATE TABLE IF NOT EXISTS "PP_States" (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL
);

-- ============================================================
-- PP_Properties
-- ============================================================
CREATE TABLE IF NOT EXISTS "PP_Properties" (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR NOT NULL,
    property_type VARCHAR NOT NULL,
    listing_type VARCHAR,
    location_id UUID NOT NULL REFERENCES "PP_Locations"(id),
    owner_id UUID,
    verification_status VARCHAR,
    status VARCHAR,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);

-- Add missing columns to existing PP_Properties table
ALTER TABLE "PP_Properties" ADD COLUMN IF NOT EXISTS listing_type VARCHAR;
ALTER TABLE "PP_Properties" ADD COLUMN IF NOT EXISTS owner_id UUID;
ALTER TABLE "PP_Properties" ADD COLUMN IF NOT EXISTS verification_status VARCHAR;
ALTER TABLE "PP_Properties" ADD COLUMN IF NOT EXISTS status VARCHAR;
ALTER TABLE "PP_Properties" ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP;

-- ============================================================
-- PP_PropertyAttributes
-- ============================================================
CREATE TABLE IF NOT EXISTS "PP_PropertyAttributes" (
    property_id UUID PRIMARY KEY REFERENCES "PP_Properties"(id) ON DELETE CASCADE,
    bedrooms INTEGER,
    bathrooms INTEGER,
    balconies INTEGER,
    area_sqft FLOAT,
    carpet_area_sqft FLOAT,
    furnishing_status VARCHAR,
    floor_number INTEGER,
    total_floors INTEGER,
    parking_spaces INTEGER,
    age_years INTEGER
);

-- Add missing columns to existing PP_PropertyAttributes
ALTER TABLE "PP_PropertyAttributes" ADD COLUMN IF NOT EXISTS balconies INTEGER;
ALTER TABLE "PP_PropertyAttributes" ADD COLUMN IF NOT EXISTS carpet_area_sqft FLOAT;
ALTER TABLE "PP_PropertyAttributes" ADD COLUMN IF NOT EXISTS furnishing_status VARCHAR;
ALTER TABLE "PP_PropertyAttributes" ADD COLUMN IF NOT EXISTS floor_number INTEGER;
ALTER TABLE "PP_PropertyAttributes" ADD COLUMN IF NOT EXISTS total_floors INTEGER;
ALTER TABLE "PP_PropertyAttributes" ADD COLUMN IF NOT EXISTS parking_spaces INTEGER;
ALTER TABLE "PP_PropertyAttributes" ADD COLUMN IF NOT EXISTS age_years INTEGER;

-- ============================================================
-- PP_PropertyPricing
-- ============================================================
CREATE TABLE IF NOT EXISTS "PP_PropertyPricing" (
    property_id UUID PRIMARY KEY REFERENCES "PP_Properties"(id) ON DELETE CASCADE,
    asking_price FLOAT NOT NULL,
    price_per_sqft FLOAT,
    maintenance_monthly FLOAT,
    security_deposit FLOAT,
    currency VARCHAR,
    price_negotiable VARCHAR,
    last_updated TIMESTAMP
);

-- Add missing columns to existing PP_PropertyPricing
ALTER TABLE "PP_PropertyPricing" ADD COLUMN IF NOT EXISTS price_per_sqft FLOAT;
ALTER TABLE "PP_PropertyPricing" ADD COLUMN IF NOT EXISTS maintenance_monthly FLOAT;
ALTER TABLE "PP_PropertyPricing" ADD COLUMN IF NOT EXISTS security_deposit FLOAT;
ALTER TABLE "PP_PropertyPricing" ADD COLUMN IF NOT EXISTS currency VARCHAR;
ALTER TABLE "PP_PropertyPricing" ADD COLUMN IF NOT EXISTS price_negotiable VARCHAR;
ALTER TABLE "PP_PropertyPricing" ADD COLUMN IF NOT EXISTS last_updated TIMESTAMP;

-- ============================================================
-- PP_PropertyMedia
-- ============================================================
CREATE TABLE IF NOT EXISTS "PP_PropertyMedia" (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    property_id UUID NOT NULL REFERENCES "PP_Properties"(id) ON DELETE CASCADE,
    media_type VARCHAR NOT NULL,
    cdn_url TEXT NOT NULL,
    is_primary BOOLEAN,
    display_order INTEGER,
    uploaded_at TIMESTAMP
);

-- Add missing columns to existing PP_PropertyMedia
ALTER TABLE "PP_PropertyMedia" ADD COLUMN IF NOT EXISTS is_primary BOOLEAN;
ALTER TABLE "PP_PropertyMedia" ADD COLUMN IF NOT EXISTS display_order INTEGER;
ALTER TABLE "PP_PropertyMedia" ADD COLUMN IF NOT EXISTS uploaded_at TIMESTAMP;

-- ============================================================
-- PP_PropertyDocuments
-- ============================================================
CREATE TABLE IF NOT EXISTS "PP_PropertyDocuments" (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    property_id UUID NOT NULL REFERENCES "PP_Properties"(id) ON DELETE CASCADE,
    document_type VARCHAR NOT NULL,
    document_url TEXT NOT NULL,
    document_name VARCHAR,
    uploaded_at TIMESTAMP
);

-- Add missing columns to existing PP_PropertyDocuments
ALTER TABLE "PP_PropertyDocuments" ADD COLUMN IF NOT EXISTS document_name VARCHAR;
ALTER TABLE "PP_PropertyDocuments" ADD COLUMN IF NOT EXISTS uploaded_at TIMESTAMP;

-- ============================================================
-- PP_PropertyClobContent
-- ============================================================
CREATE TABLE IF NOT EXISTS "PP_PropertyClobContent" (
    property_id UUID REFERENCES "PP_Properties"(id) ON DELETE CASCADE,
    content_type VARCHAR NOT NULL,
    content TEXT,
    PRIMARY KEY (property_id, content_type)
);

-- ============================================================
-- PP_VerificationLogs
-- ============================================================
CREATE TABLE IF NOT EXISTS "PP_VerificationLogs" (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    property_id UUID NOT NULL REFERENCES "PP_Properties"(id) ON DELETE CASCADE,
    verified_by UUID NOT NULL,
    verification_status VARCHAR NOT NULL,
    verification_notes TEXT,
    verified_at TIMESTAMP
);

-- Add missing columns to existing PP_VerificationLogs
ALTER TABLE "PP_VerificationLogs" ADD COLUMN IF NOT EXISTS verification_notes TEXT;
ALTER TABLE "PP_VerificationLogs" ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP;

-- ============================================================
-- Done
-- ============================================================
SELECT 'Schema sync complete.' AS result;
