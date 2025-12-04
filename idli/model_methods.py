from idli import sql_factory
from idli.errors import InvalidValueTypeError
from idli.helpers import AutoInt, AutoUUID
from idli.internal import PY_COLUMN_TYPES


def __init__(self, **kwargs):
    self.__is_stored__ = False
    for key in kwargs:
        if key in self.__table__.columns:
            setattr(self, key, kwargs[key])


def save(self):
    columns = []
    values = []
    for key in self.__table__.columns:
        column = self.__table__.columns[key]
        if hasattr(self, key):
            val = getattr(self, key)
            if val not in [AutoInt, AutoUUID, None]:
                val_type = type(val)
                if val_type not in PY_COLUMN_TYPES:
                    raise InvalidValueTypeError(f"Invalid value '{val}' for column '{key}'")
                if column.column_type != PY_COLUMN_TYPES[val_type]:
                    raise InvalidValueTypeError(f"Invalid value '{val}' for column '{key}'")
                columns.append(key)
                values.append(column.py_to_db(val))
                
    self._connection.exec_sql(sql_factory.insert_row(
        table_name = self.__table__.name,
        columns = columns,
        values = values,
    ))
                
