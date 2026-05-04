from typing import Annotated, Sequence

class AutoInt:
    pass


class AutoUUID:
    pass


class BTreeIndex:

    def __init__(self, *args):
        self.columns = list(args)


    @property
    def name_hash(self):
        return '_'.join(map(
            lambda x: 'd' + x[1:] if x.startswith('-') else 'a' + x,
            self.columns
        )) + '_btree'


class HNSWIndex:

    def __init__(self, column: str, operation: str):
        self.column = column
        self.operation = operation


    @property
    def name_hash(self):
        return f'{self.column}_{self.operation}_hnsw'


class PrimaryKey:

    def  __init__(self, *args):
        self.columns = list(args)


class _BaseVector(list):
    """Base class for all vector types in the ORM."""
    dimensions: int = 0

    def __init__(self, iterable=None):
        if iterable is not None:
            super().__init__(iterable)
            if self.dimensions > 0 and len(self) != self.dimensions:
                raise ValueError(
                    f"Expected {self.dimensions} dimensions, got {len(self)}"
                )

    def __repr__(self):
        content = super().__repr__()
        return f"Vector({self.dimensions})({content})"


class VNN:

    def __init__(self, column, operator, op_name, vector):
        self.column = column
        self.operator = operator
        self.op_name = op_name
        self.vector = vector


    @classmethod
    def l2d(cls, column, vector):
        return cls(column=column, operator='<->', op_name='l2d', vector=vector)


    @classmethod
    def inp(cls, column, vector):
        return cls(column=column, operator='<#>', op_name='inp', vector=vector)


    @classmethod
    def cos(cls, column, vector):
        return cls(column=column, operator='<=>', op_name='cos', vector=vector)


    @classmethod
    def l1d(cls, column, vector):
        return cls(column=column, operator='<+>', op_name='l1d', vector=vector)
    

def Vector(dimensions: int):
    return type(f"Vector_{dimensions}", (_BaseVector,), {"dimensions": dimensions})

