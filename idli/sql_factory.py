from typing import List

from psycopg.sql import Composed, Identifier, Literal, SQL

from idli.helpers import *
from idli.internal import Column, Table


DATE_FMT = "%Y-%m-%d %H:%M:%S.%f"

OPERATORS = dict(
    eq = SQL('{} = {}'),
    gt = SQL('{} > {}'),
    gte = SQL('{} >= {}'),
    lt = SQL('{} < {}'),
    lte = SQL('{} <= {}'),
    neq = SQL('{} IS DISTINCT FROM {}'),
)


def _exists_bit_for_join(
    table_name: str,
    col_name: str,
    related_table_name: str,
    related_col_name: str,
    filters: dict | None,
    ):
  
    sql_bits = []
    
    sql_bits.append(SQL('EXISTS ( '))
    sql_bits.append(SQL("SELECT 1 FROM {}").format(Identifier(
        related_table_name
    )))
  
    filter_bits = []
    filter_bits.append(SQL('{}.{} = {}.{}').format(
        Identifier(related_table_name),
        Identifier(related_col_name),
        Identifier(table_name),
        Identifier(col_name),
    ))
           
    for key, val in filters.items():
        if '__' in key:
            col, op = key.split('__')
            if val is None and op == 'eq':
                filter_bits.append(SQL('{} IS NULL').format(Identifier(col)))
            elif val is None and op == 'neq':
                filter_bits.append(SQL('{} IS NOT NULL').format(Identifier(col)))
            else:
                filter_bits.append(OPERATORS[op].format(Identifier(col), Literal(val)))
        else:
            if val is None:
                filter_bits.append(SQL('{} IS NULL').format(Identifier(key)))
            else:
                col, op = key, 'eq'
                filter_bits.append(OPERATORS[op].format(
                    Identifier(related_table_name, col), Literal(val)
                ))
    
    sql_bits.append(SQL('WHERE ') + SQL(' AND ').join(filter_bits))
    sql_bits.append(SQL(' )'))
    
    return Composed(sql_bits)


def _filters_to_sql(filters: dict, table_name: str | None):
    filter_bits = []
           
    for key, val in filters.items():
        if key == '__by_join':
            for ef in val:
                filter_bits.append(_exists_bit_for_join(
                    table_name = table_name,
                    col_name = ef[2],
                    related_table_name = ef[0].__table__.name,
                    related_col_name = ef[1],
                    filters = ef[3],
                ))
        elif '__' in key:
            col, op = key.split('__')
            if val is None and op == 'eq':
                filter_bits.append(SQL('{} IS NULL').format(Identifier(col)))
            elif val is None and op == 'neq':
                filter_bits.append(SQL('{} IS NOT NULL').format(Identifier(col)))
            else:
                filter_bits.append(OPERATORS[op].format(Identifier(col), Literal(val)))
        else:
            if val is None:
                filter_bits.append(SQL('{} IS NULL').format(Identifier(key)))
            else:
                col, op = key, 'eq'
                filter_bits.append(OPERATORS[op].format(
                    Identifier(col), Literal(val)
                ))
    
    return SQL('WHERE ') + SQL(' AND ').join(filter_bits)


def create_btree_index(table_name: str, columns: List[str], index_name: str):
    return SQL(' ').join([
        SQL('CREATE INDEX IF NOT EXISTS {}').format(Identifier(index_name)),
        SQL('ON {} USING BTREE').format(Identifier(table_name)),
        SQL('').join([
            SQL('('),
            SQL(', ').join(
                [Identifier(c.strip('-')) + SQL(' ') + SQL('DESC' if c.startswith('-') else 'ASC') for c in columns]
            ),
            SQL(')'),
        ])
    ])


def create_hnsw_index(table_name: str, column: str, operation: str, index_name: str):
    op_code = {
        'l2d': 'vector_l2_ops',
        'l1d': 'vector_l1_ops',
        'inp': 'vector_ip_ops',
        'cos': 'vector_cosine_ops',
    }[operation]
    return SQL(' ').join([
        SQL('CREATE INDEX IF NOT EXISTS {}').format(Identifier(index_name)),
        SQL('ON {} USING HNSW').format(Identifier(table_name)),
        SQL('').join([
            SQL('('),
            Identifier(column),
            SQL(' '),
            SQL(op_code),
            SQL(')'),
        ])
    ])


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
    if column_type == 'VECTOR' and column.length:
        column_type = f'VECTOR({column.length})'
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


def count_by_filter(table_name: str, filters: dict):
    stmt = [SQL('SELECT COUNT(*) FROM {}').format(
        Identifier(table_name),
    )]

    if (filters is not None) and len(filters):
        stmt.append(_filters_to_sql(filters, table_name = table_name))
    
    return SQL(' ').join(stmt)


def delete_by_filter(table_name: str, filter: dict):
    return SQL(' ').join([
        SQL('DELETE FROM {}').format(Identifier(table_name)),
        _filters_to_sql(filter, table_name = table_name),
    ])


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
        SELECT 
            c.table_name, 
            c.column_name, 
            -- If it's a vector, name it 'vector'; otherwise, keep the standard name
            CASE 
                WHEN c.udt_name = 'vector' THEN 'vector' 
                ELSE c.data_type 
            END AS data_type,
            -- Extract dimensions safely (only if udt_name is vector)
            CASE 
                WHEN c.udt_name = 'vector' THEN NULLIF(a.atttypmod, -1)
                ELSE NULL 
            END AS vector_dimensions,
            c.is_nullable, 
            c.column_default
        FROM information_schema.columns c
        JOIN pg_class t ON c.table_name = t.relname
        JOIN pg_namespace n ON t.relnamespace = n.oid AND c.table_schema = n.nspname
        JOIN pg_attribute a ON t.oid = a.attrelid AND c.column_name = a.attname
        WHERE c.table_schema = 'public'
        ORDER BY c.table_name, c.ordinal_position;
    """)


def list_indexes():
    return SQL('''
        SELECT schemaname, tablename, indexname, indexdef
        FROM pg_indexes
        WHERE schemaname = 'public'
        ORDER BY tablename, indexname;
    ''')


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
        filters: dict | None = None,
        limit: int | None = None,
        skip: int | None = None,
        order_by: List | None = None,
        columns: List | None = None,
    ):
    
    select_bits = [SQL('*')]
    if columns:
        select_bits = [SQL(col_name) for col_name in columns]
    
    filter_sql = None
    ordering_bits = []

    if (filters is not None) and len(filters):
        filter_sql = _filters_to_sql(filters, table_name = table_name)
    
    if order_by is not None:
        for col in order_by:
            if type(col) is VNN:
                select_bits.append(SQL(' ').join([
                    Identifier(col.column),
                    SQL(col.operator),
                    Literal(str(list(col.vector))),
                    SQL('AS'),
                    Identifier(col.column + '__vd__' + col.op_name)
                ]))
                ordering_bits.append(SQL(' ').join([
                    Identifier(col.column),
                    SQL(col.operator),
                    Literal(str(list(col.vector))),
                ]))
            elif col.startswith('-'):
                ordering_bits.append(SQL('{} DESC').format(Identifier(col[1:])))
            else:
                ordering_bits.append(Identifier(col))
    
    stmt = []
    
    from_bit = SQL(' FROM {}').format(Identifier(table_name))
    stmt.append(SQL('SELECT ') + SQL(',').join(select_bits) + from_bit)
    if filter_sql is not None:
        stmt.append(filter_sql)
    if order_by is not None:
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


def update_row(table_name: str, pk_filter: dict, updates: dict):
    return SQL(' ').join([
        SQL('UPDATE {}').format(Identifier(table_name)),
        SQL(' ').join([
            SQL('SET'),
            SQL(', ').join([SQL('{} = {}').format(Identifier(c), Literal(v)) for c, v in updates.items()]),
        ]),
        SQL(' ').join([
            SQL('WHERE'),
            SQL(', ').join([SQL('{} = {}').format(Identifier(c), Literal(v)) for c, v in pk_filter.items()]),
        ]),
    ])
