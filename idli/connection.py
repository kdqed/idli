import atexit
import inspect
import re
from typing import Optional, Union, get_args, get_type_hints

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from idli.errors import *
from idli.helpers import *
from idli.internal import Column, Table
from idli import sql_factory


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
        result = self.exec_sql_to_dict_rows(sql_factory.list_tables()).fetchall()
        self.__db_tables__ = { row['table_name']: Table(row['table_name']) for row in result }


    def load_columns(self):
        result = self.exec_sql_to_dict_rows(sql_factory.list_columns()).fetchall()
        for row in result:
            table_name = row['table_name']
            if table_name in self.__db_tables__:
                self.__db_tables__[table_name].add_column(Column.from_db_row(**row))
        

    def _ensure_table(self, cls):
        if cls.__table__.name not in self.__db_tables__:
            if self._sambar_dip:
                table_name = cls.__table__.name
                self.exec_sql(sql_factory.create_table(table_name))
                self.__db_tables__[table_name] = Table(table_name)
            else:
                raise TableNotFoundError(f'Table {cls.__tablename__} for model {cls.__name__} does not exist on database')


    def _build_column_model(self, cls):
        for key, val in get_type_hints(cls).items():
            if key.startswith('__'):
                continue
                
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
                        self.exec_sql(sql_factory.make_column_nullable(column))
                    else:
                        raise ColumnNotNullableError(f"Changing column '{column.name}' to nullable is not supported with sambar_dip=False")
                if db_column.nullable == True and column.nullable == False:
                    raise ColumnNullableError(f"Changing column '{column.name}' to not nullable is not supported")

                if db_column.default != column.default:
                    if self._sambar_dip:
                        self.exec_sql(sql_factory.set_default_column_value(column))
                    else:
                        raise ColumnDefaultMismatchError(f"Defined default value for column '{column.name}' does not match with the database")
            else:
                if self._sambar_dip:
                    self.exec_sql(sql_factory.create_column(column))
                else:
                    raise ColumnNotFoundError(f"Column '{column.name}' does not exist in table '{cls.__table__.name}'")


    def _handle_directives(self, cls):
        directives = getattr(cls, '__idli__', [])

        for d in directives:
            if type(d) is PrimaryKey:
                cls.__primary_key__ = d.columns


    def _reconcile_primary_key(self, cls):
        defined_pk_columns = getattr(cls, '__primary_key__', ['id'])
        
        result = self.exec_sql_to_dict_rows(
            sql_factory.get_primary_key_columns(cls.__table__.name)
        ).fetchall()
        existing_pk_columns = [c['column_name'] for c in result]

        reconciliation_required = False
        if len(defined_pk_columns) != len(existing_pk_columns):
            reconciliation_required = True
        else:
            for i in range(len(defined_pk_columns)):
                if defined_pk_columns[i] != existing_pk_columns[i]:
                    reconciliation_required = True
                    break
                    
        if len(existing_pk_columns) == 0 and reconciliation_required:        
            self.exec_sql(sql_factory.create_primary_key(
                table_name = cls.__table__.name,
                columns = defined_pk_columns,
            ))
        elif reconciliation_required:
            constraint_name = self.exec_sql_to_dict_rows(
                sql_factory.get_primary_key_constraint_name(cls.__table__.name),
            ).fetchall()[0]['constraint_name']
            
            self.exec_sql(sql_factory.drop_constraint(
                table_name = cls.__table__.name,
                constraint_name = constraint_name,
            ))

            self.exec_sql(sql_factory.create_primary_key(
                table_name = cls.__table__.name,
                columns = defined_pk_columns,
            ))

    
    def Model(self, cls):
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', cls.__name__)
        s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1)
        cls.__table__ = Table(s2.lower())

        self._ensure_table(cls)
        self._build_column_model(cls)
        self._reconcile_columns(cls)
        self._handle_directives(cls)
        self._reconcile_primary_key(cls)
