import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || '';

function getErrorMessage(error, fallback) {
  if (error?.response?.status === 413) return '\u9644\u4ef6\u8fc7\u5927\uff0c\u8bf7\u538b\u7f29\u540e\u91cd\u8bd5\uff08\u5f53\u524d\u9650\u5236 200MB\uff09';
  return error?.response?.data?.detail || fallback;
}

function normalizeStringArray(values) {
  if (!Array.isArray(values)) return [];
  const seen = new Set();
  const result = [];
  values.forEach((item) => {
    const normalized = String(item || '').trim();
    const key = normalized.toLowerCase();
    if (!normalized || seen.has(key)) return;
    seen.add(key);
    result.push(normalized);
  });
  return result;
}

function normalizePublishScope(value) {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized === 'class' || normalized === 'student') return normalized;
  return 'all';
}

function ExperimentEditorModal({ username, course, initialExperiment, onClose, onCreate, onUpdate }) {
  const isEdit = Boolean(initialExperiment);
  const [formData, setFormData] = useState(() => ({
    title: initialExperiment?.title || '',
    description: initialExperiment?.description || '',
    difficulty: initialExperiment?.difficulty || '\u4e2d\u7ea7',
    tags: Array.isArray(initialExperiment?.tags) ? initialExperiment.tags.join(', ') : '',
    notebook_path: initialExperiment?.notebook_path || '',
    published: initialExperiment ? Boolean(initialExperiment?.published) : true,
    publish_scope: normalizePublishScope(initialExperiment?.publish_scope),
    target_class_names: normalizeStringArray(initialExperiment?.target_class_names),
    target_student_ids: normalizeStringArray(initialExperiment?.target_student_ids),
  }));
  const [targets, setTargets] = useState({ classes: [], students: [] });
  const [loadingTargets, setLoadingTargets] = useState(false);
  const [studentKeyword, setStudentKeyword] = useState('');
  const [files, setFiles] = useState([]);
  const [saving, setSaving] = useState(false);
  const normalizedCourseId = String(course?.id || '').trim();

  useEffect(() => {
    let cancelled = false;
    const loadTargets = async () => {
      if (!username || !normalizedCourseId) {
        setTargets({ classes: [], students: [] });
        return;
      }
      setLoadingTargets(true);
      try {
        const loadCourseStudents = async () => {
          const pageSize = 100;
          let page = 1;
          let total = 0;
          const students = [];
          const seen = new Set();

          do {
            const res = await axios.get(
              `${API_BASE_URL}/api/teacher/courses/${encodeURIComponent(normalizedCourseId)}/students`,
              {
                params: {
                  teacher_username: username,
                  page,
                  page_size: pageSize,
                },
              }
            );
            const payload = res.data || {};
            const items = Array.isArray(payload?.items) ? payload.items : [];
            total = Number(payload?.total || 0);

            items.forEach((item) => {
              const studentId = String(item?.student_id || '').trim();
              if (!studentId) return;
              const key = studentId.toLowerCase();
              if (seen.has(key)) return;
              seen.add(key);
              students.push({
                student_id: studentId,
                real_name: String(item?.real_name || '').trim(),
                class_name: String(item?.class_name || '').trim(),
              });
            });

            if (items.length === 0) break;
            page += 1;
          } while (students.length < total);

          return students;
        };

        const [classRes, students] = await Promise.all([
          axios.get(`${API_BASE_URL}/api/teacher/courses/${encodeURIComponent(normalizedCourseId)}/students/classes`, {
            params: { teacher_username: username },
          }),
          loadCourseStudents(),
        ]);

        const classNames = normalizeStringArray(
          (Array.isArray(classRes.data) ? classRes.data : []).map((item) => String(item?.label || item?.value || '').trim())
        );
        if (cancelled) return;
        setTargets({
          classes: classNames.map((name) => ({ id: name, name })),
          students,
        });
      } catch (error) {
        if (!cancelled) setTargets({ classes: [], students: [] });
      } finally {
        if (!cancelled) setLoadingTargets(false);
      }
    };

    loadTargets();
    return () => {
      cancelled = true;
    };
  }, [normalizedCourseId, username]);

  const classes = Array.isArray(targets?.classes) ? targets.classes : [];
  const filteredStudents = useMemo(() => {
    const students = Array.isArray(targets?.students) ? targets.students : [];
    const needle = String(studentKeyword || '').trim().toLowerCase();
    if (!needle) return students;
    return students.filter((item) => {
      const sid = String(item?.student_id || '').toLowerCase();
      const realName = String(item?.real_name || '').toLowerCase();
      const className = String(item?.class_name || '').toLowerCase();
      return sid.includes(needle) || realName.includes(needle) || className.includes(needle);
    });
  }, [targets?.students, studentKeyword]);

  const onFileChange = (event) => {
    const next = Array.from(event.target.files || []);
    setFiles((prev) => {
      const keys = new Set(prev.map((file) => `${file.name}-${file.size}`));
      return [...prev, ...next.filter((file) => !keys.has(`${file.name}-${file.size}`))];
    });
    event.target.value = '';
  };

  const removeFile = (idx) => setFiles((prev) => prev.filter((_, i) => i !== idx));

  const toggleClass = (name) => {
    const normalizedName = String(name || '').trim();
    if (!normalizedName) return;
    setFormData((prev) => ({
      ...prev,
      target_class_names: prev.target_class_names.includes(normalizedName)
        ? prev.target_class_names.filter((item) => item !== normalizedName)
        : [...prev.target_class_names, normalizedName],
    }));
  };

  const toggleStudent = (studentId) => {
    const normalizedStudentId = String(studentId || '').trim();
    if (!normalizedStudentId) return;
    setFormData((prev) => ({
      ...prev,
      target_student_ids: prev.target_student_ids.includes(normalizedStudentId)
        ? prev.target_student_ids.filter((item) => item !== normalizedStudentId)
        : [...prev.target_student_ids, normalizedStudentId],
    }));
  };

  const submit = async (event) => {
    event.preventDefault();
    if (saving) return;

    if (formData.published && formData.publish_scope === 'class' && formData.target_class_names.length === 0) {
      alert('\u8bf7\u81f3\u5c11\u9009\u62e9\u4e00\u4e2a\u73ed\u7ea7');
      return;
    }
    if (formData.published && formData.publish_scope === 'student' && formData.target_student_ids.length === 0) {
      alert('\u8bf7\u81f3\u5c11\u9009\u62e9\u4e00\u4e2a\u5b66\u751f');
      return;
    }

    setSaving(true);
    try {
      const experiment = isEdit
        ? await onUpdate(course, initialExperiment, formData)
        : await onCreate(course, formData);

      let uploadError = null;
      if (experiment?.id && files.length > 0) {
        try {
          const data = new FormData();
          files.forEach((file) => data.append('files', file));
          await axios.post(`${API_BASE_URL}/api/teacher/experiments/${experiment.id}/attachments`, data, {
            headers: { 'Content-Type': 'multipart/form-data' },
          });
        } catch (error) {
          uploadError = error;
        }
      }

      if (uploadError) {
        alert(`\u5b9e\u9a8c\u5df2\u4fdd\u5b58\uff0c\u4f46\u9644\u4ef6\u4e0a\u4f20\u5931\u8d25\uff1a${getErrorMessage(uploadError, '\u8bf7\u7a0d\u540e\u91cd\u8bd5')}`);
        onClose();
        return;
      }

      alert(isEdit ? '\u5b9e\u9a8c\u66f4\u65b0\u6210\u529f' : '\u5b9e\u9a8c\u521b\u5efa\u6210\u529f');
      onClose();
    } catch (error) {
      console.error('save experiment failed', error);
      alert(getErrorMessage(error, isEdit ? '\u66f4\u65b0\u5b9e\u9a8c\u5931\u8d25' : '\u521b\u5efa\u5b9e\u9a8c\u5931\u8d25'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(event) => event.stopPropagation()}>
        <h2>{isEdit ? '\u7f16\u8f91\u5b9e\u9a8c' : `\u65b0\u5efa\u5b9e\u9a8c\uff1a${course?.name || ''}`}</h2>
        <form onSubmit={submit}>
          <div className="form-group">
            <label htmlFor="experiment-course-name">{'\u6240\u5c5e\u8bfe\u7a0b'}</label>
            <input id="experiment-course-name" type="text" value={course?.name || ''} disabled />
          </div>
          <div className="form-group">
            <label htmlFor="experiment-title">{'\u5b9e\u9a8c\u6807\u9898'}</label>
            <input
              id="experiment-title"
              type="text"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              placeholder={'\u8bf7\u8f93\u5165\u5b9e\u9a8c\u6807\u9898'}
              required
            />
          </div>
          <div className="form-group">
            <label htmlFor="experiment-description">{'\u5b9e\u9a8c\u63cf\u8ff0'}</label>
            <textarea
              id="experiment-description"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder={'\u8bf7\u8f93\u5165\u5b9e\u9a8c\u63cf\u8ff0'}
            />
          </div>
          <div className="form-group">
            <label htmlFor="experiment-difficulty">{'\u96be\u5ea6'}</label>
            <select
              id="experiment-difficulty"
              value={formData.difficulty}
              onChange={(e) => setFormData({ ...formData, difficulty: e.target.value })}
            >
              <option value={'\u521d\u7ea7'}>{'\u521d\u7ea7'}</option>
              <option value={'\u4e2d\u7ea7'}>{'\u4e2d\u7ea7'}</option>
              <option value={'\u9ad8\u7ea7'}>{'\u9ad8\u7ea7'}</option>
            </select>
          </div>
          <div className="form-group">
            <label htmlFor="experiment-tags">{'\u6807\u7b7e\uff08\u9017\u53f7\u5206\u9694\uff09'}</label>
            <input
              id="experiment-tags"
              type="text"
              value={formData.tags}
              onChange={(e) => setFormData({ ...formData, tags: e.target.value })}
              placeholder={'\u4f8b\u5982\uff1aPython\uff0c\u5faa\u73af\uff0c\u5217\u8868'}
            />
          </div>
          <div className="form-group">
            <label htmlFor="experiment-notebook">{'Notebook \u8def\u5f84'}</label>
            <input id="experiment-notebook" type="text" value={formData.notebook_path} onChange={(e) => setFormData({ ...formData, notebook_path: e.target.value })} placeholder="course/example.ipynb" />
          </div>
          <div className="form-group">
            <label htmlFor="experiment-attachments">{'\u4e0a\u4f20\u9644\u4ef6\uff08\u53ef\u591a\u9009\uff09'}</label>
            <input id="experiment-attachments" type="file" multiple onChange={onFileChange} />
            {files.length > 0 ? (
              <ul className="teacher-lab-upload-list">
                {files.map((file, index) => (
                  <li key={`${file.name}-${file.size}`}>
                    <span>{file.name}</span>
                    <button type="button" onClick={() => removeFile(index)}>{'\u5220\u9664'}</button>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>

          <div className="form-group checkbox">
            <label htmlFor="experiment-published">
              <input id="experiment-published" type="checkbox" checked={formData.published} onChange={(e) => setFormData({ ...formData, published: e.target.checked })} />
              {'\u7acb\u5373\u53d1\u5e03\u7ed9\u5b66\u751f'}
            </label>
          </div>

          {formData.published ? (
            <>
              <div className="form-group">
                <label>{'\u53d1\u5e03\u8303\u56f4'}</label>
                <div className="publish-scope-row">
                  <label><input type="radio" name="edit-publish-scope" checked={formData.publish_scope === 'all'} onChange={() => setFormData({ ...formData, publish_scope: 'all', target_class_names: [], target_student_ids: [] })} /> {'\u5168\u90e8\u5b66\u751f'}</label>
                  <label><input type="radio" name="edit-publish-scope" checked={formData.publish_scope === 'class'} onChange={() => setFormData({ ...formData, publish_scope: 'class', target_student_ids: [] })} /> {'\u6307\u5b9a\u73ed\u7ea7'}</label>
                  <label><input type="radio" name="edit-publish-scope" checked={formData.publish_scope === 'student'} onChange={() => setFormData({ ...formData, publish_scope: 'student', target_class_names: [] })} /> {'\u6307\u5b9a\u5b66\u751f'}</label>
                </div>
              </div>

              {formData.publish_scope === 'class' ? (
                <div className="form-group">
                  <label>{`\u9009\u62e9\u73ed\u7ea7\uff08\u5df2\u9009 ${formData.target_class_names.length}\uff09`}</label>
                  {loadingTargets ? (
                    <div className="publish-target-loading">{'\u6b63\u5728\u52a0\u8f7d\u53ef\u9009\u73ed\u7ea7...'}</div>
                  ) : (
                    <div className="publish-target-list">
                      {classes.length === 0 ? (
                        <div className="publish-target-empty">{'\u6682\u65e0\u53ef\u9009\u73ed\u7ea7'}</div>
                      ) : (
                        classes.map((item) => {
                          const name = String(item?.name || '').trim();
                          return (
                            <label key={item?.id || name}>
                              <input type="checkbox" checked={formData.target_class_names.includes(name)} onChange={() => toggleClass(name)} />
                              <span>{name}</span>
                            </label>
                          );
                        })
                      )}
                    </div>
                  )}
                </div>
              ) : null}

              {formData.publish_scope === 'student' ? (
                <div className="form-group">
                  <label>{`\u9009\u62e9\u5b66\u751f\uff08\u5df2\u9009 ${formData.target_student_ids.length}\uff09`}</label>
                  <input
                    type="text"
                    value={studentKeyword}
                    onChange={(event) => setStudentKeyword(event.target.value)}
                    placeholder={'\u8bf7\u8f93\u5165\u5b66\u53f7/\u59d3\u540d/\u73ed\u7ea7\u5173\u952e\u5b57'}
                  />
                  {loadingTargets ? (
                    <div className="publish-target-loading">{'\u6b63\u5728\u52a0\u8f7d\u53ef\u9009\u5b66\u751f...'}</div>
                  ) : (
                    <div className="publish-target-list">
                      {filteredStudents.length === 0 ? (
                        <div className="publish-target-empty">{'\u6682\u65e0\u53ef\u9009\u5b66\u751f'}</div>
                      ) : (
                        filteredStudents.map((item) => {
                          const studentId = String(item?.student_id || '').trim();
                          const realName = String(item?.real_name || '').trim();
                          const className = String(item?.class_name || '').trim();
                          return (
                            <label key={studentId}>
                              <input type="checkbox" checked={formData.target_student_ids.includes(studentId)} onChange={() => toggleStudent(studentId)} />
                              <span>{`${studentId}${realName ? ` \u00b7 ${realName}` : ''}${className ? ` \u00b7 ${className}` : ''}`}</span>
                            </label>
                          );
                        })
                      )}
                    </div>
                  )}
                </div>
              ) : null}
            </>
          ) : null}

          <div className="form-actions">
            <button type="button" onClick={onClose} disabled={saving}>{'\u53d6\u6d88'}</button>
            <button type="submit" disabled={saving}>{saving ? '\u4fdd\u5b58\u4e2d...' : (isEdit ? '\u4fdd\u5b58\u4fee\u6539' : '\u521b\u5efa\u5b9e\u9a8c')}</button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default ExperimentEditorModal;
