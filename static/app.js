(() => {
  'use strict';

  const root = document.documentElement;
  const THEME_KEY = 'notas-theme';
  const media = window.matchMedia('(prefers-color-scheme: dark)');
  const NOTAS = window.NOTAS || {};

  const themeLabels = {
    system: 'Tema del sistema',
    light: 'Tema claro',
    dark: 'Tema oscuro'
  };

  function themePref() {
    try {
      return localStorage.getItem(THEME_KEY) || 'system';
    } catch (error) {
      return 'system';
    }
  }

  function resolveTheme(pref) {
    return pref === 'dark' || (pref === 'system' && media.matches) ? 'dark' : 'light';
  }

  function applyTheme(pref) {
    const theme = resolveTheme(pref);
    root.dataset.theme = theme;
    root.dataset.themePref = pref;

    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', theme === 'dark' ? '#0b1514' : '#0f766e');

    const button = document.getElementById('theme-toggle');
    if (button) {
      button.setAttribute('aria-label', `${themeLabels[pref]}. Cambiar tema`);
      button.setAttribute('title', themeLabels[pref]);
    }
  }

  document.getElementById('theme-toggle')?.addEventListener('click', () => {
    const order = ['system', 'light', 'dark'];
    const next = order[(order.indexOf(themePref()) + 1) % order.length];
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch (error) {
      /* localStorage puede estar bloqueado */
    }
    applyTheme(next);
  });

  if (media.addEventListener) {
    media.addEventListener('change', () => {
      if (themePref() === 'system') applyTheme('system');
    });
  }
  applyTheme(themePref());

  function showError(element, message) {
    if (!element) return;
    element.textContent = message || 'Algo salió mal. Inténtalo de nuevo.';
    element.hidden = false;
  }

  function hideError(element) {
    if (!element) return;
    element.hidden = true;
    element.textContent = '';
  }

  function showOk(element, message) {
    if (!element) return;
    element.textContent = message;
    element.hidden = false;
  }

  function hideOk(element) {
    if (!element) return;
    element.hidden = true;
    element.textContent = '';
  }

  async function readError(response) {
    try {
      const data = await response.json();
      if (Array.isArray(data.detail)) {
        return data.detail.map((item) => item.msg).join(', ');
      }
      return data.detail || 'Algo salió mal.';
    } catch (error) {
      try {
        return (await response.text()) || 'Algo salió mal.';
      } catch (inner) {
        return 'Algo salió mal.';
      }
    }
  }

  document.querySelectorAll('[data-close-dialog]').forEach((button) => {
    button.addEventListener('click', () => button.closest('dialog')?.close());
  });

  document.querySelectorAll('dialog').forEach((dialog) => {
    dialog.addEventListener('click', (event) => {
      if (event.target === dialog) dialog.close();
    });
  });

  if (NOTAS.focusSearch) {
    const input = document.getElementById('search-input');
    if (input) {
      input.focus();
      input.select();
    }
  }

  /* ---------- Árbol de carpetas plegable ---------- */

  const FOLDER_STATE_KEY = 'notas-folder-state';
  let folderState = {};
  try {
    folderState = JSON.parse(localStorage.getItem(FOLDER_STATE_KEY)) || {};
  } catch (error) {
    folderState = {};
  }

  const selectedFolder = NOTAS.folder || '';
  const selectedAncestors = new Set();
  if (selectedFolder) {
    const parts = selectedFolder.split('/');
    for (let index = 1; index < parts.length; index += 1) {
      selectedAncestors.add(parts.slice(0, index).join('/'));
    }
  }

  const folderNodes = document.querySelectorAll('[data-folder-node]');

  function saveFolderState() {
    try {
      localStorage.setItem(FOLDER_STATE_KEY, JSON.stringify(folderState));
    } catch (error) {
      /* localStorage puede estar bloqueado */
    }
  }

  function applyFolderState() {
    folderNodes.forEach((node) => {
      const path = node.dataset.folderNode;
      const toggle = node.querySelector(':scope > .folder-row .folder-toggle');
      const children = node.querySelector(':scope > .folder-children');
      if (!toggle || !children) return;
      const hasState = Object.prototype.hasOwnProperty.call(folderState, path);
      const open = hasState ? Boolean(folderState[path]) : selectedAncestors.has(path);
      children.hidden = !open;
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      const name = node.dataset.folderName || '';
      toggle.setAttribute('aria-label', `${open ? 'Contraer' : 'Expandir'} ${name}`);
      toggle.setAttribute('title', `${open ? 'Contraer' : 'Expandir'} ${name}`);
    });
  }

  folderNodes.forEach((node) => {
    const toggle = node.querySelector(':scope > .folder-row .folder-toggle');
    if (!toggle) return;
    toggle.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      const path = node.dataset.folderNode;
      const open = toggle.getAttribute('aria-expanded') !== 'true';
      folderState[path] = open;
      saveFolderState();
      applyFolderState();
    });
  });

  document.getElementById('collapse-folders')?.addEventListener('click', () => {
    folderNodes.forEach((node) => {
      folderState[node.dataset.folderNode] = false;
    });
    saveFolderState();
    applyFolderState();
  });

  applyFolderState();

  /* ---------- Editor: autoguardado y vista previa ---------- */

  const noteId = NOTAS.noteId || null;
  const titleInput = document.getElementById('note-title');
  const contentInput = document.getElementById('note-content');
  const saveStatus = document.getElementById('save-status');

  function setStatus(text, isError = false) {
    if (!saveStatus) return;
    saveStatus.textContent = text;
    saveStatus.classList.toggle('is-error', isError);
  }

  if (noteId && titleInput && contentInput) {
    let timer = null;
    let saving = false;
    let dirty = false;

    const save = async () => {
      if (saving) {
        dirty = true;
        return;
      }
      const title = titleInput.value.trim();
      if (!title) {
        setStatus('El título no puede estar vacío', true);
        return;
      }

      saving = true;
      dirty = false;
      setStatus('Guardando…');

      try {
        const response = await fetch(`/api/notes/${encodeURIComponent(noteId)}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title, content: contentInput.value })
        });
        if (!response.ok) throw new Error(await readError(response));
        setStatus('Guardado');
        const listTitle = document.querySelector(
          `[data-note-item="${CSS.escape(noteId)}"] .note-title`
        );
        if (listTitle) listTitle.textContent = title;
      } catch (error) {
        console.error(error);
        dirty = true;
        setStatus('Error al guardar', true);
      } finally {
        saving = false;
        if (dirty) save();
      }
    };

    const schedule = () => {
      dirty = true;
      setStatus('Sin guardar');
      window.clearTimeout(timer);
      timer = window.setTimeout(save, 800);
    };

    titleInput.addEventListener('input', schedule);
    contentInput.addEventListener('input', schedule);

    document.addEventListener('keydown', (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
        event.preventDefault();
        dirty = true;
        save();
      }
    });

    window.addEventListener('beforeunload', (event) => {
      if (!dirty) return;
      save();
      event.preventDefault();
      event.returnValue = '';
    });
  }

  const previewButton = document.getElementById('preview-toggle');
  const previewLabel = document.getElementById('preview-label');
  const previewElement = document.getElementById('note-preview');

  if (previewButton && previewElement && contentInput) {
    let visible = false;
    let timer = null;

    const renderPreview = async () => {
      const data = new FormData();
      data.append('content', contentInput.value);
      try {
        const response = await fetch('/partials/preview', { method: 'POST', body: data });
        if (response.ok) previewElement.innerHTML = await response.text();
      } catch (error) {
        console.error(error);
      }
    };

    const showPreview = async () => {
      visible = true;
      contentInput.hidden = true;
      previewElement.hidden = false;
      if (previewLabel) previewLabel.textContent = 'Escribir';
      previewButton.setAttribute('aria-label', 'Escribir');
      await renderPreview();
    };

    const hidePreview = () => {
      visible = false;
      previewElement.hidden = true;
      contentInput.hidden = false;
      if (previewLabel) previewLabel.textContent = 'Vista previa';
      previewButton.setAttribute('aria-label', 'Vista previa');
    };

    previewButton.addEventListener('click', () => {
      if (visible) hidePreview();
      else showPreview();
    });

    contentInput.addEventListener('input', () => {
      if (!visible) return;
      window.clearTimeout(timer);
      timer = window.setTimeout(renderPreview, 400);
    });
  }

  /* ---------- Notas ---------- */

  const noteDialog = document.getElementById('note-dialog');
  const noteForm = document.getElementById('note-form');
  const newNoteTitle = document.getElementById('new-note-title');
  const newNoteFolder = document.getElementById('new-note-folder');
  const noteError = document.getElementById('note-form-error');

  function openNoteDialog() {
    if (!noteDialog) return;
    hideError(noteError);
    noteForm?.reset();
    if (newNoteFolder) newNoteFolder.value = NOTAS.folder || '';
    noteDialog.showModal();
    window.setTimeout(() => newNoteTitle?.focus(), 30);
  }

  document.querySelectorAll('[data-new-note]').forEach((button) => {
    button.addEventListener('click', openNoteDialog);
  });

  noteForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    hideError(noteError);
    const title = newNoteTitle?.value.trim() || '';
    if (!title) {
      showError(noteError, 'Ponle un título a la nota.');
      return;
    }
    const folder = newNoteFolder?.value || '';
    try {
      const response = await fetch('/api/notes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder, title, content: '' })
      });
      if (!response.ok) {
        showError(noteError, await readError(response));
        return;
      }
      const note = await response.json();
      window.location.href = `/notes?folder=${encodeURIComponent(folder)}&note=${encodeURIComponent(note.id)}`;
    } catch (error) {
      console.error(error);
      showError(noteError, 'No se pudo crear la nota.');
    }
  });

  const folderDialog = document.getElementById('folder-dialog');
  const folderForm = document.getElementById('folder-form');
  const folderName = document.getElementById('folder-name');
  const folderParent = document.getElementById('folder-parent');
  const folderMode = document.getElementById('folder-mode');
  const folderOriginal = document.getElementById('folder-original');
  const folderDelete = document.getElementById('folder-delete');
  const folderDialogTitle = document.getElementById('folder-dialog-title');
  const folderError = document.getElementById('folder-form-error');

  function openFolderDialog(mode, path = '', name = '') {
    if (!folderDialog) return;
    hideError(folderError);
    folderMode.value = mode;
    folderOriginal.value = path;
    folderDialogTitle.textContent = mode === 'edit' ? 'Editar carpeta' : 'Nueva carpeta';
    folderDelete.hidden = mode !== 'edit';

    if (mode === 'edit') {
      folderName.value = name;
      const parent = path.includes('/') ? path.slice(0, path.lastIndexOf('/')) : '';
      folderParent.value = parent;
    } else {
      folderName.value = '';
      folderParent.value = NOTAS.folder || '';
    }

    folderDialog.showModal();
    window.setTimeout(() => folderName.focus(), 30);
  }

  document.getElementById('new-folder-btn')?.addEventListener('click', () => {
    openFolderDialog('create');
  });

  document.querySelectorAll('[data-folder-path]').forEach((button) => {
    button.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      openFolderDialog('edit', button.dataset.folderPath, button.dataset.folderName);
    });
  });

  folderForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    hideError(folderError);
    const name = folderName.value.trim();
    if (!name) {
      showError(folderError, 'Ponle un nombre a la carpeta.');
      return;
    }

    const parent = folderParent.value;
    const target = parent ? `${parent}/${name}` : name;
    const mode = folderMode.value;

    try {
      const response =
        mode === 'edit'
          ? await fetch('/api/folders', {
              method: 'PATCH',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ path: folderOriginal.value, new_path: target })
            })
          : await fetch('/api/folders', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ path: target })
            });

      if (!response.ok) {
        showError(folderError, await readError(response));
        return;
      }

      const current = NOTAS.folder || '';
      const original = folderOriginal.value;
      const nextFolder =
        mode === 'edit' && (current === original || current.startsWith(original + '/'))
          ? target + current.slice(original.length)
          : current;

      window.location.href = `/notes?folder=${encodeURIComponent(nextFolder)}`;
    } catch (error) {
      console.error(error);
      showError(folderError, 'No se pudo guardar la carpeta.');
    }
  });

  folderDelete?.addEventListener('click', async () => {
    const path = folderOriginal.value;
    if (!path) return;
    if (!window.confirm(`¿Eliminar la carpeta “${path}” y todo su contenido?`)) return;

    try {
      const response = await fetch(
        `/api/folders?path=${encodeURIComponent(path)}&recursive=true`,
        { method: 'DELETE' }
      );
      if (!response.ok) {
        showError(folderError, await readError(response));
        return;
      }
      window.location.href = '/notes';
    } catch (error) {
      console.error(error);
      showError(folderError, 'No se pudo eliminar la carpeta.');
    }
  });

  const deleteNoteDialog = document.getElementById('delete-note-dialog');
  const deleteNoteForm = document.getElementById('delete-note-form');

  document.getElementById('delete-note-btn')?.addEventListener('click', () => {
    deleteNoteDialog?.showModal();
  });

  deleteNoteForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!noteId) return;
    try {
      const response = await fetch(`/api/notes/${encodeURIComponent(noteId)}`, {
        method: 'DELETE'
      });
      if (!response.ok) {
        window.alert(await readError(response));
        return;
      }
      window.location.href = `/notes?folder=${encodeURIComponent(NOTAS.folder || '')}`;
    } catch (error) {
      console.error(error);
      window.alert('No se pudo eliminar la nota.');
    }
  });

  /* ---------- Historial de la nota ---------- */

  const historyButton = document.getElementById('history-note-btn');
  const historyDialog = document.getElementById('history-dialog');
  const historyBody = document.getElementById('history-body');

  if (historyButton && historyDialog && historyBody && noteId) {
    let historyVersions = [];
    let selectedVersionId = null;

    function historyDate(value) {
      if (!value) return '';
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return value;
      return date.toLocaleString('es-CO', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    }

    function historySource(source) {
      const value = String(source || '');
      if (value === 'create') return 'Creación';
      if (value === 'snapshot') return 'Inicial';
      if (value === 'before-restore') return 'Antes de restaurar';
      if (value.startsWith('restore:')) return 'Restaurada';
      return 'Autoguardado';
    }

    async function selectHistoryVersion(versionId) {
      selectedVersionId = versionId;
      document.querySelectorAll('.history-item').forEach((item) => {
        item.classList.toggle('is-active', Number(item.dataset.versionId) === versionId);
      });
      const preview = document.getElementById('history-preview');
      if (!preview) return;
      const pre = preview.querySelector('pre');
      if (pre) pre.textContent = 'Cargando…';
      try {
        const response = await fetch(
          `/api/notes/${encodeURIComponent(noteId)}/versions/${versionId}`
        );
        if (!response.ok) throw new Error(await readError(response));
        const data = await response.json();
        if (pre) pre.textContent = data.content || '(vacía)';
        const restore = document.getElementById('restore-version');
        if (restore) restore.disabled = false;
      } catch (error) {
        console.error(error);
        if (pre) pre.textContent = 'No se pudo cargar la versión.';
      }
    }

    async function restoreHistoryVersion() {
      if (!selectedVersionId) return;
      if (
        !window.confirm(
          '¿Restaurar esta versión? La nota actual será reemplazada y se guardará una versión antes de hacerlo.'
        )
      ) {
        return;
      }
      try {
        const response = await fetch(
          `/api/notes/${encodeURIComponent(noteId)}/versions/${selectedVersionId}/restore`,
          { method: 'POST' }
        );
        if (!response.ok) throw new Error(await readError(response));
        const data = await response.json();
        if (titleInput) titleInput.value = data.title;
        if (contentInput) contentInput.value = data.content;
        const status = document.getElementById('save-status');
        if (status) {
          status.textContent = 'Guardado';
          status.classList.remove('is-error');
        }
        const listTitle = document.querySelector(
          `[data-note-item="${CSS.escape(noteId)}"] .note-title`
        );
        if (listTitle) listTitle.textContent = data.title;
        historyDialog.close();
      } catch (error) {
        console.error(error);
        window.alert('No se pudo restaurar la versión.');
      }
    }

    function renderHistory() {
      historyBody.replaceChildren();
      if (!historyVersions.length) {
        const empty = document.createElement('p');
        empty.className = 'muted';
        empty.textContent = 'No hay versiones guardadas.';
        historyBody.append(empty);
        return;
      }

      const list = document.createElement('div');
      list.className = 'history-list';
      historyVersions.forEach((version) => {
        const item = document.createElement('button');
        item.type = 'button';
        item.className = 'history-item';
        item.dataset.versionId = version.id;

        const date = document.createElement('span');
        date.className = 'history-date';
        date.textContent = historyDate(version.note_updated_at || version.created_at);
        const meta = document.createElement('span');
        meta.className = 'history-meta';
        meta.textContent = `${historySource(version.source)} · ${version.size} caracteres`;

        item.append(date, meta);
        item.addEventListener('click', () => selectHistoryVersion(version.id));
        list.append(item);
      });
      historyBody.append(list);

      const preview = document.createElement('div');
      preview.className = 'history-preview';
      preview.id = 'history-preview';
      const pre = document.createElement('pre');
      pre.textContent = 'Selecciona una versión para verla.';
      preview.append(pre);
      historyBody.append(preview);

      const actions = document.createElement('div');
      actions.className = 'history-actions';
      const restore = document.createElement('button');
      restore.type = 'button';
      restore.className = 'btn-primary';
      restore.id = 'restore-version';
      restore.textContent = 'Restaurar esta versión';
      restore.disabled = true;
      restore.addEventListener('click', restoreHistoryVersion);
      actions.append(restore);
      historyBody.append(actions);
    }

    async function openHistory() {
      selectedVersionId = null;
      historyBody.replaceChildren();
      const loading = document.createElement('p');
      loading.className = 'muted';
      loading.textContent = 'Cargando…';
      historyBody.append(loading);
      historyDialog.showModal();
      try {
        const response = await fetch(
          `/api/notes/${encodeURIComponent(noteId)}/versions`
        );
        if (!response.ok) throw new Error(await readError(response));
        const data = await response.json();
        historyVersions = data.versions || [];
        renderHistory();
      } catch (error) {
        console.error(error);
        historyBody.textContent = 'No se pudo cargar el historial.';
      }
    }

    historyButton.addEventListener('click', openHistory);
  }

  /* ---------- Barra de formato Markdown ---------- */

  function revealNoteEditor() {
    const preview = document.getElementById('note-preview');
    if (!preview || preview.hidden) return;
    preview.hidden = true;
    if (contentInput) contentInput.hidden = false;
    const label = document.getElementById('preview-label');
    if (label) label.textContent = 'Vista previa';
    const button = document.getElementById('preview-toggle');
    if (button) button.setAttribute('aria-label', 'Vista previa');
  }

  function dispatchInput(textarea) {
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
  }

  function wrapInline(textarea, before, after, placeholder) {
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selected = textarea.value.slice(start, end) || placeholder;
    const replacement = before + selected + after;
    textarea.setRangeText(replacement, start, end, 'end');
    textarea.selectionStart = start + before.length;
    textarea.selectionEnd = start + before.length + selected.length;
    dispatchInput(textarea);
    textarea.focus();
  }

  function toggleHeading(textarea, level) {
    const value = textarea.value;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const lineStart = value.lastIndexOf('\n', start - 1) + 1;
    let lineEnd = value.indexOf('\n', end);
    if (lineEnd === -1) lineEnd = value.length;
    const block = value.slice(lineStart, lineEnd);
    const lines = block.split('\n');
    const marker = '#'.repeat(level) + ' ';
    const all = lines.every((line) => line.startsWith(marker));
    const next = lines
      .map((line) => {
        const cleaned = line.replace(/^#{1,6}\s+/, '');
        return all ? cleaned : marker + cleaned;
      })
      .join('\n');
    textarea.setRangeText(next, lineStart, lineEnd, 'end');
    textarea.selectionStart = lineStart;
    textarea.selectionEnd = lineStart + next.length;
    dispatchInput(textarea);
    textarea.focus();
  }

  function toggleLinePrefix(textarea, prefix) {
    const value = textarea.value;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const lineStart = value.lastIndexOf('\n', start - 1) + 1;
    let lineEnd = value.indexOf('\n', end);
    if (lineEnd === -1) lineEnd = value.length;
    const block = value.slice(lineStart, lineEnd);
    const lines = block.split('\n');
    const all = lines.every((line) => line.startsWith(prefix));
    const next = lines
      .map((line) => (all ? line.slice(prefix.length) : prefix + line))
      .join('\n');
    textarea.setRangeText(next, lineStart, lineEnd, 'end');
    textarea.selectionStart = lineStart;
    textarea.selectionEnd = lineStart + next.length;
    dispatchInput(textarea);
    textarea.focus();
  }

  function insertCodeBlock(textarea) {
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selected = textarea.value.slice(start, end) || 'código';
    const replacement = '```\n' + selected + '\n```';
    textarea.setRangeText(replacement, start, end, 'end');
    textarea.selectionStart = start + 4;
    textarea.selectionEnd = start + 4 + selected.length;
    dispatchInput(textarea);
    textarea.focus();
  }

  function insertLink(textarea) {
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const hasSelection = start !== end;
    const text = textarea.value.slice(start, end) || 'texto';
    const replacement = `[${text}](url)`;
    textarea.setRangeText(replacement, start, end, 'end');
    if (hasSelection) {
      textarea.selectionStart = start + text.length + 3;
      textarea.selectionEnd = start + text.length + 6;
    } else {
      textarea.selectionStart = start + 1;
      textarea.selectionEnd = start + 1 + text.length;
    }
    dispatchInput(textarea);
    textarea.focus();
  }

  function insertTable(textarea) {
    const value = textarea.value;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const table = '| Columna 1 | Columna 2 |\n| --- | --- |\n| Texto | Texto |';
    const prefix = start > 0 && value[start - 1] !== '\n' ? '\n\n' : '';
    const suffix = end < value.length && value[end] !== '\n' ? '\n\n' : '';
    const replacement = prefix + table + suffix;
    textarea.setRangeText(replacement, start, end, 'end');
    const cellStart = start + prefix.length + 2;
    textarea.selectionStart = cellStart;
    textarea.selectionEnd = cellStart + 'Columna 1'.length;
    dispatchInput(textarea);
    textarea.focus();
  }

  function insertSeparator(textarea) {
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const replacement = '\n\n---\n\n';
    textarea.setRangeText(replacement, start, end, 'end');
    textarea.selectionStart = start + replacement.length;
    textarea.selectionEnd = start + replacement.length;
    dispatchInput(textarea);
    textarea.focus();
  }

  function toggleChecklist(textarea) {
    const value = textarea.value;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const lineStart = value.lastIndexOf('\n', start - 1) + 1;
    let lineEnd = value.indexOf('\n', end);
    if (lineEnd === -1) lineEnd = value.length;
    const block = value.slice(lineStart, lineEnd);
    const lines = block.split('\n');
    const allUnchecked = lines.every((line) => line.startsWith('- [ ] '));
    const allChecked = lines.every((line) => line.startsWith('- [x] '));
    let next;
    if (allUnchecked) {
      next = lines.map((line) => '- [x] ' + line.slice(6)).join('\n');
    } else if (allChecked) {
      next = lines.map((line) => line.slice(6)).join('\n');
    } else {
      next = lines
        .map((line) => '- [ ] ' + line.replace(/^- \[[ xX]\] /, ''))
        .join('\n');
    }
    textarea.setRangeText(next, lineStart, lineEnd, 'end');
    textarea.selectionStart = lineStart;
    textarea.selectionEnd = lineStart + next.length;
    dispatchInput(textarea);
    textarea.focus();
  }

  function applyFormat(textarea, format) {
    if (textarea === contentInput) revealNoteEditor();
    switch (format) {
      case 'h1':
        toggleHeading(textarea, 1);
        break;
      case 'h2':
        toggleHeading(textarea, 2);
        break;
      case 'bold':
        wrapInline(textarea, '**', '**', 'texto');
        break;
      case 'italic':
        wrapInline(textarea, '*', '*', 'texto');
        break;
      case 'strike':
        wrapInline(textarea, '~~', '~~', 'texto');
        break;
      case 'code':
        wrapInline(textarea, '`', '`', 'código');
        break;
      case 'ul':
        toggleLinePrefix(textarea, '- ');
        break;
      case 'ol':
        toggleLinePrefix(textarea, '1. ');
        break;
      case 'quote':
        toggleLinePrefix(textarea, '> ');
        break;
      case 'codeblock':
        insertCodeBlock(textarea);
        break;
      case 'link':
        insertLink(textarea);
        break;
      case 'table':
        insertTable(textarea);
        break;
      case 'checklist':
        toggleChecklist(textarea);
        break;
      case 'hr':
        insertSeparator(textarea);
        break;
      default:
        break;
    }
  }

  document.querySelectorAll('[data-format-target]').forEach((bar) => {
    const target = document.getElementById(bar.dataset.formatTarget);
    if (!target) return;
    bar.querySelectorAll('[data-format]').forEach((button) => {
      button.addEventListener('click', () => applyFormat(target, button.dataset.format));
    });
  });

  /* ---------- Recordatorios ---------- */

  const reminderForm = document.getElementById('reminder-form');
  if (reminderForm) {
    const reminderError = document.getElementById('reminder-form-error');

    reminderForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      hideError(reminderError);

      const title = document.getElementById('reminder-title')?.value.trim() || '';
      if (!title) {
        showError(reminderError, 'Escribe un título.');
        return;
      }
      const body = document.getElementById('reminder-body')?.value || '';
      const due = document.getElementById('reminder-due')?.value || null;

      try {
        const response = await fetch('/api/reminders', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title,
            body,
            due_at: due,
            timezone: NOTAS.timezone || 'America/Bogota'
          })
        });
        if (!response.ok) {
          showError(reminderError, await readError(response));
          return;
        }
        window.location.reload();
      } catch (error) {
        console.error(error);
        showError(reminderError, 'No se pudo guardar el recordatorio.');
      }
    });

    document.querySelectorAll('.reminder-check').forEach((checkbox) => {
      checkbox.addEventListener('change', async () => {
        const item = checkbox.closest('[data-reminder-id]');
        if (!item) return;
        try {
          await fetch(`/api/reminders/${encodeURIComponent(item.dataset.reminderId)}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ done: checkbox.checked })
          });
          window.location.reload();
        } catch (error) {
          console.error(error);
          checkbox.checked = !checkbox.checked;
        }
      });
    });

    document.querySelectorAll('.reminder-delete').forEach((button) => {
      button.addEventListener('click', async () => {
        const item = button.closest('[data-reminder-id]');
        if (!item) return;
        try {
          const response = await fetch(
            `/api/reminders/${encodeURIComponent(item.dataset.reminderId)}`,
            { method: 'DELETE' }
          );
          if (response.ok) item.remove();
        } catch (error) {
          console.error(error);
        }
      });
    });
  }

  /* ---------- Ajustes de cuenta ---------- */

  const usernameForm = document.getElementById('username-form');
  if (usernameForm) {
    const usernameError = document.getElementById('username-error');
    const usernameOk = document.getElementById('username-ok');

    usernameForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      hideError(usernameError);
      hideOk(usernameOk);

      const newUsername = document.getElementById('new-username').value.trim();
      const currentPassword = document.getElementById('username-current-password').value;

      try {
        const response = await fetch('/api/account', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            username: newUsername,
            current_password: currentPassword
          })
        });
        if (response.status === 401) {
          window.location.href = '/login';
          return;
        }
        if (!response.ok) {
          showError(usernameError, await readError(response));
          return;
        }
        const data = await response.json();
        document.querySelectorAll('.current-username').forEach((element) => {
          element.textContent = data.username;
        });
        showOk(usernameOk, `Usuario actualizado a ${data.username}. Úsalo en el próximo inicio de sesión.`);
        usernameForm.reset();
      } catch (error) {
        console.error(error);
        showError(usernameError, 'No se pudo cambiar el usuario.');
      }
    });
  }

  const passwordForm = document.getElementById('password-form');
  if (passwordForm) {
    const passwordError = document.getElementById('password-error');
    const passwordOk = document.getElementById('password-ok');

    passwordForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      hideError(passwordError);
      hideOk(passwordOk);

      const currentPassword = document.getElementById('current-password').value;
      const newPassword = document.getElementById('new-password').value;
      const confirmPassword = document.getElementById('new-password-confirm').value;

      if (newPassword.length < 8) {
        showError(passwordError, 'La contraseña nueva debe tener al menos 8 caracteres.');
        return;
      }
      if (newPassword !== confirmPassword) {
        showError(passwordError, 'La confirmación no coincide.');
        return;
      }

      try {
        const response = await fetch('/api/account', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            current_password: currentPassword,
            new_password: newPassword
          })
        });
        if (response.status === 401) {
          window.location.href = '/login';
          return;
        }
        if (!response.ok) {
          showError(passwordError, await readError(response));
          return;
        }
        showOk(passwordOk, 'Contraseña actualizada. Tu sesión actual sigue abierta.');
        passwordForm.reset();
      } catch (error) {
        console.error(error);
        showError(passwordError, 'No se pudo cambiar la contraseña.');
      }
    });
  }

  /* ---------- Tokens de API ---------- */

  const tokenList = document.getElementById('token-list');
  if (tokenList) {
    const tokenError = document.getElementById('token-error');
    const tokenForm = document.getElementById('token-form');
    const tokenName = document.getElementById('token-name');
    const ruleFolder = document.getElementById('rule-folder');
    const ruleLevel = document.getElementById('rule-level');
    const addRule = document.getElementById('add-rule');
    const ruleList = document.getElementById('rule-list');
    const tokenDialog = document.getElementById('token-dialog');
    const tokenValue = document.getElementById('token-value');
    const copyToken = document.getElementById('copy-token');
    const editDialog = document.getElementById('token-edit-dialog');
    const editName = document.getElementById('token-edit-name');
    const editError = document.getElementById('token-edit-error');
    const editRuleFolder = document.getElementById('edit-rule-folder');
    const editRuleLevel = document.getElementById('edit-rule-level');
    const editAddRule = document.getElementById('edit-add-rule');
    const editRuleList = document.getElementById('edit-rule-list');
    const saveRules = document.getElementById('save-token-rules');
    const newRuleFolder = document.getElementById('new-rule-folder');
    const editNewFolder = document.getElementById('edit-new-folder');
    const rules = new Map();
    const editRules = new Map();
    let editingToken = null;

    function ruleLabel(path) {
      return path || 'Todas las carpetas';
    }

    function formatTokenDate(value) {
      if (!value) return 'nunca';
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return value;
      return date.toLocaleString('es-CO', {
        day: '2-digit',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit'
      });
    }

    function renderRuleList() {
      ruleList.replaceChildren();
      rules.forEach((level, path) => {
        const item = document.createElement('li');
        const text = document.createElement('span');
        text.textContent = `${ruleLabel(path)}: ${level === 'write' ? 'escribir' : 'leer'}`;
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'rule-remove';
        remove.textContent = 'Quitar';
        remove.addEventListener('click', () => {
          rules.delete(path);
          renderRuleList();
        });
        item.append(text, remove);
        ruleList.append(item);
      });
    }

    function renderEditRules() {
      editRuleList.replaceChildren();
      editRules.forEach((level, path) => {
        const item = document.createElement('li');
        const text = document.createElement('span');
        text.textContent = `${ruleLabel(path)}: ${level === 'write' ? 'escribir' : 'leer'}`;
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'rule-remove';
        remove.textContent = 'Quitar';
        remove.addEventListener('click', () => {
          editRules.delete(path);
          renderEditRules();
        });
        item.append(text, remove);
        editRuleList.append(item);
      });
    }

    function openEditToken(token) {
      editingToken = token;
      editRules.clear();
      for (const rule of token.rules) {
        editRules.set(rule.path, rule.level);
      }
      editName.textContent = token.name;
      hideError(editError);
      renderEditRules();
      editDialog.showModal();
    }

    editAddRule?.addEventListener('click', () => {
      editRules.set(editRuleFolder.value, editRuleLevel.value);
      renderEditRules();
    });

    saveRules?.addEventListener('click', async () => {
      if (!editingToken) return;
      hideError(editError);
      const payloadRules = Array.from(editRules.entries()).map(([path, level]) => ({
        path,
        level
      }));
      try {
        const response = await fetch(
          `/api/tokens/${encodeURIComponent(editingToken.id)}`,
          {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rules: payloadRules })
          }
        );
        if (response.status === 401) {
          window.location.href = '/login';
          return;
        }
        if (!response.ok) {
          showError(editError, await readError(response));
          return;
        }
        editDialog.close();
        await loadTokens();
      } catch (error) {
        console.error(error);
        showError(editError, 'No se pudieron guardar los permisos.');
      }
    });

    async function loadFolders() {
      try {
        const response = await fetch('/api/tree');
        if (!response.ok) return;
        const data = await response.json();
        for (const select of [ruleFolder, editRuleFolder]) {
          if (!select) continue;
          while (select.options.length > 1) select.remove(1);
        }
        for (const folder of data.folders) {
          for (const select of [ruleFolder, editRuleFolder]) {
            if (!select) continue;
            const option = document.createElement('option');
            option.value = folder;
            const depth = folder.split('/').length - 1;
            option.textContent = '— '.repeat(depth) + folder.split('/').pop();
            select.append(option);
          }
        }
      } catch (error) {
        console.error(error);
      }
    }

    async function createFolder() {
      const path = window.prompt('Nombre de la carpeta (puedes usar padre/hijo):');
      if (!path || !path.trim()) return;
      const errorElement = editDialog?.open ? editError : tokenError;
      hideError(errorElement);
      try {
        const response = await fetch('/api/folders', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: path.trim() })
        });
        if (!response.ok) {
          if (response.status === 409) {
            showError(errorElement, 'Esa carpeta ya existe.');
            return;
          }
          showError(errorElement, await readError(response));
          return;
        }
        const data = await response.json();
        await loadFolders();
        if (ruleFolder) ruleFolder.value = data.path;
        if (editRuleFolder) editRuleFolder.value = data.path;
      } catch (error) {
        console.error(error);
        showError(errorElement, 'No se pudo crear la carpeta.');
      }
    }

    newRuleFolder?.addEventListener('click', createFolder);
    editNewFolder?.addEventListener('click', createFolder);

    function renderTokens(tokens) {
      tokenList.replaceChildren();
      if (!tokens.length) {
        const empty = document.createElement('p');
        empty.className = 'muted';
        empty.textContent = 'No hay tokens.';
        tokenList.append(empty);
        return;
      }
      tokens.forEach((token) => {
        const row = document.createElement('div');
        row.className = 'token-row';

        const info = document.createElement('div');
        info.className = 'token-info';
        const name = document.createElement('strong');
        name.textContent = token.name;
        const rulesText = document.createElement('span');
        rulesText.className = 'token-rules';
        rulesText.textContent = token.rules.length
          ? token.rules
              .map((rule) => `${ruleLabel(rule.path)}: ${rule.level === 'write' ? 'escribir' : 'leer'}`)
              .join(' · ')
          : 'Solo recordatorios';
        const meta = document.createElement('span');
        meta.className = 'token-meta';
        meta.textContent = `Creado ${formatTokenDate(token.created_at)} · Último uso ${
          token.last_used_at ? formatTokenDate(token.last_used_at) : 'nunca'
        }`;
        info.append(name, rulesText, meta);

        const actions = document.createElement('div');
        actions.className = 'token-actions';

        const edit = document.createElement('button');
        edit.type = 'button';
        edit.className = 'icon-btn';
        edit.title = 'Editar permisos';
        edit.setAttribute('aria-label', `Editar permisos de ${token.name}`);
        edit.innerHTML =
          '<svg class="icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/></svg>';
        edit.addEventListener('click', () => openEditToken(token));

        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'icon-btn danger';
        remove.title = 'Eliminar token';
        remove.setAttribute('aria-label', `Eliminar token ${token.name}`);
        remove.innerHTML =
          '<svg class="icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M6 6l1 14h10l1-14"/><path d="M10 11v5M14 11v5"/></svg>';
        remove.addEventListener('click', () => deleteToken(token));

        actions.append(edit, remove);
        row.append(info, actions);
        tokenList.append(row);
      });
    }

    async function loadTokens() {
      try {
        const response = await fetch('/api/tokens');
        if (response.status === 401) {
          window.location.href = '/login';
          return;
        }
        if (!response.ok) return;
        const data = await response.json();
        renderTokens(data.tokens || []);
      } catch (error) {
        console.error(error);
      }
    }

    async function deleteToken(token) {
      if (!window.confirm(`¿Eliminar el token "${token.name}"? El agente perderá acceso.`)) {
        return;
      }
      try {
        const response = await fetch(`/api/tokens/${encodeURIComponent(token.id)}`, {
          method: 'DELETE'
        });
        if (response.status === 401) {
          window.location.href = '/login';
          return;
        }
        if (!response.ok) {
          showError(tokenError, await readError(response));
          return;
        }
        await loadTokens();
      } catch (error) {
        console.error(error);
        showError(tokenError, 'No se pudo eliminar el token.');
      }
    }

    addRule?.addEventListener('click', () => {
      rules.set(ruleFolder.value, ruleLevel.value);
      renderRuleList();
    });

    tokenForm?.addEventListener('submit', async (event) => {
      event.preventDefault();
      hideError(tokenError);

      const name = tokenName.value.trim();
      if (!name) {
        showError(tokenError, 'Ponle un nombre al token.');
        return;
      }

      const payloadRules = Array.from(rules.entries()).map(([path, level]) => ({
        path,
        level
      }));

      try {
        const response = await fetch('/api/tokens', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, rules: payloadRules })
        });
        if (response.status === 401) {
          window.location.href = '/login';
          return;
        }
        if (!response.ok) {
          showError(tokenError, await readError(response));
          return;
        }
        const data = await response.json();
        tokenValue.value = data.token;
        tokenDialog.showModal();
        tokenName.value = '';
        rules.clear();
        renderRuleList();
        await loadTokens();
      } catch (error) {
        console.error(error);
        showError(tokenError, 'No se pudo crear el token.');
      }
    });

    copyToken?.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(tokenValue.value);
      } catch (error) {
        tokenValue.select();
        document.execCommand('copy');
      }
      copyToken.textContent = 'Copiado';
      window.setTimeout(() => {
        copyToken.textContent = 'Copiar';
      }, 2000);
    });

    loadFolders();
    renderRuleList();
    loadTokens();
  }
})();
