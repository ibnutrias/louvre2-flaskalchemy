from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class UserAccount(db.Model):
    __tablename__ = 'user_account'
    user_id = db.Column(db.String(10), primary_key=True)
    nama = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    no_hp = db.Column(db.String(20))
    asal_kota = db.Column(db.String(50))
    asal_negara = db.Column(db.String(50))
    kategori_usia = db.Column(db.String(20))
    password_hash = db.Column(db.String(200), nullable=False)

    bookings = db.relationship('Booking', backref='user', lazy=True)

class VirtualRoute(db.Model):
    __tablename__ = 'virtual_route'
    tur_id = db.Column(db.String(10), primary_key=True)
    nama_tur = db.Column(db.String(150), nullable=False)
    deskripsi = db.Column(db.Text)
    durasi = db.Column(db.String(20))
    harga = db.Column(db.Integer, nullable=False)
    kapasitas = db.Column(db.Integer, nullable=False)
    tanggal = db.Column(db.Date)
    jam_mulai = db.Column(db.Time)
    titik_kumpul = db.Column(db.String(50))
    kuota_tersedia = db.Column(db.Integer, nullable=False)
    status_jadwal = db.Column(db.String(20), default='tersedia')

    bookings = db.relationship('Booking', backref='route', lazy=True)
    info_points = db.relationship('InfoPoint', backref='route', lazy=True)

class InfoPoint(db.Model):
    __tablename__ = 'info_point'
    info_point_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tur_id = db.Column(db.String(10), db.ForeignKey('virtual_route.tur_id'), nullable=False)
    label = db.Column(db.String(100), nullable=False)
    coordinate_x = db.Column(db.Float, nullable=False)
    coordinate_y = db.Column(db.Float, nullable=False)
    coordinate_z = db.Column(db.Float, nullable=False)
    content = db.Column(db.Text)

class Admin(db.Model):
    __tablename__ = 'admin'
    admin_id = db.Column(db.String(10), primary_key=True)
    nama_admin = db.Column(db.String(100), nullable=False)
    peran = db.Column(db.String(50))
    user_id_admin = db.Column(db.String(20), unique=True)
    password_hash = db.Column(db.String(200), nullable=False)

    bookings = db.relationship('Booking', backref='admin_assigned', lazy=True)

class Booking(db.Model):
    __tablename__ = 'booking'
    pesanan_id = db.Column(db.String(10), primary_key=True)
    pengunjung_id = db.Column(db.String(10), db.ForeignKey('user_account.user_id'), nullable=False)
    tur_id = db.Column(db.String(10), db.ForeignKey('virtual_route.tur_id'), nullable=False)
    admin_id = db.Column(db.String(10), db.ForeignKey('admin.admin_id'))
    waktu_pesan = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    jumlah_tiket = db.Column(db.Integer, nullable=False, default=1)
    status_pesanan = db.Column(db.String(20), default='menunggu_bayar')

    payment = db.relationship('Payment', backref='booking', uselist=False)
    tickets = db.relationship('ETicket', backref='booking', lazy=True)

    @property
    def nama(self):
        return self.user.nama

    @property
    def nama_tur(self):
        return self.route.nama_tur

    @property
    def tanggal(self):
        return self.route.tanggal

    @property
    def jam_mulai(self):
        return self.route.jam_mulai

    @property
    def titik_kumpul(self):
        return self.route.titik_kumpul

    @property
    def total_biaya(self):
        return self.route.harga * self.jumlah_tiket

class Payment(db.Model):
    __tablename__ = 'payment'
    pembayaran_id = db.Column(db.String(10), primary_key=True)
    pesanan_id = db.Column(db.String(10), db.ForeignKey('booking.pesanan_id'), unique=True, nullable=False)
    metode = db.Column(db.String(30), nullable=False)
    waktu_bayar = db.Column(db.DateTime)
    status_bayar = db.Column(db.String(20), default='menunggu')

class ETicket(db.Model):
    __tablename__ = 'eticket'
    tiket_id = db.Column(db.String(10), primary_key=True)
    pesanan_id = db.Column(db.String(10), db.ForeignKey('booking.pesanan_id'), nullable=False)
    qr_code = db.Column(db.String(100), nullable=False)
    status_tiket = db.Column(db.String(20), default='aktif')
    waktu_terbit = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class Management(db.Model):
    __tablename__ = 'management'
    admin_id = db.Column(db.String(10), db.ForeignKey('admin.admin_id'), primary_key=True)
    tur_id = db.Column(db.String(10), db.ForeignKey('virtual_route.tur_id'), primary_key=True)
    tanggal_ditugaskan = db.Column(db.Date)
