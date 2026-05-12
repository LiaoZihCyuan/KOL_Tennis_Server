from flask import Blueprint, render_template

page_bp = Blueprint("page_bp", __name__)

@page_bp.route("/calendar")
def calendar_page():
    return render_template("calendar.html")

@page_bp.route("/add_user")
def add_user_page():
    return render_template("add_user.html")

@page_bp.route("/users")
def user_list_page():
    return render_template("user_list.html")