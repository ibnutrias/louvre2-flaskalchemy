"""
Louvre VR  |  Flask-SQLAlchemy  |  SQLite
=============================================
1. pip install -r requirements.txt
2. python app.py --seed
3. python app.py
"""
import sys, hashlib, secrets, os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from models import db, UserAccount, VirtualRoute, InfoPoint, Admin, Booking, Payment, ETicket, Management

app = Flask(__name__)
app.secret_key = "louvre2026"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'louvre.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)


# ── Helper ────────────────────────────────────────────────────

def pw_hash(plain):
    s = secrets.token_hex(8)
    return s + ":" + hashlib.sha256((s+plain).encode()).hexdigest()

def pw_ok(plain, stored):
    if not stored: return False
    s, h = stored.split(":", 1)
    return hashlib.sha256((s+plain).encode()).hexdigest() == h

def new_id(prefix, model, pk_name):
    """Robust ID generation: incrementing the numeric part of the last ID."""
    try:
        last_rec = model.query.order_by(db.desc(getattr(model, pk_name))).first()
        if not last_rec: return f"{prefix}001"
        last_id = getattr(last_rec, pk_name)
        # Extract numeric part, assuming it follows the prefix
        num_part = last_id[len(prefix):]
        new_num = int(num_part) + 1
        return f"{prefix}{new_num:03d}"
    except:
        # Fallback to count if anything fails
        return f"{prefix}{model.query.count() + 1:03d}"

@app.template_filter("rp")
def rp(v):
    try: return "Rp {:,}".format(int(v)).replace(",",".")
    except: return v

def parse_date(d_str):
    if not d_str or not d_str.strip(): return None
    return datetime.strptime(d_str, '%Y-%m-%d').date()

def parse_time(t_str):
    if not t_str or not t_str.strip(): return None
    for fmt in ('%H:%M:%S', '%H:%M'):
        try:
            return datetime.strptime(t_str, fmt).time()
        except ValueError:
            continue
    return datetime.strptime(t_str, '%H:%M').time() # Final attempt to trigger standard error if both fail


# ── Halaman pengunjung ────────────────────────────────────────

@app.route("/")
def index():
    tours = VirtualRoute.query.filter_by(status_jadwal='tersedia').all()
    return render_template("index.html", tours=tours)


# ── CRUD: UserAccount (Register / Update / Delete) ───────────

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        f = request.form

        # --- Validasi kolom wajib ---
        required = {"nama": "Nama", "email": "Email", "password": "Password"}
        for field, label in required.items():
            if not f.get(field, "").strip():
                flash(f"{label} tidak boleh kosong.", "danger")
                return render_template("register.html")

        try:
            if UserAccount.query.filter_by(email=f["email"].lower()).first():
                flash("Email sudah terdaftar.", "danger")
            else:
                pid = new_id("USR", UserAccount, "user_id")
                u = UserAccount(
                    user_id=pid,
                    nama=f["nama"].strip(),
                    email=f["email"].lower().strip(),
                    no_hp=f.get("no_hp",""),
                    asal_kota=f.get("kota",""),
                    asal_negara=f.get("negara",""),
                    kategori_usia=f.get("usia","Dewasa"),
                    password_hash=pw_hash(f["password"])
                )
                db.session.add(u)
                db.session.commit()
                flash("Akun berhasil dibuat!", "success")
                return redirect(url_for("login"))
        except Exception as e:
            app.logger.error(f"Register Error: {str(e)}")
            db.session.rollback()
            flash(f"Gagal membuat akun: {str(e)}", "danger")

    return render_template("register.html")


@app.route("/profil/edit", methods=["GET","POST"])
def profil_edit():
    """Update: pengunjung mengubah data profil sendiri."""
    if "uid" not in session:
        return redirect(url_for("login"))

    u = UserAccount.query.get_or_404(session["uid"])

    if request.method == "POST":
        f = request.form

        # --- Validasi kolom wajib ---
        if not f.get("nama","").strip():
            flash("Nama tidak boleh kosong.", "danger")
            return render_template("profil_edit.html", u=u)

        try:
            u.nama        = f["nama"].strip()
            u.no_hp       = f.get("no_hp", u.no_hp)
            u.asal_kota   = f.get("kota", u.asal_kota)
            u.asal_negara = f.get("negara", u.asal_negara)
            u.kategori_usia = f.get("usia", u.kategori_usia)

            # Ganti password hanya jika diisi
            new_pw = f.get("password","").strip()
            if new_pw:
                u.password_hash = pw_hash(new_pw)

            db.session.commit()
            session["nama"] = u.nama
            flash("Profil berhasil diperbarui!", "success")
            return redirect(url_for("index"))
        except Exception as e:
            app.logger.error(f"Profil Edit Error: {str(e)}")
            db.session.rollback()
            flash(f"Gagal memperbarui profil: {str(e)}", "danger")

    return render_template("profil_edit.html", u=u)


@app.route("/profil/hapus", methods=["POST"])
def profil_hapus():
    """Delete: pengunjung menghapus akun sendiri."""
    if "uid" not in session:
        return redirect(url_for("login"))

    u = UserAccount.query.get_or_404(session["uid"])

    try:
        db.session.delete(u)
        db.session.commit()
        session.clear()
        flash("Akun berhasil dihapus.", "info")
        return redirect(url_for("index"))
    except Exception as e:
        app.logger.error(f"Profil Hapus Error: {str(e)}")
        db.session.rollback()
        flash(f"Gagal menghapus akun (pastikan tidak ada pesanan aktif): {str(e)}", "danger")
        return redirect(url_for("index"))


@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        # --- Validasi kolom wajib ---
        if not request.form.get("email","").strip() or not request.form.get("password","").strip():
            flash("Email dan password wajib diisi.", "danger")
            return render_template("login.html")

        u = UserAccount.query.filter_by(email=request.form["email"].lower()).first()
        if u and pw_ok(request.form["password"], u.password_hash):
            session["uid"]  = u.user_id
            session["nama"] = u.nama
            return redirect(url_for("index"))
        flash("Email/password salah.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ── CRUD: Booking (Create / Read / Update / Delete) ──────────

@app.route("/pesan/<tur_id>", methods=["GET","POST"])
def pesan(tur_id):
    """Create booking."""
    if "uid" not in session: return redirect(url_for("login"))
    tur = VirtualRoute.query.get_or_404(tur_id)

    if request.method == "POST":
        jml = int(request.form.get("jumlah", 1))

        # --- Validasi ---
        if jml < 1:
            flash("Jumlah tiket minimal 1.", "danger")
            return render_template("pesan.html", tur=tur)
        if jml > tur.kuota_tersedia:
            flash(f"Kuota tidak mencukupi. Tersedia: {tur.kuota_tersedia}", "danger")
            return render_template("pesan.html", tur=tur)

        try:
            pid = new_id("ODR", Booking, "pesanan_id")
            booking = Booking(
                pesanan_id=pid,
                pengunjung_id=session["uid"],
                tur_id=tur_id,
                waktu_pesan=datetime.now(),
                jumlah_tiket=jml,
                status_pesanan='menunggu_bayar'
            )
            tur.kuota_tersedia -= jml
            db.session.add(booking)
            db.session.commit()
            return redirect(url_for("bayar", pid=pid))
        except Exception as e:
            app.logger.error(f"Pesan Error (Booking): {str(e)}")
            db.session.rollback()
            flash(f"Gagal membuat pesanan: {str(e)}", "danger")

    return render_template("pesan.html", tur=tur)


@app.route("/jadwal")
def jadwal():
    """Read: daftar semua pesanan pengunjung."""
    if "uid" not in session: return redirect(url_for("login"))
    rows = Booking.query.filter_by(pengunjung_id=session["uid"]).order_by(Booking.waktu_pesan.desc()).all()
    return render_template("jadwal.html", rows=rows)


@app.route("/pesanan/ubah/<pid>", methods=["GET","POST"])
def pesanan_ubah(pid):
    """Update: ubah jumlah tiket pesanan yang masih menunggu bayar."""
    if "uid" not in session: return redirect(url_for("login"))
    order = Booking.query.get_or_404(pid)

    # Pastikan pesanan milik user yang login
    if order.pengunjung_id != session["uid"]:
        flash("Akses ditolak.", "danger")
        return redirect(url_for("jadwal"))

    if order.status_pesanan != 'menunggu_bayar':
        flash("Pesanan yang sudah dibayar tidak dapat diubah.", "warning")
        return redirect(url_for("jadwal"))

    tur = VirtualRoute.query.get_or_404(order.tur_id)

    if request.method == "POST":
        jml_baru = int(request.form.get("jumlah", 1))

        # --- Validasi ---
        if jml_baru < 1:
            flash("Jumlah tiket minimal 1.", "danger")
            return render_template("pesanan_ubah.html", order=order, tur=tur)

        selisih = jml_baru - order.jumlah_tiket
        if selisih > tur.kuota_tersedia:
            flash(f"Kuota tidak mencukupi. Kuota tersisa: {tur.kuota_tersedia}", "danger")
            return render_template("pesanan_ubah.html", order=order, tur=tur)

        try:
            tur.kuota_tersedia -= selisih
            order.jumlah_tiket  = jml_baru
            db.session.commit()
            flash("Pesanan berhasil diperbarui.", "success")
            return redirect(url_for("jadwal"))
        except Exception as e:
            app.logger.error(f"Pesanan Ubah Error: {str(e)}")
            db.session.rollback()
            flash(f"Gagal memperbarui pesanan: {str(e)}", "danger")

    return render_template("pesanan_ubah.html", order=order, tur=tur)


@app.route("/pesanan/batal/<pid>", methods=["POST"])
def pesanan_batal(pid):
    """Delete: batalkan (hapus) pesanan yang masih menunggu bayar."""
    if "uid" not in session: return redirect(url_for("login"))
    order = Booking.query.get_or_404(pid)

    if order.pengunjung_id != session["uid"]:
        flash("Akses ditolak.", "danger")
        return redirect(url_for("jadwal"))

    if order.status_pesanan != 'menunggu_bayar':
        flash("Hanya pesanan dengan status 'menunggu bayar' yang dapat dibatalkan.", "warning")
        return redirect(url_for("jadwal"))

    try:
        tur = VirtualRoute.query.get(order.tur_id)
        if tur:
            tur.kuota_tersedia += order.jumlah_tiket   # kembalikan kuota
        db.session.delete(order)
        db.session.commit()
        flash("Pesanan berhasil dibatalkan.", "info")
    except Exception as e:
        app.logger.error(f"Pesanan Batal Error: {str(e)}")
        db.session.rollback()
        flash(f"Gagal membatalkan pesanan: {str(e)}", "danger")

    return redirect(url_for("jadwal"))


# ── CRUD: Payment & ETicket (Create / Read) ──────────────────

@app.route("/bayar/<pid>", methods=["GET","POST"])
def bayar(pid):
    """Create payment & e-ticket."""
    if "uid" not in session: return redirect(url_for("login"))
    order = Booking.query.get_or_404(pid)

    if request.method == "POST":
        # --- Validasi ---
        if not request.form.get("metode","").strip():
            flash("Pilih metode pembayaran.", "danger")
            return render_template("bayar.html", order=order)

        try:
            pay_id = new_id("PAY", Payment, "pembayaran_id")
            now    = datetime.now()

            payment = Payment(
                pembayaran_id=pay_id,
                pesanan_id=pid,
                metode=request.form["metode"],
                waktu_bayar=now,
                status_bayar='berhasil'
            )
            order.status_pesanan = 'lunas'

            last_tkt = ETicket.query.order_by(db.desc(ETicket.tiket_id)).first()
            base_num = 0
            if last_tkt:
                try: base_num = int(last_tkt.tiket_id[3:])
                except: base_num = ETicket.query.count()

            for i in range(order.jumlah_tiket):
                tid = f"TKT{base_num + i + 1:03d}"
                ticket = ETicket(
                    tiket_id=tid,
                    pesanan_id=pid,
                    qr_code=f"LVR|{pid}|{tid}|{secrets.token_hex(4).upper()}",
                    status_tiket='aktif',
                    waktu_terbit=now
                )
                db.session.add(ticket)

            db.session.add(payment)
            db.session.commit()
            flash("Pembayaran berhasil!", "success")
            return redirect(url_for("tiket", pid=pid))
        except Exception as e:
            app.logger.error(f"Bayar Error (Payment/Ticket): {str(e)}")
            db.session.rollback()
            flash(f"Gagal memproses pembayaran: {str(e)}", "danger")

    return render_template("bayar.html", order=order)


@app.route("/tiket/<pid>")
def tiket(pid):
    """Read: tampilkan e-tiket."""
    if "uid" not in session: return redirect(url_for("login"))
    order = Booking.query.get_or_404(pid)
    return render_template("tiket.html", order=order, tikets=order.tickets, bayar=order.payment)


# ── Admin: Auth ───────────────────────────────────────────────

@app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    if request.method == "POST":
        # --- Validasi ---
        if not request.form.get("uid","").strip() or not request.form.get("password","").strip():
            flash("ID dan password wajib diisi.", "danger")
            return render_template("admin_login.html")

        try:
            a = Admin.query.filter_by(user_id_admin=request.form["uid"]).first()
            if a and pw_ok(request.form["password"], a.password_hash):
                session["aid"]  = a.admin_id
                session["anam"] = a.nama_admin
                return redirect(url_for("admin_dashboard"))
            flash("ID/password salah.", "danger")
        except Exception as e:
            app.logger.error(f"Admin Login Error: {str(e)}")
            flash(f"Kesalahan sistem: {str(e)}", "danger")

    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("aid", None); session.pop("anam", None)
    return redirect(url_for("admin_login"))


# ── Admin: Dashboard & Read ───────────────────────────────────

@app.route("/admin")
def admin_dashboard():
    if "aid" not in session: return redirect(url_for("admin_login"))
    stats = {
        "pengunjung": UserAccount.query.count(),
        "tur":        VirtualRoute.query.count(),
        "pesanan":    Booking.query.count(),
        "tiket":      ETicket.query.count()
    }
    recent = Booking.query.order_by(Booking.waktu_pesan.desc()).limit(5).all()
    return render_template("admin_dashboard.html", stats=stats, recent=recent)


# ── Admin: CRUD VirtualRoute ──────────────────────────────────

@app.route("/admin/tur")
def admin_tur():
    """Read: daftar semua tur."""
    if "aid" not in session: return redirect(url_for("admin_login"))
    tours = VirtualRoute.query.order_by(VirtualRoute.tanggal).all()
    return render_template("admin_tur.html", tours=tours)


@app.route("/admin/tur/form", methods=["GET","POST"])
@app.route("/admin/tur/form/<tur_id>", methods=["GET","POST"])
def admin_tur_form(tur_id=None):
    """Create / Update tur."""
    if "aid" not in session: return redirect(url_for("admin_login"))
    tur = VirtualRoute.query.get(tur_id) if tur_id else None

    if request.method == "POST":
        f = request.form

        # --- Validasi kolom wajib ---
        required = {"nama_tur": "Nama Tur", "harga": "Harga", "kapasitas": "Kapasitas"}
        for field, label in required.items():
            if not f.get(field, "").strip():
                flash(f"{label} tidak boleh kosong.", "danger")
                return render_template("admin_tur_form.html", tur=tur)

        try:
            if tur_id:
                # --- UPDATE ---
                tur.nama_tur       = f["nama_tur"]
                tur.deskripsi      = f.get("deskripsi","")
                tur.durasi         = f.get("durasi","")
                tur.harga          = int(f["harga"])
                tur.kapasitas      = int(f["kapasitas"])
                tur.tanggal        = parse_date(f.get("tanggal"))
                tur.jam_mulai      = parse_time(f.get("jam_mulai"))
                tur.titik_kumpul   = f.get("titik_kumpul","")
                tur.kuota_tersedia = int(f["kuota_tersedia"])
                tur.status_jadwal  = f.get("status_jadwal","tersedia")
            else:
                # --- CREATE ---
                tid = new_id("TUR", VirtualRoute, "tur_id")
                kap = int(f["kapasitas"])
                tur = VirtualRoute(
                    tur_id=tid,
                    nama_tur=f["nama_tur"],
                    deskripsi=f.get("deskripsi",""),
                    durasi=f.get("durasi",""),
                    harga=int(f["harga"]),
                    kapasitas=kap,
                    tanggal=parse_date(f.get("tanggal")),
                    jam_mulai=parse_time(f.get("jam_mulai")),
                    titik_kumpul=f.get("titik_kumpul",""),
                    kuota_tersedia=kap,
                    status_jadwal="tersedia"
                )
                db.session.add(tur)

                mgt = Management(
                    admin_id=session["aid"],
                    tur_id=tid,
                    tanggal_ditugaskan=datetime.now().date()
                )
                db.session.add(mgt)

            db.session.commit()
            flash("Data tur berhasil disimpan!", "success")
            return redirect(url_for("admin_tur"))
        except Exception as e:
            app.logger.error(f"Admin Tur Form Error (Save): {str(e)}")
            db.session.rollback()
            flash(f"Gagal menyimpan data tur: {str(e)}", "danger")

    return render_template("admin_tur_form.html", tur=tur)


@app.route("/admin/tur/hapus/<tur_id>", methods=["POST"])
def admin_tur_hapus(tur_id):
    """Delete: hapus tur berdasarkan ID unik."""
    if "aid" not in session: return redirect(url_for("admin_login"))
    tur = VirtualRoute.query.get_or_404(tur_id)

    try:
        db.session.delete(tur)
        db.session.commit()
        flash(f"Tur '{tur.nama_tur}' berhasil dihapus.", "info")
    except Exception as e:
        app.logger.error(f"Admin Tur Hapus Error: {str(e)}")
        db.session.rollback()
        flash(f"Gagal menghapus tur (pastikan tidak ada pesanan terkait): {str(e)}", "danger")

    return redirect(url_for("admin_tur"))


# ── Admin: CRUD Pesanan (Read / Update / Delete) ─────────────

@app.route("/admin/pesanan")
def admin_pesanan():
    """Read: daftar semua pesanan."""
    if "aid" not in session: return redirect(url_for("admin_login"))
    rows = Booking.query.order_by(Booking.waktu_pesan.desc()).all()
    return render_template("admin_pesanan.html", rows=rows)


@app.route("/admin/pesanan/ubah/<pid>", methods=["GET","POST"])
def admin_pesanan_ubah(pid):
    """Update: admin mengubah status pesanan."""
    if "aid" not in session: return redirect(url_for("admin_login"))
    order = Booking.query.get_or_404(pid)

    if request.method == "POST":
        status_baru = request.form.get("status_pesanan","").strip()

        # --- Validasi ---
        status_valid = ['menunggu_bayar', 'lunas', 'dibatalkan']
        if status_baru not in status_valid:
            flash("Status pesanan tidak valid.", "danger")
            return render_template("admin_pesanan_ubah.html", order=order)

        try:
            order.status_pesanan = status_baru
            db.session.commit()
            flash("Status pesanan berhasil diperbarui.", "success")
            return redirect(url_for("admin_pesanan"))
        except Exception as e:
            app.logger.error(f"Admin Pesanan Update Error: {str(e)}")
            db.session.rollback()
            flash(f"Gagal memperbarui status: {str(e)}", "danger")

    return render_template("admin_pesanan_ubah.html", order=order)


@app.route("/admin/pesanan/hapus/<pid>", methods=["POST"])
def admin_pesanan_hapus(pid):
    """Delete: admin menghapus record pesanan."""
    if "aid" not in session: return redirect(url_for("admin_login"))
    order = Booking.query.get_or_404(pid)

    try:
        # Kembalikan kuota jika pesanan belum lunas
        if order.status_pesanan == 'menunggu_bayar':
            tur = VirtualRoute.query.get(order.tur_id)
            if tur:
                tur.kuota_tersedia += order.jumlah_tiket
        db.session.delete(order)
        db.session.commit()
        flash("Pesanan berhasil dihapus.", "info")
    except Exception as e:
        app.logger.error(f"Admin Pesanan Hapus Error: {str(e)}")
        db.session.rollback()
        flash(f"Gagal menghapus pesanan: {str(e)}", "danger")

    return redirect(url_for("admin_pesanan"))


# ── Admin: CRUD Pengunjung (Read / Update / Delete) ───────────

@app.route("/admin/pengunjung")
def admin_pengunjung():
    """Read: daftar semua pengunjung."""
    if "aid" not in session: return redirect(url_for("admin_login"))
    rows = UserAccount.query.order_by(UserAccount.nama).all()
    return render_template("admin_pengunjung.html", rows=rows)


@app.route("/admin/pengunjung/ubah/<uid>", methods=["GET","POST"])
def admin_pengunjung_ubah(uid):
    """Update: admin mengubah data pengunjung."""
    if "aid" not in session: return redirect(url_for("admin_login"))
    u = UserAccount.query.get_or_404(uid)

    if request.method == "POST":
        f = request.form

        # --- Validasi kolom wajib ---
        if not f.get("nama","").strip():
            flash("Nama tidak boleh kosong.", "danger")
            return render_template("admin_pengunjung_ubah.html", u=u)

        try:
            u.nama          = f["nama"].strip()
            u.no_hp         = f.get("no_hp", u.no_hp)
            u.asal_kota     = f.get("kota", u.asal_kota)
            u.asal_negara   = f.get("negara", u.asal_negara)
            u.kategori_usia = f.get("usia", u.kategori_usia)
            db.session.commit()
            flash("Data pengunjung berhasil diperbarui.", "success")
            return redirect(url_for("admin_pengunjung"))
        except Exception as e:
            app.logger.error(f"Admin Pengunjung Update Error: {str(e)}")
            db.session.rollback()
            flash(f"Gagal memperbarui data: {str(e)}", "danger")

    return render_template("admin_pengunjung_ubah.html", u=u)


@app.route("/admin/pengunjung/hapus/<uid>", methods=["POST"])
def admin_pengunjung_hapus(uid):
    """Delete: admin menghapus akun pengunjung berdasarkan ID unik."""
    if "aid" not in session: return redirect(url_for("admin_login"))
    u = UserAccount.query.get_or_404(uid)

    try:
        db.session.delete(u)
        db.session.commit()
        flash(f"Akun '{u.nama}' berhasil dihapus.", "info")
    except Exception as e:
        app.logger.error(f"Admin Pengunjung Hapus Error: {str(e)}")
        db.session.rollback()
        flash(f"Gagal menghapus akun (pastikan tidak ada referensi aktif): {str(e)}", "danger")

    return redirect(url_for("admin_pengunjung"))


# ── Admin: CRUD InfoPoint (Create / Read / Update / Delete) ──

@app.route("/admin/infopoint")
def admin_infopoint():
    """Read: daftar semua info point."""
    if "aid" not in session: return redirect(url_for("admin_login"))
    rows = InfoPoint.query.all()
    return render_template("admin_infopoint.html", rows=rows)


@app.route("/admin/infopoint/form", methods=["GET","POST"])
@app.route("/admin/infopoint/form/<int:ip_id>", methods=["GET","POST"])
def admin_infopoint_form(ip_id=None):
    """Create / Update info point."""
    if "aid" not in session: return redirect(url_for("admin_login"))
    ip = InfoPoint.query.get_or_404(ip_id) if ip_id else None
    tours = VirtualRoute.query.all()

    if request.method == "POST":
        f = request.form

        # --- Validasi kolom wajib ---
        if not f.get("label","").strip() or not f.get("tur_id","").strip():
            flash("Label dan Tur tidak boleh kosong.", "danger")
            return render_template("admin_infopoint_form.html", ip=ip, tours=tours)

        try:
            if ip_id:
                # --- UPDATE ---
                ip.tur_id       = f["tur_id"]
                ip.label        = f["label"].strip()
                ip.coordinate_x = float(f.get("coordinate_x", 0))
                ip.coordinate_y = float(f.get("coordinate_y", 0))
                ip.coordinate_z = float(f.get("coordinate_z", 0))
                ip.content      = f.get("content","")
            else:
                # --- CREATE ---
                ip = InfoPoint(
                    tur_id=f["tur_id"],
                    label=f["label"].strip(),
                    coordinate_x=float(f.get("coordinate_x", 0)),
                    coordinate_y=float(f.get("coordinate_y", 0)),
                    coordinate_z=float(f.get("coordinate_z", 0)),
                    content=f.get("content","")
                )
                db.session.add(ip)

            db.session.commit()
            flash("Info point berhasil disimpan.", "success")
            return redirect(url_for("admin_infopoint"))
        except Exception as e:
            app.logger.error(f"Admin InfoPoint Save Error: {str(e)}")
            db.session.rollback()
            flash(f"Gagal menyimpan info point: {str(e)}", "danger")

    return render_template("admin_infopoint_form.html", ip=ip, tours=tours)


@app.route("/admin/infopoint/hapus/<int:ip_id>", methods=["POST"])
def admin_infopoint_hapus(ip_id):
    """Delete: hapus info point berdasarkan ID unik."""
    if "aid" not in session: return redirect(url_for("admin_login"))
    ip = InfoPoint.query.get_or_404(ip_id)

    try:
        db.session.delete(ip)
        db.session.commit()
        flash("Info point berhasil dihapus.", "info")
    except Exception as e:
        app.logger.error(f"Admin InfoPoint Hapus Error: {str(e)}")
        db.session.rollback()
        flash(f"Gagal menghapus info point: {str(e)}", "danger")

    return redirect(url_for("admin_infopoint"))


# ── Seed ──────────────────────────────────────────────────────

def seed():
    with app.app_context():
        db.drop_all()
        db.create_all()

        # Seed Admin
        adm1 = Admin(admin_id="ADM001", nama_admin="Siti Rahayu",   peran="admin jadwal",  user_id_admin="UID-ADM01", password_hash=pw_hash("admin123"))
        adm2 = Admin(admin_id="ADM002", nama_admin="Doni Prasetyo", peran="petugas loket", user_id_admin="UID-ADM02", password_hash=pw_hash("admin123"))
        db.session.add_all([adm1, adm2])

        # Seed Users
        u1 = UserAccount(user_id="USR001", nama="Ahmad Fauzi",  email="ahmad@email.com", no_hp="081234567890", asal_kota="Jakarta",  asal_negara="Indonesia", kategori_usia="Dewasa",  password_hash=pw_hash("password123"))
        u2 = UserAccount(user_id="USR002", nama="Budi Santoso", email="budi@email.com",  no_hp="082345678901", asal_kota="Bandung",  asal_negara="Indonesia", kategori_usia="Pelajar", password_hash=pw_hash("password123"))
        u3 = UserAccount(user_id="USR003", nama="Citra Dewi",   email="citra@email.com", no_hp="083456789012", asal_kota="Surabaya", asal_negara="Indonesia", kategori_usia="Dewasa",  password_hash=pw_hash("password123"))
        db.session.add_all([u1, u2, u3])

        # Seed Tours
        t1 = VirtualRoute(tur_id="TUR001", nama_tur="Tur Premium Koleksi Nusantara", deskripsi="Tur eksklusif koleksi budaya Nusantara", durasi="3 jam", harga=150000, kapasitas=20, tanggal=datetime.strptime("2026-01-10", "%Y-%m-%d").date(), jam_mulai=datetime.strptime("08:00", "%H:%M").time(), titik_kumpul="GATE01", kuota_tersedia=18, status_jadwal="tersedia")
        t2 = VirtualRoute(tur_id="TUR002", nama_tur="Tur Luxury Manuskrip Kuno",     deskripsi="Tur mewah koleksi manuskrip langka",    durasi="4 jam", harga=300000, kapasitas=10, tanggal=datetime.strptime("2026-01-15", "%Y-%m-%d").date(), jam_mulai=datetime.strptime("09:00", "%H:%M").time(), titik_kumpul="GATE02", kuota_tersedia=9,  status_jadwal="tersedia")
        db.session.add_all([t1, t2])

        # Seed InfoPoints
        ip1 = InfoPoint(tur_id="TUR001", label="Arca Buddha", coordinate_x=12.5, coordinate_y=5.0, coordinate_z=0.0, content="Arca Buddha yang ditemukan di Jawa Tengah.")
        db.session.add(ip1)

        # Seed Management
        db.session.add(Management(admin_id="ADM001", tur_id="TUR001", tanggal_ditugaskan=datetime.now().date()))

        db.session.commit()
        print("Seed selesai! Login: ahmad@email.com / password123 | UID-ADM01 / admin123")


if __name__ == "__main__":
    if "--seed" in sys.argv: seed()
    else: app.run(debug=True)