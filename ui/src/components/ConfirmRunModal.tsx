import React, { useState } from 'react';
import { AlertTriangle, Info, Play, RefreshCw, X, SkipForward } from 'lucide-react';
import { needsReviewCount, providerWarning, t, stageLabel } from '../i18n';
import type { AppLocale } from '../store/settings';
import type { Segment, StageRun } from '../types/schemas';
import './ConfirmRunModal.css';

// Полный список этапов в РЕАЛЬНОМ порядке выполнения пайплайна
export const ALL_STAGES = [
  'extract_audio',
  'transcribe',
  'regroup',
  'translate',
  'timing_fit',
  'tts',
  'render',
  'export',
] as const;

export type StageName = typeof ALL_STAGES[number];

interface ConfirmRunModalProps {
  projectId: string;
  provider: string;
  isForce: boolean;
  segments: Segment[];
  locale: AppLocale;
  /** Текущие stage_runs проекта — для определения дефолтного шага продолжения */
  stageRuns?: StageRun[];
  onConfirm: (fromStage: string | null) => void;
  onCancel: () => void;
}

/** Определить первый незавершённый этап из stage_runs */
function firstIncompleteStage(stageRuns: StageRun[]): string | null {
  const completed = new Set(
    stageRuns.filter(r => r.status === 'completed').map(r => r.stage)
  );
  return ALL_STAGES.find(s => !completed.has(s)) ?? null;
}

export const ConfirmRunModal: React.FC<ConfirmRunModalProps> = ({
  projectId,
  provider,
  isForce,
  segments,
  locale,
  stageRuns = [],
  onConfirm,
  onCancel,
}) => {
  const reviewCount = needsReviewCount(segments);
  const providerNote = providerWarning(provider, locale);

  // По умолчанию: первый не завершённый этап (для resume) или null (начать с начала)
  const defaultStage = isForce ? null : firstIncompleteStage(stageRuns);
  const [fromStage, setFromStage] = useState<string | null>(defaultStage);

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="confirm-run-title">
      <div className="modal-box">
        <div className="modal-header">
          <AlertTriangle size={22} className="text-warning" />
          <h3 id="confirm-run-title">
            {isForce ? t('modal.runAgain', locale) : t('modal.continueTranslation', locale)}
          </h3>
          <button className="btn-icon" onClick={onCancel} aria-label={t('modal.close', locale)}>
            <X size={18} />
          </button>
        </div>

        <div className="modal-body">
          <div className="modal-project-id">
            {t('modal.project', locale)}: <strong>{projectId}</strong>
          </div>

          {/* Информация о провайдере */}
          {providerNote && (
            <div className="modal-warning modal-warning--info">
              <Info size={14} />
              <span>{providerNote}</span>
            </div>
          )}

          {/* Предупреждение о принудительном перезапуске */}
          {isForce && (
            <div className="modal-warning modal-warning--danger">
              <AlertTriangle size={14} />
              <span>{t('modal.forceNote', locale)}</span>
            </div>
          )}

          {/* ── Выбор шага ── */}
          <div className="modal-from-stage">
            <label className="modal-from-stage-label" htmlFor="modal-from-stage-select">
              <SkipForward size={14} />
              {isForce ? 'Начать с шага:' : 'Продолжить с шага:'}
            </label>
            <select
              id="modal-from-stage-select"
              className="modal-from-stage-select"
              value={fromStage ?? '__start__'}
              onChange={e => setFromStage(e.target.value === '__start__' ? null : e.target.value)}
            >
              {isForce && (
                <option value="__start__">— С самого начала —</option>
              )}
              {ALL_STAGES.map(s => {
                const run = stageRuns.filter(r => r.stage === s).at(-1);
                const statusBadge = run
                  ? run.status === 'completed' ? ' ✓'
                  : run.status === 'failed'    ? ' ✗'
                  : run.status === 'running'   ? ' ⟳'
                  : ''
                  : '';
                return (
                  <option key={s} value={s}>
                    {stageLabel(s, locale)}{statusBadge}
                  </option>
                );
              })}
            </select>

            {fromStage && (
              <div className="modal-from-stage-note">
                <Info size={12} />
                Этапы <strong>до</strong> «{stageLabel(fromStage, locale)}» будут пропущены.
                Этот и следующие — выполнены заново.
              </div>
            )}
            {!fromStage && isForce && (
              <div className="modal-from-stage-note modal-from-stage-note--warn">
                <AlertTriangle size={12} />
                Весь перевод будет запущен заново.
              </div>
            )}
          </div>

          {/* QA: непереведённые сегменты */}
          {!isForce && reviewCount > 0 && segments.length > 0 && (
            <div className="modal-warning modal-warning--warn">
              <AlertTriangle size={14} />
              <span>
                <strong>{reviewCount} / {segments.length}</strong> {t('modal.reviewPrefix', locale)}
              </span>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn-secondary" onClick={onCancel}>
            {t('modal.cancel', locale)}
          </button>
          <button
            className="btn-primary"
            onClick={() => onConfirm(fromStage)}
            autoFocus
          >
            {isForce
              ? <><RefreshCw size={16} /> {t('modal.runAgainButton', locale)}</>
              : <><Play size={16} /> {t('modal.continueButton', locale)}</>
            }
          </button>
        </div>
      </div>
    </div>
  );
};
