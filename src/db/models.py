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
                
                conn.commit()
                logging.info("Tables initialized successfully")

class AddressRepository:
    def __init__(self, db):
        self.db = db

    def save_address(self, address_data):
        """
        Сохраняет адрес и его теги в базу данных
        
        address_data: dict с полями:
            - address: str (адрес)
            - name: str (имя)
            - tag: str (тег из OKLink)
        """
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                try:
                    # Логирование перед сохранением
                    logging.debug(f"Сохранение адреса: {address_data['address']}")
                    
                    # Сохраняем адрес
                    cur.execute("""
                        INSERT INTO addresses (address, name)
                        VALUES (%s, %s)
                        ON CONFLICT (address) 
                        DO UPDATE SET 
                            name = EXCLUDED.name
                        RETURNING id
                    """, (
                        address_data['address'],
                        address_data['name']
                    ))
                    address_id = cur.fetchone()[0]
                    logging.debug(f"Saved to addresses table, got id: {address_id}")
                    
                    # Сохраняем тег
                    if 'tag' in address_data:
                        cur.execute("""
                            INSERT INTO tags (tag_oklink)
                            VALUES (%s)
                            ON CONFLICT (tag_oklink) DO NOTHING
                            RETURNING id
                        """, (address_data['tag'],))
                        result = cur.fetchone()
                        
                        if result:
                            tag_id = result[0]
                        else:
                            # Если тег уже существует, получаем его id
                            cur.execute("""
                                SELECT id FROM tags WHERE tag_oklink = %s
                            """, (address_data['tag'],))
                            tag_id = cur.fetchone()[0]
                        
                        # Связываем адрес с тегом
                        cur.execute("""
                            INSERT INTO address_tags (address_id, tag_id)
                            VALUES (%s, %s)
                            ON CONFLICT (address_id, tag_id) DO NOTHING
                        """, (address_id, tag_id))
                    
                    conn.commit()
                    logging.debug(f"Successfully saved address {address_data['address']} with tag {address_data.get('tag')}")
                    
                except Exception as e:
                    conn.rollback()
                    logging.error(f"Error saving address to database: {str(e)}")
                    raise 