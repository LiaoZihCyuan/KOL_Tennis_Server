from flask import Blueprint, render_template, redirect, url_for

page_bp = Blueprint("page_bp", __name__)


@page_bp.route("/")
def index_page():
    return redirect(url_for("page_bp.calendar_page"))


@page_bp.route("/calendar")
def calendar_page():
    return render_template("calendar.html")


@page_bp.route("/add_user")
def add_user_page():
    return render_template("add_user.html")


@page_bp.route("/users")
def user_list_page():
    return render_template("user_list.html")


@page_bp.route("/coaches/stats")
def coach_stats_page():
    return render_template("coach_stats.html")


@page_bp.route("/students/stats")
def student_stats_page():
    return render_template("student_stats.html")


@page_bp.route("/templates")
def templates_manage_page():
    return render_template("templates_manage.html")


@page_bp.route("/renewals/manage")
def renewals_manage_page():
    return render_template("renewals_manage.html")


@page_bp.route("/student/portal")
def student_portal_page():
    return render_template("student_portal.html")


@page_bp.route("/login")
def login_page():
    return render_template("login.html")