import io, re, os

p = r"C:\Users\19414\DeskBox\我的桌面\文章\第十二周\e22869ba-3de8-4145-89ef-40fc87a7f505.svg"
out = []
out.append("exists=%s size=%d" % (os.path.exists(p), os.path.getsize(p) if os.path.exists(p) else -1))
s = io.open(p, encoding="utf-8", errors="replace").read()
out.append("chars=%d" % len(s))
out.append("viewBox=%s" % re.findall(r'viewBox="([^"]+)"', s)[:2])
txt = [t.strip() for t in re.findall(r">([^<>]{1,90})<", s)]
txt = [t for t in txt if t.strip()]
out.append("text nodes=%d" % len(txt))
for t in txt:
    out.append("  | " + t)

# rough element inventory
for tag in ["rect", "circle", "ellipse", "line", "path", "polygon", "text"]:
    out.append("%-8s count=%d" % (tag, len(re.findall(r"<" + tag + r"[ >]", s))))

io.open(r"D:\课题组\slm\_svg_labels.txt", "w", encoding="utf-8").write("\n".join(out))
print("done")
