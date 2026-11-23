"""Opt-in sample records, only used with a separate demo database."""
from pathlib import Path
import struct
import zlib
from store import DomainError, fingerprint


def _png_chunk(kind, payload):
    return (struct.pack(">I", len(payload)) + kind + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff))


def create_demo_thumbnail(path):
    """Write a tiny synthetic landscape image without using user media or extra packages."""
    width, height = 640, 360
    scanlines = bytearray()
    for y in range(height):
        scanlines.append(0)
        for x in range(width):
            if (x - 500) ** 2 + (y - 92) ** 2 < 42 ** 2:
                color = (248, 205, 133)
            elif y > 230 + (x % 90) // 3:
                color = (35, 54, 57)
            elif y > 185 + (x % 140) // 3:
                color = (53, 80, 82)
            else:
                color = (28 + y // 10, 42 + y // 8, 65 + y // 6)
            scanlines.extend(color)
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    image = (b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", header)
             + _png_chunk(b"IDAT", zlib.compress(bytes(scanlines), 6))
             + _png_chunk(b"IEND", b""))
    path.write_bytes(image)


def seed(store, workspace):
    def ensure_channel(name, niche, style):
        match = next((row for row in store.channels() if row["name"] == name), None)
        if match:
            if match["archived"]:
                store.save_channel(name, niche, style=style, channel_id=match["id"],
                                   actor="demo-seed", archived=False)
            return match["id"]
        return store.save_channel(name, niche, style=style, actor="demo-seed")

    def ensure_album(channel_id, name, brief):
        match = next((row for row in store.albums(channel_id) if row["name"] == name), None)
        return match["id"] if match else store.create_album(channel_id, name, brief, actor="demo-seed")

    def ensure_project(channel_id, album_id, title, brief):
        match = next((row for row in store.projects(channel_id, album_id=album_id)
                      if row["title"] == title), None)
        return match["id"] if match else store.create_project(
            channel_id, title, brief=brief, owner="Sinh viên", actor="demo-seed", album_id=album_id)

    def ensure_asset(project_id, kind, path, note=""):
        info = fingerprint(path)
        slot = path.stem if kind == "clip" else "main"
        latest = [asset for asset in store.assets(project_id, latest=True)
                  if asset["kind"] == kind and asset["slot"] == slot]
        if any(asset["path"] == info["path"] and asset["sha256"] == info["sha256"]
               for asset in latest):
            return
        if store.project(project_id)["stage"] in ("review", "ready", "scheduled", "published"):
            return
        store.add_asset(project_id, kind, path, "demo-seed", note=note)

    channels = [
        ("DEMO • Winter Jazz", "Jazz / ambience", "Café mùa đông, tuyết nhẹ, camera cố định"),
        ("DEMO • Forest Calm", "Meditation / nature", "Rừng, sương nhẹ, màu xanh trầm"),
        ("DEMO • Study Jazz", "Jazz / study", "Thư viện yên tĩnh, ánh sáng ấm, chuyển động tối thiểu"),
    ]
    ids = {name: ensure_channel(name, niche, style) for name, niche, style in channels}
    releases = [
        ("DEMO • Winter Jazz", "DEMO • Snow Café Sessions", "Một đợt phát hành mùa đông với nhiều video ambience.", [
            ("DEMO • Christmas Snow Ambience", "Video nhạc jazz mùa đông, một giờ, khung hình cố định; tuyết nhẹ ngoài trời."),
            ("DEMO • Snowy Café Piano Jazz", "Video thứ hai trong cùng album; tiêu đề, hình ảnh và bản thành phẩm được theo dõi riêng."),
        ]),
        ("DEMO • Winter Jazz", "DEMO • Holiday Candlelight Collection", "Đợt phát hành nhạc lễ hội trong không gian ấm.", [
            ("DEMO • Candlelight Christmas Jazz", "Nhạc jazz Noel trong quán cà phê ánh nến, chuyển động hình ảnh chậm."),
            ("DEMO • Fireplace Carol Lounge", "Không gian lò sưởi với carol nhẹ, theo dõi riêng tài nguyên và QC."),
        ]),
        ("DEMO • Forest Calm", "DEMO • Morning Forest Collection", "Nhóm nội dung thiền buổi sáng.", [
            ("DEMO • Morning Forest", "Thiền buổi sáng trong rừng, sương mỏng, chuyển động lá rất nhẹ."),
            ("DEMO • Misty River Meditation", "Cảnh sông mù sương, âm thanh thiên nhiên và brief riêng."),
        ]),
        ("DEMO • Forest Calm", "DEMO • Night Rain Reset", "Đợt phát hành âm thanh mưa và cảnh rừng ban đêm.", [
            ("DEMO • Rain on Forest Leaves", "Mưa đêm trên tán lá, hình ảnh tĩnh và âm thanh nền liên tục."),
            ("DEMO • Quiet Cabin Rain", "Mưa ngoài cabin; video có tài nguyên và trạng thái QC độc lập."),
        ]),
        ("DEMO • Study Jazz", "DEMO • Quiet Study Hours", "Nhóm video nhạc nền đọc sách và tập trung.", [
            ("DEMO • Library Study Session", "Nhạc nền yên tĩnh cho thời gian đọc sách."),
            ("DEMO • Warm Desk Focus Jazz", "Nhạc jazz nhẹ cho góc học tập, một video/mix riêng."),
        ]),
        ("DEMO • Study Jazz", "DEMO • Late Night Reading", "Đợt phát hành nhạc nền đọc sách buổi tối.", [
            ("DEMO • Midnight Book Café", "Không gian đọc sách ban đêm, ánh sáng dịu và nhạc nền ổn định."),
            ("DEMO • Rainy Window Study", "Nhạc tập trung cạnh cửa sổ mưa, có brief và lịch sử riêng."),
        ]),
    ]
    hero_project = None
    for channel_name, album_name, album_brief, projects in releases:
        channel_id = ids[channel_name]
        album_id = ensure_album(channel_id, album_name, album_brief)
        for title, brief in projects:
            project_id = ensure_project(channel_id, album_id, title, brief)
            if title == "DEMO • Christmas Snow Ambience":
                hero_project = project_id

    output_root = Path(workspace) / "OUTPUT TỔNG" / "Content Hub" / "Demo Assets"
    output_root.mkdir(parents=True, exist_ok=True)
    research = output_root / "demo_research.md"
    research.write_text("# Dữ liệu minh họa\n\nĐây là brief nghiên cứu giả lập phục vụ demo, không phải kết quả thị trường thực.\n", encoding="utf-8")
    thumbnail = output_root / "demo_thumbnail.png"
    if not thumbnail.is_file():
        create_demo_thumbnail(thumbnail)
    ensure_asset(hero_project, "research", research)
    ensure_asset(hero_project, "thumbnail", thumbnail,
                 note="Ảnh hình học tổng hợp phục vụ demo; không lấy từ tài khoản hoặc output thật.")
    # Demo seed never links arbitrary production media from workspace output folders.
    # All transitions use real domain gates; no SQL fabrication of production stages.
    for _ in range(2):
        p = store.project(hero_project)
        if p["stage"] not in ("idea", "research"):
            break
        try:
            store.advance(hero_project, p["revision"], "demo-seed")
        except DomainError:
            break
