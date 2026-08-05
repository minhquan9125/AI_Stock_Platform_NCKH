from datetime import datetime
import os
from pathlib import Path
import re
import shutil
import sys
import time

# Ép stdout dùng UTF-8: tránh UnicodeEncodeError khi in tiếng Việt có dấu
# trên terminal Windows mặc định dùng codepage cp1252.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# =====================================================================
# CẤU HÌNH HỆ THỐNG THƯ MỤC (FINMIND DATA LAKE)
# =====================================================================
# Thư mục gốc cần giám sát (Nơi các script cào data đang xuất file ra)
WATCH_DIR = Path(".")

# Thư mục "Hồ chứa dữ liệu" (Data Lake) - Nơi sắp xếp file ngăn nắp
DATA_LAKE_DIR = Path("./FinMind_Data_Lake")

# Các đuôi file sẽ được tự động dọn dẹp và phân loại
VALID_EXTENSIONS = [".json", ".csv", ".pdf", ".xlsx", ".doc", ".docx"]

# Các từ khóa bỏ qua (Không bao giờ di chuyển các file code python hoặc system)
IGNORE_FILES = [
    "finmind_file_organizer.py",
    "cafef_scraper.py",
    "cafef_bctc_scraper.py",
    "vnstock_data_fetcher.py",
    "fireant_api_scraper.py",
    "macro_commodity_scraper.py",
]


class FinMindDataOrganizer:

    def __init__(self, watch_dir, data_lake_dir):
        self.watch_dir = Path(watch_dir)
        self.data_lake_dir = Path(data_lake_dir)
        self.data_lake_dir.mkdir(parents=True, exist_ok=True)

    def _extract_ticker(self, filename):
        """Tự động nhận diện Mã Chứng Khoán (3-4 chữ cái in hoa) từ tên
        file.
        """
        # Tách tên file thành từng token theo dấu phân cách, thay vì dùng regex
        # tham lam (dễ "ăn lẹm" dấu phân cách dùng chung giữa 2 từ liền kề,
        # khiến token phía sau mất dấu phân cách đầu và không bao giờ khớp được).
        stem = Path(filename).stem
        tokens = re.split(r"[_ \-\.]+", stem.upper())

        exclude = {"DATA", "INFO", "FILE", "JSON", "BCTC", "TCBS", "NEWS", "CSV", "XLSX", "TEMP", "TEST"}
        for token in tokens:
            if re.fullmatch(r"[A-Z]{3,4}", token) and token not in exclude:
                return token

        # Nếu không tìm thấy mã CK cụ thể, xếp vào nhóm Dữ liệu thị trường chung
        return "GENERAL_MARKET"

    def _extract_category(self, filename):
        """Tự động phân loại luồng dữ liệu dựa trên từ khóa trong tên file."""
        fname_lower = filename.lower()
        if any(
            kw in fname_lower
            for kw in ["vnstock", "tcbs", "fireant", "vndirect", "ratio", "quote"]
        ):
            return "1_Chi_So_Tai_Chinh_Vnstock"
        elif any(
            kw in fname_lower
            for kw in ["bctc", "quarterly", "income", "balance", "finance"]
        ):
            return "2_Bao_Cao_Tai_Chinh"
        elif any(
            kw in fname_lower for kw in ["cafef", "news", "tin_tuc", "article"]
        ):
            return "3_Tin_Tuc_Va_Su_Kien"
        elif any(
            kw in fname_lower
            for kw in ["macro", "commodity", "vi_mo", "hang_hoa", "gdp", "cpi"]
        ):
            return "5_Vi_Mo_Hang_Hoa"
        else:
            return "4_Du_Lieu_Khac"

    def _update_manifest(self, ticker_dir, ticker, category, filename):
        """Tự động viết nhật ký (Manifest) vào file THONG_KE_DU_LIEU.txt trong
        folder mã CK.

        Giúp Thầy/Giám khảo mở folder ra là biết ngay folder này chứa những gì.
        """
        manifest_path = ticker_dir / "THONG_KE_DU_LIEU.txt"
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Nếu file chưa tồn tại, tạo phần Tiêu đề
        if not manifest_path.exists():
            with open(manifest_path, "w", encoding="utf-8") as f:
                f.write(f"=================================================\n")
                f.write(
                    f"  HỒ SƠ DỮ LIỆU MÃ CHỨNG KHOÁN: {ticker}\n"
                )
                f.write(f"  Dự án NCKH: FinMind RAG System\n")
                f.write(f"=================================================\n\n")
                f.write(f"DANH SÁCH CHI TIẾT CÁC FILE ĐÃ THU THẬP:\n")
                f.write(
                    f"{'Thời gian lưu':<20} | {'Phân loại':<25} | {'Tên file'}\n"
                )
                f.write(f"{'-'*20} | {'-'*25} | {'-'*40}\n")

        # Thêm dòng ghi nhận file mới vào cuối
        with open(manifest_path, "a", encoding="utf-8") as f:
            f.write(f"{now_str:<20} | {category:<25} | {filename}\n")

    def scan_and_organize(self):
        """Quét thư mục gốc và sắp xếp toàn bộ file tìm thấy."""
        moved_count = 0

        # Quét tất cả file trong thư mục H:\mascot
        for item in self.watch_dir.iterdir():
            # Bỏ qua nếu là thư mục, hoặc là file script/file hệ thống
            if item.is_dir() or item.name in IGNORE_FILES:
                continue

            # Bỏ qua nếu không đúng đuôi file dữ liệu (.json, .csv, .pdf...)
            if item.suffix.lower() not in VALID_EXTENSIONS:
                continue

            # 1. Nhận diện Mã CK và Phân loại thư mục
            ticker = self._extract_ticker(item.name)
            category = self._extract_category(item.name)

            # 2. Tạo đường dẫn thư mục đích: FinMind_Data_Lake / [Mã CK] / [Phân loại]
            target_dir = self.data_lake_dir / ticker / category
            target_dir.mkdir(parents=True, exist_ok=True)

            target_file_path = target_dir / item.name

            try:
                # Nếu file đã tồn tại trong thư mục đích, ghi đè bản mới nhất
                if target_file_path.exists():
                    target_file_path.unlink()

                # 3. Di chuyển file vào đúng thư mục
                shutil.move(str(item), str(target_file_path))
                moved_count += 1

                # 4. Ghi sổ nhật ký THONG_KE_DU_LIEU.txt
                self._update_manifest(
                    self.data_lake_dir / ticker, ticker, category, item.name
                )

                print(f"   [+] Đã sắp xếp: {item.name}")
                print(
                    f"       -> Lọc vào: FinMind_Data_Lake/{ticker}/{category}/\n"
                )

            except Exception as e:
                print(
                    f"   [!] Không thể di chuyển file {item.name} (Có thể file đang mở): {e}"
                )

        return moved_count

    def run_forever(self, check_interval=5):
        """Vòng lặp Watchdog: Liên tục giám sát, cào đến đâu dọn sạch đến
        đó!
        """
        print(
            f"╔══════════════════════════════════════════════════════════════╗"
        )
        print(
            f"║  🤖 FINMIND WATCHDOG - HỆ THỐNG PHÂN LOẠI DỮ LIỆU TỰ ĐỘNG  ║"
        )
        print(
            f"║  Đang giám sát thư mục gốc: {str(self.watch_dir.absolute())[:35]}... ║"
        )
        print(
            f"║  Hồ chứa dữ liệu (Data Lake): ./FinMind_Data_Lake/           ║"
        )
        print(
            f"╚══════════════════════════════════════════════════════════════╝\n"
        )

        while True:
            # Thực hiện quét và sắp xếp
            moved = self.scan_and_organize()

            if moved > 0:
                print(
                    f"[*] Vừa dọn dẹp xong {moved} file mới. Đang kiểm tra lại lập tức (Drain loop)..."
                )
                # KIỂM TRA LẠI NGAY LẬP TỨC (Không nghỉ) đúng theo yêu cầu của bạn:
                # "kiểm tra lại nếu còn file thì lặp lại quá trình trên"
                continue
            else:
                # Nếu không còn file nào ngoài thư mục gốc, nghỉ 5 giây rồi quét tiếp
                time.sleep(check_interval)


# =====================================================================
# KHU VỰC THỰC THI CHÍNH
# =====================================================================
if __name__ == "__main__":
    # Khởi tạo robot phân loại
    organizer = FinMindDataOrganizer(
        watch_dir=".", data_lake_dir="./FinMind_Data_Lake"
    )

    # Bật chế độ trực chiến 24/7 (Bấm Ctrl + C trong Terminal nếu muốn dừng lại)
    try:
        organizer.run_forever(check_interval=5)
    except KeyboardInterrupt:
        print("\n[!] Đã tắt hệ thống giám sát FinMind Watchdog. Tạm biệt!")