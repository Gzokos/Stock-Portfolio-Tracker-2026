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

-- TIMESTAMP TRIGGER FUNCTION

CREATE OR REPLACE FUNCTION touch_modified_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.modified_on = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION touch_updated_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- tables using modified_on
CREATE TRIGGER trg_app_users_modified
BEFORE UPDATE ON app_users
FOR EACH ROW
EXECUTE FUNCTION touch_modified_timestamp();

CREATE TRIGGER trg_investment_accounts_modified
BEFORE UPDATE ON investment_accounts
FOR EACH ROW
EXECUTE FUNCTION touch_modified_timestamp();

CREATE TRIGGER trg_market_instruments_modified
BEFORE UPDATE ON market_instruments
FOR EACH ROW
EXECUTE FUNCTION touch_modified_timestamp();

CREATE TRIGGER trg_current_positions_modified
BEFORE UPDATE ON current_positions
FOR EACH ROW
EXECUTE FUNCTION touch_modified_timestamp();

CREATE TRIGGER trg_daily_market_prices_modified
BEFORE UPDATE ON daily_market_prices
FOR EACH ROW
EXECUTE FUNCTION touch_modified_timestamp();

-- tables using updated_at
CREATE TRIGGER trg_trade_ledger_updated
BEFORE UPDATE ON trade_ledger
FOR EACH ROW
EXECUTE FUNCTION touch_updated_timestamp();

-- VIEWS

CREATE VIEW vw_account_overview AS
SELECT
    ia.account_uuid,
    ia.owner_uuid,
    ia.account_title,
    ia.base_currency,
    COALESCE(pos.total_positions, 0) AS total_positions,
    COALESCE(trx.total_trades, 0) AS total_trades,
    COALESCE(pos.total_cost_basis, 0) AS total_cost_basis,
    COALESCE(pos.total_market_value, 0) AS total_market_value,
    COALESCE(pos.total_unrealized_pnl, 0) AS total_unrealized_pnl,
    CASE
        WHEN COALESCE(pos.total_cost_basis, 0) > 0
        THEN ROUND((pos.total_unrealized_pnl / pos.total_cost_basis) * 100, 2)
        ELSE 0
    END AS total_unrealized_pnl_pct
FROM investment_accounts ia
LEFT JOIN (
    SELECT
        cp.account_uuid,
        COUNT(*) AS total_positions,
        SUM(cp.units_held * cp.weighted_avg_cost) AS total_cost_basis,
        SUM(cp.units_held * COALESCE(cp.latest_market_price, 0)) AS total_market_value,
        SUM((cp.units_held * COALESCE(cp.latest_market_price, 0)) - (cp.units_held * cp.weighted_avg_cost)) AS total_unrealized_pnl
    FROM current_positions cp
    GROUP BY cp.account_uuid
) pos ON ia.account_uuid = pos.account_uuid
LEFT JOIN (
    SELECT
        tl.account_uuid,
        COUNT(*) AS total_trades
    FROM trade_ledger tl
    GROUP BY tl.account_uuid
) trx ON ia.account_uuid = trx.account_uuid;

CREATE VIEW vw_position_details AS
SELECT
    cp.position_uuid,
    cp.account_uuid,
    mi.symbol_code,
    mi.instrument_name,
    mi.exchange_name,
    mi.sector_name,
    cp.units_held,
    cp.weighted_avg_cost,
    cp.latest_market_price,
    ROUND(cp.units_held * cp.weighted_avg_cost, 2) AS cost_basis,
    ROUND(cp.units_held * COALESCE(cp.latest_market_price, 0), 2) AS market_value,
    ROUND((cp.units_held * COALESCE(cp.latest_market_price, 0)) - (cp.units_held * cp.weighted_avg_cost), 2) AS unrealized_pnl,
    cp.price_refreshed_at
FROM current_positions cp
JOIN market_instruments mi
  ON cp.instrument_uuid = mi.instrument_uuid;

CREATE VIEW vw_trade_history AS
SELECT
    tl.trade_uuid,
    tl.account_uuid,
    mi.symbol_code,
    mi.instrument_name,
    tl.trade_kind,
    tl.units,
    tl.execution_price,
    tl.gross_amount,
    tl.brokerage_fee,
    tl.tax_amount,
    (tl.gross_amount + tl.brokerage_fee + tl.tax_amount) AS settlement_amount,
    tl.executed_on,
    tl.remarks
FROM trade_ledger tl
JOIN market_instruments mi
  ON tl.instrument_uuid = mi.instrument_uuid;

-- FUNCTIONS

CREATE OR REPLACE FUNCTION fn_daily_returns(
    p_instrument_uuid UUID,
    p_limit_days INTEGER DEFAULT 30
)
RETURNS TABLE (
    trading_day DATE,
    closing_price NUMERIC,
    previous_close NUMERIC,
    return_ratio NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    WITH ordered_prices AS (
        SELECT
            dmp.trading_day,
            dmp.closing_price,
            LAG(dmp.closing_price) OVER (ORDER BY dmp.trading_day) AS prev_close
        FROM daily_market_prices dmp
        WHERE dmp.instrument_uuid = p_instrument_uuid
    ),
    limited_prices AS (
        SELECT *
        FROM ordered_prices
        ORDER BY trading_day DESC
        LIMIT p_limit_days
    )
    SELECT
        lp.trading_day,
        lp.closing_price,
        lp.prev_close,
        CASE
            WHEN lp.prev_close IS NOT NULL AND lp.prev_close > 0
            THEN ROUND(((lp.closing_price - lp.prev_close) / lp.prev_close), 6)
            ELSE NULL
        END
    FROM limited_prices lp
    WHERE lp.prev_close IS NOT NULL
    ORDER BY lp.trading_day ASC;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION fn_account_profitability(p_account_uuid UUID)
RETURNS TABLE (
    invested_amount NUMERIC,
    market_value NUMERIC,
    unrealized_profit NUMERIC,
    unrealized_profit_pct NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COALESCE(SUM(cp.units_held * cp.weighted_avg_cost), 0) AS invested_amount,
        COALESCE(SUM(cp.units_held * COALESCE(cp.latest_market_price, 0)), 0) AS market_value,
        COALESCE(SUM((cp.units_held * COALESCE(cp.latest_market_price, 0)) - (cp.units_held * cp.weighted_avg_cost)), 0) AS unrealized_profit,
        CASE
            WHEN COALESCE(SUM(cp.units_held * cp.weighted_avg_cost), 0) > 0
            THEN ROUND(
                (
                    SUM((cp.units_held * COALESCE(cp.latest_market_price, 0)) - (cp.units_held * cp.weighted_avg_cost))
                    / SUM(cp.units_held * cp.weighted_avg_cost)
                ) * 100,
                2
            )
            ELSE 0
        END AS unrealized_profit_pct
    FROM current_positions cp
    WHERE cp.account_uuid = p_account_uuid;
END;
$$ LANGUAGE plpgsql;

-- SAMPLE DATA

INSERT INTO market_instruments
(symbol_code, instrument_name, exchange_name, sector_name, industry_name, country_name, quote_currency)
VALUES
('AAPL', 'Apple Inc.', 'NASDAQ', 'Technology', 'Consumer Electronics', 'USA', 'USD'),
('MSFT', 'Microsoft Corporation', 'NASDAQ', 'Technology', 'Software', 'USA', 'USD'),
('NVDA', 'NVIDIA Corporation', 'NASDAQ', 'Technology', 'Semiconductors', 'USA', 'USD'),
('AMZN', 'Amazon.com Inc.', 'NASDAQ', 'Consumer Discretionary', 'E-Commerce', 'USA', 'USD'),
('TSLA', 'Tesla Inc.', 'NASDAQ', 'Consumer Discretionary', 'Automotive', 'USA', 'USD')
ON CONFLICT (symbol_code) DO NOTHING;