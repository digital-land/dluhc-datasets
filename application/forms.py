from flask_wtf import FlaskForm
from wtforms import Field, StringField, URLField
from wtforms.validators import ValidationError
from wtforms.widgets import TextInput


# change to a regex validator
def curie_check(form, field):
    if len(field.data.split(":")) != 2:
        raise ValidationError("curie should be in the format {namespace}:{identifier}")


class CurieField(Field):
    widget = TextInput()

    def __init__(self, **kwargs):
        super(CurieField, self).__init__(validators=[curie_check], **kwargs)


class FormBuilder:
    field_types = {
        "curie": CurieField,
        "string": StringField,
        "text": StringField,
        "url": URLField,
    }

    def build(self):
        class TheForm(FlaskForm):
            pass

        for field in self.fields:
            form_field = self.field_types.get(field.datatype)
            if form_field is not None:
                setattr(TheForm, field.field, form_field())

        return TheForm()

    def form_fields(self):
        return self.fields

    def __init__(self, fields):
        skip_fields = {"entity", "end-date", "start-date", "entry-date"}
        self.fields = []
        for field in fields:
            if field.field not in skip_fields:
                self.fields.append(field)
