import React from 'react';
import { Loader2, RefreshCw } from 'lucide-react';
import { t } from '../../i18n';
import type { Segment, VideoProject } from '../../types/schemas';
import type { AppLocale } from '../../store/settings';
import { SegmentCard } from './SegmentCard';

interface SegmentListProps {
  project: VideoProject;
  projectId: string;
  locale: AppLocale;
  segments: Segment[];
  filteredSegments: Segment[];
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
  sideBySide: boolean;
  isRunning: boolean;
  setConfirm: (params: { force: boolean } | null) => void;
}

export const SegmentList: React.FC<SegmentListProps> = ({
  project,
  projectId,
  locale,
  segments,
  filteredSegments,
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
  sideBySide,
  isRunning,
  setConfirm,
}) => {
  return (
    <div className={`segments-list${sideBySide ? ' seg-side-by-side' : ''}`}>
      {filteredSegments.map((seg, segIndex) => (
        <SegmentCard
          key={seg.id}
          seg={seg}
          segIndex={segIndex}
          segments={segments}
          project={project}
          projectId={projectId}
          locale={locale}
          activeSegId={activeSegId}
          selectedSegIds={selectedSegIds}
          setSelectedSegIds={setSelectedSegIds}
          videoRef={videoRef}
          formatTimecode={formatTimecode}
          previewingSegId={previewingSegId}
          setPreviewingSegId={setPreviewingSegId}
          previewTTS={previewTTS}
          handleSsmlChange={handleSsmlChange}
          handleSsmlReset={handleSsmlReset}
          handleTextChange={handleTextChange}
          handleMergeSegments={handleMergeSegments}
          setSegRef={setSegRef}
          setSsmlTextareaRef={setSsmlTextareaRef}
          getSsmlTextareaRef={getSsmlTextareaRef}
        />
      ))}
      {segments.length === 0 && !isRunning && (
        <div className="editor-empty-state">
          <span className="editor-empty-icon">🎬</span>
          <p className="editor-empty-title">{t('workspace.notStartedTitle', locale)}</p>
          <p className="editor-empty-hint">
            {t('workspace.notStartedHint', locale)}
          </p>
          <button
            className="btn-primary"
            onClick={() => setConfirm({ force: false })}
          >
            <RefreshCw size={16} /> {t('dashboard.run', locale)}
          </button>
        </div>
      )}
      {segments.length === 0 && isRunning && (
        <div className="editor-empty-state">
          <Loader2 size={32} className="animate-spin editor-empty-icon" />
          <p className="editor-empty-title">{t('workspace.processing', locale)}</p>
          <p className="editor-empty-hint">{t('workspace.processingHint', locale)}</p>
        </div>
      )}
    </div>
  );
};
