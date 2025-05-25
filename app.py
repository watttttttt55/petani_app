from flask import Flask, render_template, request, redirect, session, url_for, flash
import psycopg2
import os
from urllib.parse import urlparse
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from dotenv import load_dotenv
import logging

load_dotenv()

app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY")
if not app.secret_key:
    app.secret_key = "super_secret_dev_key_ganti_ini_di_prod"
    app.logger.warning("SECRET_KEY not set in environment. Using a default development key. CHANGE THIS FOR PRODUCTION!")

UPLOAD_FOLDER = 'uploads/shapefiles'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
app.logger.setLevel(logging.DEBUG)

def get_db_conn():
    conn = None
    try:
        database_url = os.environ.get('DATABASE_URL')

        if database_url:
            url = urlparse(database_url)

            db_port_val = url.port
            if db_port_val is None:
                db_port = 5432
            else:
                db_port = db_port_val

            conn = psycopg2.connect(
                host=url.hostname,
                port=db_port,
                database=url.path[1:],
                user=url.username,
                password=url.password
            )
        else:
            try:
                from config import DB_CONFIG
                db_config_copy = DB_CONFIG.copy()
                if 'port' in db_config_copy and isinstance(db_config_copy['port'], str):
                    try:
                        db_config_copy['port'] = int(db_config_copy['port'])
                    except ValueError:
                        db_config_copy['port'] = 5432

                conn = psycopg2.connect(**db_config_copy)
            except ImportError as e:
                app.logger.error(f"config.py not found or DB_CONFIG not defined: {e}", exc_info=True)
                flash("Database connection failed: Configuration missing.", "danger")
            except KeyError as ke:
                app.logger.error(f"DB_CONFIG incomplete: Missing key {ke}", exc_info=True)
                flash(f"Database connection failed: Incomplete DB_CONFIG ({ke}).", "danger")
            except Exception as e:
                app.logger.error(f"Error connecting via DB_CONFIG: {e}", exc_info=True)
                flash("Database connection failed: Error with DB_CONFIG.", "danger")

    except psycopg2.Error as e:
        app.logger.error(f"PostgreSQL connection error: {e}", exc_info=True)
        flash(f"Database connection failed: {e}", "danger")
    except Exception as e:
        app.logger.error(f"An unexpected error occurred during database connection: {e}", exc_info=True)
        flash(f"Database connection failed: An unexpected error occurred.", "danger")

    return conn

def close_db_connection(conn):
    if conn:
        conn.close()

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
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_conn()
        if conn:
            cur = None
            try:
                cur = conn.cursor()
                cur.execute("SELECT id, password FROM users WHERE username = %s", (username,))
                user = cur.fetchone()

                if user and check_password_hash(user[1], password):
                    session['user_id'] = user[0]
                    session['username'] = username
                    if cur: cur.close()
                    close_db_connection(conn)
                    return redirect(url_for('dashboard'))
                else:
                    flash("Login gagal. Cek username dan password.", "danger")
            except psycopg2.Error as e:
                flash("Terjadi kesalahan database saat login. Silakan coba lagi.", "danger")
            finally:
                if cur:
                    cur.close()
                close_db_connection(conn)
        else:
            flash("Gagal terhubung ke database saat login. Cek konfigurasi database Anda.", "danger")

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_pw = generate_password_hash(password)

        conn = get_db_conn()
        if conn:
            cur = None
            try:
                cur = conn.cursor()
                cur.execute("SELECT id FROM users WHERE username = %s", (username,))
                existing = cur.fetchone()
                if existing:
                    flash("Username sudah terdaftar.", "danger")
                else:
                    cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_pw))
                    conn.commit()
                    flash("Registrasi berhasil. Silakan login.", "success")
                    return redirect(url_for('login'))
            except psycopg2.Error as e:
                conn.rollback()
                flash("Terjadi kesalahan database saat registrasi. Silakan coba lagi.", "danger")
            finally:
                if cur:
                    cur.close()
                close_db_connection(conn)
        else:
            flash("Gagal terhubung ke database saat register. Cek konfigurasi database Anda.", "danger")

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_conn()
    if conn:
        cur = None
        petani_data = None
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM petani WHERE user_id = %s LIMIT 1", (session['user_id'],))
            petani_data = cur.fetchone()
        except psycopg2.Error as e:
            flash("Terjadi kesalahan database saat mengambil data petani.", "danger")
        finally:
            if cur:
                cur.close()
            close_db_connection(conn)
        return render_template('dashboard.html', username=session.get('username'), petani_data=petani_data)
    else:
        flash("Gagal terhubung ke database saat memuat dashboard. Cek konfigurasi database Anda.", "danger")
        return render_template('dashboard.html', username=session.get('username'), petani_data=None)

@app.route('/form_petani', methods=['GET', 'POST'])
@login_required
def form_petani():
    if request.method == 'POST':
        nama = request.form['nama']
        nik = request.form['nik']
        tanggal_lahir = request.form['tanggal_lahir']
        no_telpon = request.form['no_telpon']
        alamat = request.form['alamat']
        lat = request.form['latitude']
        lon = request.form['longitude']
        lahan_geom_wkt = request.form.get('lahan_geom')
        luas_lahan_str = request.form.get('luas_lahan', '0.0')

        try:
            luas_lahan = float(luas_lahan_str)
        except ValueError:
            flash("Luas lahan tidak valid.", "danger")
            return render_template('add_petani.html')

        if not lahan_geom_wkt or not lahan_geom_wkt.strip().upper().startswith('POLYGON'):
            flash("Geometri lahan tidak valid atau kosong. Harap gambar poligon lahan Anda.", "danger")
            return render_template('add_petani.html')

        lokasi_point = f"SRID=4326;POINT({lon} {lat})"

        conn = get_db_conn()
        if conn is None:
            flash('Gagal terhubung ke database. Cek konfigurasi database Anda.', 'danger')
            return render_template('add_petani.html')

        cur = None
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO petani (user_id, nama, nik, tanggal_lahir, no_telpon, alamat,
                                    lokasi_point, lahan_geom, luas_lahan)
                VALUES (%s, %s, %s, %s, %s, %s,
                        ST_GeomFromText(%s, 4326),
                        ST_GeomFromText(%s, 4326), %s)
            """, (
                session['user_id'], nama, nik, tanggal_lahir, no_telpon, alamat,
                lokasi_point, lahan_geom_wkt, luas_lahan
            ))
            conn.commit()
            flash("Data petani berhasil disimpan!", "success")
            return redirect(url_for('dashboard'))
        except psycopg2.Error as e:
            conn.rollback()
            flash(f"Kesalahan database saat menyimpan data petani: {e}", "danger")
        finally:
            if cur:
                cur.close()
            close_db_connection(conn)

    return render_template('add_petani.html')

@app.route('/isi_komoditas', methods=['GET', 'POST'])
@login_required
def isi_komoditas():
    conn = get_db_conn()
    if not conn:
        flash("Gagal koneksi ke database. Cek konfigurasi database Anda.", "danger")
        return redirect(url_for('dashboard'))

    cur = None
    petani_list = []
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, nama FROM petani WHERE user_id = %s", (session['user_id'],))
        petani_list = cur.fetchall()
    except psycopg2.Error as e:
        flash("Terjadi kesalahan database saat mengambil daftar petani.", "danger")
    finally:
        if cur:
            cur.close()
        close_db_connection(conn)

    if request.method == 'POST':
        petani_id = request.form['petani_id']
        nama_komoditas = request.form['nama_komoditas']
        luas_lahan = request.form['luas_lahan']
        tanggal_tanam = request.form['tanggal_tanam']

        conn_post = get_db_conn()
        if conn_post:
            cur_post = None
            try:
                cur_post = conn_post.cursor()
                cur_post.execute("""
                    INSERT INTO komoditas (petani_id, nama_komoditas, luas_lahan, tanggal_tanam)
                    VALUES (%s, %s, %s, %s)
                """, (petani_id, nama_komoditas, luas_lahan, tanggal_tanam))
                conn_post.commit()
                flash("Data komoditas berhasil disimpan", "success")
                return redirect(url_for('dashboard'))
            except psycopg2.Error as e:
                conn_post.rollback()
                flash(f"Gagal menyimpan data komoditas: {e}", "danger")
            finally:
                if cur_post:
                    cur_post.close()
                close_db_connection(conn_post)
        else:
            flash("Gagal terhubung ke database saat menyimpan komoditas. Cek konfigurasi database Anda.", "danger")
            return redirect(url_for('dashboard'))

    return render_template('isi_komoditas.html', petani_list=petani_list)

@app.route('/isi_hasil_panen', methods=['GET', 'POST'])
@login_required
def isi_hasil_panen():
    conn = get_db_conn()
    if not conn:
        flash("Gagal koneksi ke database. Cek konfigurasi database Anda.", "danger")
        return redirect(url_for('dashboard'))

    cur = None
    petani_list = []
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, nama FROM petani WHERE user_id = %s", (session['user_id'],))
        petani_list = cur.fetchall()
    except psycopg2.Error as e:
        flash("Terjadi kesalahan database saat mengambil daftar petani.", "danger")
    finally:
        if cur:
            cur.close()
        close_db_connection(conn)

    if request.method == 'POST':
        petani_id = request.form['petani_id']
        nama_komoditas = request.form['nama_komoditas']
        jumlah = request.form['jumlah']
        tanggal_panen = request.form['tanggal_panen']

        conn_post = get_db_conn()
        if conn_post:
            cur_post = None
            try:
                cur_post = conn_post.cursor()
                cur_post.execute("""
                    INSERT INTO hasil_panen (petani_id, nama_komoditas, jumlah, tanggal_panen)
                    VALUES (%s, %s, %s, %s)
                """, (petani_id, nama_komoditas, jumlah, tanggal_panen))
                conn_post.commit()
                flash("Data hasil panen berhasil disimpan", "success")
                return redirect(url_for('dashboard'))
            except psycopg2.Error as e:
                conn_post.rollback()
                flash(f"Gagal menyimpan data hasil panen: {e}", "danger")
            finally:
                if cur_post:
                    cur_post.close()
                close_db_connection(conn_post)
        else:
            flash("Gagal terhubung ke database saat menyimpan hasil panen. Cek konfigurasi database Anda.", "danger")
            return redirect(url_for('dashboard'))

    return render_template('isi_hasil_panen.html', petani_list=petani_list)

@app.route("/riwayat_petani")
@login_required
def riwayat_petani():
    user_id = session.get('user_id')
    conn = get_db_conn()
    petani_data = []
    if conn:
        cur = None
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, nama, nik, tanggal_lahir, no_telpon, alamat, luas_lahan FROM petani WHERE user_id = %s",
                (user_id,)
            )
            petani_data = cur.fetchall()
        except psycopg2.Error as e:
            flash(f"Terjadi kesalahan database saat mengambil riwayat petani: {e}", "danger")
            app.logger.error(f"Error fetching petani data for user {user_id}: {e}", exc_info=True)
        finally:
            if cur:
                cur.close()
            close_db_connection(conn)
    else:
        flash("Gagal koneksi ke database. Cek konfigurasi database Anda.", "danger")

    return render_template("riwayat_petani.html", petani=petani_data)

@app.route("/edit_petani/<int:id>", methods=["GET", "POST"])
@login_required
def edit_petani(id):
    conn = get_db_conn()
    if not conn:
        flash("Gagal koneksi ke database. Cek konfigurasi database Anda.", "danger")
        return redirect(url_for('riwayat_petani'))

    cur = None
    try:
        cur = conn.cursor()
        if request.method == "POST":
            nama = request.form['nama']
            nik = request.form['nik']
            tanggal_lahir = request.form['tanggal_lahir']
            no_telpon = request.form['no_telpon']
            alamat = request.form['alamat']
            lahan_geom = request.form['lahan_geom']

            cur.execute("""
                UPDATE petani
                SET nama=%s, nik=%s, tanggal_lahir=%s, no_telpon=%s, alamat=%s, lahan_geom=ST_GeomFromText(%s, 4326)
                WHERE id=%s AND user_id=%s
            """, (nama, nik, tanggal_lahir, no_telpon, alamat, lahan_geom, id, session['user_id']))
            conn.commit()
            flash("Data petani berhasil diperbarui!", "success")
            return redirect(url_for("riwayat_petani"))

        else:
            cur.execute("""
                SELECT id, nama, nik, tanggal_lahir, no_telpon, alamat, lokasi_point, ST_AsText(lahan_geom), luas_lahan
                FROM petani
                WHERE id = %s AND user_id = %s
            """, (id, session['user_id']))
            petani = cur.fetchone()
            if not petani:
                flash("Data petani tidak ditemukan atau Anda tidak memiliki akses.", "danger")
                return redirect(url_for("riwayat_petani"))

            petani_dict = {
                'id': petani[0],
                'nama': petani[1],
                'nik': petani[2],
                'tanggal_lahir': petani[3].strftime('%Y-%m-%d') if petani[3] else '',
                'no_telpon': petani[4],
                'alamat': petani[5],
                'lokasi_point': petani[6],
                'lahan_geom': petani[7],
                'luas_lahan': petani[8]
            }
            return render_template("edit_petani.html", petani=petani_dict)
    except Exception as e:
        conn.rollback()
        flash(f"Terjadi kesalahan saat memperbarui data petani: {e}", "danger")
        app.logger.error(f"Edit Petani Error: {e}", exc_info=True)
    finally:
        if cur:
            cur.close()
        close_db_connection(conn)

    return redirect(url_for('riwayat_petani'))

@app.route("/hapus_petani/<int:id>")
@login_required
def hapus_petani(id):
    conn = get_db_conn()
    if conn:
        cur = None
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM petani WHERE id = %s AND user_id = %s", (id, session['user_id'],))
            conn.commit()
            flash("Data berhasil dihapus", "success")
        except psycopg2.Error as e:
            conn.rollback()
            flash("Terjadi kesalahan database saat menghapus data petani.", "danger")
        finally:
            if cur:
                cur.close()
            close_db_connection(conn)
        return redirect(url_for("riwayat_petani"))
    else:
        flash("Gagal koneksi ke database. Cek konfigurasi database Anda.", "danger")
        return redirect(url_for('riwayat_petani'))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)