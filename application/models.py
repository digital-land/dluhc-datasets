import datetime
from typing import List, Optional

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from application.extensions import db

dataset_field = db.Table(
    "dataset_field",
    db.Column("dataset_name", db.Text, db.ForeignKey("dataset.name")),
    db.Column("field_name", db.Text, db.ForeignKey("field.name")),
    db.PrimaryKeyConstraint("dataset_name", "field_name"),
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

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    fields: Mapped[List["Field"]] = relationship(
        "Field",
        secondary=dataset_field,
        back_populates="datasets",
        order_by="Field.name",
    )

    entries: Mapped[List["Entry"]] = relationship("Entry", back_populates="dataset")

    def __repr__(self):
        return f"<Dataset(id={self.name}, name={self.name}, fields={self.fields})>"


class Entry(db.Model):
    __tablename__ = "entry"

    id: Mapped[int] = mapped_column(db.BigInteger, primary_key=True)
    dataset_name: Mapped[str] = mapped_column(
        Text, ForeignKey("dataset.name"), primary_key=True
    )
    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="entries")
    data: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), nullable=False)

    def __repr__(self):
        return f"<Entry(dataset_name={self.dataset_name}, id={self.id}, data={self.data}))>"


class Field(DateModel):
    __tablename__ = "field"

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    datasets: Mapped[List["Dataset"]] = relationship(
        "Dataset", secondary=dataset_field, back_populates="fields"
    )

    def __repr__(self):
        return f"<Field(name={self.name})>"
