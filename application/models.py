import datetime
import uuid
from functools import total_ordering
from typing import List, Optional

from sqlalchemy import UUID, ForeignKey, Text, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from application.extensions import db

dataset_field = db.Table(
    "dataset_field",
    db.Column("dataset", db.Text, db.ForeignKey("dataset.dataset")),
    db.Column("field", db.Text, db.ForeignKey("field.field")),
    db.PrimaryKeyConstraint("dataset", "field"),
)


class DateModel(db.Model):
    __abstract__ = True

    entry_date: Mapped[Optional[datetime.date]] = mapped_column(
        db.Date, default=db.func.current_date()
    )
    start_date: Mapped[Optional[datetime.date]] = mapped_column(db.Date)
    end_date: Mapped[Optional[datetime.date]] = mapped_column(db.Date)


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
        "Record", back_populates="dataset", order_by="Record.row_id"
    )

    last_updated: Mapped[Optional[datetime.date]] = mapped_column(
        db.Date, default=db.func.current_date()
    )

    def sorted_fields(self):
        return sorted(self.fields)

    def __repr__(self):
        return f"<Dataset(id={self.name}, name={self.name}, fields={self.fields})>"


class Record(db.Model):
    __tablename__ = "record"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    row_id: Mapped[int] = mapped_column(db.Integer, nullable=False)
    dataset_id: Mapped[str] = mapped_column(Text, ForeignKey("dataset.dataset"))
    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="records")
    data: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), nullable=False)

    end_date: Mapped[Optional[datetime.date]] = mapped_column(db.Date)

    versions: Mapped[List["RecordVersion"]] = relationship(
        "RecordVersion",
        back_populates="record",
        order_by="desc(RecordVersion.end_date)",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Record(dataset={self.dataset.name}, row_id={self.row_id}, data={self.data}))>"


class RecordVersion(db.Model):
    __tablename__ = "record_version"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    record_id: Mapped[int] = mapped_column(UUID, ForeignKey("record.id"))

    record: Mapped["Record"] = relationship("Record", back_populates="versions")
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    end_date: Mapped[datetime.datetime] = mapped_column(
        db.DateTime, nullable=False, default=datetime.datetime.utcnow
    )


@total_ordering
class Field(DateModel):
    __tablename__ = "field"

    field: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    datatype: Mapped[str] = mapped_column(Text, nullable=False)
    datasets: Mapped[List["Dataset"]] = relationship(
        "Dataset", secondary=dataset_field, back_populates="fields"
    )
    description: Mapped[Optional[str]] = mapped_column(Text)

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


@event.listens_for(Dataset.records, "append")
def receive_append(target, value, initiator):
    target.last_updated = datetime.date.today()
