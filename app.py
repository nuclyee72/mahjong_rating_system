from flask import Flask, request, jsonify, render_template, Response, redirect, url_for
from flask_cors import CORS
import sqlite3
from datetime import datetime
import os
import io
import csv
from PIL import Image, ImageOps

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "games.db")
CLUB_NAME = "그릴마당"  # 동아리 이름 (변경 가능)

# 마작 포인트 계산용 상수
UMA_VALUES = [50, 10, -10, -30]   # 1등~4등 우마 (+오카 반영한 버전)
RETURN_SCORE = 30000




def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    # 개인전 게임 기록 (4인 마작)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            player1_name TEXT NOT NULL,
            player2_name TEXT NOT NULL,
            player3_name TEXT NOT NULL,
            player4_name TEXT NOT NULL,
            player1_score INTEGER NOT NULL,
            player2_score INTEGER NOT NULL,
            player3_score INTEGER NOT NULL,
            player4_score INTEGER NOT NULL
        )
    """)

    # 대회전 게임 기록 (개인전과 동일 스키마)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tournament_games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            player1_name TEXT NOT NULL,
            player2_name TEXT NOT NULL,
            player3_name TEXT NOT NULL,
            player4_name TEXT NOT NULL,
            player1_score INTEGER NOT NULL,
            player2_score INTEGER NOT NULL,
            player3_score INTEGER NOT NULL,
            player4_score INTEGER NOT NULL
        )
    """)


    # 뱃지 정의
    conn.execute("""
        CREATE TABLE IF NOT EXISTS badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code INTEGER UNIQUE NOT NULL,
            name TEXT NOT NULL,
            grade TEXT NOT NULL,
            description TEXT
        )
    """)

    # 플레이어별 뱃지 부여
    conn.execute("""
        CREATE TABLE IF NOT EXISTS player_badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_name TEXT NOT NULL,
            badge_code INTEGER NOT NULL,
            granted_at TEXT NOT NULL
        )
    """)

    # 시즌 아카이브
    conn.execute("""
        CREATE TABLE IF NOT EXISTS archives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS archive_games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            archive_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            player1_name TEXT NOT NULL,
            player2_name TEXT NOT NULL,
            player3_name TEXT NOT NULL,
            player4_name TEXT NOT NULL,
            player1_score INTEGER NOT NULL,
            player2_score INTEGER NOT NULL,
            player3_score INTEGER NOT NULL,
            player4_score INTEGER NOT NULL
        )
    """)

    # 팀 정의
    conn.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            color TEXT,
            created_at TEXT NOT NULL
        )
    """)

    # 기존 팀 테이블에 color 컬럼이 없으면 추가 (마이그레이션)
    try:
        conn.execute("ALTER TABLE teams ADD COLUMN color TEXT")
    except sqlite3.OperationalError:
        pass
        
    try:
        conn.execute("ALTER TABLE teams ADD COLUMN logo TEXT")
    except sqlite3.OperationalError:
        pass

    # 팀 멤버 (1:N 관계로 가정 - 한 명의 플레이어가 여러 팀에 속할지 여부는 기획에 따라 다르지만, 여기서는 자유롭게 추가 가능하게)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS team_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            player_name TEXT NOT NULL,
            joined_at TEXT NOT NULL,
            UNIQUE(team_id, player_name)
        )
    """)

    # 팀 대국 기록
    conn.execute("""
        CREATE TABLE IF NOT EXISTS team_games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            player1_team_id INTEGER,
            player1_name TEXT,
            player1_score INTEGER,
            player2_team_id INTEGER,
            player2_name TEXT,
            player2_score INTEGER,
            player3_team_id INTEGER,
            player3_name TEXT,
            player3_score INTEGER,
            player4_team_id INTEGER,
            player4_name TEXT,
            player4_score INTEGER
        )
    """)

    conn.commit()
    conn.close()


app = Flask(__name__, static_folder="static", template_folder="templates")
# 한글 등 비아스키 문자 처리를 위해
app.config['JSON_AS_ASCII'] = False
# HTML 템플릿 자동 리로드 (파일 수정 시 서버 재시작 없이 반영)
app.config['TEMPLATES_AUTO_RELOAD'] = True

@app.context_processor
def inject_club_name():
    return dict(club_name=CLUB_NAME, uma_values=UMA_VALUES, return_score=RETURN_SCORE)

CORS(app)
init_db()

# 마작 포인트 계산용 상수 (Moved to top)


# ================== 개인전 API ==================

@app.route("/api/games", methods=["GET"])
def list_games():
    conn = get_db()
    cur = conn.execute("SELECT * FROM games ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])


@app.route("/api/games", methods=["POST"])
def create_game():
    data = request.get_json() or {}

    required = [
        "player1_name", "player2_name", "player3_name", "player4_name",
        "player1_score", "player2_score", "player3_score", "player4_score",
    ]
    if not all(k in data for k in required):
        return jsonify({"error": "missing fields"}), 400

    p1 = str(data["player1_name"]).strip()
    p2 = str(data["player2_name"]).strip()
    p3 = str(data["player3_name"]).strip()
    p4 = str(data["player4_name"]).strip()
    if not (p1 and p2 and p3 and p4):
        return jsonify({"error": "all player names required"}), 400

    try:
        s1 = int(data["player1_score"])
        s2 = int(data["player2_score"])
        s3 = int(data["player3_score"])
        s4 = int(data["player4_score"])
    except (ValueError, TypeError):
        return jsonify({"error": "scores must be integers"}), 400

    # 네 명 점수 합 100000 체크
    if s1 + s2 + s3 + s4 != 100000:
        return jsonify({"error": "total score must be 100000"}), 400

    created_at = datetime.now().isoformat(timespec="minutes")

    conn = get_db()
    cur = conn.execute("""
        INSERT INTO games (
            created_at,
            player1_name, player2_name, player3_name, player4_name,
            player1_score, player2_score, player3_score, player4_score
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (created_at, p1, p2, p3, p4, s1, s2, s3, s4))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()

    return jsonify({"id": new_id}), 201


@app.route("/api/games/<int:game_id>", methods=["DELETE"])
def delete_game(game_id):
    conn = get_db()
    cur = conn.execute("DELETE FROM games WHERE id = ?", (game_id,))
    conn.commit()
    deleted = cur.rowcount
    conn.close()

    if deleted == 0:
        return jsonify({"error": "not found"}), 404
    return jsonify({"ok": True})


# ---- 개인전 CSV 내보내기 ----

@app.route("/export", methods=["GET"])
def export_games():
    conn = get_db()
    cur = conn.execute("""
        SELECT
            id, created_at,
            player1_name, player2_name, player3_name, player4_name,
            player1_score, player2_score, player3_score, player4_score
        FROM games
        ORDER BY id ASC
    """)
    rows = cur.fetchall()
    conn.close()

    def calc_pts(scores):
        order = sorted(range(4), key=lambda i: scores[i], reverse=True)

        uma_for_player = [0, 0, 0, 0]
        for rank, idx in enumerate(order):
            uma_for_player[idx] = UMA_VALUES[rank]

        pts = []
        for i in range(4):
            base = (scores[i] - RETURN_SCORE) / 1000.0
            pts.append(base + uma_for_player[i])
        return pts

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "ID", "시간",
        "P1 이름", "P1 점수", "P1 pt",
        "P2 이름", "P2 점수", "P2 pt",
        "P3 이름", "P3 점수", "P3 pt",
        "P4 이름", "P4 점수", "P4 pt",
    ])

    for row in rows:
        s1 = row["player1_score"]
        s2 = row["player2_score"]
        s3 = row["player3_score"]
        s4 = row["player4_score"]
        scores = [s1, s2, s3, s4]
        pts = calc_pts(scores)

        writer.writerow([
            row["id"],
            row["created_at"],
            row["player1_name"], s1, f"{pts[0]:.1f}",
            row["player2_name"], s2, f"{pts[1]:.1f}",
            row["player3_name"], s3, f"{pts[2]:.1f}",
            row["player4_name"], s4, f"{pts[3]:.1f}",
        ])

    csv_data = output.getvalue()
    output.close()

    csv_bytes = csv_data.encode("cp949", errors="replace")

    return Response(
        csv_bytes,
        mimetype="text/csv; charset=cp949",
        headers={
            "Content-Disposition": "attachment; filename=madang_majhong_rating.csv"
        },
    )


# ---- 개인전 CSV 업로드 ----

@app.route("/import", methods=["GET", "POST"])
def import_games():
    if request.method == "GET":
        return f"""
        <!DOCTYPE html>
        <html lang="ko">
        <head>
          <meta charset="UTF-8">
          <title>개인전 CSV 업로드 - {CLUB_NAME} 마작 레이팅</title>
          <link rel="stylesheet" href="/static/style.css">
        </head>
        <body>
          <div class="top-bar">
            <h1>{CLUB_NAME} 개인전 CSV 업로드</h1>
            <div class="view-switch">
              <a href="/" class="view-switch-btn">메인으로 돌아가기</a>
            </div>
          </div>
          <div class="main-layout">
            <div class="left-panel">
              <section class="games-panel">
                <h2>개인전 CSV 업로드</h2>
                <p class="hint-text">
                  * /export 에서 받은 CSV나<br>
                  * ID / 시간 / P1 이름 / P1 점수 / ... 형식의 파일 모두 인식합니다.
                </p>
                <form method="post" enctype="multipart/form-data">
                  <p><input type="file" name="file" accept=".csv" required></p>
                  <p><button type="submit">업로드</button></p>
                </form>
              </section>
            </div>
          </div>
        </body>
        </html>
        """

    file = request.files.get("file")
    if not file:
        return "파일이 없습니다.", 400

    raw = file.read()
    text = None
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue

    if text is None:
        return "알 수 없는 인코딩입니다. UTF-8 또는 CP949로 저장해주세요.", 400

    import io as _io
    sample = "\n".join(text.splitlines()[:5])
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
    except Exception:
        dialect = csv.excel
        dialect.delimiter = ","

    reader = csv.DictReader(_io.StringIO(text), dialect=dialect)

    def pick(row, keys, default=""):
        for k in keys:
            if k in row and row[k] not in (None, ""):
                return row[k]
        return default

    def pick_int(row, keys, default=0):
        val = pick(row, keys, None)
        if val is None or val == "":
            return default
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return default

    conn = get_db()
    inserted = 0

    for row in reader:
        created_at = pick(row, ["created_at", "시간"])
        if not created_at:
            created_at = datetime.now().isoformat(timespec="minutes")

        p1_name = pick(row, ["player1_name", "P1 이름", "P1이름"])
        p2_name = pick(row, ["player2_name", "P2 이름", "P2이름"])
        p3_name = pick(row, ["player3_name", "P3 이름", "P3이름"])
        p4_name = pick(row, ["player4_name", "P4 이름", "P4이름"])

        s1 = pick_int(row, ["player1_score", "P1 점수", "P1점수"])
        s2 = pick_int(row, ["player2_score", "P2 점수", "P2점수"])
        s3 = pick_int(row, ["player3_score", "P3 점수", "P3점수"])
        s4 = pick_int(row, ["player4_score", "P4 점수", "P4점수"])

        if not (p1_name or p2_name or p3_name or p4_name):
            continue

        conn.execute("""
            INSERT INTO games (
                created_at,
                player1_name, player2_name, player3_name, player4_name,
                player1_score, player2_score, player3_score, player4_score
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (created_at,
              p1_name, p2_name, p3_name, p4_name,
              s1, s2, s3, s4))
        inserted += 1

    conn.commit()
    conn.close()

    print(f"[IMPORT] inserted rows: {inserted}")
    return redirect(url_for("index_page"))

@app.route("/api/tournament_games", methods=["GET"])
def list_tournament_games():
    conn = get_db()
    cur = conn.execute("SELECT * FROM tournament_games ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])


@app.route("/api/tournament_games", methods=["POST"])
def create_tournament_game():
    data = request.get_json() or {}

    required = [
        "player1_name", "player2_name", "player3_name", "player4_name",
        "player1_score", "player2_score", "player3_score", "player4_score",
    ]
    if not all(k in data for k in required):
        return jsonify({"error": "missing fields"}), 400

    p1 = str(data["player1_name"]).strip()
    p2 = str(data["player2_name"]).strip()
    p3 = str(data["player3_name"]).strip()
    p4 = str(data["player4_name"]).strip()
    if not (p1 and p2 and p3 and p4):
        return jsonify({"error": "all player names required"}), 400

    try:
        s1 = int(data["player1_score"])
        s2 = int(data["player2_score"])
        s3 = int(data["player3_score"])
        s4 = int(data["player4_score"])
    except (ValueError, TypeError):
        return jsonify({"error": "scores must be integers"}), 400

    # ✅ 합 100000 서버에서도 체크
    if (s1 + s2 + s3 + s4) != 100000:
        return jsonify({"error": "total score must be 100000"}), 400

    created_at = datetime.now().isoformat(timespec="minutes")

    conn = get_db()
    cur = conn.execute("""
        INSERT INTO tournament_games (
            created_at,
            player1_name, player2_name, player3_name, player4_name,
            player1_score, player2_score, player3_score, player4_score
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (created_at, p1, p2, p3, p4, s1, s2, s3, s4))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()

    return jsonify({"id": new_id}), 201


@app.route("/api/tournament_games/<int:game_id>", methods=["DELETE"])
def delete_tournament_game(game_id):
    conn = get_db()
    cur = conn.execute("DELETE FROM tournament_games WHERE id = ?", (game_id,))
    conn.commit()
    deleted = cur.rowcount
    conn.close()
    if deleted == 0:
        return jsonify({"error": "not found"}), 404
    return jsonify({"ok": True})


# ================== 뱃지 / 관리자 API ==================

@app.route("/api/badges", methods=["GET", "POST"])
def badges_api():
    if request.method == "POST":
        data = request.get_json() or {}
        try:
            code = int(data.get("code", 0))
        except (TypeError, ValueError):
            return jsonify({"error": "code must be integer"}), 400

        name = str(data.get("name", "")).strip()
        grade = str(data.get("grade", "")).strip()
        description = str(data.get("description", "")).strip()

        if not code or not name or not grade:
            return jsonify({"error": "code, name, grade required"}), 400

        conn = get_db()
        try:
            cur = conn.execute(
                "INSERT INTO badges (code, name, grade, description) VALUES (?, ?, ?, ?)",
                (code, name, grade, description),
            )
            conn.commit()
            new_id = cur.lastrowid
        except sqlite3.IntegrityError:
            conn.close()
            return jsonify({"error": "badge code already exists"}), 400
        conn.close()
        return jsonify({"id": new_id}), 201

    # GET
    conn = get_db()
    cur = conn.execute("""
        SELECT id, code, name, grade, description
        FROM badges
        ORDER BY code ASC
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(rows)


@app.route("/api/badges/<int:badge_id>", methods=["DELETE"])
def delete_badge(badge_id):
    conn = get_db()
    cur = conn.execute("SELECT code FROM badges WHERE id = ?", (badge_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "badge not found"}), 404

    code = row["code"]

    conn.execute("DELETE FROM player_badges WHERE badge_code = ?", (code,))
    cur = conn.execute("DELETE FROM badges WHERE id = ?", (badge_id,))
    conn.commit()
    deleted = cur.rowcount
    conn.close()

    if deleted == 0:
        return jsonify({"error": "badge not found"}), 404
    return jsonify({"ok": True})

@app.route("/api/player_badges", methods=["GET", "POST"])
def player_badges_api():
    if request.method == "GET":
        conn = get_db()
        cur = conn.execute("""
            SELECT
                pb.id,
                pb.player_name,
                pb.badge_code,
                pb.granted_at,
                b.name AS badge_name,
                b.grade AS badge_grade,
                b.description AS badge_description
            FROM player_badges pb
            LEFT JOIN badges b ON pb.badge_code = b.code
            ORDER BY pb.id DESC
        """)
        rows = cur.fetchall()
        conn.close()

        return jsonify([
            {
                "id": r["id"],
                "player_name": r["player_name"],
                "badge_code": r["badge_code"],
                "code": r["badge_code"],  # 프론트 편의용(옵션)
                "granted_at": r["granted_at"],
                "name": r["badge_name"] or "",
                "grade": r["badge_grade"] or "",
                "description": r["badge_description"] or "",
            }
            for r in rows
        ])

    # ===== POST (기존 assign_badge 내용 그대로) =====
    data = request.get_json() or {}
    player_name = str(data.get("player_name", "")).strip()
    try:
        badge_code = int(data.get("badge_code", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "badge_code must be integer"}), 400

    if not (player_name and badge_code):
        return jsonify({"error": "player_name and badge_code required"}), 400

    granted_at = datetime.now().isoformat(timespec="minutes")
    conn = get_db()

    cur = conn.execute("SELECT 1 FROM badges WHERE code = ?", (badge_code,))
    if not cur.fetchone():
        conn.close()
        return jsonify({"error": "badge not found"}), 400

    conn.execute("""
        INSERT INTO player_badges (player_name, badge_code, granted_at)
        VALUES (?, ?, ?)
    """, (player_name, badge_code, granted_at))
    conn.commit()
    conn.close()
    return jsonify({"ok": True}), 201



@app.route("/api/player_badges/by_player/<player_name>", methods=["GET"])
def list_player_badges(player_name):
    name = player_name.strip()
    conn = get_db()
    cur = conn.execute("""
        SELECT
            pb.id,
            pb.player_name,
            pb.badge_code AS code,
            pb.granted_at,
            b.name,
            b.grade,
            b.description
        FROM player_badges pb
        LEFT JOIN badges b ON pb.badge_code = b.code
        WHERE pb.player_name = ?
        ORDER BY pb.granted_at ASC, pb.id ASC
    """, (name,))
    rows = cur.fetchall()
    conn.close()

    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "player_name": r["player_name"],
            "code": r["code"],
            "name": r["name"] or "",
            "grade": r["grade"] or "",
            "description": r["description"] or "",
            "granted_at": r["granted_at"],
        })
    return jsonify(result)


@app.route("/api/player_badges/<int:assign_id>", methods=["DELETE"])
def delete_player_badge(assign_id):
    conn = get_db()
    cur = conn.execute("DELETE FROM player_badges WHERE id = ?", (assign_id,))
    conn.commit()
    deleted = cur.rowcount
    conn.close()
    if deleted == 0:
        return jsonify({"error": "not found"}), 404
    return jsonify({"ok": True})




# ================== 뱃지 CSV 내보내기/업로드 ==================

@app.route("/export_badges", methods=["GET"])
def export_badges():
    conn = get_db()
    cur = conn.execute("""
        SELECT code, name, grade, description
        FROM badges
        ORDER BY code ASC
    """)
    rows = cur.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["code", "name", "grade", "description"])

    for r in rows:
        writer.writerow([r["code"], r["name"], r["grade"], r["description"] or ""])

    csv_data = output.getvalue()
    output.close()
    csv_bytes = csv_data.encode("cp949", errors="replace")

    return Response(
        csv_bytes,
        mimetype="text/csv; charset=cp949",
        headers={"Content-Disposition": "attachment; filename=badges.csv"},
    )


@app.route("/import_badges", methods=["GET", "POST"])
def import_badges():
    if request.method == "GET":
        return f"""
        <!DOCTYPE html>
        <html lang="ko">
        <head>
          <meta charset="UTF-8">
          <title>뱃지 목록 CSV 업로드 - {CLUB_NAME} 마작 레이팅</title>
          <link rel="stylesheet" href="/static/style.css">
        </head>
        <body>
          <div class="top-bar">
            <h1>{CLUB_NAME} 뱃지 목록 CSV 업로드</h1>
            <div class="view-switch">
              <a href="/" class="view-switch-btn">메인으로 돌아가기</a>
            </div>
          </div>
          <div class="main-layout">
            <div class="left-panel">
              <section class="admin-panel">
                <h2>뱃지 목록 CSV 업로드</h2>
                <p class="hint-text">
                  * 헤더 예시: code,name,grade,description<br>
                  * code는 숫자(고유)입니다.
                </p>
                <form method="post" enctype="multipart/form-data">
                  <p><input type="file" name="file" accept=".csv" required></p>
                  <p><button type="submit">업로드</button></p>
                </form>
              </section>
            </div>
          </div>
        </body>
        </html>
        """

    file = request.files.get("file")
    if not file:
        return "파일이 없습니다.", 400

    raw = file.read()
    text = None
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        return "알 수 없는 인코딩입니다. UTF-8 또는 CP949로 저장해주세요.", 400

    import io as _io
    sample = "\n".join(text.splitlines()[:5])
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
    except Exception:
        dialect = csv.excel
        dialect.delimiter = ","

    reader = csv.DictReader(_io.StringIO(text), dialect=dialect)

    def pick(row, keys, default=""):
        for k in keys:
            if k in row and row[k] not in (None, ""):
                return row[k]
        return default

    conn = get_db()
    inserted = 0
    updated = 0

    for row in reader:
        try:
            code = int(float(pick(row, ["code", "코드"], "0")))
        except Exception:
            code = 0

        name = str(pick(row, ["name", "이름"], "")).strip()
        grade = str(pick(row, ["grade", "등급"], "")).strip()
        desc = str(pick(row, ["description", "설명"], "")).strip()

        if not code or not name or not grade:
            continue

        # code 기준 업서트(있으면 update, 없으면 insert)
        try:
            conn.execute(
                "INSERT INTO badges (code, name, grade, description) VALUES (?, ?, ?, ?)",
                (code, name, grade, desc),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            conn.execute(
                "UPDATE badges SET name = ?, grade = ?, description = ? WHERE code = ?",
                (name, grade, desc, code),
            )
            updated += 1

    conn.commit()
    conn.close()

    print(f"[IMPORT_BADGES] inserted={inserted}, updated={updated}")
    return redirect(url_for("index_page"))


# ================== 플레이어 뱃지 부여 CSV 내보내기/업로드 ==================

@app.route("/export_player_badges", methods=["GET"])
def export_player_badges():
    conn = get_db()
    cur = conn.execute("""
        SELECT
          pb.player_name,
          pb.badge_code,
          pb.granted_at,
          b.name AS badge_name,
          b.grade AS badge_grade,
          b.description AS badge_description
        FROM player_badges pb
        LEFT JOIN badges b ON pb.badge_code = b.code
        ORDER BY pb.id ASC
    """)
    rows = cur.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "player_name", "badge_code", "granted_at",
        "badge_name", "badge_grade", "badge_description"
    ])

    for r in rows:
        writer.writerow([
            r["player_name"],
            r["badge_code"],
            r["granted_at"],
            r["badge_name"] or "",
            r["badge_grade"] or "",
            r["badge_description"] or "",
        ])

    csv_data = output.getvalue()
    output.close()
    csv_bytes = csv_data.encode("cp949", errors="replace")

    return Response(
        csv_bytes,
        mimetype="text/csv; charset=cp949",
        headers={"Content-Disposition": "attachment; filename=player_badges.csv"},
    )


@app.route("/import_player_badges", methods=["GET", "POST"])
def import_player_badges():
    if request.method == "GET":
        return f"""
        <!DOCTYPE html>
        <html lang="ko">
        <head>
          <meta charset="UTF-8">
          <title>{CLUB_NAME} 플레이어 뱃지 부여 CSV 업로드</title>
          <link rel="stylesheet" href="/static/style.css">
        </head>
        <body>
          <div class="top-bar">
            <h1>{CLUB_NAME} 플레이어 뱃지 부여 CSV 업로드</h1>
            <div class="view-switch">
              <a href="/" class="view-switch-btn">메인으로 돌아가기</a>
            </div>
          </div>
          <div class="main-layout">
            <div class="left-panel">
              <section class="admin-panel">
                <h2>플레이어 뱃지 부여 CSV 업로드</h2>
                <p class="hint-text">
                  * 헤더 예시: player_name,badge_code,granted_at<br>
                  * granted_at이 비어있으면 업로드 시각으로 저장됩니다.
                </p>
                <form method="post" enctype="multipart/form-data">
                  <p><input type="file" name="file" accept=".csv" required></p>
                  <p><button type="submit">업로드</button></p>
                </form>
              </section>
            </div>
          </div>
        </body>
        </html>
        """

    file = request.files.get("file")
    if not file:
        return "파일이 없습니다.", 400

    raw = file.read()
    text = None
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        return "알 수 없는 인코딩입니다. UTF-8 또는 CP949로 저장해주세요.", 400

    import io as _io
    sample = "\n".join(text.splitlines()[:5])
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
    except Exception:
        dialect = csv.excel
        dialect.delimiter = ","

    reader = csv.DictReader(_io.StringIO(text), dialect=dialect)

    def pick(row, keys, default=""):
        for k in keys:
            if k in row and row[k] not in (None, ""):
                return row[k]
        return default

    conn = get_db()
    inserted = 0
    skipped = 0

    for row in reader:
        player_name = str(pick(row, ["player_name", "플레이어", "이름"], "")).strip()
        try:
            badge_code = int(float(pick(row, ["badge_code", "code", "뱃지코드", "뱃지 코드"], "0")))
        except Exception:
            badge_code = 0

        granted_at = str(pick(row, ["granted_at", "부여시각", "시간"], "")).strip()
        if not granted_at:
            granted_at = datetime.now().isoformat(timespec="minutes")

        if not player_name or not badge_code:
            skipped += 1
            continue

        # 중복 방지(완전 동일 row면 skip)
        cur = conn.execute("""
            SELECT 1 FROM player_badges
            WHERE player_name = ? AND badge_code = ? AND granted_at = ?
            LIMIT 1
        """, (player_name, badge_code, granted_at))
        if cur.fetchone():
            skipped += 1
            continue

        conn.execute("""
            INSERT INTO player_badges (player_name, badge_code, granted_at)
            VALUES (?, ?, ?)
        """, (player_name, badge_code, granted_at))
        inserted += 1

    conn.commit()
    conn.close()

    print(f"[IMPORT_PLAYER_BADGES] inserted={inserted}, skipped={skipped}")
    return redirect(url_for("index_page"))


# ================== 아카이브 API ==================

@app.route("/api/archives", methods=["GET"])
def archives_api():
    conn = get_db()
    cur = conn.execute(
        """
        SELECT
            a.id,
            a.name,
            a.created_at,
            COUNT(ag.id) AS game_count
        FROM archives a
        LEFT JOIN archive_games ag ON ag.archive_id = a.id
        GROUP BY a.id, a.name, a.created_at
        ORDER BY a.id DESC
        """
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(rows)


@app.route("/api/archives/<int:archive_id>/games", methods=["GET"])
def archive_games_api(archive_id):
    conn = get_db()
    cur = conn.execute(
        """
        SELECT
            id,
            created_at,
            player1_name, player2_name, player3_name, player4_name,
            player1_score, player2_score, player3_score, player4_score
        FROM archive_games
        WHERE archive_id = ?
        ORDER BY id ASC
        """,
        (archive_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(rows)


@app.route("/api/archives/<int:archive_id>", methods=["DELETE"])
def delete_archive(archive_id):
    conn = get_db()
    conn.execute("DELETE FROM archive_games WHERE archive_id = ?", (archive_id,))
    cur = conn.execute("DELETE FROM archives WHERE id = ?", (archive_id,))
    conn.commit()
    deleted = cur.rowcount
    conn.close()
    if deleted == 0:
        return jsonify({"error": "archive not found"}), 404
    return jsonify({"ok": True})

@app.route("/admin/archive_import", methods=["POST"])
def admin_archive_import():
    archive_name = (request.form.get("archive_name") or "").strip()
    file = request.files.get("file")

    if not archive_name:
        return "아카이브 이름이 필요합니다.", 400
    if not file:
        return "CSV 파일이 필요합니다.", 400

    raw = file.read()
    text = None
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        return "알 수 없는 인코딩입니다. UTF-8 또는 CP949로 저장해주세요.", 400

    # CSV 파싱
    sample = "\n".join(text.splitlines()[:5])
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
    except Exception:
        dialect = csv.excel
        dialect.delimiter = ","

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)

    def pick(row, keys, default=""):
        for k in keys:
            if k in row and row[k] not in (None, ""):
                return row[k]
        return default

    def pick_int(row, keys, default=0):
        val = pick(row, keys, None)
        if val is None or val == "":
            return default
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return default

    conn = get_db()
    created_at = datetime.now().isoformat(timespec="minutes")

    # archives 테이블에 먼저 등록
    cur = conn.execute(
        "INSERT INTO archives (name, created_at) VALUES (?, ?)",
        (archive_name, created_at),
    )
    archive_id = cur.lastrowid

    inserted = 0
    for row in reader:
        # 시간
        game_time = pick(row, ["created_at", "시간"])
        if not game_time:
            game_time = created_at

        # 이름
        p1_name = pick(row, ["player1_name", "P1 이름", "P1이름"])
        p2_name = pick(row, ["player2_name", "P2 이름", "P2이름"])
        p3_name = pick(row, ["player3_name", "P3 이름", "P3이름"])
        p4_name = pick(row, ["player4_name", "P4 이름", "P4이름"])

        # 점수
        s1 = pick_int(row, ["player1_score", "P1 점수", "P1점수"])
        s2 = pick_int(row, ["player2_score", "P2 점수", "P2점수"])
        s3 = pick_int(row, ["player3_score", "P3 점수", "P3점수"])
        s4 = pick_int(row, ["player4_score", "P4 점수", "P4점수"])

        # 네 명 이름이 다 비어 있으면 스킵
        if not (p1_name or p2_name or p3_name or p4_name):
            continue

        conn.execute(
            """
            INSERT INTO archive_games (
                archive_id,
                created_at,
                player1_name, player2_name, player3_name, player4_name,
                player1_score, player2_score, player3_score, player4_score
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                archive_id,
                game_time,
                p1_name, p2_name, p3_name, p4_name,
                s1, s2, s3, s4,
            ),
        )
        inserted += 1

    if inserted == 0:
        # 유효 데이터가 하나도 없으면 아카이브도 되돌리기
        conn.execute("DELETE FROM archive_games WHERE archive_id = ?", (archive_id,))
        conn.execute("DELETE FROM archives WHERE id = ?", (archive_id,))
        conn.commit()
        conn.close()
        return "CSV에서 읽을 수 있는 대국 기록이 없습니다.", 400

    conn.commit()
    conn.close()

    # 다시 메인 화면으로
    return redirect(url_for("index_page"))

# ---- 대회전 CSV 내보내기 ----

@app.route("/export_tournament", methods=["GET"])
def export_tournament_games():
    conn = get_db()
    cur = conn.execute("""
        SELECT
            id, created_at,
            player1_name, player2_name, player3_name, player4_name,
            player1_score, player2_score, player3_score, player4_score
        FROM tournament_games
        ORDER BY id ASC
    """)
    rows = cur.fetchall()
    conn.close()

    def calc_pts(scores):
        order = sorted(range(4), key=lambda i: scores[i], reverse=True)

        uma_for_player = [0, 0, 0, 0]
        for rank, idx in enumerate(order):
            uma_for_player[idx] = UMA_VALUES[rank]

        pts = []
        for i in range(4):
            base = (scores[i] - RETURN_SCORE) / 1000.0
            pts.append(base + uma_for_player[i])
        return pts

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "ID", "시간",
        "P1 이름", "P1 점수", "P1 pt",
        "P2 이름", "P2 점수", "P2 pt",
        "P3 이름", "P3 점수", "P3 pt",
        "P4 이름", "P4 점수", "P4 pt",
    ])

    for row in rows:
        scores = [
            row["player1_score"],
            row["player2_score"],
            row["player3_score"],
            row["player4_score"],
        ]
        pts = calc_pts(scores)

        writer.writerow([
            row["id"],
            row["created_at"],
            row["player1_name"], scores[0], f"{pts[0]:.1f}",
            row["player2_name"], scores[1], f"{pts[1]:.1f}",
            row["player3_name"], scores[2], f"{pts[2]:.1f}",
            row["player4_name"], scores[3], f"{pts[3]:.1f}",
        ])

    csv_data = output.getvalue()
    output.close()

    csv_bytes = csv_data.encode("cp949", errors="replace")

    return Response(
        csv_bytes,
        mimetype="text/csv; charset=cp949",
        headers={
            "Content-Disposition": "attachment; filename=madang_mahjong_tournament.csv"
        },
    )


# ---- 대회전 CSV 업로드 ----

@app.route("/import_tournament", methods=["GET", "POST"])
def import_tournament_games():
    if request.method == "GET":
        return f"""
        <!DOCTYPE html>
        <html lang="ko">
        <head>
          <meta charset="UTF-8">
          <title>{CLUB_NAME} 대회전 CSV 업로드</title>
          <link rel="stylesheet" href="/static/style.css">
        </head>
        <body>
          <div class="top-bar">
            <h1>{CLUB_NAME} 대회전 CSV 업로드</h1>
            <div class="view-switch">
              <a href="/" class="view-switch-btn">메인으로 돌아가기</a>
            </div>
          </div>
          <div class="main-layout">
            <div class="left-panel">
              <section class="games-panel">
                <h2>대회전 CSV 업로드</h2>
                <p class="hint-text">
                  * /export_tournament 에서 받은 CSV나<br>
                  * ID / 시간 / P1 이름 / P1 점수 / ... 형식의 파일 모두 인식합니다.
                </p>
                <form method="post" enctype="multipart/form-data">
                  <p><input type="file" name="file" accept=".csv" required></p>
                  <p><button type="submit">업로드</button></p>
                </form>
              </section>
            </div>
          </div>
        </body>
        </html>
        """

    file = request.files.get("file")
    if not file:
        return "파일이 없습니다.", 400

    raw = file.read()
    text = None
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue

    if text is None:
        return "알 수 없는 인코딩입니다. UTF-8 또는 CP949로 저장해주세요.", 400

    import io as _io
    sample = "\n".join(text.splitlines()[:5])
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
    except Exception:
        dialect = csv.excel
        dialect.delimiter = ","

    reader = csv.DictReader(_io.StringIO(text), dialect=dialect)

    def pick(row, keys, default=""):
        for k in keys:
            if k in row and row[k] not in (None, ""):
                return row[k]
        return default

    def pick_int(row, keys, default=0):
        val = pick(row, keys, None)
        if val is None or val == "":
            return default
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return default

    conn = get_db()
    inserted = 0

    for row in reader:
        created_at = pick(row, ["created_at", "시간"])
        if not created_at:
            created_at = datetime.now().isoformat(timespec="minutes")

        p1_name = pick(row, ["player1_name", "P1 이름", "P1이름"])
        p2_name = pick(row, ["player2_name", "P2 이름", "P2이름"])
        p3_name = pick(row, ["player3_name", "P3 이름", "P3이름"])
        p4_name = pick(row, ["player4_name", "P4 이름", "P4이름"])

        s1 = pick_int(row, ["player1_score", "P1 점수", "P1점수"])
        s2 = pick_int(row, ["player2_score", "P2 점수", "P2점수"])
        s3 = pick_int(row, ["player3_score", "P3 점수", "P3점수"])
        s4 = pick_int(row, ["player4_score", "P4 점수", "P4점수"])

        if not (p1_name or p2_name or p3_name or p4_name):
            continue

        conn.execute("""
            INSERT INTO tournament_games (
                created_at,
                player1_name, player2_name, player3_name, player4_name,
                player1_score, player2_score, player3_score, player4_score
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (created_at,
              p1_name, p2_name, p3_name, p4_name,
              s1, s2, s3, s4))
        inserted += 1

    conn.commit()
    conn.close()

    print(f"[IMPORT_TOURNAMENT] inserted rows: {inserted}")
    return redirect(url_for("index_page"))

# ================== 개인전 기록 초기화(시즌 리셋) ==================

@app.route("/api/admin/reset_games", methods=["POST"])
def reset_games():
    """
    모든 개인전 대국 기록을 삭제하고 ID도 다시 1부터 시작하도록 초기화합니다.
    (badges / player_badges / archive 등은 건드리지 않음)
    """
    conn = get_db()
    try:
        # games 테이블 전체 삭제
        conn.execute("DELETE FROM games")

        # SQLite AUTOINCREMENT 리셋 (선택사항이지만, 시즌별로 ID 깔끔하게 보이게 하려고)
        try:
            conn.execute("DELETE FROM sqlite_sequence WHERE name = 'games'")
        except Exception:
            # sqlite_sequence가 없는 경우도 있으니 무시
            pass

        conn.commit()
    finally:
        conn.close()

    return jsonify({"ok": True})

@app.route("/api/admin/reset_tournament", methods=["POST"])
def reset_tournament():
    """
    모든 대회 대국 기록을 삭제하고 ID도 다시 1부터 시작하도록 초기화합니다.
    (badges / player_badges / archive 등은 건드리지 않음)
    """
    conn = get_db()
    try:
        # tournament_games 테이블 전체 삭제
        conn.execute("DELETE FROM tournament_games")

        # SQLite AUTOINCREMENT 리셋
        try:
            conn.execute("DELETE FROM sqlite_sequence WHERE name = 'tournament_games'")
        except Exception:
            pass

        conn.commit()
    finally:
        conn.close()

    return jsonify({"ok": True})

# ================== 팀전 API ==================

@app.route("/api/teams", methods=["GET"])
def list_teams():
    conn = get_db()
    # 팀 목록 가져오기
    cur = conn.execute("SELECT * FROM teams ORDER BY name ASC")
    teams = [dict(row) for row in cur.fetchall()]
    
    # 각 팀의 멤버 가져오기
    for t in teams:
        cur_m = conn.execute("SELECT id, player_name, joined_at FROM team_members WHERE team_id = ?", (t["id"],))
        t["members"] = [dict(row) for row in cur_m.fetchall()]
        
    conn.close()
    return jsonify(teams)


@app.route("/api/teams", methods=["POST"])
def create_team():
    data = request.get_json() or {}
    name = str(data.get("name", "")).strip()
    color = str(data.get("color", "")).strip()  # 색상 추가

    if not name:
        return jsonify({"error": "team name required"}), 400
        
    conn = get_db()
    created_at = datetime.now().isoformat(timespec="minutes")
    try:
        cur = conn.execute("INSERT INTO teams (name, color, created_at) VALUES (?, ?, ?)", (name, color, created_at))
        conn.commit()
        new_id = cur.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "team name already exists"}), 400
    conn.close()
    return jsonify({"id": new_id}), 201


@app.route("/api/teams/<int:team_id>", methods=["DELETE"])
def delete_team(team_id):
    conn = get_db()
    # 로고 파일이 있다면 삭제
    cur = conn.execute("SELECT logo FROM teams WHERE id = ?", (team_id,))
    row = cur.fetchone()
    if row and row["logo"]:
        logo_path = os.path.join(BASE_DIR, row["logo"].lstrip("/"))
        if os.path.exists(logo_path):
            try:
                os.remove(logo_path)
            except OSError:
                pass
                
    # 멤버도 삭제
    conn.execute("DELETE FROM team_members WHERE team_id = ?", (team_id,))
    # 팀 삭제
    cur = conn.execute("DELETE FROM teams WHERE id = ?", (team_id,))
    conn.commit()
    deleted = cur.rowcount
    conn.close()
    
    if deleted == 0:
        return jsonify({"error": "team not found"}), 404
    return jsonify({"ok": True})


@app.route("/api/teams/<int:team_id>", methods=["PUT"])
def update_team(team_id):
    data = request.get_json() or {}
    color = data.get("color")
    
    if color is None:
        return jsonify({"error": "color is required"}), 400
        
    conn = get_db()
    cur = conn.execute("UPDATE teams SET color = ? WHERE id = ?", (str(color).strip(), team_id))
    conn.commit()
    updated = cur.rowcount
    conn.close()
    
    if updated == 0:
        return jsonify({"error": "team not found"}), 404
        
    return jsonify({"ok": True})


@app.route("/api/teams/<int:team_id>/logo", methods=["POST"])
def upload_team_logo(team_id):
    if "logo" not in request.files:
        return jsonify({"error": "No logo file provided"}), 400
        
    file = request.files["logo"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400
        
    try:
        # Open the image using Pillow
        img = Image.open(file)
        
        # Convert image to RGBA if not already to support transparency
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
            
        # Safely extract square center crop and resize identically without float interpolations
        img = ImageOps.fit(img, (500, 500), method=Image.Resampling.LANCZOS)
        
        # Ensure directory exists
        logos_dir = os.path.join(BASE_DIR, "static", "logos")
        os.makedirs(logos_dir, exist_ok=True)
        
        # Save image as PNG to preserve transparency
        filename = f"team_{team_id}.png"
        filepath = os.path.join(logos_dir, filename)
        img.save(filepath, "PNG")

        # Update database
        logo_url = f"/static/logos/{filename}"
        conn = get_db()
        cur = conn.execute("UPDATE teams SET logo = ? WHERE id = ?", (logo_url, team_id))
        conn.commit()
        
        if cur.rowcount == 0:
            conn.close()
            # Clean up the file if team doesn't exist
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({"error": "Team not found"}), 404
            
        conn.close()
        return jsonify({"ok": True, "logo": logo_url})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/teams/<int:team_id>/members", methods=["POST"])
def add_team_member(team_id):
    data = request.get_json() or {}
    player_name = str(data.get("player_name", "")).strip()
    if not player_name:
        return jsonify({"error": "player name required"}), 400
        
    created_at = datetime.now().isoformat(timespec="minutes")
    conn = get_db()
    try:
        conn.execute("INSERT INTO team_members (team_id, player_name, joined_at) VALUES (?, ?, ?)", 
                     (team_id, player_name, created_at))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "already joined"}), 400
    conn.close()
    return jsonify({"ok": True}), 201


@app.route("/api/team_members/<int:member_id>", methods=["DELETE"])
def delete_team_member(member_id):
    conn = get_db()
    cur = conn.execute("DELETE FROM team_members WHERE id = ?", (member_id,))
    conn.commit()
    deleted = cur.rowcount
    conn.close()
    
    if deleted == 0:
        return jsonify({"error": "member not found"}), 404
    return jsonify({"ok": True})


@app.route("/api/team_games", methods=["GET"])
def list_team_games():
    conn = get_db()
    
    # 조인을 통해 팀 이름을 가져옴
    query = """
        SELECT 
            g.*,
            t1.name as player1_team_name,
            t2.name as player2_team_name,
            t3.name as player3_team_name,
            t4.name as player4_team_name
        FROM team_games g
        LEFT JOIN teams t1 ON g.player1_team_id = t1.id
        LEFT JOIN teams t2 ON g.player2_team_id = t2.id
        LEFT JOIN teams t3 ON g.player3_team_id = t3.id
        LEFT JOIN teams t4 ON g.player4_team_id = t4.id
        ORDER BY g.id DESC
    """
    cur = conn.execute(query)
    rows = cur.fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])


@app.route("/api/team_games", methods=["POST"])
def create_team_game():
    data = request.get_json() or {}
    
    # data format expectation:
    # { 
    #   player1: { team_id: 1, name: "foo", score: 25000 },
    #   player2: { ... }, ...
    # }
    
    try:
        p1 = data["player1"]
        p2 = data["player2"]
        p3 = data["player3"]
        p4 = data["player4"]
        
        s1 = int(p1["score"])
        s2 = int(p2["score"])
        s3 = int(p3["score"])
        s4 = int(p4["score"])
        
        if (s1 + s2 + s3 + s4) != 100000:
            return jsonify({"error": "total score must be 100000"}), 400
            
        created_at = datetime.now().isoformat(timespec="minutes")
        
        conn = get_db()
        conn.execute("""
            INSERT INTO team_games (
                created_at,
                player1_team_id, player1_name, player1_score,
                player2_team_id, player2_name, player2_score,
                player3_team_id, player3_name, player3_score,
                player4_team_id, player4_name, player4_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            created_at,
            p1["team_id"], p1["name"], s1,
            p2["team_id"], p2["name"], s2,
            p3["team_id"], p3["name"], s3,
            p4["team_id"], p4["name"], s4
        ))
        conn.commit()
        conn.close()
        
        return jsonify({"ok": True}), 201
        
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/team_games/<int:game_id>", methods=["DELETE"])
def delete_team_game(game_id):
    conn = get_db()
    cur = conn.execute("DELETE FROM team_games WHERE id = ?", (game_id,))
    conn.commit()
    deleted = cur.rowcount
    conn.close()
    
    if deleted == 0:
        return jsonify({"error": "game not found"}), 404
    return jsonify({"ok": True})


@app.route("/api/team_ranking", methods=["GET"])
def team_ranking():
    conn = get_db()
    
    # 1. 모든 팀 게임 가져오기
    query = """
        SELECT 
            g.*,
            t1.name as player1_team_name,
            t2.name as player2_team_name,
            t3.name as player3_team_name,
            t4.name as player4_team_name
        FROM team_games g
        LEFT JOIN teams t1 ON g.player1_team_id = t1.id
        LEFT JOIN teams t2 ON g.player2_team_id = t2.id
        LEFT JOIN teams t3 ON g.player3_team_id = t3.id
        LEFT JOIN teams t4 ON g.player4_team_id = t4.id
    """
    cur = conn.execute(query)
    games = [dict(row) for row in cur.fetchall()]
    conn.close()
    
    # 2. 팀별 통계 집계
    team_stats = {}  # team_name -> { games, total_pt, rank_counts: [0,0,0,0] }
    
    def calc_pts(scores):
        # 복제
        order = sorted(range(4), key=lambda i: scores[i], reverse=True)
        # 우마
        uma_vals = UMA_VALUES # Global config
        uma_applied = [0]*4
        for r, idx in enumerate(order):
            uma_applied[idx] = uma_vals[r]
            
        final_pts = []
        for i in range(4):
            # (점수 - 반환점) / 1000 + 우마
            pt = (scores[i] - RETURN_SCORE) / 1000.0 + uma_applied[i]
            final_pts.append(pt)
        return final_pts, order # pts array, and order (list of indices sorted by score desc)

    for g in games:
        scores = [g["player1_score"], g["player2_score"], g["player3_score"], g["player4_score"]]
        team_names = [g["player1_team_name"], g["player2_team_name"], g["player3_team_name"], g["player4_team_name"]]
        
        # 이름이 없는 경우(삭제된 팀 등) 무시하거나 별도 처리? 일단 이름 있으면 집계
        
        pts, order = calc_pts(scores)
        
        # 순위(1~4) 구하기
        # order: [idx_1st, idx_2nd, idx_3rd, idx_4th]
        ranks = [0]*4
        for rank_idx, original_idx in enumerate(order):
            ranks[original_idx] = rank_idx + 1
            
        for i in range(4):
            tname = team_names[i]
            if not tname: continue
            
            if tname not in team_stats:
                team_stats[tname] = { "games": 0, "total_pt": 0.0, "rank_counts": [0,0,0,0] }
            
            team_stats[tname]["games"] += 1
            team_stats[tname]["total_pt"] += pts[i]
            team_stats[tname]["rank_counts"][ranks[i]-1] += 1

    # 3. 리스트 변환 및 정렬 (총 pt 내림차순)
    results = []
    for name, st in team_stats.items():
        avg = st["total_pt"] / st["games"] if st["games"] > 0 else 0
        results.append({
            "name": name,
            "games": st["games"],
            "total_pt": round(st["total_pt"], 1),
            "avg_pt": round(avg, 1),
            "rank_counts": st["rank_counts"]
        })
        
    results.sort(key=lambda x: x["total_pt"], reverse=True)
    
    return jsonify(results)


# ================== 기본 페이지 ==================

@app.route("/")
def index_page():
    return render_template("index.html", club_name=CLUB_NAME)


if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
