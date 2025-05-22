from flask import Flask, render_template, request, redirect, url_for, session, flash
import psycopg2
import os
import re
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Debug mode flag
debug_mode = True

# Session configuration for better security
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=not debug_mode,
    SESSION_COOKIE_SAMESITE='Lax'
)

# Konfigurasi koneksi database
DB_HOST = 'localhost'
DB_NAME = 'petani_app'
DB_USER = 'postgres'
DB_PASSWORD = '12345678'

# Fungsi koneksi database
def get_db_conn():
    return psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)

def close_db_connection(conn):
    if conn:
        conn.close()

# Fungsi validasi input

def validate_fields(*fields):
    return all(field and field.strip() for field in fields)

def is_valid_date(date_str):
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = None
        try:
            conn = get_db_conn()
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
            user = cur.fetchone()
            if user:
                session['user_id'] = user[0]
                session['username'] = user[1]
                return redirect(url_for('dashboard'))
            else:
                flash('Username atau password salah', 'danger')
        except psycopg2.Error as e:
            flash('Terjadi kesalahan saat koneksi ke database: {}'.format(e), 'danger')
        finally:
            close_db_connection(conn)
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM petani")
        petani_data = cur.fetchall()
    except psycopg2.Error as e:
        flash('Gagal mengambil data petani: {}'.format(e), 'danger')
        petani_data = []
    finally:
        close_db_connection(conn)

    return render_template('dashboard.html', petani_data=petani_data)

@app.route('/add_petani', methods=['GET', 'POST'])
def add_petani():
    if request.method == 'POST':
        nama = request.form['nama']
        nik = request.form['nik']
        tanggal_lahir = request.form['tanggal_lahir']
        no_telpon = request.form['no_telpon']
        alamat = request.form['alamat']
        lat = request.form['lat']
        lon = request.form['lon']
        lahan_geom_wkt = request.form['lahan_geom']

        if not validate_fields(nama, nik, tanggal_lahir, no_telpon, alamat, lat, lon, lahan_geom_wkt):
            flash("Semua field wajib diisi.", "danger")
            return render_template('add_petani.html')

        if not re.match(r'POLYGON\s*\(\(.*\)\)', lahan_geom_wkt.strip().upper()):
            flash("Format geometri tidak valid.", "danger")
            return render_template('add_petani.html')

        conn = None
        try:
            conn = get_db_conn()
            cur = conn.cursor()
            cur.execute("INSERT INTO petani (nama, nik, tanggal_lahir, no_telpon, alamat, geom, lat, lon) VALUES (%s, %s, %s, %s, %s, ST_GeomFromText(%s, 4326), %s, %s)",
                        (nama, nik, tanggal_lahir, no_telpon, alamat, lahan_geom_wkt, lat, lon))
            conn.commit()
            flash('Data petani berhasil ditambahkan', 'success')
            return redirect(url_for('dashboard'))
        except psycopg2.Error as e:
            flash('Terjadi kesalahan saat menyimpan data: {}'.format(e), 'danger')
        finally:
            close_db_connection(conn)

    return render_template('add_petani.html')

@app.route('/isi_komoditas', methods=['GET', 'POST'])
def isi_komoditas():
    if request.method == 'POST':
        id_petani = request.form['id_petani']
        nama_komoditas = request.form['nama_komoditas']
        jenis = request.form['jenis']
        luas_lahan = request.form['luas_lahan']
        tanggal_tanam = request.form['tanggal_tanam']

        if not validate_fields(id_petani, nama_komoditas, jenis, luas_lahan, tanggal_tanam) or not is_valid_date(tanggal_tanam):
            flash('Semua field wajib diisi dan format tanggal harus benar.', 'danger')
            return render_template('isi_komoditas.html')

        conn = None
        try:
            conn = get_db_conn()
            cur = conn.cursor()
            cur.execute("INSERT INTO komoditas (id_petani, nama_komoditas, jenis, luas_lahan, tanggal_tanam) VALUES (%s, %s, %s, %s, %s)",
                        (id_petani, nama_komoditas, jenis, luas_lahan, tanggal_tanam))
            conn.commit()
            flash('Data komoditas berhasil disimpan', 'success')
            return redirect(url_for('dashboard'))
        except psycopg2.Error as e:
            flash('Terjadi kesalahan saat menyimpan data: {}'.format(e), 'danger')
        finally:
            close_db_connection(conn)

    return render_template('isi_komoditas.html')

@app.route('/isi_hasil_panen', methods=['GET', 'POST'])
def isi_hasil_panen():
    if request.method == 'POST':
        id_petani = request.form['id_petani']
        nama_komoditas = request.form['nama_komoditas']
        jumlah = request.form['jumlah']
        satuan = request.form['satuan']
        tanggal_panen = request.form['tanggal_panen']

        if not validate_fields(id_petani, nama_komoditas, jumlah, satuan, tanggal_panen) or not is_valid_date(tanggal_panen):
            flash('Semua field wajib diisi dan format tanggal harus benar.', 'danger')
            return render_template('isi_hasil_panen.html')

        conn = None
        try:
            conn = get_db_conn()
            cur = conn.cursor()
            cur.execute("INSERT INTO hasil_panen (id_petani, nama_komoditas, jumlah, satuan, tanggal_panen) VALUES (%s, %s, %s, %s, %s)",
                        (id_petani, nama_komoditas, jumlah, satuan, tanggal_panen))
            conn.commit()
            flash('Data hasil panen berhasil disimpan', 'success')
            return redirect(url_for('dashboard'))
        except psycopg2.Error as e:
            flash('Terjadi kesalahan saat menyimpan data: {}'.format(e), 'danger')
        finally:
            close_db_connection(conn)

    return render_template('isi_hasil_panen.html')

if __name__ == '__main__':
    app.run(debug=debug_mode)
