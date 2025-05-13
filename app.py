from flask import Flask, render_template, request, redirect, session, url_for, flash
import psycopg2
from config import DB_CONFIG
import os
from shapely import wkt
from shapely.geometry import Point, Polygon, MultiPolygon
from geoalchemy2.shape import from_shape
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "12345678")  # gunakan env jika ada
UPLOAD_FOLDER = 'uploads/shapefiles'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ... (semua definisi fungsi & rute tetap seperti sebelumnya)

@app.route("/")
def home():
    print("Mengakses rute /")
    return redirect(url_for('login'))

# ... (semua route lainnya tetap sama tanpa perubahan)

# Jalankan server dengan port dari Railway
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Gunakan PORT dari Railway jika tersedia
    app.run(host="0.0.0.0", port=port)


def get_db_conn():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print("Database connection successful.")
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to database: {e}")
        return None

def close_db_connection(conn):
    if conn:
        conn.close()
        print("Database connection closed.")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Anda harus login untuk mengakses halaman ini.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

from werkzeug.security import generate_password_hash, check_password_hash

@app.route('/', methods=['GET', 'POST'])
def index():
    print("Mengakses rute /")
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    print("Mengakses rute /login")
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_conn()
        if conn:
            cur = conn.cursor()
            cur.execute("SELECT id, password FROM users WHERE username = %s", (username,))
            user = cur.fetchone()
            cur.close()
            conn.close()

            if user and check_password_hash(user[1], password):
                session['user_id'] = user[0]
                session['username'] = username
                print(f"Login berhasil, redirect ke dashboard. User: {username}")
                return redirect(url_for('dashboard'))
            else:
                flash("Login gagal. Cek username dan password.", "danger")
                print(f"Login gagal untuk user: {username}")
        else:
            flash("Gagal terhubung ke database.", "danger")
            print("Gagal terhubung ke database saat login.")

    print("Rendering login.html")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    print("Mengakses rute /register")
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
                print(f"Username {username} sudah terdaftar.")
            else:
                cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_pw))
                conn.commit()
                flash("Registrasi berhasil. Silakan login.", "success")
                print(f"Registrasi berhasil untuk user: {username}")
                return redirect(url_for('login'))

            cur.close()
            conn.close()
        else:
            flash("Gagal terhubung ke database.", "danger")
            print("Gagal terhubung ke database saat register.")

    print("Rendering register.html")
    return render_template('register.html')


@app.route('/logout')
def logout():
    print("Mengakses rute /logout")
    session.clear()
    print("Sesi di clear, redirect ke /login")
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    print("Mengakses rute /dashboard")
    if 'user_id' not in session:
        print("User tidak login, redirect ke /login")
        return redirect(url_for('login'))

    conn = get_db_conn()
    if conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM petani WHERE user_id = %s LIMIT 1", (session['user_id'],))
        petani_data = cur.fetchone()
        cur.close()
        close_db_connection(conn)
        print(f"Rendering dashboard.html untuk user: {session['username']}")
        return render_template('dashboard.html', username=session['username'], petani_data=petani_data)
    else:
        flash("Gagal terhubung ke database.", "danger")
        print("Gagal terhubung ke database saat dashboard.")
        return render_template('dashboard.html', username=session['username'], petani_data=None)

@app.route('/form_petani', methods=['GET', 'POST'])
@login_required
def form_petani():
    print("Mengakses rute /form_petani")
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
            print("Luas lahan tidak valid")
            return render_template('add_petani.html')

        if not lahan_geom_wkt or not lahan_geom_wkt.strip().upper().startswith('POLYGON'):
            flash("Geometri lahan tidak valid atau kosong.", "danger")
            print("Geometri lahan tidak valid atau kosong")
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
            print(f"Kesalahan saat memproses geometri: {e}")
            return render_template('add_petani.html')

        conn = get_db_conn()
        if conn is None:
            flash('Gagal terhubung ke database.', 'danger')
            print('Gagal terhubung ke database.')
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
            print("Data petani berhasil disimpan!")
            # Setelah berhasil menyimpan, dapatkan ID petani yang baru diinsert
            cur.execute("SELECT id FROM petani WHERE nik = %s", (nik,))
            petani_id = cur.fetchone()[0]
            cur.close()
            close_db_connection(conn)
            return redirect(url_for('edit_petani', id=petani_id))
        except psycopg2.Error as e:
            conn.rollback()
            flash(f"Kesalahan database: {e}", "danger")
            print("Database error:", e)
        finally:
            cur.close()
            close_db_connection(conn)

    print("Rendering add_petani.html")
    return render_template('add_petani.html')

@app.route('/isi_komoditas', methods=['GET', 'POST'])
@login_required
def isi_komoditas():
    print("Mengakses rute /isi_komoditas")
    conn = get_db_conn()
    if not conn:
        flash("Gagal koneksi ke database", "danger")
        print("Gagal koneksi ke database")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        petani_id = request.form['petani_id']
        nama_komoditas = request.form['nama_komoditas']
        luas_lahan = request.form['luas_lahan']
        tanggal_tanam = request.form['tanggal_tanam']

        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO komoditas (petani_id, nama_komoditas, luas_lahan, tanggal_tanam)
                VALUES (%s, %s, %s, %s)
            """, (petani_id, nama_komoditas, luas_lahan, tanggal_tanam))
            conn.commit()
            flash("Data komoditas berhasil disimpan", "success")
            print("Data komoditas berhasil disimpan")
            return redirect(url_for('dashboard'))
        except Exception as e:
            conn.rollback()
            flash(f"Gagal menyimpan data: {e}", "danger")
            print(f"Gagal menyimpan data: {e}")
        finally:
            cur.close()
            close_db_connection(conn)

    cur = conn.cursor()
    cur.execute("SELECT id, nama FROM petani")
    petani_list = cur.fetchall()
    cur.close()
    close_db_connection(conn)
    print("Rendering isi_komoditas.html")
    return render_template('isi_komoditas.html', petani_list=petani_list)

@app.route('/isi_hasil_panen', methods=['GET', 'POST'])
@login_required
def isi_hasil_panen():
    print("Mengakses rute /isi_hasil_panen")
    conn = get_db_conn()
    if not conn:
        flash("Gagal koneksi ke database", "danger")
        print("Gagal koneksi ke database")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        petani_id = request.form['petani_id']
        nama_komoditas = request.form['nama_komoditas']
        jumlah = request.form['jumlah']
        tanggal_panen = request.form['tanggal_panen']

        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO hasil_panen (petani_id, nama_komoditas, jumlah, tanggal_panen)
                VALUES (%s, %s, %s, %s)
            """, (petani_id, nama_komoditas, jumlah, tanggal_panen))
            conn.commit()
            flash("Data hasil panen berhasil disimpan", "success")
            print("Data hasil panen berhasil disimpan")
            return redirect(url_for('dashboard'))
        except Exception as e:
            conn.rollback()
            flash(f"Gagal menyimpan data: {e}", "danger")
            print(f"Gagal menyimpan data: {e}")
        finally:
            cur.close()
            close_db_connection(conn)

    cur = conn.cursor()
    cur.execute("SELECT id, nama FROM petani")
    petani_list = cur.fetchall()
    cur.close()
    close_db_connection(conn)
    print("Rendering isi_hasil_panen.html")
    return render_template('isi_hasil_panen.html', petani_list=petani_list)

@app.route("/riwayat_petani")
@login_required
def riwayat_petani():
    print("Mengakses rute /riwayat_petani")
    user_id = session.get('user_id')
    conn = get_db_conn()
    if conn:
        cur = conn.cursor()
        cur.execute("SELECT id, nama, nik, tanggal_lahir, no_telpon, alamat, luas_lahan FROM petani WHERE user_id = %s", (user_id,))
        data = cur.fetchall()
        cur.close()
        close_db_connection(conn)
        print("Rendering riwayat_petani.html")
        return render_template("riwayat_petani.html", petani=data)
    else:
        flash("Gagal koneksi ke database", "danger")
        print("Gagal koneksi ke database")
        return redirect(url_for('dashboard'))

@app.route("/edit_petani/<int:id>", methods=["GET", "POST"])
@login_required
def edit_petani(id):
    print(f"Mengakses rute /edit_petani/{id}")
    conn = get_db_conn()
    if conn:
        cur = conn.cursor()
        if request.method == "POST":
            # update data
            nama = request.form['nama']
            nik = request.form['nik']
            no_telpon = request.form['no_telpon']
            alamat = request.form['alamat']

            cur.execute("UPDATE petani SET nama=%s, nik=%s, no_telpon=%s, alamat=%s WHERE id=%s",
                        (nama, nik, no_telpon, alamat, id))
            conn.commit()
            flash("Data berhasil diperbarui", "success")
            print("Data berhasil diperbarui")
            cur.close()
            close_db_connection(conn)
            return redirect(url_for("riwayat_petani"))
        else:
            cur.execute("SELECT nama, nik, no_telpon, alamat, ST_AsText(lahan_geom) as lahan_geom FROM petani WHERE id = %s", (id,))
            petani = cur.fetchone()
            if petani:
                cur.close()
                close_db_connection(conn)
                print("Rendering edit_petani.html")
                return render_template("edit_petani.html", petani=petani, id=id)
            else:
                flash("Data petani tidak ditemukan.", "danger")
                print("Data petani tidak ditemukan.")
                cur.close()
                close_db_connection(conn)
                return redirect(url_for("riwayat_petani"))
    else:
        flash("Gagal koneksi ke database", "danger")
        print("Gagal koneksi ke database")
        return redirect(url_for('riwayat_petani'))

@app.route("/hapus_petani/<int:id>")
@login_required
def hapus_petani(id):
    print(f"Mengakses rute /hapus_petani/{id}")
    conn = get_db_conn()
    if conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM petani WHERE id = %s", (id,))
        conn.commit()
        cur.close()
        close_db_connection(conn)
        flash("Data berhasil dihapus", "success")
        print("Data berhasil dihapus")
        return redirect(url_for("riwayat_petani"))
    else:
        flash("Gagal koneksi ke database", "danger")
        print("Gagal koneksi ke database")
        return redirect(url_for('riwayat_petani'))

# Remaining routes for register, login, dashboard, etc.

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))  # default ke 5000 jika PORT tidak tersedia
    app.run(host="0.0.0.0", port=port)