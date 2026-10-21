from flask import Flask, render_template, request, redirect, flash
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = "repair_system_2026"

# 初始化数据库
def init_db():
    conn = sqlite3.connect("repair.db")
    cur = conn.cursor()
    # 用户表
    cur.execute('''CREATE TABLE IF NOT EXISTS user
    (id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT,
    role TEXT)''')
    # 工单表（字段顺序固定）
    cur.execute('''CREATE TABLE IF NOT EXISTS work_order
    (id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT,
    location TEXT,
    level TEXT,
    worker_id INTEGER,
    status TEXT DEFAULT '待处理',
    create_time TEXT)''')
    # 维修人员表
    cur.execute('''CREATE TABLE IF NOT EXISTS worker
    (id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    skill TEXT,
    task_count INTEGER DEFAULT 0)''')

    # 预置测试账号（不重复插入）
    cur.execute("INSERT OR IGNORE INTO user(username,password,role) VALUES (?,?,?)",("stu1","123","student"))
    cur.execute("INSERT OR IGNORE INTO user(username,password,role) VALUES (?,?,?)",("work1","123","worker"))
    cur.execute("INSERT OR IGNORE INTO user(username,password,role) VALUES (?,?,?)",("admin1","123","admin"))
    # 预置维修员
    cur.execute("INSERT OR IGNORE INTO worker(name,skill,task_count) VALUES (?,?,?)",("维修员A","水电",0))
    cur.execute("INSERT OR IGNORE INTO worker(name,skill,task_count) VALUES (?,?,?)",("维修员B","门窗",0))
    conn.commit()
    conn.close()

# 自动派单（分配给当前任务最少的维修员）
def auto_assign():
    conn = sqlite3.connect("repair.db")
    cur = conn.cursor()
    cur.execute("SELECT id FROM worker ORDER BY task_count ASC LIMIT 1")
    res = cur.fetchone()
    conn.close()
    return res[0]

# 登录页
@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        uname = request.form["username"]
        pwd = request.form["password"]
        conn = sqlite3.connect("repair.db")
        cur = conn.cursor()
        cur.execute("SELECT role FROM user WHERE username=? AND password=?", (uname, pwd))
        row = cur.fetchone()
        conn.close()
        if row:
            role = row[0]
            if role == "student":
                return redirect("/student")
            elif role == "worker":
                return redirect("/worker")
            else:
                return redirect("/admin")
        else:
            flash("账号或密码错误")
    return render_template("login.html")

# 兼容所有页面的 /login 返回跳转
@app.route("/login")
def back_to_login():
    return redirect("/")

# 学生报修页面
@app.route("/student", methods=["GET","POST"])
def student_page():
    if request.method == "POST":
        loc = request.form["place"]
        cont = request.form["desc"]
        lv = request.form["level"]
        wid = auto_assign()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect("repair.db")
        cur = conn.cursor()
        cur.execute("INSERT INTO work_order(location,content,level,worker_id,create_time) VALUES (?,?,?,?,?)",
                    (loc, cont, lv, wid, now))
        cur.execute("UPDATE worker SET task_count = task_count + 1 WHERE id=?", (wid,))
        conn.commit()
        conn.close()
        flash("报修提交成功，系统已自动分配维修人员！")
    return render_template("student.html")

# 维修人员页面
@app.route("/worker", methods=["GET","POST"])
def worker_page():
    conn = sqlite3.connect("repair.db")
    cur = conn.cursor()
    if request.method == "POST":
        oid = request.form["oid"]
        cur.execute("UPDATE work_order SET status='已完成' WHERE id=?", (oid,))
        conn.commit()
        flash("工单已成功标记为完成！")
    cur.execute("SELECT * FROM work_order ORDER BY create_time DESC")
    orders = cur.fetchall()
    conn.close()
    return render_template("worker.html", orders=orders)

# 管理员页面
@app.route("/admin")
def admin_page():
    conn = sqlite3.connect("repair.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM work_order ORDER BY create_time DESC")
    orders = cur.fetchall()
    conn.close()
    return render_template("admin.html", orders=orders)

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
