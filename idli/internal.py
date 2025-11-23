from uuid import UUID

from idli.coltypes import *
from idli.errors import InvalidColumnTypeError


PY_TYPES = {
    UUID: 'UUID',
    bool: 'BOOLEAN',
    float: 'NUMERIC',
    int: 'INTEGER',
    str: 'VARCHAR',
}

DB_TYPES = {
    'integer': 'INTEGER',
    'character varying': 'VARCHAR',
    'boolean': 'BOOLEAN',
    'numeric': 'NUMERIC',
    'uuid': 'UUID'
}


class Column:

    def __init__(
        self,
        name: str,
        column_class = None,
        column_dbtype = None,
        nullable: bool = False,
        default = None,
        primary_key: bool = False,
    ):
        self.name = name

        if column_dbtype:
            if column_dbtype not in DB_TYPES.values():
                raise InvalidColumnTypeError(f"Unsupported type '{column_dbtype}' for column '{name}'")
            self.column_type = DB_TYPES[column_dbtype]
        else:
            if column_class not in PY_TYPES:
                raise InvalidColumnTypeError(f"Unsupported class '{column_class.__name__}' for column '{name}'")
            self.column_type = PY_TYPES[column_class]
        
        self.nullable = nullable
        self.default = default
        self.primary_key = primary_key
        

    def __repr__(self):
        return f'Column<{self.column_type}> {self.name}'


class Table:

    def __init__(self, name: str):
        self.name = name
        self.columns = {}

    def __repr__(self):
        return f"Table {self.name}: {', '.join(self.columns.keys())}"

    def add_column(self, column: Column):
        self.columns[column.name] = column
    



