/**
 * Локализация UI и человекочитаемые названия технических терминов.
 *
 * Русский язык является дефолтным для основной аудитории проекта, английский
 * нужен для демонстраций и будущей внешней документации.
 */

import { getPersistedLocale, type AppLocale } from './store/settings';

type LocaleMap = Record<AppLocale, Record<string, string>>;

export const LOCALE_LABELS: Record<AppLocale, string> = {
  ru: 'Русский',
  en: 'English',
};

const TEXT: LocaleMap = {
  ru: {
    'app.title': 'ИИ Переводчик',
    'app.themeLight': 'Светлая тема',
    'app.themeDark': 'Тёмная тема',
    'app.themeToggle': 'Переключить тему',
    'nav.dashboard': 'Мои переводы',
    'nav.newProject': 'Новый перевод',
    'nav.settings': 'Настройки',

    'dashboard.title': 'Мои переводы',
    'dashboard.subtitle': 'Загрузите проект по имени или выберите из списка ниже.',
    'dashboard.searchPlaceholder': 'Имя проекта (например: my-video-en-ru)…',
    'dashboard.find': 'Найти',
    'dashboard.refreshList': 'Обновить список',
    'dashboard.openEditor': 'Открыть редактор',
    'dashboard.run': 'Запустить перевод',
    'dashboard.restart': 'Перезапустить всё',
    'dashboard.translationDirection': 'Направление перевода',
    'dashboard.segmentsRecognized': 'Сегментов распознано',
    'dashboard.progress': 'Прогресс обработки',
    'dashboard.notStarted': 'Обработка ещё не запускалась.',
    'dashboard.noProjectTitle': 'Проект не выбран',
    'dashboard.noProjectText': 'Введите имя проекта в строку поиска или выберите из списка ниже.',
    'dashboard.allProjects': 'Все проекты',
    'dashboard.sortedByUpdate': 'Отсортированы по времени последнего изменения.',
    'dashboard.found': 'Найдено',
    'dashboard.status': 'Статус',
    'dashboard.editor': 'Редактор',
    'dashboard.empty': 'Проекты пока не найдены. Создайте первый перевод!',
    'dashboard.segmentShort': 'сегм.',
    'dashboard.loadError': 'Не удалось загрузить проект',
    'dashboard.runError': 'Не удалось запустить перевод',

    'settings.title': 'Настройки',
    'settings.subtitle': 'Параметры приложения, сохраняются в браузере.',
    'settings.integrations': 'Интеграции',
    'settings.webhookLabel': 'Webhook URL (n8n)',
    'settings.webhookHelp': 'Этот URL получит уведомление о завершении каждого перевода.',
    'settings.providerLabel': 'Движок обработки по умолчанию',
    'settings.providerHelp': 'Используется при создании нового проекта (можно изменить на шаге 1).',
    'settings.appearance': 'Внешний вид',
    'settings.themeLabel': 'Тема оформления',
    'settings.themeDark': 'Тёмная (по умолчанию)',
    'settings.themeLight': 'Светлая',
    'settings.themeSystem': 'Системная',
    'settings.largeText': 'Крупный шрифт (для слабовидящих)',
    'settings.languageLabel': 'Язык интерфейса',
    'settings.languageHelp': 'Русский используется по умолчанию; английский нужен для демонстраций и внешних пользователей.',
    'settings.on': 'Вкл',
    'settings.off': 'Выкл',
    'settings.save': 'Сохранить настройки',
    'settings.saved': 'Сохранено!',

    'newProject.title': 'Новый перевод',
    'newProject.subtitle': 'Загрузите видео — ИИ-конвейер переведёт всё остальное.',
    'newProject.stepFile': 'Видеофайл',
    'newProject.stepParams': 'Параметры',
    'newProject.stepSettings': 'Настройки',
    'newProject.uploadFile': 'Загрузить файл',
    'newProject.urlPath': 'URL / путь на сервере',
    'newProject.dropVideo': 'Перетащите видео сюда',
    'newProject.clickToChoose': 'или кликните для выбора файла',
    'newProject.changeFile': 'Кликните или перетащите другой файл для замены',
    'newProject.projectName': 'Имя проекта (необязательно)',
    'newProject.projectNamePlaceholder': 'Генерируется автоматически из имени файла',
    'newProject.next': 'Далее',
    'newProject.back': 'Назад',
    'newProject.create': 'Создать',
    'newProject.createProject': 'Создать проект',
    'newProject.creating': 'Создание…',
    'newProject.creatingProject': 'Создание проекта…',
    'newProject.needFile': 'Пожалуйста, выберите видеофайл.',
    'newProject.needUrl': 'Введите URL или путь к файлу.',
    'newProject.createError': 'Ошибка при создании проекта',
    'newProject.preflightError': 'Ошибка предварительной проверки',

    'workspace.loading': 'Загрузка редактора…',
    'workspace.running': 'Идёт обработка…',
    'workspace.runningHint': 'Страница обновляется автоматически. Можно закрыть вкладку — перевод продолжится на сервере.',
    'workspace.back': 'Назад к списку проектов',
    'workspace.continue': 'Продолжить',
    'workspace.restart': 'Перезапустить',
    'workspace.run': 'Запустить',
    'workspace.translationSettings': 'Настройки перевода',
    'workspace.closeSettings': 'Закрыть панель настроек',
    'workspace.save': 'Сохранить',
    'workspace.saveSegments': 'Сохранить правки сегментов',
    'workspace.noChanges': 'Нет несохранённых изменений',
    'workspace.segmentsSaved': '✓ Сегменты сохранены',
    'workspace.settingsSaved': '✓ Настройки сохранены',
    'workspace.original': 'Оригинал',
    'workspace.aiTranslation': 'Перевод ИИ',
    'workspace.outputNotReady': 'Готовое видео ещё не создано',
    'workspace.translationEditor': 'Редактор перевода',
    'workspace.unsaved': 'Несохранённые правки',
    'workspace.enterTranslation': 'Введите перевод…',
    'workspace.notStartedTitle': 'Перевод ещё не запускался',
    'workspace.notStartedHint': 'Нажмите кнопку ниже — распознавание речи и перевод выполнятся автоматически.',
    'workspace.processing': 'Выполняется обработка…',
    'workspace.processingHint': 'Сегменты появятся автоматически после завершения этапа распознавания речи.',
    'workspace.statusTab': 'Статус',
    'workspace.filesTab': 'Файлы',
    'workspace.noSegments': 'Нет сегментов для анализа.',
    'workspace.noResults': 'Результаты ещё не готовы.',
    'workspace.runError': 'Не удалось запустить обработку',
    'workspace.saveError': 'Ошибка сохранения',
    'workspace.error': 'Ошибка',

    'modal.runAgain': 'Запустить заново?',
    'modal.continueTranslation': 'Продолжить перевод?',
    'modal.close': 'Закрыть',
    'modal.project': 'Проект',
    'modal.resumeNote': 'Уже завершённые этапы будут пропущены. Выполнение продолжится с первого незавершённого или упавшего этапа.',
    'modal.forceNote': 'Все этапы обработки будут запущены заново, включая уже завершённые. Готовые файлы будут перезаписаны.',
    'modal.reviewPrefix': 'сегментов не переведены. Рекомендуем заполнить их в редакторе перед запуском озвучки.',
    'modal.cancel': 'Отмена',
    'modal.runAgainButton': 'Запустить заново',
    'modal.continueButton': 'Продолжить',

    'qa.ready': 'Готово к публикации',
    'qa.checkRecommended': 'Рекомендуется проверка',
    'qa.needsWork': 'Требуется доработка',
    'qa.translated': 'Переведено',
    'qa.needsReview': 'Нужна проверка',
    'qa.longPhrases': 'Длинных фраз',
    'qa.shortPhrases': 'Коротких (<0.3с)',
    'qa.untranslatedIssue': 'сегментов без перевода — исправьте вручную перед TTS',
    'qa.longIssue': 'фраз длиннее 200 символов — возможна обрезка голосовым движком',
    'qa.shortIssue': 'сегментов короче 0.3с — голос может не успеть прочитать',

    'artifact.copyApiUrl': 'Скопировать URL API',
    'artifact.copyApiUrlAria': 'Скопировать URL для API',
    'artifact.download': 'Скачать',

    'stage.extract_audio': '🎙️ Извлечение аудио',
    'stage.transcribe': '📝 Распознавание речи',
    'stage.translate': '🌐 Перевод текста',
    'stage.tts': '🔊 Создание озвучки',
    'stage.render': '🎬 Сборка видео',
    'stage.qa': '✅ Проверка качества',
    'stage.export': '📤 Экспорт субтитров',
    'stage.normalize_audio': '🎚️ Нормализация звука',
    'stage.align': '🔗 Выравнивание',
    'stage.diarize': '👥 Разделение спикеров',
    'stage.glossary': '📖 Применение глоссария',
    'stage.review': '🔍 Ревью',
    'stage.postprocess': '⚙️ Постобработка',
    'status.created': 'Создан',
    'status.running': 'Выполняется',
    'status.completed': 'Завершён',
    'status.failed': 'Ошибка',
    'status.skipped': 'Пропущен',
    'status.pending': 'Ожидает',
    'provider.fake': 'Быстрый тест (демо-режим, без реального перевода)',
    'provider.legacy': 'Полный перевод (распознавание + перевод + озвучка)',
    'providerWarning.legacy': 'Полный перевод видео занимает несколько минут. Не закрывайте страницу — статус обновится автоматически.',
    'providerWarning.fake': 'Это демо-режим: перевод не выполняется, результат будет пустым. Используйте для проверки интерфейса.',
  },
  en: {
    'app.title': 'AI Translator',
    'app.themeLight': 'Light theme',
    'app.themeDark': 'Dark theme',
    'app.themeToggle': 'Toggle theme',
    'nav.dashboard': 'My translations',
    'nav.newProject': 'New translation',
    'nav.settings': 'Settings',

    'dashboard.title': 'My translations',
    'dashboard.subtitle': 'Load a project by name or select it from the list below.',
    'dashboard.searchPlaceholder': 'Project name, for example: my-video-en-ru…',
    'dashboard.find': 'Find',
    'dashboard.refreshList': 'Refresh list',
    'dashboard.openEditor': 'Open editor',
    'dashboard.run': 'Start translation',
    'dashboard.restart': 'Restart all',
    'dashboard.translationDirection': 'Translation direction',
    'dashboard.segmentsRecognized': 'Recognized segments',
    'dashboard.progress': 'Processing progress',
    'dashboard.notStarted': 'Processing has not started yet.',
    'dashboard.noProjectTitle': 'No project selected',
    'dashboard.noProjectText': 'Enter a project name in search or select it below.',
    'dashboard.allProjects': 'All projects',
    'dashboard.sortedByUpdate': 'Sorted by last update time.',
    'dashboard.found': 'Found',
    'dashboard.status': 'Status',
    'dashboard.editor': 'Editor',
    'dashboard.empty': 'No projects yet. Create your first translation.',
    'dashboard.segmentShort': 'seg.',
    'dashboard.loadError': 'Could not load project',
    'dashboard.runError': 'Could not start translation',

    'settings.title': 'Settings',
    'settings.subtitle': 'Application preferences stored in this browser.',
    'settings.integrations': 'Integrations',
    'settings.webhookLabel': 'Webhook URL (n8n)',
    'settings.webhookHelp': 'This URL will receive a notification when each translation finishes.',
    'settings.providerLabel': 'Default processing engine',
    'settings.providerHelp': 'Used for new projects and can be changed on step 1.',
    'settings.appearance': 'Appearance',
    'settings.themeLabel': 'Theme',
    'settings.themeDark': 'Dark (default)',
    'settings.themeLight': 'Light',
    'settings.themeSystem': 'System',
    'settings.largeText': 'Large text for low vision',
    'settings.languageLabel': 'Interface language',
    'settings.languageHelp': 'Russian is the default; English is available for demos and external users.',
    'settings.on': 'On',
    'settings.off': 'Off',
    'settings.save': 'Save settings',
    'settings.saved': 'Saved!',

    'newProject.title': 'New translation',
    'newProject.subtitle': 'Upload a video and the AI pipeline will handle the rest.',
    'newProject.stepFile': 'Video file',
    'newProject.stepParams': 'Parameters',
    'newProject.stepSettings': 'Settings',
    'newProject.uploadFile': 'Upload file',
    'newProject.urlPath': 'URL / server path',
    'newProject.dropVideo': 'Drop video here',
    'newProject.clickToChoose': 'or click to choose a file',
    'newProject.changeFile': 'Click or drop another file to replace it',
    'newProject.projectName': 'Project name (optional)',
    'newProject.projectNamePlaceholder': 'Generated from the file name automatically',
    'newProject.next': 'Next',
    'newProject.back': 'Back',
    'newProject.create': 'Create',
    'newProject.createProject': 'Create project',
    'newProject.creating': 'Creating…',
    'newProject.creatingProject': 'Creating project…',
    'newProject.needFile': 'Please choose a video file.',
    'newProject.needUrl': 'Enter a URL or file path.',
    'newProject.createError': 'Project creation failed',
    'newProject.preflightError': 'Preflight check failed',

    'workspace.loading': 'Loading editor…',
    'workspace.running': 'Processing…',
    'workspace.runningHint': 'The page refreshes automatically. You can close the tab; translation continues on the server.',
    'workspace.back': 'Back to project list',
    'workspace.continue': 'Continue',
    'workspace.restart': 'Restart',
    'workspace.run': 'Run',
    'workspace.translationSettings': 'Translation settings',
    'workspace.closeSettings': 'Close settings panel',
    'workspace.save': 'Save',
    'workspace.saveSegments': 'Save segment edits',
    'workspace.noChanges': 'No unsaved changes',
    'workspace.segmentsSaved': '✓ Segments saved',
    'workspace.settingsSaved': '✓ Settings saved',
    'workspace.original': 'Original',
    'workspace.aiTranslation': 'AI translation',
    'workspace.outputNotReady': 'Translated video is not ready yet',
    'workspace.translationEditor': 'Translation editor',
    'workspace.unsaved': 'Unsaved edits',
    'workspace.enterTranslation': 'Enter translation…',
    'workspace.notStartedTitle': 'Translation has not started yet',
    'workspace.notStartedHint': 'Click below and speech recognition plus translation will run automatically.',
    'workspace.processing': 'Processing…',
    'workspace.processingHint': 'Segments will appear automatically after speech recognition finishes.',
    'workspace.statusTab': 'Status',
    'workspace.filesTab': 'Files',
    'workspace.noSegments': 'No segments to analyze.',
    'workspace.noResults': 'Results are not ready yet.',
    'workspace.runError': 'Could not start processing',
    'workspace.saveError': 'Save failed',
    'workspace.error': 'Error',

    'modal.runAgain': 'Run again?',
    'modal.continueTranslation': 'Continue translation?',
    'modal.close': 'Close',
    'modal.project': 'Project',
    'modal.resumeNote': 'Completed stages will be skipped. Execution continues from the first unfinished or failed stage.',
    'modal.forceNote': 'All processing stages will run again, including completed ones. Existing files will be overwritten.',
    'modal.reviewPrefix': 'segments are untranslated. Fill them in the editor before text-to-speech.',
    'modal.cancel': 'Cancel',
    'modal.runAgainButton': 'Run again',
    'modal.continueButton': 'Continue',

    'qa.ready': 'Ready to publish',
    'qa.checkRecommended': 'Review recommended',
    'qa.needsWork': 'Needs fixes',
    'qa.translated': 'Translated',
    'qa.needsReview': 'Needs review',
    'qa.longPhrases': 'Long phrases',
    'qa.shortPhrases': 'Short (<0.3s)',
    'qa.untranslatedIssue': 'segments are untranslated — fix them manually before TTS',
    'qa.longIssue': 'phrases are longer than 200 characters — speech engine may trim them',
    'qa.shortIssue': 'segments are shorter than 0.3s — speech may not fit',

    'artifact.copyApiUrl': 'Copy API URL',
    'artifact.copyApiUrlAria': 'Copy API URL',
    'artifact.download': 'Download',

    'stage.extract_audio': '🎙️ Audio extraction',
    'stage.transcribe': '📝 Speech recognition',
    'stage.translate': '🌐 Text translation',
    'stage.tts': '🔊 Voice generation',
    'stage.render': '🎬 Video rendering',
    'stage.qa': '✅ Quality check',
    'stage.export': '📤 Subtitle export',
    'stage.normalize_audio': '🎚️ Audio normalization',
    'stage.align': '🔗 Alignment',
    'stage.diarize': '👥 Speaker split',
    'stage.glossary': '📖 Glossary',
    'stage.review': '🔍 Review',
    'stage.postprocess': '⚙️ Post-processing',
    'status.created': 'Created',
    'status.running': 'Running',
    'status.completed': 'Completed',
    'status.failed': 'Error',
    'status.skipped': 'Skipped',
    'status.pending': 'Pending',
    'provider.fake': 'Fast test (demo mode, no real translation)',
    'provider.legacy': 'Full translation (speech recognition + translation + voice-over)',
    'providerWarning.legacy': 'Full video translation takes several minutes. Keep the page open; status updates automatically.',
    'providerWarning.fake': 'Demo mode: translation is not performed and the result will be empty. Use it for UI checks.',
  },
};

export const STATUS_EMOJI: Record<string, string> = {
  created: '🕐',
  running: '⚙️',
  completed: '✅',
  failed: '❌',
  skipped: '⏭️',
  pending: '⏳',
};

export function currentLocale(): AppLocale {
  return getPersistedLocale();
}

export function t(key: string, locale: AppLocale = currentLocale()): string {
  return TEXT[locale][key] ?? TEXT.ru[key] ?? key;
}

export function stageLabel(raw: string, locale: AppLocale = currentLocale()): string {
  const key = `stage.${raw}`;
  const value = t(key, locale);
  return value === key ? raw.replace(/_/g, ' ') : value;
}

export function statusLabel(raw: string, locale: AppLocale = currentLocale()): string {
  const key = `status.${raw}`;
  const value = t(key, locale);
  return value === key ? raw : value;
}

export function providerLabel(raw: string, locale: AppLocale = currentLocale()): string {
  return t(`provider.${raw}`, locale);
}

export function providerWarning(raw: string, locale: AppLocale = currentLocale()): string | undefined {
  const value = t(`providerWarning.${raw}`, locale);
  return value.startsWith('providerWarning.') ? undefined : value;
}

export function providerLabels(locale: AppLocale = currentLocale()): Record<string, string> {
  return {
    fake: providerLabel('fake', locale),
    legacy: providerLabel('legacy', locale),
  };
}

export function providerWarnings(locale: AppLocale = currentLocale()): Record<string, string | undefined> {
  return {
    fake: providerWarning('fake', locale),
    legacy: providerWarning('legacy', locale),
  };
}

/** Совместимость со старыми тестами и компонентами, которые читают константы. */
export const PROVIDER_LABELS = providerLabels('ru');
export const PROVIDER_WARNINGS = providerWarnings('ru');

/** QA: нужна ли ручная проверка сегментов? */
export function needsReviewCount(segments: Array<{ translated_text?: string; source_text: string }>): number {
  return segments.filter(s => {
    const translated = (s.translated_text ?? '').trim();
    const source = s.source_text.trim();
    return !translated || translated === source;
  }).length;
}
