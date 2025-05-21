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
app.secret_key = os.environ.get("SECRET_KEY", "12345678")

# Konfigurasi Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app.logger.setLevel(logging.INFO)


def get_db_conn():
    """Membuat koneksi ke database PostgreSQL dengan logging."""
    try:
        if 'DATABASE_URL' in os.environ:
            url = urlparse(os.environ['DATABASE_URL'])
            conn = psycopg2.connect(
                host=url.hostname,
                port=url.port,
                database=url.path[1:],
                user=url.username,
                password=url.password
            )
            app.logger.info("Database connection successful (via DATABASE_URL).")
            return conn
        else:
            from config import DB_CONFIG
            conn = psycopg2.connect(**DB_CONFIG)
            app.logger.info("Database connection successful (via DB_CONFIG).")
            return conn
    except psycopg2.Error as e:
        app.logger.error(f"Error connecting to database: {e}", exc_info=True)
        return None


def close_db_connection(conn):
    """Menutup koneksi database jika terbuka dengan logging."""
    if conn:
        try:
            conn.close()
            app.logger.info("Database connection closed.")
        except Exception as e:
            app.logger.error(f"Error closing database connection: {e}", exc_info=True)


def login_required(f):
    """Dekorator untuk memastikan pengguna sudah login dengan logging."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            app.logger.info("Pengguna belum login, redirect ke /login.")
            flash('Anda harus login untuk mengakses halaman ini.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/', methods=['GET'])
def index():
    app.logger.info("Mengakses rute /")
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    app.logger.info("Mengakses rute /login")
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash("Username dan password harus diisi.", "danger")
            return render_template('login.html')

        conn = get_db_conn()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, password FROM users WHERE username = %s", (username,))
                    user = cur.fetchone()
                    if user and check_password_hash(user[1], password):
                        session['user_id'] = user[0]
                        session['username'] = username
                        app.logger.info(f"Login berhasil untuk user: {username}")
                        return redirect(url_for('dashboard'))
                    else:
                        app.logger.warning(f"Login gagal untuk user: {username}. Username atau password salah.")
                        flash("Login gagal. Cek username dan password.", "danger")
            except psycopg2.Error as e:
                app.logger.error(f"Database error saat login: {e}", exc_info=True)
                flash("Terjadi kesalahan database saat login.", "danger")
            finally:
                close_db_connection(conn)
        else:
            flash("Gagal terhubung ke database saat login.", "danger")
            app.logger.error("Gagal terhubung ke database saat login.")

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    app.logger.info("Mengakses rute /register")
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash("Username dan password harus diisi.", "danger")
            return render_template('register.html')

        hashed_pw = generate_password_hash(password)
        conn = get_db_conn()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM users WHERE username = %s", (username,))
                    existing = cur.fetchone()
                    if existing:
                        app.logger.warning(f"Username {username} sudah terdaftar.")
                        flash("Username sudah terdaftar.", "danger")
                    else:
                        cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_pw))
                        conn.commit()
                        app.logger.info(f"Registrasi berhasil untuk user: {username}")
                        flash("Registrasi berhasil. Silakan login.", "success")
                        return redirect(url_for('login'))
            except psycopg2.Error as e:
                conn.rollback()
                app.logger.error(f"Database error saat register: {e}", exc_info=True)
                flash("Terjadi kesalahan database saat registrasi.", "danger")
            finally:
                close_db_connection(conn)
        else:
            flash("Gagal terhubung ke database saat register.", "danger")
            app.logger.error("Gagal terhubung ke database saat register.")

    return render_template('register.html')


@app.route('/logout')
def logout():
    app.logger.info("Mengakses rute /logout")
    session.clear()
    app.logger.info("Sesi di-clear, redirect ke /login.")
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    app.logger.info(f"Mengakses rute /dashboard untuk user: {session.get('username')}")
    conn = get_db_conn()
    petani_data = None
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM petani WHERE user_id = %s LIMIT 1", (session['user_id'],))
                petani_data = cur.fetchone()
                app.logger.info(f"Data petani untuk user {session.get('username')}: {petani_data}")
        except psycopg2.Error as e:
            app.logger.error(f"Database error saat mengambil data petani: {e}", exc_info=True)
            flash("Terjadi kesalahan database saat mengambil data petani.", "danger")
        finally:
            close_db_connection(conn)
    else:
        flash("Gagal terhubung ke database saat dashboard.", "danger")
        app.logger.error("Gagal terhubung ke database saat dashboard.")
    return render_template('dashboard.html', username=session['username'], petani_data=petani_data)


@app.route('/form_petani', methods=['GET', 'POST'])
@login_required
def form_petani():
    app.logger.info(f"Mengakses rute /form_petani untuk user: {session.get('username')}")
    if request.method == 'POST':
        nama = request.form.get('nama')
        nik = request.form.get('nik')
        tanggal_lahir = request.form.get('tanggal_lahir')
        no_telpon = request.form.get('no_telpon')
        alamat = request.form.get('alamat')
        lat = request.form.get('latitude')
        lon = request.form.get('longitude')
        lahan_geom_wkt = request.form.get('lahan_geom')
        luas_lahan_str = request.form.get('luas_lahan', '0.0')

        # Validasi input wajib
        if not all([nama, nik, tanggal_lahir, no_telpon, alamat, lat, lon, lahan_geom_wkt]):
            flash("Semua field wajib diisi.", "danger")
            return render_template('add_petani.html')

        try:
            luas_lahan = float(luas_lahan_str)
        except ValueError:
            flash("Luas lahan tidak valid.", "danger")
            app.logger.warning(f"Luas lahan tidak valid: {luas_lahan_str}")
            return render_template('add_petani.html')

        if not lahan_geom_wkt.strip().upper().startswith('POLYGON'):
            flash("Geometri lahan tidak valid atau kosong.", "danger")
            app.logger.warning(f"Geometri lahan tidak valid atau kosong: {lahan_geom_wkt}")
            return render_template('add_petani.html')

        try:
            lat_float = float(lat)
            lon_float = float(lon)
        except ValueError:
            flash("Koordinat latitude dan longitude harus angka valid.", "danger")
            return render_template('add_petani.html')

        lokasi_point = f"POINT({lon_float} {lat_float})"

        conn = get_db_conn()
        if conn is None:
            flash('Gagal terhubung ke database.', 'danger')
            app.logger.error('Gagal terhubung ke database saat form_petani.')
            return render_template('add_petani.html')

        try:
            with conn.cursor() as cur:
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
                app.logger.info(f"Data petani untuk user {session.get('username')} berhasil disimpan.")
                return redirect(url_for('dashboard'))
        except psycopg2.Error as e:
            conn.rollback()
            flash(f"Kesalahan database saat menyimpan data petani: {e}", "danger")
            app.logger.error(f"Database error saat menyimpan data petani: {e}", exc_info=True)
        finally:
            close_db_connection(conn)

    return render_template('add_petani.html')


# Fungsi isi_komoditas dan isi_hasil_panen mirip, gunakan prinsip yang sama untuk konsistensi dan bersihkan duplikasi.

# Contoh perbaikan singkat untuk /isi_komoditas
@app.route('/isi_komoditas', methods=['GET', 'POST'])
@login_required
def isi_komoditas():
    app.logger.info(f"Mengakses rute /isi_komoditas untuk user: {session.get('username')}")
    conn = get_db_conn()
    if not conn:
        flash("Gagal koneksi ke database", "danger")
        app.logger.error("Gagal koneksi ke database saat isi_komoditas.")
        return redirect(url_for('dashboard'))

    petani_list = []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nama FROM petani WHERE user_id = %s", (session['user_id'],))
            petani_list = cur.fetchall()
            app.logger.info(f"Daftar petani untuk user {session.get('username')}: {petani_list}")
    except psycopg2.Error as e:
        flash("Error mengambil data petani", "danger")
        app.logger.error(f"Database error mengambil data petani: {e}", exc_info=True)
        return redirect(url_for('dashboard'))
    finally:
        close_db_connection(conn)

    if request.method == 'POST':
        komoditas = request.form.get('komoditas')
        tanggal_tanam = request.form.get('tanggal_tanam')
        tanggal_panen = request.form.get('tanggal_panen')
        id_petani = request.form.get('id_petani')

        if not all([komoditas, tanggal_tanam, tanggal_panen, id_petani]):
            flash("Semua field wajib diisi.", "danger")
            return render_template('isi_komoditas.html', petani=petani_list)

        conn = get_db_conn()
        if not conn:
            flash("Gagal koneksi ke database", "danger")
            return render_template('isi_komoditas.html', petani=petani_list)

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO komoditas (id_petani, komoditas, tanggal_tanam, tanggal_panen)
                    VALUES (%s, %s, %s, %s)
                """, (id_petani, komoditas, tanggal_tanam, tanggal_panen))
                conn.commit()
                flash("Data komoditas berhasil disimpan!", "success")
                app.logger.info(f"Data komoditas berhasil disimpan untuk petani ID {id_petani}")
                return redirect(url_for('dashboard'))
        except psycopg2.Error as e:
            conn.rollback()
            flash(f"Kesalahan database saat menyimpan data komoditas: {e}", "danger")
            app.logger.error(f"Database error saat menyimpan data komoditas: {e}", exc_info=True)
        finally:
            close_db_connection(conn)

    return render_template('isi_komoditas.html', petani=petani_list)


# Rute isi_hasil_panen dapat diperbaiki secara serupa seperti isi_komoditas.

@app.route('/isi_hasil_panen', methods=['GET', 'POST'])
@login_required
def isi_hasil_panen():
    app.logger.info(f"Mengakses rute /isi_hasil_panen untuk user: {session.get('username')}")
    conn = get_db_conn()
    if not conn:
        flash("Gagal koneksi ke database", "danger")
        app.logger.error("Gagal koneksi ke database saat isi_hasil_panen.")
        return redirect(url_for('dashboard'))

    petani_list = []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nama FROM petani WHERE user_id = %s", (session['user_id'],))
            petani_list = cur.fetchall()
            app.logger.info(f"Daftar petani untuk user {session.get('username')}: {petani_list}")
    except psycopg2.Error as e:
        flash("Error mengambil data petani", "danger")
        app.logger.error(f"Database error mengambil data petani: {e}", exc_info=True)
        return redirect(url_for('dashboard'))
    finally:
        close_db_connection(conn)

    if request.method == 'POST':
        hasil_panen = request.form.get('hasil_panen')
        tanggal_panen = request.form.get('tanggal_panen')
        id_petani = request.form.get('id_petani')

        if not all([hasil_panen, tanggal_panen, id_petani]):
            flash("Semua field wajib diisi.", "danger")
            return render_template('isi_hasil_panen.html', petani=petani_list)

        conn = get_db_conn()
        if not conn:
            flash("Gagal koneksi ke database", "danger")
            return render_template('isi_hasil_panen.html', petani=petani_list)

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO hasil_panen (id_petani, hasil_panen, tanggal_panen)
                    VALUES (%s, %s, %s)
                """, (id_petani, hasil_panen, tanggal_panen))
                conn.commit()
                flash("Data hasil panen berhasil disimpan!", "success")
                app.logger.info(f"Data hasil panen berhasil disimpan untuk petani ID {id_petani}")
                return redirect(url_for('dashboard'))
        except psycopg2.Error as e:
            conn.rollback()
            flash(f"Kesalahan database saat menyimpan data hasil panen: {e}", "danger")
            app.logger.error(f"Database error saat menyimpan data hasil panen: {e}", exc_info=True)
        finally:
            close_db_connection(conn)

    return render_template('isi_hasil_panen.html', petani=petani_list)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
