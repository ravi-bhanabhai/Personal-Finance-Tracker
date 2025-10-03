from flask import Blueprint, jsonify, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from flask import request
from sqlalchemy import func
from sqlalchemy import select
from .forms import LoginForm, RegisterForm, AccountForm, TransactionForm, EditAccountForm
from .models import User, Account, Transaction, Category, Subcategory
from . import db, bcrypt, login_manager
import pandas as pd
from io import TextIOWrapper
from collections import defaultdict
from datetime import datetime, timedelta

main = Blueprint("main", __name__)

@main.route("/")
def index():
    return render_template("index.html")


@main.route("/login", methods=['GET', 'POST'])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        # Check if the user exists
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password_hash, form.password.data):
            # Login user
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('main.dashboard'))
        else:
            # Flash error message for invalid credentials
            flash('Invalid email or password.', 'danger')

    return render_template("login.html", form=form)


@main.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()

    if form.validate_on_submit():
        # Check if the email is already in use
        if User.query.filter_by(email=form.email.data).first():
            flash("Email is already registered. Please log in or use another email.", "danger")
            return redirect(url_for("main.register"))

        # Hash the password and create a new user
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode("utf-8")
        user = User(name=form.name.data, email=form.email.data, password_hash=hashed_password)
        db.session.add(user)
        db.session.commit()

        flash("Account created successfully! Please log in.", "success")
        return redirect(url_for("main.login"))

    return render_template("register.html", form=form)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@main.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out successfully." "success")
    return redirect(url_for("main.login"))


@main.route('/add_account', methods=['GET', 'POST'])
@login_required
def add_account():
    form = AccountForm()
    if form.validate_on_submit():
        account = Account(
            account_name=form.account_name.data,
            account_type=form.account_type.data,
            balance=form.balance.data,
            user_id=1    #current_user.user_id TODO
        )
        db.session.add(account)
        db.session.commit()
        flash('Account added successfully!', 'success')
        return redirect(url_for('main.index'))
    return render_template('add_account.html', form=form)


@main.route('/view_transactions', methods=['GET'])
@login_required
def view_transactions():
    # Fetch transactions for the logged-in user
    transactions = (
        db.session.query(
            Transaction.transaction_date,
            Account.account_name.label("account_name"),
            Category.name.label('category_name'),
            Subcategory.name.label('subcategory_name'),
            Transaction.amount,
            Transaction.transaction_type,
            Transaction.description,
            Transaction.currency
        )
        .join(Account, Transaction.account_id == Account.account_id)
        .join(Category, Transaction.category_id == Category.category_id)
        .join(Subcategory, Transaction.subcategory_id == Subcategory.subcategory_id)
        .filter(Account.user_id == current_user.user_id)
        .all()
    )

    # Print transactions to the terminal
    print("\n--- Transactions ---")
    for transaction in transactions:
        print(
            f"Date: {transaction.transaction_date}, "
            f"Account: {transaction.account_name}, "
            f"Category: {transaction.category_name}, "
            f"Subcategory: {transaction.subcategory_name}, "
            f"Amount: {transaction.amount}, "
            f"Type: {transaction.transaction_type}, "
            f"Description: {transaction.description}, "
            f"Currency: {transaction.currency}"
        )
    print("--- End of Transactions ---\n")

    return render_template('view_transactions.html', transactions=transactions)

@main.route('/add_transaction', methods=['GET', 'POST'])
@login_required
def add_transaction():
    form = TransactionForm()
    form.account.choices = [(acc.account_id, acc.account_name) for acc in Account.query.all()]
    form.category.choices = [(cat.category_id, cat.name) for cat in Category.query.all()]
    form.subcategory.choices = [(sub.subcategory_id, sub.name) for sub in Subcategory.query.all()]

    print(form.file.data)
    if request.method == 'POST':

        if form.file.data and form.file.data.filename != '':
            print("📁 CSV file detected, processing upload...")
            # ✅ Skip full form validation for CSV upload
            # Get all categories and subcategories from the database
            categories = Category.query.all()
            subcategories = Subcategory.query.all()

            # Create name-to-ID mappings
            category_map = {cat.name: cat.category_id for cat in categories}
            subcategory_map = {sub.name: sub.subcategory_id for sub in subcategories}

            # CSV upload using Pandas
            file = TextIOWrapper(form.file.data.stream, encoding='utf-8')
            df = pd.read_csv(file)

            df['category_id'] = df['Category'].map(category_map)
            df['subcategory_id'] = df['Subcategory'].map(subcategory_map)

            # Strip and standardize column names if needed
            df.columns = df.columns.str.strip()

            # Create 'amount' and 'transaction_type' based on Debit/Credit logic
            def extract_amount_type(row):
                if pd.notnull(row['Credit Amount']):
                    return pd.Series([row['Credit Amount'], 'income'])
                elif pd.notnull(row['Debit Amount']):
                    return pd.Series([row['Debit Amount'], 'expense'])
                else:
                    return pd.Series([0.0, 'unknown'])

            df[['amount', 'transaction_type']] = df.apply(extract_amount_type, axis=1)

            # Rename columns to match your model
            df.rename(columns={
                'Transaction Date': 'transaction_date',
                'Transaction Description': 'description',
                'Category': 'category',
                'Subcategory': 'subcategory'
            }, inplace=True)
            df['transaction_date'] = pd.to_datetime(df['transaction_date'], format='%d/%m/%Y')

            # Optional: drop original Debit/Credit columns
            df.drop(columns=['Debit Amount', 'Credit Amount'], inplace=True)

            # Optional: validate required columns
            required_columns = ['category_id', 'subcategory_id', 'amount', 'transaction_date', 'transaction_type']
            missing = [col for col in required_columns if col not in df.columns]

            if missing:
                flash(f'Missing required columns in CSV: {", ".join(missing)}', 'danger')
                return redirect(url_for('main.add_transaction'))

            # Insert each row
            for i, row in df.iterrows():
                try:
                    transaction = Transaction(
                        account_id=form.account.data,
                        category_id=int(row['category_id']),
                        subcategory_id=int(row['subcategory_id']),
                        amount=float(row['amount']),
                        transaction_date=row['transaction_date'],
                        transaction_type=row['transaction_type'],
                        description=row.get('description', ''),
                        currency=row.get('currency', 'GBR')
                    )
                except Exception as e:
                    print(f"❌ Error processing row {row}: {e}")
                    raise e
                db.session.add(transaction)

            db.session.commit()
            flash('CSV transactions uploaded successfully!', 'success')
            return redirect(url_for('main.view_transactions'))
        elif form.validate_on_submit():
            print("✍️ No CSV upload, processing manual form submission...")
            # Manual form submission
            transaction = Transaction(
                account_id=form.account.data,
                category_id=form.category.data,
                subcategory_id=form.subcategory.data,
                amount=form.amount.data,
                transaction_date=form.transaction_date.data,
                transaction_type=form.transaction_type.data,
                description=form.description.data,
                currency="GBR"
            )
            db.session.add(transaction)
            db.session.commit()
            flash('Transaction added successfully!', 'success')
            return redirect(url_for('main.view_transactions'))
        else:
            print("⚠️ POST request received but form not valid")
    return render_template('add_transaction.html', form=form)

@main.route('/get_subcategories/<int:category_id>', methods=['GET'])
@login_required
def get_subcategories(category_id):
    subcategories = Subcategory.query.filter_by(category_id=category_id).all()
    subcategories_data = [{"id": sub.subcategory_id, "name": sub.name} for sub in subcategories]
    return jsonify(subcategories_data)


from collections import defaultdict

@main.route('/dashboard')
@login_required
def dashboard():
    # Financial summary
    user_accounts = Account.query.filter_by(user_id=current_user.user_id).all()
    account_ids = [acc.account_id for acc in user_accounts]

    stmt = (
        select(
            Transaction.transaction_date,
            Transaction.amount,
            Transaction.transaction_type,
            Transaction.description,
            Category.name.label("category_name"),
            Subcategory.name.label("subcategory_name"),
        )
        .join(Category, Transaction.category_id == Category.category_id)
        .join(Subcategory, Transaction.subcategory_id == Subcategory.subcategory_id)
        .filter(Transaction.account_id.in_(account_ids))
    )
    sql = stmt.compile(compile_kwargs={"literal_binds": True})
    df = pd.read_sql(str(sql), db.engine) #['transaction_date', 'amount', 'transaction_type', 'category_name','subcategory_name']

    total_income = df[df['transaction_type'] == 'income']['amount'].sum()
    total_income = round(total_income, 2)

    total_expenses = df[df['transaction_type'] == 'expense']['amount'].sum()
    total_expenses = round(total_expenses, 2)

    total_balance = db.session.query(db.func.sum(Account.balance)).filter(
        Account.user_id == current_user.user_id
    ).scalar() or 0
    total_balance = round(total_balance, 2)

    remaining_balance = round(total_balance + total_income - total_expenses, 2)

    #Filter out SubCategory = 'Investments'
    df = df[df['subcategory_name'] != 'Investments']


    # Recent transactions
    recent_transactions = db.session.query(
        Transaction.transaction_date,
        Account.account_name.label('account_name'),
        Category.name.label('category_name'),
        Subcategory.name.label('subcategory_name'),
        Transaction.amount,
        Transaction.transaction_type,
        Transaction.description,
        Transaction.currency
    ).join(Account, Transaction.account_id == Account.account_id)\
     .join(Category, Transaction.category_id == Category.category_id)\
     .join(Subcategory, Transaction.subcategory_id == Subcategory.subcategory_id)\
     .filter(Account.user_id == current_user.user_id)\
     .order_by(Transaction.transaction_date.desc())\
     .limit(5).all()

    # Spending by category
    # Filter only expenses
    expenses_df = df[df["transaction_type"] == "expense"]
    expenses_df["joined_category"] = expenses_df["category_name"].fillna("") + ' - ' + \
                            expenses_df["subcategory_name"].fillna("").radd(" - ").str.strip(" -")


    # Group by category and sum amounts
    spending_by_category = (
        expenses_df.groupby("joined_category")["amount"]
        .sum()
        .reset_index()
        .values.tolist()
    )

    income_vs_expense = {
        'income': round(total_income, 2),
        'expense': round(total_expenses, 2)
    }

    #Income vs Expense over time ()

    # Full Date range
    last_year_df = df

    # Convert to month period
    last_year_df["month"] = pd.to_datetime(last_year_df["transaction_date"]).dt.to_period("M")

    # Group by month and transaction type
    monthly_grouped = (
        last_year_df.groupby(["month", "transaction_type"])["amount"]
        .sum()
        .unstack(fill_value=0)  # columns become ['expense', 'income'] if present
        .sort_index()
    )

    # Extract series as lists (rounded)
    time_series_labels = [str(m) for m in monthly_grouped.index]
    time_series_income = monthly_grouped.get("income", pd.Series(0, index=monthly_grouped.index)).round(2).tolist()
    time_series_expense = monthly_grouped.get("expense", pd.Series(0, index=monthly_grouped.index)).round(2).tolist()


    today = datetime.today().date()

    # Stacked Area Chart (monthly expenses by category)
    stacked_area_labels = []
    stacked_area_data = defaultdict(lambda: [0]*6)
    for i in range(6):
        month = today.replace(day=1) - timedelta(days=30*i)
        label = month.strftime('%b')
        stacked_area_labels.insert(0, label)

        month_start = month.replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)

        monthly_transactions = db.session.query(
            Category.name, func.sum(Transaction.amount)
        ).join(Category).filter(
            Transaction.transaction_type == 'expense',
            Transaction.account_id.in_(account_ids),
            Transaction.transaction_date >= month_start,
            Transaction.transaction_date <= month_end
        ).group_by(Category.name).all()

        for category, total in monthly_transactions:
            stacked_area_data[category][5 - i] = round(total, 2)


    # Top 10 Descriptions by total amount spent
    top_descriptions = (
        df[df["transaction_type"] == "expense"]
        .assign(description=df["description"].str.lower())
        .groupby("description")["amount"]
        .sum()
        .sort_values(ascending=False)
        .head(20)
    )
    top_description_labels = top_descriptions.index.tolist()
    top_description_values = top_descriptions.round(2).tolist()


    return render_template(
        'dashboard.html',
        total_income=total_income,
        total_expenses=total_expenses,
        remaining_balance=remaining_balance,
        recent_transactions=recent_transactions,
        spending_by_category=spending_by_category,
        income_vs_expense=income_vs_expense,
        time_series_labels=time_series_labels,
        time_series_income=time_series_income,
        time_series_expense=time_series_expense,
        top_description_labels=top_description_labels,
        top_description_values=top_description_values,
    )