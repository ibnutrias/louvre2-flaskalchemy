import unittest
import warnings
from sqlalchemy.exc import LegacyAPIWarning

# Tambahkan baris ini untuk menekan output warning
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=LegacyAPIWarning)

from app3 import app, db, pw_hash
from models import UserAccount, VirtualRoute, Booking

class TestLouvreVRMainFunctions(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['WTF_CSRF_ENABLED'] = False
        self.app = app.test_client()

        with app.app_context():
            db.create_all()
            
            # Seed data
            u = UserAccount(
                user_id="USR001", nama="Ibnu Falah",
                email="ibnu@email.com", password_hash=pw_hash("pass123")
            )
            t = VirtualRoute(
                tur_id="TUR001", nama_tur="Tur Sejarah", harga=50000,
                kapasitas=10, kuota_tersedia=10, status_jadwal="tersedia"
            )
            b = Booking(
                pesanan_id="ODR001", pengunjung_id="USR001", tur_id="TUR001",
                jumlah_tiket=2, status_pesanan="menunggu_bayar"
            )
            t.kuota_tersedia -= 2
            
            db.session.add_all([u, t, b])
            db.session.commit()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    # ==========================================
    # U-01: FUNGSI REGISTRASI
    # ==========================================
    def test_register_happy_path(self):
        """Skenario: Registrasi valid (Happy Path)"""
        response = self.app.post('/register', data={
            'nama': 'User Baru', 'email': 'baru@email.com', 'password': 'pass'
        }, follow_redirects=True)
        self.assertIn(b'Akun berhasil dibuat!', response.data)

    def test_register_exception_empty_field(self):
        """Skenario: Registrasi gagal karena email kosong (Exception)"""
        response = self.app.post('/register', data={
            'nama': 'User Baru', 'email': '', 'password': 'pass'
        }, follow_redirects=True)
        self.assertIn(b'Email tidak boleh kosong.', response.data)

    # ==========================================
    # U-02: FUNGSI PEMESANAN
    # ==========================================
    def test_pesan_happy_path(self):
        """Skenario: Pemesanan tiket valid (Happy Path)"""
        with self.app.session_transaction() as sess:
            sess['uid'] = 'USR001'
        response = self.app.post('/pesan/TUR001', data={'jumlah': '3'}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

    def test_pesan_exception_invalid_type(self):
        """Skenario: Pemesanan dengan input huruf (Exception - EXPECTED TO FAIL)"""
        with self.app.session_transaction() as sess:
            sess['uid'] = 'USR001'
        
        # Kirim teks "dua" bukan angka "2". Ini akan membuat sistem crash (Internal Server Error)
        response = self.app.post('/pesan/TUR001', data={'jumlah': 'dua'}, follow_redirects=True)
        # Sistem seharusnya menangani error dan tidak return status 500
        self.assertNotEqual(response.status_code, 500, "Sistem Crash (ValueError) karena tidak ada validasi tipe data int")

    # ==========================================
    # U-03: FUNGSI UBAH PESANAN
    # ==========================================
    def test_pesanan_ubah_happy_path(self):
        """Skenario: Ubah jumlah tiket pesanan (Happy Path)"""
        with self.app.session_transaction() as sess:
            sess['uid'] = 'USR001'
        response = self.app.post('/pesanan/ubah/ODR001', data={'jumlah': '4'}, follow_redirects=True)
        self.assertIn(b'Pesanan berhasil diperbarui.', response.data)

    def test_pesanan_ubah_exception_invalid_type(self):
        """Skenario: Ubah tiket dengan input huruf (Exception - EXPECTED TO FAIL)"""
        with self.app.session_transaction() as sess:
            sess['uid'] = 'USR001'
        
        # Kirim teks "lima"
        response = self.app.post('/pesanan/ubah/ODR001', data={'jumlah': 'lima'}, follow_redirects=True)
        self.assertNotEqual(response.status_code, 500, "Sistem Crash (ValueError) karena tidak ada validasi tipe data int")

if __name__ == '__main__':
    unittest.main(verbosity=2, warnings='ignore')
