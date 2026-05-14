from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, IntegerField, TextAreaField
from wtforms.validators import DataRequired, Length

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class CreateUserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    full_name = StringField('Full name')
    role = StringField('Role', validators=[DataRequired()])  # 'teacher' or 'student'
    submit = SubmitField('Create')

class AssessmentForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired()])
    subject_id = IntegerField('Subject ID', validators=[DataRequired()])
    submit = SubmitField('Create')
