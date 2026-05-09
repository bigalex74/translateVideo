import React from 'react';
import { AlignLeft, Columns2 } from 'lucide-react';
import { t } from '../../i18n';
import type { Segment, VideoProject } from '../../types/schemas';
import type { AppLocale } from '../../store/settings';

interface SegmentEditorHeaderProps {
  locale: AppLocale;
  project: VideoProject | null;
  setProject: React.Dispatch<React.SetStateAction<VideoProject | null>>;
  segments: Segment[];
  filteredSegments: Segment[];
  dirty: boolean;
  setDirty: (dirty: boolean) => void;
  setMessage: (msg: string) => void;
  segSearch: string;
  setSegSearch: React.Dispatch<React.SetStateAction<string>>;
  segReplace: string;
  setSegReplace: React.Dispatch<React.SetStateAction<string>>;
  showReplace: boolean;
  setShowReplace: React.Dispatch<React.SetStateAction<boolean>>;
  qaFlagFilter: string;
  setQaFlagFilter: React.Dispatch<React.SetStateAction<string>>;
  filterEmptyOnly: boolean;
  setFilterEmptyOnly: React.Dispatch<React.SetStateAction<boolean>>;
  selectedSegIds: Set<string>;
  setSelectedSegIds: React.Dispatch<React.SetStateAction<Set<string>>>;
  sideBySide: boolean;
  setSideBySide: React.Dispatch<React.SetStateAction<boolean>>;
  selectSegmentsWhere: (predicate: (s: Segment) => boolean) => void;
  segmentActionLoading: string | null;
  runSelectedSegmentAction: (action: 'translate' | 'tts' | 'reset-tts' | 'mark-reviewed', successMsg: string, needProvider?: boolean) => void;
}

export const SegmentEditorHeader: React.FC<SegmentEditorHeaderProps> = ({
  locale,
  project,
  setProject,
  segments,
  filteredSegments,
  dirty,
  setDirty,
  setMessage,
  segSearch,
  setSegSearch,
  segReplace,
  setSegReplace,
  showReplace,
  setShowReplace,
  qaFlagFilter,
  setQaFlagFilter,
  filterEmptyOnly,
  setFilterEmptyOnly,
  selectedSegIds,
  setSelectedSegIds,
  sideBySide,
  setSideBySide,
  selectSegmentsWhere,
  segmentActionLoading,
  runSelectedSegmentAction,
}) => {
  return (
    <>
      <div className="panel-header">
        <h3 style={{minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}><AlignLeft size={16} /> {t('workspace.translationEditor', locale)}</h3>
        <span className="panel-header-meta">
          {segments.length} {t('workspace.segments', locale) || 'сегм.'}
          {dirty && <span className="dirty-indicator"> · {t('workspace.unsaved', locale)}</span>}
        </span>
      </div>

      {/* Z2.12: Поиск по сегментам */}
      <div className="seg-search-bar">
        <input
          id="seg-search-input"
          className="seg-search-input"
          type="text"
          placeholder={locale === 'ru' ? '🔍 Поиск по тексту...' : '🔍 Search segments...'}
          value={segSearch}
          onChange={e => setSegSearch(e.target.value)}
        />
        {segSearch && (
          <button className="seg-search-clear" onClick={() => setSegSearch('')} aria-label="Очистить">×</button>
        )}
        
        {/* Л5: Кнопка открытия замены */}
        <button
          className={`btn-secondary btn-xs${showReplace ? ' active' : ''}`}
          onClick={() => setShowReplace(r => !r)}
          title="Найти и заменить (Ctrl+H)"
        >⇄</button>

        {/* Л5: Панель замены */}
        {showReplace && segSearch && (
          <div className="seg-replace-row">
            <input
              type="text"
              className="seg-search-input"
              placeholder="Заменить на..."
              value={segReplace}
              onChange={e => setSegReplace(e.target.value)}
              style={{ width: 140 }}
            />
            <button
              className="btn-secondary btn-xs"
              onClick={() => {
                if (!segSearch || !project) return;
                setProject(prev => {
                  if (!prev) return prev;
                  const updatedSegs = (prev.segments as Segment[]).map(s => {
                    if (!s.translated_text?.includes(segSearch)) return s;
                    return { ...s, translated_text: s.translated_text.replaceAll(segSearch, segReplace) };
                  });
                  return { ...prev, segments: updatedSegs };
                });
                setDirty(true);
                setMessage(`Заменено: "${segSearch}" → "${segReplace}"`);
                setTimeout(() => setMessage(''), 3000);
              }}
            >Заменить всё</button>
          </div>
        )}

        {/* NC8-02: Фильтр по QA-флагу */}
        <select
          className="seg-qa-filter"
          value={qaFlagFilter}
          onChange={e => setQaFlagFilter(e.target.value)}
          title="Фильтр по QA-флагу"
        >
          <option value="">Все сегменты</option>
          <option value="translation_empty">Пустой перевод</option>
          <option value="timing_fit_failed">Не влезает в слот</option>
          <option value="tts_overflow">Переполнение TTS</option>
          <option value="render_audio_trimmed">Обрезка аудио</option>
          <option value="translation_fallback_source">Оригинал в переводе</option>
        </select>

        {/* Л6: Фильтр пустых (непереведённых) сегментов */}
        <button
          id="btn-filter-empty"
          className={`btn-secondary btn-xs${filterEmptyOnly ? ' active' : ''}`}
          onClick={() => setFilterEmptyOnly(f => !f)}
          title={filterEmptyOnly ? 'Показать все сегменты' : 'Показать только непереведённые (пустые)'}
          style={{
            flexShrink: 0,
            background: filterEmptyOnly ? 'rgba(245,158,11,0.2)' : undefined,
            borderColor: filterEmptyOnly ? '#f59e0b' : undefined,
            color: filterEmptyOnly ? '#fde68a' : undefined,
          }}
        >
          {filterEmptyOnly ? '⚠️ Пустые' : '⚠️ Пустые'}
          <span style={{ marginLeft: '4px', fontSize: '0.72rem', opacity: 0.8 }}>
            {filterEmptyOnly ? '✓' : ''}
          </span>
        </button>

        <button
          className="btn-secondary btn-xs"
          onClick={() => setSelectedSegIds(new Set(filteredSegments.map(s => s.id)))}
          disabled={filteredSegments.length === 0}
          title="Выбрать все сегменты с учётом текущих фильтров"
        >
          ✓ Видимые
        </button>

        <button
          className="btn-secondary btn-xs"
          onClick={() => selectSegmentsWhere(s => Boolean((s.translated_text ?? '').trim()) && !s.tts_path)}
          title="Выбрать переведённые сегменты без TTS"
        >
          Без TTS
        </button>

        <button
          className="btn-secondary btn-xs"
          onClick={() => selectSegmentsWhere(s => (s.qa_flags ?? []).length > 0 && !s.reviewed)}
          title="Выбрать QA-сегменты без отметки проверки"
        >
          QA
        </button>

        {/* R7-И3: Side-by-side переключатель (Валентина Вт1) */}
        <button
          id="btn-side-by-side"
          className={`btn-secondary btn-xs${sideBySide ? ' active' : ''}`}
          onClick={() => setSideBySide(s => !s)}
          title={sideBySide ? 'Обычный режим' : 'Режим side-by-side: оригинал и перевод рядом'}
          style={{
            flexShrink: 0,
            background: sideBySide ? 'rgba(99,102,241,0.2)' : undefined,
            borderColor: sideBySide ? '#6366f1' : undefined,
            color: sideBySide ? '#a5b4fc' : undefined,
          }}
        >
          <Columns2 size={13} />
          <span style={{ marginLeft: '4px' }}>‖</span>
        </button>
      </div>

      {/* Z2.15: Bulk actions bar */}
      {selectedSegIds.size > 0 && (
        <div className="bulk-actions-bar">
          <span className="bulk-count">✓ {selectedSegIds.size} выбрано</span>
          <button
            className="btn-secondary btn-xs"
            onClick={() => setSelectedSegIds(new Set(segments.map(s => s.id)))}
          >Выбрать все</button>
          <button
            className="btn-secondary btn-xs"
            onClick={() => {
              const texts = segments
                .filter(s => selectedSegIds.has(s.id))
                .map(s => s.translated_text || '')
                .join('\n');
              navigator.clipboard.writeText(texts);
            }}
          >📋 Копировать</button>
          <button
            className="btn-secondary btn-xs"
            disabled={segmentActionLoading !== null}
            onClick={() => runSelectedSegmentAction('translate', 'Переведено заново', true)}
          >
            {segmentActionLoading === 'translate' ? '...' : '🌐 Перевести'}
          </button>
          <button
            className="btn-secondary btn-xs"
            disabled={segmentActionLoading !== null}
            onClick={() => runSelectedSegmentAction('tts', 'Озвучено', true)}
          >
            {segmentActionLoading === 'tts' ? '...' : '🔊 Озвучить'}
          </button>
          <button
            className="btn-secondary btn-xs"
            disabled={segmentActionLoading !== null}
            onClick={() => runSelectedSegmentAction('reset-tts', 'TTS сброшен')}
          >
            {segmentActionLoading === 'reset-tts' ? '...' : '↺ Сброс TTS'}
          </button>
          <button
            className="btn-secondary btn-xs"
            disabled={segmentActionLoading !== null}
            onClick={() => runSelectedSegmentAction('mark-reviewed', 'Отмечено проверенными')}
          >
            {segmentActionLoading === 'mark-reviewed' ? '...' : '✓ Проверено'}
          </button>
          <button
            className="btn-secondary btn-xs"
            onClick={() => setSelectedSegIds(new Set())}
          >✕ Снять выбор</button>
        </div>
      )}

      {/* R13-И4: Мария — кнопка "Принять всё" для mark all reviewed */}
      {filteredSegments.length > 0 && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '4px' }}>
          <button
            className="btn-secondary btn-xs"
            id="btn-mark-all-reviewed"
            title="Отметить все видимые сегменты как проверенные (R13-И4)"
            disabled={segmentActionLoading !== null}
            onClick={async () => {
              // Выбираем все видимые и запускаем mark-reviewed
              const ids = new Set(filteredSegments.map(s => s.id));
              setSelectedSegIds(ids);
              // После выбора сразу запускаем action
              setTimeout(() => runSelectedSegmentAction('mark-reviewed', 'Все сегменты приняты ✅'), 50);
            }}
          >
            ✅ Принять всё ({filteredSegments.length})
          </button>
        </div>
      )}
    </>
  );
};
