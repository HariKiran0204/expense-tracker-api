"""
Seed script — populates the DB with sample users and transactions.
Usage: python seed.py
"""
from datetime import date, timedelta
import random
from app import create_app, db, bcrypt
from app.models import User, Category, Transaction

app = create_app()

SAMPLE_USERS = [
    {"name": "Alice Kumar", "email": "alice@example.com", "password": "password123"},
    {"name": "Bob Singh",   "email": "bob@example.com",   "password": "password123"},
]

TRANSACTION_NOTES = [
    "Weekly groceries", "Uber to office", "Netflix subscription",
    "Electricity bill", "Gym membership", "Coffee and snacks",
    "Flight tickets", "Dinner with friends", "Freelance payment",
    "Amazon purchase", "Doctor visit", "Book purchase",
]


def seed():
    with app.app_context():
        db.create_all()

        default_cats = Category.query.filter_by(is_default=True).all()
        if not default_cats:
            print("No default categories found. Run the app once to seed defaults.")
            return

        for u_data in SAMPLE_USERS:
            existing = User.query.filter_by(email=u_data["email"]).first()
            if existing:
                print(f"User {u_data['email']} already exists, skipping.")
                continue

            user = User(
                name=u_data["name"],
                email=u_data["email"],
                password_hash=bcrypt.generate_password_hash(u_data["password"]).decode("utf-8"),
            )
            db.session.add(user)
            db.session.flush()

            # Custom category per user
            custom_cat = Category(name="Pets", is_default=False, user_id=user.id)
            db.session.add(custom_cat)
            db.session.flush()

            accessible_cats = default_cats + [custom_cat]

            # Generate 60 random transactions over last 6 months
            for _ in range(60):
                days_ago = random.randint(0, 180)
                txn_date = date.today() - timedelta(days=days_ago)
                txn_type = random.choice(["expense", "expense", "expense", "income"])
                amount = round(random.uniform(10, 5000), 2) if txn_type == "income" else round(random.uniform(5, 800), 2)
                cat = random.choice(accessible_cats)
                note = random.choice(TRANSACTION_NOTES) if random.random() > 0.3 else None

                db.session.add(Transaction(
                    user_id=user.id,
                    category_id=cat.id,
                    type=txn_type,
                    amount=amount,
                    date=txn_date,
                    note=note,
                ))

            print(f"Seeded user: {u_data['email']} with 60 transactions.")

        db.session.commit()
        print("Seeding complete.")


if __name__ == "__main__":
    seed()
