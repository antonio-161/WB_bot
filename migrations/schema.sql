-- users: хранит скидку и подписку на лимит
CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY,
    plan TEXT DEFAULT 'plan_free',
    plan_name TEXT DEFAULT 'Бесплатный',
    discount_percent INT DEFAULT 0,
    max_links INT DEFAULT 5,
    dest BIGINT DEFAULT -1257786,    -- Москва по умолчанию
    pvz_address TEXT DEFAULT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- products: отслеживаемые товары
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    url_product TEXT NOT NULL,
    nm_id BIGINT NOT NULL,
    name_product TEXT DEFAULT 'Загрузка...',
    last_basic_price NUMERIC(10,2),
    last_product_price NUMERIC(10,2),
    selected_size TEXT DEFAULT NULL,        -- выбранный размер для отслеживания
    last_qty INT DEFAULT 0,                 -- последний известный остаток
    out_of_stock BOOLEAN DEFAULT FALSE,     -- товар закончился
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    UNIQUE(user_id, nm_id)
);

-- Индексы для оптимизации
CREATE INDEX IF NOT EXISTS idx_products_user_id ON products(user_id);
CREATE INDEX IF NOT EXISTS idx_products_nm_id ON products(nm_id);
CREATE INDEX IF NOT EXISTS idx_products_updated_at ON products(updated_at);