/**
 * ExportPanel — панель экспорта артефактов и субтитров
 * Выделена из Workspace.tsx (R11-И1 декомпозиция)
 */
import { artifactDownloadUrl, subtitleExportUrl, subtitleExportZipUrl } from '../api/client';
import type { ArtifactRecord, Segment } from '../types/schemas';
import type { AppLocale } from '../store/settings';
import { t } from '../i18n';
import { Download } from 'lucide-react';
import { ArtifactCard } from './ArtifactCard';

interface ExportPanelProps {
  projectId: string;
  locale: AppLocale;
  segments: Segment[];
  artifactRecords?: ArtifactRecord[];
  downloadableArtifacts: { kind: string; label: string; title?: string }[];
}

export function ExportPanel({
  projectId,
  locale,
  segments,
  artifactRecords,
  downloadableArtifacts,
}: ExportPanelProps) {
  return (
    <div className="right-tab-content">
      {/* Артефакты проекта */}
      {artifactRecords && artifactRecords.length > 0 ? (
        artifactRecords
          .filter(r => r.kind !== 'settings')
          .map(r => <ArtifactCard key={r.kind} record={r} projectId={projectId} locale={locale} />)
      ) : downloadableArtifacts.length > 0 ? (
        downloadableArtifacts.map(item => (
          <a key={item.kind} className="artifact-link"
            href={artifactDownloadUrl(projectId, item.kind)}
            target="_blank" rel="noreferrer"
            title={(item as { kind: string; label: string; title?: string }).title}
          >
            <Download size={14} /> {item.label}
          </a>
        ))
      ) : (
        <p className="empty-text">{t('workspace.noResults', locale)}</p>
      )}

      {/* Экспорт субтитров и скриптов */}
      {segments.length > 0 && (
        <div style={{
          marginTop: '16px', borderTop: '1px solid var(--border)',
          paddingTop: '12px',
        }}>
          {/* Субтитры */}
          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '8px', fontWeight: 600 }}>
            📄 Экспорт субтитров
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
            {(['srt', 'vtt', 'ass', 'sbv'] as const).map(fmt => (
              <a
                key={fmt}
                href={subtitleExportUrl(projectId, fmt)}
                target="_blank" rel="noreferrer"
                className="btn-secondary btn-xs"
                title={{
                  srt: 'SubRip — универсальный, VLC/DaVinci/Premiere/YouTube',
                  vtt: 'WebVTT — HTML5 браузерный плеер',
                  ass: 'Advanced SubStation Alpha — Aegisub, профессиональные редакторы',
                  sbv: 'YouTube SBV — для загрузки в YouTube Studio/Udemy',
                }[fmt]}
                style={{ textDecoration: 'none', fontFamily: 'monospace', fontSize: '0.8rem' }}
              >
                {fmt.toUpperCase()}
              </a>
            ))}
            {/* Primary button: ZIP — все форматы */}
            <a
              href={subtitleExportZipUrl(projectId)}
              target="_blank" rel="noreferrer"
              className="btn-primary btn-xs"
              title="Скачать все форматы (SRT+VTT+ASS+SBV) в одном ZIP-архиве"
              style={{ textDecoration: 'none' }}
            >
              📦 ZIP (все форматы)
            </a>
          </div>

          {/* Скрипт перевода — DOCX (primary), TSV/TXT (secondary) */}
          <div style={{ marginTop: 14 }}>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '6px', fontWeight: 600 }}>
              📝 Скрипт перевода
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
              {/* Primary: DOCX */}
              <a href={`/api/v1/projects/${projectId}/export/script?format=docx&include_source=true`}
                download className="btn-primary btn-xs" title="Скрипт в Word (.docx) — рекомендуемый формат" style={{ textDecoration: 'none' }}>
                📄 DOCX
              </a>
              {/* Secondary: TSV, TXT */}
              <a href={`/api/v1/projects/${projectId}/export/script?format=tsv&include_source=true`}
                download className="btn-secondary btn-xs" title="Таблица: таймкод + оригинал + перевод (Excel)" style={{ textDecoration: 'none' }}>
                📊 TSV
              </a>
              <a href={`/api/v1/projects/${projectId}/export/script?format=txt&include_source=true`}
                download className="btn-secondary btn-xs" title="Текстовый скрипт с таймкодами" style={{ textDecoration: 'none' }}>
                📝 TXT
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
