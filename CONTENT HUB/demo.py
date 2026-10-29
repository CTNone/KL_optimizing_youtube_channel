"""Opt-in sample records, only used with a separate demo database."""
from pathlib import Path
from store import STAGES

def seed(store, workspace):
    if store.channels():
        return
    winter = store.save_channel("DEMO • Winter Jazz", "Jazz / ambience", style="Café mùa đông, tuyết nhẹ, camera cố định", actor="demo-seed")
    forest = store.save_channel("DEMO • Forest Calm", "Meditation / nature", style="Rừng, sương nhẹ, màu xanh trầm", actor="demo-seed")
    project = store.create_project(winter, "DEMO • Christmas Snow Ambience", brief="Video nhạc jazz mùa đông, một giờ, khung hình cố định; tuyết nhẹ ngoài trời.", owner="Sinh viên", actor="demo-seed")
    store.create_project(forest, "DEMO • Morning Forest", brief="Thiền buổi sáng trong rừng, sương mỏng, chuyển động lá rất nhẹ.", owner="Sinh viên", actor="demo-seed")
    output_root = Path(workspace) / "TOOL Video Flow OUTPUT" / "Content Hub" / "Demo Assets"
    output_root.mkdir(parents=True, exist_ok=True)
    research = output_root / "demo_research.md"
    research.write_text("# Dữ liệu minh họa\n\nĐây là brief nghiên cứu giả lập phục vụ demo, không phải kết quả thị trường thực.\n", encoding="utf-8")
    store.add_asset(project, "research", research, "demo-seed")
    thumbnails = list((workspace / "TOOL NCTT" / "thumbnails").glob("*.jpg"))
    if thumbnails:
        store.add_asset(project, "thumbnail", thumbnails[0], "demo-seed", note="Ảnh minh họa từ thư viện có sẵn; chưa xác nhận cùng cảnh clip.")
    clips = sorted((Path(workspace) / "TOOL Video Flow OUTPUT" / "Video").rglob("*.mp4"))
    if clips:
        store.add_asset(project, "clip", clips[-1], "demo-seed")
    # All transitions use the real domain gates; no SQL fabrication of production stages.
    for _ in range(4):
        p = store.project(project)
        try:
            store.advance(project, p["revision"], "demo-seed")
        except ValueError:
            break
