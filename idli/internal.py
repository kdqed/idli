from datetime import datetime
from uuid import UUID

from psycopg.sql import Identifier, Literal, SQL

from idli.errors import InvalidColumnTypeError
from idli.helpers import *

COLUMN_TYPES = [
    # (PYTHON CLASS TYPE, key, PG INFO SCHEMA TYPE)
    (bool, 'BOOLEAN', 'boolean'),
    (datetime, 'TIMESTAMP', 'timestamp without time zone'),
    (float, 'NUMERIC', 'numeric'),
    (int, 'INTEGER', 'integer'),
    (str, 'VARCHAR', 'character varying'),
    (UUID, 'UUID', 'uuid'),
]

PY_COLUMN_TYPES = { t[0]: t[1] for t in COLUMN_TYPES }
DB_COLUMN_TYPES = { t[2]: t[1] for t in COLUMN_TYPES }

DATE_FMT = "%Y-%m-%d %H:%M:%S.%f"


class Column:

    def __init__(
        self,
        table_name: str,
        name: str,
        column_type = None,
        nullable: bool = False,
        default = None,
    ):
        self.table_name = table_name
        self.name = name
        self.column_type = column_type
        self.nullable = nullable
        self.default = default


    @staticmethod
    def from_py_model(
        table_name: str,
        name: str,
        column_class,
        nullable: bool = False,
        default = None,
    ):
        
        if column_class not in PY_COLUMN_TYPES:
            raise InvalidColumnTypeError(f"Unsupported class '{column_class.__name__}' for column '{name}'")
        
        return Column(
            table_name = table_name,
            name = name,
            column_type = PY_COLUMN_TYPES[column_class],
            nullable = nullable,
            default = default,
        )


    @staticmethod
    def from_db_row(
        table_name: str,
        column_name: str,
        data_type: str,
        is_nullable: str,
        column_default,
    ):
        if data_type not in DB_COLUMN_TYPES:
            raise InvalidColumnTypeError(f"Unsupported class '{column_class.__name__}' for column '{name}'")

        column_type = DB_COLUMN_TYPES[data_type]

        if column_default:
            if column_type=='BOOLEAN':
                column_default = True if column_default.lower()=='true' else False
            elif column_type=='INTEGER':
                default_for_auto = f"nextval('{table_name}_{column_name}_seq'::regclass)"
                if column_default == default_for_auto:
                    column_default = AutoInt
                else:
                    try:
                        column_default = int(column_default)
                    except:
                        pass
            elif column_type=='NUMERIC':
                try:
                    column_default = float(column_default)
                except:
                    pass
            elif column_type=="TIMESTAMP":
                try:
                    column_default = column_default.rsplit('::timestamp without time zone', 1)[0].strip("'")
                    if '.' not in column_default:
                        column_default += '.000000'
                    column_default = datetime.strptime(column_default, DATE_FMT)
                except Exception as e:
                    pass      
            elif column_type=="UUID":
                try:
                    column_default = UUID(column_default.rsplit('::uuid', 1)[0].strip("'"))
                except Exception as e:
                    pass            
            elif column_type=='VARCHAR':
                column_default = column_default.rsplit('::character varying', 1)[0].strip("'")

        
        return Column(
            table_name = table_name,
            name = column_name,
            column_type = column_type,
            nullable = is_nullable.lower()=='yes',
            default = column_default,
        )
        

    def __repr__(self):
        return f'Column<{self.column_type}> {self.name}'


    def generate_sql_for_addition(self):
        column_type = self.column_type
        default = self.default
        if default == AutoInt and column_type == 'INTEGER':
            column_type = 'SERIAL'
            default = None
            
        stmt = [
            SQL('ALTER TABLE {}').format(Identifier(self.table_name)),
            SQL('ADD COLUMN IF NOT EXISTS {} {}').format(
                Identifier(self.name),
                SQL(column_type),
            ),
        ]
        
        if self.nullable == False:
            stmt.append(SQL('NOT NULL'))
            
        if default != None:
            if self.column_type == 'TIMESTAMP':
                default_str = self.default.strftime(DATE_FMT)
            else:
                default_str = str(self.default)
            stmt.append(SQL('DEFAULT {}').format(Literal(default_str)))

        return SQL(' ').join(stmt)


    def generate_sql_for_make_nullable(self):
        return SQL('ALTER TABLE {} ALTER COLUMN {} DROP NOT NULL').format(
            Identifier(self.table_name),
            Identifier(self.name),
        )


    def generate_sql_for_set_default(self):
        if self.default != None:
            if self.column_type == 'TIMESTAMP':
                default_str = self.default.strftime(DATE_FMT)
            else:
                default_str = str(self.default)
            
            return SQL('ALTER TABLE {} ALTER COLUMN {} SET DEFAULT {}').format(
                Identifier(self.table_name),
                Identifier(self.name),
                Literal(default_str),
            )
        else:
            return SQL('ALTER TABLE {} ALTER COLUMN {} DROP DEFAULT').format(
                Identifier(self.table_name),
                Identifier(self.name),
            )


class Table:

    def __init__(self, name: str):
        self.name = name
        self.columns = {}

    def __repr__(self):
        return f"Table {self.name}: {', '.join(self.columns.keys())}"

    def add_column(self, column: Column):
        self.columns[column.name] = column
    



