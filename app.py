import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import io
import zipfile
import os

# 處理縮放相容性
try:
    RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:
    RESAMPLE = Image.LANCZOS

# 網頁基本設定
st.set_page_config(page_title="房仲多重浮水印工作站", page_icon="🏠", layout="wide")

# 初始化 Session State (確保跨重整仍保留資料)
if 'watermark_list' not in st.session_state:
    st.session_state.watermark_list = []

# 自動偵測與建立字體資料夾
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(CURRENT_DIR, "Fonts")
if not os.path.exists(FONTS_DIR):
    os.makedirs(FONTS_DIR)

# 輔助函式：產生文字圖片
def create_text_img(item):
    try:
        if not item["font"] or item["font"] == "default":
            font = ImageFont.load_default()
        else:
            font = ImageFont.truetype(item["font"], 80)
    except:
        font = ImageFont.load_default()
        
    lines = item["text"].split('\n')
    max_w = 0
    total_h = 0
    for line in lines:
        bbox = font.getbbox(line)
        max_w = max(max_w, bbox[2] - bbox[0])
        total_h += (bbox[3] - bbox[1]) + 15
    
    t_rgb = tuple(int(item["t_color"].lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    b_rgb = tuple(int(item["b_color"].lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    
    if item["style"] == "無底框+描邊":
        sw = 4
        img_w, img_h = max_w + sw*2 + 20, total_h + sw*2 + 20
        txt_img = Image.new('RGBA', (img_w, img_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(txt_img)
        y = 10
        for line in lines:
            bbox = font.getbbox(line)
            draw.text((10, y - bbox[1]), line, font=font, fill=t_rgb+(255,), stroke_width=sw, stroke_fill=b_rgb+(255,))
            y += (bbox[3] - bbox[1]) + 15
    else:
        pad = 35
        img_w, img_h = max_w + pad*2, total_h + pad*2
        txt_img = Image.new('RGBA', (img_w, img_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(txt_img)
        alpha = 160 if item["style"] == "半透明底框" else 255
        draw.rounded_rectangle((0, 0, img_w, img_h), radius=20, fill=b_rgb+(alpha,))
        y = pad
        for line in lines:
            bbox = font.getbbox(line)
            draw.text((pad, y - bbox[1]), line, font=font, fill=t_rgb+(255,))
            y += (bbox[3] - bbox[1]) + 15
    return txt_img

# ===== 1. 先處理照片上傳 (這是防止消失的關鍵) =====
st.title("🏠 台灣房屋 - 多重疊加發文工作站")
uploaded_photos = st.file_uploader("📂 第一步：上傳屋況照片 (支援全選)", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)

# ===== 2. 側邊欄設定區 =====
st.sidebar.header("⚙️ 發文設定")
rename_prefix = st.sidebar.text_input("照片命名開頭", "台灣房屋_捷運樂善物件")

st.sidebar.write("---")
st.sidebar.header("🎨 新增設計")
wm_type = st.sidebar.selectbox("想要新增什麼？", ["專屬文字標籤", "圖片浮水印 (Logo/Q版)"])

active_design_obj = None

if wm_type == "圖片浮水印 (Logo/Q版)":
    uploaded_wm = st.sidebar.file_uploader("上傳 PNG 浮水印檔案", type=['png'], key="uploader_wm")
    if uploaded_wm:
        img_obj = Image.open(uploaded_wm).convert("RGBA")
        active_design_obj = {"type": "image", "img": img_obj, "name": uploaded_wm.name}
        st.sidebar.image(img_obj, width=150, caption="準備新增的圖片")
else:
    text_input = st.sidebar.text_area("輸入內容", "帶看專線：0938-888-906\n(專屬顧問：劉昭佑)", key="text_input")
    
    # 字體過濾：只顯示 Fonts 資料夾內的
    fonts_map = {}
    if os.path.exists(FONTS_DIR):
        for font_file in os.listdir(FONTS_DIR):
            if font_file.lower().endswith(('.ttf', '.ttc', '.otf')):
                fonts_map[f"{os.path.splitext(font_file)[0]}"] = os.path.join(FONTS_DIR, font_file)
    
    if not fonts_map:
        fonts_map["(請先上傳字體檔)"] = "default"
        
    selected_font = st.sidebar.selectbox("選擇字體", list(fonts_map.keys()))
    text_style = st.sidebar.selectbox("底框樣式", ["半透明底框", "實色底框", "無底框+描邊"])
    t_col = st.sidebar.color_picker("文字顏色", "#FFFFFF")
    b_col = st.sidebar.color_picker("背景/邊框色", "#000000")
    
    if text_input:
        active_design_obj = {
            "type": "text", "text": text_input, "font": fonts_map[selected_font],
            "style": text_style, "t_color": t_col, "b_color": b_col
        }
        # 【即時預覽區】
        st.sidebar.write("樣式預覽：")
        st.sidebar.image(create_text_img(active_design_obj), use_container_width=True)

if st.sidebar.button("➕ 確認並加入清單", type="primary", use_container_width=True):
    if active_design_obj:
        active_design_obj["scale"] = 1.0
        active_design_obj["pos_x"] = 95
        active_design_obj["pos_y"] = 95
        st.session_state.watermark_list.append(active_design_obj)
        st.rerun() # 加入後強制更新畫面

st.sidebar.write("---")
st.sidebar.header("📝 已加入物件管理")

if not st.session_state.watermark_list:
    st.sidebar.write("清單目前是空的")
else:
    # 使用倒序顯示，最新加入的在最上面，方便調整
    for i, item in enumerate(st.session_state.watermark_list):
        d_name = f"物件 #{i+1} " + (item["name"] if item["type"] == "image" else item["text"].split('\n')[0][:8])
        with st.sidebar.expander(d_name, expanded=True):
            item["scale"] = st.slider(f"大小 (10x)", 0.1, 10.0, float(item["scale"]), 0.1, key=f"s_{i}")
            item["pos_x"] = st.slider(f"左右", 0, 100, int(item["pos_x"]), 1, key=f"x_{i}")
            item["pos_y"] = st.slider(f"上下", 0, 100, int(item["pos_y"]), 1, key=f"y_{i}")
            if st.button(f"🗑️ 移除此物件", key=f"del_{i}"):
                st.session_state.watermark_list.pop(i)
                st.rerun()

# ===== 3. 主畫面預覽區 (絕對渲染邏輯) =====
if uploaded_photos:
    st.subheader("👀 即時預覽 (第一張照片)")
    
    # 建立畫布
    base = Image.open(uploaded_photos[0]).convert("RGBA")
    ratio = 800 / base.width
    canvas = base.resize((800, int(base.height * ratio)), RESAMPLE)
    
    # 只要清單有東西就疊加
    for item in st.session_state.watermark_list:
        source = item["img"] if item["type"] == "image" else create_text_img(item)
        sw = max(1, int(source.width * item["scale"] * ratio))
        sh = max(1, int(source.height * item["scale"] * ratio))
        ready_wm = source.resize((sw, sh), RESAMPLE)
        
        px = int((canvas.width - sw) * (item["pos_x"] / 100))
        py = int((canvas.height - sh) * (item["pos_y"] / 100))
        
        overlay = Image.new('RGBA', canvas.size, (0,0,0,0))
        overlay.paste(ready_wm, (px, py), mask=ready_wm)
        canvas = Image.alpha_composite(canvas, overlay)
    
    # 這裡是最重要的一行：無論清單有沒有東西，這張照片一定要顯示出來
    st.image(canvas.convert("RGB"), use_container_width=True)

    if not st.session_state.watermark_list:
        st.info("💡 目前顯示原始照片。請從左側設計樣式並點擊「➕ 加入清單」來疊加浮水印。")

    # 批次處理按鈕
    if st.button("🚀 確認排版！一鍵處理所有照片", type="primary", use_container_width=True):
        progress = st.progress(0)
        zip_io = io.BytesIO()
        with zipfile.ZipFile(zip_io, "w", zipfile.ZIP_DEFLATED) as zf:
            for idx, photo in enumerate(uploaded_photos):
                img = Image.open(photo).convert("RGBA")
                # FB 1920 最佳化
                if img.width > 1920 or img.height > 1920:
                    r = min(1920/img.width, 1920/img.height)
                    img = img.resize((int(img.width*r), int(img.height*r)), RESAMPLE)
                
                final = img
                r_ratio = img.width / Image.open(photo).width
                
                for item in st.session_state.watermark_list:
                    s = item["img"] if item["type"] == "image" else create_text_img(item)
                    rw = max(1, int(s.width * item["scale"] * r_ratio))
                    rh = max(1, int(s.height * item["scale"] * r_ratio))
                    wm = s.resize((rw, rh), RESAMPLE)
                    fx = int((final.width - rw) * (item["pos_x"] / 100))
                    fy = int((final.height - rh) * (item["pos_y"] / 100))
                    ov = Image.new('RGBA', final.size, (0,0,0,0))
                    ov.paste(wm, (fx, fy), mask=wm)
                    final = Image.alpha_composite(final, ov)
                
                out = final.convert("RGB")
                name = f"{rename_prefix}_{idx+1:02d}.jpg" if rename_prefix else photo.name
                buf = io.BytesIO()
                out.save(buf, format='JPEG', quality=85, optimize=True)
                zf.writestr(name, buf.getvalue())
                progress.progress((idx + 1) / len(uploaded_photos))
        
        st.success("🎉 處理完成！")
        st.download_button("📥 下載 ZIP 壓縮包", zip_io.getvalue(), f"{rename_prefix}.zip", "application/zip", use_container_width=True)
else:
    st.write("---")
    st.info("👋 你好！請先上傳幾張照片，右側就會立刻出現預覽效果囉！")