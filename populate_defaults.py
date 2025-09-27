from app import creat_app, db
from app.models import Category, Subcategory

def preload_categories():
    default_categories = {
        "Food and Drink": ["Restaurants", "Bars", "Groceries", "Other"],
        "Transportation": ["Bus", "Train", "Car", "Other", "Hotels"],
        "Entertainment": ["Events", "Subscriptions", "Other"],
        "Shopping": ["Clothes", "Electronics", "Other"],
        "Bills": ["Utilities", "Internet", "HouseRent", "Other"],
        "Health": ["Fitness", "Doctor", "Other"],
        "Finances": ["Fees", "Investments", "Other"],
        "Other": ["Other"],
        "Income": ["Salary", "Business", "Other"]
    }

    for category_name, subcategories in default_categories.items():
        category = Category(name=category_name)
        db.session.add(category)
        db.session.commit()

        for subcategory_name in subcategories:
            subcategory = Subcategory(name=subcategory_name, category_id=category.category_id)
            db.session.add(subcategory)
        db.session.commit()

if __name__ == "__main__":
    app = creat_app()  # Initialize your Flask app
    with app.app_context():  # Activate the application context
        preload_categories()
        print("Default categories and subcategories loaded.")
