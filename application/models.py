import datetime
from functools import total_ordering
from typing import List, Optional

from sqlalchemy import ForeignKey, Text, event
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
        order_by="Field.name",
    )

    records: Mapped[List["Record"]] = relationship("Record", back_populates="dataset")

    last_updated: Mapped[Optional[datetime.date]] = mapped_column(
        db.Date, default=db.func.current_date()
    )

    def __repr__(self):
        return f"<Dataset(id={self.name}, name={self.name}, fields={self.fields})>"


class Record(db.Model):
    __tablename__ = "record"

    id: Mapped[int] = mapped_column(db.BigInteger, primary_key=True)
    dataset_id: Mapped[str] = mapped_column(
        Text, ForeignKey("dataset.dataset"), primary_key=True
    )
    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="records")
    data: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), nullable=False)

    def __repr__(self):
        return f"<Record(dataset={self.dataset.name}, id={self.id}, data={self.data}))>"


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
        else:
            if other.field not in ["entity", "name", "prefix", "reference"]:
                return self.field < other.field

        # if self.datatype == "datetime" and other.datatype != "datetime":
        #     return True
        # if self.datatype != "datetime" and other.datatype == "datetime":
        #     prefix = self.field.split("-")[0]
        #     other_prefix = other.field.split("-")[0]
        #     return prefix < other_prefix
        return False


@event.listens_for(Dataset.records, "append")
def receive_append(target, value, initiator):
    target.last_updated = datetime.date.today()
