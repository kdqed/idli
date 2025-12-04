from datetime import datetime
from uuid import UUID

from idli.errors import InvalidColumnTypeError
from idli.helpers import *


DATE_FMT = "%Y-%m-%d %H:%M:%S.%f"


class ColumnType:

    def __init__(self, py_type, db_type, py_to_db, db_to_py):
        self.py_type = py_type
        self.db_type = db_type
        self.py_to_db = py_to_db
        self.db_to_py = db_to_py

    
COLUMN_TYPES = {
    'BOOLEAN': ColumnType(
        py_type = bool,
        db_type = 'boolean',
        py_to_db = lambda x: str(x),
        db_to_py = lambda x: x.lower()=='true',
    ),
    'TIMESTAMP': ColumnType(
        py_type = datetime,
        db_type = 'timestamp without time zone',
        py_to_db = lambda x: x.strftime(DATE_FMT),
        db_to_py = lambda x: datetime.strptime(x, DATE_FMT),
    ),
    'NUMERIC': ColumnType(
        py_type = float,
        db_type = 'numeric',
        py_to_db = lambda x: str(x),
        db_to_py = lambda x: float(x),
    ),
    'INTEGER': ColumnType(
        py_type = int,
        db_type = 'integer',
        py_to_db = lambda x: str(x),
        db_to_py = lambda x: int(x),
    ),
    'VARCHAR': ColumnType(
        py_type = str,
        db_type = 'character varying',
        py_to_db = lambda x: x,
        db_to_py = lambda x: x,
    ),
    'UUID': ColumnType(
        py_type = UUID,
        db_type = 'uuid',
        py_to_db = lambda x: str(x),
        db_to_py = lambda x: UUID(x),
    ),
}

PY_COLUMN_TYPES = { COLUMN_TYPES[key].py_type: key for key in COLUMN_TYPES }
DB_COLUMN_TYPES = { COLUMN_TYPES[key].db_type: key for key in COLUMN_TYPES }



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
                    print(e)
                    pass      
            elif column_type=="UUID":
                if column_default == 'uuidv7()':
                    column_default = AutoUUID
                else:
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


    def py_to_db(self, val):
        return COLUMN_TYPES[self.column_type].py_to_db(val)


class Table:

    def __init__(self, name: str):
        self.name = name
        self.columns = {}

    def __repr__(self):
        return f"Table {self.name}: {', '.join(self.columns.keys())}"

    def add_column(self, column: Column):
        self.columns[column.name] = column
    



