import React from 'react';
import { Film } from 'lucide-react';
import { t } from '../../i18n';
import { withApiKeyQuery } from '../../api/client';
import type { VideoProject, Segment } from '../../types/schemas';
import type { AppLocale } from '../../store/settings';

const API_VIDEO = '/api/v1/video';

interface VideoPlayerSectionProps {
  project: VideoProject;
  projectId: string;
  locale: AppLocale;
  videoTab: 'source' | 'translated';
  setVideoTab: (tab: 'source' | 'translated') => void;
  isPortraitVideo: boolean;
  setIsPortraitVideo: (val: boolean) => void;
  videoRef: React.RefObject<HTMLVideoElement | null>;
  getVideoUrl: () => string;
  findArtifact: (kind: string) => any;
  segments: Segment[];
  activeSegId: string | null;
  setActiveSegId: (id: string | null) => void;
}

export const VideoPlayerSection: React.FC<VideoPlayerSectionProps> = ({
  project,
  projectId,
  locale,
  videoTab,
  setVideoTab,
  isPortraitVideo,
  setIsPortraitVideo,
  videoRef,
  getVideoUrl,
  findArtifact,
  segments,
  activeSegId,
  setActiveSegId,
}) => {
  return (
    <div className="panel video-panel glass-panel">
      <div className="panel-tabs">
        <button
          className={videoTab === 'source' ? 'active' : ''}
          onClick={() => setVideoTab('source')}
        >
          <Film size={14} /> {t('workspace.original', locale)}
        </button>
        <button
          className={videoTab === 'translated' ? 'active' : ''}
          onClick={() => setVideoTab('translated')}
          disabled={!findArtifact('output_video')}
          title={!findArtifact('output_video') ? t('workspace.outputNotReady', locale) : ''}
        >
          <Film size={14} /> {t('workspace.aiTranslation', locale)}
        </button>
      </div>
      <div className={`video-container${isPortraitVideo ? ' is-portrait' : ''}`}>
        <video
          ref={videoRef}
          controls
          src={getVideoUrl()}
          key={getVideoUrl()}
          onLoadedMetadata={(event) => {
            const video = event.currentTarget;
            setIsPortraitVideo(Boolean(video.videoWidth && video.videoHeight && video.videoWidth < video.videoHeight));
          }}
          onTimeUpdate={() => {
            const t = videoRef.current?.currentTime ?? 0;
            const active = segments.find(s => t >= s.start && t < s.end);
            setActiveSegId(active?.id ?? null);
          }}
        >
          {/* WebVTT-субтитры — браузер понимает только VTT, не SRT */}
          {project.artifacts?.['subtitles_vtt'] && (
            <track
              kind="subtitles"
              src={withApiKeyQuery(`${API_VIDEO}/${projectId}/${project.artifacts['subtitles_vtt']}`)}
              srcLang={project.config?.target_language ?? 'ru'}
              label="Субтитры"
              default
            />
          )}
        </video>
        {/* I5: Кастомный оверлей субтитров (если нет VTT или при редактировании) */}
        {activeSegId && !project.artifacts?.['subtitles_vtt'] && (() => {
          const activeSeg = segments.find(s => s.id === activeSegId);
          const subText = activeSeg?.translated_text || activeSeg?.source_text;
          return subText ? (
            <div className="subtitle-overlay" aria-live="polite">
              {subText}
            </div>
          ) : null;
        })()}
      </div>
    </div>
  );
};
