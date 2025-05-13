from flask import Flask, render_template, request, redirect, session, url_for, flash
import psycopg2
import os
from shapely import wkt
from shapely.geometry import Point, Polygon, MultiPolygon
from geoalchemy2.shape import from_shape
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from dotenv import load_dotenv
import logging
import dj_database_url

load_dotenv()

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "12345678")
UPLOAD_FOLDER = 'uploads/shapefiles'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

DATABASE_URL = os.environ.get('DATABASE_URL')
DB_CONFIG = dj_database_url.config(default=DATABASE_URL)

@app.before_request
def log_request():
    logging.info(f"Request: {request.method} {request.url}")

@app.after_request
def log_response(response):
    logging.info(f"Response: {response.status_code} for {request.url}")
    return response

def get_db_conn():
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        logging.info("Database connection successful.")
        return conn
    except psycopg2.Error as e:
        logging.error(f"Error connecting to database: {e}")
        flash(f"Gagal terhubung ke database: {e}", "danger")
        return None

def close_db_connection(conn):
    if conn:
        conn.close()
        logging.info("Database connection closed.")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Anda harus login untuk mengakses halaman ini.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/', methods=['GET', 'POST'])
def index():
    logging.info("Mengakses rute /")
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    logging.info("Mengakses rute /login")
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_conn()
        if conn:
            cur = conn.cursor()
            cur.execute("SELECT id, password FROM users WHERE username = %s", (username,))
            user = cur.fetchone()
            cur.close()
            close_db_connection(conn)

            if user and check_password_hash(user[1], password):
                session['user_id'] = user[0]
                session['username'] = username
                logging.info(f"Login berhasil, redirect ke dashboard. User: {username}")
                return redirect(url_for('dashboard'))
            else:
                flash("Login gagal. Cek username dan password.", "danger")
                logging.warning(f"Login gagal untuk user: {username}")
        # get_db_conn sudah flash error jika gagal
        logging.info("Rendering login.html")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    logging.info("Mengakses rute /register")
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_pw = generate_password_hash(password)

        conn = get_db_conn()
        if conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            existing = cur.fetchone()

            if existing:
                flash("Username sudah terdaftar.", "danger")
                logging.warning(f"Username {username} sudah terdaftar.")
            else:
                try:
                    cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_pw))
                    conn.commit()
                    flash("Registrasi berhasil. Silakan login.", "success")
                    logging.info(f"Registrasi berhasil untuk user: {username}")
                    cur.close()
                    close_db_connection(conn)
                    return redirect(url_for('login'))
                except psycopg2.Error as e:
                    conn.rollback()
                    flash(f"Kesalahan database saat registrasi: {e}", "danger")
                    logging.error(f"Kesalahan database saat registrasi: {e}")
            cur.close()
            close_db_connection(conn)
        # get_db_conn sudah flash error jika gagal

    logging.info("Rendering register.html")
    return render_template('register.html')

@app.route('/logout')
def logout():
    logging.info("Mengakses rute /logout")
    session.clear()
    logging.info("Sesi di clear, redirect ke /login")
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    logging.info("Mengakses rute /dashboard")
    if 'user_id' not in session:
        logging.info("User tidak login, redirect ke /login")
        return redirect(url_for('login'))

    conn = get_db_conn()
    if conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM petani WHERE user_id = %s LIMIT 1", (session['user_id'],))
        petani_data = cur.fetchone()
        cur.close()
        close_db_connection(conn)
        logging.info(f"Rendering dashboard.html untuk user: {session['username']}")
        return render_template('dashboard.html', username=session['username'], petani_data=petani_data)
    else:
        # get_db_conn sudah flash error jika gagal
        return render_template('dashboard.html', username=session['username'], petani_data=None)

@app.route('/form_petani', methods=['GET', 'POST'])
@login_required
def form_petani():
    logging.info("Mengakses rute /form_petani")
    if request.method == 'POST':
        nama = request.form['nama']
        nik = request.form['nik']
        tanggal_lahir = request.form['tanggal_lahir']
        no_telpon = request.form['no_telpon']
        alamat = request.form['alamat']
        lat = request.form['latitude']
        lon = request.form['longitude']
        lahan_geom_wkt = request.form.get('lahan_geom')
        luas_lahan = request.form.get('luas_lahan', 0.0)

        try:
            luas_lahan = float(luas_lahan)
        except ValueError:
            flash("Luas lahan tidak valid.", "danger")
            logging.warning("Luas lahan tidak valid")
            return render_template('add_petani.html')

        if not lahan_geom_wkt or not lahan_geom_wkt.strip().upper().startswith('POLYGON'):
            flash("Geometri lahan tidak valid atau kosong.", "danger")
            logging.warning("Geometri lahan tidak valid atau kosong")
            return render_template('add_petani.html')

        # Konversi geometri
        try:
            lokasi_point = f"SRID=4326;POINT({lon} {lat})"
            polygon = wkt.loads(lahan_geom_wkt)
            if isinstance(polygon, Polygon):
                polygon = MultiPolygon([polygon])
            multipolygon_wkt = polygon.wkt
        except Exception as e:
            flash(f"Kesalahan saat memproses geometri: {e}", "danger")
            logging.error(f"Kesalahan saat memproses geometri: {e}")
            return render_template('add_petani.html')

        conn = get_db_conn()
        if conn is None:
            # get_db_conn sudah flash error jika gagal
            return render_template('add_petani.html')

        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO petani (user_id, nama, nik, tanggal_lahir, no_telpon, alamat,
                                    lokasi_point, lahan_geom, luas_lahan)
                VALUES (%s, %s, %s, %s, %s, %s,
                        ST_GeomFromText(%s, 4326),
                        ST_GeomFromText(%s, 4326), %s)
            """, (
                session['user_id'], nama, nik, tanggal_lahir, no_telpon, alamat,
                lokasi_point, multipolygon_wkt, luas_lahan
            ))
            conn.commit()
            flash("Data petani berhasil disimpan!", "success")
            logging.info("Data petani berhasil disimpan!")
            cur.execute("SELECT id FROM petani WHERE nik = %s", (nik,))
            petani_id = cur.fetchone()[0]
            cur.close()
            close_db_connection(conn)
            return redirect(url_for('edit_petani', id=petani_id))
        except psycopg2.Error as e:
            conn.rollback()
            flash(f"Kesalahan database: {e}", "danger")
            logging.error(f"Kesalahan database saat menyimpan petani: {e}")
        finally:
            if cur:
                cur.close()
            close_db_connection(conn)

    logging.info("Rendering add_petani.html")
    return render_template('add_petani.html')

@app.route('/isi_komoditas', methods=['GET', 'POST'])
@login_required
def isi_komoditas():
    logging.info("Mengakses rute /isi_komoditas")
    conn = get_db_conn()
    if not conn:
        # get_db_conn sudah flash error jika gagal
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        petani_id = request.form['petani_id']
        nama_komoditas = request.form['nama_komoditas']
        luas_lahan = request.form['luas_lahan']
        tanggal_tanam = request.form['tanggal_tanam']

        cur = None
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO komoditas (petani_id, nama_komoditas, luas_lahan, tanggal_tanam)
                VALUES (%s, %s, %s, %s)
            """, (petani_id, nama_komoditas, luas_lahan, tanggal_tanam))
            conn.commit()
            flash("Data komoditas berhasil disimpan", "success")
            logging.info("Data komoditas berhasil disimpan")
            return redirect(url_for('dashboard'))
        except Exception as e:
            conn.rollback()
            flash(f"Gagal menyimpan data komoditas: {e}", "danger")
            logging.error(f"Gagal menyimpan data komoditas: {e}")
        finally:
            if cur:
                cur.close()
            close_db_connection(conn)

    cur = None
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, nama FROM petani")
        petani_list = cur.fetchall()
        logging.info("Rendering isi_komoditas.html")
        return render_template('isi_komoditas.html', petani_list=petani_list)
    finally:
        if cur:
            cur.close()
        close_db_connection(conn)

@app.route('/isi_hasil_panen', methods=['GET', 'POST'])
@login_required
def isi_hasil_panen():
    logging.info("Mengakses rute /isi_hasil_panen")
    conn = get_db_conn()
    if not conn:
        # get_db_conn sudah flash error jika gagal
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        petani_id = request.form['petani_id']
        nama_komoditas = request.form['nama_komoditas']
        jumlah = request.form['jumlah']
        tanggal_panen = request.form['tanggal_panen']

        cur = None
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO hasil_panen (petani_id, nama_komoditas, jumlah, tanggal_panen)
                VALUES (%s, %s, %s, %s)
            """, (petani_id, nama_komoditas, jumlah, tanggal_panen))
            conn.commit()
            flash("Data hasil panen berhasil disimpan", "success")
            logging.info("Data hasil panen berhasil disimpan")
            return redirect(url_for('dashboard'))
        except Exception as e:
            conn.rollback()
            flash(f"Gagal menyimpan data hasil panen: {e}", "danger")
            logging.error(f"Gagal menyimpan data hasil panen: {e}")
        finally:
            if cur:
                cur.close()
            close_db_connection(conn)

    cur = None
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, nama FROM petani")
        petani_list = cur.fetchall()
        logging.info("Rendering isi_hasil_panen.html")
        return render_template('isi_hasil_panen.html', petani_list=petani_list)
    finally:
        if cur:
            cur.close()
        close_db_connection(conn)

@app.route("/riwayat_petani")
@login_required
def riwayat_petani():
    logging.info("Mengakses rute /riwayat_petani")
    user_id = session.get('user_id')
    conn = get_db_conn()
    if conn:
        cur = conn.cursor()
        cur.execute("SELECT id, nama, nik, tanggal_lahir, no_telpon, alamat, luas_lahan FROM petani WHERE user_id = %s", (user_id,))
        data = cur.fetchall()
        cur.close()
        close_db_connection(conn)
        logging.info("Rendering riwayat_petani.html")
        return render_template("riwayat_petani.html", petani=data)
    else:
        # get_db_conn sudah flash error jika gagal
        return redirect(url_for('dashboard'))

@app.route("/edit_petani/<int:id>", methods=["GET", "POST"])
@login_required
def edit_petani(id):
    logging.info(f"Mengakses rute /edit_petani/{id}")
    conn = get_db_conn()
    if conn:
        cur = conn.cursor()
        if request.method == "POST":
            nama = request.form['nama']
            nik = request.form['nik']
            no_telpon = request.form['no_telpon']
            alamat = request.form['alamat']
            try:
                cur.execute("UPDATE petani SET nama=%s, nik=%s, no_telpon=%s, alamat=%s WHERE id=%s",
                            (nama, nik, no_telpon, alamat, id))
                conn.commit()
                flash("Data berhasil diperbarui", "success")
                logging.info("Data berhasil diperbarui")
                cur.close()
                close_db_connection(conn)
                return redirect(url_for("riwayat_petani"))
            except psycopg2.Error as e:
                conn.rollback()
                flash(f"Kesalahan database saat memperbarui: {e}", "danger")
                logging.error(f"Kesalahan database saat memperbarui: {e}")
            finally:
                if cur:
                    cur.close()
                close_db_connection(conn)
        else:
            cur.execute("SELECT nama, nik, no_telpon, alamat, ST_AsText(lahan_geom) as lahan_geom FROM petani WHERE id = %s", (id,))
            petani = cur.fetchone()
            if petani:
                cur.close()
                close_db_connection(conn)
                logging.info("Rendering edit_petani.html")
                return render_template("edit_petani.html", petani=petani, id=id)
            else:
                flash("Data petani tidak ditemukan.", "danger")
                logging.warning("Data petani tidak ditemukan.")
                cur.close()
                close_db_connection(conn)
                return redirect(url_for("riwayat_petani"))
    else:
        # get_db_conn sudah flash error jika gagal
        return redirect(url_for('riwayat_petani'))

@app.route("/hapus_petani/<int:id>")
@login_required
def hapus_petani(id):
    logging.info(f"Mengakses rute /hapus_petani/{id}")
    conn = get_db_conn()
    if conn:
        cur = conn.cursor()