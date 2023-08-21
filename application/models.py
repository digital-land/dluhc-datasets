import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from application.extensions import db


class DateModel(db.Model):
    __abstract__ = True

    entry_date: Mapped[Optional[datetime.date]] = mapped_column(
        db.Date, default=db.func.current_date()
    )
    start_date: Mapped[Optional[datetime.date]] = mapped_column(db.Date)
    end_date: Mapped[Optional[datetime.date]] = mapped_column(db.Date)


class DatasetField(db.Model):
    __tablename__ = "dataset_field"

    id: Mapped[int] = mapped_column(db.BigInteger, primary_key=True)

    dataset_name: Mapped[str] = mapped_column(
        Text, ForeignKey("dataset.name"), primary_key=True
    )
    field_name: Mapped[str] = mapped_column(
        Text, ForeignKey("field.name"), primary_key=True
    )

    dataset: Mapped[Optional["Dataset"]] = relationship(
        "Dataset", back_populates="fields"
    )
    field: Mapped[Optional["Field"]] = relationship("Field", back_populates="datasets")

    value: Mapped[str] = mapped_column(Text, nullable=False)

    def __repr__(self):
        return f"<DatasetField(dataset_name={self.dataset_name}, field_name={self.field_name})>"


class Dataset(DateModel):
    __tablename__ = "dataset"

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    fields: Mapped[Optional["DatasetField"]] = relationship(
        "DatasetField", back_populates="dataset"
    )

    def __repr__(self):
        return f"<Dataset(id={self.id}, name={self.name})>"


class Field(DateModel):
    __tablename__ = "field"

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    datasets: Mapped[Optional["DatasetField"]] = relationship(
        "DatasetField", back_populates="field"
    )

    def __repr__(self):
        return f"<Field(name={self.name})>"
