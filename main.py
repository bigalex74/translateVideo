import os
import asyncio
import json
import shutil
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip
from moviepy.audio.fx.all import volumex
from faster_whisper import WhisperModel
from deep_translator import GoogleTranslator
import edge_tts

async def generate_tts(text, output_file, voice="ru-RU-SvetlanaNeural", rate="+0%"):
    """Генерация аудио из текста с помощью edge-tts."""
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(output_file)

def extract_audio(video_path, audio_path):
    """Извлекает аудио из видео."""
    print(f"Извлечение аудио из {video_path}...")
    video = VideoFileClip(video_path)
    video.audio.write_audiofile(audio_path, logger=None)
    video.close()

def transcribe_audio(audio_path, model_size="base"):
    """Распознает речь в аудиофайле с таймкодами."""
    print(f"Распознавание речи (модель {model_size})...")
    # Используем CPU, т.к. видеокарты нет. Задействуем все потоки процессора для скорости.
    model = WhisperModel(model_size, device="cpu", compute_type="int8", cpu_threads=os.cpu_count())
    segments, info = model.transcribe(audio_path, beam_size=5)
    
    transcribed_segments = []
    for segment in segments:
        transcribed_segments.append({
            "start": segment.start,
            "end": segment.end,
            "text": segment.text.strip()
        })
    return transcribed_segments

def translate_segments(segments):
    """Переводит распознанные фрагменты на русский."""
    print("Перевод текста...")
    translator = GoogleTranslator(source='auto', target='ru')
    translated_segments = []
    for seg in segments:
        # Избегаем пустых строк
        if not seg["text"]:
            continue
        try:
            translated_text = translator.translate(seg["text"])
            translated_segments.append({
                "start": seg["start"],
                "end": seg["end"],
                "text": translated_text
            })
        except Exception as e:
            print(f"Ошибка перевода ({seg['text']}): {e}")
            translated_segments.append({
                "start": seg["start"],
                "end": seg["end"],
                "text": ""
            })
    return translated_segments

async def create_russian_audio_track(segments, original_audio_path, temp_dir="temp_audio"):
    """Генерирует озвучку и сводит ее с приглушенным фоном."""
    print("Генерация озвучки и сведение...")
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    # Загружаем оригинальное аудио и приглушаем его (ducking)
    original_audio = AudioFileClip(original_audio_path)
    # Уменьшаем громкость оригинального аудио (оставляем ~15% громкости)
    ducked_audio = volumex(original_audio, 0.15)
    
    audio_clips = [ducked_audio]

    for i, seg in enumerate(segments):
        if not seg["text"]:
            continue
            
        tts_file = os.path.join(temp_dir, f"tts_{i}.mp3")
        temp_tts_file = os.path.join(temp_dir, f"temp_{i}.mp3")
        
        # Динамическая подгонка времени
        try:
            # 1. Генерируем с базовой скоростью (базово +15% как вы просили)
            base_rate = 15
            await generate_tts(seg["text"], temp_tts_file, rate=f"+{base_rate}%")
            
            # Замеряем получившуюся длину
            temp_clip = AudioFileClip(temp_tts_file)
            tts_duration = temp_clip.duration
            temp_clip.close()
            
            target_duration = seg["end"] - seg["start"]
            
            # 2. Если даже базовая скорость не влезает в тайминг - ускоряем сильнее
            if tts_duration > target_duration:
                # Вычисляем дополнительное ускорение
                speed_ratio = tts_duration / target_duration
                # Добавляем к базовой скорости
                total_speed = int((1 + (base_rate/100)) * speed_ratio * 100) - 100
                # Ограничиваем максимальное ускорение (например, до +80%), чтобы речь оставалась разборчивой
                final_rate = min(total_speed, 80)
                rate_str = f"+{final_rate}%"
                
                print(f"[{i}] Фраза длиннее оригинала. Динамическое ускорение: {rate_str}")
                await generate_tts(seg["text"], tts_file, rate=rate_str)
                os.remove(temp_tts_file)
            else:
                # Если влезает, просто перезаписываем/переименовываем
                os.replace(temp_tts_file, tts_file)
                
        except Exception as e:
            print(f"Пропуск TTS для фрагмента '{seg['text']}': {e}")
            continue
        
        # Загружаем сгенерированный голос
        speech_clip = AudioFileClip(tts_file)
        
        # Сдвигаем на нужный таймкод
        speech_clip = speech_clip.set_start(seg["start"])
        audio_clips.append(speech_clip)

    # Сводим все аудиоклипы в один
    final_audio = CompositeAudioClip(audio_clips)
    
    output_track_path = "final_audio_track.wav"
    final_audio.write_audiofile(output_track_path, fps=44100, logger=None)
    
    # Закрываем файлы
    for clip in audio_clips:
        clip.close()
        
    return output_track_path

def merge_audio_video(video_path, new_audio_path, output_video_path):
    """Соединяет видео с новой аудиодорожкой."""
    print("Финальная сборка видео...")
    video = VideoFileClip(video_path)
    new_audio = AudioFileClip(new_audio_path)
    
    final_video = video.set_audio(new_audio)
    final_video.write_videofile(output_video_path, codec="libx264", audio_codec="aac", logger=None)
    video.close()
    new_audio.close()

async def main(video_path, output_video_path):
    temp_original_audio = "original_audio.wav"
    
    cache_file = "segments_cache.json"
    
    if os.path.exists(cache_file):
        print("Найдено кэшированное распознавание и перевод! Загружаем из кэша...")
        with open(cache_file, "r", encoding="utf-8") as f:
            translated_segments = json.load(f)
    else:
        # 1. Извлечение аудио
        extract_audio(video_path, temp_original_audio)
        
        # 2. Транскрибация
        segments = transcribe_audio(temp_original_audio)
        
        # 3. Перевод
        translated_segments = translate_segments(segments)
        
        # Сохраняем в кэш
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(translated_segments, f, ensure_ascii=False, indent=4)
        
    # 4 & 5. TTS и наложение
    final_audio_path = await create_russian_audio_track(translated_segments, temp_original_audio)
    
    # 6. Сборка
    merge_audio_video(video_path, final_audio_path, output_video_path)
    
    # 7. Очистка временных файлов
    print("Уборка временных файлов...")
    if os.path.exists(temp_original_audio):
        os.remove(temp_original_audio)
    if os.path.exists(final_audio_path):
        os.remove(final_audio_path)
    if os.path.exists("temp_audio"):
        shutil.rmtree("temp_audio")
        
    print(f"Готово! Результат сохранен в {output_video_path}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Использование: python main.py <путь_к_видео>")
        sys.exit(1)
        
    input_video = sys.argv[1]
    output_video = f"translated_{os.path.basename(input_video)}"
    
    # Запуск асинхронного цикла для edge-tts
    asyncio.run(main(input_video, output_video))
