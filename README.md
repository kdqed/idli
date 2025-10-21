# Coming Soon: An SQL ORM For Python That Treats You Like Its 2025

Alchemy is complex, but Idli is simple.

## Have Some Idli

(Doesn't work yet)

```bash
$ pip install idli
```

```bash
$ uv add idli
```

## Goals

- Act as a simple data persistence & query layer for simple Python apps (typical CRUD apps).
- Primarily support solo devs and small teams who iterate fast. Not intended for those who need 4 approvals to create a new column.
- Be as declarative as possible.
- Keep your data layer code minimal and elegant.
- Manage as much database administration as possible within the application.
- Handle migrations natively, with least nagging.
- Be framework agnostic.
- Support both `sync` and `async`.
- Be well documented.

## What Could It Be Like?

```python
from datetime import datetime
import uuid

from idli import connect

db = connect('postgresql://user:pwd@localhost/somedb')


@db.Model
class Task:
    id: uuid.UUID = uuid.uuid7 # initialize with function value
    title: str
    description: str | None # nullable column because None is an allowed type
    status: str = 'todo' #  initialize with default value as 'todo'
    created: datetime = datetime.now
    updated: datetime | None


task = Task(
    title = "Ship this ORM", 
    description = "Before the year ends",
)
task.save()

# tomorrow
task = Task.one_where(title = "Ship this ORM")
task.status = 'doing'
task.save()

# few weeks later
task = Task.one_where(title = "Ship this ORM")
task.update(status = 'done') # using .update will update the status and save it.

# next year
pending_tasks = Task.where(status__ne='done')
for task in pending_tasks:
    print(task.title, ',', 'Pending Since:', datetime.now()-task.created)

```

## Migrations

Apart from Django ORM, there is no other Python ORM that I know of that handles database migrations natively. Even with that, I'm too lazy to 'make migrations', check them into my VCS, run them, etc. It's okay be to lazy and prioritize other things in life. Hence, Idli will support auto-migrations for non-destructive migrations. Destructive migrations will have to be done by hand. Suppose the above data model has to be extended a few days later:

```python
from datetime import datetime
import uuid

from idli import connect, PrimaryKey, Index

db = connect(
    'postgresql://user:pwd@localhost/somedb',
    sambar_dip = True # this will automatically create tables, columns, and indexes defined below
)


@db.Model
class Task:
    id: uuid.UUID = uuid.uuid7 # initialize with function value
    title: str
    description: str | None # nullable column because None is an allowed type
    status: str = 'todo' #  initialize with default value as 'todo'
    created: datetime = datetime.now
    updated: datetime | None
    owner: User # newly created column referencing another table

    __idli__ = [
        Index('owner', '-created') # newly created Index
    ]


@db.Model
class User: # new table
    username: str
    full_name: str
    email: str
    send_task_reminders: bool = False

    __idli__ = [
        PrimaryKey('username')
    ]
```

This is inspired from GORM for Golang:

> NOTE: AutoMigrate will create tables, missing foreign keys, constraints, columns and indexes. It will change existing column’s type if its size, precision changed, or if it’s changing from non-nullable to nullable. It WON’T delete unused columns to protect your data.
> \- (from GORM docs: https://gorm.io/docs/migration.html)


## Async

```python
import asyncio
from datetime import datetime
import uuid

from idli import async_connect

db = async_connect('postgresql://user:pwd@localhost/somedb')


@db.Model
class Task:
    id: uuid.UUID = uuid.uuid7 # initialize with function value
    title: str
    description: str | None # nullable column because None is an allowed type
    status: str = 'todo' #  initialize with default value as 'todo'
    created: datetime = datetime.now
    updated: datetime | None


async def main():
    task = Task(
        title = "Ship this ORM", 
        description = "Before the year ends",
    )
    await task.save()


asyncio.run(main())
```

