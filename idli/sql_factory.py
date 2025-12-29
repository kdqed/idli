from typing import List

from psycopg.sql import Identifier, Literal, SQL

from idli.helpers import *
from idli.internal import Column, Table


DATE_FMT = "%Y-%m-%d %H:%M:%S.%f"


def create_primary_key(table_name: str, columns: List[str]):
    return SQL(' ').join([
        SQL('ALTER TABLE {}').format(Identifier(table_name)),
        SQL('ADD CONSTRAINT {}').format(Identifier(table_name + '_pkey')),
        SQL('PRIMARY KEY'),
        SQL('').join([
            SQL('('),
            SQL(', ').join([Identifier(c) for c in columns]),
            SQL(')')
        ])
    ])


def create_column(column: Column):
    column_type = column.column_type
    default = column.default
    if default == AutoInt and column_type == 'INTEGER':
        column_type = 'SERIAL'
        default = None
    elif default == AutoUUID and column_type == 'UUID':
        default = 'uuidv7()'
        
    stmt = [
        SQL('ALTER TABLE {}').format(Identifier(column.table_name)),
        SQL('ADD COLUMN IF NOT EXISTS {} {}').format(
            Identifier(column.name),
            SQL(column_type),
        ),
    ]
    
    if column.nullable == False:
        stmt.append(SQL('NOT NULL'))
        
    if default != None:
        if column.column_type == 'TIMESTAMP':
            stmt.append(SQL('DEFAULT {}').format(Literal(default.strftime(DATE_FMT))))
        elif default=='uuidv7()':
            stmt.append(SQL('DEFAULT uuidv7()'))
        else:
            stmt.append(SQL('DEFAULT {}').format(Literal(str(default))))

    return SQL(' ').join(stmt)


def create_table(table_name: str):
    return SQL('''
        CREATE TABLE IF NOT EXISTS {} ();
    ''').format(Identifier(table_name))


def drop_constraint(table_name: str, constraint_name: str):
    return SQL('''
        ALTER TABLE {} DROP CONSTRAINT {};
    ''').format(Identifier(table_name), Identifier(constraint_name))


def get_primary_key_columns(constraint_name: str):
    return SQL('''
        SELECT column_name 
        FROM information_schema.key_column_usage 
        WHERE constraint_schema = 'public' AND constraint_name = {}
        ORDER BY ordinal_position;
    ''').format(Literal(constraint_name))


def get_primary_key_constraint_name(table_name: str):
    return SQL('''
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE constraint_type = 'PRIMARY KEY' AND table_name = {};
    ''').format(Literal(table_name))


def insert_row(table_name: str, columns: List[str], values: List[str]):
    return SQL(' ').join([
        SQL('INSERT INTO {}').format(Identifier(table_name)),
        SQL('').join([
            SQL('('),
            SQL(', ').join([Identifier(c) for c in columns]),
            SQL(')'),
        ]),
        SQL('VALUES'),
        SQL('').join([
            SQL('('),
            SQL(', ').join([Literal(v) for v in values]),
            SQL(')'),
        ]),
    ])


def list_columns():
    return SQL("""
        SELECT table_name, column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = 'public';
    """)


def list_tables():
    return SQL("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE';
    """)
    

def make_column_nullable(column: Column):
    return SQL('ALTER TABLE {} ALTER COLUMN {} DROP NOT NULL').format(
        Identifier(column.table_name),
        Identifier(column.name),
    )


def query_rows(
        table_name: str,
        limit: int | None = None,
        skip: int | None = None,
        order_by: List | None = None,
    ):
    
    stmt = [SQL('SELECT * FROM {}').format(
        Identifier(table_name),
    )]
    
    if order_by is not None:
        ordering_bits = []
        for col_name in order_by:
            if col_name.startswith('-'):
                ordering_bits.append(SQL('{} DESC').format(Identifier(col_name[1:])))
            else:
                ordering_bits.append(Identifier(col_name))
        stmt.append(SQL('ORDER BY ') + SQL(',').join(ordering_bits))

    if limit is not None:
        stmt.append(SQL('LIMIT {}').format(Literal(limit)))
    
    if skip is not None:
        stmt.append(SQL('OFFSET {}').format(Literal(skip)))
        
    return SQL(' ').join(stmt)


def set_default_column_value(column: Column):
    if column.default != None:
        if column.default == AutoUUID:
            return SQL('ALTER TABLE {} ALTER COLUMN {} SET DEFAULT uuidv7()').format(
                Identifier(column.table_name),
                Identifier(column.name),
            )
            
        if column.column_type == 'TIMESTAMP':
            default_str = column.default.strftime(DATE_FMT)
        else:
            default_str = str(column.default)
        
        return SQL('ALTER TABLE {} ALTER COLUMN {} SET DEFAULT {}').format(
            Identifier(column.table_name),
            Identifier(column.name),
            Literal(default_str),
        )
    else:
        return SQL('ALTER TABLE {} ALTER COLUMN {} DROP DEFAULT').format(
            Identifier(column.table_name),
            Identifier(column.name),
        )

