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
    base_currency CHAR(3) NOT NULL DEFAULT 'EUR',
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
    quote_currency CHAR(3) NOT NULL DEFAULT 'EUR',
    created_on TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_on TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_symbol_code
        CHECK (symbol_code ~ '^[A-Z0-9.-]{1,12}$')
);

CREATE INDEX ix_market_instruments_symbol_code ON market_instruments(symbol_code);
CREATE INDEX ix_market_instruments_sector_name ON market_instruments(sector_name);

-- 4. TRADE LEDGER

CREATE TABLE trade_ledger (
    trade_uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_uuid UUID NOT NULL REFERENCES investment_accounts(account_uuid) ON DELETE CASCADE,
    instrument_uuid UUID NOT NULL REFERENCES market_instruments(instrument_uuid) ON DELETE RESTRICT,
    trade_kind VARCHAR(12) NOT NULL,
    units NUMERIC(18,4) NOT NULL CHECK (units > 0),
    execution_price NUMERIC(18,6) NOT NULL CHECK (execution_price >= 0),
    gross_amount NUMERIC(18,2) NOT NULL CHECK (gross_amount >= 0),
    brokerage_fee NUMERIC(18,2) NOT NULL DEFAULT 0,
    tax_amount NUMERIC(18,2) NOT NULL DEFAULT 0,
    executed_on DATE NOT NULL,
    remarks TEXT,
    inserted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_trade_kind
        CHECK (trade_kind IN ('BUY', 'SELL', 'DIVIDEND')),
    CONSTRAINT chk_executed_on
        CHECK (executed_on <= CURRENT_DATE)
);

CREATE INDEX ix_trade_ledger_account_uuid ON trade_ledger(account_uuid);
CREATE INDEX ix_trade_ledger_instrument_uuid ON trade_ledger(instrument_uuid);
CREATE INDEX ix_trade_ledger_trade_kind ON trade_ledger(trade_kind);
CREATE INDEX ix_trade_ledger_executed_on ON trade_ledger(executed_on DESC);

-- 5. CURRENT POSITIONS

CREATE TABLE current_positions (
    position_uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_uuid UUID NOT NULL REFERENCES investment_accounts(account_uuid) ON DELETE CASCADE,
    instrument_uuid UUID NOT NULL REFERENCES market_instruments(instrument_uuid) ON DELETE RESTRICT,
    units_held NUMERIC(18,4) NOT NULL CHECK (units_held > 0),
    weighted_avg_cost NUMERIC(18,6) NOT NULL CHECK (weighted_avg_cost > 0),
    latest_market_price NUMERIC(18,6),
    price_refreshed_at TIMESTAMP,
    created_on TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_on TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_account_instrument_position UNIQUE (account_uuid, instrument_uuid)
);

CREATE INDEX ix_current_positions_account_uuid ON current_positions(account_uuid);
CREATE INDEX ix_current_positions_instrument_uuid ON current_positions(instrument_uuid);

-- 6. DAILY MARKET PRICES

CREATE TABLE daily_market_prices (
    price_uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instrument_uuid UUID NOT NULL REFERENCES market_instruments(instrument_uuid) ON DELETE RESTRICT,
    trading_day DATE NOT NULL,
    opening_price NUMERIC(18,6),
    highest_price NUMERIC(18,6),
    lowest_price NUMERIC(18,6),
    closing_price NUMERIC(18,6) NOT NULL CHECK (closing_price >= 0),
    adjusted_close_price NUMERIC(18,6),
    traded_volume BIGINT CHECK (traded_volume IS NULL OR traded_volume >= 0),
    created_on TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_on TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_instrument_trading_day UNIQUE (instrument_uuid, trading_day),
    CONSTRAINT chk_trading_day_not_future CHECK (trading_day <= CURRENT_DATE),
    CONSTRAINT chk_daily_prices
        CHECK (
            (opening_price IS NULL OR opening_price >= 0) AND
            (highest_price IS NULL OR highest_price >= 0) AND
            (lowest_price IS NULL OR lowest_price >= 0) AND
            (highest_price IS NULL OR lowest_price IS NULL OR highest_price >= lowest_price)
        )
);

CREATE INDEX ix_daily_market_prices_instrument_day
    ON daily_market_prices(instrument_uuid, trading_day DESC);

-- 7. ACCOUNT ANALYTICS

CREATE TABLE account_analytics (
    analytics_uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_uuid UUID NOT NULL UNIQUE REFERENCES investment_accounts(account_uuid) ON DELETE CASCADE,
    capital_contributed NUMERIC(18,2) DEFAULT 0,
    portfolio_market_value NUMERIC(18,2) DEFAULT 0,
    unrealized_pnl NUMERIC(18,2) DEFAULT 0,
    unrealized_pnl_percentage NUMERIC(10,4) DEFAULT 0,
    volatility_1m NUMERIC(10,6),
    volatility_3m NUMERIC(10,6),
    sharpe_ratio_1m NUMERIC(10,6),
    sharpe_ratio_3m NUMERIC(10,6),
    strongest_symbol VARCHAR(12),
    weakest_symbol VARCHAR(12),
    recalculated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_account_analytics_recalculated_at ON account_analytics(recalculated_at DESC);

-- 8. EXTERNAL API CREDENTIALS

CREATE TABLE external_api_credentials (
    credential_uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_uuid UUID NOT NULL REFERENCES app_users(user_uuid) ON DELETE CASCADE,
    provider_name VARCHAR(50) NOT NULL,
    encrypted_secret TEXT NOT NULL,
    active_flag BOOLEAN NOT NULL DEFAULT TRUE,
    created_on TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_accessed_at TIMESTAMP,
    CONSTRAINT uq_owner_provider UNIQUE (owner_uuid, provider_name)
);

CREATE INDEX ix_external_api_credentials_owner_uuid
    ON external_api_credentials(owner_uuid);

-- 9. CHANGE EVENTS / AUDIT

CREATE TABLE change_events (
    event_uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_uuid UUID REFERENCES app_users(user_uuid) ON DELETE SET NULL,
    entity_name VARCHAR(100) NOT NULL,
    entity_uuid UUID,
    event_type VARCHAR(20) NOT NULL,
    state_before JSONB,
    state_after JSONB,
    client_ip INET,
    happened_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_event_type
        CHECK (event_type IN ('INSERT', 'UPDATE', 'DELETE'))
);

CREATE INDEX ix_change_events_actor_uuid ON change_events(actor_uuid);
CREATE INDEX ix_change_events_entity_name ON change_events(entity_name);
CREATE INDEX ix_change_events_happened_at ON change_events(happened_at DESC);