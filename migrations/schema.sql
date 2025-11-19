-- users: хранит скидку и подписку на лимит
CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY,
    plan TEXT DEFAULT 'plan_free',
    plan_name TEXT DEFAULT 'Бесплатный',
    discount_percent INT DEFAULT 0,
    max_links INT DEFAULT 5,
    dest BIGINT DEFAULT -1257786,    -- Москва по умолчанию
    pvz_address TEXT DEFAULT NULL,
    sort_mode TEXT DEFAULT 'savings',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- products: отслеживаемые товары
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    url_product TEXT NOT NULL,
    nm_id BIGINT NOT NULL,
    name_product TEXT DEFAULT 'Загрузка...',
    custom_name TEXT DEFAULT NULL,              -- пользовательское название
    last_basic_price INT,
    last_product_price INT,
    selected_size TEXT DEFAULT NULL,
    -- Настройки уведомлений
    notify_mode TEXT DEFAULT NULL,  -- 'percent', 'threshold', NULL (все уведомления)
    notify_value INT DEFAULT NULL,  -- Процент или порог
    last_qty INT DEFAULT 0,
    out_of_stock BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    UNIQUE(user_id, nm_id)
);

-- price_history: история изменений цен для графиков
CREATE TABLE IF NOT EXISTS price_history (
    id SERIAL PRIMARY KEY,
    product_id INT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    basic_price INT NOT NULL,
    product_price INT NOT NULL,
    qty INT DEFAULT 0,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Индексы для оптимизации
CREATE INDEX IF NOT EXISTS idx_products_user_id ON products(user_id);
CREATE INDEX IF NOT EXISTS idx_products_nm_id ON products(nm_id);
CREATE INDEX IF NOT EXISTS idx_products_updated_at ON products(updated_at);
CREATE INDEX IF NOT EXISTS idx_price_history_product_id ON price_history(product_id);
CREATE INDEX IF NOT EXISTS idx_price_history_recorded_at ON price_history(recorded_at);