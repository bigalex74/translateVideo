import React from 'react';
import { artifactDownloadUrl } from '../api/client';
import type { ArtifactRecord } from '../types/schemas';
import type { AppLocale } from '../store/settings';
import { t } from '../i18n';
import { Download, Copy, CheckCircle2, FileVideo, FileText, FileAudio, FileJson, File } from 'lucide-react';
import './ArtifactCard.css';

const KIND_ICONS: Record<string, React.ReactNode> = {
  output_video:          <FileVideo size={20} />,
  source_transcript:     <FileText size={20} />,
  translated_transcript: <FileJson size={20} />,
  tts_audio:             <FileAudio size={20} />,
  final_audio:           <FileAudio size={20} />,
  source_audio:          <FileAudio size={20} />,
  subtitles:             <FileText size={20} />,
  qa_report:             <FileText size={20} />,
  settings:              <File size={20} />,
};

const KIND_LABELS: Record<string, string> = {
  output_video:          'Готовое видео',
  source_transcript:     'Расшифровка оригинала',
  translated_transcript: 'Перевод (JSON)',
  tts_audio:             'TTS-аудио',
  final_audio:           'Финальное аудио',
  source_audio:          'Аудио оригинала',
  subtitles:             'Субтитры',
  qa_report:             'QA-отчёт',
  settings:              'Настройки',
};

function formatBytes(bytes?: number | string): string {
  const n = Number(bytes);
  if (!n || isNaN(n)) return '';
  if (n < 1024) return `${n} Б`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} КБ`;
  return `${(n / 1024 / 1024).toFixed(2)} МБ`;
}

function shortChecksum(checksum?: string): string {
  if (!checksum) return '';
  return checksum.slice(0, 8);
}

interface ArtifactCardProps {
  record: ArtifactRecord;
  projectId: string;
  locale: AppLocale;
}

export const ArtifactCard: React.FC<ArtifactCardProps> = ({ record, projectId, locale }) => {
  const [copied, setCopied] = React.useState(false);

  const downloadUrl = artifactDownloadUrl(projectId, record.kind);
  const apiUrl = `${window.location.origin}${downloadUrl}`;
  const label = KIND_LABELS[record.kind] ?? record.kind;
  const icon = KIND_ICONS[record.kind] ?? <File size={20} />;
  const sizeStr = formatBytes(record.metadata?.size_bytes as number | undefined);
  const checksumStr = shortChecksum(record.metadata?.checksum as string | undefined);
  const date = record.created_at
    ? new Date(record.created_at).toLocaleString(locale === 'en' ? 'en-US' : 'ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
    : '';

  const handleCopyUrl = async () => {
    try {
      await navigator.clipboard.writeText(apiUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* ignore */
    }
  };

  return (
    <div className="artifact-card">
      <div className="artifact-icon">{icon}</div>
      <div className="artifact-info">
        <span className="artifact-label">{label}</span>
        <div className="artifact-meta">
          {date && <span>{date}</span>}
          {sizeStr && <span>{sizeStr}</span>}
          {checksumStr && <span className="artifact-checksum" title={record.metadata?.checksum as string}>SHA:{checksumStr}</span>}
        </div>
      </div>
      <div className="artifact-actions">
        <button
          type="button"
          className="artifact-btn"
          title={t('artifact.copyApiUrl', locale)}
          onClick={handleCopyUrl}
          aria-label={t('artifact.copyApiUrlAria', locale)}
        >
          {copied ? <CheckCircle2 size={15} /> : <Copy size={15} />}
        </button>
        <a
          href={downloadUrl}
          download
          className="artifact-btn"
          title={t('artifact.download', locale)}
          aria-label={`${t('artifact.download', locale)} ${label}`}
        >
          <Download size={15} />
        </a>
      </div>
    </div>
  );
};
