-- users: хранит скидку и подписку на лимит
CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY,
    plan TEXT DEFAULT NULL,
    discount_percent INT DEFAULT 0,
    max_links INT DEFAULT 5, -- бесплатно
    dest BIGINT DEFAULT -2279934 -- Москва
);

-- products: отслеживаемые товары
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    url_product TEXT NOT NULL,
    nm_id BIGINT NOT NULL,
    name_product TEXT,
    last_basic_price NUMERIC(10,2),
    last_product_price NUMERIC(10,2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    UNIQUE(user_id, nm_id)
);
