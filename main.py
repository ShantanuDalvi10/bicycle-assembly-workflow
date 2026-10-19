import os
from flask import Flask,render_template,redirect,url_for,flash,request
from flask_login import (
    UserMixin, login_user, LoginManager,
    current_user, logout_user, login_required, login_manager
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
load_dotenv()


app = Flask(__name__)

app.config["SECRET_KEY"] = "development-secret-key"
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL", "sqlite:///bicycle.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

class User(UserMixin,db.Model):
    __tablename__="user"

    id = db.Column(db.Integer,primary_key=True)
    username = db.Column(db.String(100),unique=True,nullable=False)
    email = db.Column(db.String(150),unique=True,nullable=False)
    password = db.Column(db.String(256),nullable=False)

class Bicycle(db.Model):
    __tablename__="bicycle"

    id = db.Column(db.Integer,primary_key=True)
    name = db.Column(db.String(100),nullable=False)
    status = db.Column(db.String(20),default="In Progress")
    user_id = db.Column(db.Integer,db.ForeignKey("user.id"),nullable=False)

class BicyclePart(db.Model):
    __tablename__="bicycle_part"

    id = db.Column(db.Integer,primary_key=True)
    name = db.Column(db.String(20),nullable=False)
    quantity = db.Column(db.Integer,default=1)
    stage = db.Column(db.String(20),default="Procurement")
    bicycle_id = db.Column(db.Integer,db.ForeignKey("bicycle.id"),nullable=False)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User,int(user_id))

with app.app_context():
    db.create_all()

@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/register",methods=["GEt","POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username","").strip()
        email = request.form.get("email","").strip()
        password = request.form.get("password","")

        if not username or not email or not password :
            flash("Please fill all the fields")
            return redirect(url_for("register"))

        user = db.session.execute(
            db.select(User).filter(
                (User.username == username) | (User.email == email)
            )
        ).scalar_one_or_none()

        if user:
            flash("User already exists.")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)

        new_user = User(
            username=username,
            email=email,
            password=hashed_password
        )

        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        return redirect(url_for("dashboard"))
    return render_template("register.html")

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip()
        password = request.form.get("password","")

        user = db.session.execute(
            db.select(User).filter_by(email=email)
        ).scalar_one_or_none()

        if user and check_password_hash(user.password,password):
            login_user(user)
            return redirect(url_for("dashboard"))

        flash("Incorrect email or password")

    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/dashboard",methods=["GET","POST"])
@login_required
def dashboard():
    if request.method == "POST":
        name = request.form.get("name","").strip()

        if not name:
            flash("Please enter bicycle name.")
            return redirect(url_for("dashboard"))

        new_bicycle = Bicycle(
            name=name,
            status="In Progress",
            user_id=current_user.id
        )
        db.session.add(new_bicycle)
        db.session.flush()

        for part_name in ["Body","Wheel","Handle"]:
            new_part = BicyclePart(
                name=part_name,
                quantity=1,
                stage="Procurement",
                bicycle_id=new_bicycle.id
            )
            db.session.add(new_part)

        db.session.commit()
        flash("Bicycle created successfully.")
        return redirect(url_for("dashboard"))

    bicycles = db.session.execute(
        db.select(Bicycle).filter_by(user_id=current_user.id)
    ).scalars().all()

    return render_template("dashboard.html",bicycles=bicycles)

@app.route("/bicycle/<int:bicycle_id>",methods=["GET","POST"])
@login_required
def bicycle_details(bicycle_id):
    bicycle = db.session.get(Bicycle,bicycle_id)

    if bicycle is None or bicycle.user_id != current_user.id:
        return "Bicycle Not Found",404

    if request.method == "POST":
        part_id = request.form.get("part_id",type=int)
        part = db.session.get(BicyclePart,part_id)

        if part is None or part.bicycle_id != bicycle.id:
            return "Part Not Found",404

        if part.stage == "Procurement":
            part.stage = "Assembly"
        elif part.stage == "Assembly":
            part.stage = "Done"

        parts = db.session.execute(
            db.select(BicyclePart).filter_by(bicycle_id=bicycle.id)
        ).scalars().all()

        if len(parts) == 3 and all(i.stage=="Done" for i in parts):
            bicycle.status = "Done"
        else:
            bicycle.status = "In Progress"

        db.session.commit()

        return redirect(url_for("bicycle_details",bicycle_id=bicycle.id))

    parts = db.session.execute(
        db.select(BicyclePart).filter_by(bicycle_id=bicycle.id)
    ).scalars().all()

    return render_template("bicycle_details.html",
                           bicycle=bicycle,
                           parts=parts)

if __name__ == "__main__":
    app.run(debug=True)