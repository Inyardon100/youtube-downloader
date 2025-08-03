# app.py (v3.0 - 안정성 최우선)

import streamlit as st
import yt_dlp
import os
import re

# --- 페이지 기본 설정 ---
st.set_page_config(page_title="Pro Downloader", page_icon="🚀", layout="centered")

# --- 설정값 정의 ---
VIDEO_FORMATS = { "mp4": "MP4 (권장)", "mkv": "MKV (고품질)", "webm": "WebM (웹 최적화)" }
AUDIO_FORMATS = { "mp3": "MP3 (일반)", "m4a": "M4A (고음질)", "flac": "FLAC (무손실)", "wav": "WAV (무압축)" }
AUDIO_QUALITY_MAP = { "Best (최고 음질)": "0", "High (256k)": "2", "Standard (192k)": "5", "Low (128k)": "7" }

# --- 핵심 함수들 ---
@st.cache_data(ttl=3600)
def fetch_video_info(url):
    try:
        ydl_opts = {'quiet': True, 'no_warnings': True, 'skip_download': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        st.error(f"정보 조회 오류: {e}")
        return None

def get_available_formats(video_info):
    formats = video_info.get('formats', [])
    res_fps_map = {}
    for f in formats:
        if f.get('vcodec') != 'none' and f.get('height'):
            height = f['height']
            res = f'{height}p'
            fps = int(f.get("fps", 0))
            if fps > 0:
                if res not in res_fps_map:
                    res_fps_map[res] = set()
                res_fps_map[res].add(fps)
    sorted_res = sorted(res_fps_map.keys(), key=lambda x: int(x[:-1]), reverse=True)
    for res in res_fps_map:
        res_fps_map[res] = sorted(list(res_fps_map[res]), reverse=True)
    return sorted_res, res_fps_map

# --- 웹사이트 UI 구성 ---
st.title("🚀 Pro Downloader")
st.caption("v3.0 (Stability First)")

if 'video_info' not in st.session_state: st.session_state.video_info = None
if 'download_result' not in st.session_state: st.session_state.download_result = None

# 1. URL 입력
url = st.text_input("YouTube 영상 링크를 붙여넣으세요:", key="url_input")

if st.button("정보 가져오기", use_container_width=True, type="primary"):
    st.session_state.download_result = None; st.session_state.video_info = None
    if url:
        with st.spinner("영상 정보를 가져오는 중..."):
            info = fetch_video_info(url)
            if info: st.session_state.video_info = info
            else: st.error("영상 정보를 가져올 수 없습니다. URL을 확인해주세요.")
    else:
        st.warning("URL을 입력해주세요.")

# 2. 영상 정보 및 다운로드 옵션 표시
if st.session_state.video_info:
    info = st.session_state.video_info
    
    col1, col2 = st.columns([1, 2])
    with col1:
        thumbnail_url = info.get('thumbnails', [{}])[-1].get('url')
        if thumbnail_url: st.image(thumbnail_url)
    with col2:
        st.subheader(info.get('title', ''))
        st.caption(f"채널: {info.get('channel', '')} | 길이: {int(info.get('duration', 0)//60)}:{int(info.get('duration', 0)%60):02d}")

    st.divider()
    st.subheader("다운로드 옵션")
    
    download_type = st.radio("다운로드 형식", ("영상 + 음성", "음원만"), horizontal=True, key="download_type_radio")

    if download_type == "영상 + 음성":
        sorted_res, res_fps_map = get_available_formats(info)
        col_q, col_f, col_e = st.columns(3)
        with col_q: selected_res = st.selectbox("화질", sorted_res, key="quality_select")
        with col_f:
            available_fps = res_fps_map.get(selected_res, [60, 30])
            selected_fps = st.selectbox("프레임 (사용 가능)", available_fps, key="fps_select")
        with col_e: selected_ext = st.selectbox("파일 형식", list(VIDEO_FORMATS.keys()), format_func=lambda x: VIDEO_FORMATS[x], key="video_ext")
    else:
        col_a, col_b = st.columns(2)
        with col_a: selected_ext = st.selectbox("음원 형식", list(AUDIO_FORMATS.keys()), format_func=lambda x: AUDIO_FORMATS[x], key="audio_ext")
        with col_b:
            is_lossless = selected_ext in ['flac', 'wav']
            selected_quality_str = st.selectbox("음원 품질", list(AUDIO_QUALITY_MAP.keys()), key="audio_quality", disabled=is_lossless, help="무손실 형식은 항상 최고 음질로 저장됩니다.")

    if st.button("다운로드 시작", use_container_width=True):
        progress_bar = st.progress(0, text="다운로드를 준비 중입니다...")
        
        def progress_hook(d):
            if d['status'] == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate')
                if total: progress_bar.progress(d['downloaded_bytes'] / total, text=f"다운로드 중... {int(d['downloaded_bytes'] / total * 100)}%")
            elif d['status'] == 'finished':
                 progress_bar.progress(1.0, text="파일 처리 및 병합 중...")

        # 파일 이름 오류를 원천적으로 방지
        info_dict = yt_dlp.YoutubeDL({'quiet': True, 'restrictfilenames': True}).extract_info(url, download=False)
        safe_title = info_dict['title']
        final_filename = f"{safe_title}.{selected_ext}"

        ydl_opts = {
            'progress_hooks': [progress_hook],
            'ffmpeg_location': '/usr/bin/ffmpeg',
            'outtmpl': f"{safe_title}.%(ext)s",
            'restrictfilenames': True,
        }

        if download_type == "영상 + 음성":
            res_val = selected_res.replace('p', '')
            ydl_opts['format'] = f'bestvideo[height<={res_val}][fps={selected_fps}]+bestaudio/bestvideo[height<={res_val}]+bestaudio/best'
            ydl_opts['merge_output_format'] = selected_ext
        else: # 음원만
            audio_quality = AUDIO_QUALITY_MAP.get(selected_quality_str, "5") if not is_lossless else "0"
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': selected_ext, 'preferredquality': audio_quality}]

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([url])

            with open(final_filename, "rb") as file: file_bytes = file.read()
            st.session_state.download_result = { "file_name": final_filename, "file_bytes": file_bytes }
            os.remove(final_filename)
            progress_bar.empty()

        except Exception as e:
            st.error(f"다운로드 중 오류가 발생했습니다. (오류: {e})")

# 3. 다운로드 버튼 표시
if st.session_state.download_result:
    res = st.session_state.download_result
    st.success(f"'{res['file_name']}' 다운로드가 준비되었습니다!")
    st.download_button(
        label="📥 파일 다운로드", data=res['file_bytes'],
        file_name=res['file_name'], mime="application/octet-stream",
        use_container_width=True
    )
