import React from 'react';
import { Loader2, Play } from 'lucide-react';
import { t, statusLabel } from '../../i18n';
import type { Segment, VideoProject } from '../../types/schemas';
import type { AppLocale } from '../../store/settings';
import { SSMLToolbar, renderTtsMarkup } from '../SSMLToolbar';

interface SegmentCardProps {
  seg: Segment;
  segIndex: number;
  segments: Segment[];
  project: VideoProject;
  projectId: string;
  locale: AppLocale;
  activeSegId: string | null;
  selectedSegIds: Set<string>;
  setSelectedSegIds: React.Dispatch<React.SetStateAction<Set<string>>>;
  videoRef: React.RefObject<HTMLVideoElement | null>;
  formatTimecode: (sec: number) => string;
  previewingSegId: string | null;
  setPreviewingSegId: (id: string | null) => void;
  previewTTS: (projectId: string, text: string, force: boolean) => Promise<string>;
  handleSsmlChange: (segId: string, value: string) => void;
  handleSsmlReset: (segId: string) => void;
  handleTextChange: (segId: string, newText: string, field?: "translated_text" | "notes") => void;
  handleMergeSegments: (segId: string) => void;
  setSegRef: (id: string, el: HTMLDivElement | null) => void;
  setSsmlTextareaRef: (id: string, el: HTMLTextAreaElement | null) => void;
  getSsmlTextareaRef: (id: string) => HTMLTextAreaElement | null;
}

export const SegmentCard: React.FC<SegmentCardProps> = ({
  seg,
  segIndex,
  segments,
  project,
  projectId,
  locale,
  activeSegId,
  selectedSegIds,
  setSelectedSegIds,
  videoRef,
  formatTimecode,
  previewingSegId,
  setPreviewingSegId,
  previewTTS,
  handleSsmlChange,
  handleSsmlReset,
  handleTextChange,
  handleMergeSegments,
  setSegRef,
  setSsmlTextareaRef,
  getSsmlTextareaRef,
}) => {
  return (
    <div
      data-seg-id={String(seg.id)}
      ref={(el) => setSegRef(seg.id, el)}
      className={`segment-item ${seg.status}${activeSegId === seg.id ? ' segment-active' : ''}${
        selectedSegIds.has(seg.id) ? ' seg-selected' : ''
      }${
        (seg.qa_flags ?? []).some((f: string) => ['translation_empty','tts_invalid_slot','timing_fit_invalid_slot'].includes(f)) ? ' seg-qa-critical' :
        (seg.qa_flags ?? []).some((f: string) => ['timing_fit_failed','render_audio_trimmed','tts_overflow_after_rate'].includes(f)) ? ' seg-qa-error' :
        (seg.qa_flags ?? []).length > 0 ? ' seg-qa-warning' : ''
      }`}
    >
      <div className="seg-header">
        {/* D6: Номер сегмента для ориентации в длинных текстах */}
        <span
          className="seg-number"
          title={`Сегмент №${segIndex + 1} из ${segments.length}`}
        >
          #{segIndex + 1}
        </span>
        {/* Z2.15: Checkbox для batch-выбора */}
        <input
          type="checkbox"
          className="seg-checkbox"
          checked={selectedSegIds.has(seg.id)}
          onChange={(e) => {
            setSelectedSegIds(prev => {
              const next = new Set(prev);
              if (e.target.checked) next.add(seg.id);
              else next.delete(seg.id);
              return next;
            });
          }}
          aria-label={`Выбрать сегмент №${segIndex + 1}`}
        />
        <span
          className="seg-timing seg-timing--clickable"
          title="Перейти к этому моменту в видео"
          onClick={() => {
            if (videoRef.current) {
              videoRef.current.currentTime = seg.start;
              videoRef.current.play().catch(() => {});
            }
          }}
        >
          {formatTimecode(seg.start)} — {formatTimecode(seg.end)}
          <span className="seg-duration">({(seg.end - seg.start).toFixed(1)}с)</span>
        </span>
        <span className="seg-status">{statusLabel(seg.status ?? '', locale)}</span>
        {/* Z2.16: Badge счётчика правок */}
        {(seg.edit_count ?? 0) > 0 && (
          <span className="seg-edit-count" title="Количество ручных правок">
            ✏️ {seg.edit_count}
          </span>
        )}
        {seg.reviewed && (
          <span className="seg-reviewed-badge" title="Сегмент проверен вручную">
            ✓ Проверено
          </span>
        )}
        {/* Z2.10: copy translated text */}
        {seg.translated_text && (
          <button
            className="seg-copy-btn"
            title={locale === 'ru' ? 'Скопировать перевод' : 'Copy translation'}
            onClick={() => navigator.clipboard.writeText(seg.translated_text!).catch(() => {})}
            aria-label="Скопировать перевод"
          >
            📋
          </button>
        )}
      </div>
      {/* R13-И4: Мария — оригинал с явной меткой для переводчиков */}
      <div className="seg-source-row">
        <div className="seg-source">
          <span className="seg-source-label">📖 Оригинал:</span>
          {seg.source_text}
        </div>
        {/* Z4.11: diff — кол-во символов до/после */}
        {seg.translated_text && seg.source_text && (
          <span className={`seg-diff-badge ${
            seg.translated_text.length > seg.source_text.length * 1.3 ? 'seg-diff--long' :
            seg.translated_text.length < seg.source_text.length * 0.7 ? 'seg-diff--short' :
            'seg-diff--ok'}`}
            title={`Оригинал: ${seg.source_text.length} символов → Перевод: ${seg.translated_text.length} символов`}
          >
            {seg.source_text.length} → {seg.translated_text.length}
          </span>
        )}
      </div>

      {/* TTS-тулбар — показывается только при Яндекс TTS */}
      {project.config?.professional_tts_provider === 'yandex' && (() => {
        const ssmlOverride = (seg as Segment & { tts_ssml_override?: string }).tts_ssml_override || '';
        const currentText = ssmlOverride || seg.translated_text || '';
        return (
          <SSMLToolbar
            getTextarea={() => getSsmlTextareaRef(seg.id)}
            currentText={currentText}
            hasOverride={!!ssmlOverride}
            onChange={(v) => handleSsmlChange(seg.id, v)}
            onReset={() => handleSsmlReset(seg.id)}
            onPreview={async (text) => {
              const url = await previewTTS(projectId, text, false);
              const audio = new Audio();
              // Сохраняем ссылку на window чтобы GC не убил объект во время воспроизведения
              window.__ttsPreviewAudio = audio;
              audio.onended = () => { URL.revokeObjectURL(url); delete window.__ttsPreviewAudio; };
              audio.onerror = (e) => { console.error('[preview] audio error', e); URL.revokeObjectURL(url); delete window.__ttsPreviewAudio; };
              audio.src = url;
              audio.load();
              try { await audio.play(); } catch(e) { console.error('[preview] play error', e); }
            }}
          />
        );
      })()}

      {/* Превью TTS — для OpenAI-совместимых провайдеров (Polza, NeuroAPI) */}
      {(() => {
        const prov = project.config?.professional_tts_provider ?? '';
        if (!prov || prov === 'yandex') return null;
        const segText = (seg as Segment & { tts_ssml_override?: string }).tts_ssml_override
          || seg.translated_text || '';
        const isPreviewing = previewingSegId === seg.id;
        return (
          <div className="seg-preview-bar">
            <button
              className={`seg-preview-btn${isPreviewing ? ' seg-preview-btn--loading' : ''}`}
              title="Прослушать синтез голоса для этого сегмента"
              disabled={isPreviewing || !segText.trim()}
              onClick={async () => {
                if (isPreviewing) return;
                setPreviewingSegId(seg.id);
                try {
                  const url = await previewTTS(projectId, segText, false);
                  const audio = new Audio();
                  window.__ttsPreviewAudio = audio;
                  audio.onended = () => { URL.revokeObjectURL(url); delete window.__ttsPreviewAudio; setPreviewingSegId(null); };
                  audio.onerror = () => { URL.revokeObjectURL(url); delete window.__ttsPreviewAudio; setPreviewingSegId(null); };
                  audio.src = url;
                  audio.load();
                  await audio.play();
                } catch {
                  setPreviewingSegId(null);
                }
              }}
            >
              {isPreviewing
                ? <Loader2 size={13} className="seg-preview-spinner" />
                : <Play size={13} />}
              {isPreviewing ? 'Синтез…' : 'Превью'}
            </button>
          </div>
        );
      })()}
      {/* D8: Копировать перевод сегмента в буфер обмена */}
      <div style={{ display: 'flex', gap: '6px', alignItems: 'center', marginTop: '4px' }}>
        <button
          className="seg-copy-btn"
          title="Копировать перевод в буфер (D8)"
          onClick={() => {
            const text = (seg as Segment & { tts_ssml_override?: string }).tts_ssml_override
              || seg.translated_text || seg.source_text || '';
            navigator.clipboard.writeText(text).then(() => {
              // Визуальный фидбек через атрибут
              const btn = document.activeElement as HTMLElement;
              if (btn) { btn.textContent = '✅'; setTimeout(() => { btn.textContent = '📋'; }, 1200); }
            });
          }}
          style={{
            background: 'none', border: '1px solid var(--border-color)',
            borderRadius: '4px', padding: '2px 6px', fontSize: '13px',
            cursor: 'pointer', color: 'var(--text-muted)',
          }}
        >📋</button>
        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
          {seg.source_text?.split(' ').length ?? 0} слов
        </span>
      </div>

      <textarea
        ref={(el) => setSsmlTextareaRef(seg.id, el)}
        className={`seg-translated text-input ${
          !seg.translated_text?.trim() ? 'seg-empty' : ''
        }${
          (seg as Segment & { tts_ssml_override?: string }).tts_ssml_override ? ' seg-has-ssml' : ''
        }`}
        value={
          (seg as Segment & { tts_ssml_override?: string }).tts_ssml_override
            || (seg.translated_text ?? '')
        }
        onChange={(e) => {
          const hasOverride = !!(seg as Segment & { tts_ssml_override?: string }).tts_ssml_override;
          if (hasOverride) {
            handleSsmlChange(seg.id, e.target.value);
          } else {
            handleTextChange(seg.id, e.target.value);
          }
        }}
        placeholder={
          (seg as Segment & { tts_ssml_override?: string }).tts_ssml_override
            ? 'SSML / текст с тегами Яндекс SpeechKit'
            : t('workspace.enterTranslation', locale)
        }
        rows={2}
        onInput={(e) => {
          /* В2: Авторасширение textarea [R11-И2] */
          const el = e.currentTarget;
          el.style.height = 'auto';
          el.style.height = `${el.scrollHeight}px`;
        }}
        style={{ resize: 'none', overflow: 'hidden' }}
      />
      {/* Л4: Счётчик символов — предупреждение при > 84 (стандарт субтитров) */}
      {(() => {
        const txt = (seg as Segment & { tts_ssml_override?: string }).tts_ssml_override || seg.translated_text || '';
        const len = txt.length;
        const maxLine = Math.max(...(txt.split('\n').map(l => l.length)));
        const isOverLimit = maxLine > 84;
        const isWarning = maxLine > 60;
        if (len === 0) return null;
        return (
          <div style={{
            display: 'flex', justifyContent: 'flex-end', gap: '8px',
            fontSize: '0.7rem', marginTop: '2px',
          }}
          >
            {/* R7-И2: Счётчик символов всего */}
            <span style={{ color: 'var(--text-muted, #94a3b8)' }} title={`Всего символов: ${len}`}>
              {len} симв.
            </span>
            {/* R7-И2: Длина максимальной строки (стандарт субтитров 42 симв./строка) */}
            <span
              style={{ color: isOverLimit ? '#ef4444' : isWarning ? '#f59e0b' : '#6ee7b7', fontWeight: isOverLimit ? 700 : 400 }}
              title={isOverLimit
                ? `⚠️ Строка ${maxLine} символов — превышает стандарт 84 знака. Субтитры могут обрезаться.`
                : maxLine > 42
                ? `Строка ${maxLine} симв. — превышает профессиональный стандарт 42 знака/строку`
                : `Длина строки OK (≤42 симв.)`}
            >
              {isOverLimit ? '⚠️ ' : maxLine > 42 ? '⚡ ' : '✓ '}строка: {maxLine}/42
            </span>
          </div>
        );
      })()}
      {/* TTS Rich Preview — визуализация разметки */}
      {(() => {
        const ov = (seg as Segment & { tts_ssml_override?: string }).tts_ssml_override;
        if (!ov) return null;
        const hasTtsMarkup = /\*\*|sil<\[|<\[(tiny|small|medium|large|huge)\]>|\[\[|\+[аеёиоуыэюяАЕЁИОУЫЭЮЯaeiouAEIOU]/i.test(ov);
        if (!hasTtsMarkup) return null;
        return (
          <div className="tts-rich-preview" title="Предпросмотр TTS-разметки">
            {renderTtsMarkup(ov)}
          </div>
        );
      })()}
      {/* Z2.11: Notes — комментарий редактора */}
      <input
        type="text"
        className="seg-notes-input"
        placeholder={locale === 'ru' ? '💬 Заметка редактора...' : '💬 Note...'}
        value={seg.notes ?? ''}
        onChange={(e) => handleTextChange(seg.id, e.target.value, 'notes')}
      />
      {/* Z2.14: Объединить с следующим сегментом */}
      {segments.indexOf(seg) < segments.length - 1 && (
        <button
          className="seg-merge-btn"
          title={locale === 'ru' ? 'Объединить с следующим сегментом' : 'Merge with next segment'}
          onClick={() => handleMergeSegments(seg.id)}
        >
          ⤵ Объединить
        </button>
      )}
    </div>
  );
};
