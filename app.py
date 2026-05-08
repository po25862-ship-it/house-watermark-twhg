import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io
import zipfile
import os
import time

# 處理舊版與新版 PIL 的縮放濾鏡相容性
try:
    RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:
    RESAMPLE = Image.LANCZOS

# 網頁基本設定
st.set_page_config(page_title="房仲多重浮水印工作站", page_icon="🏠", layout="wide")

# 初始化 Session State
if 'watermark_list' not in st.session_state:
    st.session_state.watermark_list = []

# 路徑設定與自動建立資料夾
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(CURRENT_DIR, "Fonts")
WM_DIR = os.path.join(CURRENT_DIR, "Watermarks")

for d in [FONTS_DIR, WM_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

# 輔助函式：產生文字圖片 (🚀 這裡修正了隱形邊界問題)
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
    line_spacing = 15 # 行距
    
    # 第一階段：精準計算文字實際佔用的寬高，去除多餘的底部空白
    for i, line in enumerate(lines):
        bbox = font.getbbox(line)
        max_w = max(max_w, bbox[2] - bbox[0])
        total_h += (bbox[3] - bbox[1])
        # 只有不是最後一行時，才加上行距
        if i < len(lines) - 1:
            total_h += line_spacing
            
    t_rgb = tuple(int(item["t_color"].lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    b_rgb = tuple(int(item["b_color"].lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    
    if item["style"] == "無底框+描邊":
        sw = 4
        # 將透明邊界縮減到極限，只保留給描邊用的空間
        pad = sw + 2 
        img_w, img_h = max_w + pad*2, total_h + pad*2
        txt_img = Image.new('RGBA', (img_w, img_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(txt_img)
        y = pad
        for i, line in enumerate(lines):
            bbox = font.getbbox(line)
            draw.text((pad, y - bbox[1]), line, font=font, fill=t_rgb+(255,), stroke_width=sw, stroke_fill=b_rgb+(255,))
            y += (bbox[3] - bbox[1]) + line_spacing
    else:
        # 有底框的版本因為需要色塊背景，保留原本的 Padding
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
            y += (bbox[3] - bbox[1]) + line_spacing
            
    return txt_img

# ===== 主畫面：照片上傳區 =====
st.title("🏠 台灣房屋 - 多重疊加發文工作站")
uploaded_photos = st.file_uploader("📂 第一步：上傳屋況照片 (更換物件時，直接點 X 刪除舊照片再上傳新的)", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)

# ===== 側邊欄：設計與控制面板 =====
st.sidebar.header("⚙️ 輸出命名設定")
rename_prefix = st.sidebar.text_input("照片批次命名開頭", "台灣房屋_A7捷運樂善物件")

st.sidebar.write("---")
st.sidebar.header("🎨 新增設計物件")

add_mode = st.sidebar.radio("選擇新增方式", ["從常用圖庫選取", "上傳新圖片", "設計文字標籤"])

active_design_obj = None

if add_mode == "從常用圖庫選取":
    preset_files = [f for f in os.listdir(WM_DIR) if f.lower().endswith('.png')]
    if not preset_files:
        st.sidebar.warning("圖庫目前是空的。請切換到「上傳新圖片」並點擊記憶圖庫！")
    else:
        selected_wm_file = st.sidebar.selectbox("選擇預設 Logo/Q版圖", preset_files)
        if selected_wm_file:
            img_path = os.path.join(WM_DIR, selected_wm_file)
            img_obj = Image.open(img_path).convert("RGBA")
            active_design_obj = {"type": "image", "img": img_obj, "name": selected_wm_file}
            st.sidebar.image(img_obj, width=150, caption=f"預覽：{selected_wm_file}")

elif add_mode == "上傳新圖片":
    uploaded_wm = st.sidebar.file_uploader("上傳 PNG 浮水印", type=['png'], key="manual_up")
    if uploaded_wm:
        img_obj = Image.open(uploaded_wm).convert("RGBA")
        active_design_obj = {"type": "image", "img": img_obj, "name": uploaded_wm.name}
        st.sidebar.image(img_obj, width=150)
        
        if st.sidebar.button("💾 記憶此圖（加入常用圖庫）"):
            save_path = os.path.join(WM_DIR, uploaded_wm.name)
            with open(save_path, "wb") as f:
                f.write(uploaded_wm.getbuffer())
            st.sidebar.success("✅ 已成功記憶！以後可以直接從圖庫選取。")
            time.sleep(1)
            st.rerun()

else:
    st.sidebar.subheader("文字內容設計")
    template_option = st.sidebar.selectbox("📋 選擇快速範本", [
        "自定義輸入", "帶看專線範本", "店址資訊範本", "FB廣告精簡版"
    ])
    
    default_text = ""
    if template_option == "帶看專線範本":
        default_text = "帶看專線：0938-888-906\n專屬顧問：劉昭佑"
    elif template_option == "店址資訊範本":
        default_text = "台灣房屋 捷運樂善直營店\n預約賞屋：0938-888-906"
    elif template_option == "FB廣告精簡版":
        default_text = "🏠 精選物件 歡迎預約\n📞 0938-888-906 劉昭佑"
    
    text_input = st.sidebar.text_area("編輯文字內容", default_text if template_option != "自定義輸入" else "請輸入文字內容", key="text_input")
    
    fonts_map = {}
    if os.path.exists(FONTS_DIR):
        for font_file in os.listdir(FONTS_DIR):
            if font_file.lower().endswith(('.ttf', '.ttc', '.otf')):
                fonts_map[f"{os.path.splitext(font_file)[0]}"] = os.path.join(FONTS_DIR, font_file)
    
    if not fonts_map: fonts_map["(請先將字體檔放入 Fonts 資料夾)"] = "default"
    selected_font = st.sidebar.selectbox("選擇字體", list(fonts_map.keys()))
    text_style = st.sidebar.selectbox("底框樣式", ["半透明底框", "實色底框", "無底框+描邊"])
    t_col = st.sidebar.color_picker("文字顏色", "#FFFFFF")
    b_col = st.sidebar.color_picker("背景/邊框色", "#000000")
    
    if text_input:
        active_design_obj = {
            "type": "text", "text": text_input, "font": fonts_map[selected_font],
            "style": text_style, "t_color": t_col, "b_color": b_col
        }
        st.sidebar.image(create_text_img(active_design_obj), use_container_width=True)

if st.sidebar.button("➕ 將此物件加入畫面", type="primary", use_container_width=True):
    if active_design_obj:
        active_design_obj["scale"] = 1.0
        active_design_obj["pos_x"] = 95
        active_design_obj["pos_y"] = 95
        st.session_state.watermark_list.append(active_design_obj)
        st.rerun()

st.sidebar.write("---")
st.sidebar.header("📝 已加入的排版圖層")

if not st.session_state.watermark_list:
    st.sidebar.write("目前畫面無任何圖層")
else:
    for i, item in enumerate(st.session_state.watermark_list):
        d_name = f"圖層 #{i+1} " + (item["name"] if item["type"] == "image" else item["text"].split('\n')[0][:10])
        with st.sidebar.expander(d_name, expanded=True):
            item["scale"] = st.number_input(f"放大倍率 (1.0為原尺寸)", min_value=0.1, max_value=20.0, value=float(item["scale"]), step=0.1, format="%.1f", key=f"s_{i}")
            item["pos_x"] = st.slider(f"左右位置", 0, 100, int(item["pos_x"]), 1, key=f"x_{i}")
            item["pos_y"] = st.slider(f"上下位置", 0, 100, int(item["pos_y"]), 1, key=f"y_{i}")
            if st.button(f"🗑️ 刪除此圖層", key=f"del_{i}"):
                st.session_state.watermark_list.pop(i)
                st.rerun()

# ===== 主畫面：即時預覽與輸出區 =====
if uploaded_photos:
    st.subheader("👀 即時預覽 (目前顯示第一張)")
    raw_preview = Image.open(uploaded_photos[0])
    fixed_preview = ImageOps.exif_transpose(raw_preview)
    base = fixed_preview.convert("RGBA")
    
    ratio = 800 / base.width
    canvas = base.resize((800, int(base.height * ratio)), RESAMPLE)
    
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
    
    st.image(canvas.convert("RGB"), use_container_width=True)

    if st.button("🚀 確認版型！一鍵產出所有照片 (FB畫質最佳化)", type="primary", use_container_width=True):
        progress = st.progress(0)
        zip_io = io.BytesIO()
        with zipfile.ZipFile(zip_io, "w", zipfile.ZIP_DEFLATED) as zf:
            for idx, photo in enumerate(uploaded_photos):
                raw_img = Image.open(photo)
                fixed_img = ImageOps.exif_transpose(raw_img)
                img = fixed_img.convert("RGBA")
                
                if img.width > 1920 or img.height > 1920:
                    r = min(1920/img.width, 1920/img.height)
                    img = img.resize((int(img.width*r), int(img.height*r)), RESAMPLE)
                
                final = img
                r_ratio = img.width / fixed_img.width
                
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
        
        st.success("🎉 處理完成！請點擊下方按鈕下載打包檔。")
        st.download_button("📥 下載處理完成的照片包 (ZIP)", zip_io.getvalue(), f"{rename_prefix}.zip", "application/zip", use_container_width=True)
else:
    st.info("👋 嗨！請先將要發文的屋況照片拖曳進來，就可以開始排版囉！換新物件時只需刪除舊照片，排好的版型都會自動保留。")
