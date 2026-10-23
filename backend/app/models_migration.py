from sqlmodel import SQLModel, Field
from sqlalchemy import UniqueConstraint


class MigrationGroup(SQLModel, table=True):
    id: str = Field(primary_key=True)
    state: str = 'open'
    ever_activated: bool = False
    new_writes: bool = False
    ownership_json: str = '{}'
    thaw_receipt_json: str | None = None


class MigrationSource(SQLModel, table=True):
    id: str = Field(primary_key=True)
    group_id: str = Field(index=True, foreign_key='migrationgroup.id')
    origin: str
    roots_json: str
    registered_generation: str = ''
    path_aliases_json: str = '{}'


class MigrationBatch(SQLModel, table=True):
    id: str = Field(primary_key=True)
    group_id: str = Field(index=True, foreign_key='migrationgroup.id')
    source_id: str = Field(foreign_key='migrationsource.id')
    state: str = 'prepared'
    package_path: str = ''
    package_sha256: str = ''


class MigrationMember(SQLModel, table=True):
    __table_args__ = (UniqueConstraint('batch_id', 'task_id'),)
    id: str = Field(primary_key=True)
    batch_id: str = Field(index=True, foreign_key='migrationbatch.id')
    task_id: str
    generation: str
    candidate_path: str
    candidate_sha256: str
    state: str = 'prepared'


class MigrationDependency(SQLModel, table=True):
    id: str = Field(primary_key=True)
    group_id: str = Field(index=True, foreign_key='migrationgroup.id')
    batch_id: str = Field(foreign_key='migrationbatch.id')
    source_id: str = Field(foreign_key='migrationsource.id')
    generation: str
    kind: str
    active: bool = True
