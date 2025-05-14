from datetime import datetime
import psycopg2
from psycopg2 import pool
from contextlib import contextmanager
import logging
import json

class Database:
    def __init__(self, config):
        self.pool = psycopg2.pool.SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            **config
        )
        
    @contextmanager
    def get_connection(self):
        conn = self.pool.getconn()
        try:
            yield conn
        finally:
            self.pool.putconn(conn)

    def init_tables(self):
        """Инициализация таблиц при первом запуске"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Создаем таблицу тегов
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS tags (
                        id SERIAL PRIMARY KEY,
                        tag_oklink VARCHAR(255) UNIQUE NOT NULL,
                        tag_unified VARCHAR(255),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Создаем таблицу адресов
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS addresses (
                        id SERIAL PRIMARY KEY,
                        address VARCHAR(42) UNIQUE NOT NULL,
                        name VARCHAR(255),
                        chain VARCHAR(50) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Создаем таблицу связи адресов и тегов
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS address_tags (
                        address_id INTEGER REFERENCES addresses(id),
                        tag_id INTEGER REFERENCES tags(id),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (address_id, tag_id)
                    )
                """)
                
                # Создаем таблицу унифицированных адресов
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS unified_addresses (
                        address VARCHAR(50) NOT NULL,
                        type VARCHAR(20) NOT NULL,
                        address_name VARCHAR(50),
                        labels JSON,
                        source VARCHAR(50),
                        created_at TIMESTAMP DEFAULT timezone('utc'::text, now()) NOT NULL,
                        id SERIAL PRIMARY KEY,
                        CONSTRAINT unified_addresses_unique_address UNIQUE (address)
                    )
                """)
                
                conn.commit()
                logging.info("Таблицы инициализированы успешно")

class AddressRepository:
    def __init__(self, db):
        self.db = db

    def save_tag(self, tag_data):
        """
        Сохраняет тег в таблицу tags
        
        tag_data: dict с полями:
            - tag_oklink: str (тег из OKLink)
        """
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute("""
                        INSERT INTO tags (tag_oklink)
                        VALUES (%s)
                        ON CONFLICT (tag_oklink) DO NOTHING
                    """, (tag_data['tag_oklink'],))
                    
                    conn.commit()
                    logging.debug(f"Успешно сохранен тег: {tag_data['tag_oklink']}")
                    
                except Exception as e:
                    conn.rollback()
                    logging.error(f"Ошибка при сохранении тега {tag_data['tag_oklink']}: {str(e)}")
                    raise

    def get_unified_type(self, oklink_tag):
        """Получает унифицированный тип из таблицы tags"""
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT tag_unified 
                    FROM tags 
                    WHERE tag_oklink = %s
                """, (oklink_tag,))
                result = cur.fetchone()
                return result[0] if result and result[0] else None

    def save_address(self, address_data):
        """
        Сохраняет адрес и его теги в базу данных
        
        address_data: dict с полями:
            - address: str (адрес)
            - name: str (имя)
            - tag: str (тег из OKLink)
            - chain: str (блокчейн)
        """
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                try:
                    # Логирование перед сохранением
                    logging.info(f"Начинаем сохранение адреса: {address_data['address']}")
                    logging.info(f"Данные для сохранения: {address_data}")
                    
                    # Сохраняем адрес
                    cur.execute("""
                        INSERT INTO addresses (address, name, chain)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (address) 
                        DO UPDATE SET 
                            name = EXCLUDED.name,
                            chain = EXCLUDED.chain
                        RETURNING id
                    """, (
                        address_data['address'],
                        address_data['name'],
                        address_data.get('chain', 'ethereum')
                    ))
                    address_id = cur.fetchone()[0]
                    logging.info(f"Адрес сохранен в таблицу addresses, id: {address_id}")
                    
                    # Сохраняем тег, если он есть
                    if 'tag' in address_data:
                        logging.info(f"Сохраняем тег: {address_data['tag']}")
                        cur.execute("""
                            INSERT INTO tags (tag_oklink)
                            VALUES (%s)
                            ON CONFLICT (tag_oklink) DO NOTHING
                            RETURNING id
                        """, (address_data['tag'],))
                        result = cur.fetchone()
                        
                        if result:
                            tag_id = result[0]
                            logging.info(f"Создан новый тег с id: {tag_id}")
                        else:
                            # Если тег уже существует, получаем его id
                            cur.execute("""
                                SELECT id FROM tags WHERE tag_oklink = %s
                            """, (address_data['tag'],))
                            tag_id = cur.fetchone()[0]
                            logging.info(f"Найден существующий тег с id: {tag_id}")
                        
                        # Связываем адрес с тегом
                        cur.execute("""
                            INSERT INTO address_tags (address_id, tag_id)
                            VALUES (%s, %s)
                            ON CONFLICT (address_id, tag_id) DO NOTHING
                        """, (address_id, tag_id))
                        logging.info(f"Адрес {address_id} связан с тегом {tag_id}")
                    
                    conn.commit()
                    logging.info(f"Успешно сохранен адрес {address_data['address']} с тегом {address_data.get('tag')}")
                    
                    # Проверяем unified_type и сохраняем в unified_addresses если есть
                    if 'tag' in address_data:
                        logging.info(f"Проверяем unified_type для тега: {address_data['tag']}")
                        unified_type = self.get_unified_type(address_data['tag'])
                        logging.info(f"Получен unified_type: {unified_type}")
                        
                        if unified_type:
                            # Проверяем, не совпадает ли имя с адресом
                            if address_data['name'] == address_data['address']:
                                logging.info(f"⏩ Пропускаем сохранение в unified_addresses - имя совпадает с адресом: {address_data['address']}")
                            else:
                                # Сохраняем в unified_addresses
                                cur.execute("""
                                    INSERT INTO unified_addresses (address, type, address_name, labels, source)
                                    VALUES (%s, %s, %s, %s, %s)
                                    ON CONFLICT (address) 
                                    DO UPDATE SET 
                                        type = EXCLUDED.type,
                                        address_name = EXCLUDED.address_name,
                                        labels = EXCLUDED.labels,
                                        source = EXCLUDED.source
                                """, (
                                    address_data['address'],
                                    unified_type,
                                    address_data['name'],
                                    '{}',  # пустой JSON
                                    'oklink-txs'
                                ))
                                conn.commit()
                                logging.info(f"Успешно сохранен адрес {address_data['address']} в unified_addresses")
                        else:
                            logging.info(f"Пропуск сохранения в unified_addresses - нет tag_unified для тега {address_data['tag']}")
                    
                except Exception as e:
                    conn.rollback()
                    logging.error(f"Ошибка при сохранении адреса {address_data['address']}: {str(e)}")
                    raise 