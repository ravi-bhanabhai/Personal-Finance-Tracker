from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import DateField, StringField, PasswordField, SubmitField, FloatField, TextAreaField, SelectField, DateTimeField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
from .models import User

class RegisterForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(min=3, max=100)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password', "Password must match")])

    submit = SubmitField('Register')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email is already registered')
        
class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Register')

class AccountForm(FlaskForm):
    account_name = StringField('Account Name', validators=[DataRequired(), Length(min=3, max=100)])
    account_type = SelectField('Account Type', choices=[('cash', 'Cash'), ('bank', 'Bank')], validators=[DataRequired()])
    balance = FloatField('Initial Balance', validators=[DataRequired()])
    submit = SubmitField('Add Account')

class TransactionForm(FlaskForm):
    account = SelectField('Account', coerce=int, validators=[DataRequired()])
    category = SelectField('Category', coerce=int, validators=[DataRequired()])
    subcategory = SelectField('Subcategory', coerce=int, validators=[DataRequired()])
    amount = FloatField('Amount', validators=[DataRequired()])
    transaction_date = DateField('Date', format='%Y-%m-%d', validators=[DataRequired()])
    transaction_type = SelectField('Type', choices=[('income', 'Income'), ('expense', 'Expense')], validators=[DataRequired()])
    description = TextAreaField('Description', validators=[Length(max=200)])
    # 👇 New field for CSV upload
    file = FileField('Upload CSV', validators=[FileAllowed(['csv'], 'CSV files only!')])
    submit = SubmitField('Add Transaction')


class EditAccountForm(FlaskForm):
    account_name = StringField('Account Name', validators=[DataRequired(), Length(min=2, max=100)])
    account_type = SelectField('Account Type', choices=[('cash', 'Cash'), ('bank', 'Bank')], validators=[DataRequired()])
    balance = FloatField('Balance', validators=[DataRequired()])
    submit = SubmitField('Update Account')