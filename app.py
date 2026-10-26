from flask import Flask, render_template, request, redirect, flash, session
import sqlite3
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = "repair_system_2026"

DB = "repair.db"

# 工单状态常量（五级闭环流转 + 驳回）
STATUS_PENDING = "待接单"      # 学生已提交，待管理员审核接单
STATUS_ASSIGNED = "维修中"     # 管理员已派单，维修人员处理中
STATUS_FINISHED = "维修完成"   # 维修人员已完结，待学生评价
STATUS_EVALUATED = "评价结束"  # 学生已评价，工单归档
STATUS_REJECTED = "已驳回"     # 管理员审核不通过

FAULT_TYPES = ["水电故障", "门窗故障", "家具损坏", "网络故障", "卫浴故障", "其他故障"]


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


# 初始化数据库
def init_db():
    conn = get_db()
    cur = conn.cursor()
    # 用户表（学生/管理员/维修人员，维修人员关联 worker 档案）
    cur.execute('''CREATE TABLE IF NOT EXISTS user
    (id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT,
    role TEXT,
    name TEXT,
    worker_id INTEGER)''')
    # 维修人员档案表
    cur.execute('''CREATE TABLE IF NOT EXISTS worker
    (id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    skill TEXT,
    task_count INTEGER DEFAULT 0)''')
    # 工单表（报修、派单、维修、评价全流程数据留存）
    cur.execute('''CREATE TABLE IF NOT EXISTS work_order
    (id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_no TEXT UNIQUE,
    student_id INTEGER,
    building TEXT,
    floor TEXT,
    room TEXT,
    fault_type TEXT,
    description TEXT,
    status TEXT DEFAULT '待接单',
    worker_id INTEGER,
    create_time TEXT,
    assign_time TEXT,
    finish_time TEXT,
    repair_method TEXT,
    repair_content TEXT,
    materials TEXT,
    repair_result TEXT,
    rating INTEGER,
    evaluate_text TEXT,
    evaluate_time TEXT)''')

    # 预置维修人员档案
    cur.execute("INSERT OR IGNORE INTO worker(id,name,skill,task_count) VALUES (1,'张师傅','水电故障',0)")
    cur.execute("INSERT OR IGNORE INTO worker(id,name,skill,task_count) VALUES (2,'李师傅','门窗家具',0)")
    cur.execute("INSERT OR IGNORE INTO worker(id,name,skill,task_count) VALUES (3,'王师傅','网络卫浴',0)")
    # 预置测试账号
    cur.execute("INSERT OR IGNORE INTO user(username,password,role,name) VALUES ('stu1','123','student','张同学')")
    cur.execute("INSERT OR IGNORE INTO user(username,password,role,name) VALUES ('stu2','123','student','李同学')")
    cur.execute("INSERT OR IGNORE INTO user(username,password,role,name) VALUES ('admin1','123','admin','宿管管理员')")
    cur.execute("INSERT OR IGNORE INTO user(username,password,role,name,worker_id) VALUES ('work1','123','worker','张师傅',1)")
    cur.execute("INSERT OR IGNORE INTO user(username,password,role,name,worker_id) VALUES ('work2','123','worker','李师傅',2)")
    cur.execute("INSERT OR IGNORE INTO user(username,password,role,name,worker_id) VALUES ('work3','123','worker','王师傅',3)")
    conn.commit()
    conn.close()


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# 生成唯一工单编号：WO + 日期时间 + 随机后缀
def gen_order_no():
    return "WO" + datetime.now().strftime("%Y%m%d%H%M%S%f")[:17]


# 角色权限校验装饰器：未登录或角色不符一律跳回登录页
def role_required(role):
    def deco(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if session.get("role") != role:
                flash("请先以对应身份登录")
                return redirect("/")
            return f(*args, **kwargs)
        return wrapper
    return deco


# ========== 登录 / 注销 ==========
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        uname = request.form.get("username", "").strip()
        pwd = request.form.get("password", "").strip()
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM user WHERE username=? AND password=?", (uname, pwd))
        row = cur.fetchone()
        conn.close()
        if row:
            session["uid"] = row["id"]
            session["role"] = row["role"]
            session["name"] = row["name"]
            session["worker_id"] = row["worker_id"]
            if row["role"] == "student":
                return redirect("/student")
            elif row["role"] == "worker":
                return redirect("/worker")
            else:
                return redirect("/admin")
        else:
            flash("账号或密码错误")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# 兼容旧链接
@app.route("/login")
def back_to_login():
    return redirect("/")


# ========== 学生端 ==========
@app.route("/student")
@role_required("student")
def student_page():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''SELECT w.*, k.name AS worker_name FROM work_order w
                   LEFT JOIN worker k ON w.worker_id = k.id
                   WHERE w.student_id=? ORDER BY w.create_time DESC''', (session["uid"],))
    orders = cur.fetchall()
    conn.close()
    return render_template("student.html", orders=orders, fault_types=FAULT_TYPES,
                           name=session["name"])


@app.route("/student/submit", methods=["POST"])
@role_required("student")
def student_submit():
    building = request.form.get("building", "").strip()
    floor = request.form.get("floor", "").strip()
    room = request.form.get("room", "").strip()
    fault_type = request.form.get("fault_type", "").strip()
    desc = request.form.get("desc", "").strip()
    if not (building and floor and room and fault_type and desc):
        flash("请完整填写楼栋、楼层、宿舍号、故障类型与故障描述")
        return redirect("/student")
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''INSERT INTO work_order(order_no,student_id,building,floor,room,
                   fault_type,description,status,create_time)
                   VALUES (?,?,?,?,?,?,?,?,?)''',
                (gen_order_no(), session["uid"], building, floor, room,
                 fault_type, desc, STATUS_PENDING, now_str()))
    conn.commit()
    conn.close()
    flash("报修提交成功，工单已录入，等待管理员审核接单！")
    return redirect("/student")


@app.route("/student/evaluate/<int:oid>", methods=["POST"])
@role_required("student")
def student_evaluate(oid):
    rating = request.form.get("rating", "").strip()
    text = request.form.get("evaluate_text", "").strip()
    if rating not in ("1", "2", "3", "4", "5"):
        flash("请选择星级评分")
        return redirect("/student")
    conn = get_db()
    cur = conn.cursor()
    # 仅允许评价本人名下、状态为"维修完成"的工单
    cur.execute('''UPDATE work_order SET rating=?, evaluate_text=?, evaluate_time=?,
                   status=? WHERE id=? AND student_id=? AND status=?''',
                (int(rating), text, now_str(), STATUS_EVALUATED,
                 oid, session["uid"], STATUS_FINISHED))
    if cur.rowcount == 0:
        flash("评价失败：工单不存在或当前状态不可评价")
    else:
        flash("评价成功，本次报修流程已闭环归档！")
    conn.commit()
    conn.close()
    return redirect("/student")


# ========== 管理员端 ==========
@app.route("/admin")
@role_required("admin")
def admin_page():
    # 多条件检索：时间区间、宿舍楼栋、故障类别、维修人员、工单状态
    f_building = request.args.get("building", "").strip()
    f_type = request.args.get("fault_type", "").strip()
    f_status = request.args.get("status", "").strip()
    f_worker = request.args.get("worker", "").strip()
    f_start = request.args.get("start", "").strip()
    f_end = request.args.get("end", "").strip()

    sql = '''SELECT w.*, k.name AS worker_name, u.name AS student_name
             FROM work_order w
             LEFT JOIN worker k ON w.worker_id = k.id
             LEFT JOIN user u ON w.student_id = u.id WHERE 1=1'''
    params = []
    if f_building:
        sql += " AND w.building=?"
        params.append(f_building)
    if f_type:
        sql += " AND w.fault_type=?"
        params.append(f_type)
    if f_status:
        sql += " AND w.status=?"
        params.append(f_status)
    if f_worker:
        sql += " AND w.worker_id=?"
        params.append(f_worker)
    if f_start:
        sql += " AND w.create_time>=?"
        params.append(f_start + " 00:00:00")
    if f_end:
        sql += " AND w.create_time<=?"
        params.append(f_end + " 23:59:59")
    sql += " ORDER BY w.create_time DESC"

    conn = get_db()
    cur = conn.cursor()
    cur.execute(sql, params)
    orders = cur.fetchall()
    cur.execute("SELECT * FROM worker ORDER BY id")
    workers = cur.fetchall()
    cur.execute("SELECT DISTINCT building FROM work_order ORDER BY building")
    buildings = [r[0] for r in cur.fetchall()]
    # 状态统计总览
    cur.execute("SELECT status, COUNT(*) FROM work_order GROUP BY status")
    stat = {r[0]: r[1] for r in cur.fetchall()}
    conn.close()
    return render_template("admin.html", orders=orders, workers=workers,
                           buildings=buildings, fault_types=FAULT_TYPES, stat=stat,
                           filters={"building": f_building, "fault_type": f_type,
                                    "status": f_status, "worker": f_worker,
                                    "start": f_start, "end": f_end},
                           statuses=[STATUS_PENDING, STATUS_ASSIGNED, STATUS_FINISHED,
                                     STATUS_EVALUATED, STATUS_REJECTED])


@app.route("/admin/review/<int:oid>", methods=["POST"])
@role_required("admin")
def admin_review(oid):
    """工单审核：通过（进入派单）或驳回"""
    action = request.form.get("action")
    conn = get_db()
    cur = conn.cursor()
    if action == "reject":
        cur.execute("UPDATE work_order SET status=? WHERE id=? AND status=?",
                    (STATUS_REJECTED, oid, STATUS_PENDING))
        flash("该工单已驳回")
    conn.commit()
    conn.close()
    return redirect("/admin")


@app.route("/admin/assign/<int:oid>", methods=["POST"])
@role_required("admin")
def admin_assign(oid):
    """派单：将工单分配给指定维修人员，状态流转为维修中"""
    worker_id = request.form.get("worker_id")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM worker WHERE id=?", (worker_id,))
    if not cur.fetchone():
        flash("维修人员不存在")
        conn.close()
        return redirect("/admin")
    cur.execute('''UPDATE work_order SET worker_id=?, status=?, assign_time=?
                   WHERE id=? AND status=?''',
                (worker_id, STATUS_ASSIGNED, now_str(), oid, STATUS_PENDING))
    if cur.rowcount == 0:
        flash("派单失败：工单不存在或已处理")
    else:
        cur.execute("UPDATE worker SET task_count = task_count + 1 WHERE id=?", (worker_id,))
        flash("派单成功，工单已进入维修阶段！")
    conn.commit()
    conn.close()
    return redirect("/admin")


# ========== 维修人员端 ==========
@app.route("/worker")
@role_required("worker")
def worker_page():
    conn = get_db()
    cur = conn.cursor()
    # 仅显示指派给本人的工单，权责隔离
    cur.execute('''SELECT w.*, u.name AS student_name FROM work_order w
                   LEFT JOIN user u ON w.student_id = u.id
                   WHERE w.worker_id=? ORDER BY
                   CASE w.status WHEN '维修中' THEN 0 ELSE 1 END, w.assign_time DESC''',
                (session["worker_id"],))
    orders = cur.fetchall()
    conn.close()
    return render_template("worker.html", orders=orders, name=session["name"])


@app.route("/worker/finish/<int:oid>", methods=["POST"])
@role_required("worker")
def worker_finish(oid):
    """维修登记并完结工单：维修方式、维修内容、耗材情况、处理结果"""
    method = request.form.get("method", "").strip()
    content = request.form.get("content", "").strip()
    materials = request.form.get("materials", "").strip()
    result = request.form.get("result", "").strip()
    if not (method and content and result):
        flash("请完整填写维修方式、维修内容与处理结果")
        return redirect("/worker")
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''UPDATE work_order SET repair_method=?, repair_content=?,
                   materials=?, repair_result=?, finish_time=?, status=?
                   WHERE id=? AND worker_id=? AND status=?''',
                (method, content, materials, result, now_str(), STATUS_FINISHED,
                 oid, session["worker_id"], STATUS_ASSIGNED))
    if cur.rowcount == 0:
        flash("操作失败：工单不存在或不属于当前可处理状态")
    else:
        cur.execute("UPDATE worker SET task_count = MAX(task_count - 1, 0) WHERE id=?",
                    (session["worker_id"],))
        flash("维修登记完成，工单已完结，等待学生评价！")
    conn.commit()
    conn.close()
    return redirect("/worker")


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
