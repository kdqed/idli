import atexit
import inspect
import re
from typing import Optional, Union, get_args, get_type_hints

import psycopg
from psycopg.rows import dict_row
from psycopg.sql import Identifier, Literal, SQL
from psycopg_pool import ConnectionPool

from idli.errors import *
from idli.helpers import *
from idli.internal import Column, Table


class Connection:

    def __init__(self, db_uri: str, sambar_dip: bool=False):
        self._pool = ConnectionPool(db_uri, open=True)
        atexit.register(self._pool.close)
        
        self._sambar_dip = sambar_dip

        self.load_tables()
        self.load_columns()
        

    def exec_sql(self, *args):
        with self._pool.connection() as conn:
            return conn.execute(*args)
            
    
    def exec_sql_to_dict_rows(self, *args):
        with self._pool.connection() as conn:
            cur = conn.cursor(row_factory = dict_row)
            return cur.execute(*args)


    def load_tables(self):
        result = self.exec_sql_to_dict_rows("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE';
        """).fetchall()

        self.__db_tables__ = { row['table_name']: Table(row['table_name']) for row in result }


    def load_columns(self):
        result = self.exec_sql_to_dict_rows("""
            SELECT table_name, column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public';
        """).fetchall()

        for row in result:
            table_name = row['table_name']
            if table_name in self.__db_tables__:
                self.__db_tables__[table_name].add_column(Column.from_db_row(**row))
        


    def _ensure_table(self, cls):
        if cls.__table__.name not in self.__db_tables__:
            if self._sambar_dip:
                self.exec_sql(
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
                
            cls.__table__.add_column(Column.from_py_model(
                table_name = cls.__table__.name,
                name = col_name, 
                column_class = col_class, 
                nullable = nullable,
                default = default, 
            ))


    def _reconcile_columns(self, cls):
        for column in cls.__table__.columns.values():
            db_table = self.__db_tables__[cls.__table__.name]
            db_column = db_table.columns.get(column.name)
            
            if db_column:
                if db_column.column_type != column.column_type:
                    raise ColumnTypeMismatchError(f"Column '{column.name}' is type '{db_column.column_type}' on database")
                
                if db_column.nullable == False and column.nullable == True:
                    if self._sambar_dip:
                        self.exec_sql(column.generate_sql_for_make_nullable())
                    else:
                        raise ColumnNotNullableError(f"Changing column '{column.name}' to nullable is not supported with sambar_dip=False")
                if db_column.nullable == True and column.nullable == False:
                    raise ColumnNullableError(f"Changing column '{column.name}' to not nullable is not supported")

                if db_column.default != column.default:
                    if self._sambar_dip:
                        self.exec_sql(column.generate_sql_for_set_default())
                    else:
                        raise ColumnDefaultMismatchError(f"Defined default value for column '{column.name}' does not match with the database")
            else:
                if self._sambar_dip:
                    self.exec_sql(column.generate_sql_for_addition())
                else:
                    raise ColumnNotFoundError(f"Column '{column.name}' does not exist in table '{cls.__table__.name}'")

                
    def Model(self, cls):
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', cls.__name__)
        s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1)
        cls.__table__ = Table(s2.lower())

        self._ensure_table(cls)
        self._build_column_model(cls)
        self._reconcile_columns(cls)
