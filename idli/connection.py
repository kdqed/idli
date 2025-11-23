import atexit
import inspect
import re
from typing import Optional, Union, get_args, get_type_hints

import psycopg
from psycopg.rows import dict_row
from psycopg.sql import Identifier, Literal, SQL
from psycopg_pool import ConnectionPool

from idli.errors import TableNotFoundError
from idli.helpers import *
from idli.internal import Column, Table


class Connection:

    def __init__(self, db_uri: str, sambar_dip: bool=False):
        self._pool = ConnectionPool(db_uri, open=True)
        atexit.register(self._pool.close)
        
        self._sambar_dip = sambar_dip

        self.load_tables()
        self.load_columns()
        

    def raw_sql(self, *args):
        with self._pool.connection() as conn:
            return conn.execute(*args)
            
    
    def raw_sql_dict(self, *args):
        with self._pool.connection() as conn:
            cur = conn.cursor(row_factory = dict_row)
            return cur.execute(*args)


    def load_tables(self):
        result = self.raw_sql_dict("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE';
        """).fetchall()

        self.__db_tables__ = { row['table_name']: Table(row['table_name']) for row in result }


    def load_columns(self):
        result = self.raw_sql_dict("""
            SELECT table_name, column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public';
        """).fetchall()

        for row in result:
            print(row)
            # table_name = row[0]
            # if table_name in self.__db_tables__:
            #     table = self.__db_tables__[table_name]
            #     table.add_column(Column(
            #         name = row[1],
            #         column_dbtype = row[2],
            #         nullable = row[3].lower() == 'yes'
            #     ))
        


    def _ensure_table(self, cls):
        if cls.__table__.name not in self.__db_tables__:
            if self._sambar_dip:
                self.raw_sql(
                    SQL('''
                        CREATE TABLE IF NOT EXISTS {} ();
                    ''').format(Identifier(cls.__table__.name)),
                )
            else:
                raise TableNotFoundError(f'Table {cls.__tablename__} for model {cls.__name__} does not exist on database')


    def _build_column_model(self, cls):
        for key, val in get_type_hints(cls).items():
            col_name = key
            if getattr(val, '__origin__', None) in [Optional, Union]:
                col_class = list(filter(lambda x: type(x) is not None, get_args(val)))[0]
                nullable = True
            else:
                col_class = val
                nullable = False

            default = getattr(cls, key, None)
            primary_key = key=='id'
                
            cls.__table__.add_column(Column(
                name = col_name, 
                column_class = col_class, 
                nullable = nullable,
                default = default, 
                primary_key = primary_key,
            ))


    def _reconcile_columns(self, cls):
        for column in cls.__table__.columns.values():
            column_type = column.column_type
            default = column.default
            if default == AutoInt and column_type == 'INTEGER':
                column_type = 'SERIAL'
                default = None
                
            stmt = [
                SQL('ALTER TABLE {}').format(Identifier(cls.__table__.name)),
                SQL('ADD COLUMN IF NOT EXISTS {} {}').format(
                    Identifier(column.name),
                    SQL(column_type),
                ),
            ]
            
            if column.nullable == False:
                stmt.append(SQL('NOT NULL'))
                
            if default != None:
                stmt.append(SQL('DEFAULT {}').format(Literal(column.default)))

            if column.primary_key:
                stmt.append(SQL('PRIMARY KEY'))

            self.raw_sql(SQL(' ').join(stmt))
                
            

    def Model(self, cls):
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', cls.__name__)
        s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1)
        cls.__table__ = Table(s2.lower())

        self._ensure_table(cls)
        self._build_column_model(cls)
        self._reconcile_columns(cls)
