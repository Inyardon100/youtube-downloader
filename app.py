# app.py (진짜 최종 버전 v2.7 - 오류 완벽 수정)

import streamlit as st
import yt_dlp
import os
import re
from PIL import Image
import requests
from io import BytesIO

# --- 설정값 정의 ---
st.set_page_config(page_title="Pro Downloader", page_icon="🚀", layout="centered")

VIDEO_FORMATS = {
    "mp4": "MP4 (권장, 높은 호환성)", "mkv": "MKV (고품질, 다중트랙 지원)",
    "webm": "WebM (웹 최적화, 고효율)", "mov": "MOV (Apple, 영상 편집용)",
    "avi": "AVI (구형, 범용적)", "flv": "FLV (플래시, 구형 웹)"
}
AUDIO_FORMATS = {
    "mp3": "MP3 (가장 일반적인 형식)", "m4a": "M4A (AAC 코덱, 좋은 음질)",
    "flac": "FLAC (무손실 음원, 원음 그대로)", "wav": "WAV (무압축 원음, 용량 큼)",
    "opus": "Opus (고효율, 스트리밍용)", "aac": "AAC (MP3보다 발전된 형식)"
}
AUDIO_QUALITY_MAP = {
    "Best (최고 음질)": "0", "High (≈256k)": "2", 
    "Standard (≈192k)": "5", "Low (≈128k)": "7"
}
FRAME_RATES = [60, 45, 30, 24, 15]

# --- 핵심 함수들 ---
@st.cache_data(ttl=3600)
def fetch_video_info(url):
    try:
        ydl_opts = {'quiet': True, 'no_warnings': True, 'skip_download': True, 'ffmpeg_location': '/usr/bin/ffmpeg'}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception:
        return None

def get_available_resolutions(video_info):
    formats = video_info.get('formats', [])
    resolutions = set()
    for f in formats:
        if f.get('vcodec') != 'none' and f.get('height'):
            resolutions.add(f'{f["height"]}p')
    return sorted(list(resolutions), key=lambda x: int(x[:-1]), reverse=True)

# --- 웹사이트 UI 구성 ---
st.title("🚀 Pro YouTube Downloader")
st.caption("v2.7 The Real Final")

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
        st.write("##### 🎬 영상 설정")
        col_q, col_f, col_e = st.columns(3)
        with col_q: selected_res = st.selectbox("화질", get_available_resolutions(info), key="quality_select")
        with col_f: selected_fps = st.selectbox("프레임 (강제 변환)", FRAME_RATES, key="fps_select")
        with col_e: selected_ext = st.selectbox("파일 형식", list(VIDEO_FORMATS.keys()), format_func=lambda x: VIDEO_FORMATS[x], key="video_ext")
        st.write("##### 🎧 음원 설정 (영상에 포함될)")
        selected_audio_quality_str = st.selectbox("음원 품질", list(AUDIO_QUALITY_MAP.keys()), key="video_audio_quality")
    else:
        st.write("##### 🎧 음원 설정")
        col_a, col_b = st.columns(2)
        with col_a: selected_ext = st.selectbox("음원 형식", list(AUDIO_FORMATS.keys()), format_func=lambda x: AUDIO_FORMATS[x], key="audio_ext")
        with col_b:
            is_lossless = selected_ext in ['flac', 'wav']
            selected_quality_str = st.selectbox("음원 품질", list(AUDIO_QUALITY_MAP.keys()), key="audio_quality", disabled=is_lossless, help="무손실 형식(flac, wav)은 항상 최고 음질로 저장됩니다.")

    if st.button("다운로드 시작", use_container_width=True):
        progress_bar = st.progress(0, text="다운로드를 준비 중입니다...")
        
        # 파일 이름에 포함될 수 있는 특수문자 및 이모지 문제 해결
        ydl_opts = {
            'progress_hooks': [progress_hook],
            'ffmpeg_location': '/usr/bin/ffmpeg',
            'outtmpl': '%(title)s.%(ext)s',
            'restrictfilenames': True, # 이 옵션이 파일 이름 오류를 방지함
            'postprocessors': []
        }

        def progress_hook(d):
            if d['status'] == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate')
                if total: progress_bar.progress(d['downloaded_bytes'] / total, text=f"다운로드 중... {int(d['downloaded_bytes'] / total * 100)}%")
            elif d['status'] == 'finished':
                 progress_bar.progress(1.0, text="파일 처리 및 변환 중...")

        if download_type == "영상 + 음성":
            res_val = selected_res.replace('p', '')
            audio_quality_selector = AUDIO_QUALITY_MAP.get(selected_audio_quality_str, "0")
            
            ydl_opts['format'] = f'bestvideo[height<={res_val}]+bestaudio/bestvideo+bestaudio/best'
            ydl_opts['merge_output_format'] = selected_ext
            
            # 후처리 대신 ffmpeg_args를 사용하여 안정성 확보
            ydl_opts['postprocessor_args'] = {
                'video': ['-vf', f'fps={selected_fps}'],
                'audio': ['-q:a', audio_quality_selector]
            }
        else:
            audio_quality = AUDIO_QUALITY_MAP.get(selected_quality_str, "5") if not is_lossless else "0"
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'].append({'key': 'FFmpegExtractAudio', 'preferredcodec': selected_ext, 'preferredquality': audio_quality})

        try:
            # 다운로드 전, 파일 이름을 미리 가져와서 사용
            info_dict = yt_dlp.YoutubeDL({'quiet': True, 'restrictfilenames': True}).extract_info(url, download=False)
            final_filename = f"{info_dict['title']}.{selected_ext}"

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
