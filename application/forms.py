from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired
from wtforms import IntegerField, StringField, TextAreaField, URLField
from wtforms.validators import URL, DataRequired, Optional, ValidationError

from application.utils import is_url_field, url_error


# change to a regex validator
def curie_check(form, field):
    if field.data is None:
        return
    value = str(field.data).strip()
    if value == "":
        return

    if len(field.data.split(":")) != 2:
        raise ValidationError(
            f"{field.name} is a curie and should be in the format 'namespace:identifier'"  # noqa: E231
        )


def url_check(form, field):
    error = url_error(field.data)
    if error:
        raise ValidationError(f"{field.name} {error}")


class FormBuilder:
    field_types = {
        "curie": StringField,
        "string": StringField,
        "text": TextAreaField,
        "url": URLField,
        "datetime": StringField,
        "integer": IntegerField,
    }

    def build(self):
        class TheForm(FlaskForm):
            pass

        for field in self.fields:
            form_field = self.field_types.get(field.datatype)
            if form_field is not None:
                if field.datatype == "curie":
                    setattr(TheForm, field.field, form_field(validators=[curie_check]))
                elif field.field == "name" or (
                    field.field == "reference" and self.require_reference
                ):
                    setattr(
                        TheForm, field.field, form_field(validators=[DataRequired()])
                    )
                elif is_url_field(field):
                    # Optional first, so an empty url is left alone. Without it
                    # URL() rejects a blank value and the field becomes required,
                    # which the specification never asks for.
                    setattr(
                        TheForm,
                        field.field,
                        form_field(validators=[Optional(), URL(), url_check]),
                    )
                elif field.datatype == "datetime":
                    setattr(TheForm, field.field, StringField(validators=[Optional()]))
                else:
                    setattr(TheForm, field.field, form_field())

        if self.include_edit_notes:
            setattr(TheForm, "edit_notes", TextAreaField(validators=[DataRequired()]))

        return TheForm()

    def form_fields(self):
        return sorted(self.fields)

    def __init__(self, fields, include_edit_notes=False, require_reference=True):
        skip_fields = {"entry-date", "prefix"}
        self.fields = []
        self.include_edit_notes = include_edit_notes
        self.require_reference = require_reference
        for field in fields:
            if field.field not in skip_fields:
                self.fields.append(field)


class CsvUploadForm(FlaskForm):
    csv_file = FileField("Upload a file", validators=[FileRequired()])
