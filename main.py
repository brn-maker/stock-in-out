# app.py — Stock In & Out  (Streamlit)
# Run:  pip install streamlit pillow
#       streamlit run app.py

import io
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import streamlit as st
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

# ----------------------------------------------------------------------
# Setup & persistence
# ----------------------------------------------------------------------
st.set_page_config(page_title="Stock In & Out", page_icon="📦", layout="wide")

DATA_FILE = Path("stock_data.json")
IMAGE_DIR = Path("stock_images")
IMAGE_DIR.mkdir(exist_ok=True)


def load_data() -> dict:
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text())
        except Exception:
            pass
    return {"items": []}


def save_data() -> None:
    DATA_FILE.write_text(json.dumps(st.session_state.data, indent=2))


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def get_item(item_id: str) -> Optional[dict]:
    return next((i for i in st.session_state.data["items"] if i["id"] == item_id), None)


def image_file(item: dict) -> Optional[Path]:
    p = item.get("image")
    if p and Path(p).exists():
        return Path(p)
    return None


if "data" not in st.session_state:
    st.session_state.data = load_data()
if "photo_bytes" not in st.session_state:
    st.session_state.photo_bytes = None


# ----------------------------------------------------------------------
# Image editing
# ----------------------------------------------------------------------
def edit_image(img: Image.Image, *, rotate: int, flip_h: bool, flip_v: bool,
               crop: tuple, brightness: float, contrast: float, saturation: float,
               sharpness: float, blur: float, mode: str, max_size: int) -> Image.Image:
    img = img.convert("RGB")

    if rotate % 360:
        img = img.rotate(-rotate, expand=True)          # positive = clockwise
    if flip_h:
        img = ImageOps.mirror(img)
    if flip_v:
        img = ImageOps.flip(img)

    l, r, t, b = crop
    w, h = img.size
    box = (int(w * l / 100), int(h * t / 100),
           int(w * (1 - r / 100)), int(h * (1 - b / 100)))
    if box[2] - box[0] > 10 and box[3] - box[1] > 10:
        img = img.crop(box)

    if brightness != 1.0:
        img = ImageEnhance.Brightness(img).enhance(brightness)
    if contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(contrast)
    if saturation != 1.0:
        img = ImageEnhance.Color(img).enhance(saturation)
    if sharpness != 1.0:
        img = ImageEnhance.Sharpness(img).enhance(sharpness)
    if blur > 0:
        img = img.filter(ImageFilter.GaussianBlur(blur))

    if mode == "Grayscale":
        img = ImageOps.grayscale(img).convert("RGB")
    elif mode == "Sepia":
        gray = ImageOps.grayscale(img)
        img = ImageOps.colorize(gray, black=(25, 20, 15),
                                white=(255, 240, 210), mid=(130, 90, 55))

    if max(img.size) > max_size:
        img.thumbnail((max_size, max_size))
    return img


def reset_edits() -> None:
    """Button callback – runs before widgets are created, so it's safe."""
    for k in [k for k in st.session_state.keys() if k.startswith("ed_")]:
        del st.session_state[k]


# ----------------------------------------------------------------------
# Sidebar — add stock
# ----------------------------------------------------------------------
with st.sidebar:
    st.header("➕ Add stock")
    with st.form("add_stock", clear_on_submit=True):
        new_name = st.text_input("Stock name")
        new_qty = st.number_input("Quantity", min_value=0, value=1, step=1)
        new_unit = st.text_input("Unit", value="pcs")
        add = st.form_submit_button("Add stock")

    if add:
        name = new_name.strip()
        if not name:
            st.error("Please enter a stock name.")
        elif any(i["name"].lower() == name.lower() for i in st.session_state.data["items"]):
            st.warning("That stock already exists.")
        else:
            st.session_state.data["items"].append({
                "id": uuid.uuid4().hex[:8],
                "name": name,
                "quantity": int(new_qty),
                "unit": new_unit.strip() or "pcs",
                "image": None,
                "updated": now_str(),
            })
            save_data()
            st.success(f"Added “{name}”")
            st.rerun()

    st.divider()
    st.caption("Data lives in `stock_data.json`, photos in `stock_images/`.")

# ----------------------------------------------------------------------
# Header metrics
# ----------------------------------------------------------------------
st.title("📦 Stock In & Out")

items = st.session_state.data["items"]
m1, m2, m3 = st.columns(3)
m1.metric("Stock items", len(items))
m2.metric("Total quantity", sum(i["quantity"] for i in items))
m3.metric("Items with photo", sum(1 for i in items if image_file(i)))

tab_stock, tab_photo = st.tabs(["📦 Stock", "📷 Stock photos"])

# ----------------------------------------------------------------------
# Tab 1 — stock list / stock in & out / edit quantity
# ----------------------------------------------------------------------
with tab_stock:
    items = st.session_state.data["items"]
    if not items:
        st.info("No stock yet — add one in the sidebar.")
    else:
        search = st.text_input("🔍 Search stock", "")
        visible = [i for i in items if search.strip().lower() in i["name"].lower()]
        if not visible:
            st.warning("No matching stock.")

        for item in visible:
            with st.container(border=True):
                c_img, c_main, c_actions = st.columns([1, 4, 3])

                with c_img:
                    p = image_file(item)
                    if p:
                        st.image(str(p), width=110)
                    else:
                        st.markdown("🖼️\n\n*no photo*")

                with c_main:
                    st.markdown(f"#### {item['name']}")
                    st.markdown(f"**Quantity:** {item['quantity']} {item['unit']}")
                    st.caption(f"Last updated: {item['updated']}")

                with c_actions:
                    b1, b2 = st.columns(2)
                    if b1.button("➕ In", key=f"in_{item['id']}"):
                        item["quantity"] += 1
                        item["updated"] = now_str()
                        save_data()
                        st.rerun()
                    if b2.button("➖ Out", key=f"out_{item['id']}"):
                        item["quantity"] = max(0, item["quantity"] - 1)
                        item["updated"] = now_str()
                        save_data()
                        st.rerun()

                    with st.expander("✏️ Edit quantity"):
                        with st.form(f"form_{item['id']}"):
                            q = st.number_input(
                                "New quantity", min_value=0,
                                value=int(item["quantity"]), step=1,
                                key=f"qty_{item['id']}",
                            )
                            if st.form_submit_button("Save quantity"):
                                item["quantity"] = int(q)
                                item["updated"] = now_str()
                                save_data()
                                st.rerun()

                    if st.button("🗑️ Delete", key=f"del_{item['id']}"):
                        st.session_state.data["items"] = [
                            i for i in st.session_state.data["items"] if i["id"] != item["id"]
                        ]
                        p = image_file(item)
                        if p:
                            p.unlink(missing_ok=True)
                        save_data()
                        st.rerun()

# ----------------------------------------------------------------------
# Tab 2 — take / upload & edit a photo for a named stock
# ----------------------------------------------------------------------
with tab_photo:
    items = st.session_state.data["items"]
    if not items:
        st.info("Add a stock item first.")
    else:
        labels = {f"{i['name']} — {i['quantity']} {i['unit']}": i["id"] for i in items}
        choice = st.selectbox("Which stock item?", list(labels))
        item = get_item(labels[choice])

        # reset the working photo when the user switches item
        if st.session_state.get("photo_item") != item["id"]:
            st.session_state.photo_item = item["id"]
            st.session_state.photo_bytes = None
            st.session_state.last_cam = None

        existing = image_file(item)

        c1, c2 = st.columns(2)
        with c1:
            cam = st.camera_input("📷 Take a picture")
            if cam is not None:
                cam_bytes = cam.getvalue()
                # only take it when it is a *new* shot, so "load saved photo" isn't overwritten
                if cam_bytes != st.session_state.get("last_cam"):
                    st.session_state.last_cam = cam_bytes
                    st.session_state.photo_bytes = cam_bytes
        with c2:
            up = st.file_uploader("…or upload a photo", type=["png", "jpg", "jpeg", "webp"])
            if up is not None:
                st.session_state.photo_bytes = up.getvalue()

            if existing and st.button("📂 Load saved photo for editing"):
                st.session_state.photo_bytes = existing.read_bytes()
                st.session_state.last_cam = None
                st.rerun()

            if st.session_state.photo_bytes is not None:
                if st.button("🧹 Clear working photo"):
                    st.session_state.photo_bytes = None
                    st.session_state.last_cam = None
                    st.rerun()

        if st.session_state.photo_bytes is None:
            st.caption("Take or upload a photo to start editing.")
        else:
            src = ImageOps.exif_transpose(
                Image.open(io.BytesIO(st.session_state.photo_bytes))
            ).convert("RGB")

            with st.expander("🎛️ Edit photo", expanded=True):
                r1, r2, r3 = st.columns(3)
                with r1:
                    rotate = st.slider("Rotate °", 0, 355, 0, 5, key="ed_rotate")
                    flip_h = st.checkbox("Flip horizontal", key="ed_fliph")
                    flip_v = st.checkbox("Flip vertical", key="ed_flipv")
                with r2:
                    brightness = st.slider("Brightness", 0.2, 2.0, 1.0, 0.05, key="ed_bright")
                    contrast = st.slider("Contrast", 0.2, 2.0, 1.0, 0.05, key="ed_contrast")
                    saturation = st.slider("Saturation", 0.0, 2.0, 1.0, 0.05, key="ed_sat")
                with r3:
                    sharpness = st.slider("Sharpness", 0.0, 3.0, 1.0, 0.05, key="ed_sharp")
                    blur = st.slider("Blur", 0.0, 10.0, 0.0, 0.5, key="ed_blur")
                    mode = st.selectbox("Colour mode", ["Colour", "Grayscale", "Sepia"],
                                        key="ed_mode")

                st.markdown("**Crop (%)**")
                q1, q2, q3, q4 = st.columns(4)
                crop_l = q1.slider("Left", 0, 45, 0, key="ed_cl")
                crop_r = q2.slider("Right", 0, 45, 0, key="ed_cr")
                crop_t = q3.slider("Top", 0, 45, 0, key="ed_ct")
                crop_b = q4.slider("Bottom", 0, 45, 0, key="ed_cb")

                max_size = st.slider("Max output size (px)", 200, 2000, 1200, 100,
                                     key="ed_max")

                st.button("↩️ Reset all edits", on_click=reset_edits)

            edited = edit_image(
                src,
                rotate=rotate, flip_h=flip_h, flip_v=flip_v,
                crop=(crop_l, crop_r, crop_t, crop_b),
                brightness=brightness, contrast=contrast, saturation=saturation,
                sharpness=sharpness, blur=blur, mode=mode, max_size=max_size,
            )

            p1, p2 = st.columns(2)
            p1.image(src, caption="Original")
            p2.image(edited, caption="Edited preview")

            buf = io.BytesIO()
            edited.save(buf, format="PNG")
            payload = buf.getvalue()

            a1, a2, a3 = st.columns(3)
            if a1.button("💾 Save as stock photo", type="primary"):
                path = IMAGE_DIR / f"{item['id']}.png"
                edited.save(path, format="PNG")
                item["image"] = str(path)
                item["updated"] = now_str()
                save_data()
                st.success(f"Photo saved for “{item['name']}”.")
                st.rerun()

            a2.download_button("⬇️ Download edited photo", payload,
                               file_name=f"{item['name']}.png", mime="image/png")

            if existing and a3.button("🗑️ Remove saved photo"):
                existing.unlink(missing_ok=True)
                item["image"] = None
                item["updated"] = now_str()
                save_data()
                st.rerun()
