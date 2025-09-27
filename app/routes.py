from flask import Blueprint, jsonify, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from flask import request
from sqlalchemy import func
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

    query = db.session.query(Transaction).filter(Transaction.account_id.in_(account_ids))
    # Convert to DataFrame
    df = pd.read_sql(query.statement, db.session.bind)


    total_income = db.session.query(db.func.sum(Transaction.amount)).filter(
        Transaction.transaction_type == 'income',
        Transaction.account_id.in_(account_ids)
    ).scalar() or 0
    total_income = round(total_income, 2)


    total_expenses = db.session.query(db.func.sum(Transaction.amount)).filter(
        Transaction.transaction_type == 'expense',
        Transaction.account_id.in_(account_ids)
    ).scalar() or 0
    total_expenses = round(total_expenses, 2)

    total_balance = db.session.query(db.func.sum(Account.balance)).filter(
        Account.user_id == current_user.user_id
    ).scalar() or 0
    total_balance = round(total_balance, 2)

    remaining_balance = round(total_balance + total_income - total_expenses, 2)

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
    spending_by_category = defaultdict(float)
    transactions = db.session.query(Transaction.amount, Category.name).join(
        Category, Transaction.category_id == Category.category_id
    ).filter(
        Transaction.transaction_type == 'expense',
        Transaction.account_id.in_(account_ids)
    ).all()

    for amount, category_name in transactions:
        spending_by_category[category_name] += amount
    spending_by_category = list(spending_by_category.items())

    income_vs_expense = {
        'income': round(total_income, 2),
        'expense': round(total_expenses, 2)
    }

    # Time Series Chart (last 30 days)
    today = datetime.today().date()
    dates = [today - timedelta(days=i) for i in range(29, -1, -1)]
    time_series_labels = [d.strftime('%Y-%m-%d') for d in dates]
    time_series_income = []
    time_series_expense = []

    for d in dates:
        income = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.transaction_type == 'income',
            Transaction.account_id.in_(account_ids),
            func.date(Transaction.transaction_date) == d
        ).scalar() or 0
        expense = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.transaction_type == 'expense',
            Transaction.account_id.in_(account_ids),
            func.date(Transaction.transaction_date) == d
        ).scalar() or 0
        time_series_income.append(round(income, 2))
        time_series_expense.append(round(expense, 2))

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

    stacked_area_datasets = [
        {
            'label': category,
            'data': values,
            'backgroundColor': '#'+format(hash(category) % 0xFFFFFF, '06x'),
            'fill': True
        }
        for category, values in stacked_area_data.items()
    ]


    # Waterfall Chart (simplified cash flow)
    waterfall_labels = ['Income', 'Rent', 'Groceries', 'Transport', 'Savings']
    waterfall_values = [
        round(total_income, 2),
        -800,  # Replace with actual category totals if needed
        -300,
        -150,
        -500
    ]

    # Heatmap Matrix (daily spending intensity)
    heatmap_matrix = []
    for d in dates:
        expense = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.transaction_type == 'expense',
            Transaction.account_id.in_(account_ids),
            func.date(Transaction.transaction_date) == d
        ).scalar() or 0
        heatmap_matrix.append({
            'x': d.strftime('%Y-%m-%d'),
            'y': 'Spending',
            'v': round(expense, 2)
        })

    # Donut Chart (category drilldown)
    donut_labels = [cat for cat, _ in spending_by_category]
    donut_values = [round(val, 2) for _, val in spending_by_category]


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
        stacked_area_labels=stacked_area_labels,
        stacked_area_datasets=stacked_area_datasets,
        waterfall_labels=waterfall_labels,
        waterfall_values=waterfall_values,
        heatmap_matrix=heatmap_matrix,
        donut_labels=donut_labels,
        donut_values=donut_values
    )
