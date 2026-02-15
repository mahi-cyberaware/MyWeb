from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, TextAreaField, SelectField, BooleanField, URLField, PasswordField, EmailField
from wtforms.validators import DataRequired, Optional, URL, Email, EqualTo, Length, ValidationError
from models import User

class ToolForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[DataRequired()])
    category = SelectField('Category', choices=[
        ('Network Security', 'Network Security'),
        ('Web Security', 'Web Security'),
        ('Password Security', 'Password Security'),
        ('Other', 'Other')
    ], validators=[DataRequired()])
    language = StringField('Language', validators=[Optional()])
    code = TextAreaField('Code', validators=[Optional()])
    github_url = URLField('GitHub URL', validators=[Optional(), URL()])

class BlogForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired()])
    slug = StringField('Slug', validators=[DataRequired()])
    excerpt = TextAreaField('Excerpt', validators=[Optional()])
    content = TextAreaField('Content (Markdown)', validators=[DataRequired()])
    featured_image = FileField('Featured Image', validators=[Optional(), FileAllowed(['jpg', 'png', 'jpeg', 'gif'], 'Images only!')])
    tags = StringField('Tags (comma separated)', validators=[Optional()])
    published = BooleanField('Publish immediately')

class UploadFileForm(FlaskForm):
    description = TextAreaField('Description', validators=[Optional()])
    file_type = SelectField('Category', choices=[
        ('image', 'Image'),
        ('video', 'Video'),
        ('code', 'Code File')
    ], validators=[DataRequired()])
    file = FileField('File', validators=[FileRequired()])

# Registration, Login, ChangePassword, ContactForm remain the same as before
class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already taken.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered.')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])

class ChangePasswordForm(FlaskForm):
    old_password = PasswordField('Old Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[DataRequired(), Length(min=6)])
    confirm_new_password = PasswordField('Confirm New Password', validators=[DataRequired(), EqualTo('new_password')])

class ContactForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    email = EmailField('Your Email', validators=[DataRequired(), Email()])
    subject = StringField('Subject', validators=[DataRequired()])
    message = TextAreaField('Message', validators=[DataRequired()])
