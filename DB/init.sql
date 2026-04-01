CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. APP USERS

CREATE TABLE app_users (
    user_uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email_address VARCHAR(255) NOT NULL UNIQUE,
    login_name VARCHAR(60) NOT NULL UNIQUE,
    password_digest VARCHAR(255) NOT NULL,
    given_name VARCHAR(100),
    family_name VARCHAR(100),
    active_status BOOLEAN NOT NULL DEFAULT TRUE,
    last_sign_in TIMESTAMP,
    created_on TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_on TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_email_format
        CHECK (email_address ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

CREATE INDEX ix_app_users_email_address ON app_users(email_address);
CREATE INDEX ix_app_users_login_name ON app_users(login_name);

-- 2. INVESTMENT ACCOUNTS / PORTFOLIOS

CREATE TABLE investment_accounts (
    account_uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_uuid UUID NOT NULL REFERENCES app_users(user_uuid) ON DELETE CASCADE,
    account_title VARCHAR(150) NOT NULL,
    base_currency CHAR(3) NOT NULL DEFAULT 'USD',
    account_notes TEXT,
    preferred_account BOOLEAN NOT NULL DEFAULT FALSE,
    created_on TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_on TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_owner_account_title UNIQUE (owner_uuid, account_title)
);

CREATE INDEX ix_investment_accounts_owner_uuid ON investment_accounts(owner_uuid);

-- 3. MARKET INSTRUMENTS

CREATE TABLE market_instruments (
    instrument_uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_code VARCHAR(12) NOT NULL UNIQUE,
    instrument_name VARCHAR(255) NOT NULL,
    exchange_name VARCHAR(80),
    sector_name VARCHAR(100),
    industry_name VARCHAR(100),
    country_name VARCHAR(60),
    quote_currency CHAR(3) NOT NULL DEFAULT 'USD',
    created_on TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_on TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_symbol_code
        CHECK (symbol_code ~ '^[A-Z0-9.-]{1,12}$')
);

CREATE INDEX ix_market_instruments_symbol_code ON market_instruments(symbol_code);
CREATE INDEX ix_market_instruments_sector_name ON market_instruments(sector_name);