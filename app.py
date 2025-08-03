# app.py (v2.9)

import streamlit as st
import yt_dlp
import os
import re
import subprocess # FFmpeg를 직접 제어하기 위해 추가

# --- 페이지 기본 설정 ---
st.set_page_config(page_title="Pro Downloader", page_icon="🚀", layout="centered")

# --- 설정값 정의 ---
VIDEO_FORMATS = {
    "mp4": "MP4 (권장, 높은 호환성)", "mkv": "MKV (고품질, 다중트랙 지원)",
    "webm": "WebM (웹 최적화, 고효율)", "mov": "MOV (Apple, 영상 편집용)"
}
AUDIO_FORMATS = {
    "mp3": "MP3 (가장 일반적인 형식)", "m4a": "M4A (AAC 코덱, 좋은 음질)",
    "flac": "FLAC (무손실 음원, 원음 그대로)", "wav": "WAV (무압축 원음, 용량 큼)"
}
AUDIO_QUALITY_MAP_BITRATE = {
    "Best (최고 음질)": "320k", "High (≈256k)": "256k", 
    "Standard (≈192k)": "192k", "Low (≈128k)": "128k"
}
AUDIO_QUALITY_MAP_FFMPEG = {
    "Best (최고 음질)": "0", "High (≈256k)": "2", 
    "Standard (≈192k)": "5", "Low (≈128k)": "7"
}
FRAME_RATES = [60, 45, 30, 24, 15]

# --- 핵심 함수들 ---
@st.cache_data(ttl=3600)
def fetch_video_info(url):
    try:
        ydl_opts = {'quiet': True, 'no_warnings': True, 'skip_download': True}
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
st.caption("v2.9")

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
        selected_audio_quality_str = st.selectbox("음원 품질", list(AUDIO_QUALITY_MAP_BITRATE.keys()), key="video_audio_quality")
    else:
        st.write("##### 🎧 음원 설정")
        col_a, col_b = st.columns(2)
        with col_a: selected_ext = st.selectbox("음원 형식", list(AUDIO_FORMATS.keys()), format_func=lambda x: AUDIO_FORMATS[x], key="audio_ext")
        with col_b:
            is_lossless = selected_ext in ['flac', 'wav']
            selected_quality_str = st.selectbox("음원 품질", list(AUDIO_QUALITY_MAP_BITRATE.keys()), key="audio_quality", disabled=is_lossless, help="무손실 형식(flac, wav)은 항상 최고 음질로 저장됩니다.")

    if st.button("다운로드 시작", use_container_width=True):
        progress_bar = st.progress(0, text="다운로드를 준비 중입니다...")
        
        info_dict = yt_dlp.YoutubeDL({'quiet': True, 'restrictfilenames': True}).extract_info(url, download=False)
        base_filename = info_dict['title']
        final_filename = f"{base_filename}.{selected_ext}"
        temp_video_file = f"{base_filename}_video.tmp"
        temp_audio_file = f"{base_filename}_audio.tmp"
        
        try:
            if download_type == "영상 + 음성":
                # 1단계: 영상 다운로드
                progress_bar.progress(0.1, text="최고 화질 영상 다운로드 중...")
                res_val = selected_res.replace('p', '')
                ydl_opts_video = {'format': f'bestvideo[height<={res_val}]', 'outtmpl': temp_video_file, 'quiet': True}
                with yt_dlp.YoutubeDL(ydl_opts_video) as ydl: ydl.download([url])

                # 2단계: 음원 다운로드
                progress_bar.progress(0.5, text="최고 음질 음원 다운로드 중...")
                ydl_opts_audio = {'format': 'bestaudio', 'outtmpl': temp_audio_file, 'quiet': True}
                with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl: ydl.download([url])

                # 3단계: FFmpeg로 직접 변환 및 병합
                progress_bar.progress(0.8, text="파일 변환 및 병합 중 (시간이 걸릴 수 있습니다)...")
                audio_bitrate = AUDIO_QUALITY_MAP_BITRATE.get(selected_audio_quality_str, "192k")
                
                ffmpeg_command = [
                    'ffmpeg', '-y',
                    '-i', f"{temp_video_file}.{ydl_opts_video['format'].split('[ext=')[-1].split(']')[0] if '[ext=' in ydl_opts_video['format'] else 'mp4'}", # 실제 확장자 추정
                    '-i', f"{temp_audio_file}.{ydl_opts_audio['format'].split('[ext=')[-1].split(']')[0] if '[ext=' in ydl_opts_audio['format'] else 'm4a'}",
                    '-c:v', 'libx264', '-preset', 'medium', '-crf', '22', # 비디오 인코딩
                    '-vf', f'fps={selected_fps}', # 프레임 변환
                    '-c:a', 'aac', '-b:a', audio_bitrate, # 오디오 인코딩
                    final_filename
                ]
                # 임시 파일 이름 수정 (yt-dlp가 확장자를 붙이므로)
                video_ext = yt_dlp.YoutubeDL(ydl_opts_video).extract_info(url, download=False)['ext']
                audio_ext = yt_dlp.YoutubeDL(ydl_opts_audio).extract_info(url, download=False)['ext']
                
                ffmpeg_command[3] = f"{temp_video_file}.{video_ext}"
                ffmpeg_command[5] = f"{temp_audio_file}.{audio_ext}"
                
                subprocess.run(ffmpeg_command, check=True, capture_output=True)

            else: # 음원만
                progress_bar.progress(0.3, text="최고 음질 음원 다운로드 중...")
                ydl_opts_audio = {'format': 'bestaudio/best', 'outtmpl': temp_audio_file, 'quiet': True}
                with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl: ydl.download([url])

                progress_bar.progress(0.7, text="음원 형식 변환 중...")
                audio_quality_ffmpeg = AUDIO_QUALITY_MAP_FFMPEG.get(selected_quality_str, "5")
                audio_ext_temp = yt_dlp.YoutubeDL(ydl_opts_audio).extract_info(url, download=False)['ext']
                
                ffmpeg_command = ['ffmpeg', '-y', '-i', f"{temp_audio_file}.{audio_ext_temp}", '-vn']
                if not is_lossless:
                    ffmpeg_command.extend(['-c:a', selected_ext if selected_ext != 'm4a' else 'aac', '-b:a', f'{audio_quality_ffmpeg}']) # for mp3, etc.
                else:
                    ffmpeg_command.extend(['-c:a', selected_ext]) # for flac, wav
                ffmpeg_command.append(final_filename)
                
                # m4a는 aac 코덱을 사용
                if selected_ext == 'm4a':
                    ffmpeg_command[ffmpeg_command.index('-c:a')+1] = 'aac'

                subprocess.run(ffmpeg_command, check=True, capture_output=True)

            progress_bar.progress(1.0, text="완료!")
            with open(final_filename, "rb") as file: file_bytes = file.read()
            st.session_state.download_result = { "file_name": final_filename, "file_bytes": file_bytes }

        except Exception as e:
            st.error(f"다운로드 중 오류가 발생했습니다. (오류: {e})")
        finally:
            # 모든 임시 파일 및 최종 파일 정리
            for f in os.listdir('.'):
                if f.startswith(base_filename):
                    os.remove(f)
            progress_bar.empty()

# 3. 다운로드 버튼 표시
if st.session_state.download_result:
    res = st.session_state.download_result
    st.success(f"'{res['file_name']}' 다운로드가 준비되었습니다!")
    st.download_button(
        label="📥 파일 다운로드", data=res['file_bytes'],
        file_name=res['file_name'], mime="application/octet-stream",
        use_container_width=True
    )
