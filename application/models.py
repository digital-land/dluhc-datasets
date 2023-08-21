from typing import Optional

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from application.extensions import db


class DatasetField(db.Model):
    __tablename__ = "dataset_field"

    dataset_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dataset.id"), primary_key=True
    )
    field_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("field.id"), primary_key=True
    )

    dataset: Mapped[Optional["Dataset"]] = relationship(
        "Dataset", back_populates="fields"
    )
    field: Mapped[Optional["Field"]] = relationship("Field", back_populates="datasets")

    value: Mapped[str] = mapped_column(Text, nullable=False)

    def __repr__(self):
        return f"<DatasetField(dataset_id={self.dataset_id}, field_id={self.field_id})>"


class Dataset(db.Model):
    __tablename__ = "dataset"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Integer, nullable=False)
    fields: Mapped[Optional["DatasetField"]] = relationship(
        "DatasetField", back_populates="dataset"
    )

    def __repr__(self):
        return f"<Dataset(id={self.id}, name={self.name})>"


class Field(db.Model):
    __tablename__ = "field"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Integer, nullable=False)
    datasets: Mapped[Optional["DatasetField"]] = relationship(
        "DatasetField", back_populates="field"
    )

    def __repr__(self):
        return f"<Field(id={self.id}, name={self.name})>"
