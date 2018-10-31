from flask_wtf import Form
from flask_wtf.file import FileField

from wtforms import SelectField, StringField, SelectMultipleField
from wtforms.validators import InputRequired, Optional
from wtforms.widgets import ListWidget, CheckboxInput


class NoAnnotationDataError(Exception):
    pass


class SelectViewForm(Form):
    options = SelectField('View', choices=[])


class SelectAnnoForm(Form):
    options = SelectField(u"Filename",  choices=[], validators=[InputRequired()])


class MultipleCheckboxField(SelectMultipleField):
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()


class DeleteMultiForm(Form):
    options = SelectMultipleField(u"Filename", choices=[])


class UploadForm(Form):
    ufile = FileField(validators=[Optional()])
    #visualize_file = FileField(validators=[Optional()])

    def validate(self):
        if not self.ufile.data: #and not self.visualize_file.data:
            return False
        return True


class OutputAnnotationsForm(Form):
    starttime = StringField(u'start time', render_kw={'placeholder': 'Breath Start #'})
    endtime = StringField(u'end time', render_kw={'placeholder': 'Breath End #'})


class VisualizeForm(Form):
    raw_data_files = SelectField("Raw Data Filename", choices=[], validators=[InputRequired()])
    annotations = SelectField("Annotation Filename", choices=[], validators=[InputRequired()])


class ReconcileForm(Form):
    raw_data_files = SelectField("Raw Data Filename", validators=[InputRequired()])
    reviewer_1 = SelectField("Reviewer 1", validators=[InputRequired()])
    reviewer_2 = SelectField("Reviewer 2", validators=[InputRequired()])


class TimeData(object):
    def __init__(self, rel_time):
        self.rel_time = rel_time
