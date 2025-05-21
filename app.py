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
    conn = None
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
        else:
            from config import DB_CONFIG
            conn = psycopg2.connect(**DB_CONFIG)
            app.logger.info("Database connection successful (via DB_CONFIG).")
    except psycopg2.Error as e:
        app.logger.error(f"Error connecting to database: {e}", exc_info=True)
    return conn

def close_db_connection(conn):
    """Menutup koneksi database jika terbuka dengan logging."""
    if conn:
        conn.close()
        app.logger.info("Database connection closed.")

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

@app.route('/', methods=['GET', 'POST'])
def index():
    app.logger.info("Mengakses rute /")
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    app.logger.info("Mengakses rute /login")
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_conn()
        if conn:
            cur = conn.cursor()
            try:
                cur.execute("SELECT id, password FROM users WHERE username = %s", (username,))
                user = cur.fetchone()
                if user and check_password_hash(user[1], password):
                    session['user_id'] = user[0]
                    session['username'] = username
                    app.logger.info(f"Login berhasil untuk user: {username}, redirect ke dashboard.")
                    cur.close()
                    close_db_connection(conn)
                    return redirect(url_for('dashboard'))
                else:
                    app.logger.warning(f"Login gagal untuk user: {username}. Username atau password salah.")
                    flash("Login gagal. Cek username dan password.", "danger")
            except psycopg2.Error as e:
                app.logger.error(f"Database error saat login: {e}", exc_info=True)
                flash("Terjadi kesalahan database saat login.", "danger")
            finally:
                cur.close()
                close_db_connection(conn)
        else:
            flash("Gagal terhubung ke database saat login.", "danger")
            app.logger.error("Gagal terhubung ke database saat login.")

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    app.logger.info("Mengakses rute /register")
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_pw = generate_password_hash(password)
        conn = get_db_conn()
        if conn:
            cur = conn.cursor()
            try:
                cur.execute("SELECT id FROM users WHERE username = %s", (username,))
                existing = cur.fetchone()
                if existing:
                    app.logger.warning(f"Username {username} sudah terdaftar.")
                    flash("Username sudah terdaftar.", "danger")
                else:
                    cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_pw))
                    conn.commit()
                    app.logger.info(f"Registrasi berhasil untuk user: {username}, redirect ke login.")
                    flash("Registrasi berhasil. Silakan login.", "success")
                    return redirect(url_for('login'))
            except psycopg2.Error as e:
                conn.rollback()
                app.logger.error(f"Database error saat register: {e}", exc_info=True)
                flash("Terjadi kesalahan database saat registrasi.", "danger")
            finally:
                cur.close()
                close_db_connection(conn)
        else:
            flash("Gagal terhubung ke database saat register.", "danger")
            app.logger.error("Gagal terhubung ke database saat register.")

    return render_template('register.html')

@app.route('/logout')
def logout():
    app.logger.info("Mengakses rute /logout")
    session.clear()
    app.logger.info("Sesi di clear, redirect ke /login.")
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    app.logger.info(f"Mengakses rute /dashboard untuk user: {session.get('username')}")
    conn = get_db_conn()
    if conn:
        cur = conn.cursor()
        try:
            cur.execute("SELECT id FROM petani WHERE user_id = %s LIMIT 1", (session['user_id'],))
            petani_data = cur.fetchone()
            app.logger.info(f"Data petani untuk user {session.get('username')}: {petani_data}")
        except psycopg2.Error as e:
            app.logger.error(f"Database error saat mengambil data petani: {e}", exc_info=True)
            flash("Terjadi kesalahan database saat mengambil data petani.", "danger")
            petani_data = None
        finally:
            cur.close()
            close_db_connection(conn)
        return render_template('dashboard.html', username=session['username'], petani_data=petani_data)
    else:
        flash("Gagal terhubung ke database saat dashboard.", "danger")
        app.logger.error("Gagal terhubung ke database saat dashboard.")
        return render_template('dashboard.html', username=session['username'], petani_data=None)

@app.route('/form_petani', methods=['GET', 'POST'])
@login_required
def form_petani():
    app.logger.info(f"Mengakses rute /form_petani untuk user: {session.get('username')}")
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
            app.logger.warning(f"Luas lahan tidak valid: {luas_lahan_str}")
            return render_template('add_petani.html')

        if not lahan_geom_wkt or not lahan_geom_wkt.strip().upper().startswith('POLYGON'):
            flash("Geometri lahan tidak valid atau kosong.", "danger")
            app.logger.warning(f"Geometri lahan tidak valid atau kosong: {lahan_geom_wkt}")
            return render_template('add_petani.html')

        lokasi_point = f"SRID=4326;POINT({lon} {lat})"

        conn = get_db_conn()
        if conn is None:
            flash('Gagal terhubung ke database.', 'danger')
            app.logger.error('Gagal terhubung ke database saat form_petani.')
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
            cur.close()
            close_db_connection(conn)

    return render_template('add_petani.html')

@app.route('/isi_komoditas', methods=['GET', 'POST'])
@login_required
def isi_komoditas():
    app.logger.info(f"Mengakses rute /isi_komoditas untuk user: {session.get('username')}")
    conn = get_db_conn()
    if not conn:
        flash("Gagal koneksi ke database", "danger")
        app.logger.error("Gagal koneksi ke database saat isi_komoditas.")
        return redirect(url_for('dashboard'))

    cur = conn.cursor()
    petani_list = []
    try:
        cur.execute("SELECT id, nama FROM petani WHERE user_id = %s", (session['user_id'],))
        petani_list = cur.fetchall()
        app.logger.info(f"Daftar petani untuk user {session.get('username')}: {petani_list}")
    except psycopg2.Error as e:
        app.logger.error(f"Database error saat mengambil daftar petani: {e}", exc_info=True)
        flash("Terjadi kesalahan database saat mengambil daftar petani.", "danger")
    finally:
        cur.close()

    if request.method == 'POST':
        petani_id = request.form['petani_id']
        nama_komoditas = request.form['nama_komoditas']
        luas_lahan = request.form['luas_lahan']
        tanggal_tanam = request.form['tanggal_tanam']

        conn = get_db_conn()
        if conn:
            cur = conn.cursor()
            try:
                cur.execute("""
                    INSERT INTO komoditas (petani_id, nama_komoditas, luas_lahan, tanggal_tanam)
                    VALUES (%s, %s, %s, %s)
                """, (petani_id, nama_komoditas, luas_lahan, tanggal_tanam))
                conn.commit()
                flash("Data komoditas berhasil disimpan", "success")
                app.logger.info(f"Data komoditas untuk petani {petani_id} berhasil disimpan.")
                return redirect(url_for('dashboard'))
            except psycopg2.Error as e:
                conn.rollback()
                flash(f"Gagal menyimpan data komoditas: {e}", "danger")
                app.logger.error(f"Database error saat menyimpan data komoditas: {e}", exc_info=True)
            finally:
                cur.close()
                close_db_connection(conn)
        else:
            flash("Gagal terhubung ke database saat menyimpan komoditas.", "danger")
            app.logger.error("Gagal terhubung ke database saat menyimpan komoditas.")
            return redirect(url_for('dashboard'))

    close_db_connection(conn)
    return render_template('isi_komoditas.html', petani_list=petani_list)

@app.route('/isi_hasil_panen', methods=['GET', 'POST'])
@login_required
def isi_hasil_panen():
    app.logger.info(f"Mengakses rute /isi_hasil_panen untuk user: {session.get('username')}")
    conn = get_db_conn()
    if not conn:
        flash("Gagal koneksi ke database", "danger")
        app.logger.error("Gagal koneksi ke database saat isi_hasil_panen.")
        return redirect(url_for('dashboard'))

    cur = conn.cursor()
    petani_list = []
    try:
        cur.execute("SELECT id, nama FROM petani WHERE user_id = %s", (session['user_id'],))
        petani_list = cur.fetchall()
        app.logger.info(f"Daftar petani untuk user {session.get('username')}: {petani_list}")
    except psycopg2.Error as e:
        app.logger.error(f"Database error saat mengambil daftar petani: {e}", exc_info=True)
        flash("Terjadi kesalahan database saat mengambil daftar petani.", "danger")
    finally:
        cur.close()

    if request.method == 'POST':
        petani_id = request.form['petani_id']
        nama_komoditas = request.form['nama_komoditas']
        jumlah = request.form['jumlah']
        tanggal_panen = request.form['tanggal_panen']

        conn = get_db_conn()
        if conn:
            cur = conn.cursor()
            try:
                cur.execute("""
                    INSERT INTO hasil_panen (petani_id, nama_komoditas, jumlah, tanggal_panen)
                    VALUES (%s, %s, %s, %s)
                """, (petani_id, nama_komoditas, jumlah, tanggal_panen))
                conn.commit()
                flash("Data hasil panen berhasil disimpan", "success")
                app.logger.info(f"Data hasil panen untuk petani {petani_id} berhasil disimpan.")
                return redirect(url_for('dashboard'))
            except psycopg2.Error as e:
                conn.rollback()
                flash(f"Gagal menyimpan data hasil panen: {e}", "danger")
                app.logger.error(f"Database error saat menyimpan data hasil panen: {e}", exc_info=True)
            finally:
                cur.close()
                close_db_connection(conn)
        else:
            flash("Gagal terhubung ke database saat menyimpan hasil panen.", "danger")
            app.logger.error("Gagal terhubung ke database saat menyimpan hasil panen.")
            return redirect(url_for('dashboard'))

    close_db_connection(conn)
    return render_template('isi_hasil_panen.html', petani_list=petani_list)

@app.route("/riwayat_petani")
@login_required
def riwayat_petani():
    app.logger.info(f"Mengakses rute /riwayat_petani untuk user: {session.get('username')}")
    user_id = session.get('user_id')
    conn = get_db_conn()
    if conn:
        cur = conn.cursor()
        petani_data = []
        try:
            cur.execute("SELECT id, nama, nik, tanggal_lahir, no_telpon, alamat, luas_lahan FROM petani WHERE user_id = %s", (user_id,))
            petani_data = cur.fetchall()
            app.logger.info(f"Riwayat petani untuk user {user_id}: {petani_data}")
        except psycopg2.Error as e:
            app.logger.error(f"Database error saat mengambil riwayat petani: {e}", exc_info=True)
            flash("Terjadi kesalahan database saat mengambil riwayat petani.", "danger")
        finally:
            cur.close()
            close_db_connection(conn)
        return render_template("riwayat_petani.html", petani=petani_data)
    else:
        flash("Gagal koneksi ke database", "danger")
        app.logger.error("Gagal koneksi ke database saat riwayat_petani.")
        return redirect(url_for('dashboard'))

@app.route("/edit_petani/<int:id>", methods=["GET", "POST"])
@login_required
def edit_petani(id):
    app.logger.info(f"Mengakses rute /edit_petani/{id} untuk user: {session.get('username')}")
    conn = get_db_conn()
    if conn:
        cur = conn.cursor()
        petani = None
        try:
            if request.method == "POST":
                nama = request.form['nama']
                nik = request.form['nik']
                no_telpon = request.form['no_telpon']
                alamat = request.form['alamat']
                cur.execute("UPDATE petani SET nama=%s, nik=%s, no_telpon=%s, alamat=%s WHERE id=%s AND user_id=%s",
                            (nama, nik, no_telpon, alamat, id, session['user_id']))
                conn.commit()
                flash("Data berhasil diperbarui", "success")
                app.logger.info(f"Data petani dengan ID {id} berhasil diperbarui oleh user {session.get('username')}.")
                cur.close()
                close_db_connection(conn)
                return redirect(url_for("riwayat_petani"))
            else:
                cur.execute("SELECT nama, nik, no_telpon, alamat, ST_AsText(lahan_geom) as lahan_geom FROM petani WHERE id = %s AND user_id = %s", (id, session['user_id'],))
                petani = cur.fetchone()
                if petani:
                    app.logger.info(f"Menampilkan form edit untuk petani ID {id} oleh user {session.get('username')}.")
                else:
                    flash("Data petani tidak ditemukan.", "danger")
                    app.logger.warning(f"Data petani dengan ID {id} tidak ditemukan untuk user {session.get('username')}.")
                    return redirect(url_for("riwayat_petani"))
        except psycopg2.Error as e:
            conn.rollback()
            app.logger.error(f"Database error saat edit petani ID {id}: {e}", exc_info=True)
            flash("Terjadi kesalahan database saat memperbarui data petani.", "danger")
        finally:
            if cur:
                cur.close()
            close_db_connection(conn)
        return render_template("edit_petani.html", petani=petani, id=id)
    else:
        flash("Gagal koneksi ke database", "danger")
        app.logger.error(f"Gagal koneksi ke database saat edit petani ID {id}.")
        return redirect(url_for('riwayat_petani'))

@app.route("/hapus_petani/<int:id>")
@login_required
def hapus_petani(id):
    app.logger.info(f"Mengakses rute /hapus_petani/{id} untuk user: {session.get('username')}")
    conn = get_db_conn()
    if conn:
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM petani WHERE id = %s AND user_id = %s", (id, session['user_id'],))
            conn.commit()
            flash("Data berhasil dihapus", "success")
            app.logger.info(f"Data petani dengan ID {id} berhasil dihapus oleh user {session.get('username')}.")
        except psycopg2.Error as e:
            conn.rollback()
            app.logger.error(f"Database error saat hapus petani ID {id}: {e}", exc_info=True)
            flash("Terjadi kesalahan database saat menghapus data petani.", "danger")
        finally:
            cur.close()
            close_db_connection(conn)
        return redirect(url_for("riwayat_petani"))
    else:
        flash("Gagal koneksi ke database", "danger")
        app.logger.error(f"Gagal koneksi ke database saat hapus petani ID {id}.")
        return redirect(url_for('riwayat_petani'))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True) # Tetap aktifkan debug untuk pengembangan