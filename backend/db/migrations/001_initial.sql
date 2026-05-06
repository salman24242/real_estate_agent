-- ============================================================================
-- Real Estate Chat Agent — Initial schema
-- ============================================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ----------------------------------------------------------------------------
-- agents
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agents (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        TEXT NOT NULL,
    email       TEXT UNIQUE NOT NULL,
    phone       TEXT,
    agency      TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- listings
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS listings (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title           TEXT NOT NULL,
    description     TEXT,
    listing_type    VARCHAR(10) NOT NULL CHECK (listing_type IN ('rent', 'buy')),
    property_type   VARCHAR(20) CHECK (property_type IN ('apartment','house','studio','villa','penthouse','townhouse')),
    price           INTEGER NOT NULL,
    bedrooms        INTEGER,
    bathrooms       INTEGER,
    area_sqft       INTEGER,
    city            VARCHAR(100) NOT NULL,
    neighbourhood   VARCHAR(100),
    address         TEXT,
    latitude        DECIMAL(9,6),
    longitude       DECIMAL(9,6),
    tags            TEXT[] DEFAULT '{}',
    images          TEXT[] DEFAULT '{}',
    available       BOOLEAN DEFAULT TRUE,
    agent_id        UUID REFERENCES agents(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    search_vector   TSVECTOR GENERATED ALWAYS AS (
                        to_tsvector('english', coalesce(title,'') || ' ' || coalesce(description,''))
                    ) STORED
);

CREATE INDEX IF NOT EXISTS idx_listings_city           ON listings(city);
CREATE INDEX IF NOT EXISTS idx_listings_price          ON listings(price);
CREATE INDEX IF NOT EXISTS idx_listings_bedrooms       ON listings(bedrooms);
CREATE INDEX IF NOT EXISTS idx_listings_listing_type   ON listings(listing_type);
CREATE INDEX IF NOT EXISTS idx_listings_property_type  ON listings(property_type);
CREATE INDEX IF NOT EXISTS idx_listings_tags           ON listings USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_listings_search_vector  ON listings USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS idx_listings_available      ON listings(available) WHERE available = TRUE;
CREATE INDEX IF NOT EXISTS idx_listings_location       ON listings(latitude, longitude);

-- ----------------------------------------------------------------------------
-- users
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           TEXT UNIQUE NOT NULL,
    hashed_password TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- saved_searches
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS saved_searches (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name                TEXT,
    filters             JSONB NOT NULL,
    notify              BOOLEAN DEFAULT TRUE,
    last_notified_ids   UUID[] DEFAULT '{}',
    last_checked_at     TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_saved_searches_user    ON saved_searches(user_id);
CREATE INDEX IF NOT EXISTS idx_saved_searches_filters ON saved_searches USING GIN(filters);
