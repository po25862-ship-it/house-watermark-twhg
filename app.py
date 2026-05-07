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

# 自動偵測與建立字體資料夾
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(CURRENT_DIR, "Fonts")
if not os.path.exists(FONTS_DIR):
    os.makedirs(FONTS_DIR)

# 輔助函式：產生文字圖片 (移到最前面，讓左側預覽區也能呼叫)
def create_text_img(item):
    try:
        if item["font"] == "default":
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

# 網頁基本設定
st.set_page_config(page_title="房仲多重浮水印工作站", page_icon="🏠", layout="wide")
st.title("🏠 台灣房屋 - 多重疊加發文工作站")
st.write("支援同時放置多張浮水印/文字標籤！設定好後可一鍵批次處理所有照片。")

if 'watermark_list' not in st.session_state:
    st.session_state.watermark_list = []

# ===== 側邊欄：控制面板 =====
st.sidebar.header("1. 批次命名設定")
rename_prefix = st.sidebar.text_input("照片命名開頭", "台灣房屋_捷運樂善物件")

st.sidebar.write("---")
st.sidebar.header("2. 新增物件")
wm_type = st.sidebar.selectbox("想要新增什麼？", ["圖片浮水印 (Logo/Q版)", "專屬文字標籤"])

new_obj = None

if wm_type == "圖片浮水印 (Logo/Q版)":
    uploaded_wm = st.sidebar.file_uploader("上傳 PNG 浮水印檔案", type=['png'], key="uploader_wm")
    if uploaded_wm:
        img_obj = Image.open(uploaded_wm).convert("RGBA")
        new_obj = {"type": "image", "img": img_obj, "name": uploaded_wm.name}
        
        # 新增：即時預覽圖片浮水印
        st.sidebar.markdown("**👀 浮水印預覽：**")
        st.sidebar.image(img_obj, use_container_width=True)
else:
    text_input = st.sidebar.text_area("輸入重點文字", "帶看專線：0938-888-906\n(專屬顧問：劉昭佑)", key="text_input")
    
    # 徹底移除預設字體，只掃描 Fonts 資料夾
    fonts_map = {}
    for font_file in os.listdir(FONTS_DIR):
        if font_file.lower().endswith(('.ttf', '.ttc', '.otf')):
            fonts_map[f"{os.path.splitext(font_file)[0]}"] = os.path.join(FONTS_DIR, font_file)
            
    # 防呆機制：如果資料夾是空的，給一個提示
    if not fonts_map:
        fonts_map["(請先上傳字體檔到 Fonts 資料夾)"] = "default"
        
    selected_font = st.sidebar.selectbox("選擇字體", list(fonts_map.keys()))
    text_style = st.sidebar.selectbox("樣式", ["半透明底框", "實色底框", "無底框+描邊"])
    t_col = st.color_picker("文字顏色", "#FFFFFF")
    b_col = st.color_picker("背景/邊框顏色", "#000000")
    
    if text_input:
        new_obj = {
            "type": "text", 
            "text": text_input, 
            "font": fonts_map[selected_font],
            "style": text_style,
            "t_color": t_col,
            "b_color": b_col
        }
        
        # 新增：即時預覽文字標籤
        st.sidebar.markdown("**👀 文字樣式預覽：**")
        preview_txt_img = create_text_img(new_obj)
        st.sidebar.image(preview_txt_img, use_container_width=True)

if st.sidebar.button("➕ 將此物件加入照片", type="primary", use_container_width=True):
    if new_obj:
        new_obj["scale"] = 1.0
        new_obj["pos_x"] = 95
        new_obj["pos_y"] = 95
        st.session_state.watermark_list.append(new_obj)
        st.toast("已成功加入清單！")
    else:
        st.error("請先上傳圖片或輸入文字喔！")

st.sidebar.write("---")
st.sidebar.header("3. 已加入的物件清單")

for i, item in enumerate(st.session_state.watermark_list):
    display_name = f"#{i+1} " + (item["name"] if item["type"] == "image" else item["text"].split('\n')[0][:10] + "...")
    with st.sidebar.expander(display_name, expanded=True):
        item["scale"] = st.slider(f"大小縮放 (最高10倍)", 0.1, 10.0, float(item["scale"]), 0.1, key=f"scale_{i}")
        item["pos_x"] = st.slider(f"左右位置", 0, 100, int(item["pos_x"]), 1, key=f"x_{i}")
        item["pos_y"] = st.slider(f"上下位置", 0, 100, int(item["pos_y"]), 1, key=f"y_{i}")
        if st.button(f"🗑️ 移除此物件", key=f"del_{i}"):
            st.session_state.watermark_list.pop(i)
            st.rerun()

# ===== 主畫面 =====
uploaded_photos = st.file_uploader("📂 上傳屋況照片 (支援全選批次處理)", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)

if uploaded_photos:
    st.subheader("👀 第一張照片預覽效果")
    preview_base = Image.open(uploaded_photos[0]).convert("RGBA")
    p_ratio = 800 / preview_base.width
    p_h = int(preview_base.height * p_ratio)
    preview_canvas = preview_base.resize((800, p_h), RESAMPLE)
    
    if not st.session_state.watermark_list:
        # 修正：如果清單被刪光，照片依然保留，只顯示溫馨提示
        st.info("💡 提示：目前尚未加入任何浮水印或文字，所以只顯示原始照片。請從左側設計並加入！")
    else:
        for item in st.session_state.watermark_list:
            wm_source = item["img"] if item["type"] == "image" else create_text_img(item)
            w_w = max(1, int(wm_source.width * item["scale"] * p_ratio))
            w_h = max(1, int(wm_source.height * item["scale"] * p_ratio))
            wm_ready = wm_source.resize((w_w, w_h), RESAMPLE)
            
            fx = int((preview_canvas.width - w_w) * (item["pos_x"] / 100))
            fy = int((preview_canvas.height - w_h) * (item["pos_y"] / 100))
            
            overlay = Image.new('RGBA', preview_canvas.size, (0,0,0,0))
            overlay.paste(wm_ready, (fx, fy), mask=wm_ready)
            preview_canvas = Image.alpha_composite(preview_canvas, overlay)
        
    st.image(preview_canvas.convert("RGB"), use_container_width=True)
    
    if st.button("🚀 確認所有排版，開始批次處理 (FB畫質最佳化)！", type="primary", use_container_width=True):
        progress_bar = st.progress(0)
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for idx, photo in enumerate(uploaded_photos):
                base = Image.open(photo).convert("RGBA")
                
                # FB 1920 最佳化
                m_size = 1920
                if base.width > m_size or base.height > m_size:
                    r = min(m_size/base.width, m_size/base.height)
                    base = base.resize((int(base.width*r), int(base.height*r)), RESAMPLE)
                
                r_ratio = base.width / Image.open(photo).width
                final_canvas = base
                
                for item in st.session_state.watermark_list:
                    wm_s = item["img"] if item["type"] == "image" else create_text_img(item)
                    rw = max(1, int(wm_s.width * item["scale"] * r_ratio))
                    rh = max(1, int(wm_s.height * item["scale"] * r_ratio))
                    wm_f = wm_s.resize((rw, rh), RESAMPLE)
                    
                    px = int((final_canvas.width - rw) * (item["pos_x"] / 100))
                    py = int((final_canvas.height - rh) * (item["pos_y"] / 100))
                    
                    ov = Image.new('RGBA', final_canvas.size, (0,0,0,0))
                    ov.paste(wm_f, (px, py), mask=wm_f)
                    final_canvas = Image.alpha_composite(final_canvas, ov)
                
                out_img = final_canvas.convert("RGB")
                out_name = f"{rename_prefix}_{idx+1:02d}.jpg" if rename_prefix else photo.name
                img_io = io.BytesIO()
                out_img.save(img_io, format='JPEG', quality=85, optimize=True)
                zf.writestr(out_name, img_io.getvalue())
                progress_bar.progress((idx + 1) / len(uploaded_photos))
        
        st.success("🎉 處理完成！")
        st.download_button("📥 下載處理完成的照片包 (ZIP)", zip_buf.getvalue(), f"{rename_prefix}.zip", "application/zip", use_container_width=True)