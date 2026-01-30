import datetime
import uuid
from enum import Enum, auto
from functools import total_ordering
from typing import List, Optional

from flask import url_for
from sqlalchemy import JSON, UUID, ForeignKey, Text, event
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from application.extensions import db
from application.utils import collect_start_date, date_to_string, parse_date

dataset_field = db.Table(
    "dataset_field",
    db.Column("dataset", db.Text, db.ForeignKey("dataset.dataset")),
    db.Column("field", db.Text, db.ForeignKey("field.field")),
    db.PrimaryKeyConstraint("dataset", "field"),
)


class DateModel(db.Model):
    __abstract__ = True

    entry_date: Mapped[datetime.date] = mapped_column(
        db.Date, default=datetime.datetime.today
    )
    start_date: Mapped[Optional[datetime.date]] = mapped_column(db.Date)
    end_date: Mapped[Optional[datetime.date]] = mapped_column(db.Date)


class ChangeType(Enum):
    ADD = "ADD"
    EDIT = "EDIT"
    ARCHIVE = "ARCHIVE"


class ChangeLog(db.Model):
    __tablename__ = "change_log"

    id: Mapped[uuid.uuid4] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    dataset_id: Mapped[str] = mapped_column(Text, ForeignKey("dataset.dataset"))
    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="change_log")

    change_type: Mapped[ChangeType] = mapped_column(ENUM(ChangeType), nullable=False)

    created_date: Mapped[datetime.date] = mapped_column(
        db.Date, default=datetime.datetime.today
    )
    data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    record_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "record.id",
            ondelete="cascade",
        ),
    )
    record: Mapped["Record"] = relationship("Record", back_populates="change_log")
    github_login: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self):
        parts = [
            f"<ChangeLog(dataset={self.dataset.name}",
            f"change_type={self.change_type}",
            f"created_date={self.created_date}",
        ]
        return ", ".join(parts)


class Dataset(DateModel):
    __tablename__ = "dataset"

    dataset: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)

    fields: Mapped[List["Field"]] = relationship(
        "Field",
        secondary=dataset_field,
        back_populates="datasets",
    )

    records: Mapped[List["Record"]] = relationship(
        "Record",
        back_populates="dataset",
        order_by="Record.row_id",
        cascade="all, delete",
    )

    change_log: Mapped[List["ChangeLog"]] = relationship(
        "ChangeLog", back_populates="dataset", order_by="ChangeLog.created_date"
    )

    last_updated: Mapped[Optional[datetime.date]] = mapped_column(
        db.Date, default=datetime.datetime.today
    )

    entity_minimum: Mapped[int] = mapped_column(db.BigInteger, nullable=True)
    entity_maximum: Mapped[int] = mapped_column(db.BigInteger, nullable=True)
    consideration: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    custodian: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    specification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    referenced_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    references: Mapped[List["Reference"]] = relationship(
        "Reference", back_populates="dataset", cascade="all, delete"
    )

    def sorted_fields(self):
        return sorted(self.fields)

    def __repr__(self):
        return (
            f"<Dataset(dataset={self.dataset}, name={self.name}, fields={self.fields})>"
        )

    def to_dict(self):
        return {
            "dataset": self.dataset,
            "name": self.name,
            "total_records": len(self.records),
            "last_updated": self.last_updated,
            "data": f"{url_for('main.dataset_json', id=self.dataset, _external=True)}",
        }


class Reference(db.Model):
    __tablename__ = "reference"

    id: Mapped[uuid.uuid4] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    dataset_id: Mapped[str] = mapped_column(Text, ForeignKey("dataset.dataset"))
    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="references")
    referenced_by: Mapped[str] = mapped_column(Text, nullable=False)
    specification: Mapped[str] = mapped_column(Text, nullable=True)

    def __repr__(self):
        return f"<Reference(dataset={self.dataset_id}, referenced_by={self.referenced_by}, specification={self.specification})>"  # noqa

    def __eq__(self, other: "Reference") -> bool:
        if not isinstance(other, Reference):
            return NotImplemented
        if self.referenced_by == other.referenced_by:
            if self.specification is None and other.specification is None:
                return True
            return self.specification == other.specification
        return False

    def __hash__(self) -> int:
        if self.specification is None:
            return hash(self.referenced_by)
        return hash((self.referenced_by, self.specification))


class Record(DateModel):
    __tablename__ = "record"

    id: Mapped[uuid.uuid4] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    row_id: Mapped[int] = mapped_column(db.Integer, nullable=False)

    entity: Mapped[int] = mapped_column(db.BigInteger, nullable=True)
    prefix: Mapped[str] = mapped_column(Text, nullable=True)
    reference: Mapped[str] = mapped_column(Text, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)

    data: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), nullable=False)

    dataset_id: Mapped[str] = mapped_column(Text, ForeignKey("dataset.dataset"))
    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="records")

    change_log: Mapped[List["ChangeLog"]] = relationship(
        "ChangeLog",
        back_populates="record",
        order_by="ChangeLog.created_date",
        cascade="all, delete",
    )

    def get(self, field, default=None):
        field_name = field.replace("-", "_")
        if field_name != "dataset":
            if hasattr(self, field_name):
                value = getattr(self, field_name)
                if value:
                    return value
        return self.data.get(field, default)

    def __repr__(self):
        return f"<Record(dataset={self.dataset.name}, row_id={self.row_id}, data={self.data}))>"

    def to_dict(self):
        data = {
            "entity": self.entity,
            "prefix": self.prefix,
            "reference": self.reference,
            **self.data,
        }
        if self.description:
            data["description"] = self.description
        if self.notes:
            data["notes"] = self.notes

        if self.start_date:
            if isinstance(self.start_date, datetime.date):
                data["start-date"] = self.start_date.strftime("%Y-%m-%d")
            else:
                data["start-date"] = self.start_date
        if self.end_date:
            data["end-date"] = self.end_date.strftime("%Y-%m-%d")
        if self.entry_date:
            if isinstance(self.entry_date, datetime.date):
                data["entry-date"] = self.entry_date.strftime("%Y-%m-%d")
            else:
                data["entry-date"] = self.entry_date
        return data

    @classmethod
    def factory(cls, row_id, entity, dataset, data_dict, config):
        record = cls()
        for column in record.__table__.columns:
            if column.name != "data":
                if column.name in data_dict:
                    setattr(record, column.name, data_dict.pop(column.name))

        for key, value in data_dict.items():
            if key.endswith("-date") and value:
                date_key = key.replace("-", "_")
                date_value = parse_date(value)
                setattr(record, date_key, date_value)

        for key in ["start-date", "end-date", "entry-date"]:
            if key in data_dict:
                data_dict.pop(key)

        record.row_id = row_id
        record.entity = int(entity)
        record.prefix = (
            "wikidata" if dataset in config["WIKIDATA_PREFIX_DATASETS"] else dataset
        )
        record.data = data_dict
        record.dataset_id = dataset

        return record


@total_ordering
class Field(DateModel):
    __tablename__ = "field"

    field: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    datatype: Mapped[str] = mapped_column(Text, nullable=False)
    datasets: Mapped[List[Dataset]] = relationship(
        "Dataset", secondary=dataset_field, back_populates="fields"
    )
    description: Mapped[Optional[str]] = mapped_column(Text)

    def to_dict(self):
        return {
            "field": self.field,
            "name": self.name,
            "datatype": self.datatype,
            "description": self.description,
        }

    def __repr__(self):
        return f"<Field(name={self.name})>"

    def __eq__(self, other):
        return self.field == other.field

    def __lt__(self, other):
        if self.field == "entity":
            return True
        if self.field == "name" and other.field != "entity":
            return True
        if self.field == "prefix" and other.field not in ["entity", "name"]:
            return True
        if self.field == "reference" and other.field not in [
            "entity",
            "name",
            "prefix",
        ]:
            return True

        if self.field not in [
            "entity",
            "name",
            "prefix",
            "reference",
        ] and other.field not in ["entity", "name", "prefix", "reference"]:
            if self.datatype == "datetime" and other.datatype != "datetime":
                return False

            if self.datatype == "datetime" and other.datatype == "datetime":
                prefix = self.field.split("-")[0]
                other_prefix = other.field.split("-")[0]
                if prefix == "entry" and other_prefix != "entry":
                    return True
                if prefix == "start" and other_prefix != "entry":
                    return True
                if prefix == "end" and other_prefix not in ["entry", "start"]:
                    return False

            if self.datatype != "datetime" and other.datatype != "datetime":
                return self.field < other.field

            if self.datatype != "datetime" and other.datatype == "datetime":
                return True

        return False


class UpdateStatus(Enum):
    PENDING = auto()
    COMPLETE = auto()
    INCOMPLETE = auto()
    CANCELLED = auto()


class Update(db.Model):
    __tablename__ = "update"
    id: Mapped[uuid.uuid4] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    dataset_id: Mapped[str] = mapped_column(Text, db.ForeignKey("dataset.dataset"))
    dataset: Mapped[Dataset] = relationship("Dataset", backref="updates")
    records: Mapped[List["UpdateRecord"]] = relationship(
        "UpdateRecord", backref="update", cascade="all, delete"
    )
    created_date: Mapped[datetime.date] = mapped_column(
        db.Date, default=datetime.datetime.today
    )

    status: Mapped[ENUM] = mapped_column(
        ENUM(UpdateStatus), nullable=False, default=UpdateStatus.PENDING
    )


class UpdateRecord(db.Model):
    __tablename__ = "update_record"

    id: Mapped[uuid.uuid4] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    update_id: Mapped[uuid.uuid4] = mapped_column(
        UUID(as_uuid=True), db.ForeignKey("update.id")
    )
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    processed: Mapped[bool] = mapped_column(db.Boolean, default=False, nullable=False)
    changes: Mapped[dict] = mapped_column(JSON, nullable=True)
    new_record: Mapped[bool] = mapped_column(db.Boolean, default=False, nullable=False)


def create_change_log(record, data, change_type):
    previous = record.to_dict()
    reference = previous["reference"]

    for key, value in data.items():
        if key not in ["csrf_token", "edit_notes", "csv_file", "entity"]:
            k = key
            v = value
            if "-date" in k:
                k = k.replace("-date", "_date")
                if isinstance(v, str):
                    v = value
                elif isinstance(v, datetime.date):
                    v = date_to_string(value)
            if hasattr(record, k):
                setattr(record, k, v)
            else:
                record.data[key] = v

    # if this comes from a form, start date is in the form
    if data.get("year") or data.get("month") or data.get("day"):
        start_date, format = collect_start_date(data)
        if start_date:
            start_date = datetime.datetime.strptime(start_date, format)
            if start_date != record.start_date:
                record.start_date = start_date
                record.data["start-date"] = start_date.strftime(format)

    # set existing reference as it is not in data
    record.data["reference"] = reference

    # check for end date in the original record and data
    if change_type == ChangeType.ARCHIVE:
        end_date = data.get("end-date")
        if end_date is None:
            record.end_date = datetime.datetime.today()
        else:
            record.end_date = end_date

    edit_notes = data.get("edit_notes", None)
    if edit_notes:
        edit_notes = f"Updated {record.prefix}:{reference}. {edit_notes}"

    current = record.to_dict()

    for key, value in previous.items():
        if value is None:
            previous[key] = ""

    for key, value in current.items():
        if value is None:
            current[key] = ""

    change_log = ChangeLog(
        change_type=change_type,
        data={"from": previous, "to": current},
        notes=edit_notes,
        record_id=record.id,
    )
    return change_log


@event.listens_for(Dataset.records, "append")
def receive_append(target, value, initiator):
    target.last_updated = datetime.date.today()


@event.listens_for(Record, "before_insert")
def receive_before_insert(mapper, connection, target):
    start_date = target.data.get("start-date", None)
    end_date = target.data.get("end-date", None)
    if start_date:
        try:
            target.start_date = datetime.datetime.strptime(
                start_date, "%Y-%m-%d"
            ).date()
        except Exception:
            target.start_date = None
    if end_date:
        try:
            target.end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
        except Exception:
            target.end_date = None
